# src/services/salesforce_browser_session.py
"""Playwright-based browser session management for Salesforce, used when
API access isn't available (see src/CLAUDE.md - other developers doing
similar integration work at this org hit the same wall and had to fall
back to browser automation).

MFA can't be completed by an automated script - there's no way for code
running unattended to receive a push notification or read a code off the
developer's phone. So this is deliberately semi-interactive:
scripts/salesforce_login.py opens a real, visible browser window once,
the developer logs in themselves (MFA included), and the resulting
session (cookies/local storage) is saved to STORAGE_STATE_PATH. Anything
that needs an authenticated Salesforce session afterward
(PlaywrightStudentDataProvider, a future note-writing adapter) loads that
saved state instead of logging in again, until the session expires - at
which point scripts/salesforce_login.py needs to be re-run.

STORAGE_STATE_PATH's contents are as sensitive as a password - whoever
holds the file can act as the logged-in session. Never commit it, never
log its contents; .gitignore already excludes it.
"""
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_STATE_PATH = REPO_ROOT / "data" / ".salesforce_session.json"


def has_saved_session() -> bool:
    return STORAGE_STATE_PATH.exists()


def save_session_interactively(playwright: Playwright, login_url: str) -> None:
    """Opens a real, visible browser at `login_url`, waits for the
    developer to log in manually (including MFA), then saves the
    resulting session to STORAGE_STATE_PATH.

    "Logged in" is confirmed by the developer themselves (pressing Enter
    in the terminal) rather than guessed from the URL - the org's actual
    SSO/MFA redirect chain isn't known in advance, and an intermediate
    redirect hop briefly matching "looks logged in" caused the session to
    be saved before login had actually happened.
    """
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(login_url)

    print("Log in (including MFA) in the browser window that just opened.")
    input("Once you're fully logged in and see your normal Salesforce/Learner360 view, press Enter here...")

    STORAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(STORAGE_STATE_PATH))
    browser.close()

    print(f"Session saved to {STORAGE_STATE_PATH}")


def open_authenticated_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """Returns a browser context pre-loaded with the saved session, for
    anything that needs to navigate authenticated Salesforce pages
    without logging in again. Raises RuntimeError if no session has been
    saved yet - callers should catch this and tell the user to run
    scripts/salesforce_login.py first."""
    if not has_saved_session():
        raise RuntimeError(
            f"No saved Salesforce session at {STORAGE_STATE_PATH}. "
            f"Run scripts/salesforce_login.py first to log in interactively."
        )
    browser = playwright.chromium.launch(headless=headless)
    return browser.new_context(storage_state=str(STORAGE_STATE_PATH))
