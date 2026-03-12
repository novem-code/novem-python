#!/usr/bin/env python3
"""
Mention responder — listens for @mention events and prints the thread context.

Usage:
    pip install novem[events]
    python examples/mention_responder.py
    python examples/mention_responder.py "/u/myuser/p/*/e/mention"
    python examples/mention_responder.py --profile sd
"""

import argparse
import asyncio
import sys

from novem.comments import Context
from novem.events import Events

parser = argparse.ArgumentParser(description="Listen for @mention events and print thread context.")
parser.add_argument("pattern", nargs="?", default="/u/*/p/*/e/mention", help="Event subscription pattern")
parser.add_argument("--profile", default=None, help="Novem config profile to use")
args = parser.parse_args()

pattern = args.pattern
profile = args.profile


async def main() -> None:
    print(f"Listening on: {pattern}", file=sys.stderr)
    ev_kwargs: dict = {}
    ctx_kwargs: dict = {}
    if profile:
        ev_kwargs["profile"] = profile
        ctx_kwargs["config_profile"] = profile
    async for msg in Events([pattern], **ev_kwargs):
        print(f"[{msg.ts}] {msg.event_type}: {msg.actor} -> {msg.fqnp}", file=sys.stderr)

        if not msg.target_fqnp:
            continue

        # target_fqnp is the full comment permalink, e.g.
        # /u/alice/p/myplot/c/@sen~topic/c/@bob~reply
        ctx = Context(msg.target_fqnp, **ctx_kwargs)
        print(await ctx.atxt())

        # The context knows where in the tree we are:
        # ctx.topic    — the focused Topic
        # ctx.comment  — the focused Comment (deepest /c/ segment)
        # ctx.topics   — all topics on the VDE

        # Uncomment to auto-reply at the mention location:
        await ctx.areply(f"Thanks for the mention, @{msg.actor}!")


asyncio.run(main())
