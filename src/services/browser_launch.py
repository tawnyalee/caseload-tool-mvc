# src/services/browser_launch.py
"""Every browser the app drives (Salesforce login/roster/notes, Mongoose)
starts here, so which browser is used is decided in one place.

Microsoft Edge - the copy already installed on every Windows machine -
rather than Playwright's own downloaded Chromium (developer's call,
2026-10-22, for packaging): the .exe stays small, there's no separate
browser download for IT to block, and Edge updates itself with Windows.
Edge is built on Chromium, so the automation is the same.

Login windows use the app's own saved Edge profile (developer's call,
2026-10-28): with a blank profile every time, PingID treated each login as
a brand-new device. The profile keeps what any browser keeps - the
"seen this device before" record and sign-in cookies - but never the
password, unless the professor chooses to let Edge save it, same as their
own browser. The app itself still never sees or stores credentials.
"""
import threading
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Error as PlaywrightError, Playwright, sync_playwright

from src.services import app_paths

BROWSER_CHANNEL = "msedge"

_this_thread = threading.local()


def acquire_playwright() -> Playwright:
    """The one Playwright connection for this thread. Playwright's sync API
    allows only one at a time per thread, and an email-and-text run needs
    Mongoose and the notes browser open together, so everything shares it
    (found live 2026-10-31: every note in such a run failed). Pair each call
    with release_playwright(); the last release stops it."""
    if getattr(_this_thread, "users", 0) == 0:
        _this_thread.playwright = sync_playwright().start()
        _this_thread.users = 0
    _this_thread.users += 1
    return _this_thread.playwright


def release_playwright() -> None:
    _this_thread.users -= 1
    if _this_thread.users == 0:
        _this_thread.playwright.stop()
        _this_thread.playwright = None


@contextmanager
def playwright_session() -> Iterator[Playwright]:
    playwright = acquire_playwright()
    try:
        yield playwright
    finally:
        release_playwright()

PROFILE_IN_USE_MESSAGE = (
    "Another login window from this app is already open. "
    "Finish or close that one, then try again."
)

EDGE_MISSING_MESSAGE = (
    "Microsoft Edge couldn't be started - this app uses Edge for Salesforce and Mongoose. "
    "Make sure Edge is installed and up to date."
)


def launch_browser(playwright: Playwright, headless: bool = True) -> Browser:
    try:
        return playwright.chromium.launch(channel=BROWSER_CHANNEL, headless=headless)
    except PlaywrightError as exc:
        _raise_plain_error_if_edge_missing(exc)
        raise


def launch_login_context(playwright: Playwright, headless: bool = False) -> BrowserContext:
    """A browser window on the app's saved Edge profile, for logging in.
    Close it with context.close(). Only one can be open at a time, since
    Edge locks a profile folder while it's in use."""
    try:
        # chromium_sandbox: Playwright turns Edge's sandbox off by default
        # (--no-sandbox), and a visible Edge then shows an "unsupported
        # command-line flag" warning bar (seen live 2026-10-28).
        return playwright.chromium.launch_persistent_context(
            str(app_paths.browser_profile_dir()), channel=BROWSER_CHANNEL, headless=headless,
            chromium_sandbox=True,
        )
    except PlaywrightError as exc:
        _raise_plain_error_if_edge_missing(exc)
        # Edge doesn't say "in use" here: when another Edge holds the profile,
        # the new one hands off to it and exits, so Playwright just sees the
        # browser close during launch.
        message = str(exc).lower()
        if "already in use" in message or "processsingleton" in message or "has been closed" in message:
            raise RuntimeError(PROFILE_IN_USE_MESSAGE) from None
        raise


class LoginWindow:
    """The app's one visible Edge window, shared by the Salesforce login and
    Mongoose as tabs (developer, 2026-11-18): right after the Salesforce
    login, the Mongoose tab opens in front in the same window, so the
    professor logs in to both at once. One window also means a later
    Salesforce login never has to close Mongoose: Edge allows only one
    window on the saved profile at a time.

    A tab is opened with new_tab() and given back with close_tab(); the
    window closes with its last tab. Background thread only, like every
    Playwright call in the app."""

    def __init__(self):
        self._context = None
        self._holds_playwright = False
        self._closed = False

    @property
    def is_open(self) -> bool:
        return self._context is not None and not self._closed

    def new_tab(self, playwright: Playwright, headless: bool = False):
        """A new tab, brought to the front, opening the window first if it
        isn't open. While open, the window keeps this thread's shared
        Playwright connection running (acquire_playwright)."""
        if not self.is_open:
            self.close()  # whatever is left of a window the professor closed
            if playwright is getattr(_this_thread, "playwright", None):
                acquire_playwright()
                self._holds_playwright = True
            try:
                self._context = launch_login_context(playwright, headless=headless)
            except Exception:
                self.close()
                raise
            self._closed = False
            self._context.on("close", lambda _context: setattr(self, "_closed", True))
            blank = [p for p in self._context.pages if p.url in ("", "about:blank")]
            page = blank[0] if blank else self._context.new_page()
        else:
            page = self._context.new_page()
        page.bring_to_front()
        return page

    def close_tab(self, page) -> None:
        """Closes one tab, and the window if it was the last one. Never raises."""
        try:
            page.close()
        except Exception:
            pass
        try:
            if self.is_open and not self._context.pages:
                self.close()
        except Exception:
            self.close()

    def close(self) -> None:
        """Closes the window. Never raises."""
        if self._context is not None and not self._closed:
            try:
                self._context.close()
            except Exception:
                pass
        if self._holds_playwright:
            try:
                release_playwright()
            except Exception:
                pass
        self._context = None
        self._holds_playwright = False
        self._closed = False


_login_window = LoginWindow()


def login_window() -> LoginWindow:
    return _login_window


def clear_cached_pages(context: BrowserContext, url: str, keep_local_storage: bool = False) -> None:
    """Drops `url`'s site's cached pages and site storage from the saved
    profile, keeping only its cookies. The login waits on the Caseload page,
    so without this the roster could sit in Edge's cache on disk - and no
    student data may outlive an app session (FERPA, developer's rule).
    `keep_local_storage` is for a site that keeps its sign-in there, as
    Mongoose appears to: clearing it signed the professor out every run."""
    if not context.pages:
        return
    parts = urlparse(url)
    cdp = context.new_cdp_session(context.pages[0])
    try:
        cdp.send("Network.clearBrowserCache")
        if parts.scheme in ("http", "https"):
            cdp.send("Storage.clearDataForOrigin", {
                "origin": f"{parts.scheme}://{parts.netloc}",
                "storageTypes": (
                    "file_systems,indexeddb,cache_storage,service_workers,websql,shader_cache"
                    + ("" if keep_local_storage else ",local_storage")
                ),
            })
    finally:
        cdp.detach()


def _raise_plain_error_if_edge_missing(exc: PlaywrightError) -> None:
    # Only the first line: a failed launch appends Edge's own command line
    # (which names msedge.exe) to every error, so matching "msedge" anywhere
    # called a locked profile "Edge missing" (seen live 2026-10-28).
    first_line = str(exc).lower().splitlines()[0] if str(exc) else ""
    if "is not found" in first_line or "executable doesn't exist" in first_line:
        raise RuntimeError(EDGE_MISSING_MESSAGE) from None
