"""FastMCP server exposing D2R game data lookup tools.

Usage:
    python3 -m d2r_mcp          # stdio transport (for Claude Code)
"""
import sys

from mcp.server.fastmcp import FastMCP

from d2r_mcp.lookups import (
    lookup_unique, lookup_set_item, lookup_item_base,
    lookup_runeword, lookup_stat, lookup_skill, search_all,
)

mcp = FastMCP("d2r-data")


@mcp.tool()
async def d2r_lookup_unique(query: str) -> str:
    """Look up a D2R unique item by name or numeric UID.

    Searches unique_items.py data. Returns item info + stats.
    Supports substring matching (e.g. "harlequin" finds Harlequin Crest).

    Args:
        query: Item name (or substring) or numeric UID
    """
    return lookup_unique(query)


@mcp.tool()
async def d2r_lookup_set_item(query: str) -> str:
    """Look up a D2R set item by name or numeric ID.

    Searches set_items.py data. Returns item info + set membership.
    Supports substring matching.

    Args:
        query: Item name (or substring) or numeric set item ID
    """
    return lookup_set_item(query)


@mcp.tool()
async def d2r_lookup_item_base(query: str) -> str:
    """Look up a D2R base item by 3-char code or name.

    Searches item_bases.py data. Returns dimensions, requirements, sockets.
    Supports substring matching on names.

    Args:
        query: 3-character item code (e.g. "hax") or item name
    """
    return lookup_item_base(query)


@mcp.tool()
async def d2r_lookup_runeword(query: str) -> str:
    """Look up a D2R runeword by name or numeric ID.

    Searches runewords.py data. Returns runes, valid bases, stats.
    Supports substring matching.

    Args:
        query: Runeword name (or substring) or numeric runeword ID
    """
    return lookup_runeword(query)


@mcp.tool()
async def d2r_lookup_stat(query: str) -> str:
    """Look up a D2R stat by ID, canonical name, or YAML alias.

    Searches item_stat_cost.py data. Returns encoding info (save bits,
    save add, param bits, value shift) needed for binary stat encoding.

    Args:
        query: Stat ID, canonical name (e.g. "fireresist"), or alias (e.g. "fcr")
    """
    return lookup_stat(query)


@mcp.tool()
async def d2r_lookup_skill(query: str) -> str:
    """Look up a D2R skill by name or numeric ID.

    Searches skills.py data. Returns skill ID and class.
    Supports substring matching.

    Args:
        query: Skill name (or substring) or numeric skill ID
    """
    return lookup_skill(query)


@mcp.tool()
async def d2r_search(query: str) -> str:
    """Search across ALL D2R item types: uniques, sets, runewords, bases.

    Use this when you don't know what type of item you're looking for.
    Returns up to 20 results tagged by type.

    Args:
        query: Search term (substring match across all item names)
    """
    return search_all(query)


def main():
    sys.stderr.write("D2R data MCP server starting...\n")
    mcp.run(transport="stdio")
