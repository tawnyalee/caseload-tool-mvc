# scripts/mongoose_login.py
"""One-off, run-by-hand tool: opens a real browser window to log into
Mongoose (Cadence), then saves that session for the Playwright-based
Mongoose automation to reuse - see
src/services/mongoose_browser_session.py for the full explanation of why
this has to be interactive rather than fully automated. Completely
separate from Salesforce's own login/session (scripts/salesforce_login.py)
- a different site with its own credentials.

Run manually, and re-run whenever the saved session has expired:

    python scripts/mongoose_login.py

The login URL defaults to Mongoose's sign-in page - override with the
MONGOOSE_LOGIN_URL environment variable if this org uses a different one
(e.g. an SSO-specific entry point).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from src.services.mongoose_browser_session import save_session_interactively

DEFAULT_LOGIN_URL = "https://sms.mongooseresearch.com"


def main() -> None:
    login_url = os.environ.get("MONGOOSE_LOGIN_URL", DEFAULT_LOGIN_URL)
    with sync_playwright() as playwright:
        save_session_interactively(playwright, login_url)


if __name__ == "__main__":
    main()
