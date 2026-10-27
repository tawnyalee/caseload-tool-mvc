import pytest

from src.models.action import Action
from src.models.email_template import EmailTemplate
from src.models.group import Group
from src.models.student import Student
from src.services.action_runner import ActionRunner
from src.services.activity_logger import ActivityLogger
from src.services.email_sender import FakeEmailSender
from src.services.note_writer import FakeNoteWriter
from src.services.student_data_provider import StudentDataProvider
from src.services.template_repository import TemplateRepository
from src.services.text_sender import FakeTextSender


class _StaticStudentProvider(StudentDataProvider):
    def __init__(self, students):
        self._students = students

    def get_students(self):
        return self._students


def _make_students(course_code=""):
    return [
        Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test", phone="555-0001", course_code=course_code),
        Student(salesforce_id="SF2", first_name="John", last_name="Roe", email="john@example.test", phone="555-0002", course_code=course_code),
        Student(salesforce_id="SF3", first_name="Amy", last_name="Lee", email="amy@example.test", phone="555-0003", course_code=course_code),
    ]


def _make_runner(tmp_path, students, email_fail_for=None, text_fail_for=None, note_fail_for=None):
    template_repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    template = EmailTemplate(name="Welcome", body="<b>Hi</b>")
    template_repo.save(template)

    email_sender = FakeEmailSender(fail_for=email_fail_for)
    text_sender = FakeTextSender(fail_for=text_fail_for)
    note_writer = FakeNoteWriter(fail_for=note_fail_for)
    activity_logger = ActivityLogger(log_dir=str(tmp_path / "logs"))

    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=email_sender,
        text_sender=text_sender,
        note_writer=note_writer,
        template_repo=template_repo,
        activity_logger=activity_logger,
    )
    return runner, template, email_sender, text_sender, note_writer


def _make_action(template_id, is_email=True, is_text=True, has_note=True, follow_up_note="", filters=None):
    return Action(
        name="Welcome Action",
        group_id="G1",
        is_email=is_email,
        is_text=is_text,
        template_id=template_id,
        email_subject="Welcome",
        email_signature="Sig",
        text_subject="Hi",
        text_body="Welcome text",
        note_subject="Contacted" if has_note else "",
        note_body="Reached out to student" if has_note else "",
        follow_up_note=follow_up_note,
        filters=filters,
    )


def test_all_steps_succeed(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id)

    summary = runner.run(action, group_name="General")

    # 3 students x (email + text + note) = 9 successful steps
    assert summary.succeeded == 9
    assert summary.failed == 0
    assert summary.skipped == 0


def test_email_subject_and_body_render_merge_fields_per_student(tmp_path):
    students = [
        Student(
            salesforce_id="SF1", first_name="Jane", last_name="Doe",
            email="jane@example.test", course_code="D424",
        ),
        Student(
            salesforce_id="SF2", first_name="John", last_name="Roe",
            email="john@example.test", course_code="D370",
        ),
    ]
    template_repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    template = EmailTemplate(name="Welcome", body="Hi {{student_name}}, welcome to {{course_code}}!")
    template_repo.save(template)
    email_sender = FakeEmailSender()
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=email_sender,
        text_sender=FakeTextSender(),
        note_writer=FakeNoteWriter(),
        template_repo=template_repo,
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )
    action = Action(
        name="Welcome Action", group_id="G1", is_email=True,
        template_id=template.id, email_subject="Hi {{student_name}}!",
    )

    runner.run(action, group_name="General")

    sent_by_email = {s["to"]: s for s in email_sender.sent}
    assert sent_by_email["jane@example.test"]["subject"] == "Hi Jane Doe!"
    assert sent_by_email["jane@example.test"]["body"] == "Hi Jane Doe, welcome to D424!"
    assert sent_by_email["john@example.test"]["subject"] == "Hi John Roe!"
    assert sent_by_email["john@example.test"]["body"] == "Hi John Roe, welcome to D370!"


def test_ad_hoc_email_also_renders_merge_fields_per_student(tmp_path):
    students = [
        Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test"),
    ]
    runner, *_ = _make_runner(tmp_path, students)
    email_sender = runner.email_sender

    runner.send_ad_hoc_email(subject="Hi {{student_name}}", body="Hello, {{student_name}}.")

    assert email_sender.sent[0]["subject"] == "Hi Jane Doe"
    assert email_sender.sent[0]["body"] == "Hello, Jane Doe."


