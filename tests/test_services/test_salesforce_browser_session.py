import pytest
from playwright.sync_api import sync_playwright

from src.services import salesforce_browser_session as sbs


@pytest.fixture(autouse=True)
def no_session(monkeypatch):
    """Every test starts logged out; monkeypatch restores the real value after."""
    monkeypatch.setattr(sbs, "_session_state", None)


def _page(tmp_path, body):
    path = tmp_path / "page.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return f"file:///{path.as_posix()}"


def test_not_logged_in_until_a_session_exists():
    assert sbs.has_session() is False
    sbs.set_session_state({"cookies": [], "origins": []})
    assert sbs.has_session() is True


def test_clear_session_logs_out():
    sbs.set_session_state({"cookies": [], "origins": []})
    sbs.clear_session()
    assert sbs.has_session() is False


def test_open_authenticated_context_raises_a_clear_error_when_not_logged_in():
    with sync_playwright() as playwright:
        with pytest.raises(sbs.NotLoggedInError, match='Click "Refresh Caseload" to log in'):
            sbs.open_authenticated_context(playwright)


def test_open_authenticated_context_uses_the_in_memory_session():
    sbs.set_session_state({"cookies": [], "origins": []})
    with sync_playwright() as playwright:
        context = sbs.open_authenticated_context(playwright, headless=True)
        try:
            context.new_page().goto("about:blank")
        finally:
            context.browser.close()


def test_login_succeeds_once_the_logged_in_element_appears_and_keeps_it_in_memory(tmp_path):
    url = _page(tmp_path, '<button title="Download">Download</button>')
    files_before = set(tmp_path.iterdir())

    with sync_playwright() as playwright:
        sbs.log_in_interactively(playwright, url, '[title="Download"]', headless=True)

    assert sbs.has_session()
    assert isinstance(sbs._session_state, dict)
    assert set(tmp_path.iterdir()) == files_before  # nothing written to disk


def test_login_that_never_finishes_raises_and_stays_logged_out(tmp_path, monkeypatch):
    monkeypatch.setattr(sbs, "LOGIN_TIMEOUT_MS", 500)
    url = _page(tmp_path, "WGU sign-in page - no Download button here")

    with sync_playwright() as playwright:
        with pytest.raises(RuntimeError, match="wasn't finished"):
            sbs.log_in_interactively(playwright, url, '[title="Download"]', headless=True)

    assert sbs.has_session() is False


def test_looks_like_a_different_host_true_on_sso_redirect():
    assert sbs.looks_like_a_different_host(
        "https://srm.lightning.force.com/lightning/n/Caseload_App_Page",
        "https://access.wgu.edu/pingfed/idp/SSO.saml2",
    ) is True


def test_looks_like_a_different_host_false_on_same_host():
    assert sbs.looks_like_a_different_host(
        "https://srm.lightning.force.com/lightning/n/Caseload_App_Page",
        "https://srm.lightning.force.com/lightning/n/Caseload_App_Page?x=1",
    ) is False
