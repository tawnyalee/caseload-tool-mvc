# src/services/filter_engine.py
"""Evaluates a Student against an Action's filter conditions.

Every condition is combined with AND - there is no OR/grouping logic here
at all, by design (see docs/filter_engine_requirements.md): OR is only
ever needed across multiple values of the *same* field, which the IsOneOf
operator already covers on its own.

A condition looks like:
    {"field": "course_code", "operator": "IsOneOf", "value": ["D424", "C769"]}
    {"field": "days_since_last_course_contact", "operator": "GreaterThan", "value": "10"}
    {"field": "assignment_start_date", "operator": "IsEmpty"}

Unknown fields, operators not valid for that field's kind, and unparseable
values all fail to match rather than raising - a malformed condition or a
corrupted data value should never crash a batch send (see the real
data-corruption case documented in docs/filter_engine_requirements.md).
"""
from datetime import date, datetime, timedelta
import re
from typing import Any, Dict, List, Optional

from src.models.student import Student
from src.services.filterable_fields import FILTERABLE_FIELDS, FieldKind, Operator

_VALID_OPERATOR_VALUES = {field.name: {op.value for op in field.operators} for field in FILTERABLE_FIELDS.values()}

# Task fields store "YYYY-MM-DD (attempt#)" - strip the attempt suffix
# before parsing the date portion.
_TASK_DATE_SUFFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*\(\d+\)$")


def matches_student(student: Student, conditions: List[Dict[str, Any]]) -> bool:
    """True if `student` satisfies every condition (AND). No conditions
    means everyone matches, same as running an action unfiltered today."""
    return all(_matches_condition(student, condition) for condition in conditions)


def _matches_condition(student: Student, condition: Dict[str, Any]) -> bool:
    field_name = condition.get("field")
    field_def = FILTERABLE_FIELDS.get(field_name)
    if field_def is None:
        return False

    operator = condition.get("operator")
    if operator not in _VALID_OPERATOR_VALUES[field_name]:
        return False

    raw_value = getattr(student, field_name, None)
    is_blank = raw_value is None or (isinstance(raw_value, str) and not raw_value.strip())

    if operator == Operator.IS_EMPTY.value:
        return is_blank
    if operator == Operator.IS_NOT_EMPTY.value:
        return not is_blank
    if is_blank:
        return False  # a blank field can't satisfy any other operator

    value = condition.get("value")
    if field_def.kind == FieldKind.TEXT_EQUALS:
        return _text_equals(raw_value, operator, value)
    if field_def.kind in (FieldKind.SET_VALUE_FIXED, FieldKind.SET_VALUE_LIVE):
        return _is_one_of(raw_value, operator, value)
    if field_def.kind == FieldKind.TEXT_CONTAINS:
        return _contains(raw_value, operator, value)
    if field_def.kind == FieldKind.NUMERIC:
        return _numeric(raw_value, operator, value)
    if field_def.kind == FieldKind.DATE:
        return _date_compare(raw_value, operator, value)
    if field_def.kind == FieldKind.BOOLEAN:
        return _boolean(raw_value, operator, value)
    return False


def _text_equals(raw_value: str, operator: str, value: Any) -> bool:
    return operator == Operator.EQUALS.value and raw_value.strip() == str(value).strip()


def _is_one_of(raw_value: str, operator: str, value: Any) -> bool:
    if operator != Operator.IS_ONE_OF.value:
        return False
    candidates = value if isinstance(value, list) else [value]
    return raw_value.strip() in {str(v).strip() for v in candidates}


def _contains(raw_value: str, operator: str, value: Any) -> bool:
    return operator == Operator.CONTAINS.value and str(value).lower() in raw_value.lower()


def _parse_number(raw: Any) -> Optional[float]:
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw).strip().rstrip("%"))
    except (ValueError, TypeError):
        return None


def _numeric(raw_value: Any, operator: str, value: Any) -> bool:
    left = _parse_number(raw_value)
    right = _parse_number(value)
    if left is None or right is None:
        return False
    if operator == Operator.EQUALS.value:
        return left == right
    if operator == Operator.GREATER_THAN.value:
        return left > right
    if operator == Operator.GREATER_THAN_OR_EQUAL.value:
        return left >= right
    if operator == Operator.LESS_THAN.value:
        return left < right
    if operator == Operator.LESS_THAN_OR_EQUAL.value:
        return left <= right
    return False


def _parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().upper() == "TRUE"


def _boolean(raw_value: Any, operator: str, value: Any) -> bool:
    return operator == Operator.EQUALS.value and _parse_bool(raw_value) == _parse_bool(value)


def _parse_date(raw: Any) -> Optional[date]:
    text = str(raw).strip()
    if not text:
        return None

    match = _TASK_DATE_SUFFIX_RE.match(text)
    if match:
        text = match.group(1)
    elif "T" in text:  # ISO datetime, e.g. "2026-08-17T20:07:30.000Z"
        text = text.split("T", 1)[0]

    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _date_compare(raw_value: Any, operator: str, value: Any) -> bool:
    left = _parse_date(raw_value)
    if left is None:
        return False

    if operator == Operator.MORE_THAN_DAYS_AGO.value:
        n = _parse_number(value)
        return n is not None and left < (date.today() - timedelta(days=int(n)))

    if operator == Operator.WITHIN_NEXT_DAYS.value:
        n = _parse_number(value)
        if n is None:
            return False
        today = date.today()
        return today <= left <= today + timedelta(days=int(n))

    if operator == Operator.BETWEEN.value:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return False
        start, end = _parse_date(value[0]), _parse_date(value[1])
        return start is not None and end is not None and start <= left <= end

    right = _parse_date(value)
    if right is None:
        return False
    if operator == Operator.EQUALS.value:
        return left == right
    if operator == Operator.BEFORE.value:
        return left < right
    if operator == Operator.ON_OR_BEFORE.value:
        return left <= right
    if operator == Operator.AFTER.value:
        return left > right
    if operator == Operator.ON_OR_AFTER.value:
        return left >= right
    return False
