from datetime import date
from unittest.mock import MagicMock

import pytest

from src.models.group import Group
from src.models.student import Student
from src.models.action import Action
from src.models.email_template import EmailTemplate
from src.services.action_runner import ActionRunner, RunControl
from src.services.app_settings_repository import AppSettingsRepository
from src.services.email_sender import FakeEmailSender
from src.services.note_writer import FakeNoteWriter
from src.services.task_emails import (
    batches_for_review, build_task_email, html_to_plain_text, parse_look_back_days, passed_in_look_back,
)
from src.services.task_utils import passed_task_number
from src.services.text_sender import FakeTextSender, TextSkipped

MONDAY = date(2026, 11, 2)


def _student(sid="S1", **fields):
    defaults = dict(
        salesforce_id=sid, first_name="Jane", last_name="Doe", email=f"{sid}@example.test",
        course_code="D424", latest_task_status="Passed", latest_task_date="11/1/2026",
        task_1="2026-10-20 (1)", task_2="2026-11-01 (1)", latest_task_number=2,
    )
    return Student(**{**defaults, **fields})


def _course(**fields):
    defaults = dict(
        name="D424", group_id="G1", is_course=True, course_code="D424", has_tasks=True, task_count=4,
        task_emails={"2": {"template_id": "T3"}},
    )
    return Group(**{**defaults, **fields})


def _template(template_id):
    if template_id != "T3":
        return None
    return EmailTemplate(name="Task 3 email", body="<p>Here are the Task 3 tips.</p>", template_id="T3")


def _runner(students):
    provider = MagicMock()
    provider.get_students.return_value = students
    templates = MagicMock()
    templates.get_by_id.side_effect = _template
    runner = ActionRunner(provider, FakeEmailSender(), FakeTextSender(), FakeNoteWriter(), templates, MagicMock())
    return runner


# --- Which task passed -------------------------------------------------------

def test_a_later_submitted_task_doesnt_count_as_the_passed_one():
    # The real case: passed Task 2 (dated like LatestTaskDate), Task 3 submitted.
    student = _student(task_3="2026-10-25 (0)")
    assert passed_task_number(student) == 2


def test_when_two_tasks_share_the_date_the_evaluated_one_wins():
    assert passed_task_number(_student(task_3="2026-11-01 (0)")) == 2


def test_no_date_match_falls_back_to_the_latest_task_number():
    assert passed_task_number(_student(latest_task_date="", latest_task_number=2)) == 2


def test_nothing_counts_as_passed_unless_the_status_is_passed():
    assert passed_task_number(_student(latest_task_status="Revisions Needed")) is None


# --- Look-back days ----------------------------------------------------------

@pytest.mark.parametrize("text, days", [("", 1), ("  ", 1), ("3", 3), (" 14 ", 14), ("365", 365)])
def test_valid_look_back_days(text, days):
    assert parse_look_back_days(text) == days


@pytest.mark.parametrize("text", ["0", "-1", "2.5", "abc", "3 days", "366", "٣"])
def test_invalid_look_back_days(text):
    assert parse_look_back_days(text) is None


def test_default_is_yesterday_only():
    assert passed_in_look_back(_student(latest_task_date="11/1/2026"), 1, MONDAY)
    assert not passed_in_look_back(_student(latest_task_date="10/31/2026", task_2="2026-10-31 (1)"), 1, MONDAY)


@pytest.mark.parametrize("passed_on, included", [
    ("11/2/2026", False),  # today
    ("11/1/2026", True),  # Sunday
    ("10/30/2026", True),  # Friday
    ("10/29/2026", False),  # Thursday
])
def test_three_on_a_monday_is_friday_through_sunday(passed_on, included):
    assert passed_in_look_back(_student(latest_task_date=passed_on), 3, MONDAY) is included


# --- The email ---------------------------------------------------------------

def test_email_has_the_next_tasks_subject_and_a_greeting_above_the_saved_text():
    email = build_task_email(_student(), _course(), _template)
    assert email.subject == "Task 3 Support"
    assert email.body == "<p>Hello Jane,</p><p>Here are the Task 3 tips.</p>"


