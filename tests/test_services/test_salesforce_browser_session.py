import json

import pytest
from playwright.sync_api import sync_playwright

from src.services import salesforce_browser_session as sbs


@pytest.fixture
def isolated_storage_path(tmp_path, monkeypatch):
    path = tmp_path / ".salesforce_session.json"
    monkeypatch.setattr(sbs, "STORAGE_STATE_PATH", path)
    return path


def test_has_saved_session_is_false_when_no_file_exists(isolated_storage_path):
    assert sbs.has_saved_session() is False


def test_has_saved_session_is_true_once_a_file_exists(isolated_storage_path):
    isolated_storage_path.write_text("{}", encoding="utf-8")
    assert sbs.has_saved_session() is True


def test_open_authenticated_context_raises_a_clear_error_when_no_session_saved(isolated_storage_path):
    with sync_playwright() as playwright:
        with pytest.raises(RuntimeError, match="salesforce_login.py"):
            sbs.open_authenticated_context(playwright)


def test_open_authenticated_context_loads_a_saved_session(isolated_storage_path):
    isolated_storage_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    with sync_playwright() as playwright:
        context = sbs.open_authenticated_context(playwright, headless=True)
        try:
            assert context is not None
            page = context.new_page()
            page.goto("about:blank")
        finally:
            context.browser.close()
