# src/services/essential_actions.py
"""Salesforce's Essential Actions list, for Send OA Emails (oa_emails.py).

Reading: the Essential Actions page loads its whole list with one Aura call,
`getEssentialActionRows` (MentorEventContainerController; its name is in the
request's descriptor). The page is opened in a hidden browser and that
response is read, the same way caseload_grid.py reads the roster grid.
Memory only (FERPA).

Saving the note and closing the Essential Action, the developer's two routes
(2026-11-04, both ship together):
  - direct (salesforce_direct_save.py): fetch the student's full EA records
    (getEssentialActions), then save the note with that EA in
    saveNoteAndCloseEAs, as the form does. Afterward the EA is fetched again
    and must show a completed date.
  - the form (essential_action_form.py): the clicks the developer recorded
    on the Essential Actions page, used when direct saves are off in
    Settings or a direct save fails before reaching Salesforce.

A direct save whose note went in but whose EA stayed open is NOT retried
through the form, which would file a second note: it's reported for the
professor to close by hand.
"""
from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from src.services.browser_launch import acquire_playwright, release_playwright
from src.services.oa_emails import EssentialActionRow, rows_from_ea_response
from src.services.salesforce_browser_session import (
    EXPIRED_MESSAGE, SessionExpiredError, looks_like_a_different_host, open_authenticated_context,
)
from src.services.salesforce_direct_save import (
    AuraCredentials, DirectSaveFailed, close_ea_record, get_essential_actions, is_closed, save_note,
)

ESSENTIAL_ACTIONS_URL = "https://srm.lightning.force.com/lightning/n/Essential_Actions"
EA_ROWS_ACTION = "getEssentialActionRows"
ROWS_WAIT_MS = 60_000
STEP_TIMEOUT_MS = 2 * 60 * 1000


class EaNotClosed(RuntimeError):
    """The note was saved but the Essential Action is still open."""


class EssentialActions(ABC):
    @abstractmethod
    def read_rows(self) -> List[dict]:
        """Every row of the Essential Actions list, as Salesforce sent it."""

    @abstractmethod
    def save_note_and_close(self, row: EssentialActionRow, subject: str, body: str) -> str:
        """Saves the note on the student with the Essential Action closed.
        Returns how, for the log. Raises on failure (EaNotClosed if only the
        close is missing)."""

    def close(self) -> None:
        """Ends any browser kept between steps. Must not raise."""


class FakeEssentialActions(EssentialActions):
    def __init__(self, rows: Optional[List[dict]] = None, fail_for: Optional[set] = None):
        self.rows = list(rows or [])
        self.fail_for = fail_for or set()
        self.closed: List[dict] = []

    def read_rows(self) -> List[dict]:
        return list(self.rows)

    def save_note_and_close(self, row: EssentialActionRow, subject: str, body: str) -> str:
        if row.ea_id in self.fail_for:
            raise RuntimeError(f"Simulated close failure for {row.ea_id}")
        self.closed.append({"ea_id": row.ea_id, "subject": subject, "body": body})
        return "Written and closed"


class TestModeEssentialActions(EssentialActions):
    """Test mode: reads the real list, writes nothing to Salesforce."""

    def __init__(self, real: EssentialActions):
        self.real = real

    def read_rows(self) -> List[dict]:
        return self.real.read_rows()

    def save_note_and_close(self, row: EssentialActionRow, subject: str, body: str) -> str:
        return "TEST MODE - note not written and Essential Action left open"

    def close(self) -> None:
        self.real.close()