def test_next_task_already_submitted_gets_the_congratulations_instead():
    email = build_task_email(_student(task_3="2026-10-25 (0)"), _course(task_emails={}), _template)
    assert email.problem == ""
    assert "Hi Jane, congrats on passing Task 2. I see you submitted the next task." in email.body
    assert "Here are the Task 3 tips" not in email.body


def test_no_email_set_up_is_a_listed_problem():
    assert "No task email set up for D424 Task 2" in build_task_email(_student(), _course(task_emails={}), _template).problem


def test_deleted_template_is_a_listed_problem():
    group = _course(task_emails={"2": {"template_id": "gone"}})
    assert "no longer exists" in build_task_email(_student(), group, _template).problem


def test_passing_the_last_task_has_nothing_next():
    assert build_task_email(_student(), _course(task_count=2), _template) is None


def test_review_batches_split_by_task_and_wording_and_leave_out_problems():
    group = _course()
    same_a = build_task_email(_student("S1"), group, _template)
    same_b = build_task_email(_student("S2"), group, _template)
    congrats = build_task_email(_student("S3", task_3="2026-10-25 (0)"), group, _template)
    stuck = build_task_email(_student("S4"), _course(task_emails={}), _template)

    batches = batches_for_review([same_a, congrats, same_b, stuck])

    assert [[t.student.salesforce_id for t in batch] for batch in batches] == [["S3"], ["S1", "S2"]]
    assert same_a.email_name == "Task 3 email"
    assert same_a.preview() == "Hello Jane,\n\nHere are the Task 3 tips."


def test_html_becomes_readable_note_text():
    assert html_to_plain_text("<p>Hello Jane,</p><p>Tips &amp; tricks<br>Line two</p>") == (
        "Hello Jane,\n\nTips & tricks\nLine two"
    )


# --- The run -----------------------------------------------------------------

def test_a_sent_email_writes_its_text_as_the_note_and_the_same_subject_everywhere():
    runner = _runner([_student()])
    emails = runner.get_task_emails([_course()], 1, MONDAY)

    summary = runner.run_task_emails(emails, "My Signature")

    assert summary.failed == 0 and summary.skipped == 0
    sent = runner.email_sender.sent[0]
    assert sent["subject"] == "Task 3 Support" and sent["signature"] == "My Signature"
    assert runner.note_writer.written[0]["subject"] == "Task 3 Support"
    assert runner.note_writer.written[0]["body"] == "Hello Jane,\n\nHere are the Task 3 tips."
    assert runner.note_writer.written[0]["course_code"] == "D424"
    assert runner.note_writer.follow_up_notes["S1"] == "Task 3 Support"


def test_only_students_in_the_course_and_the_days_are_found():
    runner = _runner([
        _student("S1"), _student("S2", course_code="C769"),
        _student("S3", latest_task_date="10/1/2026", task_2="2026-10-01 (1)"),
        _student("S4", latest_task_status="Task Submitted"),
    ])
    emails = runner.get_task_emails([_course()], 1, MONDAY)
    assert [t.student.salesforce_id for t in emails["G1"]] == ["S1"]


def test_nobody_who_passed_is_left_out_because_of_their_follow_up_note():
    runner = _runner([_student(course_followup_note="task 3 support")])
    assert len(runner.get_task_emails([_course()], 1, MONDAY)["G1"]) == 1


def test_unchecked_students_arent_sent_and_problems_are_listed_as_skipped():
    runner = _runner([_student("S1"), _student("S2"), _student("S3", latest_task_date="11/1/2026", task_2="", task_1="2026-11-01 (1)")])
    emails = runner.get_task_emails([_course()], 1, MONDAY)

    summary = runner.run_task_emails(emails, "Sig", included_ids_by_group_id={"G1": {"S1"}})

    assert [e["to"] for e in runner.email_sender.sent] == ["S1@example.test"]
    assert [r.student.salesforce_id for r in summary.skipped_steps] == ["S3"]


def test_failed_email_skips_the_note():
    runner = _runner([_student()])
    runner.email_sender = FakeEmailSender(fail_for={"S1@example.test"})

    summary = runner.run_task_emails(runner.get_task_emails([_course()], 1, MONDAY), "Sig")

    assert summary.failed == 1 and summary.skipped == 1
    assert runner.note_writer.written == []


