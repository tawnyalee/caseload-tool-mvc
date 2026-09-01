# src/services/note_records.py
"""The record that would need to persist to wherever student communication
history is kept (Salesforce today, possibly Learner360 later - see
CLAUDE.md's platform-independence design decision) as a result of one
note step. Kept platform-independent on purpose - the real adapter,
whichever backend it targets, decides how many actual API calls this
becomes (e.g. one write for the interaction note, another for the
follow-up field); nothing here assumes Salesforce specifically.
"""
from dataclasses import dataclass
from typing import List, Optional

from src.models.student import Student


@dataclass
class NoteInsertRecord:
    salesforce_id: str
    course_code: str
    note_subject: str
    note_body: str
    follow_up_note: str


def resolve_course_code(student: Student, group_name: Optional[str] = None) -> str:
    """The course code to record for a note: the group's name if it's a
    real, specific course group (groups are course codes for this app's
    purposes); the student's own course_code field if the action ran via
    "General" or an ad-hoc send with no group at all. May come back blank
    if the student's own record doesn't have a course_code - that's an
    accepted, valid outcome (e.g. a mentor's view may not always have
    one), not an error."""
    if group_name and group_name != "General":
        return group_name
    return student.course_code


def validate_note_record(record: NoteInsertRecord) -> List[str]:
    """Returns a list of problems with `record` (empty list = valid).
    Only checks what's verifiable without knowing real backend-specific
    constraints (object type, field limits) - those aren't known until
    the real adapter is scoped, so this isn't a guarantee Salesforce (or
    Learner360) would actually accept the record, just that it's not
    obviously broken on our side."""
    problems = []
    if not record.salesforce_id or not record.salesforce_id.strip():
        problems.append("Missing student ID - cannot insert without knowing who this is for.")
    if not (record.note_subject.strip() or record.note_body.strip() or record.follow_up_note.strip()):
        problems.append("No note content at all - nothing to insert.")
    return problems
