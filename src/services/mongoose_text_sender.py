# src/services/mongoose_text_sender.py
"""The app's real TextSender: schedules each text in Mongoose.

One browser window per run (ensure_ready opens it, finish closes it), on the
app's saved Edge profile, so Mongoose recognizes the device and the professor
only logs in when Mongoose asks. It stays visible on purpose. Driving it all
happens on the BackgroundWorker thread, since Playwright's sync API must stay
on the thread that started it.

Per student (mongoose_compose.py does the clicking): the student's course
department, found by Salesforce Contact Id, scheduled for the next 10 AM-8 PM
slot in the student's own time zone (text_scheduling.py). A student with no
Contact Id, no time zone, or no match in that department is SKIPPED and
listed, never guessed at.

Three modes:
  - DRY_RUN (test mode): fill everything in, then throw it away. Nothing is
    scheduled - the texting version of test mode's email redirect.
  - REVIEW (live, for now): fill it in, then wait for the professor to click
    Schedule or Cancel in the window themselves.
  - AUTOMATIC: click Schedule. Only once the professor decides to trust it.
"""
from datetime import datetime
from typing import Optional

from src.models.student import Student
from src.services.browser_launch import clear_cached_pages, launch_login_context
from src.services.mongoose_browser_session import MONGOOSE_URL
from src.services.mongoose_compose import (
    LOGGED_IN_SELECTOR, NoMongooseMatch, ScheduledText, compose_scheduled_text,
)
from src.services.text_scheduling import NoTimeZoneError, next_send_time
from src.services.text_sender import TextSender, TextSkipped

DRY_RUN = "dry_run"
REVIEW = "review"
AUTOMATIC = "automatic"

LOGIN_TIMEOUT_MS = 5 * 60 * 1000
REVIEW_TIMEOUT_MS = 10 * 60 * 1000


def mongoose_entry_time(student_time: datetime) -> datetime:
    """The time to type into Mongoose's scheduler for a send at
    `student_time`. Assumed (2026-10-28, not yet confirmed) to be this
    computer's own time zone, since Mongoose's Schedule screen names none.
    Mongoose separately warns when a time is too early for the student. If
    the first real scheduled text shows otherwise, this is the one place to
    change."""
    return student_time.astimezone()


def describe_time(moment: datetime) -> str:
    return moment.strftime("%a %m/%d %I:%M %p %Z").replace(" 0", " ")


class MongooseTextSender(TextSender):
    def __init__(self, mode: str = REVIEW):
        if mode not in (DRY_RUN, REVIEW, AUTOMATIC):
            raise ValueError(f"Unknown texting mode: {mode}")
        self.mode = mode
        self._playwright = None
        self._context = None
        self._page = None

    def ensure_ready(self) -> None:
        if self._page is not None:
            return
        from playwright.sync_api import Error as PlaywrightError, sync_playwright

        self._playwright = sync_playwright().start()
        try:
            self._context = launch_login_context(self._playwright, headless=False)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._go_home()
        except PlaywrightError:
            self.finish()
            raise RuntimeError("Mongoose couldn't be opened, or its window was closed before login finished.") from None
        except Exception:
            self.finish()
            raise

    def _go_home(self) -> None:
        """Mongoose's start page, waiting (up to 5 minutes) for the professor
        to log in if it asks. Also how each text starts from a clean page."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        self._page.goto(MONGOOSE_URL)
        try:
            self._page.wait_for_selector(LOGGED_IN_SELECTOR, state="visible", timeout=LOGIN_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            raise RuntimeError("Mongoose login wasn't finished within 5 minutes - no texts were sent.") from None

    def send(self, student: Student, body: str, message_name: str) -> str:
        if not student.texting_contact_id:
            raise TextSkipped("No texting ID for this student (click Refresh Caseload, then try again)")
        if not student.course_code:
            raise TextSkipped("No course code, so no Mongoose department to text from")
        try:
            student_time = next_send_time(student.timezone)
        except NoTimeZoneError:
            raise TextSkipped(f"No usable time zone ({student.timezone or 'blank'}) - text them by hand") from None
        entry_time = mongoose_entry_time(student_time)

        self.ensure_ready()
        self._go_home()
        text = ScheduledText(
            course_code=student.course_code,
            contact_id=student.texting_contact_id,
            body=body,
            message_name=message_name,
            send_at=entry_time,
        )
        try:
            compose_scheduled_text(self._page, text, commit=self.mode == AUTOMATIC)
        except NoMongooseMatch as exc:
            raise TextSkipped(f"{exc} ({student.course_code})") from None

        when = f"{describe_time(student_time)} student time"
        if self.mode == DRY_RUN:
            return f"TEST MODE - filled in for {when}, not scheduled"
        if self.mode == REVIEW:
            self._wait_for_review()
            return f"Filled in for {when}; you clicked Schedule or Cancel in Mongoose"
        return f"Scheduled for {when}"

    def _wait_for_review(self) -> None:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        try:
            self._page.get_by_role("textbox", name="Message Name").wait_for(
                state="hidden", timeout=REVIEW_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            raise RuntimeError("Nobody clicked Schedule or Cancel within 10 minutes - not scheduled") from None

    def finish(self) -> None:
        """Clears Mongoose's cached pages from the profile, then closes the
        window. Never raises: it runs after every texting run, even a failed one."""
        if self._context is not None:
            try:
                clear_cached_pages(self._context, MONGOOSE_URL)
            except Exception:
                pass
            try:
                self._context.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._playwright = self._context = self._page = None
