"""Tests for the novem.compute.v1 client.

The integration tests use a local WebSocket peer speaking the public
protocol, exercising the aiohttp client path, frame codec and message
dispatch without mocking the transport.
"""

import asyncio
import base64
import io
import json
import os
import secrets
import signal
import sys
import threading

import aiohttp
import pytest
from aiohttp import web

from novem.code.compute import (
    MAX_DATA_BYTES,
    PROTOCOL,
    STREAM_STDERR,
    STREAM_STDOUT,
    Channel,
    ComputeConnection,
    Hello,
    NovemComputeError,
    NovemComputeTransportError,
    _exec_collect_channel,
    _open_interactive_pty,
    _pty_interactive,
    _pump_stdin,
    _split_argv,
    _use_channel_with_stdin,
    _with_retry,
    _with_sigint_forwarding,
    decode_frame,
    encode_frame,
    target_for,
    ws_url,
)

TARGET = "/v1/users/alice/code/computers/box"


# --- pure units --------------------------------------------------------------


def test_frame_round_trip():
    channel = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")
    frame = encode_frame(channel, b"hello", STREAM_STDOUT)
    assert len(frame) == 17 + 5
    assert decode_frame(frame) == (STREAM_STDOUT, channel, b"hello")


def test_frame_rejects_empty_and_oversized():
    channel = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")
    with pytest.raises(ValueError, match="empty"):
        encode_frame(channel, b"")
    with pytest.raises(ValueError, match="exceeds"):
        encode_frame(channel, b"x" * (MAX_DATA_BYTES + 1))


def test_decode_rejects_short_frame():
    with pytest.raises(ValueError, match="too short"):
        decode_frame(b"\x00" + b"y" * 16)  # header only, no payload


def test_ws_url_is_host_rooted():
    # /ws-cu is served at the host root, not under /v1
    assert ws_url("https://api.novem.io/v1/") == "wss://api.novem.io/ws-cu"
    assert ws_url("http://localhost:9090/v1/") == "ws://localhost:9090/ws-cu"
    with pytest.raises(ValueError, match="scheme and host"):
        ws_url("localhost:9090/v1/")


def test_target_is_canonical():
    # the short /v1/code/... form is not accepted here
    assert target_for("alice", "box") == TARGET


def test_split_argv():
    assert _split_argv(["ls", "-la"], "argv") == ("ls", ["-la"])
    assert _split_argv("ls", "argv") == ("ls", [])
    assert _split_argv("ps aux | wc -l", "shell") == ("ps aux | wc -l", [])
    with pytest.raises(ValueError, match="single command string"):
        _split_argv(["ps", "aux"], "shell")
    with pytest.raises(ValueError, match="command is required"):
        _split_argv([], "argv")


def test_open_validation_matches_protocol_rules():
    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        with pytest.raises(ValueError, match="shell mode"):
            await conn.open_exec(TARGET, "ls", ["-la"], mode="shell")
        with pytest.raises(ValueError, match="relative executable"):
            await conn.open_exec(TARGET, "./run.sh")
        with pytest.raises(ValueError, match="cwd must be absolute"):
            await conn.open_exec(TARGET, "ls", cwd="rel/path")

    asyncio.run(check())


def test_unknown_error_codes_pass_through_as_terminal():
    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        fut = asyncio.get_running_loop().create_future()
        conn._pending["np-future"] = fut

        conn._on_text(
            {
                "type": "error",
                "request_id": "np-future",
                "code": "new_server_code",
                "message": "A newer server reported an error",
            }
        )

        with pytest.raises(NovemComputeError) as exc_info:
            await fut
        assert exc_info.value.code == "new_server_code"
        assert exc_info.value.retryable is False
        assert exc_info.value.cli_message == "A newer server reported an error"

    asyncio.run(check())


