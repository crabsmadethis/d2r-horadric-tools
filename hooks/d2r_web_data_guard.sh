#!/bin/bash
# PreToolUse: Warn when web-searching for D2R game data (Rule 9).
# Game data MUST come from d2r_chargen/data/ files, not web sources.
# Web sources have fabricated skill trees, tier lists, and forum posts.
# This is a WARNING (exit 0), not a block — some web searches are valid.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')

case "$TOOL" in
    WebSearch)
        QUERY=$(echo "$INPUT" | jq -r '.tool_input.query // ""' | tr '[:upper:]' '[:lower:]')
        ;;
    WebFetch)
        QUERY=$(echo "$INPUT" | jq -r '.tool_input.url // ""' | tr '[:upper:]' '[:lower:]')
        ;;
    *) exit 0 ;;
esac

# Data-related keywords that indicate game data lookup
DATA_KEYWORDS="unique item|set item|runeword|item stat|stat cost|skill tree|item code|item uid|item base|socket|d2r stat|diablo.*item.*stat|diablo.*runeword|diablo.*unique"

# Known D2R data wiki/database domains
DATA_DOMAINS="maxroll\.gg|d2runewizard|arreat.*summit|diablo\.fandom|d2\.lc|theamazonbasin"

WARNED=0

if echo "$QUERY" | grep -qiE "$DATA_KEYWORDS"; then
    WARNED=1
fi

if echo "$QUERY" | grep -qiE "$DATA_DOMAINS"; then
    WARNED=1
fi

if [ "$WARNED" -eq 1 ]; then
    echo "Rule 9 WARNING: D2R game data MUST come from d2r_chargen/data/ files."
    echo "  Use MCP data tools instead: d2r_lookup_unique, d2r_lookup_runeword, etc."
    echo "  Web sources have fabricated data. If data isn't in the data files, it doesn't exist."
fi

exit 0
