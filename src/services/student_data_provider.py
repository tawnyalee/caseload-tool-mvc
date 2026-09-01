# src/services/student_data_provider.py
"""Abstract source of student roster data, plus a local fake implementation.

Real adapters (Salesforce, Cadence) and the fake one both conform to
StudentDataProvider, so the rest of the app never depends on which is behind
it — swapping data sources later means writing a new class here, not
touching anything that calls get_students().

Filtering is intentionally NOT part of this yet — that's a separate, not-
yet-designed concern (field-type-aware operators, AND/OR grouping) that will
layer on top once it's been worked out. get_students() just returns
everything available from the source.
"""
import json
import tempfile
from abc import ABC, abstractmethod
from dataclasses import fields
from pathlib import Path
from typing import List

from src.models.student import Student
from src.services.csv_student_import import parse_students_csv
from src.services.salesforce_browser_session import open_authenticated_context
from src.services.task_utils import get_latest_task_number

_STUDENT_FIELD_NAMES = {f.name for f in fields(Student)}


class StudentDataProvider(ABC):
    @abstractmethod
    def get_students(self) -> List[Student]:
        """Returns every student currently available from this data source."""
        raise NotImplementedError


class FakeStudentDataProvider(StudentDataProvider):
    """Loads students from a local, hand-editable JSON fixture — lets the app
    be built and tested end-to-end without touching real student data."""

    def __init__(self, file_path: str = "data/fake_students.json"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._save_raw([])

    def _save_raw(self, data: List[dict]) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def get_students(self) -> List[Student]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

        students = [
            Student(**{k: v for k, v in item.items() if k in _STUDENT_FIELD_NAMES})
            for item in raw_data
        ]
        for student in students:
            student.latest_task_number = get_latest_task_number(student)
        return students


class CsvStudentDataProvider(StudentDataProvider):
    """Reads the roster from a Salesforce report-export CSV instead of the
    real API - a hedge adapter for when live API access isn't available
    (see src/CLAUDE.md's integration plan). Re-reads csv_path fresh on
    every get_students() call rather than caching, so replacing the file
    (a fresh manual export, or a scheduled Data Loader job) is picked up
    without restarting the app.

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

    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)

    def get_students(self) -> List[Student]:
        return parse_students_csv(self.csv_path)


class PlaywrightStudentDataProvider(StudentDataProvider):
    """Reads the roster by driving a real, already-authenticated browser
    (see salesforce_browser_session.py - requires a session saved via
    scripts/salesforce_login.py first) to a report/export page and
    downloading its CSV, then parsing it exactly like
    CsvStudentDataProvider does. The browser-automation step is the only
    difference from the CSV hedge - it replaces a manual export with an
    automated one, feeding the same parser either way.

    `report_url` and `export_button_selector` are Salesforce-specific and
    deliberately passed in rather than hardcoded, so switching to a
    different target later (e.g. the in-house Learner360 caseload app at
    learner360.wgu.edu, if that ends up being what's actually automated
    against) is just different constructor arguments, not a rewrite -
    same platform-independence principle as the StudentDataProvider
    interface itself. Find the real selector for your org by running
    `python -m playwright codegen <report_url>` and recording yourself
    clicking Export - copy the resulting selector in here."""

    def __init__(self, report_url: str, export_button_selector: str, headless: bool = True):
        self.report_url = report_url
        self.export_button_selector = export_button_selector
        self.headless = headless

    def get_students(self) -> List[Student]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            context = open_authenticated_context(playwright, headless=self.headless)
            try:
                page = context.new_page()
                page.goto(self.report_url)
                with page.expect_download() as download_info:
                    page.click(self.export_button_selector)
                download = download_info.value

                csv_path = Path(tempfile.mkdtemp()) / download.suggested_filename
                download.save_as(str(csv_path))
            finally:
                context.browser.close()

        return parse_students_csv(csv_path)