def test_run_only_processes_students_matching_the_actions_filters(tmp_path):
    students = _make_students()
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)
    action = _make_action(
        template.id, filters=[{"field": "first_name", "operator": "Equals", "value": "Jane"}]
    )

    summary = runner.run(action, group_name="General")

    # Only Jane matches - 1 student x (email + text + note) = 3 successful steps
    assert summary.succeeded == 3
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "jane@example.test"


def test_run_with_no_filters_processes_the_full_roster(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, filters=[])

    summary = runner.run(action, group_name="General")

    assert summary.succeeded == 9  # unchanged - same as no filters at all


def test_get_matching_students_returns_filtered_students_without_running_anything(tmp_path):
    students = _make_students()
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)
    action = _make_action(
        template.id, filters=[{"field": "first_name", "operator": "Equals", "value": "Jane"}]
    )

    matches = runner.get_matching_students(action)

    assert [s.salesforce_id for s in matches] == ["SF1"]
    assert email_sender.sent == []


def test_included_student_ids_further_restricts_a_run_to_the_selected_subset(tmp_path):
    students = _make_students()
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, is_text=False, has_note=False)

    runner.run(action, group_name="General", included_student_ids={"SF2"})

    assert [s["to"] for s in email_sender.sent] == ["john@example.test"]


def test_included_student_ids_none_means_everyone_filter_matched_still_runs(tmp_path):
    students = _make_students()
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, is_text=False, has_note=False)

    runner.run(action, group_name="General", included_student_ids=None)

    assert len(email_sender.sent) == 3


def test_run_logs_currently_running_count_and_per_student_processing_lines(tmp_path):
    students = _make_students()
    received = []
    activity_logger = ActivityLogger(log_dir=str(tmp_path / "logs"), ui_callback=received.append)
    runner, template, *_ = _make_runner(tmp_path, students)
    runner.activity_logger = activity_logger
    action = _make_action(template.id, is_text=False, has_note=False)

    runner.run(action, group_name="General", included_student_ids={"SF1", "SF3"})

    joined = "\n".join(received)
    assert "'Welcome Action' is currently running for 2 students" in joined
    assert "[PROCESSING] Jane Doe (ID: SF1)" in joined
    assert "[PROCESSING] Amy Lee (ID: SF3)" in joined
    assert "[PROCESSING] John Roe (ID: SF2)" not in joined


def test_email_subject_and_body_overrides_replace_the_actions_own_content(tmp_path):
    students = [Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test")]
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, is_text=False, has_note=False)  # action.email_subject == "Welcome"

    runner.run(
        action, group_name="General",
        email_subject_override="Overridden Subject {{student_name}}",
        email_body_override="Overridden body.",
    )

    assert email_sender.sent[0]["subject"] == "Overridden Subject Jane Doe"
    assert email_sender.sent[0]["body"] == "Overridden body."


def test_no_override_falls_back_to_the_actions_own_subject_and_template_body(tmp_path):
    students = [Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test")]
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)  # template.body == "<b>Hi</b>"
    action = _make_action(template.id, is_text=False, has_note=False)  # action.email_subject == "Welcome"

    runner.run(action, group_name="General")

    assert email_sender.sent[0]["subject"] == "Welcome"
    assert email_sender.sent[0]["body"] == "<b>Hi</b>"


def test_send_ad_hoc_email_included_student_ids_restricts_who_is_emailed(tmp_path):
    students = _make_students()
    runner, *_ = _make_runner(tmp_path, students)
    email_sender = runner.email_sender

    runner.send_ad_hoc_email(subject="Hi", body="Hello", included_student_ids={"SF3"})

    assert [s["to"] for s in email_sender.sent] == ["amy@example.test"]


def test_one_failed_communication_channel_still_leaves_a_note(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students, text_fail_for={"555-0001"})
    action = _make_action(template.id)

    summary = runner.run(action, group_name="General")

    # Jane: email succeeds, text fails, note still attempted (and succeeds)
    jane_results = [r for r in summary.results if r.student.salesforce_id == "SF1"]
    outcomes = {r.step_type: r.outcome for r in jane_results}
    assert outcomes == {"email": "success", "text": "failed", "note": "success"}

    assert summary.failed == 1
    assert summary.skipped == 0


