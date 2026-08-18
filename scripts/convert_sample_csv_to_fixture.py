# scripts/convert_sample_csv_to_fixture.py
"""One-off dev tool: regenerate data/fake_students.json from Sample.csv.

Run this manually whenever Sample.csv is updated with new sanitized test
data:

    python scripts/convert_sample_csv_to_fixture.py

Not used by the running app — FakeStudentDataProvider only ever reads the
JSON fixture this produces.
"""
import csv
import json
from pathlib import Path

from src.models.student import Student
from src.services.name_utils import resolve_first_last_name

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Sample.csv"
FIXTURE_PATH = REPO_ROOT / "data" / "fake_students.json"

# reverse of Student.SALESFORCE_FIELD_MAP: raw CSV column -> snake_case field
_RAW_TO_FIELD = {raw: snake for snake, raw in Student.SALESFORCE_FIELD_MAP.items()}


def convert_row(row: dict) -> dict:
    first_name, last_name = resolve_first_last_name(
        row.get("Name", ""), row.get("stuprename", "")
    )
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


def main() -> None:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    students = [convert_row(row) for row in rows]

    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(students, f, indent=4)

    print(f"Wrote {len(students)} students to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
