"""Unit tests for independent portal credential loading and auth/register flow."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import browser


class _FakeElement:
    def __init__(self, visible: bool = True, value: str = "", attrs: dict | None = None):
        self._visible = visible
        self._value = value
        self._attrs = attrs or {}
        self.clicks = 0

    def is_visible(self) -> bool:
        return self._visible

    def input_value(self) -> str:
        return self._value

    def fill(self, val: str) -> None:
        self._value = val

    def click(self, **_kwargs) -> None:
        self.clicks += 1

    def press(self, _key: str) -> None:
        pass

    def get_attribute(self, key: str) -> str:
        return self._attrs.get(key, "")


class TestCandidateCredentialsAndAuthFlow(unittest.TestCase):
    def test_get_candidate_credentials_merges_secrets_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_secret = tmp_path / "client_secret.json"
            global_secret = tmp_path / "global_client_secret.json"
            legacy_dot_secret = tmp_path / ".candidate_secrets.json"

            repo_secret.write_text(
                json.dumps(
                    {
                        "candidate_profile": {"first_name": "Test"},
                        "credentials": {
                            "default_email": "secret@example.com",
                            "default_password": "PrimarySecretPassword1!",
                            "alternate_password1": "AltOne1!",
                        },
                    }
                ),
                encoding="utf-8",
            )
            legacy_dot_secret.write_text(
                json.dumps(
                    {
                        "email": "legacy@example.com",
                        "standard_ats_password": "LegacyStandardPassword1!",
                        "alternate_password": "AltTwo2!",
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(browser, "DEFAULT_CANDIDATE", {"first_name": "", "email": ""}),
                mock.patch.object(browser, "SECRETS_FILE", repo_secret),
                mock.patch.object(browser, "GLOBAL_SECRETS_FILE", global_secret),
                mock.patch.object(browser, "LEGACY_SECRETS_FILE", legacy_dot_secret),
                mock.patch.object(browser.Path, "home", return_value=tmp_path),
                mock.patch.dict(
                    os.environ,
                    {
                        "CANDIDATE_EMAIL": "env_user@example.com",
                        "CANDIDATE_STANDARD_PASSWORD": "EnvPassword1!",
                        "CANDIDATE_ALT_PASSWORD": "AltOne1!",
                    },
                    clear=False,
                ),
            ):
                prof, email, pwd, alts = browser.get_candidate_credentials()

            self.assertEqual(email, "env_user@example.com")
            self.assertEqual(prof["first_name"], "Test")
            self.assertEqual(pwd, "PrimarySecretPassword1!")
            self.assertEqual(
                alts,
                ["AltOne1!", "LegacyStandardPassword1!", "AltTwo2!", "EnvPassword1!"],
            )

    def test_auto_authenticate_switches_create_account_tries_passwords_then_registers(self):
        call_order: list[str] = []
        browser._AUTHENTICATION_ATTEMPTS.clear()

        class _FakePage:
            url = "https://example.wd503.myworkdayjobs.com/apply/autofillWithResume"

            def __init__(self):
                self.on_create_account = True

            def query_selector(self, sel: str):
                if "verifyPassword" in sel or "createAccountSubmitButton" in sel or "createAccountPage" in sel:
                    return _FakeElement(visible=self.on_create_account)
                if "signInLink" in sel and self.on_create_account:
                    link = _FakeElement(visible=True, attrs={"data-automation-id": "signInLink"})
                    orig_click = link.click

                    def _switch(**kw):
                        orig_click(**kw)
                        call_order.append("switch_to_signin")
                        self.on_create_account = False

                    link.click = _switch
                    return link
                if "signInContent" in sel or "password" in sel:
                    return _FakeElement(visible=True)
                return None

            def inner_text(self, _sel: str) -> str:
                return "Create Account" if self.on_create_account else "Sign In"

        fake_page = _FakePage()

        def _fake_login(_page, _email, pwd, is_retry=False):
            call_order.append(f"login:{pwd}:retry={is_retry}")
            return False, False

        def _fake_register(_page, _prof, reg_email, reg_pwd, _ats, _url):
            call_order.append(f"register:{reg_email}:{reg_pwd}")
            return True

        with (
            mock.patch.object(
                browser,
                "get_candidate_credentials",
                return_value=({"email": "u@example.com"}, "u@example.com", "Primary1!", ["Alt1!"]),
            ),
            mock.patch.object(
                browser,
                "get_portal_credentials",
                return_value=("u@example.com", "Primary1!", ["Alt1!"]),
            ),
            mock.patch.object(browser, "_attempt_login_step", side_effect=_fake_login),
            mock.patch.object(browser, "_attempt_register", side_effect=_fake_register),
            mock.patch.object(browser, "alert"),
            mock.patch.dict(
                os.environ,
                {"CANDIDATE_EMAIL": "env@example.com", "CANDIDATE_STANDARD_PASSWORD": "EnvPassword1!"},
                clear=False,
            ),
        ):
            result = browser.auto_authenticate_or_register(
                fake_page, "workday", "https://example.wd503.myworkdayjobs.com/job/1"
            )

        self.assertTrue(result)
        self.assertEqual(
            call_order,
            [
                "switch_to_signin",
                "login:Primary1!:retry=False",
                "login:Alt1!:retry=True",
                "register:env@example.com:EnvPassword1!",
            ],
        )

    def test_auto_authenticate_halts_on_lockout_without_retry_or_register(self):
        call_order: list[str] = []
        browser._AUTHENTICATION_ATTEMPTS.clear()

        class _LockedPage:
            url = "https://locked.wd503.myworkdayjobs.com/login"

            def query_selector(self, sel: str):
                if "password" in sel:
                    return _FakeElement(visible=True)
                return None

            def inner_text(self, _sel: str) -> str:
                return "Sign In"

        def _fake_login_locked(_page, _email, pwd, is_retry=False):
            call_order.append(f"login:{pwd}")
            return False, True

        def _fake_register(*_args, **_kwargs):
            call_order.append("register_should_not_run")
            return True

        with (
            mock.patch.object(
                browser,
                "get_candidate_credentials",
                return_value=({"email": "u@example.com"}, "u@example.com", "Primary1!", ["Alt1!"]),
            ),
            mock.patch.object(
                browser,
                "get_portal_credentials",
                return_value=("u@example.com", "Primary1!", ["Alt1!"]),
            ),
            mock.patch.object(browser, "_attempt_login_step", side_effect=_fake_login_locked),
            mock.patch.object(browser, "_attempt_register", side_effect=_fake_register),
            mock.patch.object(browser, "alert"),
        ):
            result = browser.auto_authenticate_or_register(
                _LockedPage(), "workday", "https://locked.wd503.myworkdayjobs.com/job/2"
            )

        self.assertFalse(result)
        self.assertEqual(call_order, ["login:Primary1!"])

    def test_upload_resume_skips_photo_upload_and_duplicate_resume(self):
        uploaded_paths: list[str] = []

        class _FakeFileInput:
            def __init__(self, meta_info: dict):
                self._meta_info = meta_info

            def evaluate(self, _script: str, _arg=None):
                return self._meta_info

            def set_input_files(self, path: str):
                uploaded_paths.append(path)

        photo_inp = _FakeFileInput({"accept": "image/*", "meta": "photo upload *", "hasExistingItem": False})
        existing_resume_inp = _FakeFileInput(
            {"accept": ".pdf", "meta": "resume/cv upload a file", "hasExistingItem": True}
        )

        class _PageWithPhotoOnly:
            def query_selector_all(self, sel: str):
                if sel == "input[type='file']":
                    return [photo_inp]
                return []

            def query_selector(self, sel: str):
                if sel == "input[type='file']":
                    return photo_inp
                return None

        class _PageWithExistingResume:
            def query_selector_all(self, sel: str):
                if sel == "input[type='file']":
                    return [existing_resume_inp]
                return []

            def query_selector(self, sel: str):
                if sel == "input[type='file']":
                    return existing_resume_inp
                return None

        with mock.patch.object(browser, "RESUME_PATH", Path("/tmp/Ankit_Resume_v4.pdf")):
            self.assertFalse(browser._upload_resume(_PageWithPhotoOnly()))
            self.assertEqual(uploaded_paths, [])
            self.assertTrue(browser._upload_resume(_PageWithExistingResume()))
            self.assertEqual(uploaded_paths, [])


if __name__ == "__main__":
    unittest.main()
