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

# Cheap in-process dedup: skip duplicate events for the same target.
# The real dedup happens at reply time (server-side check), but this
# avoids wasting LLM calls when multiple events fire simultaneously.
_active: set[str] = set()

_SYSTEM_PREFIX = (
    "You are @{username} on the novem data visualization platform. "
    "You ARE @{username} — every comment you post appears under that name. "
    "When you see previous comments from @{username} in a thread, those are YOUR "
    "OWN prior replies. Do NOT refer to yourself in the third person, do NOT "
    "reply to your own comments, and do NOT repeat what you have already said.\n\n"
    "Use the available tools to explore context if needed, then reply concisely.\n\n"
)
_SYSTEM_SELF_REPLY = (
    "When an event is triggered by your own actions (actor is @{username}), "
    "you should almost always do nothing — only reply if there is an obvious "
    "error to correct or if adding a comment would provide significant value. "
    "When in doubt, do NOT reply.\n\n"
)
_SYSTEM_DOCS: str = MCP.DOCS_MARKDOWN_COMMENTS  # type: ignore[attr-defined]


async def handle(msg: Any) -> None:
    try:
        await _handle(msg)
    finally:
        _active.discard(msg.target_fqnp)


async def _handle(msg: Any) -> None:
    print(f"[{msg.ts}] {msg.event_type}: {msg.actor} -> {msg.fqnp}", file=sys.stderr)

    start = time.time()
    mcp = MCP(msg.target_fqnp)
    # Fixed slug: all replies (On it! + final) write to the same comment.
    # Concurrent handlers hitting the same target will 409 on create and
    # just update the existing comment instead of creating duplicates.
    mcp.reply_slug = "reply"
    tools = await mcp.api_tools()

    # Username comes from the server (via the GQL query that loaded the thread)
    my_username = mcp.ctx.me

    # Don't reply to our own comments — the focused comment is the one we'd
    # be replying under. If we wrote it, there's nothing to respond to.
    focused = mcp.ctx.comment or mcp.ctx.topic
    if focused and focused.creator == my_username:
        print(f"[{msg.ts}] focused comment is ours, skipping: {msg.fqnp}", file=sys.stderr)
        return

    def on_reply(text: str) -> str:
        elapsed = time.time() - start
        return f"{text}\n\n---\n^^ Generated in {elapsed:.1f}s using {MODEL}"

    mcp.on_reply = on_reply

    # Instant acknowledgement — will be overwritten with the real reply.
    # Uses the fixed slug, so concurrent "On it!" posts are idempotent.
    if msg.actor != my_username:
        await mcp.call_tool("novem_reply", {"text": "On it!"})

    system = (
        _SYSTEM_PREFIX.format(username=my_username) + _SYSTEM_SELF_REPLY.format(username=my_username) + _SYSTEM_DOCS
    )

    # Give the agent the conversation chain upfront so it doesn't need to
    # fetch context via tools (saves round-trips and avoids loops).
    thread = mcp.ctx.focused_thread
    prompt = f"@{msg.actor} mentioned you at {msg.target_fqnp}."
    if thread:
        prompt += f"\n\nConversation leading to the mention:\n\n{thread}"
    prompt += (
        "\n\nReply helpfully and concisely. Do NOT repeat what you have already said. "
        "If you need more context (e.g. the full thread, other topics, the visualization itself), "
        "use the available tools before replying."
    )

    messages: List[Any] = [
        {
            "role": "user",
            "content": prompt,
        },
    ]

    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )

        tool_blocks = [b for b in resp.content if b.type == "tool_use"]
        if not tool_blocks:
            break

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in tool_blocks:
            try:
                result = await mcp.call_tool(block.name, block.input)
            except Exception as e:
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(e), "is_error": True})
                continue
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
        if not msg.target_fqnp:
            continue
        # Dedup: check synchronously before spawning the task
        if msg.target_fqnp in _active:
            print(f"[{msg.ts}] dedup, already handling: {msg.target_fqnp}", file=sys.stderr)
            continue
        _active.add(msg.target_fqnp)
        asyncio.create_task(handle(msg))


asyncio.run(main())