def test_stop_leaves_the_rest_not_started():
    runner = _runner([_student("S1"), _student("S2")])
    control = RunControl()
    control.request_stop()

    summary = runner.run_task_emails(runner.get_task_emails([_course()], 1, MONDAY), "Sig", control=control)

    assert runner.email_sender.sent == []
    assert [r.step_type for r in summary.results] == ["stopped", "stopped"]


def test_oa_courses_have_no_row_after_the_last_task_for_now():
    assert _course(task_count=3, has_objective_assessment=True).task_email_rows() == [1, 2]


# --- Default signature -------------------------------------------------------

def test_default_signature_is_blank_until_saved_and_survives_reloading(tmp_path):
    path = tmp_path / "app_settings.json"
    assert AppSettingsRepository(path).default_signature == ""
    AppSettingsRepository(path).save_default_signature("My Signature")
    assert AppSettingsRepository(path).default_signature == "My Signature"


def test_notes_share_one_run_even_when_an_email_run_fails_partway():
    runner = _runner([_student()])
    runner.note_writer = MagicMock(wraps=runner.note_writer)
    runner.note_writer.write_note.side_effect = RuntimeError("Salesforce hiccup")

    summary = runner.run_task_emails(runner.get_task_emails([_course()], 1, MONDAY), "Sig")

    assert summary.failed == 1
    runner.note_writer.start_run.assert_called_once()
    runner.note_writer.finish_run.assert_called_once()


def test_an_email_and_text_action_still_writes_the_note_when_the_text_is_skipped():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    runner.text_sender.send.side_effect = TextSkipped("Nobody by that ID in this department")
    action = Action(
        name="Welcome", is_email=True, is_text=True, template_id="T3", email_subject="Hi", email_signature="Sig",
        text_body="Hello", note_subject="Welcome Email", note_body="Sent", follow_up_note="Welcome Email",
    )

    summary = runner.run(action, group_name="D424")

    assert [(r.step_type, r.outcome) for r in summary.results] == [
        ("email", "success"), ("note", "success"), ("text", "skipped"),
    ]
    assert runner.note_writer.written[0]["subject"] == "Welcome Email"


from src.services.action_runner import RunControl


def _email_note_and_text_action():
    return Action(
        name="Welcome", is_email=True, is_text=True, template_id="T3", email_subject="Hi", email_signature="Sig",
        text_body="Hello", note_subject="Welcome Email", note_body="Sent", follow_up_note="Welcome Email",
    )


def test_the_note_is_saved_before_the_text_is_tried():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    notes_when_texting = []
    runner.text_sender.send.side_effect = lambda *_: notes_when_texting.append(len(runner.note_writer.written)) or "ok"

    runner.run(_email_note_and_text_action(), group_name="D424")

    assert notes_when_texting == [1]


def test_mongoose_failing_to_open_still_sends_the_email_and_writes_the_note():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    runner.text_sender.ensure_ready.side_effect = RuntimeError("Mongoose login wasn't finished")

    summary = runner.run(_email_note_and_text_action(), group_name="D424")

    assert [(r.step_type, r.outcome) for r in summary.results] == [
        ("email", "success"), ("note", "success"), ("text", "skipped"),
    ]
    assert "Mongoose login wasn't finished" in summary.results[2].detail
    runner.text_sender.send.assert_not_called()


def test_mongoose_failing_to_open_lists_a_text_only_run_as_skipped():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    runner.text_sender.ensure_ready.side_effect = RuntimeError("Mongoose login wasn't finished")
    action = Action(name="Reminder", is_text=True, text_body="Hello")

    summary = runner.run(action, group_name="D424")

    assert [(r.step_type, r.outcome) for r in summary.results] == [("text", "skipped")]


def test_mongoose_only_opens_after_every_students_email_and_note():
    runner = _runner([_student(), _student()])
    runner.text_sender = MagicMock()
    notes_when_opened = []
    runner.text_sender.ensure_ready.side_effect = lambda: notes_when_opened.append(len(runner.note_writer.written))

    runner.run(_email_note_and_text_action(), group_name="D424")

    assert notes_when_opened == [2]
    assert runner.text_sender.send.call_count == 2


