from src.models.student import Student
from src.services.note_records import NoteInsertRecord, resolve_course_code, validate_note_record


def _student(**kwargs) -> Student:
    defaults = {"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", "email": "jane@example.test"}
    defaults.update(kwargs)
    return Student(**defaults)


def test_resolve_course_code_uses_the_group_name_for_a_real_course_group():
    student = _student(course_code="D999")  # should be ignored - group wins
    assert resolve_course_code(student, "D424") == "D424"


def test_resolve_course_code_uses_the_students_own_field_for_general():
    student = _student(course_code="D424")
    assert resolve_course_code(student, "General") == "D424"


def test_resolve_course_code_uses_the_students_own_field_with_no_group_at_all():
    """Covers the ad-hoc 'Send Email to All Students' case, which has no
    group concept at all."""
    student = _student(course_code="D370")
    assert resolve_course_code(student, None) == "D370"
    assert resolve_course_code(student, "") == "D370"


def test_resolve_course_code_can_come_back_blank():
    """A mentor's view of a student may not always have a course_code -
    that's an accepted outcome, not an error."""
    student = _student(course_code="")
    assert resolve_course_code(student, "General") == ""


def test_validate_note_record_flags_missing_student_id():
    record = NoteInsertRecord(
        salesforce_id="", course_code="D424", note_subject="Hi", note_body="", follow_up_note=""
    )
    problems = validate_note_record(record)
    assert len(problems) == 1
    assert "student ID" in problems[0]


def test_validate_note_record_flags_no_content_at_all():
    record = NoteInsertRecord(
        salesforce_id="SF1", course_code="D424", note_subject="", note_body="", follow_up_note=""
    )
    problems = validate_note_record(record)
    assert len(problems) == 1
    assert "content" in problems[0]


def test_validate_note_record_passes_with_only_a_follow_up_note():
    record = NoteInsertRecord(
        salesforce_id="SF1", course_code="D424", note_subject="", note_body="", follow_up_note="Checked in"
    )
    assert validate_note_record(record) == []


def test_validate_note_record_can_have_multiple_problems():
    record = NoteInsertRecord(
        salesforce_id="", course_code="", note_subject="", note_body="", follow_up_note=""
    )
    assert len(validate_note_record(record)) == 2
