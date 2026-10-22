import pytest
from playwright.sync_api import sync_playwright

from src.services import mongoose_browser_session as mbs
from src.services import salesforce_browser_session as sbs


@pytest.fixture(autouse=True)
def no_sessions(monkeypatch):
    """Every test starts logged out of both; monkeypatch restores afterward."""
    monkeypatch.setattr(mbs, "_session_state", None)
    monkeypatch.setattr(sbs, "_session_state", None)


def _page(tmp_path, body):
    path = tmp_path / "page.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return f"file:///{path.as_posix()}"


def test_not_logged_in_until_a_session_exists():
    assert mbs.has_session() is False
    mbs.set_session_state({"cookies": [], "origins": []})
    assert mbs.has_session() is True


def test_clear_session_logs_out():
    mbs.set_session_state({"cookies": [], "origins": []})
    mbs.clear_session()
    assert mbs.has_session() is False


def test_mongoose_and_salesforce_logins_are_separate():
    mbs.set_session_state({"cookies": [], "origins": []})
    assert sbs.has_session() is False


def test_open_authenticated_context_raises_a_clear_error_when_not_logged_in():
    with sync_playwright() as playwright:
        with pytest.raises(mbs.NotLoggedInError, match="Not logged in to Mongoose"):
            mbs.open_authenticated_context(playwright)


def test_open_authenticated_context_uses_the_in_memory_session():
    mbs.set_session_state({"cookies": [], "origins": []})
    with sync_playwright() as playwright:
        context = mbs.open_authenticated_context(playwright, headless=True)
        try:
            context.new_page().goto("about:blank")
        finally:
            context.browser.close()


def test_login_succeeds_once_the_logged_in_element_appears_and_writes_nothing(tmp_path):
    url = _page(tmp_path, '<div id="inbox">Inbox</div>')
    files_before = set(tmp_path.iterdir())

    with sync_playwright() as playwright:
        mbs.log_in_interactively(playwright, "#inbox", target_url=url, headless=True)

    assert mbs.has_session()
    assert set(tmp_path.iterdir()) == files_before


def test_login_that_never_finishes_raises_and_stays_logged_out(tmp_path, monkeypatch):
    monkeypatch.setattr(mbs, "LOGIN_TIMEOUT_MS", 500)
    url = _page(tmp_path, "Mongoose sign-in page")

    with sync_playwright() as playwright:
        with pytest.raises(RuntimeError, match="wasn't finished"):
            mbs.log_in_interactively(playwright, "#inbox", target_url=url, headless=True)

    assert mbs.has_session() is False