def test_both_communication_channels_failing_skips_the_note(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(
        tmp_path, students, email_fail_for={"jane@example.test"}, text_fail_for={"555-0001"}
    )
    action = _make_action(template.id)

    summary = runner.run(action, group_name="General")

    jane_results = [r for r in summary.results if r.student.salesforce_id == "SF1"]
    outcomes = {r.step_type: r.outcome for r in jane_results}
    assert outcomes == {"email": "failed", "text": "failed", "note": "skipped"}

    assert summary.failed == 2
    assert summary.skipped == 1
    assert summary.skipped_steps[0].student.salesforce_id == "SF1"


def test_text_success_alone_does_not_write_a_note(tmp_path):
    # Mongoose notes texts itself, so only a successful email earns a note.
    students = _make_students()
    runner, template, _, _, note_writer = _make_runner(tmp_path, students, email_fail_for={"jane@example.test"})
    action = _make_action(template.id)

    summary = runner.run(action, group_name="General")

    jane_results = [r for r in summary.results if r.student.salesforce_id == "SF1"]
    outcomes = {r.step_type: r.outcome for r in jane_results}
    assert outcomes == {"email": "failed", "text": "success", "note": "skipped"}
    assert "SF1" not in [n["salesforce_id"] for n in note_writer.written]


def test_text_only_action_has_no_note_steps_at_all(tmp_path):
    students = _make_students()
    runner, template, _, _, note_writer = _make_runner(tmp_path, students)
    action = _make_action(template.id, is_email=False, is_text=True, follow_up_note="Texted")

    summary = runner.run(action, group_name="General")

    assert [r.step_type for r in summary.results] == ["text", "text", "text"]
    assert summary.skipped == 0
    assert note_writer.written == []
    assert note_writer.follow_up_notes == {}


def test_no_note_content_means_no_note_steps_at_all(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, has_note=False)

    summary = runner.run(action, group_name="General")

    note_steps = [r for r in summary.results if r.step_type == "note"]
    assert note_steps == []
    assert summary.succeeded == 6  # 3 students x (email + text)


def test_a_single_students_failure_does_not_stop_the_run(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(
        tmp_path, students, email_fail_for={"jane@example.test"}, text_fail_for={"555-0001"}
    )
    action = _make_action(template.id)

    summary = runner.run(action, group_name="General")

    # Jane fails everything and her note gets skipped, but John and Amy still fully succeed
    john_results = [r for r in summary.results if r.student.salesforce_id == "SF2"]
    amy_results = [r for r in summary.results if r.student.salesforce_id == "SF3"]
    assert all(r.outcome == "success" for r in john_results)
    assert all(r.outcome == "success" for r in amy_results)
    assert len(john_results) == 3
    assert len(amy_results) == 3


def test_fake_senders_actually_receive_the_configured_content(tmp_path):
    students = _make_students()
    runner, template, email_sender, text_sender, note_writer = _make_runner(tmp_path, students[:1])
    action = _make_action(template.id)

    runner.run(action, group_name="General")

    assert email_sender.sent[0]["to"] == "jane@example.test"
    assert email_sender.sent[0]["subject"] == "Welcome"
    assert email_sender.sent[0]["body"] == "<b>Hi</b>"
    assert text_sender.sent[0]["to"] == "555-0001"
    assert note_writer.written[0]["salesforce_id"] == "SF1"


def test_note_record_uses_group_name_as_course_code_for_a_real_course_group(tmp_path):
    students = _make_students(course_code="D424")
    received = []
    activity_logger = ActivityLogger(log_dir=str(tmp_path / "logs"), ui_callback=received.append)
    runner, template, *_ = _make_runner(tmp_path, students)
    runner.activity_logger = activity_logger
    action = _make_action(template.id)

    runner.run(action, group_name="D424")

    joined = "\n".join(received)
    assert "[NOTE RECORD]" in joined
    assert "course_code='D424'" in joined


def test_note_record_falls_back_to_students_course_code_for_general(tmp_path):
    students = [
        Student(
            salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test",
            course_code="D370",
        )
    ]
    received = []
    activity_logger = ActivityLogger(log_dir=str(tmp_path / "logs"), ui_callback=received.append)
    runner, template, *_ = _make_runner(tmp_path, students)
    runner.activity_logger = activity_logger
    action = _make_action(template.id)

    runner.run(action, group_name="General")

    joined = "\n".join(received)
    assert "course_code='D370'" in joined


def test_note_record_issue_is_logged_for_a_student_with_no_salesforce_id(tmp_path):
    students = [
        Student(salesforce_id="", first_name="Jane", last_name="Doe", email="jane@example.test", course_code="D424"),
    ]
    received = []
    activity_logger = ActivityLogger(log_dir=str(tmp_path / "logs"), ui_callback=received.append)
    runner, template, *_ = _make_runner(tmp_path, students)
    runner.activity_logger = activity_logger
    action = _make_action(template.id)

    runner.run(action, group_name="D424")

    joined = "\n".join(received)
    assert "[NOTE RECORD ISSUE]" in joined
    assert "student ID" in joined


def test_run_logs_start_template_and_summary(tmp_path):
    students = _make_students()
    received = []
    template_repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    template = EmailTemplate(name="Welcome", body="<b>Hi</b>")
    template_repo.save(template)

    activity_logger = ActivityLogger(log_dir=str(tmp_path / "logs"), ui_callback=received.append)
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=FakeEmailSender(),
        text_sender=FakeTextSender(),
        note_writer=FakeNoteWriter(),
        template_repo=template_repo,
        activity_logger=activity_logger,
    )
    action = _make_action(template.id)

    runner.run(action, group_name="General")

    joined = "\n".join(received)
    assert "Starting run" in joined
    assert "Welcome" in joined  # template name logged
    assert "Run complete" in joined


def test_follow_up_note_is_updated_when_note_step_succeeds(tmp_path):
    students = _make_students()
    runner, template, _, _, note_writer = _make_runner(tmp_path, students[:1])
    action = _make_action(template.id, follow_up_note="Sent welcome email")

    runner.run(action, group_name="General")

    assert note_writer.follow_up_notes == {"SF1": "Sent welcome email"}


def test_follow_up_note_only_action_still_triggers_a_note_step(tmp_path):
    """An action with ONLY follow_up_note set (no note_subject/note_body) should
    still count as having note content and run the note step."""
    students = _make_students()
    runner, template, _, _, note_writer = _make_runner(tmp_path, students[:1])
    action = _make_action(template.id, has_note=False, follow_up_note="Sent welcome email")

    summary = runner.run(action, group_name="General")

    note_steps = [r for r in summary.results if r.step_type == "note"]
    assert len(note_steps) == 1
    assert note_steps[0].outcome == "success"
    assert note_writer.written == []  # no note_subject/body, so write_note was never called
    assert note_writer.follow_up_notes == {"SF1": "Sent welcome email"}


def test_follow_up_note_failure_fails_the_whole_note_step(tmp_path):
    students = _make_students()
    template_repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    template = EmailTemplate(name="Welcome", body="<b>Hi</b>")
    template_repo.save(template)

    note_writer = FakeNoteWriter(fail_for={"SF1"})
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students[:1]),
        email_sender=FakeEmailSender(),
        text_sender=FakeTextSender(),
        note_writer=note_writer,
        template_repo=template_repo,
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )
    action = _make_action(template.id, follow_up_note="Sent welcome email")

    summary = runner.run(action, group_name="General")

    note_steps = [r for r in summary.results if r.step_type == "note"]
    assert note_steps[0].outcome == "failed"


