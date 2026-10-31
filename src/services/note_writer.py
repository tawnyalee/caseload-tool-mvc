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

if TYPE_CHECKING:
    from playwright.sync_api import Page


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
    ):
        self.student_record_url_template = student_record_url_template
        self.write_note_fn = write_note_fn
        self.update_follow_up_fn = update_follow_up_fn
        self.headless = headless
        self._in_run = False
        self._playwright = None
        self._context = None
        self._page = None
        self._reload_before_next_note = False

    def start_run(self) -> None:
        """Every note and follow-up shares one hidden browser for the whole
        app session, until close() (Refresh Caseload, or the app closing).
        Opening a browser and loading the Caseload page twice per student
        was most of a run's time (developer, 2026-10-31). Opened on the first
        note, on the background thread, which must also close it: Playwright's
        sync API stays on one thread. A page left sitting between runs may
        have timed out, so each run's first note reloads it once."""
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
        self._playwright = self._context = self._page = None

    def _open_shared_page(self, salesforce_id: str) -> "Page":
        url = self.student_record_url_template.format(salesforce_id=salesforce_id)
        if self._page is not None and self._reload_before_next_note:
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
            self._page = self._context.new_page()
            self._go_to(url)
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
        self._run(salesforce_id, lambda page: self.write_note_fn(page, salesforce_id, subject, body, course_code))

    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        self._run(salesforce_id, lambda page: self.update_follow_up_fn(page, salesforce_id, text))

    def _run(self, salesforce_id: str, action: "Callable[[Page], None]") -> None:
        if self._in_run:
            self._run_on_shared_page(salesforce_id, action)
            return

        with playwright_session() as playwright:
            context = open_authenticated_context(playwright, headless=self.headless)
            try:
                page = context.new_page()
                url = self.student_record_url_template.format(salesforce_id=salesforce_id)
                page.goto(url)
                if looks_like_a_different_host(url, page.url):
                    raise SessionExpiredError(EXPIRED_MESSAGE)
                action(page)
            finally:
                context.browser.close()
