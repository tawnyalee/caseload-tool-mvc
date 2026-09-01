from src.models.student import Student
from src.services.merge_fields import MERGE_FIELDS, render_merge_fields


def _student(**kwargs) -> Student:
    defaults = {"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", "email": "jane@example.test"}
    defaults.update(kwargs)
    return Student(**defaults)


def test_registry_has_exactly_the_five_supported_fields():
    assert set(MERGE_FIELDS.keys()) == {
        "student_name", "course_code", "last_submitted_task", "last_passed_task", "next_task",
    }
    assert MERGE_FIELDS["student_name"].label == "Student Name"
    assert MERGE_FIELDS["course_code"].label == "Course Code"
    assert MERGE_FIELDS["last_submitted_task"].label == "Last Submitted Task"
    assert MERGE_FIELDS["last_passed_task"].label == "Last Passed Task"
    assert MERGE_FIELDS["next_task"].label == "Next Task"


def test_render_replaces_student_name():
    student = _student(first_name="Jane", last_name="Doe")
    assert render_merge_fields("Hi, {{student_name}}!", student) == "Hi, Jane Doe!"


def test_render_replaces_course_code():
    student = _student(course_code="D424")
    assert render_merge_fields("Regarding {{course_code}}", student) == "Regarding D424"


def test_render_replaces_repeated_occurrences_of_the_same_token():
    student = _student(first_name="Jane", last_name="Doe")
    text = "{{student_name}} {{student_name}}"
    assert render_merge_fields(text, student) == "Jane Doe Jane Doe"


def test_render_leaves_unrecognized_tokens_untouched():
    student = _student()
    text = "Hi {{nickname}}!"
    assert render_merge_fields(text, student) == "Hi {{nickname}}!"


class TestLastSubmittedTask:
    def test_blank_when_nothing_submitted(self):
        student = _student(latest_task_number=None)
        assert render_merge_fields("{{last_submitted_task}}", student) == ""

    def test_reflects_the_highest_submitted_task_regardless_of_status(self):
        student = _student(latest_task_number=5, latest_task_status="Revisions Needed")
        assert render_merge_fields("{{last_submitted_task}}", student) == "Task 5"


class TestLastPassedTask:
    def test_blank_when_nothing_submitted(self):
        student = _student(latest_task_number=None)
        assert render_merge_fields("{{last_passed_task}}", student) == ""

    def test_matches_last_submitted_when_the_latest_status_is_passed(self):
        student = _student(latest_task_number=2, latest_task_status="Passed")
        assert render_merge_fields("{{last_passed_task}}", student) == "Task 2"

    def test_blank_when_the_latest_submission_needs_revisions(self):
        """The last-passed task number isn't recoverable here - there's no
        per-task status history, only the status of whichever task is
        latest (see task_utils). Blank, not a guess."""
        student = _student(latest_task_number=3, latest_task_status="Revisions Needed")
        assert render_merge_fields("{{last_passed_task}}", student) == ""

    def test_blank_when_the_latest_submission_is_still_pending_evaluation(self):
        student = _student(latest_task_number=3, latest_task_status="Evaluation Started")
        assert render_merge_fields("{{last_passed_task}}", student) == ""


class TestNextTask:
    def test_is_task_one_when_nothing_submitted_yet(self):
        student = _student(latest_task_number=None)
        assert render_merge_fields("{{next_task}}", student) == "Task 1"

    def test_is_one_past_the_last_submitted_task(self):
        student = _student(latest_task_number=2)
        assert render_merge_fields("{{next_task}}", student) == "Task 3"

    def test_blank_once_all_fifteen_tasks_are_submitted(self):
        student = _student(latest_task_number=15)
        assert render_merge_fields("{{next_task}}", student) == ""


def test_render_combines_all_three_task_fields_in_one_message():
    student = _student(latest_task_number=2, latest_task_status="Passed")
    text = "Congrats on passing {{last_passed_task}}! Do you need help with {{next_task}}?"
    assert render_merge_fields(text, student) == "Congrats on passing Task 2! Do you need help with Task 3?"
