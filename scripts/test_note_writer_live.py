# scripts/test_note_writer_live.py
"""One-off, run-by-hand tool: exercises PlaywrightNoteWriter's real
write_note_fn/update_follow_up_fn against the actual org, non-headless so
you can watch it happen and check the result in Salesforce afterward.
This writes real data - only run it against a student you're fine
touching (defaults to the same test student used while capturing these
selectors).

Requires a saved session (run scripts/salesforce_login.py first if
data/.salesforce_session.json doesn't exist or has expired).

Run manually - by default runs both the note and the follow-up update;
pass "note" or "followup" to run just one (much faster to iterate on
the follow-up piece alone without also writing a note each time):

    python scripts/test_note_writer_live.py
    python scripts/test_note_writer_live.py followup
    python scripts/test_note_writer_live.py note
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.note_writer import PlaywrightNoteWriter
from src.services.salesforce_callbacks import CASELOAD_APP_URL, update_follow_up_fn, write_note_fn

TEST_STUDENT_ID = "011730370"


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "both"

    writer = PlaywrightNoteWriter(
        student_record_url_template=CASELOAD_APP_URL,
        write_note_fn=write_note_fn,
        update_follow_up_fn=update_follow_up_fn,
        headless=False,
    )

    if which in ("both", "note"):
        print(f"Writing a test note for student {TEST_STUDENT_ID}...")
        writer.write_note(
            salesforce_id=TEST_STUDENT_ID,
            subject="Automated test note",
            body="Verifying PlaywrightNoteWriter.write_note()",
            course_code="D413",
        )
        print("Done - check the student's record in Salesforce.")

    if which in ("both", "followup"):
        print(f"Updating follow-up note for student {TEST_STUDENT_ID}...")
        writer.update_follow_up_note(TEST_STUDENT_ID, "Automated follow-up test")
        print("Done - check the roster's follow-up column.")


if __name__ == "__main__":
    main()
