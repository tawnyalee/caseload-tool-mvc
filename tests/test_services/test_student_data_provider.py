import json

import pytest

from src.models.student import Student
from src.services import salesforce_browser_session as sbs
from src.services.student_data_provider import (
    CsvStudentDataProvider,
    FakeStudentDataProvider,
    PlaywrightStudentDataProvider,
)


def test_fake_provider_loads_fixture_students(tmp_path):
    fixture = tmp_path / "fake_students.json"
    fixture.write_text(
        '[{"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", '
        '"email": "jane@example.test", "phone": "555-1111", "has_signed_up_for_text": true}]',
        encoding="utf-8",
    )

    provider = FakeStudentDataProvider(file_path=str(fixture))
    students = provider.get_students()

    assert len(students) == 1
    assert isinstance(students[0], Student)
    assert students[0].full_name == "Jane Doe"
    assert students[0].email == "jane@example.test"
    assert students[0].has_signed_up_for_text is True


def test_fake_provider_creates_empty_fixture_if_missing(tmp_path):
    fixture = tmp_path / "does_not_exist_yet.json"
    provider = FakeStudentDataProvider(file_path=str(fixture))

    assert fixture.exists()
    assert provider.get_students() == []


def test_fake_provider_returns_empty_list_on_malformed_json(tmp_path):
    fixture = tmp_path / "broken.json"
    fixture.write_text("{not valid json", encoding="utf-8")

    provider = FakeStudentDataProvider(file_path=str(fixture))
    assert provider.get_students() == []


def test_shipped_fake_fixture_loads_cleanly():
    """Sanity-checks the actual data/fake_students.json fixture committed to the repo."""
    provider = FakeStudentDataProvider()
    students = provider.get_students()

    assert len(students) >= 1
    assert all(isinstance(s, Student) for s in students)
    assert all(s.email for s in students)


def test_get_students_computes_latest_task_number(tmp_path):
    """latest_task_number isn't stored in the JSON fixture - it must be
    computed fresh every load, since it's derived from task_1..task_15."""
    fixture = tmp_path / "fake_students.json"
    fixture.write_text(
        '[{"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", '
        '"email": "jane@example.test", "task_1": "2026-01-01 (1)", "task_2": "2026-01-08 (1)"},'
        '{"salesforce_id": "SF2", "first_name": "John", "last_name": "Roe", '
        '"email": "john@example.test"}]',
        encoding="utf-8",
    )

    provider = FakeStudentDataProvider(file_path=str(fixture))
    students = provider.get_students()

    assert students[0].latest_task_number == 2
    assert students[1].latest_task_number is None


def _write_csv(path, header, rows):
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_csv_provider_returns_empty_list_when_file_missing(tmp_path):
    provider = CsvStudentDataProvider(csv_path=tmp_path / "does_not_exist.csv")
    assert provider.get_students() == []


def test_csv_provider_parses_a_real_export_shaped_csv(tmp_path):
    csv_path = tmp_path / "export.csv"
    _write_csv(
        csv_path,
        ["StudentID", "StudentEmail", "MobilePhone", "Name", "stuprename", "CourseCode", "TextingPreference"],
        [["SF1", "jane@example.test", "555-0001", "Jane Doe", "", "D424", "Opted In"]],
    )

    provider = CsvStudentDataProvider(csv_path=csv_path)
    students = provider.get_students()

    assert len(students) == 1
    student = students[0]
    assert isinstance(student, Student)
    assert student.salesforce_id == "SF1"
    assert student.email == "jane@example.test"
    assert student.course_code == "D424"
    assert student.full_name == "Jane Doe"
    assert student.has_signed_up_for_text is True


def test_csv_provider_returns_empty_roster_rather_than_crashing_when_a_required_column_is_missing(tmp_path):
    """csv.DictReader fills every declared header for every row, so a
    blank value alone can never omit a required Student kwarg - only a
    whole export generated without a required column (here, StudentID)
    can. That must return an empty roster, not raise, so one bad export
    doesn't crash the caller."""
    csv_path = tmp_path / "export.csv"
    _write_csv(
        csv_path,
        ["StudentEmail", "Name"],  # StudentID column missing entirely
        [["jane@example.test", "Jane Doe"]],
    )

    provider = CsvStudentDataProvider(csv_path=csv_path)
    assert provider.get_students() == []


def test_csv_provider_computes_latest_task_number(tmp_path):
    csv_path = tmp_path / "export.csv"
    _write_csv(
        csv_path,
        ["StudentID", "StudentEmail", "Name", "Task1", "Task2"],
        [["SF1", "jane@example.test", "Jane Doe", "2026-01-01 (1)", "2026-01-08 (1)"]],
    )

    provider = CsvStudentDataProvider(csv_path=csv_path)
    students = provider.get_students()

    assert students[0].latest_task_number == 2


_EXPORT_PAGE_HTML = """<!DOCTYPE html>
<html><body>
<button id="export-btn" onclick="downloadCsv()">Export</button>
<script>
function downloadCsv() {{
  const csv = {csv_js_string};
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'export.csv';
  document.body.appendChild(a);
  a.click();
}}
</script>
</body></html>
"""


def test_playwright_provider_downloads_and_parses_the_exported_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(sbs, "STORAGE_STATE_PATH", tmp_path / "session.json")
    sbs.STORAGE_STATE_PATH.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    csv_content = "StudentID,StudentEmail,Name,CourseCode\nSF1,jane@example.test,Jane Doe,D424\n"
    html_path = tmp_path / "report.html"
    html_path.write_text(
        _EXPORT_PAGE_HTML.format(csv_js_string=json.dumps(csv_content)), encoding="utf-8"
    )

    provider = PlaywrightStudentDataProvider(
        report_url=f"file:///{html_path.as_posix()}",
        export_button_selector="#export-btn",
        headless=True,
    )
    students = provider.get_students()

    assert len(students) == 1
    assert students[0].salesforce_id == "SF1"
    assert students[0].course_code == "D424"
    assert students[0].full_name == "Jane Doe"


def test_playwright_provider_raises_a_clear_error_when_no_session_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(sbs, "STORAGE_STATE_PATH", tmp_path / "session.json")

    provider = PlaywrightStudentDataProvider(
        report_url="file:///does-not-matter.html", export_button_selector="#export-btn",
    )

    with pytest.raises(RuntimeError, match="salesforce_login.py"):
        provider.get_students()
