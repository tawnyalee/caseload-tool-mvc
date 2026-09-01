# src/services/merge_fields.py
"""Mail-merge token substitution for email subject/body. Supports exactly the
fields chosen for end-user personalization - not the full filterable-field
registry, since drafting an email is a different concern from filtering the
roster.
"""
from dataclasses import dataclass
from typing import Callable, Dict

from src.models.student import Student
from src.services.task_utils import MAX_TASK_NUMBER, is_latest_task_passed


@dataclass
class MergeField:
    token: str  # what the user inserts into subject/body, e.g. "{{student_name}}"
    label: str  # shown in the "Insert Field" picker, e.g. "Student Name"
    resolve: Callable[[Student], str]


def _last_submitted_task(student: Student) -> str:
    """The highest-numbered task the student has submitted, submitted or
    not - see task_utils.get_latest_task_number. Blank if nothing's been
    submitted at all (there's no "Task 0")."""
    if student.latest_task_number is None:
        return ""
    return f"Task {student.latest_task_number}"


def _last_passed_task(student: Student) -> str:
    """Only knowable when the student's most recent submission was itself a
    pass - there's no per-task pass/fail history on this data (see
    task_utils's module docstring), only the status of whichever task is
    latest. Blank rather than a guess in every other case (currently in
    revisions, pending evaluation, or nothing submitted)."""
    if student.latest_task_number is not None and is_latest_task_passed(student):
        return f"Task {student.latest_task_number}"
    return ""


def _next_task(student: Student) -> str:
    """The task the student hasn't submitted yet: Task 1 if nothing's been
    submitted, otherwise one past the last submitted task. Blank once
    they're past Task 15 - there's nothing left to point them to."""
    next_number = 1 if student.latest_task_number is None else student.latest_task_number + 1
    if next_number > MAX_TASK_NUMBER:
        return ""
    return f"Task {next_number}"


MERGE_FIELDS: Dict[str, MergeField] = {
    "student_name": MergeField("{{student_name}}", "Student Name", lambda s: s.full_name),
    "course_code": MergeField("{{course_code}}", "Course Code", lambda s: s.course_code),
    "last_submitted_task": MergeField("{{last_submitted_task}}", "Last Submitted Task", _last_submitted_task),
    "last_passed_task": MergeField("{{last_passed_task}}", "Last Passed Task", _last_passed_task),
    "next_task": MergeField("{{next_task}}", "Next Task", _next_task),
}


def render_merge_fields(text: str, student: Student) -> str:
    """Replaces every supported {{token}} occurrence in `text` with
    `student`'s value. A token that isn't recognized is left as-is - it
    might be literal text the sender typed on purpose, not a typo'd field."""
    for field in MERGE_FIELDS.values():
        text = text.replace(field.token, field.resolve(student))
    return text
