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


def _make_students():
    return [
        Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test", phone="555-0001"),
        Student(salesforce_id="SF2", first_name="John", last_name="Roe", email="john@example.test", phone="555-0002"),
        Student(salesforce_id="SF3", first_name="Amy", last_name="Lee", email="amy@example.test", phone="555-0003"),
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

    summary = runner.run(action, group_name="Test Group")

    # 3 students x (email + text + note) = 9 successful steps
    assert summary.succeeded == 9
    assert summary.failed == 0
    assert summary.skipped == 0


def test_run_only_processes_students_matching_the_actions_filters(tmp_path):
    students = _make_students()
    runner, template, email_sender, *_ = _make_runner(tmp_path, students)
    action = _make_action(
        template.id, filters=[{"field": "first_name", "operator": "Equals", "value": "Jane"}]
    )

    summary = runner.run(action, group_name="Test Group")

    # Only Jane matches - 1 student x (email + text + note) = 3 successful steps
    assert summary.succeeded == 3
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "jane@example.test"


def test_run_with_no_filters_processes_the_full_roster(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, filters=[])

    summary = runner.run(action, group_name="Test Group")

    assert summary.succeeded == 9  # unchanged - same as no filters at all


def test_one_failed_communication_channel_still_leaves_a_note(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students, text_fail_for={"555-0001"})
    action = _make_action(template.id)

    summary = runner.run(action, group_name="Test Group")

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

    summary = runner.run(action, group_name="Test Group")

    jane_results = [r for r in summary.results if r.student.salesforce_id == "SF1"]
    outcomes = {r.step_type: r.outcome for r in jane_results}
    assert outcomes == {"email": "failed", "text": "failed", "note": "skipped"}

    assert summary.failed == 2
    assert summary.skipped == 1
    assert summary.skipped_steps[0].student.salesforce_id == "SF1"


def test_no_note_content_means_no_note_steps_at_all(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(tmp_path, students)
    action = _make_action(template.id, has_note=False)

    summary = runner.run(action, group_name="Test Group")

    note_steps = [r for r in summary.results if r.step_type == "note"]
    assert note_steps == []
    assert summary.succeeded == 6  # 3 students x (email + text)


def test_a_single_students_failure_does_not_stop_the_run(tmp_path):
    students = _make_students()
    runner, template, *_ = _make_runner(
        tmp_path, students, email_fail_for={"jane@example.test"}, text_fail_for={"555-0001"}
    )
    action = _make_action(template.id)

    summary = runner.run(action, group_name="Test Group")

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

    runner.run(action, group_name="Test Group")

    assert email_sender.sent[0]["to"] == "jane@example.test"
    assert email_sender.sent[0]["subject"] == "Welcome"
    assert email_sender.sent[0]["body"] == "<b>Hi</b>"
    assert text_sender.sent[0]["to"] == "555-0001"
    assert note_writer.written[0]["salesforce_id"] == "SF1"


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

    runner.run(action, group_name="Test Group")

    joined = "\n".join(received)
    assert "Starting run" in joined
    assert "Welcome" in joined  # template name logged
    assert "Run complete" in joined


def test_follow_up_note_is_updated_when_note_step_succeeds(tmp_path):
    students = _make_students()
    runner, template, _, _, note_writer = _make_runner(tmp_path, students[:1])
    action = _make_action(template.id, follow_up_note="Sent welcome email")

    runner.run(action, group_name="Test Group")

    assert note_writer.follow_up_notes == {"SF1": "Sent welcome email"}


def test_follow_up_note_only_action_still_triggers_a_note_step(tmp_path):
    """An action with ONLY follow_up_note set (no note_subject/note_body) should
    still count as having note content and run the note step."""
    students = _make_students()
    runner, template, _, _, note_writer = _make_runner(tmp_path, students[:1])
    action = _make_action(template.id, has_note=False, follow_up_note="Sent welcome email")

    summary = runner.run(action, group_name="Test Group")

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

    summary = runner.run(action, group_name="Test Group")

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
        Group(name="Group A", group_id="G1", welcome_action_id="ACT-A"),
        Group(name="Group B", group_id="G2", welcome_action_id="ACT-B"),
        Group(name="No Welcome Set", group_id="G3", welcome_action_id=None),
        Group(name="Dangling Reference", group_id="G4", welcome_action_id="ACT-MISSING"),
    ]
    actions_by_id = {"ACT-A": action_a, "ACT-B": action_b}

    students = _make_students()
    runner = ActionRunner(
        student_provider=_StaticStudentProvider(students),
        email_sender=FakeEmailSender(),
        text_sender=FakeTextSender(),
        note_writer=FakeNoteWriter(),
        template_repo=template_repo,
        activity_logger=ActivityLogger(log_dir=str(tmp_path / "logs")),
    )

    summary = runner.run_welcome_emails(groups, actions_by_id)

    # 2 groups x 3 students x 1 email step = 6 successful steps; other 2 groups skipped
    assert summary.succeeded == 6
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

    batch_summary = runner.run_batch([(action_a, "Group A"), (action_b, "Group B")])

    assert len(batch_summary.items) == 2
    assert batch_summary.items[0].action_name == "Action A"
    assert batch_summary.items[0].group_name == "Group A"
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

    def flaky_run(action, group_name):
        if action.name == "Broken Action":
            raise RuntimeError("boom")
        return original_run(action, group_name)

    monkeypatch.setattr(runner, "run", flaky_run)

    batch_summary = runner.run_batch([(broken_action, "Group A"), (good_action, "Group B")])

    assert len(batch_summary.items) == 2
    assert batch_summary.items[0].error == "boom"
    assert batch_summary.items[0].summary.succeeded == 0
    assert batch_summary.items[1].error is None
    assert batch_summary.items[1].summary.succeeded == 3


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
