# scripts/salesforce_login.py
"""One-off, run-by-hand tool: opens a real browser window to log into
Salesforce (including completing MFA yourself), then saves that session
for the Playwright-based adapters to reuse - see
src/services/salesforce_browser_session.py for the full explanation of
why this has to be interactive rather than fully automated.

Run manually, and re-run whenever the saved session has expired:

    python scripts/salesforce_login.py

The login URL defaults to your org's My Domain host - override with the
SF_LOGIN_URL environment variable if needed (e.g. a sandbox, or a
different path than /lightning).
"""
import os

from playwright.sync_api import sync_playwright

from src.services.salesforce_browser_session import save_session_interactively

DEFAULT_LOGIN_URL = "https://srm.lightning.force.com"


def main() -> None:
    login_url = os.environ.get("SF_LOGIN_URL", DEFAULT_LOGIN_URL)
    with sync_playwright() as playwright:
        save_session_interactively(playwright, login_url)


if __name__ == "__main__":
    main()
