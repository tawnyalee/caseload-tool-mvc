from datetime import date, timedelta

from src.models.student import Student
from src.services.filter_engine import matches_student


def _student(**kwargs) -> Student:
    defaults = {"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", "email": "jane@example.test"}
    defaults.update(kwargs)
    return Student(**defaults)


def test_no_conditions_matches_everyone():
    assert matches_student(_student(), []) is True


def test_matches_student_ands_every_condition():
    student = _student(momentum="Low", course_code="D424")
    conditions = [
        {"field": "momentum", "operator": "IsOneOf", "value": ["Low"]},
        {"field": "course_code", "operator": "IsOneOf", "value": ["D424"]},
    ]
    assert matches_student(student, conditions) is True

    conditions_with_a_miss = conditions + [
        {"field": "course_version", "operator": "IsOneOf", "value": ["9"]},
    ]
    assert matches_student(student, conditions_with_a_miss) is False


def test_is_one_of_matches_any_listed_value():
    student = _student(course_code="C769")
    condition = {"field": "course_code", "operator": "IsOneOf", "value": ["D424", "C769"]}
    assert matches_student(student, [condition]) is True

    student_no_match = _student(course_code="D999")
    assert matches_student(student_no_match, [condition]) is False


def test_text_equals_on_identity_fields():
    student = _student(salesforce_id="000000001")
    assert matches_student(student, [{"field": "salesforce_id", "operator": "Equals", "value": "000000001"}]) is True
    assert matches_student(student, [{"field": "salesforce_id", "operator": "Equals", "value": "000000002"}]) is False


def test_contains_is_case_insensitive_substring():
    student = _student(course_followup_note="Task 2 Support")
    assert matches_student(student, [{"field": "course_followup_note", "operator": "Contains", "value": "task 2"}]) is True
    assert matches_student(student, [{"field": "course_followup_note", "operator": "Contains", "value": "task 9"}]) is False


def test_numeric_operators():
    student = _student(days_since_last_course_contact="10")
    assert matches_student(student, [{"field": "days_since_last_course_contact", "operator": "Equals", "value": "10"}]) is True
    assert matches_student(student, [{"field": "days_since_last_course_contact", "operator": "GreaterThan", "value": "5"}]) is True
    assert matches_student(student, [{"field": "days_since_last_course_contact", "operator": "GreaterThanOrEqual", "value": "10"}]) is True
    assert matches_student(student, [{"field": "days_since_last_course_contact", "operator": "LessThan", "value": "5"}]) is False
    assert matches_student(student, [{"field": "days_since_last_course_contact", "operator": "LessThanOrEqual", "value": "10"}]) is True


def test_numeric_handles_malformed_value_without_crashing():
    student = _student(days_since_last_course_contact="8/17/2026")  # garbled real-world example
    condition = {"field": "days_since_last_course_contact", "operator": "GreaterThan", "value": "5"}
    assert matches_student(student, [condition]) is False


def test_numeric_works_on_computed_int_field():
    student = _student(task_1="2026-01-01 (1)", task_2="2026-01-08 (1)")
    student.latest_task_number = 2
    assert matches_student(student, [{"field": "latest_task_number", "operator": "Equals", "value": "2"}]) is True
    assert matches_student(student, [{"field": "latest_task_number", "operator": "Equals", "value": "3"}]) is False


def test_date_equals_before_after():
    student = _student(term_end_date="6/15/2026")
    assert matches_student(student, [{"field": "term_end_date", "operator": "Equals", "value": "6/15/2026"}]) is True
    assert matches_student(student, [{"field": "term_end_date", "operator": "Before", "value": "7/1/2026"}]) is True
    assert matches_student(student, [{"field": "term_end_date", "operator": "After", "value": "7/1/2026"}]) is False
    assert matches_student(student, [{"field": "term_end_date", "operator": "OnOrBefore", "value": "6/15/2026"}]) is True
    assert matches_student(student, [{"field": "term_end_date", "operator": "OnOrAfter", "value": "6/15/2026"}]) is True


def test_date_between():
    student = _student(term_end_date="6/15/2026")
    assert matches_student(student, [{"field": "term_end_date", "operator": "Between", "value": ["6/1/2026", "6/30/2026"]}]) is True
    assert matches_student(student, [{"field": "term_end_date", "operator": "Between", "value": ["7/1/2026", "7/30/2026"]}]) is False


