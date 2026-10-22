# tests/conftest.py
"""Project-wide test safeguards (pytest loads this automatically)."""
import pytest

from src.services import app_paths

from src.services import mongoose_browser_session, salesforce_browser_session


@pytest.fixture(autouse=True)
def _never_open_a_visible_login_window(monkeypatch):
    """A test must never pop a real Salesforce sign-in window on the
    developer's screen - this happened once (2026-10-22) when older tests
    started reaching the new login-at-startup code. Headless calls (the
    login tests' own fake pages) still run for real; a visible one fails
    the test immediately instead."""
    real_login = salesforce_browser_session.log_in_interactively

    def guarded(playwright, target_url, logged_in_selector, headless=False):
        if not headless:
            raise AssertionError(
                "A test tried to open a real, visible Salesforce login window - "
                "patch AppController._log_in_to_salesforce in that test."
            )
        return real_login(playwright, target_url, logged_in_selector, headless=True)

    monkeypatch.setattr(salesforce_browser_session, "log_in_interactively", guarded)


@pytest.fixture(autouse=True)
def _never_open_a_visible_mongoose_login_window(monkeypatch):
    """Same safeguard as above, for the Mongoose login."""
    real_login = mongoose_browser_session.log_in_interactively

    def guarded(playwright, logged_in_selector, target_url=mongoose_browser_session.MONGOOSE_URL, headless=False):
        if not headless:
            raise AssertionError("A test tried to open a real, visible Mongoose login window.")
        return real_login(playwright, logged_in_selector, target_url=target_url, headless=True)

    monkeypatch.setattr(mongoose_browser_session, "log_in_interactively", guarded)


@pytest.fixture(autouse=True)
def _isolated_data_folder(tmp_path, monkeypatch):
    """Every test gets its own empty data folder, so nothing a test saves
    (groups, actions, templates, logs...) ever lands in the real
    app data folder (%LOCALAPPDATA% / CaseloadTool). Before 2026-10-22 tests wrote straight
    into the real data files (a long-standing known quirk)."""
    folder = tmp_path / "caseload_data"
    monkeypatch.setenv(app_paths.DATA_DIR_ENV_VAR, str(folder))
    return folder
