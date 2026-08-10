"""Live connections to a running novem computer.

A computer exposes one multiplexed WebSocket — ``novem.compute.v1`` on
``/ws-cu`` — carrying independent channels. This module implements the
client side of that protocol:

    c = Computer("box")

    # one-off command, buffered
    res = c.run(["ls", "-la"], cwd="/home/user")
    print(res.stdout, res.code)

    # streamed straight to local stdout/stderr
    code, signal = c.stream(["tail", "-f", "/var/log/app.log"])

    # interactive shell (takes over the terminal)
    c.shell()

Text control messages are strict JSON, and byte data uses a single binary
layout::

    byte 0       stream discriminator (0 pty/tcp + all client input,
                                       1 exec stdout, 2 exec stderr)
    bytes 1..16  raw 128-bit channel id
    bytes 17..   payload, 1..65536 bytes

Channels are opened with a caller-generated ``request_id`` and answered with
``ready`` (carrying an opaque channel id) or a scoped ``error``. A denied open
leaves sibling channels usable; a protocol violation closes the connection.
"""

import asyncio
import base64
import json
import os
import secrets
import sys
import threading
from dataclasses import dataclass
from typing import IO, Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from urllib.parse import urlparse

from novem.exceptions import NovemException

PROTOCOL = "novem.compute.v1"
PATH = "/ws-cu"
MAX_DATA_BYTES = 64 * 1024
BINARY_HEADER = 17
MAX_MESSAGE_BYTES = 128 * 1024
HELLO_TIMEOUT_SECONDS = 10.0

# stream discriminators
STREAM_DATA = 0  # pty/tcp bytes, and every client-to-server frame
STREAM_STDOUT = 1
STREAM_STDERR = 2

# Error codes documented when this client was released. This set is
# informational: a server may add codes during a rolling upgrade, so unknown
# codes must pass through as terminal, non-retryable errors.
ERROR_CODES = frozenset(
    {
        "invalid_request",
        "not_found",
        "not_running",
        "limit_exceeded",
        "agent_upgrade_required",
        "authorization_revoked",
        "computer_restarted",
        "timeout",
        "backpressure_timeout",
        "upstream_unavailable",
        "process_start_failed",
        "connection_failed",
        "protocol_error",
    }
)

# Codes worth retrying against the same target: a computer that has just been
# told to boot answers these until its agent is reachable.
RETRYABLE_CODES = frozenset({"not_running", "upstream_unavailable", "timeout"})

SIGNALS = frozenset({"HUP", "INT", "QUIT", "TERM", "KILL"})
StdinSource = Union[str, bytes, bytearray, IO[Any]]


class NovemComputeError(NovemException):
    """A scoped error from the compute protocol.

    Known codes may receive client hints or be retried during admission.
    Unknown codes remain terminal so newer servers stay compatible with older
    clients.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE_CODES

    @property
    def cli_message(self) -> str:
        hint = _HINTS.get(self.code)
        base = self.message or self.code
        return f"{base}\n{hint}" if hint else base


class NovemComputeTransportError(NovemException):
    """The compute connection failed without a remote command exit status."""

    def __init__(
        self,
        message: str,
        close_code: Optional[int] = None,
        *,
        code: str = "connection_failed",
        retryable: bool = False,
        retry_after: Optional[float] = None,
    ) -> None:
        self.close_code = close_code
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after
        self._retry_after_exceeds_timeout = False
        detail = f"{message} (WebSocket close code {close_code})" if close_code is not None else message
        super().__init__(detail)

    @property
    def cli_message(self) -> str:
        base = str(self)
        if self._retry_after_exceeds_timeout:
            return (
                f"{base}\nThe service requested a retry delay longer than --connect-timeout allows. "
                "Increase --connect-timeout and try again."
            )
        # Close-frame messages are curated for the specific close code and
        # already contain any action the user can take.
        if self.close_code is not None:
            return base
        hint = _HINTS.get(self.code)
        if not hint:
            return base
        base_key = base.casefold().strip().rstrip(".")
        hint_key = hint.casefold().strip().rstrip(".")
        if hint_key in base_key or base_key in hint_key:
            return base
        return f"{base}\n{hint}"


_HINTS = {
    "invalid_request": "The compute request was rejected. Check the options and upgrade the CLI if it persists.",
    # A missing entitlement, no access, and no such computer are
    # deliberately indistinguishable — never claim "permission denied".
    "not_found": "The computer was not found, or you do not have access to it.",
    "not_running": "The computer is not running. Start it with: novem -c <name> -w status online",
    "agent_upgrade_required": "The computer is running an older agent. Restart it to pick up the new one.",
    "limit_exceeded": "The service is busy. Wait briefly and try again.",
    "upstream_unavailable": "The compute service is temporarily unavailable.",
    "authorization_revoked": "Authorization for the session ended. Connect again.",
    "computer_restarted": "The computer restarted during the session. Connect again.",
    "timeout": "The operation timed out.",
    "backpressure_timeout": "The data stream stalled. Wait briefly and try again.",
    "process_start_failed": "The command could not be started.",
    "connection_failed": "The connection to the computer failed.",
    "protocol_error": "The compute protocol was rejected. Upgrade the CLI and try again.",
}


_CLOSE_REASONS = {
    1001: ("session_ended", "The compute session ended."),
    1008: ("protocol_error", "The compute protocol was rejected. Upgrade the CLI and try again."),
    1011: ("upstream_unavailable", "The compute service ended the session."),
}


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    """Parse an HTTP Retry-After delay or date into seconds from now."""

    if not value:
        return None
    value = value.strip()
    try:
        seconds = int(value)
    except ValueError:
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime

        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    if seconds < 0:
        return None
    try:
        return float(seconds)
    except OverflowError:
        return None


@dataclass
class Hello:
    """The server's opening message, carrying negotiated limits."""

    protocol: str
    max_channels: int
    max_data_bytes: int
    heartbeat_seconds: int


