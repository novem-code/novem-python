#!/usr/bin/env python3
"""
Mention responder — listens for @mention events and prints the thread context.

Usage:
    pip install novem[events]
    python examples/mention_responder.py
    python examples/mention_responder.py "/u/<user>/p/*/e/mention"
    python examples/mention_responder.py "/o/<org>/g/*/e/mention"
    python examples/mention_responder.py --profile sd
"""

import argparse
import asyncio
import sys
from typing import Dict, List

from novem.comments import Context
from novem.events import Events

# Default patterns cover VDE mentions, user group mentions, and org group mentions
DEFAULT_PATTERNS = [
    "/u/*/p/*/e/mention",
    "/u/*/grp/*/e/mention",
    "/o/*/g/*/e/mention",
]

parser = argparse.ArgumentParser(description="Listen for @mention events and print thread context.")
parser.add_argument("pattern", nargs="*", default=DEFAULT_PATTERNS, help="Event subscription pattern(s)")
parser.add_argument("--profile", default=None, help="Novem config profile to use")
args = parser.parse_args()

patterns: List[str] = args.pattern
profile = args.profile


async def main() -> None:
    for p in patterns:
        print(f"Listening on: {p}", file=sys.stderr)
    ev_kwargs: Dict[str, str] = {}
    ctx_kwargs: Dict[str, str] = {}
    if profile:
        ev_kwargs["profile"] = profile
        ctx_kwargs["config_profile"] = profile
    async for msg in Events(patterns, **ev_kwargs):
        print(f"[{msg.ts}] {msg.event_type}: {msg.actor} -> {msg.fqnp}", file=sys.stderr)

        if not msg.target_fqnp:
            continue

        # target_fqnp is the full comment permalink, e.g.
        # /u/user1/p/my-plot/c/@user2~topic/c/@user3~reply
        # /u/user1/grp/my-group/c/@user2~topic
        # /o/my-org/g/my-group/c/@user2~topic
        ctx = Context(msg.target_fqnp, **ctx_kwargs)
        print(await ctx.atxt())

        # The context knows where in the tree we are:
        # ctx.topic    — the focused Topic
        # ctx.comment  — the focused Comment (deepest /c/ segment)
        # ctx.topics   — all topics on the VDE or group

        # Uncomment to auto-reply at the mention location:
        await ctx.areply(f"Thanks for the mention, @{msg.actor}!")


asyncio.run(main())
