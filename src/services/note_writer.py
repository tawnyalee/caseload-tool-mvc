# src/services/note_writer.py
"""Abstract note-writing against a student's CRM record, plus a local fake
that records what would have been written, and a Playwright-based real
adapter for when API access isn't available (see
src/services/salesforce_browser_session.py and src/CLAUDE.md's
integration plan).
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, List, Optional, Set

from src.services.browser_launch import acquire_playwright, playwright_session, release_playwright
from src.services.salesforce_browser_session import (
    EXPIRED_MESSAGE,
    SessionExpiredError,
    looks_like_a_different_host,
    open_authenticated_context,
)
from src.services.salesforce_direct_save import AuraCredentials, DirectSaveFailed, save_follow_up, save_note

if TYPE_CHECKING:
    from playwright.sync_api import Page

# How long any one click, field or page load may take, up from Playwright's
# 30 seconds: Salesforce can be very slow, and a note must not fail for that
# (developer, 2026-11-01).
NOTE_STEP_TIMEOUT_MS = 2 * 60 * 1000
# How long a loaded page gets to make the request that direct saves read their
# credentials from.
CREDENTIALS_WAIT_CHECKS = 120  # 30 seconds, at 250 ms each


class NoteWriter(ABC):
    @abstractmethod
    def write_note(self, salesforce_id: str, subject: str, body: str, course_code: str = "") -> None:
        """Writes a note against a student's record. Raises an exception if it fails."""
        raise NotImplementedError

    @abstractmethod
    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        """Overwrites the short follow-up-note field on a student's roster record
        (e.g. 'Sent welcome email'). Raises an exception if it fails."""
        raise NotImplementedError

    def start_run(self) -> None:
        """Called before a run's notes, so a writer can share one connection
        across them. finish_run() always follows."""

    def finish_run(self) -> None:
        """Called after a run's notes. Must not raise."""

    def close(self) -> None:
        """Ends any connection kept between runs. Must not raise."""

    def describe_written(self, student_name: str) -> str:
        """The log wording for a successful note step. Test mode overrides
        it, since nothing reaches Salesforce."""
        return f"Written for {student_name}"


class FakeNoteWriter(NoteWriter):
    """Records every write_note()/update_follow_up_note() call instead of touching
    Salesforce. `fail_for` lets tests/dev simulate specific students failing,
    deterministically, for either operation."""

    def __init__(self, fail_for: Optional[Set[str]] = None):
        self.fail_for = fail_for or set()
        self.written: List[dict] = []
        self.follow_up_notes: dict = {}  # salesforce_id -> latest text

    def write_note(self, salesforce_id: str, subject: str, body: str, course_code: str = "") -> None:
        if salesforce_id in self.fail_for:
            raise RuntimeError(f"Simulated note-write failure for {salesforce_id}")
        self.written.append({
            "salesforce_id": salesforce_id, "subject": subject, "body": body, "course_code": course_code,
        })

    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        if salesforce_id in self.fail_for:
            raise RuntimeError(f"Simulated follow-up-note update failure for {salesforce_id}")
        self.follow_up_notes[salesforce_id] = text


