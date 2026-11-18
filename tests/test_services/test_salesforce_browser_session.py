import pytest
from playwright.sync_api import sync_playwright

from src.services import app_paths
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

    with sync_playwright() as playwright:
        sbs.log_in_interactively(playwright, url, '[title="Download"]', headless=True)

    assert sbs.has_session()
    assert isinstance(sbs._session_state, dict)


def test_login_keeps_the_browser_profile_so_the_device_is_recognized_next_time(tmp_path):
    """The profile folder outlives the login (that's what lets PingID
    recognize the device); the session itself still lives only in memory."""
    url = _page(tmp_path, '<button title="Download">Download</button>')

    with sync_playwright() as playwright:
        sbs.log_in_interactively(playwright, url, '[title="Download"]', headless=True)
        sbs.clear_session()
        sbs.log_in_interactively(playwright, url, '[title="Download"]', headless=True)  # profile reopens fine

    assert any(app_paths.browser_profile_dir().iterdir())
    assert sbs.has_session()


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


# --- One shared login window (developer, 2026-11-18) ---

from src.services.browser_launch import login_window


def _named_page(tmp_path, name, body):
    path = tmp_path / f"{name}.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return f"file:///{path.as_posix()}"


def test_the_tab_opened_after_login_keeps_the_window_open_once_the_login_tab_closes(tmp_path):
    login_url = _page(tmp_path, '<button title="Download">Download</button>')
    mongoose_url = _named_page(tmp_path, "mongoose", "Mongoose sign-in")
    opened = []

    with sync_playwright() as playwright:
        def open_mongoose():
            page = login_window().new_tab(playwright, headless=True)
            page.goto(mongoose_url)
            opened.append(page)

        sbs.log_in_interactively(playwright, login_url, '[title="Download"]', headless=True, after_login=open_mongoose)

        assert sbs.has_session()
        assert login_window().is_open
        assert [p.url for p in login_window()._context.pages] == [mongoose_url]  # only Mongoose is left

        login_window().close_tab(opened[0])
        assert not login_window().is_open  # the window went with its last tab


def test_a_later_login_opens_beside_an_open_tab_instead_of_needing_it_closed(tmp_path):
    """Edge allows one window on the saved profile: before 2026-11-18 a new
    Salesforce login had to close Mongoose first."""
    login_url = _page(tmp_path, '<button title="Download">Download</button>')

    with sync_playwright() as playwright:
        mongoose = login_window().new_tab(playwright, headless=True)

        sbs.log_in_interactively(playwright, login_url, '[title="Download"]', headless=True)

        assert sbs.has_session()
        assert not mongoose.is_closed()
        login_window().close()


def test_a_failing_after_login_step_doesnt_undo_the_login(tmp_path):
    login_url = _page(tmp_path, '<button title="Download">Download</button>')

    def broken():
        raise RuntimeError("Mongoose couldn't be opened.")

    with sync_playwright() as playwright:
        sbs.log_in_interactively(playwright, login_url, '[title="Download"]', headless=True, after_login=broken)

    assert sbs.has_session()
    assert not login_window().is_open
