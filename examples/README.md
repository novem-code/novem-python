# Examples

## mention_responder.py

Listens for `@mention` events and prints the thread context. Auto-replies with a thank-you message.

```
uv run --extra events examples/mention_responder.py
```

## mcp_mention_responder.py

Same idea, but hands Claude an MCP server so it can explore the thread and craft its own reply.

Requires an `ANTHROPIC_API_KEY` in `.env` or environment.

```
uv run --extra events --extra mcp --with anthropic --with python-dotenv examples/mcp_mention_responder.py
```

Optional: pass custom event patterns as arguments:

```
uv run --extra events --extra mcp --with anthropic --with python-dotenv examples/mcp_mention_responder.py "/u/<user>/p/*/e/mention"
```
