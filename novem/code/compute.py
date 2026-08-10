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
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from novem.exceptions import NovemException

PROTOCOL = "novem.compute.v1"
PATH = "/ws-cu"
MAX_DATA_BYTES = 64 * 1024
BINARY_HEADER = 17

# stream discriminators
STREAM_DATA = 0  # pty/tcp bytes, and every client-to-server frame
STREAM_STDOUT = 1
STREAM_STDERR = 2

# The server's stable error vocabulary. Anything outside this set is a
# protocol violation on the server's side, not ours.
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


class NovemComputeError(NovemException):
    """A scoped error from the compute protocol.

    ``code`` is one of the server's stable codes; messages are sanitised
    server-side and never carry run ids, addresses or command payloads.
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


_HINTS = {
    # A missing entitlement, no access, and no such computer are
    # deliberately indistinguishable — never claim "permission denied".
    "not_found": "The computer was not found, or you do not have access to it.",
    "not_running": "The computer is not running. Start it with: novem -c <name> -w status online",
    "agent_upgrade_required": "The computer is running an older agent. Restart it to pick up the new one.",
    "limit_exceeded": "Too many open connections or channels. Close one and try again.",
    "upstream_unavailable": "The compute service is temporarily unavailable.",
}


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
    scheme = "wss" if parsed.scheme in ("https", "wss") else "ws"
    netloc = parsed.netloc or parsed.path
    return f"{scheme}://{netloc}{PATH}"


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
        for i in range(0, len(payload), MAX_DATA_BYTES):
            await self._conn._send_binary(encode_frame(self.id, payload[i : i + MAX_DATA_BYTES]))

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
        self.hello: Optional[Hello] = None
        self._channels: Dict[str, Channel] = {}
        self._pending: Dict[str, "asyncio.Future[Channel]"] = {}
        self._fatal: Optional[BaseException] = None

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
                max_msg_size=128 * 1024,
                ssl=False if self._ignore_ssl else True,
                autoping=True,
            )
        except Exception:
            await self._session.close()
            raise

        if self._debug:
            print(f"WS: {self._url} ({PROTOCOL})", file=sys.stderr)

        self._reader = asyncio.ensure_future(self._read_loop())
        await self._await_hello()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
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
        for _ in range(200):
            if self.hello is not None:
                return
            if self._fatal is not None:
                raise self._fatal
            await asyncio.sleep(0.01)
        raise NovemException("compute connection did not send hello")

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
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._on_text(json.loads(msg.data))
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    stream, channel, payload = decode_frame(msg.data)
                    ch = self._channels.get(channel)
                    if ch is not None:
                        ch._feed(stream, payload)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:  # pragma: no cover - transport failure
            self._abort(e)
            return
        self._abort(NovemException("compute connection closed"))

    def _abort(self, err: BaseException) -> None:
        self._fatal = err
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
            self.hello = Hello(
                protocol=msg.get("protocol", ""),
                max_channels=int(msg.get("max_channels", 0)),
                max_data_bytes=int(msg.get("max_data_bytes", 0)),
                heartbeat_seconds=int(msg.get("heartbeat_seconds", 0)),
            )
            if self.hello.protocol != PROTOCOL:
                self._abort(NovemException(f"unexpected compute protocol {self.hello.protocol!r}"))
            return

        if kind == "ready":
            fut = self._pending.pop(msg.get("request_id", ""), None)
            channel = Channel(self, msg["channel"], msg.get("kind", ""))
            self._channels[channel.id] = channel
            if fut is not None and not fut.done():
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
            return

        if kind == "exit":
            ch = self._channels.get(msg.get("channel", ""))
            if ch is not None:
                ch._finish(int(msg.get("code", 0)), msg.get("signal"))
            return

        if kind == "closed":
            ch = self._channels.get(msg.get("channel", ""))
            if ch is not None:
                ch._closed_by_server()
            return

    # -- opening channels --------------------------------------------------

    async def _open(self, spec: Dict[str, Any]) -> Channel:
        request_id = spec["request_id"]
        fut: "asyncio.Future[Channel]" = asyncio.get_event_loop().create_future()
        self._pending[request_id] = fut
        await self._send_json(spec)
        return await fut

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


async def _with_retry(open_channel: Any, use_channel: Any, connect: Any, retry_seconds: float) -> Any:
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
    while True:
        async with connect() as conn:
            try:
                channel = await open_channel(conn)
            except NovemComputeError as e:
                if not e.retryable or time.monotonic() >= deadline:
                    raise
            else:
                return await use_channel(channel)
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 3.0)


async def _exec_collect_channel(ch: Channel, stdin: Optional[bytes]) -> ExecResult:
    """Collect output from an admitted exec channel."""
    if stdin:
        await ch.send(stdin)
    await ch.stdin_eof()

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


async def _exec_collect(
    conn: ComputeConnection,
    target: str,
    command: str,
    args: List[str],
    mode: str,
    cwd: str,
    stdin: Optional[bytes],
    timeout_seconds: int,
) -> ExecResult:
    ch = await conn.open_exec(target, command, args, mode=mode, cwd=cwd, timeout_seconds=timeout_seconds)
    return await _exec_collect_channel(ch, stdin)


async def _exec_stream_channel(ch: Channel, stdin: Optional[bytes]) -> Tuple[int, Optional[str]]:
    """Stream output from an admitted exec channel to local stdout/stderr."""
    if stdin:
        await ch.send(stdin)
    await ch.stdin_eof()

    async for stream, data in ch:
        sink = sys.stderr.buffer if stream == STREAM_STDERR else sys.stdout.buffer
        sink.write(data)
        sink.flush()
    return await ch.wait()


async def _exec_stream(
    conn: ComputeConnection,
    target: str,
    command: str,
    args: List[str],
    mode: str,
    cwd: str,
    stdin: Optional[bytes],
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

    size = os.get_terminal_size()
    return await conn.open_pty(target, rows=size.lines, cols=size.columns)


async def _pty_interactive(ch: Channel) -> Tuple[int, Optional[str]]:
    """Attach the local terminal to an admitted PTY channel."""
    import signal as signalmod
    import termios
    import tty

    loop = asyncio.get_event_loop()
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)

    def on_winch(*_: Any) -> None:
        try:
            new = os.get_terminal_size()
        except OSError:
            return
        asyncio.ensure_future(ch.resize(new.lines, new.columns))

    def on_stdin() -> None:
        data = os.read(fd, 8192)
        if data:
            asyncio.ensure_future(ch.send(data))

    try:
        tty.setraw(fd)
        loop.add_signal_handler(signalmod.SIGWINCH, on_winch)
        loop.add_reader(fd, on_stdin)

        async for _stream, data in ch:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        return await ch.wait()
    finally:
        loop.remove_reader(fd)
        try:
            loop.remove_signal_handler(signalmod.SIGWINCH)
        except (NotImplementedError, RuntimeError):  # pragma: no cover
            pass
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


__all__ = [
    "PROTOCOL",
    "PATH",
    "MAX_DATA_BYTES",
    "STREAM_DATA",
    "STREAM_STDOUT",
    "STREAM_STDERR",
    "ERROR_CODES",
    "RETRYABLE_CODES",
    "NovemComputeError",
    "Hello",
    "ExecResult",
    "Channel",
    "ComputeConnection",
    "encode_frame",
    "decode_frame",
    "ws_url",
    "target_for",
]
