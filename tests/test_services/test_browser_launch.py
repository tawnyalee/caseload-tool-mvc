from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error as PlaywrightError

from src.services.browser_launch import BROWSER_CHANNEL, launch_browser


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
