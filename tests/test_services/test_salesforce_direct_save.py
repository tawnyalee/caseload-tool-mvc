import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs

import pytest

from src.models.student import Student
from src.services import salesforce_direct_save as direct
from src.services.browser_launch import launch_browser, playwright_session
from src.services.caseload_grid import GridCapture, apply_contact_ids
from src.services.diagnostics import Diagnostics
from src.services.note_writer import PlaywrightNoteWriter

PAGE_URL = "https://caseload.test/lightning/n/Caseload_App_Page"
CONTACT_ID = "003000000000001AAA"
RECORD_ID = "a6d000000000001AAA"


class _Request:
    def __init__(self, url="https://x.test/aura?a=1", method="POST", post_data="aura.token=T&aura.context=C"):
        self.url, self.method, self.post_data = url, method, post_data


def test_credentials_come_from_the_pages_own_aura_requests():
    credentials = direct.AuraCredentials()
    credentials.on_request(_Request(url="https://x.test/other"))
    credentials.on_request(_Request(method="GET"))
    assert not credentials.ready

    credentials.on_request(_Request())

    assert (credentials.token, credentials.context) == ("T", "C")


def test_a_bad_request_never_breaks_the_page():
    request = MagicMock()
    type(request).post_data = property(lambda self: 1 / 0)
    request.method, request.url = "POST", "https://x.test/aura"
    direct.AuraCredentials().on_request(request)


def test_note_text_is_escaped_with_one_paragraph_per_line():
    assert direct.note_body_as_html("a < b\n\nnext") == "<p>a &lt; b</p><p><br></p><p>next</p>"


@pytest.mark.parametrize("body,state", [
    ('while(1);\n{"actions":[{"state":"SUCCESS"}]}', "SUCCESS"),
    ('{"actions":[{"state":"ERROR"}]}', "ERROR"),
    ('{"actions":[{"state":"SUCCESS","returnValue":"cut off', "SUCCESS"),
    ("<html>login</html>", ""),
    ("", ""),
])
def test_only_what_salesforce_said_counts(body, state):
    assert direct.result_state(body) == state


def test_anything_but_success_is_a_failed_save():
    page = MagicMock()
    page.evaluate.return_value = {"status": 200, "body": '{"actions":[{"state":"ERROR"}]}'}
    credentials = direct.AuraCredentials()
    with pytest.raises(direct.DirectSaveFailed, match="state=ERROR"):
        direct.save_follow_up(page, credentials, RECORD_ID, "Welcome Email")


# --- real Edge, against a stand-in Salesforce page ------------------------------

STAND_IN_PAGE = """<html><body>Caseload<script>
fetch('/aura?r=1&other.Page.load=1', {method: 'POST', body: 'aura.token=TOKEN&aura.context=CONTEXT'});
</script></body></html>"""


def test_a_note_really_posts_what_salesforce_expects_from_inside_the_page():
    posts = []

    def stand_in(route):
        request = route.request
        if request.method == "GET":
            route.fulfill(status=200, content_type="text/html", body=STAND_IN_PAGE)
            return
        posts.append((request.url, request.post_data))
        route.fulfill(status=200, content_type="application/json", body='{"actions":[{"state":"SUCCESS"}]}')

    credentials = direct.AuraCredentials()
    with playwright_session() as playwright:
        browser = launch_browser(playwright, headless=True)
        try:
            context = browser.new_context()
            context.on("request", credentials.on_request)
            context.route("https://caseload.test/**", stand_in)
            page = context.new_page()
            page.goto(PAGE_URL)
            page.wait_for_function("() => performance.getEntriesByType('resource').length > 0")
            for _ in range(40):
                if credentials.ready:
                    break
                page.wait_for_timeout(50)

            direct.save_note(page, credentials, CONTACT_ID, "D424", "Welcome Email", "Sent <today>")
            direct.save_follow_up(page, credentials, RECORD_ID, "Welcome Email")
        finally:
            browser.close()

    note_url, note_post = posts[-2]
    fields = parse_qs(note_post)
    action = json.loads(fields["message"][0])["actions"][0]
    assert "saveNoteCmpValues" in note_url
    assert (fields["aura.token"][0], fields["aura.context"][0]) == ("TOKEN", "CONTEXT")
    assert action["descriptor"] == "apex://NotesController/ACTION$saveNoteCmpValues"
    assert action["params"]["contactId"] == CONTACT_ID
    assert action["params"]["courseCode"] == "D424"
    assert action["params"]["noteType"] == "Email to Student"
    assert action["params"]["subject"] == "Welcome Email"
    assert action["params"]["text"] == "<p>Sent &lt;today&gt;</p>"

    follow_up_url, follow_up_post = posts[-1]
    params = json.loads(parse_qs(follow_up_post)["message"][0])["actions"][0]["params"]
    assert "saveCourseFollowupNoteToSF" in follow_up_url
    assert params == {"theStudentAcaCourseId": RECORD_ID, "theCourseFollowupNote": "Welcome Email"}


