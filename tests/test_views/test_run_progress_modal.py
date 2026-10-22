import pytest
import customtkinter as ctk

from src.views.run_progress_modal import RunProgressModal


@pytest.fixture(scope="module")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def test_shows_who_is_being_sent_to_and_how_far_along(ctk_root):
    modal = RunProgressModal(ctk_root, "Run", on_stop=lambda: None)
    try:
        modal.update_progress(3, 10, "Jane Doe")
        assert modal.status_label.cget("text") == "Sending to Jane Doe"
        assert modal.count_label.cget("text") == "3 of 10"
        assert modal.progress_bar.get() == pytest.approx(0.2)
    finally:
        modal.close()


def test_stop_button_requests_a_stop_once_and_says_so(ctk_root):
    calls = []
    modal = RunProgressModal(ctk_root, "Run", on_stop=lambda: calls.append("stop"))
    try:
        modal.stop_button.invoke()
        assert calls == ["stop"]
        assert modal.stop_button.cget("state") == "disabled"
        assert "Stopping" in modal.stop_button.cget("text")
    finally:
        modal.close()


def test_closing_the_window_counts_as_stop_and_does_not_close_it(ctk_root):
    calls = []
    modal = RunProgressModal(ctk_root, "Run", on_stop=lambda: calls.append("stop"))
    try:
        modal.request_stop()  # what the window's X calls
        assert calls == ["stop"]
        assert modal.winfo_exists()
    finally:
        modal.close()


def test_refresh_style_window_has_no_stop_button(ctk_root):
    modal = RunProgressModal(ctk_root, "Refreshing", on_stop=None)
    try:
        assert modal.stop_button is None
        modal.request_stop()  # X does nothing; it closes itself when done
        assert modal.winfo_exists()
    finally:
        modal.close()


def test_updates_after_close_are_ignored(ctk_root):
    modal = RunProgressModal(ctk_root, "Run", on_stop=lambda: None)
    modal.close()
    modal.update_progress(1, 2, "late")  # must not raise
    modal.set_status("late")
