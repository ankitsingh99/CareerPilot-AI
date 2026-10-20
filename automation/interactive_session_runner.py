#!/usr/bin/env python3
"""
Universal Interactive Session Controller with Dynamic Python & JS Execution Loop.
Keeps a persistent browser open continuously and executes commands via scratch IPC.

Usage:
    python tools/interactive_session_runner.py --url "<JOB_URL>" [--app-dir "<DIR_PATH>"]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).parent.parent
SESSION_DIR = ROOT_DIR / ".browser_session"
SCRATCH_DIR = ROOT_DIR / "scratch"
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RESUME_PATH = ROOT_DIR / os.getenv("CANDIDATE_MASTER_RESUME", "cv/resume.pdf")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def alert(title: str, message: str):
    try:
        subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ])
    except Exception:
        pass

def parse_args():
    parser = argparse.ArgumentParser(description="Universal Interactive Session Controller")
    parser.add_argument("--url", default="", help="Target job URL to open")
    parser.add_argument("--app-dir", default="", help="Directory for storing screenshots & session audits")
    parser.add_argument("--cmd-file", default="", help="Custom IPC command file path")
    return parser.parse_args()

def main():
    args = parse_args()
    
    app_dir = Path(args.app_dir) if args.app_dir else SCRATCH_DIR
    app_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = Path(args.cmd_file) if args.cmd_file else SCRATCH_DIR / "cmd.txt"
    status_file = SCRATCH_DIR / "status.json"
    shot_path = app_dir / "step_current.png"

    print(f"[session] Starting universal interactive browser session...")
    pw = sync_playwright().start()
    try:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            no_viewport=True,
            user_agent=USER_AGENT,
            args=["--start-maximized", "--no-default-browser-check"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
    except Exception as e:
        print(f"[session] Launch exception ({e}). Launching headed standalone browser...")
        browser = pw.chromium.launch(
            headless=False,
            args=["--start-maximized", "--no-default-browser-check"]
        )
        ctx = browser.new_context(
            no_viewport=True,
            user_agent=USER_AGENT,
        )
        page = ctx.new_page()

    target_url = args.url.strip()
    if target_url and target_url not in page.url:
        print(f"[session] Navigating to target URL -> {target_url}")
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as err:
            print(f"[session] Navigation warning: {err}")

    time.sleep(3)
    try:
        page.screenshot(path=str(shot_path))
    except Exception:
        pass
    
    status_file.write_text(json.dumps({
        "status": "ready",
        "url": page.url,
        "title": page.title(),
        "time": time.time()
    }))

    print(f"[session] Page ready: {page.url} | Title: {page.title()}")
    print(f"[session] Listening for IPC commands on {cmd_file}...")

    # Main Command Execution Loop
    while True:
        if cmd_file.exists():
            cmd_content = cmd_file.read_text().strip()
            cmd_file.unlink(missing_ok=True)
            if not cmd_content:
                time.sleep(0.5)
                continue

            print(f"\n[session] Executing command: {cmd_content[:60]}...")
            try:
                if len(ctx.pages) > 1:
                    page = ctx.pages[-1]

                if cmd_content.startswith("py:"):
                    code_to_exec = cmd_content[3:].strip()
                    exec_scope = {
                        "page": page,
                        "ctx": ctx,
                        "pw": pw,
                        "time": time,
                        "alert": alert,
                        "RESUME_PATH": DEFAULT_RESUME_PATH,
                        "SHOT_PATH": shot_path,
                        "APP_DIR": app_dir,
                    }
                    exec(code_to_exec, exec_scope)

                elif cmd_content == "click_continue":
                    clicked = False
                    for sel in [
                        "button:has-text('Continue')",
                        "button:has-text('Sign In')",
                        "button:has-text('Sign in')",
                        "button:has-text('Next')",
                        "button[type='submit']",
                        "button.btn-primary",
                        "input[type='submit']",
                    ]:
                        try:
                            btn = page.query_selector(sel)
                            if btn and btn.is_visible():
                                print(f"[session] Clicking button via {sel}...")
                                btn.click()
                                clicked = True
                                break
                        except Exception:
                            pass

                    if not clicked:
                        print("[session] Fallback: Clicking primary button via evaluate...")
                        page.evaluate("""() => {
                            let btns = Array.from(document.querySelectorAll('button, input[type=submit]'));
                            let b = btns.find(el => el.innerText.toLowerCase().includes('continue') || el.type === 'submit');
                            if (b) b.click();
                        }""")

                    time.sleep(4)
                    if len(ctx.pages) > 1:
                        page = ctx.pages[-1]

                    b_txt = (page.inner_text("body") or "").lower()
                    if "code" in b_txt or "otp" in b_txt or "verification" in b_txt:
                        alert("Verification Code Needed", "Please enter the OTP verification code in the browser window.")

                elif cmd_content == "screenshot":
                    pass

                elif cmd_content.startswith("goto "):
                    nav_url = cmd_content.replace("goto ", "").strip()
                    page.goto(nav_url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(3)

                time.sleep(2)
                if len(ctx.pages) > 1:
                    page = ctx.pages[-1]
                try:
                    page.screenshot(path=str(shot_path))
                except Exception:
                    pass

                status_file.write_text(json.dumps({
                    "status": "done",
                    "last_cmd": cmd_content[:40],
                    "url": page.url,
                    "title": page.title(),
                    "time": time.time()
                }))
                print(f"[session] Completed. Current URL: {page.url} | Title: {page.title()}")

            except Exception as e:
                print(f"[session] Error executing '{cmd_content[:30]}': {e}")
                status_file.write_text(json.dumps({
                    "status": "error",
                    "error": str(e),
                    "time": time.time()
                }))

        time.sleep(0.5)

if __name__ == "__main__":
    main()
