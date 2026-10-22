# src/services/browser_launch.py
"""Every browser the app drives (Salesforce login/roster/notes, Mongoose)
starts here, so which browser is used is decided in one place.

Microsoft Edge - the copy already installed on every Windows machine -
rather than Playwright's own downloaded Chromium (developer's call,
2026-10-22, for packaging): the .exe stays small, there's no separate
browser download for IT to block, and Edge updates itself with Windows.
Edge is built on Chromium, so the automation is the same.
"""
from playwright.sync_api import Browser, Error as PlaywrightError, Playwright

BROWSER_CHANNEL = "msedge"

EDGE_MISSING_MESSAGE = (
    "Microsoft Edge couldn't be started - this app uses Edge for Salesforce and Mongoose. "
    "Make sure Edge is installed and up to date."
)


def launch_browser(playwright: Playwright, headless: bool = True) -> Browser:
    try:
        return playwright.chromium.launch(channel=BROWSER_CHANNEL, headless=headless)
    except PlaywrightError as exc:
        if "msedge" in str(exc).lower() or "executable doesn't exist" in str(exc).lower():
            raise RuntimeError(EDGE_MISSING_MESSAGE) from None
        raise
