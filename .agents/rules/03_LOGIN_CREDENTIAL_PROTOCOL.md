# HARD RULE: Login Credential Protocol (ZERO-TOLERANCE)

## Rule: Always Use Saved Credentials — Never Pause for Sign-In

When any job application portal presents a login screen (email + password form), you MUST:

1. **Immediately look up credentials** from `~/.config/job-agent/.candidate_secrets.json`:
   - First check `accounts[]` list for a domain-specific match (`company`, `website`).
   - If no exact match, fall back to `standard_ats_password` with `email` field.
2. **Fill and submit the form silently** — do NOT pause, do NOT ask the user.
3. **Never interrupt the user** for email/password login under any circumstances.

## The ONLY exceptions that require human attention:

- **CAPTCHA** (image/checkbox/puzzle challenge)
- **OTP / 2FA** (one-time code sent to phone or email)
- **Biometric or hardware key prompt**
- **Security warning** indicating account lockout risk

In these cases ONLY: sound `Glass.aiff`, send a macOS notification, and pause.

## On Auth Failure (wrong password):

- If login fails with saved credentials, do NOT retry with guesses.
- Check `accounts[]` again for any alternate entry for the same domain.
- If still no match, sound notification and pause — but NEVER ask the user to type credentials.
- The user will correct the saved secrets file; automation picks up after that.

## Credential Lookup Priority

1. `accounts[]` where portal domain matches `website` field
2. `standard_ats_password` + `email` (global fallback)
