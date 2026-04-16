#!/bin/bash
# PreToolUse: Block xdotool click/key commands (Rule 16).
# xdotool XTest events don't reach Wine/DirectInput.
# Use evdev.UInput with EV_KEY events instead.
# xdotool mousemove and windowactivate are still allowed.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
[ "$TOOL" = "Bash" ] || exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

if echo "$CMD" | grep -qE 'xdotool\s+(click|key|keydown|keyup|type|mousedown|mouseup)'; then
    echo "BLOCKED — Rule 16: xdotool click/key events don't reach Wine/DirectInput."
    echo "  Use evdev.UInput with EV_KEY events instead:"
    echo "    BTN_LEFT for mouse clicks, KEY_* for keyboard input."
    echo "  xdotool mousemove and windowactivate still work."
    exit 2
fi

exit 0