def test_run_welcome_emails_aggregates_across_groups(tmp_path):
    template_repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    template = EmailTemplate(name="Welcome", body="<b>Hi</b>")
    template_repo.save(template)

    action_a = _make_action(template.id, is_text=False, has_note=False)
    action_a.id = "ACT-A"
    action_b = _make_action(template.id, is_text=False, has_note=False)
    action_b.id = "ACT-B"

    groups = [
        Group(name="D424", group_id="G1", welcome_action_id="ACT-A"),
        Group(name="D425", group_id="G2", welcome_action_id="ACT-B"),
        Group(name="No Welcome Set", group_id="G3", welcome_action_id=None),
        Group(name="Dangling Reference", group_id="G4", welcome_action_id="ACT-MISSING"),
    ]
    actions_by_id = {"ACT-A": action_a, "ACT-B": action_b}

    students = _make_students(course_code="D424")
    students[2].course_code = "D425"  # Jane + John in D424, Amy in D425
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=FakeEmailSender(),
        text_sender=FakeTextSender(),
        note_writer=FakeNoteWriter(),
        template_repo=template_repo,
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    summary = runner.run_welcome_emails(groups, actions_by_id)

    # Each student is emailed once, by their own course's welcome action
    # (D424: Jane + John, D425: Amy); the other 2 groups are skipped.
    assert summary.succeeded == 3
    assert summary.failed == 0
    assert summary.skipped == 0


