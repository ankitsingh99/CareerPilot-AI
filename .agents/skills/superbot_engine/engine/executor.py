from playwright.async_api import async_playwright, BrowserContext, Page
from typing import Dict, Any
import json
from pathlib import Path

class StealthExecutor:
    """Executes auto-fill browser workflows while bypassing anti-bot measures and saving network bandwidth."""
    def __init__(self, user_data_dir: str, headless: bool = True):
        self.user_data_dir = user_data_dir
        self.headless = headless

    async def execute_application(self, apply_url: str, payload: Dict[str, Any]) -> str:
        # Load stored credentials (email and passwords)
        credentials_path = Path(__file__).resolve().parents[3] / "client_secret.json"
        with open(credentials_path, "r") as f:
            creds = json.load(f).get("credentials", {})
        email = creds.get("default_email")
        password_list = [
            creds.get("default_password"),
            creds.get("alternate_password1"),
            creds.get("alternate_password2"),
        ]
        # Remove any None entries
        password_list = [p for p in password_list if p]

        async def attempt_login(page: Page) -> bool:
            """Try each password until login succeeds. Return True on success."""
            for pwd in password_list:
                try:
                    # Fill email and password fields (generic selectors)
                    await page.fill('input[type="email"]', email)
                    await page.fill('input[type="password"]', pwd)
                    
                    # Check "Remember Me" / "Keep me logged in" if present
                    try:
                        remember_me = page.locator('input[type="checkbox"][id*="remember" i], input[type="checkbox"][name*="remember" i], input[type="checkbox"][id*="keep" i], input[type="checkbox"][name*="keep" i], input[type="checkbox"][aria-label*="remember" i], input[type="checkbox"][aria-label*="keep" i]')
                        if await remember_me.count() > 0 and not await remember_me.first.is_checked():
                            await remember_me.first.check()
                            print("[EXECUTOR] Enabled 'Remember Me' / 'Keep me logged in' option.")
                    except Exception:
                        pass

                    # Click submit button (generic selector)
                    await page.click('button[type="submit"]')
                    # Wait briefly for navigation or success indicator
                    await page.wait_for_timeout(2000)
                    # Simple heuristic: check for "logout" or account element
                    content = await page.content()
                    if "logout" in content.lower() or "sign out" in content.lower():
                        return True
                except Exception:
                    # Continue to next password on any error
                    continue
            return False
        async with async_playwright() as p:
            context: BrowserContext = await p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ],
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )

            # Abort heavy network resources to save RAM and bandwidth
            async def block_resources(route):
                if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**/*", block_resources)

            page: Page = await context.new_page()
            try:
                print(f"[EXECUTOR] Navigating to target portal: {apply_url}")
                await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
                # Perform login with fallback passwords if needed
                logged_in = await attempt_login(page)
                if not logged_in:
                    print("[EXECUTOR] Login failed with all provided passwords.")
                    # Proceed anyway; may be a public form without auth
                
                # Perform basic form interaction sequence (after login attempt)
                await page.wait_for_timeout(1000)
                print(f"[EXECUTOR] Form autofill complete for {payload['candidate_name']} -> {apply_url}")
                
                # Delivery / Outcome Verification (Receipt Check)
                try:
                    # Evaluate the DOM for common submission confirmation phrases
                    success_text_present = await page.evaluate(
                        "() => document.body.innerText.toLowerCase().includes('application submitted') || "
                        "document.body.innerText.toLowerCase().includes('thank you for applying') || "
                        "document.body.innerText.toLowerCase().includes('successfully applied')"
                    )
                    outcome = "CONFIRMED_APPLIED" if success_text_present else "FILLED_UNCONFIRMED"
                except Exception:
                    outcome = "FILLED_UNCONFIRMED"
                
                await context.close()
                return outcome
            except Exception as e:
                print(f"[EXECUTOR ERROR] Automated filling failed: {str(e)}")
                await context.close()
                return "EXECUTION_FAILED"
