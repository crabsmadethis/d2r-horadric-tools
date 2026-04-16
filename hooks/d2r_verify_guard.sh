#!/bin/bash
# PreToolUse: block dangerous commands if a build is pending verification.
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
[ "$TOOL" = "Bash" ] || exit 0

# No pending verification — allow everything
[ -f /tmp/d2r_verify_pending ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Always allow verify commands (flag stays until PostToolUse confirms success)
if echo "$CMD" | grep -qE 'd2r_mod\s+verify'; then
    exit 0
fi
# Allow build --verify regardless of flag position (e.g., --force --verify)
if echo "$CMD" | grep -qE 'd2r_chargen\s+build' && echo "$CMD" | grep -q -- '--verify'; then
    exit 0
fi

# Block commands that modify .d2s files, deploy, or build
BLOCKED=0
# Chargen build (another build on top of unverified)
echo "$CMD" | grep -qE 'd2r_chargen\s+build' && BLOCKED=1
# Mod deploy
echo "$CMD" | grep -qE 'd2r_mod\s+deploy' && BLOCKED=1
# Direct .d2s file writes (cp TO .d2s, write redirects, python writing)
# Allow read-only ops: cat, ls, stat, scan, validate, diff, head, xxd
echo "$CMD" | grep -qE '(>\s*\S+\.d2s|cp\s+\S+\s+\S+\.d2s|shutil\.(copy|move)\S*.*\.d2s|deploy_character)' && BLOCKED=1

[ "$BLOCKED" -eq 0 ] && exit 0

CHAR=$(cat /tmp/d2r_verify_pending)
echo "BUILD PENDING VERIFICATION: $CHAR was built but not verified."
echo "  Run: python3 -m d2r_mod verify $CHAR"
echo "  Or:  python3 -m d2r_chargen build $CHAR --verify"
echo ""
echo "  The character must join a game successfully before more builds/deploys."
echo "  Escape hatch: rm /tmp/d2r_verify_pending"
exit 2
