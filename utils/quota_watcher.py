#!/usr/bin/env python3
"""Quota watcher that periodically checks model token usage and notifies when usage drops below a threshold.
It runs indefinitely as a background daemon. The threshold is a heuristic for when the model quota has been reset.
"""
import time, subprocess, os, sys, re

# Adjust these values as needed
THRESHOLD_TOKENS = 2000  # Consider quota reset if total token usage is below this
CHECK_INTERVAL_SECONDS = 1800  # 15 minutes

def get_total_tokens():
    try:
        # Run the token audit script and capture output
        result = subprocess.run(["python3", "token-kit/tools/token_audit.py"], capture_output=True, text=True, timeout=60)
        output = result.stdout
        # Look for the line containing "TOTAL always‑on ~"
        match = re.search(r"TOTAL always‑on ~([0-9]+)t", output)
        if match:
            return int(match.group(1))
    except Exception as e:
        print(f"Quota watcher error: {e}", file=sys.stderr)
    return None

def notify_reset():
    # macOS notification with chime
    os.system('afplay /System/Library/Sounds/Glass.aiff && osascript -e "display notification \"Model quota appears reset – you can start applying.\" with title \"Quota Reset\""')

if __name__ == "__main__":
    # Run forever
    while True:
        tokens = get_total_tokens()
        if tokens is not None:
            # Debug print (goes to the daemon log)
            print(f"[QuotaWatcher] Total tokens: {tokens}")
            if tokens < THRESHOLD_TOKENS:
                notify_reset()
        else:
            print("[QuotaWatcher] Could not determine token usage.")
        time.sleep(CHECK_INTERVAL_SECONDS)