class PlaywrightEssentialActions(EssentialActions):
    """One hidden browser on the Essential Actions page, opened by the first
    call and kept until close(). Runs on the BackgroundWorker thread, like
    every Playwright call in the app."""

    def __init__(
        self,
        use_direct_saves: Callable[[], bool] = lambda: True,
        log: Optional[Callable[[str], None]] = None,
        fill_form: Optional[Callable] = None,
        headless: bool = True,
    ):
        """`fill_form(page, row, subject, body)` is the recorded form route
        (essential_action_form.py)."""
        self.use_direct_saves = use_direct_saves
        self.log = log or (lambda message: None)
        self.fill_form = fill_form
        self.headless = headless
        self._playwright = None
        self._context = None
        self._page = None
        self._aura = None
        self._rows_bodies: List[str] = []

    def _on_response(self, response) -> None:
        """Never raises: a listener error must not break the page."""
        try:
            if "/aura" not in response.url:
                return
            if EA_ROWS_ACTION not in (response.request.post_data or ""):
                return
            self._rows_bodies.append(response.text())
        except Exception:
            pass

    def _open(self) -> None:
        if self._page is not None and not self._page.is_closed():
            return
        self.close()
        self._playwright = acquire_playwright()
        self._aura = AuraCredentials()
        self._context = open_authenticated_context(self._playwright, headless=self.headless)
        self._context.set_default_timeout(STEP_TIMEOUT_MS)
        self._context.on("request", self._aura.on_request)
        self._context.on("response", self._on_response)
        self._page = self._context.new_page()
        self._page.goto(ESSENTIAL_ACTIONS_URL)
        if looks_like_a_different_host(ESSENTIAL_ACTIONS_URL, self._page.url):
            self.close()
            raise SessionExpiredError(EXPIRED_MESSAGE)

    def _reload(self) -> None:
        self._page.goto(ESSENTIAL_ACTIONS_URL)
        if looks_like_a_different_host(ESSENTIAL_ACTIONS_URL, self._page.url):
            raise SessionExpiredError(EXPIRED_MESSAGE)

    def read_rows(self) -> List[dict]:
        """A fresh load each time, so the list is today's."""
        fresh = self._page is None
        self._open()
        if not fresh:
            self._rows_bodies = []
            self._reload()
        waited = 0
        while not self._rows_bodies and waited < ROWS_WAIT_MS:
            self._page.wait_for_timeout(250)
            waited += 250
        if not self._rows_bodies:
            raise RuntimeError("The Essential Actions page didn't send its list within a minute")
        self._page.wait_for_timeout(500)  # in case the page sends more than one
        rows: List[dict] = []
        for body in self._rows_bodies:
            rows.extend(rows_from_ea_response(body))
        return rows

    def save_note_and_close(self, row: EssentialActionRow, subject: str, body: str) -> str:

        self._open()
        if self.use_direct_saves():
            try:
                self._save_directly(row, subject, body)
                return "Written and closed (direct)"
            except (SessionExpiredError, EaNotClosed):
                raise
            except Exception as exc:
                self.log(f"[NOTE] Direct save didn't work, using the form: {exc}")
        if self.fill_form is None:
            raise RuntimeError("No form route is set up for closing Essential Actions")
        try:
            self._reload()
            self.fill_form(self._page, row, subject, body)
        except Exception:
            self.close()  # the page's state is unknown now
            raise
        if not self.use_direct_saves():
            return "Written and closed (form)"
        # The check reads Salesforce privately like a direct save, so only
        # when those are allowed. Here the form failed over from a direct save.
        try:
            closed = is_closed(get_essential_actions(self._page, self._aura, row.contact_id), row.ea_id)
        except Exception as exc:
            self.log(f"[NOTE] Couldn't check that the form closed the Essential Action: {exc}")
            return "Written and closed (form, close not checked)"
        if not closed:
            raise EaNotClosed("Note submitted through the form, but the Essential Action is still open - close it by hand")
        return "Written and closed (form)"

    def _save_directly(self, row: EssentialActionRow, subject: str, body: str) -> None:

        self._wait_for_credentials()
        record = close_ea_record(get_essential_actions(self._page, self._aura, row.contact_id), row.ea_id)
        save_note(
            self._page, self._aura, row.contact_id, row.course_code, subject, body, close_eas=[record],
        )
        # From here on the note is in: a problem must not send it again.
        try:
            closed = is_closed(get_essential_actions(self._page, self._aura, row.contact_id), row.ea_id)
        except Exception as exc:
            raise EaNotClosed(f"Note saved, but whether the Essential Action closed couldn't be checked ({exc}) - check it by hand") from exc
        if not closed:
            raise EaNotClosed("Note saved, but the Essential Action is still open - close it by hand")

    def _wait_for_credentials(self) -> None:

        for _ in range(80):
            if self._aura.ready:
                return
            self._page.wait_for_timeout(250)
        raise DirectSaveFailed("the page never made a request to read its credentials from")

    def close(self) -> None:

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
        self._rows_bodies = []
