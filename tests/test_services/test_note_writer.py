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
    monkeypatch.setattr(sbs, "STORAGE_STATE_PATH", tmp_path / "session.json")
    sbs.STORAGE_STATE_PATH.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")


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


def test_playwright_note_writer_raises_a_clear_error_when_no_session_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(sbs, "STORAGE_STATE_PATH", tmp_path / "session.json")

    writer = PlaywrightNoteWriter(
        student_record_url_template="file:///does-not-matter.html?id={salesforce_id}",
        write_note_fn=lambda page, sid, subject, body, course_code: None,
        update_follow_up_fn=lambda page, sid, text: None,
    )

    with pytest.raises(RuntimeError, match="salesforce_login.py"):
        writer.write_note("SF1", "Subject", "Body")