class PlaywrightNoteWriter(NoteWriter):
    """Writes notes and updates the follow-up-note field by driving a
    real, already-authenticated browser (see salesforce_browser_session.py
    - requires logging in first, which the app does at startup) to
    a student's record page and simulating the same clicks/typing a
    person would do - confirmed there's no faster path for this org
    (see src/CLAUDE.md's integration plan).

    The exact interaction (which button opens a note form, which field
    is which, whether the follow-up field is inline-editable or needs a
    separate edit step) depends entirely on the target org's real page
    layout, which isn't known yet. Rather than guess wrong selectors, the
    actual click/fill sequence is supplied as callbacks -
    `write_note_fn(page, salesforce_id, subject, body, course_code)` and
    `update_follow_up_fn(page, salesforce_id, text)` - so this class only
    owns what's reusable (opening the authenticated session, navigating
    to the record, cleaning up the browser) and the site-specific part
    gets written once the real page is visible, e.g. via
    `python -m playwright codegen <a real student record URL>`, recording
    the note-entry flow, and turning that recording into a callback.

    Same swap-later principle as PlaywrightStudentDataProvider: a
    different target later (e.g. the in-house Learner360 caseload app at
    learner360.wgu.edu, if that ends up being what's actually automated
    against instead of raw Salesforce) is a different pair of callbacks
    and a different student_record_url_template, not a rewrite of this
    class or anything that calls NoteWriter."""

    def __init__(
        self,
        student_record_url_template: str,
        write_note_fn: "Callable[[Page, str, str, str, str], None]",
        update_follow_up_fn: "Callable[[Page, str, str], None]",
        headless: bool = True,
        find_students: Optional[Callable[[str], list]] = None,
        log: Optional[Callable[[str], None]] = None,
    ):
        """`find_students(salesforce_id)` gives that ID's roster rows, which
        hold what a direct save needs. Without it, every note uses the form."""
        self.student_record_url_template = student_record_url_template
        self.write_note_fn = write_note_fn
        self.update_follow_up_fn = update_follow_up_fn
        self.headless = headless
        self.find_students = find_students
        self.log = log or (lambda message: None)
        self._aura = AuraCredentials()
        self._note_course = {}  # salesforce_id -> the course its note just used
        self._how_saved = []  # "direct"/"form" per step, for the log
        self._in_run = False
        self._playwright = None
        self._context = None
        self._page = None
        self._reload_before_next_note = False
        self._page_student = None

    def start_run(self) -> None:
        """Every note and follow-up shares one hidden browser for the whole
        app session, until close() (Refresh Caseload, or the app closing).
        Opening a browser and loading the Caseload page twice per student
        was most of a run's time (developer, 2026-10-31). Opened on the first
        note, on the background thread, which must also close it: Playwright's
        sync API stays on one thread. A page left sitting between runs may
        have timed out, so each run's first note reloads it once.

        Each new student also gets a freshly loaded page. Reusing it failed
        about every second note in a live run (2026-10-31): the previous
        student's note form was likely still there, hidden, and the clicks
        landed on it. One student's note and follow-up do share a page.

        Notes and follow-ups try a direct save first (salesforce_direct_save.py),
        which needs the page loaded once but no reload per student and no form.
        Anything but a clear success falls back to the form (developer,
        2026-11-02), so a Salesforce change costs speed, not the note."""
        self._in_run = True
        self._reload_before_next_note = self._page is not None

    def finish_run(self) -> None:
        self._in_run = False

    def close(self) -> None:
        self._close_shared_page()

    def _close_shared_page(self) -> None:
        if self._context is not None:
            try:
                self._context.browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                release_playwright()
            except Exception:
                pass
        self._playwright = self._context = self._page = self._page_student = None
        self._aura = AuraCredentials()

    def _open_shared_page(self, salesforce_id: str, for_the_form: bool = True) -> "Page":
        """`for_the_form` False is a direct save: it doesn't touch the page's
        form, so a new student needs no reload."""
        url = self.student_record_url_template.format(salesforce_id=salesforce_id)
        new_student = for_the_form and salesforce_id != self._page_student
        if self._page is not None and (self._reload_before_next_note or new_student):
            self._reload_before_next_note = False
            try:
                self._go_to(url)
            except SessionExpiredError:
                raise
            except Exception:
                self._close_shared_page()  # the browser died while idle: start over
        if self._page is None:
            self._playwright = acquire_playwright()
            self._context = open_authenticated_context(self._playwright, headless=self.headless)
            self._context.set_default_timeout(NOTE_STEP_TIMEOUT_MS)
            self._context.on("request", self._aura.on_request)
            self._page = self._context.new_page()
            self._go_to(url)
        if for_the_form:
            self._page_student = salesforce_id
        return self._page

    def _go_to(self, url: str) -> None:
        self._page.goto(url)
        if looks_like_a_different_host(url, self._page.url):
            raise SessionExpiredError(EXPIRED_MESSAGE)

    def _run_on_shared_page(self, salesforce_id: str, action: "Callable[[Page], None]") -> None:
        """After any failure the page's state is unknown, so the next note
        starts over on a new browser and a freshly loaded page."""
        try:
            action(self._open_shared_page(salesforce_id))
        except Exception:
            self._close_shared_page()
            raise

    def write_note(self, salesforce_id: str, subject: str, body: str, course_code: str = "") -> None:
        self._note_course[salesforce_id] = course_code
        contact_id = next((s.texting_contact_id for s in self._roster_rows(salesforce_id) if s.texting_contact_id), "")
        if contact_id and course_code and self._saved_directly(
            salesforce_id, lambda page: save_note(page, self._aura, contact_id, course_code, subject, body)
        ):
            return
        self._run(salesforce_id, lambda page: self.write_note_fn(page, salesforce_id, subject, body, course_code))
        self._how_saved.append("form")

    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        record_id = self._course_record_id(salesforce_id)
        if record_id and self._saved_directly(
            salesforce_id, lambda page: save_follow_up(page, self._aura, record_id, text)
        ):
            return
        self._run(salesforce_id, lambda page: self.update_follow_up_fn(page, salesforce_id, text))
        self._how_saved.append("form")

    def describe_written(self, student_name: str) -> str:
        how, self._how_saved = " then ".join(self._how_saved), []
        return f"Written for {student_name} ({how})" if how else f"Written for {student_name}"

    def _roster_rows(self, salesforce_id: str) -> list:
        if self.find_students is None or not self._in_run:
            return []
        try:
            return list(self.find_students(salesforce_id))
        except Exception:
            return []

    def _course_record_id(self, salesforce_id: str) -> str:
        """The record for the course the student's note just used. With no
        note, only a student with a single course: never guess between two."""
        rows = self._roster_rows(salesforce_id)
        course = self._note_course.get(salesforce_id, "").strip().upper()
        if course:
            rows = [s for s in rows if s.course_code.strip().upper() == course]
        return rows[0].course_record_id if len(rows) == 1 else ""

    def _saved_directly(self, salesforce_id: str, save: "Callable[[Page], None]") -> bool:
        """False means the form should be used instead. An expired login is
        the one thing it doesn't hide, since the form couldn't work either."""
        try:
            page = self._open_shared_page(salesforce_id, for_the_form=False)
            self._wait_for_credentials(page)
            save(page)
        except SessionExpiredError:
            raise
        except Exception as exc:
            self.log(f"[NOTE] Direct save didn't work, using the form: {exc}")
            return False
        self._how_saved.append("direct")
        return True

    def _wait_for_credentials(self, page: "Page") -> None:
        for _ in range(CREDENTIALS_WAIT_CHECKS):
            if self._aura.ready:
                return
            page.wait_for_timeout(250)
        raise DirectSaveFailed("the page never made a request to read its credentials from")

    def _run(self, salesforce_id: str, action: "Callable[[Page], None]") -> None:
        if self._in_run:
            self._run_on_shared_page(salesforce_id, action)
            return

        with playwright_session() as playwright:
            context = open_authenticated_context(playwright, headless=self.headless)
            context.set_default_timeout(NOTE_STEP_TIMEOUT_MS)
            try:
                page = context.new_page()
                url = self.student_record_url_template.format(salesforce_id=salesforce_id)
                page.goto(url)
                if looks_like_a_different_host(url, page.url):
                    raise SessionExpiredError(EXPIRED_MESSAGE)
                action(page)
            finally:
                context.browser.close()
