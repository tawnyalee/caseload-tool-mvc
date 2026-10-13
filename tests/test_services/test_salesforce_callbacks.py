from pathlib import Path

import pytest

from src.services import salesforce_callbacks


class FakePage:
    """Stands in for playwright.sync_api.Page's screenshot() method - real
    Page objects require a running browser, which these unit tests don't
    need for exercising _screenshot_failure's own path/directory logic."""

    def __init__(self, raise_on_screenshot: bool = False):
        self.raise_on_screenshot = raise_on_screenshot
        self.screenshot_calls = []

    def screenshot(self, path, full_page):
        self.screenshot_calls.append((path, full_page))
        if self.raise_on_screenshot:
            raise RuntimeError("simulated: browser/page already closed")


@pytest.fixture
def temp_screenshots_dir(tmp_path: Path, monkeypatch) -> Path:
    screenshots_dir = tmp_path / "logs" / "screenshots"
    monkeypatch.setattr(salesforce_callbacks, "SCREENSHOTS_DIR", screenshots_dir)
    return screenshots_dir


def test_screenshot_failure_creates_dir_and_saves_full_page_screenshot(temp_screenshots_dir: Path):
    page = FakePage()

    out = salesforce_callbacks._screenshot_failure(page, "write_note_SF1")

    assert temp_screenshots_dir.exists()
    assert out.parent == temp_screenshots_dir
    assert "write_note_SF1" in out.name
    assert out.suffix == ".png"
    assert page.screenshot_calls == [(str(out), True)]


def test_screenshot_failure_is_best_effort_if_page_is_already_gone(temp_screenshots_dir: Path):
    page = FakePage(raise_on_screenshot=True)

    # Should not raise even though page.screenshot() itself blows up - a
    # failed diagnostic screenshot must never mask the original failure.
    out = salesforce_callbacks._screenshot_failure(page, "tag")

    assert isinstance(out, Path)


def test_write_note_fn_wraps_failure_with_screenshot_path_and_student_id(temp_screenshots_dir: Path):
    class ExplodingPage(FakePage):
        def locator(self, *args, **kwargs):
            raise RuntimeError("simulated: element not found")

    with pytest.raises(RuntimeError) as excinfo:
        salesforce_callbacks.write_note_fn(ExplodingPage(), "SF1", "Subject", "Body", "D424")

    message = str(excinfo.value)
    assert "SF1" in message
    assert "Screenshot:" in message
    assert "simulated: element not found" in message


def test_update_follow_up_fn_wraps_failure_with_screenshot_path_and_student_id(temp_screenshots_dir: Path):
    class ExplodingPage(FakePage):
        def locator(self, *args, **kwargs):
            raise RuntimeError("simulated: element not found")

    with pytest.raises(RuntimeError) as excinfo:
        salesforce_callbacks.update_follow_up_fn(ExplodingPage(), "SF2", "Sent welcome email")

    message = str(excinfo.value)
    assert "SF2" in message
    assert "Screenshot:" in message
    assert "simulated: element not found" in message
