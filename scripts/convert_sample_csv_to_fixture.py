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

from src.services.csv_student_import import csv_row_to_student_fields

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Sample.csv"
FIXTURE_PATH = REPO_ROOT / "data" / "fake_students.json"


def main() -> None:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    students = [csv_row_to_student_fields(row) for row in rows]

    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(students, f, indent=4)

    print(f"Wrote {len(students)} students to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
