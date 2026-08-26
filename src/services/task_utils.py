# src/services/task_utils.py
"""Helper for the Task1..Task15 flat field structure (see docs/filter_engine_requirements.md).

Salesforce's LatestTask/LatestTaskStatus/LatestTaskDate/LatestTaskAttempts
fields already give the status, date, and attempt count of whichever task
is latest - but not its number. This fills that one gap.
"""
from typing import Optional

from src.models.student import Student

MAX_TASK_NUMBER = 15

# The confirmed-complete set of real LatestTaskStatus values (see
# docs/filter_engine_requirements.md). "Revisions Needed" is the only one
# that means failed-but-can-resubmit; the others are a pass or still-pending
# states, not failures.
TASK_STATUS_FAILED = "Revisions Needed"


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
