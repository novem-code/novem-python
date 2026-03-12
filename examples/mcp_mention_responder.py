#!/usr/bin/env python3
"""
MCP mention responder — on each @mention, spins up an MCP server
and lets Claude explore the thread and reply via tool use.

Usage:
    pip install novem[events,mcp] anthropic
    python examples/mcp_mention_responder.py
    python examples/mcp_mention_responder.py "/u/myuser/p/*/e/mention"
"""

import asyncio
import sys
from typing import Any, List

import anthropic

from novem.comments import MCP
from novem.events import Events

DEFAULT_PATTERNS = [
    "/u/*/p/*/e/mention",
    "/u/*/grp/*/e/mention",
    "/o/*/g/*/e/mention",
]

patterns = sys.argv[1:] or DEFAULT_PATTERNS

client = anthropic.Anthropic()

SYSTEM = (
    "You are a helpful assistant responding to mentions on the novem "
    "data visualization platform. Use the available tools to read the "
    "conversation context, then reply concisely."
)


async def handle(msg: Any) -> None:
    """Handle a single mention event."""
    if not msg.target_fqnp:
        return

    print(f"[{msg.ts}] {msg.actor} -> {msg.fqnp}", file=sys.stderr)

    mcp = MCP(msg.target_fqnp)
    tools = await mcp.api_tools()

    messages: List[Any] = [
        {
            "role": "user",
            "content": f"@{msg.actor} mentioned you at {msg.target_fqnp}. Read the thread and reply helpfully.",
        },
    ]

    # Agentic tool-use loop
    while True:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM,
            tools=tools,
            messages=messages,
        )

        if resp.stop_reason == "end_of_turn":
            break

        # Execute tool calls against the MCP server
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                content, _meta = await mcp.call_tool(block.name, block.input)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content[0].text if content else "",
                    }
                )
        messages.append({"role": "user", "content": results})


async def main() -> None:
    for p in patterns:
        print(f"Listening on: {p}", file=sys.stderr)

    async for msg in Events(patterns):
        asyncio.create_task(handle(msg))


asyncio.run(main())
