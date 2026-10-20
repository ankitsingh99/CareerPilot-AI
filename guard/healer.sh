#!/bin/bash
# Autonomous state healer for ai-job-search database.
# Recovers leased jobs that timed out or crashed during processing.
# Rule: Zero em dashes permitted.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${REPO_ROOT}/jobs.db"
LOG_FILE="${REPO_ROOT}/guard/healer.log"

if [ ! -f "$DB_PATH" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Database not found at $DB_PATH, skipping heal." >> "$LOG_FILE"
    exit 0
fi

NOW=$(date +%s)

# Reset applying jobs whose lease expired more than 300 seconds ago
sqlite3 "$DB_PATH" <<EOF
UPDATE jobs 
SET status = 'ready_to_apply', claim_pid = NULL, lease_until = NULL, updated_at = CURRENT_TIMESTAMP
WHERE status = 'applying' AND lease_until IS NOT NULL AND lease_until < $NOW;

INSERT INTO audit_logs (job_id, action, details)
SELECT id, 'healer_recovery', 'Reset expired lease back to ready_to_apply'
FROM jobs
WHERE status = 'ready_to_apply' AND updated_at >= datetime('now', '-1 minute');
EOF

echo "$(date '+%Y-%m-%d %H:%M:%S') - Healer cycle completed successfully." >> "$LOG_FILE"