def test_unknown_or_invalid_ready_is_a_transport_error():
    async def check():
        unknown = ComputeConnection("ws://unused/ws-cu", "nut-x")
        unknown._on_text({"type": "ready", "request_id": "not-pending", "channel": _channel(), "kind": "exec"})
        assert isinstance(unknown._fatal, NovemComputeTransportError)
        assert unknown._channels == {}

        invalid = ComputeConnection("ws://unused/ws-cu", "nut-x")
        future = asyncio.get_running_loop().create_future()
        invalid._pending["np-pending"] = future
        invalid._on_text({"type": "ready", "request_id": "np-pending", "kind": "exec"})
        assert isinstance(invalid._fatal, NovemComputeTransportError)
        assert invalid._channels == {}
        with pytest.raises(NovemComputeTransportError):
            await future

    asyncio.run(check())


@pytest.mark.parametrize(
    ("close_code", "reason", "message"),
    [
        (1001, "session_ended", "session ended"),
        (1008, "protocol_error", "Upgrade the CLI"),
        (1011, "upstream_unavailable", "service ended"),
        (1006, "connection_failed", "connection to the computer was lost"),
    ],
)
def test_close_codes_map_to_distinct_transport_errors(close_code, reason, message):
    class ClosedSocket:
        def __init__(self):
            self.close_code = close_code

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        conn._ws = ClosedSocket()
        await conn._read_loop()
        assert isinstance(conn._fatal, NovemComputeTransportError)
        assert conn._fatal.close_code == close_code
        assert conn._fatal.code == reason
        assert message in str(conn._fatal)

    asyncio.run(check())


def test_protocol_mismatch_cannot_complete_hello():
    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        conn._hello_event = asyncio.Event()
        conn._on_text(
            {
                "type": "hello",
                "protocol": "novem.compute.future",
                "max_channels": 16,
                "max_data_bytes": MAX_DATA_BYTES,
                "heartbeat_seconds": 30,
            }
        )
        with pytest.raises(NovemComputeTransportError, match="unexpected compute protocol"):
            await conn._await_hello()

    asyncio.run(check())


def test_liveness_watchdog_fails_a_silent_connection():
    class Socket:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        conn._ws = Socket()
        conn.hello = Hello(PROTOCOL, 16, MAX_DATA_BYTES, 0.01)
        conn._last_inbound = asyncio.get_running_loop().time() - 1
        await asyncio.wait_for(conn._watch_liveness(), timeout=0.2)
        assert isinstance(conn._fatal, NovemComputeTransportError)
        assert conn._ws.closed is True

    asyncio.run(check())


def test_channel_honours_a_smaller_negotiated_frame_limit():
    class Connection:
        max_data_bytes = 4

        def __init__(self):
            self.frames = []

        async def _send_binary(self, frame):
            self.frames.append(frame)

    async def check():
        conn = Connection()
        channel = Channel(conn, _channel(), "exec")
        await channel.send(b"abcdefghij")
        assert [decode_frame(frame)[2] for frame in conn.frames] == [b"abcd", b"efgh", b"ij"]

    asyncio.run(check())


def test_connection_enforces_and_releases_negotiated_channel_limit():
    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        conn.hello = Hello(PROTOCOL, 1, MAX_DATA_BYTES, 30)
        channel_id = _channel()
        conn._channels[channel_id] = Channel(conn, channel_id, "exec")

        with pytest.raises(NovemComputeError) as exc_info:
            await conn.open_exec(TARGET, "true")
        assert exc_info.value.code == "limit_exceeded"

        conn._on_text({"type": "exit", "channel": channel_id, "code": 0, "signal": None})
        assert conn._channels == {}

    asyncio.run(check())


def test_file_stdin_preserves_arbitrary_bytes():
    class RecordingChannel:
        def __init__(self):
            self.data = []
            self.eof = False

        async def send(self, data):
            self.data.append(data)

        async def stdin_eof(self):
            self.eof = True

    async def check():
        channel = RecordingChannel()
        await _pump_stdin(channel, io.BytesIO(b"\xff\xfe\x00\x80"))
        assert b"".join(channel.data) == b"\xff\xfe\x00\x80"
        assert channel.eof is True

    asyncio.run(check())


