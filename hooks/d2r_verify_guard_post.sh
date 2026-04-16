#!/bin/bash
# PostToolUse: set/clear verify-pending flag after chargen builds.
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_output.exit_code // ""')

# Job 1: After a full chargen build (no --phase, no --verify), set the flag
if echo "$CMD" | grep -qE 'd2r_chargen\s+build'; then
    if ! echo "$CMD" | grep -qE -- '--verify|--phase'; then
        CHAR=$(echo "$CMD" | grep -oP 'd2r_chargen\s+build\s+\K\w+')
        if [ -n "$CHAR" ] && [ "$EXIT_CODE" = "0" ]; then
            echo "$CHAR" > /tmp/d2r_verify_pending
        fi
    fi
fi

# Job 2: After a successful verify, clear the flag
if echo "$CMD" | grep -qE 'd2r_mod\s+verify|d2r_chargen\s+build\s+\S+\s+--verify'; then
    if [ "$EXIT_CODE" = "0" ]; then
        rm -f /tmp/d2r_verify_pending
    fi
fi

exit 0
