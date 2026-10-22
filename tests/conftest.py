# tests/conftest.py
"""Project-wide test safeguards (pytest loads this automatically)."""
import pytest

from src.services import salesforce_browser_session


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
