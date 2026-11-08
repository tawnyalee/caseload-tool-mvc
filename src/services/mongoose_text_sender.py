# src/services/mongoose_text_sender.py
"""The app's real TextSender: schedules each text in Mongoose.

One browser window for the whole app session (ensure_ready opens it, close
ends it on Refresh Caseload or when the app closes), on the app's saved Edge
profile, so the professor only logs in when Mongoose asks. It stays visible
on purpose. Driving it all
happens on the BackgroundWorker thread, since Playwright's sync API must stay
on the thread that started it.

One message per class (developer, 2026-11-08; mongoose_compose.py does the
clicking): the course's department, every recipient found by Salesforce
Contact Id, scheduled for the first time inside every recipient's own
10 AM-8 PM window (text_scheduling.shared_send_time). A student with no
Contact Id, no time zone, or no match in that department is SKIPPED and
listed, never guessed at.

Three modes:
  - DRY_RUN (test mode): fill everything in, then throw it away. Nothing is
    scheduled - the texting version of test mode's email redirect.
  - REVIEW: fill it in, then wait for the professor to click Schedule or
    Cancel in the window themselves. No longer used by the app; kept for
    the live test script.
  - AUTOMATIC (live, since 2026-11-08): click Schedule, then check that
    Mongoose closed the form.
"""
from datetime import datetime
from typing import Dict, List, Optional

from src.models.student import Student
from src.services.browser_launch import (
    acquire_playwright, clear_cached_pages, launch_login_context, release_playwright,
)
from src.services.mongoose_browser_session import MONGOOSE_URL
from src.services.mongoose_compose import (
    LOGGED_IN_SELECTOR, NoMongooseMatch, ScheduledText, compose_scheduled_text,
)
from src.services.text_scheduling import NoTimeZoneError, shared_send_time, student_zone
from src.services.text_sender import TextOutcome, TextSender, TextSkipped

DRY_RUN = "dry_run"
REVIEW = "review"
AUTOMATIC = "automatic"