def test_run_batch_itemizes_results_per_action(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)

    action_a = _make_action(
        template.id, filters=[{"field": "first_name", "operator": "Equals", "value": "Jane"}]
    )
    action_a.name = "Action A"
    action_b = _make_action(
        template.id, filters=[{"field": "first_name", "operator": "Equals", "value": "John"}]
    )
    action_b.name = "Action B"

    batch_summary = runner.run_batch([(action_a, "General"), (action_b, "General")])

    assert len(batch_summary.items) == 2
    assert batch_summary.items[0].action_name == "Action A"
    assert batch_summary.items[0].group_name == "General"
    assert batch_summary.items[0].summary.succeeded == 3  # Jane: email + text + note
    assert batch_summary.items[1].action_name == "Action B"
    assert batch_summary.items[1].summary.succeeded == 3  # John: email + text + note
    assert batch_summary.succeeded == 6  # combined total


def test_run_batch_continues_after_one_action_raises(tmp_path, monkeypatch):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)

    broken_action = _make_action(template.id)
    broken_action.name = "Broken Action"
    good_action = _make_action(
        template.id, filters=[{"field": "first_name", "operator": "Equals", "value": "Jane"}]
    )
    good_action.name = "Good Action"

    original_run = runner.run

    def flaky_run(action, group_name, **kwargs):
        if action.name == "Broken Action":
            raise RuntimeError("boom")
        return original_run(action, group_name, **kwargs)

    monkeypatch.setattr(runner, "run", flaky_run)

    batch_summary = runner.run_batch([(broken_action, "General"), (good_action, "General")])

    assert len(batch_summary.items) == 2
    assert batch_summary.items[0].error == "boom"
    assert batch_summary.items[0].summary.succeeded == 0
    assert batch_summary.items[1].error is None
    assert batch_summary.items[1].summary.succeeded == 3


def test_run_welcome_emails_included_ids_by_group_id_restricts_each_group(tmp_path):
    template_repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    template = EmailTemplate(name="Welcome", body="<b>Hi</b>")
    template_repo.save(template)

    action_a = _make_action(template.id, is_text=False, has_note=False)
    action_a.id = "ACT-A"
    action_b = _make_action(template.id, is_text=False, has_note=False)
    action_b.id = "ACT-B"

    groups = [
        Group(name="D424", group_id="G1", welcome_action_id="ACT-A"),
        Group(name="D424", group_id="G2", welcome_action_id="ACT-B"),
    ]
    actions_by_id = {"ACT-A": action_a, "ACT-B": action_b}

    students = _make_students(course_code="D424")  # SF1 Jane, SF2 John, SF3 Amy
    email_sender = FakeEmailSender()
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=email_sender,
        text_sender=FakeTextSender(),
        note_writer=FakeNoteWriter(),
        template_repo=template_repo,
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    runner.run_welcome_emails(
        groups, actions_by_id,
        included_ids_by_group_id={"G1": {"SF1"}, "G2": set()},
    )

    sent_addresses = {s["to"] for s in email_sender.sent}
    assert sent_addresses == {"jane@example.test"}  # Group B (G2) fully deselected, John/Amy excluded


def test_run_batch_included_ids_by_index_restricts_each_item(tmp_path):
    students = _make_students()  # SF1 Jane, SF2 John, SF3 Amy
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)

    action_one = _make_action(template.id, is_text=False, has_note=False)
    action_one.name = "First"
    action_two = _make_action(template.id, is_text=False, has_note=False)
    action_two.name = "Second"

    runner.run_batch(
        [(action_one, "General"), (action_two, "General")],
        included_ids_by_index={0: {"SF2"}, 1: {"SF1", "SF3"}},
    )

    sent_addresses = [s["to"] for s in email_sender.sent]
    assert sent_addresses == ["john@example.test", "jane@example.test", "amy@example.test"]


def test_run_batch_preserves_given_order(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)

    action_first = _make_action(template.id)
    action_first.name = "First"
    action_second = _make_action(template.id)
    action_second.name = "Second"
    action_third = _make_action(template.id)
    action_third.name = "Third"

    batch_summary = runner.run_batch(
        [(action_third, "G"), (action_first, "G"), (action_second, "G")]
    )

    assert [item.action_name for item in batch_summary.items] == ["Third", "First", "Second"]