def test_pipe_stdin_sends_a_frame_before_writer_eof():
    class RecordingChannel:
        def __init__(self):
            self.data = []
            self.received = asyncio.Event()
            self.eof = False

        async def send(self, data):
            self.data.append(data)
            self.received.set()

        async def stdin_eof(self):
            self.eof = True

    async def check():
        read_fd, write_fd = os.pipe()
        source = os.fdopen(read_fd, "rb", buffering=0)
        channel = RecordingChannel()
        try:
            task = asyncio.create_task(_pump_stdin(channel, source))
            os.write(write_fd, b"first chunk")
            await asyncio.wait_for(channel.received.wait(), timeout=1)
            assert task.done() is False
            assert channel.data == [b"first chunk"]
            os.close(write_fd)
            write_fd = -1
            await asyncio.wait_for(task, timeout=1)
            assert channel.eof is True
        finally:
            source.close()
            if write_fd >= 0:
                os.close(write_fd)

    asyncio.run(check())


def test_output_is_consumed_while_file_stdin_is_still_open():
    class BlockingInput:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()
            self.complete = False

        def read(self, size):
            self.started.set()
            self.release.wait(timeout=2)
            if self.complete:
                return b""
            self.complete = True
            return b"input"

    class RecordingChannel:
        def __init__(self):
            self.data = []
            self.eof = asyncio.Event()

        async def send(self, data):
            self.data.append(data)

        async def stdin_eof(self):
            self.eof.set()

    async def check():
        source = BlockingInput()
        channel = RecordingChannel()
        output_seen = asyncio.Event()

        async def consume():
            output_seen.set()
            await channel.eof.wait()
            return "done"

        task = asyncio.create_task(_use_channel_with_stdin(channel, source, consume))
        for _ in range(100):
            if source.started.is_set():
                break
            await asyncio.sleep(0.001)
        assert source.started.is_set()
        await asyncio.wait_for(output_seen.wait(), timeout=0.1)
        source.release.set()
        assert await asyncio.wait_for(task, timeout=1) == "done"
        assert channel.data == [b"input"]

    asyncio.run(check())


def test_first_sigint_is_forwarded_to_the_command(monkeypatch):
    class RecordingChannel:
        def __init__(self):
            self.signals = []
            self.forwarded = asyncio.Event()

        async def signal(self, name):
            self.signals.append(name)
            self.forwarded.set()

    async def check():
        loop = asyncio.get_running_loop()
        handlers = {}
        monkeypatch.setattr(loop, "add_signal_handler", lambda sig, callback: handlers.setdefault(sig, callback))
        monkeypatch.setattr(loop, "remove_signal_handler", lambda sig: handlers.pop(sig, None) is not None)
        monkeypatch.setattr(signal, "getsignal", lambda sig: signal.default_int_handler)
        monkeypatch.setattr(signal, "signal", lambda sig, handler: None)

        channel = RecordingChannel()

        async def command():
            await channel.forwarded.wait()
            return (0, "INT")

        task = asyncio.create_task(_with_sigint_forwarding(channel, command))
        for _ in range(100):
            if signal.SIGINT in handlers:
                break
            await asyncio.sleep(0.001)
        handlers[signal.SIGINT]()
        assert await asyncio.wait_for(task, timeout=1) == (0, "INT")
        assert channel.signals == ["INT"]

    asyncio.run(check())


@pytest.mark.skipif(os.name == "nt", reason="PTY handling is Unix-only")
def test_open_pty_uses_stdin_for_size_and_has_a_fallback(monkeypatch):
    class Stdin:
        def isatty(self):
            return True

        def fileno(self):
            return 42

    class Connection:
        async def open_pty(self, target, **kwargs):
            self.target = target
            self.kwargs = kwargs
            return "channel"

    seen = []

    def no_size(fd):
        seen.append(fd)
        raise OSError("no terminal size")

    monkeypatch.setattr(sys, "stdin", Stdin())
    monkeypatch.setattr(os, "get_terminal_size", no_size)

    async def check():
        conn = Connection()
        assert await _open_interactive_pty(conn, TARGET) == "channel"
        assert conn.target == TARGET
        assert conn.kwargs == {"rows": 24, "cols": 80}

    asyncio.run(check())
    assert seen == [42]


