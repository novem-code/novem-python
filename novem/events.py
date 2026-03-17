"""Real-time event subscription client for the novem platform."""

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, List, Optional
from urllib.parse import urlparse

from .utils import get_current_config


@dataclass
class EventMessage:
    """Typed event payload from the server."""

    subscription: str
    event_class: str
    event_type: str
    target_fqnp: str
    actor: str
    ts: str
    level: Optional[str] = None

    @property
    def uri(self) -> str:
        """Alias for target_fqnp."""
        return self.target_fqnp

    @property
    def fqnp(self) -> str:
        """Alias for target_fqnp."""
        return self.target_fqnp


def _derive_ws_url(api_root: str) -> str:
    """Derive websocket origin from api_root."""
    parsed = urlparse(api_root)
    ws_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        ws_url = f"{ws_url}:{parsed.port}"
    return ws_url


def _make_event(data: Any) -> EventMessage:
    return EventMessage(
        subscription=data.get("subscription", ""),
        event_class=data.get("event_class", ""),
        event_type=data.get("event_type", ""),
        target_fqnp=data.get("target_fqnp", ""),
        actor=data.get("actor", ""),
        ts=data.get("ts", ""),
        level=data.get("level"),
    )


class Events:
    """Real-time event subscription client.

    Primary interface is async::

        async for msg in Events(["/u/alice/p/*/e/mention"]):
            ctx = Context(msg.fqnp)
            txt = await ctx.atxt
            await ctx.areply(Message("thanks!"))

    Each handler runs concurrently — while one awaits an API call,
    the next event can start processing.
    """

    def __init__(self, patterns: List[str], **kwargs: Any) -> None:
        self._patterns = patterns

        if "profile" in kwargs:
            kwargs["config_profile"] = kwargs.pop("profile")

        _, config = get_current_config(**kwargs)
        self._token: Optional[str] = config.get("token")
        api_root: str = config.get("api_root", "https://api.novem.io/v1/")
        self._ws_url = _derive_ws_url(api_root)

    def _check_deps(self) -> Any:
        try:
            import socketio

            return socketio
        except ImportError:
            raise ImportError('The "events" extra is required. Install with: pip install novem[events]')

    async def __aiter__(self) -> AsyncIterator[EventMessage]:
        """Async iterator — yields events as they arrive."""
        socketio = self._check_deps()

        if not self._token:
            raise RuntimeError("No authentication token found. Run novem --init first.")

        q: "asyncio.Queue[EventMessage]" = asyncio.Queue()
        sio = socketio.AsyncClient(reconnection=True, reconnection_attempts=0)

        @sio.on("connected")
        async def on_connected(data: Any) -> None:
            for pattern in self._patterns:
                await sio.emit("subscribe_events", {"subscription": pattern})

        @sio.on("event")
        async def on_event(data: Any) -> None:
            await q.put(_make_event(data))

        headers = {"Authorization": f"Bearer {self._token}"}
        await sio.connect(self._ws_url, socketio_path="/ws", headers=headers, transports=["websocket"])

        try:
            while True:
                yield await q.get()
        finally:
            await sio.disconnect()