# --- PlaywrightNoteWriter: direct first, the form if not ------------------------

def _student(course="D424", record=RECORD_ID):
    return Student(
        salesforce_id="S1", first_name="Jane", last_name="Doe", email="j@x.test", course_code=course,
        texting_contact_id=CONTACT_ID, course_record_id=record,
    )


def _writer(monkeypatch, rows, state="SUCCESS"):
    context = MagicMock()
    page = context.new_page.return_value
    page.url = "https://example.test/caseload"
    page.evaluate.return_value = {"status": 200, "body": json.dumps({"actions": [{"state": state}]})}
    monkeypatch.setattr("src.services.note_writer.open_authenticated_context", lambda *_a, **_k: context)
    monkeypatch.setattr("src.services.browser_launch.sync_playwright", lambda: MagicMock())
    logged = []
    writer = PlaywrightNoteWriter(
        student_record_url_template="https://example.test/caseload",
        write_note_fn=MagicMock(), update_follow_up_fn=MagicMock(),
        find_students=lambda _sid: rows, log=logged.append,
    )
    writer._aura.token, writer._aura.context = "T", "C"
    return writer, page, logged


@pytest.fixture(autouse=True)
def _no_connection_left_for_other_tests():
    from src.services import browser_launch

    yield
    browser_launch._this_thread.users = 0


def test_direct_saves_skip_the_form_and_the_reload_for_each_student(monkeypatch):
    writer, page, _ = _writer(monkeypatch, [_student()])

    writer.start_run()
    for student_id in ("S1", "S2"):
        writer.write_note(student_id, "Subject", "Body", "D424")
        writer.update_follow_up_note(student_id, "Welcome Email")
    writer.finish_run()

    writer.write_note_fn.assert_not_called()
    writer.update_follow_up_fn.assert_not_called()
    page.goto.assert_called_once()
    assert page.evaluate.call_count == 4
    assert writer.describe_written("Jane") == "Written for Jane (direct then direct then direct then direct)"


def test_an_unclear_answer_falls_back_to_the_form_and_says_why(monkeypatch):
    writer, page, logged = _writer(monkeypatch, [_student()], state="ERROR")

    writer.start_run()
    writer.write_note("S1", "Subject", "Body", "D424")
    writer.update_follow_up_note("S1", "Welcome Email")
    writer.finish_run()

    writer.write_note_fn.assert_called_once()
    writer.update_follow_up_fn.assert_called_once()
    assert "state=ERROR" in logged[0]
    assert writer.describe_written("Jane") == "Written for Jane (form then form)"


def test_a_student_with_no_contact_id_uses_the_form():
    row = _student()
    row.texting_contact_id = ""
    writer = PlaywrightNoteWriter("https://x.test", MagicMock(), MagicMock(), find_students=lambda _sid: [row])
    writer._run = MagicMock()
    writer.start_run()

    writer.write_note("S1", "Subject", "Body", "D424")

    writer._run.assert_called_once()


def test_the_follow_up_only_uses_the_record_for_the_notes_course():
    writer = PlaywrightNoteWriter(
        "https://x.test", MagicMock(), MagicMock(),
        find_students=lambda _sid: [_student("D424", "a6dONE"), _student("C769", "a6dTWO")],
    )
    writer.start_run()
    assert writer._course_record_id("S1") == ""  # two courses and no note: never guess

    writer._note_course["S1"] = "c769"

    assert writer._course_record_id("S1") == "a6dTWO"


def test_outside_a_run_everything_uses_the_form():
    writer = PlaywrightNoteWriter("https://x.test", MagicMock(), MagicMock(), find_students=lambda _sid: [_student()])
    assert writer._roster_rows("S1") == []


def test_each_student_gets_the_record_id_for_their_own_course():
    grid = GridCapture()
    grid.add_rows([
        {"StudentID": "S1", "CourseCode": "D424", "contactID": CONTACT_ID, "StudentAcademicCourseId": "a6dONE"},
        {"StudentID": "S1", "CourseCode": "C769", "contactID": CONTACT_ID, "StudentAcademicCourseId": "a6dTWO"},
    ])
    students = [_student("D424", ""), _student("C769", ""), _student("D502", "")]

    report = apply_contact_ids(students, grid)

    assert [s.course_record_id for s in students] == ["a6dONE", "a6dTWO", ""]
    assert "Course record IDs found for 2 of 3 students" in report.log_lines()


def test_course_record_ids_are_scrubbed_from_the_diagnostics_log(tmp_path):
    diag = Diagnostics(tmp_path)
    assert diag.scrub("record a6d000000000001AAA") == "record [contact-id]"