def test_run_batch_with_empty_list_returns_empty_summary(tmp_path):
    students = _make_students()
    runner, *_ = _make_runner(tmp_path, students)

    batch_summary = runner.run_batch([])

    assert batch_summary.items == []
    assert batch_summary.succeeded == 0


def test_send_ad_hoc_email_reaches_every_student_and_isolates_failures(tmp_path):
    students = _make_students()
    email_sender = FakeEmailSender(fail_for={"jane@example.test"})
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=email_sender,
        text_sender=FakeTextSender(),
        note_writer=FakeNoteWriter(),
        template_repo=TemplateRepository(file_path=str(tmp_path / "templates.json")),
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    summary = runner.send_ad_hoc_email(subject="Class Canceled", body="<p>No class today.</p>")

    assert summary.succeeded == 2
    assert summary.failed == 1
    assert len(email_sender.sent) == 2
    assert all(e["subject"] == "Class Canceled" for e in email_sender.sent)


def test_send_ad_hoc_email_with_no_note_content_writes_no_notes(tmp_path):
    students = _make_students()
    note_writer = FakeNoteWriter()
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=FakeEmailSender(),
        text_sender=FakeTextSender(),
        note_writer=note_writer,
        template_repo=TemplateRepository(file_path=str(tmp_path / "templates.json")),
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    runner.send_ad_hoc_email(subject="Class Canceled", body="<p>No class today.</p>")

    assert note_writer.written == []
    assert note_writer.follow_up_notes == {}


def test_send_ad_hoc_email_writes_an_identical_note_to_a_regular_actions_note_step(tmp_path):
    students = _make_students()
    note_writer = FakeNoteWriter()
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=FakeEmailSender(),
        text_sender=FakeTextSender(),
        note_writer=note_writer,
        template_repo=TemplateRepository(file_path=str(tmp_path / "templates.json")),
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    summary = runner.send_ad_hoc_email(
        subject="Class Canceled",
        body="<p>No class today.</p>",
        note_subject="Broadcast sent",
        note_body="Notified of class cancellation",
        follow_up_note="Class canceled - see broadcast",
    )

    # 3 students x (email + note) = 6 successful steps
    assert summary.succeeded == 6
    assert len(note_writer.written) == 3
    assert all(n["subject"] == "Broadcast sent" for n in note_writer.written)
    assert all(text == "Class canceled - see broadcast" for text in note_writer.follow_up_notes.values())


def test_send_ad_hoc_email_skips_the_note_for_a_student_whose_email_failed(tmp_path):
    students = _make_students()
    note_writer = FakeNoteWriter()
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=FakeEmailSender(fail_for={"jane@example.test"}),
        text_sender=FakeTextSender(),
        note_writer=note_writer,
        template_repo=TemplateRepository(file_path=str(tmp_path / "templates.json")),
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    summary = runner.send_ad_hoc_email(
        subject="Class Canceled", body="<p>No class today.</p>", note_subject="Broadcast sent",
    )

    assert summary.failed == 1  # Jane's email
    assert summary.skipped == 1  # Jane's note, skipped rather than attempted
    assert len(note_writer.written) == 2  # John and Amy only


# --- RunControl: progress and stopping -----------------------------------

from src.services.action_runner import RunControl


def test_run_reports_progress_before_each_student(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)
    seen = []

    runner.run(_make_action(template.id), group_name="General", control=RunControl(on_progress=lambda *a: seen.append(a)))

    assert seen == [(1, 3, "Jane Doe"), (2, 3, "John Roe"), (3, 3, "Amy Lee")]


def test_stop_finishes_the_current_student_then_marks_the_rest_not_started(tmp_path):
    students = _make_students()
    runner, template, email_sender, _, _ = _make_runner(tmp_path, students)
    control = RunControl()
    # Ask to stop while the first student is being processed.
    control.on_progress = lambda position, total, name: control.request_stop() if position == 1 else None

    summary = runner.run(_make_action(template.id), group_name="General", control=control)

    assert [s["to"] for s in email_sender.sent] == ["jane@example.test"]  # Jane finished
    stopped = [r for r in summary.results if r.step_type == "stopped"]
    assert [r.student.salesforce_id for r in stopped] == ["SF2", "SF3"]
    assert all(r.outcome == "skipped" for r in stopped)


