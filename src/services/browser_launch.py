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
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Error as PlaywrightError, Playwright

from src.services import app_paths

BROWSER_CHANNEL = "msedge"

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
        if "already in use" in str(exc).lower() or "processsingleton" in str(exc).lower():
            raise RuntimeError(PROFILE_IN_USE_MESSAGE) from None
        raise


def clear_cached_pages(context: BrowserContext, url: str) -> None:
    """Drops `url`'s site's cached pages and site storage from the saved
    profile, keeping only its cookies. The login waits on the Caseload page,
    so without this the roster could sit in Edge's cache on disk - and no
    student data may outlive an app session (FERPA, developer's rule)."""
    if not context.pages:
        return
    parts = urlparse(url)
    cdp = context.new_cdp_session(context.pages[0])
    try:
        cdp.send("Network.clearBrowserCache")
        if parts.scheme in ("http", "https"):
            cdp.send("Storage.clearDataForOrigin", {
                "origin": f"{parts.scheme}://{parts.netloc}",
                "storageTypes": "file_systems,indexeddb,local_storage,cache_storage,service_workers,websql,shader_cache",
            })
    finally:
        cdp.detach()


def _raise_plain_error_if_edge_missing(exc: PlaywrightError) -> None:
    if "msedge" in str(exc).lower() or "executable doesn't exist" in str(exc).lower():
        raise RuntimeError(EDGE_MISSING_MESSAGE) from None
