from unittest.mock import patch

import customtkinter as ctk
import pytest
from src.views.dashboard_view import DashboardView


class MockController:
    def __init__(self):
        self.welcome_clicked = False
        self.batch_runner_opened = False
        self.ad_hoc_calls = []
        self.signature_provider = None

    def handle_send_welcome_emails(self):
        self.welcome_clicked = True

    def handle_open_batch_runner(self):
        self.batch_runner_opened = True

    def handle_send_ad_hoc_email(self, **kwargs):
        self.ad_hoc_calls.append(kwargs)


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def test_dashboard_view_has_all_three_sections(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    assert isinstance(view.btn_send_welcome, ctk.CTkButton)
    assert isinstance(view.btn_send_all, ctk.CTkButton)
    assert isinstance(view.btn_run_batch, ctk.CTkButton)
    # The ad-hoc section is inline on the dashboard now, not a modal.
    assert isinstance(view.adhoc_subject, ctk.CTkEntry)
    assert isinstance(view.adhoc_body_text, ctk.CTkTextbox)
    assert isinstance(view.adhoc_note_subject, ctk.CTkEntry)
    assert isinstance(view.adhoc_note_body, ctk.CTkTextbox)
    assert isinstance(view.adhoc_followup_note, ctk.CTkEntry)


def test_send_welcome_button_calls_controller(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    view.btn_send_welcome.invoke()

    assert controller.welcome_clicked is True


def test_run_batch_button_calls_controller(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    view.btn_run_batch.invoke()

    assert controller.batch_runner_opened is True


@patch("src.views.dashboard_view.messagebox.showwarning")
def test_send_all_with_empty_subject_is_rejected(mock_showwarning, ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)
    view.adhoc_body_text.insert("0.0", "Some message")

    view.btn_send_all.invoke()

    mock_showwarning.assert_called_once()
    assert controller.ad_hoc_calls == []


@patch("src.views.dashboard_view.messagebox.showwarning")
def test_send_all_with_empty_body_is_rejected(mock_showwarning, ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)
    view.adhoc_subject.insert(0, "Class Canceled")

    view.btn_send_all.invoke()

    mock_showwarning.assert_called_once()
    assert controller.ad_hoc_calls == []


@patch("src.views.dashboard_view.messagebox.askokcancel", return_value=False)
def test_send_all_cancelled_at_confirmation_does_not_call_controller(mock_confirm, ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)
    view.adhoc_subject.insert(0, "Class Canceled")
    view.adhoc_body_text.insert("0.0", "No class today.")

    view.btn_send_all.invoke()

    assert mock_confirm.called
    assert controller.ad_hoc_calls == []


@patch("src.views.dashboard_view.messagebox.askokcancel", return_value=True)
def test_send_all_confirmed_calls_controller_with_email_and_note_fields(mock_confirm, ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)
    view.adhoc_subject.insert(0, "Class Canceled")
    view.adhoc_body_text.insert("0.0", "No class today.")
    view.adhoc_note_subject.insert(0, "Broadcast sent")
    view.adhoc_note_body.insert("0.0", "Notified of cancellation")
    view.adhoc_followup_note.insert(0, "Class canceled - see broadcast")

    view.btn_send_all.invoke()

    assert len(controller.ad_hoc_calls) == 1
    call = controller.ad_hoc_calls[0]
    assert call["subject"] == "Class Canceled"
    assert "No class today." in call["body"]
    assert call["note_subject"] == "Broadcast sent"
    assert call["note_body"] == "Notified of cancellation"
    assert call["follow_up_note"] == "Class canceled - see broadcast"


@patch("src.views.dashboard_view.messagebox.askokcancel", return_value=True)
def test_send_all_note_fields_are_optional(mock_confirm, ctk_root):
    """The note section is identical to a regular Action's optional note
    step - a broadcast email should still send with no note filled in."""
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)
    view.adhoc_subject.insert(0, "Class Canceled")
    view.adhoc_body_text.insert("0.0", "No class today.")

    view.btn_send_all.invoke()

    assert len(controller.ad_hoc_calls) == 1
    call = controller.ad_hoc_calls[0]
    assert call["note_subject"] == ""
    assert call["note_body"] == ""
    assert call["follow_up_note"] == ""
