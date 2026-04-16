#!/bin/bash
# d2s_backup_guard.sh — PreToolUse hook
# Checks if a .d2s file is being modified without a recent backup.
# Reads tool_name and tool_input from stdin (JSON).

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')

# Only check Bash, Write, Edit
case "$TOOL" in
  Bash|Write|Edit) ;;
  *) exit 0 ;;
esac

# Extract the relevant path or command
if [ "$TOOL" = "Bash" ]; then
  CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
  # Check if command writes to a .d2s file
  if ! echo "$CMD" | grep -qE '\.d2s'; then
    exit 0
  fi
  # Extract .d2s paths from the command
  D2S_FILES=$(echo "$CMD" | grep -oE '[^ "'"'"']+\.d2s' | sort -u)
else
  # Write or Edit tool — check file_path
  FPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
  if [[ "$FPATH" != *.d2s ]]; then
    exit 0
  fi
  D2S_FILES="$FPATH"
fi

# For each .d2s file, check if a backup exists from the last 5 minutes
NOW=$(date +%s)
for F in $D2S_FILES; do
  if [ ! -f "$F" ]; then
    continue  # New file, no backup needed
  fi

  # Look for any .bak file for this save
  BASENAME=$(basename "$F")
  DIRNAME=$(dirname "$F")
  RECENT_BAK=0

  for BAK in "$DIRNAME"/"$BASENAME".*_bak "$DIRNAME"/"$BASENAME".bak; do
    if [ -f "$BAK" ]; then
      BAK_TIME=$(stat -c %Y "$BAK" 2>/dev/null || echo 0)
      AGE=$(( NOW - BAK_TIME ))
      if [ "$AGE" -lt 300 ]; then
        RECENT_BAK=1
        break
      fi
    fi
  done

  if [ "$RECENT_BAK" -eq 0 ]; then
    echo "⚠ D2S BACKUP GUARD: No recent backup (<5min) found for $BASENAME"
    echo "  Create one first: shutil.copy2('$F', '$F.pre_edit_bak')"
    echo "  Or via bash: cp '$F' '$F.pre_edit_bak'"
    # Hard block — prevent writes without backup.
    exit 2
  fi
done

exit 0