@pytest.mark.skipif(os.name == "nt", reason="PTY handling is Unix-only")
def test_pty_hangup_sends_eof_once_without_spinning(monkeypatch):
    import pty

    class RecordingChannel:
        def __init__(self):
            self.eof_calls = 0
            self.eof = asyncio.Event()

        async def send(self, data):
            pass

        async def resize(self, rows, cols):
            pass

        async def stdin_eof(self):
            self.eof_calls += 1
            self.eof.set()

        def __aiter__(self):
            async def output():
                await self.eof.wait()
                if False:
                    yield (0, b"")

            return output()

        async def wait(self):
            return (0, None)

    master_fd, slave_fd = pty.openpty()
    stdin = os.fdopen(os.dup(slave_fd), "rb", buffering=0)
    monkeypatch.setattr(sys, "stdin", stdin)

    async def check():
        channel = RecordingChannel()
        task = asyncio.create_task(_pty_interactive(channel))
        await asyncio.sleep(0.02)
        os.close(master_fd)
        assert await asyncio.wait_for(task, timeout=1) == (0, None)
        assert channel.eof_calls == 1

    try:
        asyncio.run(check())
    finally:
        stdin.close()
        os.close(slave_fd)


# --- protocol, against a real server ----------------------------------------


class FakeServer:
    """A minimal server-side implementation of novem.compute.v1."""

    def __init__(self, script, *, reject_statuses=None, protocols=(PROTOCOL,), send_hello=True):
        self.script = script
        self.seen = []
        self.auth = None
        self.subprotocol = None
        self.connections = 0
        self.reject_statuses = list(reject_statuses or [])
        self.protocols = protocols
        self.send_hello = send_hello

    async def handler(self, request):
        self.connections += 1
        if self.reject_statuses:
            return web.Response(status=self.reject_statuses.pop(0))
        self.auth = request.headers.get("Authorization")
        self.subprotocol = request.headers.get("Sec-WebSocket-Protocol")
        ws = web.WebSocketResponse(protocols=self.protocols)
        await ws.prepare(request)

        if self.send_hello:
            await ws.send_str(
                json.dumps(
                    {
                        "type": "hello",
                        "protocol": PROTOCOL,
                        "max_channels": 16,
                        "max_data_bytes": MAX_DATA_BYTES,
                        "heartbeat_seconds": 30,
                    }
                )
            )

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                payload = json.loads(msg.data)
                self.seen.append(payload)
                await self.script(ws, payload, self)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                self.seen.append(decode_frame(msg.data))
        return ws


def _channel() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")