@dataclass
class ExecResult:
    """The outcome of a buffered :meth:`Computer.run`."""

    code: int
    signal: Optional[str]
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0 and self.signal is None


def _channel_bytes(channel: str) -> bytes:
    """22-char unpadded base64url -> the raw 16 bytes."""
    return base64.urlsafe_b64decode(channel + "==")


def _channel_str(raw: bytes) -> str:
    """The raw 16 bytes -> 22-char unpadded base64url."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def encode_frame(channel: str, payload: bytes, stream: int = STREAM_DATA) -> bytes:
    if not payload:
        raise ValueError("empty data frames are invalid")
    if len(payload) > MAX_DATA_BYTES:
        raise ValueError(f"payload exceeds {MAX_DATA_BYTES} bytes")
    return bytes([stream]) + _channel_bytes(channel) + payload


def decode_frame(data: bytes) -> Tuple[int, str, bytes]:
    if len(data) <= BINARY_HEADER:
        raise ValueError("binary frame is too short")
    return data[0], _channel_str(data[1:BINARY_HEADER]), data[BINARY_HEADER:]


def ws_url(api_root: str) -> str:
    """Derive the compute endpoint from the configured api root.

    ``/ws-cu`` is served at the host root rather than under ``/v1``, and the
    path must match exactly — no trailing slash, query or fragment.
    """
    parsed = urlparse(api_root)
    if parsed.scheme not in ("http", "https", "ws", "wss") or not parsed.netloc:
        raise ValueError("api_root must include an http:// or https:// scheme and host")
    scheme = "wss" if parsed.scheme in ("https", "wss") else "ws"
    return f"{scheme}://{parsed.netloc}{PATH}"


def target_for(owner: str, computer: str) -> str:
    """The canonical target: the owner is always spelled out.

    The short ``/v1/code/computers/<name>`` form is not accepted here.
    """
    return f"/v1/users/{owner}/code/computers/{computer}"


class Channel:
    """One open channel on a :class:`ComputeConnection`."""

    def __init__(self, conn: "ComputeConnection", channel: str, kind: str) -> None:
        self._conn = conn
        self.id = channel
        self.kind = kind
        self._queue: "asyncio.Queue[Optional[Tuple[int, bytes]]]" = asyncio.Queue()
        self._exit: "asyncio.Future[Tuple[int, Optional[str]]]" = asyncio.get_event_loop().create_future()
        self._closed = False

    # -- inbound, driven by the connection's read loop ---------------------

    def _feed(self, stream: int, data: bytes) -> None:
        self._queue.put_nowait((stream, data))

    def _finish(self, code: int, signal: Optional[str]) -> None:
        if not self._exit.done():
            self._exit.set_result((code, signal))
        self._queue.put_nowait(None)

    def _fail(self, err: NovemComputeError) -> None:
        if not self._exit.done():
            self._exit.set_exception(err)
        self._queue.put_nowait(None)

    def _closed_by_server(self) -> None:
        self._closed = True
        if not self._exit.done():
            self._exit.set_result((0, None))
        self._queue.put_nowait(None)

    # -- outbound ----------------------------------------------------------

    async def send(self, payload: bytes) -> None:
        """Write bytes to the channel's stdin (or the TCP stream)."""
        chunk_size = self._conn.max_data_bytes
        for i in range(0, len(payload), chunk_size):
            await self._conn._send_binary(encode_frame(self.id, payload[i : i + chunk_size]))

    async def stdin_eof(self) -> None:
        """Close stdin without closing the channel.

        On a PTY this writes Ctrl-D rather than closing the master, and
        sending it twice is a protocol violation.
        """
        await self._conn._send_json({"type": "stdin_eof", "channel": self.id})

    async def resize(self, rows: int, cols: int) -> None:
        if self.kind != "pty":
            raise ValueError("resize is only valid on a pty channel")
        await self._conn._send_json({"type": "resize", "channel": self.id, "rows": rows, "cols": cols})

    async def signal(self, name: str) -> None:
        if name not in SIGNALS:
            raise ValueError(f"signal must be one of {sorted(SIGNALS)}")
        await self._conn._send_json({"type": "signal", "channel": self.id, "signal": name})

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._conn._send_json({"type": "close", "channel": self.id})

    # -- consumption -------------------------------------------------------

    async def __aiter__(self) -> AsyncIterator[Tuple[int, bytes]]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def wait(self) -> Tuple[int, Optional[str]]:
        """Await termination, returning ``(code, signal)``.

        The wire carries the exit code as a signed 32-bit value: a process
        killed by a signal reports ``-1`` with a non-null signal name.
        """
        return await self._exit


