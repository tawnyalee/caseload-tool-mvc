from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error as PlaywrightError

from src.services import app_paths
from src.services.browser_launch import BROWSER_CHANNEL, launch_browser, launch_login_context


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
