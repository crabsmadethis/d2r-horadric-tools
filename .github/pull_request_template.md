## Summary

<!-- One or two sentences. What does this PR change and why? -->

## Changes

<!-- Bullet list of what you actually changed. Skip files that are mechanical (formatting, renames). -->

-

## Testing

<!-- What did you run? Tier 1 alone is fine for most changes. Note if you ran the slower tiers locally. -->

- [ ] Tier 1 passes: `pytest tests/ -v --timeout=60 -m "not integration and not slow and not e2e and not smoke" --ignore=tests/fixtures/ --ignore=tests/test_chargen.py --ignore=tests/test_decoder.py --ignore=tests/test_fixtures.py --ignore=tests/test_importer.py`
- [ ] Public hygiene passes: `python tools/public_hygiene_check.py`
- [ ] Added or updated tests for the change
- [ ] Tested manually (describe how)

## Save-file safety (only if this PR writes to `.d2s`)

- [ ] Backup is taken before any write
- [ ] Writes go to a temp/staging file, scanner runs before promoting
- [ ] Scanner passes on the resulting file
- [ ] Checksum verified

## MCP changes (only if `d2r_mcp/` is touched)

- [ ] `d2r_mcp/README.md` updated (tool list / count)
- [ ] Root `README.md` tool count updated if changed
- [ ] Tests added in `tests/test_mcp_*.py`

## Related issues

<!-- "Closes #123" or "Refs #45" -->
