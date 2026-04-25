# Codex driver: d2r MCP cross-client parity test

You are being invoked from Claude Code to verify that the `d2r-tools`
MCP server returns the same results when consumed from Codex as it does
from Claude. Your job is narrow and mechanical — do not improvise.

## What you have access to

Your config (`~/.codex/config.toml`) registers `d2r-tools` as an MCP
server. Its tools are exposed to you under names like
`d2r-tools.d2r_search`, `d2r-tools.d2r_lookup_unique`, etc. (Use the
actual tool name your MCP client surface shows.)

## What to do

1. Read the test matrix at
   `tests/mcp_cross_client/matrix.yaml` (relative to the d2r-tools
   project root).

2. For each row, call the named d2r-tools MCP tool with exactly the
   `args` given. Do not modify the args. Do not call any other tools
   besides the d2r-tools ones and the shell `cat` needed to read the
   matrix.

3. For each row, determine PASS/FAIL:
   - If row has `must_contain`: serialize the tool's response as text.
     Row passes iff EVERY listed substring is present in the response.
   - If row has `error_regex`: row passes iff the tool raised an error
     whose message matches the regex. A successful response = FAIL for
     this row.

4. Collect results into a single JSON object and emit it as your
   FINAL message, wrapped in a fenced code block tagged `json`. No
   other prose after the JSON block.

## Output format (strict)

```json
{
  "client": "codex",
  "results": [
    {
      "id": 1,
      "tool": "d2r_search",
      "pass": true,
      "observed_excerpt": "first 300 chars of the raw tool response",
      "missing": [],
      "error": null
    }
  ],
  "summary": {"passed": 11, "failed": 0, "total": 11}
}
```

Field rules:
- `observed_excerpt`: first 300 chars of the tool's raw response
  (or the error message if the tool raised). Truncate cleanly.
- `missing`: for `must_contain` rows that fail, list the substrings
  that were absent. Empty list if row passed or is an `error_regex`
  row.
- `error`: the error message if the tool raised, else null.
- `summary.total` must equal `len(results)`.

## Guardrails

- Sandbox is read-only. You cannot write files or deploy anything.
- Do NOT call `d2r_chargen_build`, `d2r_mod_deploy`, `d2r_mod_build`,
  `d2r_mod_undeploy`, or any `d2r_save_*` tool beyond `d2r_save_scan`.
  Only the tools listed in the matrix.
- If a tool call hangs or takes > 30s, mark that row as failed with
  `error: "timeout"` and continue.
- Do not ask clarifying questions. If something is ambiguous, make the
  most conservative choice and note it in `observed_excerpt`.

Begin.
