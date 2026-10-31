import json

import pytest

from src.services import salesforce_browser_session as sbs
from src.services.note_writer import FakeNoteWriter, PlaywrightNoteWriter


def test_fake_note_writer_records_written_note():
    writer = FakeNoteWriter()
    writer.write_note(salesforce_id="SF1", subject="Follow up", body="Called student", course_code="D424")

    assert len(writer.written) == 1
    assert writer.written[0] == {
        "salesforce_id": "SF1", "subject": "Follow up", "body": "Called student", "course_code": "D424",
    }


def test_fake_note_writer_raises_for_configured_failure():
    writer = FakeNoteWriter(fail_for={"SF2"})

    with pytest.raises(RuntimeError):
        writer.write_note(salesforce_id="SF2", subject="Follow up", body="body")

    assert writer.written == []


def test_fake_note_writer_records_follow_up_note_update():
    writer = FakeNoteWriter()
    writer.update_follow_up_note(salesforce_id="SF1", text="Sent welcome email")

    assert writer.follow_up_notes == {"SF1": "Sent welcome email"}


def test_fake_note_writer_follow_up_note_update_raises_for_configured_failure():
    writer = FakeNoteWriter(fail_for={"SF2"})

    with pytest.raises(RuntimeError):
        writer.update_follow_up_note(salesforce_id="SF2", text="Sent welcome email")

    assert writer.follow_up_notes == {}


def test_fake_note_writer_follow_up_note_overwrites_previous_value():
    writer = FakeNoteWriter()
    writer.update_follow_up_note(salesforce_id="SF1", text="First note")
    writer.update_follow_up_note(salesforce_id="SF1", text="Second note")

    assert writer.follow_up_notes == {"SF1": "Second note"}


@pytest.fixture
def saved_session(tmp_path, monkeypatch):
    monkeypatch.setattr(sbs, "_session_state", {"cookies": [], "origins": []})  # logged in, in memory


@pytest.fixture
def record_page_url(tmp_path):
    html_path = tmp_path / "record.html"
    html_path.write_text("<html><body>Student Record</body></html>", encoding="utf-8")
    return f"file:///{html_path.as_posix()}?id={{salesforce_id}}"


def test_write_note_navigates_to_the_students_record_and_invokes_the_callback(saved_session, record_page_url):
    calls = []

    def write_note_fn(page, salesforce_id, subject, body, course_code):
        calls.append((salesforce_id, subject, body, course_code, page.url))

    writer = PlaywrightNoteWriter(
        student_record_url_template=record_page_url,
        write_note_fn=write_note_fn,
        update_follow_up_fn=lambda page, sid, text: None,
        headless=True,
    )
    writer.write_note("SF1", "Follow up", "Called student", course_code="D424")

    assert len(calls) == 1
    salesforce_id, subject, body, course_code, url = calls[0]
    assert (salesforce_id, subject, body, course_code) == ("SF1", "Follow up", "Called student", "D424")
    assert "id=SF1" in url


def test_update_follow_up_note_navigates_and_invokes_the_callback(saved_session, record_page_url):
    calls = []

    writer = PlaywrightNoteWriter(
        student_record_url_template=record_page_url,
        write_note_fn=lambda page, sid, subject, body, course_code: None,
        update_follow_up_fn=lambda page, sid, text: calls.append((sid, text)),
        headless=True,
    )
    writer.update_follow_up_note("SF2", "Sent welcome email")

    assert calls == [("SF2", "Sent welcome email")]


def test_playwright_note_writer_raises_a_clear_error_when_not_logged_in(tmp_path, monkeypatch):
    monkeypatch.setattr(sbs, "_session_state", None)  # nobody has logged in

    writer = PlaywrightNoteWriter(
        student_record_url_template="file:///does-not-matter.html?id={salesforce_id}",
        write_note_fn=lambda page, sid, subject, body, course_code: None,
        update_follow_up_fn=lambda page, sid, text: None,
    )

    with pytest.raises(RuntimeError, match="Not logged in to Salesforce"):
        writer.write_note("SF1", "Subject", "Body")


def _shared_writer(monkeypatch, opened):
    """A real PlaywrightNoteWriter over stand-in browser objects."""
    from unittest.mock import MagicMock

    def fake_open(_playwright, headless=True):
        context = MagicMock()
        context.new_page.return_value.url = "https://example.test/caseload"
        opened.append(context)
        return context

    monkeypatch.setattr("src.services.note_writer.open_authenticated_context", fake_open)
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: MagicMock())
    return PlaywrightNoteWriter(
        student_record_url_template="https://example.test/caseload",
        write_note_fn=MagicMock(), update_follow_up_fn=MagicMock(),
    )


def test_a_run_shares_one_browser_and_page_across_students(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    writer.start_run()
    for student_id in ("S1", "S2", "S3"):
        writer.write_note(student_id, "Subject", "Body", "D424")
        writer.update_follow_up_note(student_id, "Task 2 Support")
    writer.finish_run()

    assert len(opened) == 1
    opened[0].new_page.return_value.goto.assert_called_once()
    opened[0].browser.close.assert_not_called()
    assert writer.write_note_fn.call_count == 3 and writer.update_follow_up_fn.call_count == 3


def test_the_browser_stays_open_between_runs_and_each_run_reloads_once(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    for run in range(2):
        writer.start_run()
        writer.write_note("S1", "Subject", "Body", "D424")
        writer.update_follow_up_note("S1", "Task 2 Support")
        writer.finish_run()

    assert len(opened) == 1
    assert opened[0].new_page.return_value.goto.call_count == 2


def test_close_ends_the_browser_and_the_next_run_opens_a_new_one(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    writer.start_run()
    writer.write_note("S1", "Subject", "Body", "D424")
    writer.finish_run()
    writer.close()
    opened[0].browser.close.assert_called_once()

    writer.start_run()
    writer.write_note("S2", "Subject", "Body", "D424")
    writer.finish_run()
    assert len(opened) == 2


def test_a_browser_that_died_between_runs_is_replaced(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)
    writer.start_run()
    writer.write_note("S1", "Subject", "Body", "D424")
    writer.finish_run()
    opened[0].new_page.return_value.goto.side_effect = RuntimeError("target closed")

    writer.start_run()
    writer.write_note("S2", "Subject", "Body", "D424")
    writer.finish_run()

    assert len(opened) == 2
    assert writer.write_note_fn.call_count == 2


def test_after_a_failure_the_next_note_starts_on_a_fresh_page(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)
    writer.write_note_fn.side_effect = [RuntimeError("page got stuck"), None]

    writer.start_run()
    with pytest.raises(RuntimeError):
        writer.write_note("S1", "Subject", "Body", "D424")
    writer.write_note("S2", "Subject", "Body", "D424")
    writer.finish_run()

    assert len(opened) == 2
    opened[0].browser.close.assert_called_once()


def test_finish_run_is_safe_when_no_note_was_written(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    writer.start_run()
    writer.finish_run()

    assert opened == []
