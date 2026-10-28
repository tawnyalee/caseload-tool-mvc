# scripts/test_text_sender_live.py
"""One-off, run-by-hand dry run of src/services/mongoose_compose.py against
real Mongoose, in a visible window so you can watch every step.

By default it fills in a whole scheduled text - department, recipient,
message, Message Name, date and time - and STOPS before the final Schedule
click. Nothing is sent or scheduled. Look it over, cancel it in Mongoose,
then close the window to end the script.

Uses the app's saved Edge profile (log in yourself if Mongoose asks), and
clears Mongoose's cached pages from it when you close the window.

    python scripts/test_text_sender_live.py <contact id> <course code>
    python scripts/test_text_sender_live.py <contact id> <course code> --schedule

The contact id is the student's Salesforce Contact Id ("003..."). --schedule
really schedules it (only after a dry run looked right).
"""
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.browser_launch import clear_cached_pages, launch_login_context
from src.services.mongoose_browser_session import MONGOOSE_URL
from src.services.mongoose_compose import LOGGED_IN_SELECTOR, ScheduledText, compose_scheduled_text


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    contact_id, course_code = sys.argv[1], sys.argv[2]
    commit = "--schedule" in sys.argv[3:]

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        context = launch_login_context(playwright, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(MONGOOSE_URL)
            print("Log in to Mongoose in the window if it asks...")
            page.wait_for_selector(LOGGED_IN_SELECTOR, state="visible", timeout=5 * 60 * 1000)
            label = page.locator(".timezone-label").first
            if label.count():
                print("Mongoose's time zone label:", label.inner_text().strip())

            tomorrow_10am = datetime.combine(datetime.now().date() + timedelta(days=1), time(10, 0))
            text = ScheduledText(
                course_code=course_code,
                contact_id=contact_id,
                body="Test from the Caseload tool - please ignore.",
                message_name="Caseload tool test",
                send_at=tomorrow_10am,
            )
            compose_scheduled_text(page, text, commit=commit, say=print)
            print("Check the window. Cancel the text in Mongoose, then close the window.")
            page.wait_for_event("close", timeout=0)
        except Exception as exc:
            print(f"\nSTOPPED: {type(exc).__name__}: {exc}")
            print("Leave the window as it is and tell Claude what it shows; close it when done.")
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass
        finally:
            try:
                scratch = context.new_page()
                clear_cached_pages(context, MONGOOSE_URL)
                scratch.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
