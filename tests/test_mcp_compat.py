"""The mcp extra is optional, so nothing else in the suite imports it.

mcp 2.x renamed FastMCP to MCPServer and moved it out of mcp.server.fastmcp,
and renamed Tool.inputSchema to input_schema. These pin the surface
novem.comments.MCP() actually touches, against whichever major is installed.
"""

import asyncio

import pytest

pytest.importorskip("mcp", reason="the mcp extra is not installed")

from novem.comments import _import_mcp  # noqa: E402


def test_server_symbol_resolves_on_either_major():
    assert _import_mcp("FastMCP").__name__ in {"FastMCP", "MCPServer"}


def test_image_symbol_resolves_on_either_major():
    assert _import_mcp("Image").__name__ == "Image"


def test_missing_symbol_reports_the_extra():
    with pytest.raises(ImportError, match="mcp"):
        _import_mcp("NoSuchSymbolAnywhere")


def test_server_exposes_the_api_the_helper_uses():
    server = _import_mcp("FastMCP")("novem-comments (probe)")
    for attr in ("tool", "list_tools", "run"):
        assert hasattr(server, attr), f"server has no {attr}()"


def test_tool_input_schema_is_reachable():
    """Mirrors the api_tools() lookup in novem/comments.py."""
    server = _import_mcp("FastMCP")("novem-comments (probe)")

    @server.tool()
    def hello(name: str) -> str:
        """Say hello."""
        return f"hi {name}"

    tool = asyncio.run(server.list_tools())[0]
    assert tool.name == "hello"
    assert getattr(tool, "input_schema", None) or tool.inputSchema
