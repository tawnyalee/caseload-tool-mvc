# src/services/salesforce_browser_session.py
"""Playwright-based browser session management for Salesforce, used when
API access isn't available (see src/CLAUDE.md - other developers doing
similar integration work at this org hit the same wall and had to fall
back to browser automation).

MFA can't be completed by code - there's no way for it to receive a push
notification or read a code off the professor's phone. So login is
deliberately interactive: log_in_interactively() opens a real, visible
browser window at the Caseload page, the professor logs in themselves
(password + MFA - the app never sees or handles either), and once the
Caseload page has actually loaded, the resulting session (cookies) is
kept IN MEMORY for the rest of this app session. Everything that needs an
authenticated Salesforce page afterward (PlaywrightStudentDataProvider,
PlaywrightNoteWriter) opens its own hidden browser loaded with it.

Nothing is ever written to disk (developer's explicit call, 2026-10-22):
when the app closes, the session is gone, and the next launch asks to log
in again. An earlier version saved the session to a file for reuse across
launches; that file was as good as being logged in for anyone who copied
it, and it also meant a fresh app launch never asked to log in.
"""
from typing import Optional
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Playwright, TimeoutError as PlaywrightTimeoutError

from src.services.browser_launch import launch_browser

LOGIN_TIMEOUT_MS = 5 * 60 * 1000

NOT_LOGGED_IN_MESSAGE = 'Not logged in to Salesforce. Click "Refresh Caseload" to log in.'
EXPIRED_MESSAGE = 'Your Salesforce login has expired. Click "Refresh Caseload" to log in again.'

# Playwright storage_state as a dict - cookies for this app session only.
_session_state: Optional[dict] = None


class NotLoggedInError(RuntimeError):
    pass


class SessionExpiredError(RuntimeError):
    pass


def has_session() -> bool:
    return _session_state is not None


def clear_session() -> None:
    global _session_state
    _session_state = None


def set_session_state(state: Optional[dict]) -> None:
    """Mainly for tests - normal code logs in via log_in_interactively()."""
    global _session_state
    _session_state = state


def looks_like_a_different_host(original_url: str, landed_url: str) -> bool:
    """True when navigating to `original_url` ended up on a different host -
    an expired/missing login gets redirected to WGU's SSO sign-in page."""
    return urlparse(landed_url).netloc != urlparse(original_url).netloc


def log_in_interactively(
    playwright: Playwright, target_url: str, logged_in_selector: str, headless: bool = False,
) -> None:
    """Opens a visible browser at `target_url` and waits (up to 5 minutes)
    for the professor to log in. "Logged in" means `logged_in_selector` -
    an element that only exists on the real, authenticated target page
    (the Caseload page's Download button) - has appeared, so a redirect hop
    partway through SSO/MFA can't be mistaken for success. Raises
    RuntimeError if the window is closed first or time runs out.
    `headless` exists only so tests don't pop up a window."""
    global _session_state
    browser = launch_browser(playwright, headless=headless)
    try:
        page = browser.new_context().new_page()
        page.goto(target_url)
        page.wait_for_selector(logged_in_selector, state="visible", timeout=LOGIN_TIMEOUT_MS)
        _session_state = page.context.storage_state()  # a dict, kept in memory only
    except PlaywrightTimeoutError:
        raise RuntimeError("Salesforce login wasn't finished within 5 minutes.") from None
    except PlaywrightError:
        raise RuntimeError("The Salesforce login window was closed before login finished.") from None
    finally:
        try:
            browser.close()
        except PlaywrightError:
            pass  # already closed by the professor


def open_authenticated_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """A new browser context loaded with this app session's login. Raises
    NotLoggedInError if nobody has logged in yet."""
    if _session_state is None:
        raise NotLoggedInError(NOT_LOGGED_IN_MESSAGE)
    browser = launch_browser(playwright, headless=headless)
    return browser.new_context(storage_state=_session_state)
