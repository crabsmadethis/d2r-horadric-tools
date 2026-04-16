#!/bin/bash
# SessionStart: remove verify-pending flags older than 1 hour (stale from crash).
if [ -f /tmp/d2r_verify_pending ]; then
    AGE=$(( $(date +%s) - $(stat -c %Y /tmp/d2r_verify_pending) ))
    if [ "$AGE" -gt 3600 ]; then
        rm -f /tmp/d2r_verify_pending
    fi
fi
exit 0
