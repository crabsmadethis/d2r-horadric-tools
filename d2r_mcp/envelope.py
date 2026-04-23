"""Shared response envelope for d2r_mcp tools.

Every MCP tool returns a dict with a top-level "status" field of "ok" or "error".
On error, details live under "error": {"type": str, "detail": str}. Tool-specific
payload fields are merged into the envelope at the top level.
"""


def ok(**payload) -> dict:
    """Return a success envelope with the given payload merged in."""
    return {"status": "ok", **payload}


def error(type: str, detail: str, **extra) -> dict:
    """Return an error envelope with a typed error and optional extra fields."""
    return {"status": "error", "error": {"type": type, "detail": detail}, **extra}
