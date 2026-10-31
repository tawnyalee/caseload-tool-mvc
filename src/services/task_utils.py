# src/services/task_utils.py
"""Helper for the Task1..Task15 flat field structure (see docs/filter_engine_requirements.md).

Salesforce's LatestTask/LatestTaskStatus/LatestTaskDate/LatestTaskAttempts
fields already give the status, date, and attempt count of whichever task
is latest - but not its number. This fills that one gap.
"""
from datetime import date, datetime
from typing import Optional

from src.models.student import Student

MAX_TASK_NUMBER = 15

# The confirmed-complete set of real LatestTaskStatus values (see
# docs/filter_engine_requirements.md). "Revisions Needed" is the only one
# that means failed-but-can-resubmit; the others are a pass or still-pending
# states, not failures.
TASK_STATUS_FAILED = "Revisions Needed"
TASK_STATUS_PASSED = "Passed"


def get_latest_task_number(student: Student) -> Optional[int]:
    """Returns the highest-numbered Task1..Task15 field on `student` that
    has a value, or None if no tasks have been submitted at all.

    This is a heuristic, not a guarantee: if a student submits multiple
    tasks in one batch (against the intended one-at-a-time flow), the
    highest-numbered one isn't necessarily the one LatestTaskStatus
    actually describes. By agreement, this is acceptable - a human visual
    check is expected before sending anything task-specific.
    """
    latest = None
    for n in range(1, MAX_TASK_NUMBER + 1):
        if getattr(student, f"task_{n}", "").strip():
            latest = n
    return latest


def is_latest_task_failed(student: Student) -> bool:
    """True if the student's most recent task submission came back needing
    revisions (this org's definition of "failed, but can resubmit"). False
    for a pass, a still-pending status, or no submission at all."""
    return student.latest_task_status.strip() == TASK_STATUS_FAILED


def is_latest_task_passed(student: Student) -> bool:
    """True if the student's most recent task submission passed. Mirrors
    is_latest_task_failed - see its docstring for the same caveats."""
    return student.latest_task_status.strip() == TASK_STATUS_PASSED


def parse_task_date(text: str) -> Optional[date]:
    """The date in a Task1..Task15 value ("2026-07-27 (1)") or LatestTaskDate
    ("7/27/2026"), or None if there isn't a readable one."""
    parts = (text or "").split()
    if not parts:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(parts[0], fmt).date()
        except ValueError:
            continue
    return None


def passed_task_number(student: Student) -> Optional[int]:
    """The task the Passed status belongs to, or None if the latest status
    isn't Passed. Not simply the highest-numbered task: a student can submit
    Task 3 while Task 2 is being evaluated, and then Passed is about Task 2
    (found live 2026-10-30, and in Sample.csv). So it's the task dated the
    same as LatestTaskDate, preferring one that's been evaluated (a value
    ending "(0)" hasn't been) if two share that date. With no date match,
    falls back to latest_task_number."""
    if not is_latest_task_passed(student):
        return None
    latest_date = parse_task_date(student.latest_task_date)
    dated = {n: getattr(student, f"task_{n}", "") for n in range(1, MAX_TASK_NUMBER + 1)}
    matches = [n for n, value in dated.items() if latest_date and parse_task_date(value) == latest_date]
    evaluated = [n for n in matches if not dated[n].strip().endswith("(0)")]
    if matches:
        return (evaluated or matches)[-1]
    return student.latest_task_number


def has_submitted_task(student: Student, task_number: int) -> bool:
    return bool(getattr(student, f"task_{task_number}", "").strip())
