from src.models.action import Action
from src.models.email_template import EmailTemplate
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


def _make_action(template_id, is_email=True, is_text=True, has_note=True):
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
