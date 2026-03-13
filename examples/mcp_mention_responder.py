#!/usr/bin/env python3
"""
MCP mention responder — on each @mention or reply, spins up an MCP server
and lets Claude explore the thread and reply via tool use.

Usage:
    uv run --extra events --extra mcp --with anthropic --with python-dotenv examples/mcp_mention_responder.py
"""

import asyncio
import sys
import time
from typing import Any, List

import anthropic
from dotenv import load_dotenv

from novem.comments import MCP
from novem.events import Events

load_dotenv()

MODEL = "claude-sonnet-4-6"

DEFAULT_PATTERNS = [
    "/u/*/p/*/e/mention:me",
    "/u/*/p/*/e/comment_reply:me",
]

patterns = sys.argv[1:] or DEFAULT_PATTERNS

client = anthropic.Anthropic()

SYSTEM = (
    "You are a helpful assistant responding to mentions on the novem "
    "data visualization platform. Use the available tools to read the "
    "conversation context, then reply concisely.\n\n"
    f"{MCP.DOCS_MARKDOWN_COMMENTS}"  # type: ignore[attr-defined]
)


async def handle(msg: Any) -> None:
    if not msg.target_fqnp:
        return

    print(f"[{msg.ts}] {msg.event_type}: {msg.actor} -> {msg.fqnp}", file=sys.stderr)

    start = time.time()
    mcp = MCP(msg.target_fqnp)
    tools = await mcp.api_tools()

    def on_reply(text: str) -> str:
        elapsed = time.time() - start
        return f"{text}\n\n---\n^^ Generated in {elapsed:.1f}s using {MODEL}"

    mcp.on_reply = on_reply

    # Instant acknowledgement — will be overwritten with the real reply
    await mcp.call_tool("reply", {"text": "On it!"})

    messages: List[Any] = [
        {
            "role": "user",
            "content": f"@{msg.actor} mentioned you at {msg.target_fqnp}. Read the thread and reply helpfully.",
        },
    ]

    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM,
            tools=tools,
            messages=messages,
        )

        tool_blocks = [b for b in resp.content if b.type == "tool_use"]
        if not tool_blocks:
            break

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in tool_blocks:
            result = await mcp.call_tool(block.name, block.input)
            content = result[0] if isinstance(result, tuple) else result
            result_content: List[Any] = []
            for item in content:
                if item.type == "image":
                    result_content.append(
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": item.mimeType, "data": item.data},
                        }
                    )
                else:
                    result_content.append({"type": "text", "text": item.text})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_content})
        messages.append({"role": "user", "content": results})


async def main() -> None:
    for p in patterns:
        print(f"Listening on: {p}", file=sys.stderr)

    async for msg in Events(patterns):
        asyncio.create_task(handle(msg))


asyncio.run(main())
