# src/services/csv_student_import.py
"""Shared raw-CSV-row -> Student-field-dict conversion. Originally built
just for scripts/convert_sample_csv_to_fixture.py (regenerating the fake
fixture from Sample.csv); reused here by CsvStudentDataProvider
(src/services/student_data_provider.py) - the hedge adapter for reading
the roster from a real Salesforce report export CSV if live API access
isn't available. Both read the exact same raw column shape (a Salesforce
report/export - see Student.SALESFORCE_FIELD_MAP for the column names),
so there's one place that knows how to turn a row into Student fields.
"""
import csv
from dataclasses import fields
from pathlib import Path
from typing import Dict, List

from src.models.student import Student
from src.services.name_utils import resolve_first_last_name
from src.services.task_utils import get_latest_task_number

# reverse of Student.SALESFORCE_FIELD_MAP: raw CSV column -> snake_case field
_RAW_TO_FIELD = {raw: snake for snake, raw in Student.SALESFORCE_FIELD_MAP.items()}
_STUDENT_FIELD_NAMES = {f.name for f in fields(Student)}


def csv_row_to_student_fields(row: Dict[str, str]) -> dict:
    """Converts one raw CSV row (Salesforce export column names) into a
    dict of Student field names -> values. first_name/last_name are
    synthesized from the "Name"/"stuprename" (preferred name) columns
    rather than a 1:1 mapping - see SALESFORCE_FIELD_MAP's own comment on
    why those two aren't listed there."""
    first_name, last_name = resolve_first_last_name(row.get("Name", ""), row.get("stuprename", ""))
    record = {
        "first_name": first_name,
        "last_name": last_name,
        "has_signed_up_for_text": row.get("TextingPreference", "") == "Opted In",
    }
    for raw_col, value in row.items():
        field_name = _RAW_TO_FIELD.get(raw_col)
        if field_name:
            record[field_name] = value
    return record


def parse_students_csv(csv_path: Path) -> List[Student]:
    """Parses a Salesforce report-export CSV at csv_path into Students,
    computing latest_task_number the same way every StudentDataProvider
    does. Used by both CsvStudentDataProvider (reads a manually-placed
    file) and PlaywrightStudentDataProvider (downloads the same shape of
    file via browser automation) - parsing is identical either way, only
    how the file gets there differs.

    If the CSV's header is missing a column Student requires (StudentID/
    Email - first_name/last_name always come from csv_row_to_student_fields,
    even if blank), csv.DictReader still fills every declared row with
    every declared header, so a per-row TypeError from a merely blank
    value can't happen - only a whole-file one, if the export itself was
    generated without a required column. That case is caught per-row here
    so one clearly-broken export returns an empty roster (and can be
    noticed and re-exported) rather than raising and crashing the caller.
    Not surfaced/logged anywhere yet - acceptable for this hedge/prototype
    pass, worth revisiting if this ends up as the real long-term source."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return []

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    students = []
    for row in rows:
        record = csv_row_to_student_fields(row)
        record = {k: v for k, v in record.items() if k in _STUDENT_FIELD_NAMES}
        try:
            students.append(Student(**record))
        except TypeError:
            continue

    for student in students:
        student.latest_task_number = get_latest_task_number(student)
    return students
