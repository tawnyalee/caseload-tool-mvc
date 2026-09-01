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
from typing import Dict

from src.models.student import Student
from src.services.name_utils import resolve_first_last_name

# reverse of Student.SALESFORCE_FIELD_MAP: raw CSV column -> snake_case field
_RAW_TO_FIELD = {raw: snake for snake, raw in Student.SALESFORCE_FIELD_MAP.items()}


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
