# src/services/filterable_fields.py
"""Registry of which Student fields are filterable, what kind each one is,
and which operators apply to it - the single source of truth for both the
filter-evaluation engine (filter_engine.py, built next) and the eventual
filter-building UI in AddActionView, so they can't drift out of sync with
each other.

Built directly from docs/filter_engine_requirements.md - don't add, remove,
or change an entry here without updating that doc to match, and vice versa.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class FieldKind(Enum):
    TEXT_EQUALS = "text_equals"           # unbounded, typed exact match (names, IDs)
    SET_VALUE_FIXED = "set_value_fixed"   # small hand-maintained list of known values
    SET_VALUE_LIVE = "set_value_live"     # dropdown built from whatever values exist in the data right now
    TEXT_CONTAINS = "text_contains"       # free text, substring search
    NUMERIC = "numeric"                   # stored as a string, compared as a number
    DATE = "date"                         # stored as a string, compared as a date
    BOOLEAN = "boolean"                   # "TRUE"/"FALSE" strings


class Operator(Enum):
    EQUALS = "Equals"
    IS_ONE_OF = "IsOneOf"
    CONTAINS = "Contains"
    GREATER_THAN = "GreaterThan"
    GREATER_THAN_OR_EQUAL = "GreaterThanOrEqual"
    LESS_THAN = "LessThan"
    LESS_THAN_OR_EQUAL = "LessThanOrEqual"
    BEFORE = "Before"
    ON_OR_BEFORE = "OnOrBefore"
    AFTER = "After"
    ON_OR_AFTER = "OnOrAfter"
    BETWEEN = "Between"
    MORE_THAN_DAYS_AGO = "MoreThanDaysAgo"
    WITHIN_NEXT_DAYS = "WithinNextDays"
    IS_EMPTY = "IsEmpty"
    IS_NOT_EMPTY = "IsNotEmpty"


@dataclass
class FilterableField:
    name: str                       # the matching attribute name on Student
    kind: FieldKind
    operators: List[Operator]
    fixed_values: Optional[List[str]] = None  # only set for SET_VALUE_FIXED


# Shared operator sets, so the table below stays readable and consistent.
_TEXT_EQUALS_OPS = [Operator.EQUALS]
_SET_VALUE_OPS = [Operator.IS_ONE_OF]
_SET_VALUE_OPS_WITH_EMPTY = [Operator.IS_ONE_OF, Operator.IS_EMPTY, Operator.IS_NOT_EMPTY]
_CONTAINS_OPS = [Operator.CONTAINS, Operator.IS_EMPTY, Operator.IS_NOT_EMPTY]
_NUMERIC_OPS = [
    Operator.EQUALS, Operator.GREATER_THAN, Operator.GREATER_THAN_OR_EQUAL,
    Operator.LESS_THAN, Operator.LESS_THAN_OR_EQUAL,
]
_NUMERIC_OPS_WITH_EMPTY = _NUMERIC_OPS + [Operator.IS_EMPTY]
_DATE_OPS = [
    Operator.EQUALS, Operator.BEFORE, Operator.ON_OR_BEFORE, Operator.AFTER,
    Operator.ON_OR_AFTER, Operator.BETWEEN, Operator.MORE_THAN_DAYS_AGO,
    Operator.WITHIN_NEXT_DAYS, Operator.IS_EMPTY, Operator.IS_NOT_EMPTY,
]
_BOOLEAN_OPS = [Operator.EQUALS]

# Fixed known-value lists for the SET_VALUE_FIXED fields (as opposed to
# SET_VALUE_LIVE fields, whose options come from whatever's actually in the
# pulled data - see docs/filter_engine_requirements.md).
MOMENTUM_VALUES = ["Low", "Med Low", "Med", "Med High", "High"]
STUDENT_STATUS_VALUES = ["AS", "TB"]
TASK_STATUS_VALUES = ["Passed", "Task Submitted", "Revisions Needed", "Evaluation Started"]
ASSESSMENT_STATUS_VALUES = ["Passed", "Not Passed"]


def _date_field(name: str) -> FilterableField:
    return FilterableField(name, FieldKind.DATE, _DATE_OPS)


FILTERABLE_FIELDS: Dict[str, FilterableField] = {
    # Identity / Contact
    "salesforce_id": FilterableField("salesforce_id", FieldKind.TEXT_EQUALS, _TEXT_EQUALS_OPS),
    "first_name": FilterableField("first_name", FieldKind.TEXT_EQUALS, _TEXT_EQUALS_OPS),
    "last_name": FilterableField("last_name", FieldKind.TEXT_EQUALS, _TEXT_EQUALS_OPS),

    # Program / course identity - live dropdown, built from current data
    "program_code": FilterableField("program_code", FieldKind.SET_VALUE_LIVE, _SET_VALUE_OPS),
    "program_name": FilterableField("program_name", FieldKind.SET_VALUE_LIVE, _SET_VALUE_OPS),
    "program_version": FilterableField("program_version", FieldKind.SET_VALUE_LIVE, _SET_VALUE_OPS),
    "course_code": FilterableField("course_code", FieldKind.SET_VALUE_LIVE, _SET_VALUE_OPS),
    "course_version": FilterableField("course_version", FieldKind.SET_VALUE_LIVE, _SET_VALUE_OPS),
    "course_status": FilterableField("course_status", FieldKind.SET_VALUE_LIVE, _SET_VALUE_OPS),

    # Dates / term timeline
    "course_start_date": _date_field("course_start_date"),
    "course_end_date": _date_field("course_end_date"),
    "term_start_date": _date_field("term_start_date"),
    "term_end_date": _date_field("term_end_date"),
    "term_break_end_date": _date_field("term_break_end_date"),
    "actual_start_date": _date_field("actual_start_date"),
    "assignment_start_date": _date_field("assignment_start_date"),
    "term_days_left": FilterableField("term_days_left", FieldKind.NUMERIC, _NUMERIC_OPS),

    # Contact / outreach tracking
    "course_contact": _date_field("course_contact"),
    "last_sm_contact": _date_field("last_sm_contact"),
    "my_course_contact": _date_field("my_course_contact"),
    "last_academic_activity_date": _date_field("last_academic_activity_date"),
    "days_since_last_course_contact": FilterableField(
        "days_since_last_course_contact", FieldKind.NUMERIC, _NUMERIC_OPS_WITH_EMPTY
    ),
    "course_followup_note": FilterableField("course_followup_note", FieldKind.TEXT_CONTAINS, _CONTAINS_OPS),
    "student_status": FilterableField(
        "student_status", FieldKind.SET_VALUE_FIXED, _SET_VALUE_OPS, fixed_values=STUDENT_STATUS_VALUES
    ),

    # Momentum / credit / SAP
    "momentum": FilterableField(
        "momentum", FieldKind.SET_VALUE_FIXED, _SET_VALUE_OPS, fixed_values=MOMENTUM_VALUES
    ),
    "term_remaining_cu": FilterableField("term_remaining_cu", FieldKind.NUMERIC, _NUMERIC_OPS),
    "term_sap": FilterableField("term_sap", FieldKind.NUMERIC, _NUMERIC_OPS),

    # Tasks - task_1..task_15 all share the same shape, so generate them
    # instead of writing 15 near-identical lines by hand.
    **{f"task_{n}": _date_field(f"task_{n}") for n in range(1, 16)},
    "latest_task_status": FilterableField(
        "latest_task_status", FieldKind.SET_VALUE_FIXED, _SET_VALUE_OPS_WITH_EMPTY,
        fixed_values=TASK_STATUS_VALUES,
    ),
    "latest_task_date": _date_field("latest_task_date"),
    "latest_task_date_yesterday": FilterableField(
        "latest_task_date_yesterday", FieldKind.BOOLEAN, _BOOLEAN_OPS
    ),
    "number_of_days_since_last_task_date": FilterableField(
        "number_of_days_since_last_task_date", FieldKind.NUMERIC, _NUMERIC_OPS_WITH_EMPTY
    ),
    "latest_task_number": FilterableField("latest_task_number", FieldKind.NUMERIC, [Operator.EQUALS]),

    # Assessments
    "last_pre_assessment_date": _date_field("last_pre_assessment_date"),
    "last_pre_assessment_actual_date": _date_field("last_pre_assessment_actual_date"),
    "last_pre_assessment_status": FilterableField(
        "last_pre_assessment_status", FieldKind.SET_VALUE_FIXED, _SET_VALUE_OPS_WITH_EMPTY,
        fixed_values=ASSESSMENT_STATUS_VALUES,
    ),
    "last_objective_assessment_date": _date_field("last_objective_assessment_date"),
    "last_objective_assessment_actual_date": _date_field("last_objective_assessment_actual_date"),
    "last_objective_assessment_status": FilterableField(
        "last_objective_assessment_status", FieldKind.SET_VALUE_FIXED, _SET_VALUE_OPS_WITH_EMPTY,
        fixed_values=ASSESSMENT_STATUS_VALUES,
    ),
}
