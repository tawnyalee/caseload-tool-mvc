from src.models.student import Student
from src.services.task_utils import get_latest_task_number, is_latest_task_failed


def _student(**kwargs) -> Student:
    return Student(
        salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test",
        **kwargs,
    )


def test_no_tasks_submitted_returns_none():
    student = _student()
    assert get_latest_task_number(student) is None


def test_returns_highest_numbered_submitted_task():
    student = _student(task_1="2026-01-01 (1)", task_2="2026-01-08 (1)", task_3="2026-01-15 (1)")
    assert get_latest_task_number(student) == 3


def test_ignores_blank_and_whitespace_only_task_fields():
    student = _student(task_1="2026-01-01 (1)", task_2="   ", task_3="")
    assert get_latest_task_number(student) == 1


def test_only_task_one_submitted():
    student = _student(task_1="2026-01-01 (1)")
    assert get_latest_task_number(student) == 1


def test_all_fifteen_tasks_submitted_returns_fifteen():
    kwargs = {f"task_{n}": f"2026-01-{n:02d} (1)" for n in range(1, 16)}
    student = _student(**kwargs)
    assert get_latest_task_number(student) == 15


def test_revisions_needed_is_a_failure():
    student = _student(latest_task_status="Revisions Needed")
    assert is_latest_task_failed(student) is True


def test_passed_is_not_a_failure():
    student = _student(latest_task_status="Passed")
    assert is_latest_task_failed(student) is False


def test_pending_statuses_are_not_failures():
    for status in ("Task Submitted", "Evaluation Started"):
        student = _student(latest_task_status=status)
        assert is_latest_task_failed(student) is False


def test_no_submission_at_all_is_not_a_failure():
    student = _student()
    assert is_latest_task_failed(student) is False
