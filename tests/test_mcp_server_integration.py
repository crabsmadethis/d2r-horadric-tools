"""End-to-end test: spawn d2r_mcp over stdio and call a tool.

Catches transport-level regressions that unit tests can't see: FastMCP
serialization, async signatures, tool registration, return-type coercion.
"""
import json
import os
import sys
import pytest

# Marked integration: requires pytest-asyncio (not in the bare CI dev extras)
# plus the mcp client library plus extracted game data.
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_server_lists_all_tool_categories():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "d2r_mcp"],
        env={**os.environ},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            # At least one tool from every category
            assert any(n.startswith("d2r_lookup_") for n in names), \
                f"no lookup tools in {sorted(names)}"
            assert any(n.startswith("d2r_save_") for n in names), \
                f"no save tools in {sorted(names)}"
            assert any(n.startswith("d2r_chargen_") for n in names), \
                f"no chargen tools in {sorted(names)}"
            assert any(n.startswith("d2r_mod_") for n in names), \
                f"no mod tools in {sorted(names)}"


@pytest.mark.asyncio
async def test_save_scan_over_stdio():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    fixture = os.path.join(
        os.path.dirname(__file__), "fixtures", "hexshade_lv98_haseen.d2s"
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "d2r_mcp"],
        env={**os.environ},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "d2r_save_scan", arguments={"path": fixture}
            )
            # FastMCP typically serializes dict returns into text content.
            # Parse the JSON payload from result.content[0].text.
            assert result.content, f"empty content: {result}"
            first = result.content[0]
            # Different FastMCP versions return TextContent with .text or dict
            # structured content — handle both.
            if hasattr(first, "text"):
                payload = json.loads(first.text)
            else:
                payload = first
            assert payload["status"] in ("ok", "error"), \
                f"unexpected status in payload: {payload}"
            assert "checksum_ok" in payload, \
                f"missing checksum_ok in payload: {payload}"
