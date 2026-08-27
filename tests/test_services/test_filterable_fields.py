from dataclasses import fields

from src.models.student import Student
from src.services.filterable_fields import (
    FILTERABLE_FIELDS,
    FieldKind,
    Operator,
    MOMENTUM_VALUES,
    STUDENT_STATUS_VALUES,
    TASK_STATUS_VALUES,
    ASSESSMENT_STATUS_VALUES,
)

_STUDENT_FIELD_NAMES = {f.name for f in fields(Student)}


def test_every_entry_name_matches_its_dict_key():
    for key, entry in FILTERABLE_FIELDS.items():
        assert key == entry.name


def test_every_entry_is_a_real_student_attribute():
    for key in FILTERABLE_FIELDS:
        assert key in _STUDENT_FIELD_NAMES, f"{key} is not a Student field"


def test_registry_has_exactly_the_expected_field_count():
    # 3 identity + 6 program/course + 8 dates + 7 contact tracking +
    # 3 momentum/credit + 20 tasks (15 task_N + 5 others) + 6 assessments
    assert len(FILTERABLE_FIELDS) == 53


def test_set_value_fixed_entries_all_have_fixed_values():
    for entry in FILTERABLE_FIELDS.values():
        if entry.kind == FieldKind.SET_VALUE_FIXED:
            assert entry.fixed_values, f"{entry.name} is SET_VALUE_FIXED but has no fixed_values"
        else:
            assert entry.fixed_values is None, f"{entry.name} is not SET_VALUE_FIXED but has fixed_values"


def test_fields_deliberately_excluded_are_not_filterable():
    # Stored but not filterable, or removed entirely - either way, absent here.
    excluded = {
        "email", "phone", "has_signed_up_for_text", "texting_preference", "timezone",
        "latest_task", "latest_task_attempts",
    }
    assert excluded.isdisjoint(FILTERABLE_FIELDS.keys())


def test_known_value_lists_match_confirmed_real_data():
    assert MOMENTUM_VALUES == ["Low", "Med Low", "Med", "Med High", "High"]
    assert STUDENT_STATUS_VALUES == ["AS", "TB"]
    assert TASK_STATUS_VALUES == ["Passed", "Task Submitted", "Revisions Needed", "Evaluation Started"]
    assert ASSESSMENT_STATUS_VALUES == ["Passed", "Not Passed"]


def test_term_days_left_has_no_is_empty():
    ops = FILTERABLE_FIELDS["term_days_left"].operators
    assert Operator.IS_EMPTY not in ops
    assert Operator.GREATER_THAN_OR_EQUAL in ops


def test_days_since_last_course_contact_has_is_empty():
    ops = FILTERABLE_FIELDS["days_since_last_course_contact"].operators
    assert Operator.IS_EMPTY in ops


def test_latest_task_number_is_equals_only():
    assert FILTERABLE_FIELDS["latest_task_number"].operators == [Operator.EQUALS]


def test_course_code_is_live_dropdown_not_fixed():
    entry = FILTERABLE_FIELDS["course_code"]
    assert entry.kind == FieldKind.SET_VALUE_LIVE
    assert entry.fixed_values is None


def test_date_fields_include_the_full_retroactive_operator_set():
    ops = FILTERABLE_FIELDS["term_end_date"].operators
    for expected in (
        Operator.EQUALS, Operator.BEFORE, Operator.ON_OR_BEFORE, Operator.AFTER,
        Operator.ON_OR_AFTER, Operator.BETWEEN, Operator.MORE_THAN_DAYS_AGO,
        Operator.WITHIN_NEXT_DAYS, Operator.IS_EMPTY, Operator.IS_NOT_EMPTY,
    ):
        assert expected in ops