class ComputeConnection:
    """A live ``novem.compute.v1`` connection.

    Use as an async context manager; channels opened on it are multiplexed
    over the single socket.
    """

    def __init__(self, url: str, token: str, ignore_ssl: bool = False, debug: bool = False) -> None:
        self._url = url
        self._token = token
        self._ignore_ssl = ignore_ssl
        self._debug = debug
        self._ws: Any = None
        self._session: Any = None
        self._reader: Optional["asyncio.Task[None]"] = None
        self._watchdog: Optional["asyncio.Task[None]"] = None
        self.hello: Optional[Hello] = None
        self.max_data_bytes = MAX_DATA_BYTES
        self._receive_max_data_bytes = MAX_DATA_BYTES
        self._last_inbound = 0.0
        self._channels: Dict[str, Channel] = {}
        self._pending: Dict[str, "asyncio.Future[Channel]"] = {}
        self._fatal: Optional[BaseException] = None
        self._hello_event: Optional[asyncio.Event] = None

    # -- lifecycle ---------------------------------------------------------

    @staticmethod
    def _aiohttp() -> Any:
        try:
            import aiohttp
        except ImportError:
            raise ImportError("The compute extra is required. Install with: pip install 'novem[compute]'") from None
        return aiohttp

    async def __aenter__(self) -> "ComputeConnection":
        aiohttp = self._aiohttp()

        if not self._token:
            raise NovemException("No authentication token found. Run novem --init first.")

        # A native client must not send Origin: it is self-asserted and
        # therefore neither required nor trusted by the server.
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(
                self._url,
                protocols=(PROTOCOL,),
                headers={"Authorization": f"Bearer {self._token}"},
                max_msg_size=MAX_MESSAGE_BYTES,
                ssl=False if self._ignore_ssl else True,
                autoping=False,
            )
            if self._ws.protocol != PROTOCOL:
                raise NovemComputeTransportError("compute connection did not negotiate the expected protocol")

            if self._debug:
                print(f"WS: {self._url} ({PROTOCOL})", file=sys.stderr)

            self._hello_event = asyncio.Event()
            self._last_inbound = asyncio.get_running_loop().time()
            self._reader = asyncio.create_task(self._read_loop())
            await self._await_hello()
            self._watchdog = asyncio.create_task(self._watch_liveness())
            if self._fatal is not None:
                raise self._fatal
            return self
        except NovemComputeTransportError:
            await self.aclose()
            raise
        except aiohttp.WSServerHandshakeError as e:
            await self.aclose()
            headers = getattr(e, "headers", None)
            retry_after = _retry_after_seconds(headers.get("Retry-After") if headers is not None else None)
            if e.status == 429:
                raise NovemComputeTransportError(
                    "compute connection is temporarily at capacity",
                    code="limit_exceeded",
                    retryable=True,
                    retry_after=retry_after,
                ) from e
            if e.status == 503:
                raise NovemComputeTransportError(
                    "compute service is temporarily unavailable",
                    code="upstream_unavailable",
                    retryable=True,
                    retry_after=retry_after,
                ) from e
            raise NovemComputeTransportError(f"compute connection could not be established (HTTP {e.status})") from e
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            await self.aclose()
            raise NovemComputeTransportError("compute connection could not be established") from e
        except BaseException:
            await self.aclose()
            raise

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
            try:
                await self._watchdog
            except (asyncio.CancelledError, Exception):
                pass
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws is not None:
            await self._ws.close()
        if self._session is not None:
            await self._session.close()

    async def _await_hello(self) -> None:
        # Clients must wait for and validate hello before opening channels.
        assert self._hello_event is not None
        try:
            await asyncio.wait_for(self._hello_event.wait(), timeout=HELLO_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            raise NovemComputeTransportError("compute connection did not send hello") from None
        if self._fatal is not None:
            raise self._fatal
        if self.hello is None:
            raise NovemComputeTransportError("compute connection did not send hello")

    # -- plumbing ----------------------------------------------------------

    async def _send_json(self, message: Dict[str, Any]) -> None:
        if self._fatal is not None:
            raise self._fatal
        await self._ws.send_str(json.dumps(message))

    async def _send_binary(self, frame: bytes) -> None:
        if self._fatal is not None:
            raise self._fatal
        await self._ws.send_bytes(frame)

    async def _read_loop(self) -> None:
        aiohttp = self._aiohttp()
        try:
            async for msg in self._ws:
                self._last_inbound = asyncio.get_running_loop().time()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._on_text(json.loads(msg.data))
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    stream, channel, payload = decode_frame(msg.data)
                    if len(payload) > self._receive_max_data_bytes:
                        raise ValueError("binary frame exceeds the negotiated payload limit")
                    ch = self._channels.get(channel)
                    if ch is not None:
                        ch._feed(stream, payload)
                elif msg.type == aiohttp.WSMsgType.PING:
                    await self._ws.pong(msg.data)
                elif msg.type == aiohttp.WSMsgType.PONG:
                    continue
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - exact transport failure varies by platform
            self._abort(NovemComputeTransportError("compute connection failed"))
            return
        close_code = getattr(self._ws, "close_code", None)
        reason, message = _CLOSE_REASONS.get(
            close_code or 0,
            ("connection_failed", "The connection to the computer was lost."),
        )
        self._abort(NovemComputeTransportError(message, close_code, code=reason))

    async def _watch_liveness(self) -> None:
        """Fail a connection whose advertised heartbeat has gone silent."""

        assert self.hello is not None
        heartbeat = float(self.hello.heartbeat_seconds)
        interval = max(0.05, heartbeat)
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(interval)
            if loop.time() - self._last_inbound <= heartbeat * 2:
                continue
            self._abort(NovemComputeTransportError("The connection to the computer stopped responding."))
            if self._ws is not None:
                await self._ws.close()
            return

    def _abort(self, err: BaseException) -> None:
        if self._fatal is not None:
            return
        self._fatal = err
        if self._hello_event is not None:
            self._hello_event.set()
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()
        for ch in list(self._channels.values()):
            if not ch._exit.done():
                ch._exit.set_exception(err)
            ch._queue.put_nowait(None)

    def _on_text(self, msg: Dict[str, Any]) -> None:
        kind = msg.get("type")

        if kind == "hello":
            hello = Hello(
                protocol=msg.get("protocol", ""),
                max_channels=int(msg.get("max_channels", 0)),
                max_data_bytes=int(msg.get("max_data_bytes", 0)),
                heartbeat_seconds=int(msg.get("heartbeat_seconds", 0)),
            )
            if hello.protocol != PROTOCOL:
                self._abort(NovemComputeTransportError(f"unexpected compute protocol {hello.protocol!r}"))
                return
            if hello.max_channels <= 0:
                self._abort(NovemComputeTransportError("compute connection sent an invalid channel limit"))
                return
            if hello.max_data_bytes <= 0 or hello.max_data_bytes + BINARY_HEADER > MAX_MESSAGE_BYTES:
                self._abort(NovemComputeTransportError("compute connection sent an invalid payload limit"))
                return
            if hello.heartbeat_seconds <= 0:
                self._abort(NovemComputeTransportError("compute connection sent an invalid heartbeat interval"))
                return
            self.hello = hello
            self.max_data_bytes = min(MAX_DATA_BYTES, hello.max_data_bytes)
            self._receive_max_data_bytes = hello.max_data_bytes
            if self._hello_event is not None:
                self._hello_event.set()
            return

        if kind == "ready":
            request_id = msg.get("request_id", "")
            fut = self._pending.get(request_id)
            if fut is None or fut.done():
                self._abort(NovemComputeTransportError("compute connection sent an unexpected ready message"))
                return
            channel_id = msg.get("channel")
            if not isinstance(channel_id, str):
                self._abort(NovemComputeTransportError("compute connection sent an invalid ready message"))
                return
            try:
                valid_channel = len(_channel_bytes(channel_id)) == 16
            except Exception:
                valid_channel = False
            if not valid_channel:
                self._abort(NovemComputeTransportError("compute connection sent an invalid ready message"))
                return
            self._pending.pop(request_id, None)
            channel = Channel(self, channel_id, msg.get("kind", ""))
            self._channels[channel.id] = channel
            fut.set_result(channel)
            return

        if kind == "error":
            code = msg.get("code", "protocol_error")
            err = NovemComputeError(code, msg.get("message", code))
            # before ready the error carries request_id, after it a channel
            rid = msg.get("request_id")
            if rid is not None:
                fut = self._pending.pop(rid, None)
                if fut is not None and not fut.done():
                    fut.set_exception(err)
                return
            ch = self._channels.get(msg.get("channel", ""))
            if ch is not None:
                ch._fail(err)
                self._channels.pop(ch.id, None)
            return

        if kind == "exit":
            ch = self._channels.get(msg.get("channel", ""))
            if ch is not None:
                ch._finish(int(msg.get("code", 0)), msg.get("signal"))
                self._channels.pop(ch.id, None)
            return

        if kind == "closed":
            ch = self._channels.get(msg.get("channel", ""))
            if ch is not None:
                ch._closed_by_server()
                self._channels.pop(ch.id, None)
            return

    # -- opening channels --------------------------------------------------

    async def _open(self, spec: Dict[str, Any]) -> Channel:
        if self.hello is not None and len(self._channels) + len(self._pending) >= self.hello.max_channels:
            raise NovemComputeError("limit_exceeded", "The connection has reached its channel limit")
        request_id = spec["request_id"]
        fut: "asyncio.Future[Channel]" = asyncio.get_event_loop().create_future()
        self._pending[request_id] = fut
        try:
            await self._send_json(spec)
            return await fut
        except BaseException:
            self._pending.pop(request_id, None)
            if not fut.done():
                fut.cancel()
            raise

    async def open_exec(
        self,
        target: str,
        command: str,
        args: Optional[List[str]] = None,
        mode: str = "argv",
        cwd: str = "",
        timeout_seconds: int = 600,
    ) -> Channel:
        if mode not in ("argv", "shell"):
            raise ValueError('mode must be "argv" or "shell"')
        if mode == "shell" and args:
            raise ValueError("shell mode does not accept args")
        if mode == "argv" and "/" in command and not command.startswith("/"):
            raise ValueError("a relative executable path is invalid; use an absolute path")
        if cwd and not cwd.startswith("/"):
            raise ValueError("cwd must be absolute")
        return await self._open(
            {
                "type": "open",
                "request_id": _request_id(),
                "target": target,
                "kind": "exec",
                "mode": mode,
                "command": command,
                "args": list(args or []),
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
            }
        )

    async def open_pty(
        self,
        target: str,
        rows: int = 24,
        cols: int = 80,
        timeout_seconds: int = 28800,
    ) -> Channel:
        return await self._open(
            {
                "type": "open",
                "request_id": _request_id(),
                "target": target,
                "kind": "pty",
                "rows": max(1, min(1000, rows)),
                "cols": max(1, min(1000, cols)),
                "timeout_seconds": timeout_seconds,
            }
        )


def _request_id() -> str:
    return f"np-{secrets.token_hex(8)}"


# ── sync helpers used by the CLI and by simple library callers ────────────


def _run_sync(coro: Any) -> Any:
    """Drive a coroutine from synchronous code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise NovemException(
        "A compute call was made from inside a running event loop. " "Use the async API (Computer.connect()) instead."
    )


def _split_argv(argv: Any, mode: str) -> Tuple[str, List[str]]:
    """Split a caller's invocation into ``(command, args)``.

    In argv mode a list is taken apart so arguments survive without shell
    re-parsing; in shell mode the command is one string and args are refused.
    """
    if mode == "shell":
        if not isinstance(argv, str):
            raise ValueError("shell mode takes a single command string")
        return argv, []
    if isinstance(argv, str):
        return argv, []
    if not argv:
        raise ValueError("a command is required")
    return argv[0], list(argv[1:])


async def _with_retry(
    open_channel: Any,
    use_channel: Any,
    connect: Any,
    retry_seconds: float,
    on_retry: Optional[Callable[[NovemException], None]] = None,
) -> Any:
    """Open and use a channel, retrying only failed admission attempts.

    A computer that has just been told to boot reports ``not_running`` (and
    friends) until its agent is reachable, so a bounded retry turns the boot
    race into a wait rather than a failure. Once a channel is ready,
    ``use_channel`` runs outside the retry handler so an interrupted command is
    never replayed.
    """
    import time

    deadline = time.monotonic() + max(0.0, retry_seconds)
    delay = 0.5
    notified = False

    def notify(error: NovemException) -> None:
        nonlocal notified
        if on_retry is not None and not notified:
            on_retry(error)
        notified = True

    async def wait_before_retry(error: NovemException) -> bool:
        """Wait for local backoff and any longer server-requested delay."""

        nonlocal delay
        remaining = max(0.0, deadline - time.monotonic())
        retry_after = getattr(error, "retry_after", None)
        wait = max(delay, retry_after or 0.0)
        if retry_after is not None and retry_after > remaining:
            if isinstance(error, NovemComputeTransportError):
                error._retry_after_exceeds_timeout = True
            return False
        notify(error)
        await asyncio.sleep(min(wait, remaining))
        delay = min(delay * 1.5, 3.0)
        return True

    # Retrying a failed upgrade is safe because no open request was sent. Once
    # connected, explicit admission errors reuse that connection; a transport
    # failure after an open request is never replayed because readiness may
    # have been lost in transit.
    while True:
        context = connect()
        try:
            conn = await context.__aenter__()
        except NovemComputeTransportError as e:
            if not e.retryable or time.monotonic() >= deadline:
                raise
            if not await wait_before_retry(e):
                raise
            continue
        break

    try:
        while True:
            try:
                channel = await open_channel(conn)
            except NovemComputeError as e:
                if not e.retryable or time.monotonic() >= deadline:
                    raise
                if not await wait_before_retry(e):
                    raise
            else:
                return await use_channel(channel)
    finally:
        await context.__aexit__(*sys.exc_info())


async def _pump_stdin(ch: Channel, stdin: Optional[StdinSource]) -> None:
    """Forward stdin incrementally without blocking the event loop.

    File reads run in one bounded daemon worker. At most one chunk waits
    locally while the previous chunk is written, and cancellation does not
    wait for a pipe producer that keeps its end open.
    """

    if stdin is None:
        await ch.stdin_eof()
        return
    if isinstance(stdin, str):
        if stdin:
            await ch.send(stdin.encode("utf-8"))
        await ch.stdin_eof()
        return
    if isinstance(stdin, (bytes, bytearray)):
        if stdin:
            await ch.send(bytes(stdin))
        await ch.stdin_eof()
        return

    loop = asyncio.get_running_loop()
    queue: "asyncio.Queue[Tuple[Any, Optional[BaseException]]]" = asyncio.Queue()
    may_read = threading.Event()
    stopped = threading.Event()
    may_read.set()

    def deliver(chunk: Any, error: Optional[BaseException]) -> bool:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, (chunk, error))
            return True
        except RuntimeError:
            return False

    def read_stdin() -> None:
        reader = getattr(stdin, "read1", stdin.read)
        while True:
            may_read.wait()
            may_read.clear()
            if stopped.is_set():
                return
            try:
                chunk = reader(MAX_DATA_BYTES)
            except BaseException as e:
                deliver(None, e)
                return
            if not deliver(chunk, None) or not chunk:
                return

    threading.Thread(target=read_stdin, name="novem-stdin", daemon=True).start()
    try:
        while True:
            chunk, error = await queue.get()
            if error is not None:
                raise error
            if not chunk:
                break
            payload = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
            if payload:
                await ch.send(payload)
            may_read.set()
        await ch.stdin_eof()
    finally:
        stopped.set()
        may_read.set()


_T = TypeVar("_T")


async def _use_channel_with_stdin(
    ch: Channel,
    stdin: Optional[StdinSource],
    consume: Callable[[], Awaitable[_T]],
) -> _T:
    """Pump input and consume output concurrently for one exec channel."""

    pump: "asyncio.Task[None]" = asyncio.create_task(_pump_stdin(ch, stdin))
    output: "asyncio.Future[_T]" = asyncio.ensure_future(consume())
    try:
        done, _ = await asyncio.wait((pump, output), return_when=asyncio.FIRST_COMPLETED)
        if pump in done:
            await pump
        return await output
    finally:
        for task in (pump, output):
            if not task.done():
                task.cancel()
        await asyncio.gather(pump, output, return_exceptions=True)


async def _with_sigint_forwarding(ch: Channel, operation: Callable[[], Awaitable[_T]]) -> _T:
    """Forward the first SIGINT to a command and abort locally on the second."""

    if os.name == "nt" or threading.current_thread() is not threading.main_thread():
        return await operation()

    import signal as signalmod

    loop = asyncio.get_running_loop()
    pending: "asyncio.Queue[str]" = asyncio.Queue()
    second_interrupt: "asyncio.Future[None]" = loop.create_future()
    interrupts = 0

    def on_sigint() -> None:
        nonlocal interrupts
        interrupts += 1
        if interrupts == 1:
            pending.put_nowait("INT")
        elif not second_interrupt.done():
            second_interrupt.set_result(None)

    previous = signalmod.getsignal(signalmod.SIGINT)
    try:
        loop.add_signal_handler(signalmod.SIGINT, on_sigint)
    except (NotImplementedError, RuntimeError, ValueError):  # pragma: no cover - platform/event-loop guard
        return await operation()

    async def forward() -> None:
        while True:
            await ch.signal(await pending.get())

    sender: "asyncio.Task[None]" = asyncio.create_task(forward())
    command: "asyncio.Future[_T]" = asyncio.ensure_future(operation())
    try:
        done, _ = await asyncio.wait((sender, command, second_interrupt), return_when=asyncio.FIRST_COMPLETED)
        if command in done:
            return await command
        if sender in done:
            await sender
        raise KeyboardInterrupt
    finally:
        loop.remove_signal_handler(signalmod.SIGINT)
        try:
            signalmod.signal(signalmod.SIGINT, previous)
        except (OSError, RuntimeError, ValueError):  # pragma: no cover - process teardown
            pass
        for task in (sender, command):
            if not task.done():
                task.cancel()
        if not second_interrupt.done():
            second_interrupt.cancel()
        await asyncio.gather(sender, command, return_exceptions=True)


async def _exec_collect_channel(ch: Channel, stdin: Optional[StdinSource]) -> ExecResult:
    """Collect output from an admitted exec channel."""

    async def collect() -> ExecResult:
        out: List[bytes] = []
        err: List[bytes] = []
        async for stream, data in ch:
            (err if stream == STREAM_STDERR else out).append(data)
        code, signal = await ch.wait()
        return ExecResult(
            code=code,
            signal=signal,
            stdout=b"".join(out).decode("utf-8", "replace"),
            stderr=b"".join(err).decode("utf-8", "replace"),
        )

    return await _use_channel_with_stdin(ch, stdin, collect)


async def _exec_collect(
    conn: ComputeConnection,
    target: str,
    command: str,
    args: List[str],
    mode: str,
    cwd: str,
    stdin: Optional[StdinSource],
    timeout_seconds: int,
) -> ExecResult:
    ch = await conn.open_exec(target, command, args, mode=mode, cwd=cwd, timeout_seconds=timeout_seconds)
    return await _exec_collect_channel(ch, stdin)


async def _exec_stream_channel(
    ch: Channel,
    stdin: Optional[StdinSource],
    forward_signals: bool = False,
) -> Tuple[int, Optional[str]]:
    """Stream output from an admitted exec channel to local stdout/stderr."""

    async def stream_output() -> Tuple[int, Optional[str]]:
        async for stream, data in ch:
            sink = sys.stderr.buffer if stream == STREAM_STDERR else sys.stdout.buffer
            sink.write(data)
            sink.flush()
        return await ch.wait()

    async def transfer() -> Tuple[int, Optional[str]]:
        return await _use_channel_with_stdin(ch, stdin, stream_output)

    if forward_signals:
        return await _with_sigint_forwarding(ch, transfer)
    return await transfer()


async def _exec_stream(
    conn: ComputeConnection,
    target: str,
    command: str,
    args: List[str],
    mode: str,
    cwd: str,
    stdin: Optional[StdinSource],
    timeout_seconds: int,
) -> Tuple[int, Optional[str]]:
    """Stream straight to local stdout/stderr and return the exit status."""
    ch = await conn.open_exec(target, command, args, mode=mode, cwd=cwd, timeout_seconds=timeout_seconds)
    return await _exec_stream_channel(ch, stdin)


async def _open_interactive_pty(conn: ComputeConnection, target: str) -> Channel:
    """Validate the local terminal and request an interactive PTY channel."""
    if os.name == "nt":  # pragma: no cover - platform guard
        raise NovemException("An interactive shell is not supported on Windows yet.")
    if not sys.stdin.isatty():
        raise NovemException("An interactive shell requires a terminal. Use -R to run a command instead.")

    try:
        size = os.get_terminal_size(sys.stdin.fileno())
    except OSError:
        size = os.terminal_size((80, 24))
    return await conn.open_pty(target, rows=size.lines, cols=size.columns)


async def _pty_interactive(ch: Channel) -> Tuple[int, Optional[str]]:
    """Attach the local terminal to an admitted PTY channel."""
    import signal as signalmod
    import termios
    import tty

    loop = asyncio.get_event_loop()
    fd = sys.stdin.fileno()
    try:
        saved = termios.tcgetattr(fd)
    except (OSError, termios.error) as e:
        raise NovemException("The local terminal became unavailable before the interactive shell was ready.") from e
    outbound: "asyncio.Queue[Tuple[str, Any]]" = asyncio.Queue()
    reader_registered = False
    stdin_ended = False

    def register_reader() -> None:
        nonlocal reader_registered
        if not reader_registered and not stdin_ended:
            loop.add_reader(fd, on_stdin)
            reader_registered = True

    def on_winch(*_: Any) -> None:
        try:
            new = os.get_terminal_size(fd)
        except OSError:
            new = os.terminal_size((80, 24))
        outbound.put_nowait(("resize", (new.lines, new.columns)))

    def on_stdin() -> None:
        nonlocal reader_registered, stdin_ended
        if reader_registered:
            loop.remove_reader(fd)
            reader_registered = False
        try:
            data = os.read(fd, 8192)
        except OSError:
            data = b""
        if not data:
            stdin_ended = True
            outbound.put_nowait(("eof", None))
            return
        outbound.put_nowait(("data", data))

    async def write_outbound() -> None:
        while True:
            kind, value = await outbound.get()
            if kind == "data":
                await ch.send(value)
                register_reader()
            elif kind == "resize":
                rows, cols = value
                await ch.resize(rows, cols)
            else:
                await ch.stdin_eof()

    async def read_remote() -> Tuple[int, Optional[str]]:
        async for _stream, data in ch:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        return await ch.wait()

    try:
        try:
            tty.setraw(fd)
        except (OSError, termios.error) as e:
            raise NovemException("The local terminal became unavailable before the interactive shell was ready.") from e
        loop.add_signal_handler(signalmod.SIGWINCH, on_winch)
        register_reader()

        writer = asyncio.create_task(write_outbound())
        remote = asyncio.create_task(read_remote())
        try:
            done, _ = await asyncio.wait((writer, remote), return_when=asyncio.FIRST_COMPLETED)
            if writer in done:
                await writer
            return await remote
        finally:
            for task in (writer, remote):
                if not task.done():
                    task.cancel()
            await asyncio.gather(writer, remote, return_exceptions=True)
    finally:
        if reader_registered:
            loop.remove_reader(fd)
        try:
            loop.remove_signal_handler(signalmod.SIGWINCH)
        except (NotImplementedError, RuntimeError):  # pragma: no cover
            pass
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        except (OSError, termios.error):  # terminal already hung up
            pass


__all__ = [
    "PROTOCOL",
    "PATH",
    "MAX_DATA_BYTES",
    "MAX_MESSAGE_BYTES",
    "STREAM_DATA",
    "STREAM_STDOUT",
    "STREAM_STDERR",
    "ERROR_CODES",
    "RETRYABLE_CODES",
    "NovemComputeError",
    "NovemComputeTransportError",
    "StdinSource",
    "Hello",
    "ExecResult",
    "Channel",
    "ComputeConnection",
    "encode_frame",
    "decode_frame",
    "ws_url",
    "target_for",
]