def test_date_more_than_days_ago_and_within_next_days():
    ten_days_ago = (date.today() - timedelta(days=10)).strftime("%m/%d/%Y")
    five_days_ahead = (date.today() + timedelta(days=5)).strftime("%m/%d/%Y")

    stale_student = _student(term_end_date=ten_days_ago)
    assert matches_student(stale_student, [{"field": "term_end_date", "operator": "MoreThanDaysAgo", "value": "5"}]) is True
    assert matches_student(stale_student, [{"field": "term_end_date", "operator": "MoreThanDaysAgo", "value": "20"}]) is False

    upcoming_student = _student(term_end_date=five_days_ahead)
    assert matches_student(upcoming_student, [{"field": "term_end_date", "operator": "WithinNextDays", "value": "7"}]) is True
    assert matches_student(upcoming_student, [{"field": "term_end_date", "operator": "WithinNextDays", "value": "2"}]) is False


def test_date_parsing_handles_every_real_format():
    # plain M/D/YYYY
    assert matches_student(_student(term_end_date="6/15/2026"), [{"field": "term_end_date", "operator": "Equals", "value": "6/15/2026"}]) is True
    # ISO datetime with time component
    assert matches_student(_student(course_contact="2026-06-15T20:07:30.000Z"), [{"field": "course_contact", "operator": "Equals", "value": "6/15/2026"}]) is True
    # task composite "date (attempt)" format
    assert matches_student(_student(task_1="2026-06-15 (1)"), [{"field": "task_1", "operator": "Equals", "value": "6/15/2026"}]) is True


def test_date_handles_unparseable_value_without_crashing():
    student = _student(term_end_date="not a date")
    assert matches_student(student, [{"field": "term_end_date", "operator": "Before", "value": "6/15/2026"}]) is False


def test_is_empty_and_is_not_empty():
    empty_student = _student()
    filled_student = _student(assignment_start_date="6/15/2026")
    assert matches_student(empty_student, [{"field": "assignment_start_date", "operator": "IsEmpty"}]) is True
    assert matches_student(empty_student, [{"field": "assignment_start_date", "operator": "IsNotEmpty"}]) is False
    assert matches_student(filled_student, [{"field": "assignment_start_date", "operator": "IsEmpty"}]) is False
    assert matches_student(filled_student, [{"field": "assignment_start_date", "operator": "IsNotEmpty"}]) is True


def test_boolean_equals():
    student = _student(latest_task_date_yesterday="TRUE")
    assert matches_student(student, [{"field": "latest_task_date_yesterday", "operator": "Equals", "value": "TRUE"}]) is True
    assert matches_student(student, [{"field": "latest_task_date_yesterday", "operator": "Equals", "value": "FALSE"}]) is False


def test_unknown_field_never_matches():
    student = _student()
    assert matches_student(student, [{"field": "not_a_real_field", "operator": "Equals", "value": "x"}]) is False


def test_operator_not_valid_for_field_kind_never_matches():
    # Contains isn't a valid operator for a numeric field
    student = _student(days_since_last_course_contact="10")
    condition = {"field": "days_since_last_course_contact", "operator": "Contains", "value": "1"}
    assert matches_student(student, [condition]) is False


def test_real_example_just_passed_task_2():
    """From docs/filter_engine_requirements.md: task_2 has a date, task_3 is
    still empty, and latest_task_status is Passed - the 3-condition pattern
    for correctly identifying 'just passed task 2'."""
    conditions = [
        {"field": "task_2", "operator": "IsNotEmpty"},
        {"field": "task_3", "operator": "IsEmpty"},
        {"field": "latest_task_status", "operator": "IsOneOf", "value": ["Passed"]},
    ]

    passed_student = _student(task_2="2026-06-15 (1)", task_3="", latest_task_status="Passed")
    assert matches_student(passed_student, conditions) is True

    revisions_needed_student = _student(task_2="2026-06-15 (1)", task_3="", latest_task_status="Revisions Needed")
    assert matches_student(revisions_needed_student, conditions) is False

    already_moved_on_student = _student(task_2="2026-06-15 (1)", task_3="2026-06-20 (1)", latest_task_status="Passed")
    assert matches_student(already_moved_on_student, conditions) is False


def test_real_example_low_momentum_across_multiple_courses():
    """From the developer's own example: course code as an OR (IsOneOf),
    momentum as an AND, task status as an AND - no OR/grouping logic needed."""
    conditions = [
        {"field": "course_code", "operator": "IsOneOf", "value": ["D424", "D370", "D030"]},
        {"field": "momentum", "operator": "IsOneOf", "value": ["Low"]},
        {"field": "task_1", "operator": "IsEmpty"},
    ]

    matching_student = _student(course_code="D370", momentum="Low", task_1="")
    assert matches_student(matching_student, conditions) is True

    wrong_course_student = _student(course_code="D999", momentum="Low", task_1="")
    assert matches_student(wrong_course_student, conditions) is False

    already_submitted_student = _student(course_code="D424", momentum="Low", task_1="2026-06-15 (1)")
    assert matches_student(already_submitted_student, conditions) is False