async def _serve(server):
    app = web.Application()
    app.router.add_get("/ws-cu", server.handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, f"ws://127.0.0.1:{port}/ws-cu"


def _drive(server, body):
    async def main():
        runner, url = await _serve(server)
        try:
            return await body(url)
        finally:
            await runner.cleanup()

    return asyncio.run(main())


def test_exec_streams_output_and_exit_status():
    async def script(ws, msg, gw):
        if msg["type"] == "open":
            ch = _channel()
            gw.channel = ch
            await ws.send_str(
                json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": ch, "kind": "exec"})
            )
            await ws.send_bytes(encode_frame(ch, b"out\n", STREAM_STDOUT))
            await ws.send_bytes(encode_frame(ch, b"err\n", STREAM_STDERR))
            await ws.send_str(json.dumps({"type": "exit", "channel": ch, "code": 3, "signal": None}))

    server = FakeServer(script)

    async def body(url):
        from novem.code.compute import _exec_collect

        async with ComputeConnection(url, "nut-secret") as conn:
            assert conn.hello is not None
            assert conn.hello.max_channels == 16
            return await _exec_collect(conn, TARGET, "ls", ["-la"], "argv", "", None, 600)

    result = _drive(server, body)

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert result.code == 3
    assert result.ok is False

    # the client authenticated with a bearer token and asked for the protocol,
    # and never sent an Origin (self-asserted, so not trusted)
    assert server.auth == "Bearer nut-secret"
    assert server.subprotocol == PROTOCOL

    opened = server.seen[0]
    assert opened["kind"] == "exec"
    assert opened["mode"] == "argv"
    assert opened["command"] == "ls"
    assert opened["args"] == ["-la"]
    assert opened["target"] == TARGET
    # stdin is closed explicitly rather than by closing the channel
    assert {"type": "stdin_eof", "channel": server.channel} in server.seen


def test_signalled_process_reports_signal():
    async def script(ws, msg, gw):
        if msg["type"] == "open":
            ch = _channel()
            await ws.send_str(
                json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": ch, "kind": "exec"})
            )
            # a signalled process carries -1 with a signal name
            await ws.send_str(json.dumps({"type": "exit", "channel": ch, "code": -1, "signal": "TERM"}))

    async def body(url):
        from novem.code.compute import _exec_collect

        async with ComputeConnection(url, "nut-x") as conn:
            return await _exec_collect(conn, TARGET, "sleep", ["100"], "argv", "", None, 600)

    result = _drive(FakeServer(script), body)
    assert result.code == -1
    assert result.signal == "TERM"
    assert result.ok is False


def test_error_before_ready_raises_with_stable_code():
    async def script(ws, msg, gw):
        if msg["type"] == "open":
            await ws.send_str(
                json.dumps(
                    {
                        "type": "error",
                        "request_id": msg["request_id"],
                        "code": "not_running",
                        "message": "Computer connection could not be started",
                    }
                )
            )

    async def body(url):
        async with ComputeConnection(url, "nut-x") as conn:
            with pytest.raises(NovemComputeError) as ei:
                await conn.open_exec(TARGET, "ls")
            return ei.value

    err = _drive(FakeServer(script), body)
    assert err.code == "not_running"
    assert err.retryable is True
    assert "novem -c" in err.cli_message  # the hint tells you how to start it


def test_retry_reuses_connection_after_retryable_admission_error():
    attempts = 0

    async def script(ws, msg, server):
        nonlocal attempts
        if msg["type"] != "open":
            return

        attempts += 1
        if attempts == 1:
            await ws.send_str(
                json.dumps(
                    {
                        "type": "error",
                        "request_id": msg["request_id"],
                        "code": "not_running",
                        "message": "Computer is starting",
                    }
                )
            )
            return

        channel = _channel()
        await ws.send_str(
            json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": channel, "kind": "exec"})
        )
        await ws.send_str(json.dumps({"type": "exit", "channel": channel, "code": 0, "signal": None}))

    async def body(url):
        return await _with_retry(
            lambda conn: conn.open_exec(TARGET, "true"),
            lambda channel: _exec_collect_channel(channel, None),
            lambda: ComputeConnection(url, "nut-x"),
            1.0,
        )

    server = FakeServer(script)
    result = _drive(server, body)
    assert result.code == 0
    assert attempts == 2
    assert server.connections == 1


def test_retryable_handshake_failure_reconnects_before_any_open():
    async def script(ws, msg, server):
        if msg["type"] != "open":
            return
        channel = _channel()
        await ws.send_str(
            json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": channel, "kind": "exec"})
        )
        await ws.send_str(json.dumps({"type": "exit", "channel": channel, "code": 0, "signal": None}))

    server = FakeServer(script, reject_statuses=[503])
    retries = []

    async def body(url):
        return await _with_retry(
            lambda conn: conn.open_exec(TARGET, "true"),
            lambda channel: _exec_collect_channel(channel, None),
            lambda: ComputeConnection(url, "nut-x"),
            1.0,
            retries.append,
        )

    result = _drive(server, body)
    assert result.code == 0
    assert server.connections == 2
    assert len(retries) == 1
    assert isinstance(retries[0], NovemComputeTransportError)
    assert retries[0].code == "upstream_unavailable"


def test_handshake_validation_failure_closes_all_resources(monkeypatch):
    async def script(ws, msg, server):
        pass

    async def missing_protocol(url):
        conn = ComputeConnection(url, "nut-x")
        with pytest.raises(NovemComputeTransportError, match="negotiate"):
            await conn.__aenter__()
        assert conn._session.closed is True
        assert conn._ws.closed is True

    _drive(FakeServer(script, protocols=()), missing_protocol)

    monkeypatch.setattr("novem.code.compute.HELLO_TIMEOUT_SECONDS", 0.05)

    async def missing_hello(url):
        conn = ComputeConnection(url, "nut-x")
        with pytest.raises(NovemComputeTransportError, match="did not send hello"):
            await conn.__aenter__()
        assert conn._session.closed is True
        assert conn._ws.closed is True
        assert conn._reader.done() is True

    _drive(FakeServer(script, send_hello=False), missing_hello)


def test_retry_does_not_replay_a_command_after_ready():
    attempts = 0

    async def script(ws, msg, server):
        nonlocal attempts
        if msg["type"] != "open":
            return

        attempts += 1
        channel = _channel()
        await ws.send_str(
            json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": channel, "kind": "exec"})
        )
        await ws.send_str(
            json.dumps(
                {
                    "type": "error",
                    "channel": channel,
                    "code": "upstream_unavailable",
                    "message": "Connection was interrupted",
                }
            )
        )

    async def body(url):
        with pytest.raises(NovemComputeError) as exc_info:
            await _with_retry(
                lambda conn: conn.open_exec(TARGET, "touch", ["marker"]),
                lambda channel: _exec_collect_channel(channel, None),
                lambda: ComputeConnection(url, "nut-x"),
                1.0,
            )
        return exc_info.value

    error = _drive(FakeServer(script), body)
    assert error.code == "upstream_unavailable"
    assert attempts == 1


def test_not_found_never_claims_permission_denied():
    async def script(ws, msg, gw):
        if msg["type"] == "open":
            await ws.send_str(
                json.dumps(
                    {
                        "type": "error",
                        "request_id": msg["request_id"],
                        "code": "not_found",
                        "message": "Computer was not found",
                    }
                )
            )

    async def body(url):
        async with ComputeConnection(url, "nut-x") as conn:
            with pytest.raises(NovemComputeError) as ei:
                await conn.open_exec(TARGET, "ls")
            return ei.value

    err = _drive(FakeServer(script), body)
    assert err.code == "not_found"
    assert err.retryable is False
    # a missing entitlement is indistinguishable from no access by design
    assert "do not have access" in err.cli_message
    assert "denied" not in err.cli_message.lower()


def test_stdin_is_sent_before_eof():
    async def script(ws, msg, gw):
        if msg["type"] == "open":
            ch = _channel()
            gw.channel = ch
            await ws.send_str(
                json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": ch, "kind": "exec"})
            )
            await ws.send_str(json.dumps({"type": "exit", "channel": ch, "code": 0, "signal": None}))

    server = FakeServer(script)

    async def body(url):
        from novem.code.compute import _exec_collect

        async with ComputeConnection(url, "nut-x") as conn:
            return await _exec_collect(conn, TARGET, "wc", ["-l"], "argv", "", b"a\nb\n", 600)

    _drive(server, body)

    binary = [f for f in server.seen if isinstance(f, tuple)]
    assert binary, "stdin should arrive as a binary frame"
    stream, channel, payload = binary[0]
    assert stream == 0  # clients may only send stream 0
    assert payload == b"a\nb\n"


def test_large_stdin_is_chunked_to_the_frame_limit():
    async def script(ws, msg, gw):
        if msg["type"] == "open":
            ch = _channel()
            await ws.send_str(
                json.dumps({"type": "ready", "request_id": msg["request_id"], "channel": ch, "kind": "exec"})
            )
            await ws.send_str(json.dumps({"type": "exit", "channel": ch, "code": 0, "signal": None}))

    server = FakeServer(script)
    blob = b"x" * (MAX_DATA_BYTES + 100)

    async def body(url):
        from novem.code.compute import _exec_collect

        async with ComputeConnection(url, "nut-x") as conn:
            return await _exec_collect(conn, TARGET, "cat", [], "argv", "", blob, 600)

    _drive(server, body)

    frames = [f for f in server.seen if isinstance(f, tuple)]
    assert len(frames) == 2
    assert len(frames[0][2]) == MAX_DATA_BYTES
    assert len(frames[1][2]) == 100
