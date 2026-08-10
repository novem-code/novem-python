"""Tests for the novem.compute.v1 client.

The protocol tests run against a real WebSocket server that speaks the
server's side of the contract, so the aiohttp client path, the frame codec
and the message dispatch are all exercised for real rather than mocked.
"""

import asyncio
import base64
import json
import secrets

import pytest

from novem.code.compute import (
    MAX_DATA_BYTES,
    PROTOCOL,
    STREAM_STDERR,
    STREAM_STDOUT,
    ComputeConnection,
    NovemComputeError,
    _split_argv,
    decode_frame,
    encode_frame,
    target_for,
    ws_url,
)

aiohttp = pytest.importorskip("aiohttp")
web = pytest.importorskip("aiohttp.web")

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


def test_open_validation_matches_server_rules():
    async def check():
        conn = ComputeConnection("ws://unused/ws-cu", "nut-x")
        with pytest.raises(ValueError, match="shell mode"):
            await conn.open_exec(TARGET, "ls", ["-la"], mode="shell")
        with pytest.raises(ValueError, match="relative executable"):
            await conn.open_exec(TARGET, "./run.sh")
        with pytest.raises(ValueError, match="cwd must be absolute"):
            await conn.open_exec(TARGET, "ls", cwd="rel/path")

    asyncio.run(check())


# --- protocol, against a real server ----------------------------------------


class FakeServer:
    """A minimal server-side implementation of novem.compute.v1."""

    def __init__(self, script):
        self.script = script
        self.seen = []
        self.auth = None
        self.subprotocol = None

    async def handler(self, request):
        self.auth = request.headers.get("Authorization")
        self.subprotocol = request.headers.get("Sec-WebSocket-Protocol")
        ws = web.WebSocketResponse(protocols=(PROTOCOL,))
        await ws.prepare(request)

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
