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
    monkeypatch.setattr("src.services.browser_launch.sync_playwright", lambda: MagicMock())
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
    opened[0].browser.close.assert_not_called()
    assert writer.write_note_fn.call_count == 3 and writer.update_follow_up_fn.call_count == 3


def test_slow_salesforce_steps_get_two_minutes_not_the_usual_thirty_seconds(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    writer.start_run()
    writer.write_note("S1", "Subject", "Body", "D424")
    writer.finish_run()

    opened[0].set_default_timeout.assert_called_once_with(120_000)


def test_each_new_student_gets_a_freshly_loaded_page(monkeypatch):
    """The live failure: on a reused page, every second note timed out."""
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    writer.start_run()
    for student_id in ("S1", "S2", "S3"):
        writer.write_note(student_id, "Subject", "Body", "D424")
        writer.update_follow_up_note(student_id, "Task 2 Support")
    writer.finish_run()

    assert opened[0].new_page.return_value.goto.call_count == 3


def test_a_follow_up_with_no_note_also_gets_a_fresh_page_for_a_new_student(monkeypatch):
    opened = []
    writer = _shared_writer(monkeypatch, opened)

    writer.start_run()
    writer.update_follow_up_note("S1", "Task 2 Support")
    writer.update_follow_up_note("S2", "Task 2 Support")
    writer.finish_run()

    assert opened[0].new_page.return_value.goto.call_count == 2


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


@pytest.fixture(autouse=True)
def _no_connection_left_for_other_tests():
    """Shared-browser tests leave their stand-in connection open on purpose."""
    from src.services import browser_launch

    yield
    browser_launch._this_thread.users = 0


def _recording_writer(record_page_url, calls):
    return PlaywrightNoteWriter(
        student_record_url_template=record_page_url,
        write_note_fn=lambda page, sid, subject, body, course_code: calls.append(("note", sid)),
        update_follow_up_fn=lambda page, sid, text: calls.append(("follow-up", sid)),
        headless=True,
    )


def test_nothing_from_one_student_is_left_on_the_page_for_the_next(saved_session, record_page_url):
    """With real Edge: anything one student's note leaves on the page is gone
    for the next student, but still there for that student's follow-up."""
    seen = []

    def leave_a_form_behind(page, sid, subject, body, course_code):
        seen.append(("note", sid, page.evaluate("window.leftover || null")))
        page.evaluate(f"window.leftover = '{sid}'")

    def look_for_the_form(page, sid, text):
        seen.append(("follow-up", sid, page.evaluate("window.leftover || null")))

    writer = PlaywrightNoteWriter(
        student_record_url_template=record_page_url,
        write_note_fn=leave_a_form_behind, update_follow_up_fn=look_for_the_form, headless=True,
    )
    try:
        writer.start_run()
        for student_id in ("S1", "S2"):
            writer.write_note(student_id, "Subject", "Body", "D424")
            writer.update_follow_up_note(student_id, "Welcome Email")
        writer.finish_run()
    finally:
        writer.close()

    assert seen == [
        ("note", "S1", None), ("follow-up", "S1", "S1"),
        ("note", "S2", None), ("follow-up", "S2", "S2"),
    ]


def test_notes_really_save_while_another_browser_holds_the_connection(saved_session, record_page_url):
    """The live failure, with real Edge: Mongoose holds Playwright for a whole
    email-and-text run while each student's note is written on the same thread."""
    from src.services.browser_launch import acquire_playwright, launch_browser, release_playwright

    calls = []
    writer = _recording_writer(record_page_url, calls)
    mongoose_stand_in = launch_browser(acquire_playwright(), headless=True)
    try:
        writer.start_run()
        for student_id in ("S1", "S2"):
            writer.write_note(student_id, "Subject", "Body", "D424")
            writer.update_follow_up_note(student_id, "Welcome Email")
        writer.finish_run()
    finally:
        writer.close()
        mongoose_stand_in.close()
        release_playwright()

    assert calls == [("note", "S1"), ("follow-up", "S1"), ("note", "S2"), ("follow-up", "S2")]


def test_mongoose_can_start_while_the_notes_browser_stays_open(saved_session, record_page_url):
    """The other order: notes from an earlier run are still open when a text
    run starts, and later notes still work."""
    from src.services.browser_launch import acquire_playwright, launch_browser, release_playwright

    calls = []
    writer = _recording_writer(record_page_url, calls)
    try:
        writer.start_run()
        writer.write_note("S1", "Subject", "Body", "D424")
        writer.finish_run()

        mongoose_stand_in = launch_browser(acquire_playwright(), headless=True)
        writer.start_run()
        writer.update_follow_up_note("S1", "Welcome Email")
        writer.finish_run()
        mongoose_stand_in.close()
        release_playwright()
    finally:
        writer.close()

    assert calls == [("note", "S1"), ("follow-up", "S1")]
