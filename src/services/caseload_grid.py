# src/services/caseload_grid.py
"""Reads each student's Salesforce Contact Id from the Caseload page's own
grid data, so texting can find students in Mongoose exactly.

Mongoose's recipient search ("Search by First, Last, ID, or Mobile") matches
the Salesforce Contact Id ("003...") - not the WGU student ID, which is why
searching by student ID never worked. The roster CSV export doesn't include
the Contact Id, but the Caseload page fetches it anyway: on load it calls the
Aura action `getCaseLoadMainGridData`, whose JSON response lists every row
with StudentID, CourseCode, contactID and CaseloadTotalRows. GridCapture
listens for those responses while PlaywrightStudentDataProvider loads the
page. Approach taken from the reference project (ashejim/caseload-tool,
browser_worker.py `_capture_grid_data`).

Confirmed live 2026-10-28 (counts only): one page load fired the action three
times by itself (100 + 100 + 69 rows), covering all 269 students, every one
with a Contact Id - including 166 rows for one course. CaseloadTotalRows is
the page's own total, so a load that stopped early can be noticed.

Kept in memory only, like the rest of the roster (FERPA).
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

GRID_ACTION_NAME = "getCaseLoadMainGridData"


def rows_from_grid_response(body: str) -> List[dict]:
    """The row dicts from one getCaseLoadMainGridData response body (an Aura
    envelope: {"actions": [{"state": "SUCCESS", "returnValue": [rows...]}]}).
    Anything unreadable gives []."""
    try:
        envelope = json.loads(body)
    except ValueError:
        return []
    rows: List[dict] = []
    for action in envelope.get("actions") or [] if isinstance(envelope, dict) else []:
        value = action.get("returnValue") if isinstance(action, dict) else None
        if action.get("state") == "SUCCESS" and isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    return rows


class GridCapture:
    """Collects grid rows from page responses. Rows are keyed by (StudentID,
    CourseCode), so a chunk seen twice isn't counted twice."""

    def __init__(self):
        self.rows_by_key: Dict[tuple, dict] = {}
        self.expected_total: Optional[int] = None

    def on_response(self, response) -> None:
        """Playwright context "response" handler. Never raises: a listener
        error must not break the roster load itself."""
        try:
            if GRID_ACTION_NAME not in response.url:
                return
            self.add_rows(rows_from_grid_response(response.text()))
        except Exception:
            pass

    def add_rows(self, rows: List[dict]) -> None:
        for row in rows:
            student_id = str(row.get("StudentID") or "").strip()
            if not student_id:
                continue
            self.rows_by_key[(student_id, str(row.get("CourseCode") or "").strip())] = row
            try:
                self.expected_total = int(row.get("CaseloadTotalRows"))
            except (TypeError, ValueError):
                pass

    @property
    def is_complete(self) -> bool:
        return self.expected_total is not None and len(self.rows_by_key) >= self.expected_total

    def wait_until_complete(self, page, timeout_ms: int) -> None:
        """Gives the page's remaining chunks time to arrive. Returns early once
        CaseloadTotalRows rows are in; otherwise gives up after timeout_ms."""
        waited = 0
        while not self.is_complete and waited < timeout_ms:
            page.wait_for_timeout(250)
            waited += 250

    def contact_ids_by_student_id(self) -> Dict[str, str]:
        result = {}
        for (student_id, _course), row in self.rows_by_key.items():
            contact_id = str(row.get("contactID") or "").strip()
            if contact_id.startswith("003"):
                result[student_id] = contact_id
        return result


@dataclass
class ContactIdReport:
    """What a roster load found out about texting IDs, for the log."""
    students: int
    with_contact_id: int
    grid_rows: int
    expected_grid_rows: Optional[int]
    missing_names: List[str] = field(default_factory=list)

    @property
    def grid_incomplete(self) -> bool:
        return self.expected_grid_rows is None or self.grid_rows < self.expected_grid_rows

    def log_lines(self) -> List[str]:
        lines = [f"Texting IDs found for {self.with_contact_id} of {self.students} students"]
        if self.grid_incomplete:
            expected = "an unknown number of" if self.expected_grid_rows is None else str(self.expected_grid_rows)
            lines.append(
                f"[TEXTING IDS INCOMPLETE] The Caseload page sent {self.grid_rows} of {expected} rows - "
                "click Refresh Caseload before texting"
            )
        if self.missing_names:
            lines.append("No texting ID (texts to them will be skipped): " + ", ".join(self.missing_names))
        return lines


def apply_contact_ids(students, grid: GridCapture) -> ContactIdReport:
    """Sets each student's texting_contact_id from the captured grid (by
    student ID) and reports how complete that was."""
    contact_ids = grid.contact_ids_by_student_id()
    missing = []
    for student in students:
        student.texting_contact_id = contact_ids.get(student.salesforce_id, "")
        if not student.texting_contact_id:
            missing.append(student.full_name)
    return ContactIdReport(
        students=len(students),
        with_contact_id=len(students) - len(missing),
        grid_rows=len(grid.rows_by_key),
        expected_grid_rows=grid.expected_total,
        missing_names=sorted(set(missing)),
    )