LOGIN_TIMEOUT_MS = 5 * 60 * 1000
# Most students in one Mongoose message. Mongoose's own limit is unknown;
# a typical run is 20-30 students (developer, 2026-10-13).
MAX_RECIPIENTS = 25
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
    def __init__(self, mode: str = AUTOMATIC):
        if mode not in (DRY_RUN, REVIEW, AUTOMATIC):
            raise ValueError(f"Unknown texting mode: {mode}")
        self.mode = mode
        self._playwright = None
        self._context = None
        self._page = None

    def ensure_ready(self) -> None:
        if self._page is not None and not self._page.is_closed():
            return
        self.close()  # the professor may have closed the window between runs
        from playwright.sync_api import Error as PlaywrightError

        self._playwright = acquire_playwright()
        try:
            self._context = launch_login_context(self._playwright, headless=False)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._go_home()
        except PlaywrightError:
            self.close()
            raise RuntimeError("Mongoose couldn't be opened, or its window was closed before login finished.") from None
        except Exception:
            self.close()
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
        """One student: the same route as a message to a class of one."""
        outcome = self.send_group([student], body, message_name)[0]
        if outcome.outcome == "skipped":
            raise TextSkipped(outcome.detail)
        if outcome.outcome == "failed":
            raise RuntimeError(outcome.detail) from outcome.error
        return outcome.detail

    def send_group(self, students: List[Student], body: str, message_name: str) -> List[TextOutcome]:
        """One Mongoose message to every student here who can be placed
        (developer, 2026-11-08: one message per class). The caller groups
        them by course and wording. A student with no Contact Id, course or
        usable time zone, or not found in the department, is skipped and
        listed; the rest still get the text. Over MAX_RECIPIENTS, or when no
        one time suits everyone's zone, it's split into more messages."""
        outcomes: Dict[int, TextOutcome] = {}
        ready: List[int] = []
        for index, student in enumerate(students):
            problem = self._why_not_textable(student)
            if problem:
                outcomes[index] = TextOutcome(student, "skipped", problem)
            else:
                ready.append(index)
        for group in self._message_groups(ready, students):
            group_outcomes = self._schedule_one_message([students[i] for i in group], body, message_name)
            outcomes.update(zip(group, group_outcomes))
        return [outcomes[index] for index in range(len(students))]

    @staticmethod
    def _why_not_textable(student: Student) -> str:
        if not student.texting_contact_id:
            return "No texting ID for this student (click Refresh Caseload, then try again)"
        if not student.course_code:
            return "No course code, so no Mongoose department to text from"
        try:
            student_zone(student.timezone)
        except NoTimeZoneError:
            return f"No usable time zone ({student.timezone or 'blank'}) - text them by hand"
        return ""

    @staticmethod
    def _message_groups(indexes: List[int], students: List[Student]) -> List[List[int]]:
        """Positions of the students sharing each message: the same course,
        at most MAX_RECIPIENTS, and one time that suits every one of them
        (otherwise one message per time zone)."""
        by_course: Dict[str, List[int]] = {}
        for index in indexes:
            by_course.setdefault(students[index].course_code.strip().upper(), []).append(index)
        groups = []
        for course_indexes in by_course.values():
            try:
                shared_send_time([students[i].timezone for i in course_indexes])
                parts = [course_indexes]
            except ValueError:
                by_zone: Dict[str, List[int]] = {}
                for index in course_indexes:
                    by_zone.setdefault(students[index].timezone.strip().upper(), []).append(index)
                parts = list(by_zone.values())
            for part in parts:
                groups.extend(part[i:i + MAX_RECIPIENTS] for i in range(0, len(part), MAX_RECIPIENTS))
        return groups

    def _schedule_one_message(self, students: List[Student], body: str, message_name: str) -> List[TextOutcome]:
        send_at = shared_send_time([s.timezone for s in students])
        try:
            self.ensure_ready()
            self._go_home()
            text = ScheduledText(
                course_code=students[0].course_code,
                contact_ids=[s.texting_contact_id for s in students],
                body=body,
                message_name=message_name,
                send_at=mongoose_entry_time(send_at),
            )
            missing = set(compose_scheduled_text(self._page, text, commit=self.mode == AUTOMATIC))
            found = [s for s in students if s.texting_contact_id not in missing]
            if self.mode == REVIEW:
                self._wait_for_review(found[0])
        except NoMongooseMatch as exc:
            return [TextOutcome(s, "skipped", f"{exc} ({s.course_code})") for s in students]
        except Exception as exc:
            shot = self._screenshot("text-failed")
            return [TextOutcome(s, "failed", f"{exc} (screenshot: {shot})", exc) for s in students]

        together = f" (one message to {len(found)} students)" if len(found) > 1 else ""
        outcomes = []
        for student in students:
            if student.texting_contact_id in missing:
                outcomes.append(TextOutcome(student, "skipped", (
                    "Not found in this Mongoose department (they may have opted out of texts) "
                    f"({student.course_code})"
                )))
                continue
            when = f"{describe_time(send_at.astimezone(student_zone(student.timezone)))} student time"
            if self.mode == DRY_RUN:
                detail = f"TEST MODE - filled in for {when}{together}, not scheduled"
            elif self.mode == REVIEW:
                detail = f"Filled in for {when}{together}; you clicked Schedule or Cancel in Mongoose"
            else:
                detail = f"Scheduled for {when}{together}"
            outcomes.append(TextOutcome(student, "success", detail))
        return outcomes

    def _screenshot(self, tag: str) -> str:
        """Saves what the Mongoose window showed when a step failed, next to
        the Salesforce failure screenshots (kept one day, like the log).
        Best-effort: returns the path, or a note if it couldn't be taken."""
        from src.services import app_paths

        if self._page is None:
            return "not available"
        folder = app_paths.screenshots_dir()
        path = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{tag}.png"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self._page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return "not available"

    def _wait_for_review(self, student: Student) -> None:
        """Says plainly that it's the professor's turn. A window left behind
        others looked like a frozen run (developer, 2026-10-31)."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        self._page.bring_to_front()
        if self.on_waiting:
            self.on_waiting(
                f"Waiting for you: click Schedule or Cancel in the Mongoose window for {student.full_name}."
            )
        try:
            self._page.get_by_role("textbox", name="Message Name").wait_for(
                state="hidden", timeout=REVIEW_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            raise RuntimeError("Nobody clicked Schedule or Cancel within 10 minutes - not scheduled") from None

    def close(self) -> None:
        """Clears Mongoose's cached pages from the profile, keeping its
        sign-in, then closes the window. Called on Refresh Caseload and when
        the app closes, on the background thread. Never raises."""
        if self._context is not None:
            try:
                clear_cached_pages(self._context, MONGOOSE_URL, keep_local_storage=True)
            except Exception:
                pass
            try:
                self._context.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                release_playwright()
            except Exception:
                pass
        self._playwright = self._context = self._page = None
