# src/services/mongoose_browser_session.py
"""Playwright-based browser session management for Mongoose (Cadence),
mirroring salesforce_browser_session.py's approach - MFA/SSO can't be
completed by unattended code, so this is deliberately semi-interactive:
scripts/mongoose_login.py opens a real, visible browser window once, the
developer logs in themselves, and the resulting session (cookies/local
storage) is saved to STORAGE_STATE_PATH. Anything that needs an
authenticated Mongoose session afterward loads that saved state instead of
logging in again, until the session expires - at which point
scripts/mongoose_login.py needs to be re-run.

This is a COMPLETELY SEPARATE session/browser context from Salesforce's -
Mongoose is a different site with its own login, not something that
piggybacks on the Salesforce session at all.

STORAGE_STATE_PATH's contents are as sensitive as a password - whoever
holds the file can act as the logged-in session. Never commit it, never
log its contents; .gitignore already excludes it.
"""
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_STATE_PATH = REPO_ROOT / "data" / ".mongoose_session.json"


def has_saved_session() -> bool:
    return STORAGE_STATE_PATH.exists()


def save_session_interactively(playwright: Playwright, login_url: str) -> None:
    """Opens a real, visible browser at `login_url`, waits for the
    developer to log in manually, then saves the resulting session to
    STORAGE_STATE_PATH.

    "Logged in" is confirmed by the developer themselves (pressing Enter
    in the terminal) rather than guessed from the URL - same reasoning as
    salesforce_browser_session.py's identical function: an intermediate
    redirect hop could briefly look logged-in and save the session too
    early.
    """
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(login_url)

    print("Log in to Mongoose in the browser window that just opened.")
    input("Once you're fully logged in and see your normal Mongoose dashboard, press Enter here...")

    STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(STORAGE_STATE_PATH))
    browser.close()

    print(f"Session saved to {STORAGE_STATE_PATH}")


def open_authenticated_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """Returns a browser context pre-loaded with the saved session, for
    anything that needs to navigate authenticated Mongoose pages without
    logging in again. Raises RuntimeError if no session has been saved
    yet - callers should catch this and tell the user to run
    scripts/mongoose_login.py first."""
    if not has_saved_session():
        raise RuntimeError(
            f"No saved Mongoose session at {STORAGE_STATE_PATH}. "
            f"Run scripts/mongoose_login.py first to log in interactively."
        )
    browser = playwright.chromium.launch(headless=headless)
    return browser.new_context(storage_state=str(STORAGE_STATE_PATH))
