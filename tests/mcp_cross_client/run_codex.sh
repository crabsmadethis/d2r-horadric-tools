#!/usr/bin/env bash
# Invoke Codex as a d2r-tools MCP client against matrix.yaml.
# Writes raw Codex output to codex_report.out for diff against Claude.
#
# Requires: codex CLI logged in (`codex login status`) with d2r-tools
# registered in ~/.codex/config.toml:
#   [mcp_servers.d2r-tools]
#   command = "python3"
#   args = ["-m", "d2r_mcp"]
set -u
cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"
OUT="tests/mcp_cross_client/codex_report.out"
: > "$OUT"

PROMPT='Read the file tests/mcp_cross_client/matrix.yaml. For EACH row in `rows`, do this:
1. Use tool_search_tool to load the d2r-tools MCP tool named in `tool` (e.g. `d2r_search`).
2. Call that tool with the exact `args` mapping. Do not modify types — if args has `{"query": 248}` (integer), pass an integer. If `{"yaml_only": true}` pass a boolean.
3. Capture the raw tool response text (or error message if the call raised).

After ALL rows have been processed, emit ONE final fenced ```json block containing:
{
  "client": "codex",
  "results": [
    {"id": <n>, "tool": "<name>", "raw_response": "<first 2000 chars of raw, or null on error>", "error": "<message or null>"}
  ]
}

The results list must have exactly one entry per matrix row, in matrix order. Emit no prose before or after the JSON block. Do not stop early. If any tool errors, put the error in `error` and set `raw_response` to null and CONTINUE to the next row.'

timeout 600 codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  --cd "$REPO_ROOT" \
  -c model_reasoning_effort='"low"' \
  "$PROMPT" > "$OUT" 2>&1
echo "--- exit: $? ---" >> "$OUT"
