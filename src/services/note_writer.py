# src/services/note_writer.py
"""Abstract note-writing against a student's CRM record, plus a local fake
that records what would have been written, and a Playwright-based real
adapter for when API access isn't available (see
src/services/salesforce_browser_session.py and src/CLAUDE.md's
integration plan).
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, List, Optional, Set

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

    def write_note(self, salesforce_id: str, subject: str, body: str, course_code: str = "") -> None:
        self._run(salesforce_id, lambda page: self.write_note_fn(page, salesforce_id, subject, body, course_code))

    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        self._run(salesforce_id, lambda page: self.update_follow_up_fn(page, salesforce_id, text))

    def _run(self, salesforce_id: str, action: "Callable[[Page], None]") -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
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
