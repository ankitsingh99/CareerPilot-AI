import os
import sys
import time
import subprocess
from pathlib import Path
import lazy_import
sync_playwright = lazy_import.lazy_callable("playwright.sync_api:sync_playwright")

def alert(title: str, message: str):
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ])

def parse_env():
    env_file = Path(".env")
    creds = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds

def run():
    creds = parse_env()
    email = creds.get("LINKEDIN_EMAIL", "")
    password = creds.get("LINKEDIN_PASSWORD", "")
    
    session_dir = Path(".browser_session").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    
    pw = sync_playwright().start()
    
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(session_dir),
        headless=False,
        no_viewport=True,
        args=["--start-maximized", "--no-default-browser-check", "--remote-debugging-port=9222"],
    )
        
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    time.sleep(2)
    
    curr = page.url
    print(f"[LinkedIn] Arrived at: {curr}")
    
    username_field = page.query_selector("#username")
    if username_field:
        username_field.fill(email)
        print("[LinkedIn] Filled email.")
        
    pwd_field = page.query_selector("#password")
    if pwd_field:
        pwd_field.fill(password)
        print("[LinkedIn] Filled password.")
        
    btn = page.query_selector("button[type='submit']")
    if btn:
        btn.click()
        print("[LinkedIn] Clicked Sign In.")
        time.sleep(5)
        
    curr = page.url
    print(f"[LinkedIn] URL after submit: {curr}")
    
    if "checkpoint" in curr or "challenge" in curr or "captcha" in curr:
        print("[LinkedIn] 2FA / Security challenge detected!")
        alert("LinkedIn Verification Needed", "Please enter OTP or verify security checkpoint in the browser.")
        for i in range(40):
            time.sleep(3)
            if "feed" in page.url or "jobs" in page.url:
                print("[LinkedIn] Login verified successfully!")
                break
    
    print("[LinkedIn] Page title:", page.title())
    print("[LinkedIn] Final URL:", page.url)
    
    # Do NOT close browser per user directive
    print("[LinkedIn] Browser will remain open. Pausing script...")
    while True:
        time.sleep(10)

if __name__ == "__main__":
    run()
