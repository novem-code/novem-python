#!/usr/bin/env python3
"""
Mention responder — listens for @mention events and prints the thread context.

Usage:
    pip install novem[events]
    python examples/mention_responder.py
    python examples/mention_responder.py "/u/myuser/p/*/e/mention"
"""

import asyncio
import sys

from novem.comments import Context
from novem.events import Events

pattern = sys.argv[1] if len(sys.argv) > 1 else "/u/*/p/*/e/mention"


async def main() -> None:
    async for msg in Events([pattern]):
        print(f"[{msg.ts}] {msg.event_type}: {msg.actor} -> {msg.fqnp}", file=sys.stderr)

        if not msg.target_fqnp:
            continue

        # target_fqnp is the full comment permalink, e.g.
        # /u/alice/p/myplot/c/@sen~topic/c/@bob~reply
        ctx = Context(msg.target_fqnp)
        print(await ctx.atxt())

        # The context knows where in the tree we are:
        # ctx.topic    — the focused Topic
        # ctx.comment  — the focused Comment (deepest /c/ segment)
        # ctx.topics   — all topics on the VDE

        # Uncomment to auto-reply at the mention location:
        # await ctx.areply(f"Thanks for the mention, @{msg.actor}!")


asyncio.run(main())
