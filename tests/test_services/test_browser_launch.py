from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error as PlaywrightError

from src.services import app_paths
from src.services.browser_launch import (
    BROWSER_CHANNEL, acquire_playwright, launch_browser, launch_login_context, playwright_session, release_playwright,
)


def test_launches_the_installed_edge():
    playwright = MagicMock()
    launch_browser(playwright, headless=False)
    playwright.chromium.launch.assert_called_once_with(channel=BROWSER_CHANNEL, headless=False)
    assert BROWSER_CHANNEL == "msedge"


def test_missing_edge_gives_a_plain_message():
    playwright = MagicMock()
    playwright.chromium.launch.side_effect = PlaywrightError("Chromium distribution 'msedge' is not found")
    with pytest.raises(RuntimeError, match="Microsoft Edge couldn't be started"):
        launch_browser(playwright)


def test_other_browser_errors_pass_through_unchanged():
    playwright = MagicMock()
    playwright.chromium.launch.side_effect = PlaywrightError("Target page, context or browser has been closed")
    with pytest.raises(PlaywrightError, match="has been closed"):
        launch_browser(playwright)


def test_login_window_uses_the_apps_saved_edge_profile():
    """A blank profile on every login made PingID treat each launch as a new
    device (found live 2026-10-28)."""
    playwright = MagicMock()
    launch_login_context(playwright)
    playwright.chromium.launch_persistent_context.assert_called_once_with(
        str(app_paths.browser_profile_dir()), channel=BROWSER_CHANNEL, headless=False,
        chromium_sandbox=True,  # no "unsupported command-line flag: --no-sandbox" warning bar
    )
    assert app_paths.browser_profile_dir().parent == app_paths.data_dir()


def test_second_login_window_at_once_gives_a_plain_message():
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context.side_effect = PlaywrightError(
        "Failed to create a ProcessSingleton for your profile directory"
    )
    with pytest.raises(RuntimeError, match="Another login window from this app is already open"):
        launch_login_context(playwright)


def test_login_window_with_missing_edge_gives_a_plain_message():
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context.side_effect = PlaywrightError("Chromium distribution 'msedge' is not found")
    with pytest.raises(RuntimeError, match="Microsoft Edge couldn't be started"):
        launch_login_context(playwright)


def test_profile_held_by_another_edge_is_not_reported_as_edge_missing():
    """Real error seen 2026-10-28 when the profile was still open elsewhere:
    the browser log appended to it names msedge.exe."""
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context.side_effect = PlaywrightError(
        "BrowserType.launch_persistent_context: Target page, context or browser has been closed\n"
        "Browser logs:\n<launching> C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe --headless"
    )
    with pytest.raises(RuntimeError, match="Another login window from this app is already open"):
        launch_login_context(playwright)


def test_two_users_on_one_thread_share_a_real_playwright_connection():
    # What failed live: Mongoose held a connection when the note step wanted one.
    first = acquire_playwright()
    try:
        with playwright_session() as second:
            assert second is first
    finally:
        release_playwright()


def test_the_last_user_stops_the_connection(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr("src.services.browser_launch.sync_playwright", lambda: fake)

    acquire_playwright()
    acquire_playwright()
    release_playwright()
    fake.start.return_value.stop.assert_not_called()
    release_playwright()
    fake.start.return_value.stop.assert_called_once()