def test_ad_hoc_email_can_be_stopped_too(tmp_path):
    students = _make_students()
    runner, _, email_sender, _, _ = _make_runner(tmp_path, students)
    control = RunControl()
    control.request_stop()  # stopped before anyone

    summary = runner.send_ad_hoc_email("Hi", "<p>x</p>", control=control)

    assert email_sender.sent == []
    assert [r.step_type for r in summary.results] == ["stopped"] * 3


def test_batch_labels_progress_with_the_item_and_stops_across_items(tmp_path):
    students = _make_students(course_code="D424")
    runner, template, email_sender, _, _ = _make_runner(tmp_path, students)
    action = _make_action(template.id, is_text=False, has_note=False)
    seen = []
    control = RunControl()

    def on_progress(position, total, text):
        seen.append(text)
        if text.startswith("D424"):
            control.request_stop()  # during the first item's first student
    control.on_progress = on_progress

    batch = runner.run_batch([(action, "D424"), (action, "D424")], control=control)

    assert seen == ["D424 — Welcome Action (1 of 2): Jane Doe"]
    assert len(email_sender.sent) == 1
    second_item = batch.items[1].summary
    assert [r.step_type for r in second_item.results] == ["stopped"] * 3


# --- ensure_ready: stop before the first student if email can't work -------

class _NotReadyEmailSender(FakeEmailSender):
    def ensure_ready(self):
        raise RuntimeError("Outlook isn't open. Open Outlook, let it finish loading, then try again.")


def _runner_with(tmp_path, email_sender):
    runner, template, *_ = _make_runner(tmp_path, _make_students())
    runner.email_sender = email_sender
    return runner, template


def test_email_run_stops_before_any_student_when_outlook_is_not_open(tmp_path):
    sender = _NotReadyEmailSender()
    runner, template = _runner_with(tmp_path, sender)
    with pytest.raises(RuntimeError, match="Outlook isn't open"):
        runner.run(_make_action(template.id), group_name="General")
    assert sender.sent == []


def test_ad_hoc_email_stops_before_any_student_when_outlook_is_not_open(tmp_path):
    runner, _ = _runner_with(tmp_path, _NotReadyEmailSender())
    with pytest.raises(RuntimeError, match="Outlook isn't open"):
        runner.send_ad_hoc_email("Hi", "<p>x</p>")


def test_text_only_run_does_not_need_outlook(tmp_path):
    runner, template = _runner_with(tmp_path, _NotReadyEmailSender())
    summary = runner.run(_make_action(template.id, is_email=False, is_text=True, has_note=False), group_name="General")
    assert [r.step_type for r in summary.results] == ["text"] * 3


def test_batch_reports_outlook_not_open_per_action_instead_of_crashing(tmp_path):
    runner, template = _runner_with(tmp_path, _NotReadyEmailSender())
    batch = runner.run_batch([(_make_action(template.id), "General")])
    assert "Outlook isn't open" in batch.items[0].error


# --- An action in a course group only reaches that course's students -------

def test_course_group_limits_the_run_to_that_courses_students(tmp_path):
    students = _make_students(course_code="D424")
    students[2].course_code = "E210"  # Amy is in a different course
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)

    runner.run(_make_action(template.id, is_text=False, has_note=False), group_name="D424")

    assert [s["to"] for s in email_sender.sent] == ["jane@example.test", "john@example.test"]


def test_general_group_still_reaches_every_course(tmp_path):
    students = _make_students(course_code="D424")
    students[2].course_code = "E210"
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)

    runner.run(_make_action(template.id, is_text=False, has_note=False), group_name="General")

    assert len(email_sender.sent) == 3


def test_course_match_ignores_case_and_spaces(tmp_path):
    students = _make_students(course_code=" d424 ")
    runner, template, *_ = _make_runner(tmp_path, students)
    assert len(runner.get_matching_students(_make_action(template.id), "D424")) == 3


def test_review_list_uses_the_same_course_rule_as_the_run(tmp_path):
    students = _make_students(course_code="D424")
    students[0].course_code = "C769"
    runner, template, *_ = _make_runner(tmp_path, students)

    matches = runner.get_matching_students(_make_action(template.id), "D424")

    assert [s.salesforce_id for s in matches] == ["SF2", "SF3"]
