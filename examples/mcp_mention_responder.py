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


def _log(msg: Any, text: str) -> None:
    print(f"[{msg.ts}] {text}", file=sys.stderr)


def _tool_content(result: Any) -> Any:
    """The content list from a call_tool result, across mcp v1 and v2.

    v1 returns the list itself, or a (list, dict) tuple when the tool declares
    structured output. v2 returns a CallToolResult, which is not subscriptable.
    """
    if hasattr(result, "content"):
        return result.content
    return result[0] if isinstance(result, tuple) else result


async def _handle(msg: Any) -> None:
    _log(msg, f"event: {msg.event_type} from @{msg.actor} -> {msg.fqnp}")

    start = time.time()
    mcp = MCP(msg.target_fqnp)
    # Fixed slug: all replies (On it! + final) write to the same comment.
    # Concurrent handlers hitting the same target will 409 on create and
    # just update the existing comment instead of creating duplicates.
    mcp.reply_slug = "reply"
    tools = await mcp.api_tools()

    # Username comes from the server (via the GQL query that loaded the thread)
    my_username = mcp.ctx.me
    _log(msg, f"authenticated as @{my_username}")

    # Don't reply to our own comments — the focused comment is the one we'd
    # be replying under. If we wrote it, there's nothing to respond to.
    focused = mcp.ctx.comment or mcp.ctx.topic
    if focused and focused.creator == my_username:
        _log(msg, f"skip: focused comment by ourselves (@{my_username})")
        return

    if focused:
        _log(msg, f"focused on {focused.ref} by @{focused.creator}")
    else:
        _log(msg, "no focused comment/topic found")

    # Check for existing replies from us
    if mcp.ctx.has_my_reply:
        _log(msg, "skip: already replied to this comment")
        return

    def on_reply(text: str) -> str:
        elapsed = time.time() - start
        return f"{text}\n\n---\n^^ Generated in {elapsed:.1f}s using {MODEL}"

    mcp.on_reply = on_reply

    # Instant acknowledgement — will be overwritten with the real reply.
    # Uses the fixed slug, so concurrent "On it!" posts are idempotent.
    if msg.actor != my_username:
        _log(msg, "posting 'On it!' acknowledgement")
        ack_result = await mcp.call_tool("novem_reply", {"text": "On it!"})
        ack_text = _tool_content(ack_result)[0].text
        _log(msg, f"  ack result: {ack_text}")
    else:
        _log(msg, "actor is us, skipping acknowledgement")

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

    _log(msg, f"calling {MODEL} (thread context: {len(thread)} chars)")

    messages: List[Any] = [
        {
            "role": "user",
            "content": prompt,
        },
    ]

    turn = 0
    while True:
        turn += 1
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )

        tool_blocks = [b for b in resp.content if b.type == "tool_use"]
        text_blocks = [b for b in resp.content if b.type == "text"]

        if not tool_blocks:
            if text_blocks:
                _log(msg, f"turn {turn}: model finished with text (no tool call)")
            else:
                _log(msg, f"turn {turn}: model finished (empty response)")
            break

        tool_names = [b.name for b in tool_blocks]
        _log(msg, f"turn {turn}: model called {tool_names}")

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in tool_blocks:
            try:
                result = await mcp.call_tool(block.name, block.input)
            except Exception as e:
                _log(msg, f"  tool {block.name} error: {e}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(e), "is_error": True})
                continue
            content = _tool_content(result)
            result_content: List[Any] = []
            for item in content:
                if item.type == "image":
                    result_content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": getattr(item, "mime_type", None) or item.mimeType,
                                "data": item.data,
                            },
                        }
                    )
                else:
                    preview = item.text[:100].replace("\n", " ")
                    _log(msg, f"  tool {block.name} -> {preview}{'...' if len(item.text) > 100 else ''}")
                    result_content.append({"type": "text", "text": item.text})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_content})
        messages.append({"role": "user", "content": results})

    elapsed = time.time() - start
    _log(msg, f"done in {elapsed:.1f}s ({turn} turn{'s' if turn != 1 else ''})")


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
