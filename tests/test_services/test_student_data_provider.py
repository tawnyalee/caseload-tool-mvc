import json
from pathlib import Path

import pytest

import src.services.student_data_provider as sdp
from src.models.student import Student
from src.services import salesforce_browser_session as sbs
from src.services.student_data_provider import (
    CachingStudentDataProvider,
    CsvStudentDataProvider,
    FakeStudentDataProvider,
    PlaywrightStudentDataProvider,
    StudentDataProvider,
    _looks_like_a_different_host,
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


def test_playwright_provider_cleans_up_the_downloaded_csvs_temp_dir(tmp_path, monkeypatch):
    """The downloaded roster CSV is real student PII - per the developer's
    explicit FERPA constraint, its temp directory must not linger on disk
    after parsing, success or failure."""
    monkeypatch.setattr(sbs, "STORAGE_STATE_PATH", tmp_path / "session.json")
    sbs.STORAGE_STATE_PATH.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    csv_content = "StudentID,StudentEmail,Name,CourseCode\nSF1,jane@example.test,Jane Doe,D424\n"
    html_path = tmp_path / "report.html"
    html_path.write_text(
        _EXPORT_PAGE_HTML.format(csv_js_string=json.dumps(csv_content)), encoding="utf-8"
    )

    created_dirs = []
    real_mkdtemp = sdp.tempfile.mkdtemp

    def _tracking_mkdtemp(*args, **kwargs):
        created = real_mkdtemp(*args, **kwargs)
        created_dirs.append(created)
        return created

    monkeypatch.setattr(sdp.tempfile, "mkdtemp", _tracking_mkdtemp)

    provider = PlaywrightStudentDataProvider(
        report_url=f"file:///{html_path.as_posix()}",
        export_button_selector="#export-btn",
        headless=True,
    )
    provider.get_students()

    assert created_dirs, "expected the CSV download to have created a temp dir"
    assert not Path(created_dirs[0]).exists()


def test_looks_like_a_different_host_true_on_sso_redirect():
    """The exact failure mode hit live once already: an expired session
    getting redirected from the Salesforce app to WGU's SSO login page."""
    assert _looks_like_a_different_host(
        "https://srm.lightning.force.com/lightning/n/Caseload_App_Page",
        "https://access.wgu.edu/pingfed/idp/SSO.saml2",
    ) is True


def test_looks_like_a_different_host_false_when_staying_on_the_same_host():
    assert _looks_like_a_different_host(
        "https://srm.lightning.force.com/lightning/n/Caseload_App_Page",
        "https://srm.lightning.force.com/lightning/n/Caseload_App_Page?overrideNavRules=true",
    ) is False


# --- CachingStudentDataProvider ---------------------------------------------

class _ScriptedProvider(StudentDataProvider):
    """A StudentDataProvider whose get_students() returns/raises whatever
    was scripted for that call number, so CachingStudentDataProvider's
    fetch-once/refresh/retry-after-failure behavior can be tested without a
    real (or fake-but-slow) underlying provider."""

    def __init__(self, scripted_results):
        self._scripted_results = list(scripted_results)
        self.call_count = 0

    def get_students(self):
        self.call_count += 1
        result = self._scripted_results[self.call_count - 1]
        if isinstance(result, Exception):
            raise result
        return result


def _student(sid: str, first: str, last: str) -> Student:
    return Student(salesforce_id=sid, first_name=first, last_name=last, email=f"{first}@example.test")


def test_caching_provider_fetches_once_and_reuses_the_cache():
    jane = _student("SF1", "Jane", "Doe")
    real = _ScriptedProvider([[jane]])
    provider = CachingStudentDataProvider(real)

    first = provider.get_students()
    second = provider.get_students()

    assert first == [jane]
    assert second == [jane]
    assert real.call_count == 1


def test_caching_provider_refresh_forces_a_new_fetch():
    jane = _student("SF1", "Jane", "Doe")
    john = _student("SF2", "John", "Roe")
    real = _ScriptedProvider([[jane], [jane, john]])
    provider = CachingStudentDataProvider(real)
    provider.get_students()

    refreshed = provider.refresh()

    assert refreshed == [jane, john]
    assert provider.get_students() == [jane, john]
    assert real.call_count == 2


def test_caching_provider_a_failed_fetch_leaves_cache_empty_so_the_next_call_retries():
    jane = _student("SF1", "Jane", "Doe")
    real = _ScriptedProvider([RuntimeError("session expired"), [jane]])
    provider = CachingStudentDataProvider(real)

    with pytest.raises(RuntimeError, match="session expired"):
        provider.get_students()

    # NOT permanently stuck on failure - the next call retries rather than
    # caching an error state or an empty list.
    assert provider.get_students() == [jane]
    assert real.call_count == 2


def test_caching_provider_a_failed_refresh_does_not_clobber_a_good_cache():
    jane = _student("SF1", "Jane", "Doe")
    real = _ScriptedProvider([[jane], RuntimeError("session expired")])
    provider = CachingStudentDataProvider(real)
    provider.get_students()  # populates the cache with [jane]

    with pytest.raises(RuntimeError, match="session expired"):
        provider.refresh()

    # A failed manual "Refresh Caseload" click shouldn't wipe out an
    # already-good roster - the professor can keep working with what's
    # cached until a retry succeeds.
    assert provider.get_students() == [jane]
    assert real.call_count == 2
