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

The app never saves the session itself (developer's explicit call,
2026-10-22): when the app closes, it's gone, and the next launch opens the
login window again. An earlier version saved the session to a file of its
own for reuse across launches; that file was as good as being logged in
for anyone who copied it, and a fresh app launch never asked to log in.

The login window does use the app's own saved Edge profile (2026-10-28,
see browser_launch.py), the way the professor's everyday Edge would, so
PingID recognizes the device instead of treating every launch as new.
"""
from typing import Callable, Optional
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Playwright, TimeoutError as PlaywrightTimeoutError

from src.services.browser_launch import clear_cached_pages, launch_browser, login_window

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
    after_login: Optional[Callable[[], None]] = None,
) -> None:
    """Opens `target_url` in a tab of the app's login window
    (browser_launch.LoginWindow) and waits (up to 5 minutes) for the
    professor to log in. "Logged in" means `logged_in_selector` - an
    element that only exists on the real, authenticated target page (the
    Caseload page's Download button) - has appeared, so a redirect hop
    partway through SSO/MFA can't be mistaken for success. Raises
    RuntimeError if the tab is closed first or time runs out.

    `after_login` runs once the login succeeds, before this tab closes: the
    app opens the Mongoose tab there, so the window stays up in front
    (developer, 2026-11-18). Its own failure doesn't undo the login.
    `headless` exists only so tests don't pop up a window."""
    global _session_state
    page = login_window().new_tab(playwright, headless=headless)
    try:
        page.goto(target_url)
        page.wait_for_selector(logged_in_selector, state="visible", timeout=LOGIN_TIMEOUT_MS)
        _session_state = page.context.storage_state()  # a dict, kept in memory only
        clear_cached_pages(page.context, page.url)
    except PlaywrightTimeoutError:
        login_window().close_tab(page)
        raise RuntimeError("Salesforce login wasn't finished within 5 minutes.") from None
    except PlaywrightError:
        login_window().close_tab(page)
        raise RuntimeError("The Salesforce login window was closed before login finished.") from None
    if after_login is not None:
        try:
            after_login()
        except Exception:
            pass  # e.g. Mongoose couldn't open; texts will ask for it later
    login_window().close_tab(page)


def open_authenticated_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """A new browser context loaded with this app session's login. Raises
    NotLoggedInError if nobody has logged in yet."""
    if _session_state is None:
        raise NotLoggedInError(NOT_LOGGED_IN_MESSAGE)
    browser = launch_browser(playwright, headless=headless)
    return browser.new_context(storage_state=_session_state)
