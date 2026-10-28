# src/services/mongoose_browser_session.py
"""Playwright-based browser session management for Mongoose (Cadence),
mirroring salesforce_browser_session.py: login can't be automated (SSO/
MFA), so log_in_interactively() opens a visible browser, the professor
logs in themselves, and the resulting session (cookies) is kept IN MEMORY
for the rest of this app session. The app never saves that session
itself (same rule as Salesforce); the login window uses the app's saved
Edge profile, as Salesforce's does (see browser_launch.py).

This is a COMPLETELY SEPARATE session from Salesforce's - Mongoose is a
different site with its own login.

What proves "logged in" on Mongoose isn't known yet: the caller passes
`logged_in_selector` - an element that only exists once logged in (e.g.
something on the inbox/dashboard). Capture it during the Mongoose
`playwright codegen` recording session, along with the compose/schedule
selectors, rather than guessing now. Nothing calls this yet; the real
Mongoose TextSender will.
"""
from typing import Optional

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Playwright, TimeoutError as PlaywrightTimeoutError

from src.services.browser_launch import clear_cached_pages, launch_browser, launch_login_context

MONGOOSE_URL = "https://sms.mongooseresearch.com"
LOGIN_TIMEOUT_MS = 5 * 60 * 1000

NOT_LOGGED_IN_MESSAGE = "Not logged in to Mongoose - log in again to send texts."

# Playwright storage_state as a dict - cookies for this app session only.
_session_state: Optional[dict] = None


class NotLoggedInError(RuntimeError):
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


def log_in_interactively(
    playwright: Playwright, logged_in_selector: str, target_url: str = MONGOOSE_URL, headless: bool = False,
) -> None:
    """Opens a visible browser at `target_url` and waits (up to 5 minutes)
    for the professor to log in, i.e. for `logged_in_selector` to appear.
    Raises RuntimeError if the window is closed first or time runs out.
    `headless` exists only so tests don't pop up a window."""
    global _session_state
    context = launch_login_context(playwright, headless=headless)
    try:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(target_url)
        page.wait_for_selector(logged_in_selector, state="visible", timeout=LOGIN_TIMEOUT_MS)
        _session_state = context.storage_state()  # a dict, kept in memory only
        clear_cached_pages(context, page.url)
    except PlaywrightTimeoutError:
        raise RuntimeError("Mongoose login wasn't finished within 5 minutes.") from None
    except PlaywrightError:
        raise RuntimeError("The Mongoose login window was closed before login finished.") from None
    finally:
        try:
            context.close()
        except PlaywrightError:
            pass  # already closed by the professor


def open_authenticated_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """A new browser context loaded with this app session's Mongoose login.
    Raises NotLoggedInError if nobody has logged in yet."""
    if _session_state is None:
        raise NotLoggedInError(NOT_LOGGED_IN_MESSAGE)
    browser = launch_browser(playwright, headless=headless)
    return browser.new_context(storage_state=_session_state)
