#!/bin/bash
# Autonomous watchdog monitor for ai-job-search.
# Checks pipeline health, triggers healer, and alerts user via macOS notifications.
# Rule: Zero em dashes permitted.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${REPO_ROOT}/guard/watchdog.log"
HEALER_SCRIPT="${REPO_ROOT}/guard/healer.sh"

notify_user() {
    local title="$1"
    local message="$2"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        afplay /System/Library/Sounds/Glass.aiff 2>/dev/null || true
        osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
    fi
}

echo "$(date '+%Y-%m-%d %H:%M:%S') - Watchdog tick running." >> "$LOG_FILE"

# Run state healing
if [ -f "$HEALER_SCRIPT" ]; then
    bash "$HEALER_SCRIPT"
fi

# Check for jobs needing human attention
DB_PATH="${REPO_ROOT}/jobs.db"
if [ -f "$DB_PATH" ]; then
    NEEDS_HUMAN_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM jobs WHERE status = 'needs_human';")
    if [ "$NEEDS_HUMAN_COUNT" -gt 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Alert: $NEEDS_HUMAN_COUNT jobs need human attention." >> "$LOG_FILE"
        notify_user "AI Job Search Alert" "$NEEDS_HUMAN_COUNT job applications require your attention or manual verification."
    fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Watchdog tick completed." >> "$LOG_FILE"
