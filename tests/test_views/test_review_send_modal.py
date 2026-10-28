import customtkinter as ctk
import pytest

from src.models.student import Student
from src.views.review_send_modal import ReviewSendModal


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def _students():
    return [
        Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test"),
        Student(salesforce_id="SF2", first_name="John", last_name="Roe", email="john@example.test"),
    ]


def test_send_and_cancel_are_anchored_to_the_bottom_of_the_window(ctk_root):
    """Regression test: Cancel/Send used to be packed after a tall
    scrollable list + email compose area inside a fixed-height window,
    which could push them off the visible bottom of the dialog with
    nothing left to actually confirm a send (reported during manual
    testing of 'Run D424Welcome'). They're now packed side="bottom" right
    after the header, before anything else, so they always claim their
    space first regardless of how tall the rest of the content grows or
    whether rendering the email body runs into trouble.

    This checks the pack side directly rather than absolute pixel
    geometry - a withdrawn/offscreen root in a headless test run doesn't
    reliably report real screen geometry, so a pixel-based assertion here
    can't actually distinguish the fixed layout from the original bug."""
    modal = ReviewSendModal(
        master=ctk_root, title="Run 'D424Welcome'", students=_students(), is_email=True,
        initial_subject="Welcome!", initial_body="<p>Hi</p>",
    )

    assert modal.send_button.master.pack_info()["side"] == "bottom"
    assert modal.cancel_button.master.pack_info()["side"] == "bottom"
    # Every other top-level child packed after the button row's frame must
    # stack above it (side="top", the pack default) rather than also
    # competing for bottom space.
    for child in modal.winfo_children():
        if child is not modal.send_button.master:
            assert child.pack_info().get("side", "top") != "bottom"

    modal.destroy()


def test_real_d424welcome_template_content_renders_without_error(ctk_root):
    """The actual template body saved for the D424Welcome action (real
    HTML + merge tokens, pulled from data/templates.json while
    investigating the missing-Send-button report) must not blow up
    html_richtext rendering partway through __init__, which would also
    leave the dialog visible without reaching the rest of its content."""
    real_body = (
        '<b>Trying</b> this<a href="www.aol.com">www.aol.com</a> '
        '<a href="www.wgu.edu">out.</a><br>\n<br>\n{{course_code}}{{student_name}}'
    )
    modal = ReviewSendModal(
        master=ctk_root, title="Run 'D424Welcome'", students=_students(), is_email=True,
        initial_subject="Welcome!", initial_body=real_body,
    )

    assert modal.send_button is not None

    modal.destroy()


def test_zero_students_shows_empty_state_with_a_close_button(ctk_root):
    modal = ReviewSendModal(master=ctk_root, title="Run 'Empty Action'", students=[], is_email=True)

    assert not modal._check_vars
    assert modal.send_button is None

    modal.destroy()


def test_select_all_and_select_none(ctk_root):
    modal = ReviewSendModal(master=ctk_root, title="Run 'X'", students=_students(), is_email=False)

    modal._select_none()
    assert all(var.get() == "off" for var in modal._check_vars.values())

    modal._select_all()
    assert all(var.get() == "on" for var in modal._check_vars.values())

    modal.destroy()


def test_send_with_none_selected_warns_and_does_not_confirm(ctk_root, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "src.views.review_send_modal.messagebox.showwarning",
        lambda title, msg: warnings.append((title, msg)),
    )
    confirmed = []
    modal = ReviewSendModal(
        master=ctk_root, title="Run 'X'", students=_students(), is_email=False,
        on_confirm=lambda ids, subject, body: confirmed.append((ids, subject, body)),
    )
    modal._select_none()

    modal._on_send()

    assert confirmed == []
    assert len(warnings) == 1


def test_send_calls_on_confirm_with_selected_ids_and_edited_email_content(ctk_root):
    confirmed = []
    modal = ReviewSendModal(
        master=ctk_root, title="Run 'X'", students=_students(), is_email=True,
        initial_subject="Original Subject", initial_body="<p>Original</p>",
        on_confirm=lambda ids, subject, body: confirmed.append((ids, subject, body)),
    )
    modal._check_vars["SF2"].set("off")  # deselect John, keep Jane

    modal.subject_entry.delete(0, "end")
    modal.subject_entry.insert(0, "Edited Subject")

    modal._on_send()

    assert len(confirmed) == 1
    selected_ids, subject, body = confirmed[0]
    assert selected_ids == {"SF1"}
    assert subject == "Edited Subject"
    assert "Original" in body


def test_send_closes_the_dialog_before_on_confirm_runs(ctk_root):
    """Regression test (found live 2026-10-28): on_confirm opens the run's
    progress window. CustomTkinter remembers the focused widget (the Send
    button) when a new window opens and re-focuses it 10 ms later; if this
    dialog closed after on_confirm, that widget was gone and the professor
    saw "Something went wrong: bad window path name". Closing first means
    no widget of this dialog can be remembered."""
    still_open_during_confirm = []
    modal = ReviewSendModal(
        master=ctk_root, title="Run 'X'", students=_students(), is_email=False,
        on_confirm=lambda ids, subject, body: still_open_during_confirm.append(bool(modal.winfo_exists())),
    )

    modal._on_send()

    assert still_open_during_confirm == [False]


def test_non_email_dialog_has_no_subject_or_body_fields(ctk_root):
    modal = ReviewSendModal(master=ctk_root, title="Run 'Text Only'", students=_students(), is_email=False)

    assert modal.subject_entry is None
    assert modal.body_text is None

    modal.destroy()
