# scripts/test_student_data_provider_live.py
"""One-off, run-by-hand tool: exercises PlaywrightStudentDataProvider
against the actual org, non-headless so you can watch it happen. Read-only -
downloads and parses the roster export, writes nothing to Salesforce.

report_url/export_button_selector below are a first guess, not yet
confirmed: EXPORT_BUTTON_SELECTOR was captured incidentally while recording
write_note_fn/update_follow_up_fn (the same Caseload App Page has a Download
button), but the export flow itself has never been run end-to-end. If this
fails, the printed error is the starting point for a fresh codegen recording
of the real Export action - same process that resolved every note-writing
selector issue (see src/CLAUDE.md).

Deliberately does NOT print any real student PII beyond counts and a
redacted sample - the exported CSV can carry the entire roster's names/
emails/phones, unlike test_note_writer_live's single-student scope.

Requires a saved session (run scripts/salesforce_login.py first if
data/.salesforce_session.json doesn't exist or has expired).

    python scripts/test_student_data_provider_live.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.salesforce_callbacks import CASELOAD_APP_URL, EXPORT_BUTTON_SELECTOR
from src.services.student_data_provider import PlaywrightStudentDataProvider


def main() -> None:
    provider = PlaywrightStudentDataProvider(
        report_url=CASELOAD_APP_URL,
        export_button_selector=EXPORT_BUTTON_SELECTOR,
        headless=False,
    )

    print(f"Fetching roster export from {CASELOAD_APP_URL} ...")
    students = provider.get_students()

    print(f"Loaded {len(students)} students.")
    if students:
        first = students[0]
        print(
            "First row sanity check - "
            f"salesforce_id starts with: {first.salesforce_id[:4]!r}..., "
            f"course_code={first.course_code!r}, "
            f"has_email={bool(first.email)}, has_phone={bool(first.phone)}, "
            f"has_name={bool(first.first_name or first.last_name)}"
        )
        with_email = sum(1 for s in students if s.email)
        with_phone = sum(1 for s in students if s.phone)
        with_course = sum(1 for s in students if s.course_code)
        print(f"Coverage - email: {with_email}/{len(students)}, "
              f"phone: {with_phone}/{len(students)}, course_code: {with_course}/{len(students)}")
    else:
        print("No students parsed - check the downloaded CSV's shape/headers "
              "(the export may have worked but the column names don't match "
              "Student.SALESFORCE_FIELD_MAP, or the click didn't trigger a real export).")


if __name__ == "__main__":
    main()
