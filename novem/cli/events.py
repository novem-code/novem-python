import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict, List

from ..utils import get_current_config

# ANSI color codes — disabled when output is not a tty
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _dim(text: str) -> str:
    return _c("2", text)


def _bold(text: str) -> str:
    return _c("1", text)


def _cyan(text: str) -> str:
    return _c("36", text)


def _green(text: str) -> str:
    return _c("32", text)


def _yellow(text: str) -> str:
    return _c("33", text)


def parse_events_arg(events_arg: List[str]) -> List[str]:
    """Validate FQNP patterns from --events args."""
    return [p.strip() for p in events_arg if p.strip()]


def _format_event(data: Dict[str, Any]) -> str:
    """Format an event as a human-readable line with colors."""
    ts = data.get("ts")
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            local_dt = dt.astimezone()
            time_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except (ValueError, TypeError):
            time_str = ts
    else:
        time_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    event_type = data.get("event_type", "unknown")
    actor = data.get("actor") or "system"
    target = data.get("target_fqnp") or ""

    parts = [_dim(time_str), _bold(_yellow(event_type)), _green(actor)]
    if target:
        parts.append(_dim("\u2192"))
        parts.append(_cyan(target))

    return "  ".join(parts)


async def _subscribe_events(args: Dict[str, Any], patterns: List[str]) -> None:
    try:
        import socketio
    except ImportError:
        print(
            'Error: The "events" extra is required for --events.\n' "Install it with: pip install novem[events]",
            file=sys.stderr,
        )
        sys.exit(1)

    json_output = args.get("json_output", False)

    # Resolve auth config
    if args.get("profile"):
        args["config_profile"] = args["profile"]
    _, config = get_current_config(**args)

    token = args.get("token") or config.get("token")
    if not token:
        print("Error: No authentication token found. Run novem --init first.", file=sys.stderr)
        sys.exit(1)

    # Derive websocket URL from api_root
    # api_root is like https://api.novem.io/v1/ — we need the base origin
    api_root: str = config.get("api_root", "https://api.novem.io/v1/")
    from urllib.parse import urlparse

    parsed = urlparse(api_root)
    ws_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        ws_url = f"{ws_url}:{parsed.port}"

    sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=0)

    @sio.event
    async def connect() -> None:
        if args.get("debug"):
            print(f"Connected to {ws_url}", file=sys.stderr)

    @sio.on("connected")
    async def on_connected(data: Any) -> None:
        if args.get("debug"):
            print(f"Server ack: {data}", file=sys.stderr)
        # Subscribe to all patterns — server handles FQNP normalization
        for pattern in patterns:
            await sio.emit("subscribe_events", {"subscription": pattern})
            if args.get("debug"):
                print(f"Subscribed: {pattern}", file=sys.stderr)

    @sio.on("event")
    async def on_event(data: Any) -> None:
        if json_output:
            print(json.dumps(data), flush=True)
        else:
            print(_format_event(data), flush=True)

    @sio.event
    async def disconnect() -> None:
        if args.get("debug"):
            print("Disconnected", file=sys.stderr)

    @sio.event
    async def connect_error(data: Any) -> None:
        print(f"Connection error: {data}", file=sys.stderr)

    headers = {"Authorization": f"Bearer {token}"}

    if args.get("debug"):
        print(f"Connecting to {ws_url}/ws", file=sys.stderr)
        print(f"Patterns: {patterns}", file=sys.stderr)

    await sio.connect(ws_url, socketio_path="/ws", headers=headers, transports=["websocket"])

    # Wait until interrupted
    try:
        await sio.wait()
    except asyncio.CancelledError:
        pass
    finally:
        await sio.disconnect()


def run_events(args: Dict[str, Any]) -> None:
    """Entry point for --events from the CLI."""
    patterns = parse_events_arg(args["events"])
    if not patterns:
        print("Error: No event patterns provided.", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(_subscribe_events(args, patterns))
    except KeyboardInterrupt:
        pass