def test_a_batch_finishes_every_actions_emails_and_notes_before_any_text():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    notes_when_opened = []
    runner.text_sender.ensure_ready.side_effect = lambda: notes_when_opened.append(len(runner.note_writer.written))
    action = _email_note_and_text_action()

    summary = runner.run_batch([(action, "D424"), (action, "D424")])

    assert notes_when_opened == [2]
    runner.text_sender.ensure_ready.assert_called_once()
    assert [r.step_type for r in summary.items[1].summary.results] == ["email", "note", "text"]


def test_stopping_during_the_emails_leaves_the_texts_unsent_and_listed():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    control = RunControl()
    runner.email_sender.send = MagicMock(side_effect=lambda *a, **k: control.request_stop())

    summary = runner.run(_email_note_and_text_action(), group_name="D424", control=control)

    runner.text_sender.send.assert_not_called()
    assert summary.results[-1].step_type == "text" and summary.results[-1].outcome == "skipped"


def test_a_text_over_the_limit_is_skipped_and_never_reaches_mongoose():
    runner = _runner([_student()])
    runner.text_sender = MagicMock()
    action = Action(
        name="Check in", is_text=True, template_id=None, text_body="{{student_name}}" + "x" * 148,
    )

    summary = runner.run(action, group_name="D424")

    runner.text_sender.send.assert_not_called()
    assert summary.results[0].outcome == "skipped"
    assert "152 characters" in summary.results[0].detail


def test_preview_shows_a_welcome_actions_filled_in_email_and_text():
    runner = _runner([])
    action = Action(
        name="D424Welcome", is_email=True, is_text=True, template_id="T3",
        email_subject="Welcome, {{student_name}}", text_body="Hi {{student_name}}",
    )

    preview = runner.preview_for(action, _student())

    assert preview == "Subject: Welcome, Jane\n\nHere are the Task 3 tips.\n\nText: Hi Jane"


def test_direct_saves_are_on_until_turned_off_and_survive_reloading(tmp_path):
    path = str(tmp_path / "app_settings.json")
    settings = AppSettingsRepository(path)
    assert settings.use_direct_saves is True

    settings.save_default_signature("Mine")
    settings.save_use_direct_saves(False)

    reloaded = AppSettingsRepository(path)
    assert reloaded.use_direct_saves is False
    assert reloaded.default_signature == "Mine"


# --- courses whose tasks can be done in any order ------------------------------

def _any_order_course(**fields):
    return _course(sequential_tasks=False, task_count=3, task_emails={"support1": {"template_id": "T3"}}, **fields)


def test_any_order_sends_the_lowest_task_not_yet_submitted():
    student = _student(task_1="", task_2="", task_3="2026-11-01 (1)", latest_task_number=3)

    email = build_task_email(student, _any_order_course(), _template)

    assert email.passed_task == 3
    assert email.subject == "Task 1 Support"
    assert email.body.startswith("<p>Hello Jane,</p>")
    assert email.problem == ""


def test_any_order_counts_any_value_as_submitted():
    student = _student(task_1="2026-10-01 (0)", task_2="", task_3="2026-11-01 (1)", latest_task_number=3)

    email = build_task_email(student, _any_order_course(), _template)

    assert email.subject == "Task 2 Support"
    assert "No task email set up for D424 Task 2 Support" in email.problem


def test_any_order_skips_a_student_who_submitted_every_task():
    student = _student(task_1="2026-10-01 (0)", task_2="2026-11-01 (1)", task_3="2026-10-28 (0)")

    assert build_task_email(student, _any_order_course(), _template) is None


def test_in_order_courses_work_as_before():
    email = build_task_email(_student(), _course(), _template)
    assert email.subject == "Task 3 Support" and email.problem == ""


def test_each_kind_of_course_keeps_its_own_emails():
    course = _course(task_count=3, task_emails={"2": {"template_id": "A"}, "support2": {"template_id": "B"}})
    assert course.task_email_rows() == [1, 2]
    assert course.task_email_for(2)["template_id"] == "A"

    course.sequential_tasks = False

    assert course.task_email_rows() == [1, 2, 3]
    assert course.support_email_for(2)["template_id"] == "B"
    assert course.task_email_for(2) is None
