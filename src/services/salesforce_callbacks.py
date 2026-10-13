# src/services/salesforce_callbacks.py
"""The real, org-specific Playwright automation for the Caseload App Page
at srm.lightning.force.com - captured via `python -m playwright codegen`
against the actual org (see src/CLAUDE.md's Salesforce integration plan).
Not wired into AppController yet - same "build it, test it, swap in only
when ready" pattern as the rest of this integration.

Every action starts from the same shared list page (there's no
per-student record URL to navigate straight to) - the student's row is
found by an exact match on their own StudentID (Student.salesforce_id) in
a table cell, not by name, so a duplicate or renamed display name can
never cause a note to land on the wrong student's record. Writing a note
then clicks that row's dedicated "Open Student Notes for Selected
Student" icon - one of a handful of action icons that are always in the
same fixed position on the far left of every row, unlike the student's
name (which can move depending on how the roster is sorted/configured) -
to open the interaction-logging form. Updating the follow-up note happens
back on the shared list instead, which is why write_note_fn ends by
returning to the "Caseload" tab.

Screenshot-on-failure (_screenshot_failure) was ported from researching
another WGU-caseload-tool's open-source Salesforce automation (see
src/CLAUDE.md's Mongoose/cross-project research note) - deliberately the
only thing borrowed from it. That other project's click sequence is also
more defensive (retry-until-verified clicks, poll-before-read on button
state), but this module's click sequence is already confirmed working
end-to-end against production (see src/CLAUDE.md), and there's no way to
verify a change to that sequence without a live run - so it's left alone.
Reach for that project's retry/poll patterns only if a live run starts
showing intermittent Submit-disabled or lost-click failures; the
screenshot this now saves on any failure is what would show that.
"""
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

CASELOAD_APP_URL = "https://srm.lightning.force.com/lightning/n/Caseload_App_Page?overrideNavRules=true"
EXPORT_BUTTON_SELECTOR = '[title="Download"]'

# Reuses the existing gitignored logs/ directory rather than adding a new
# ignore entry - screenshots are debug artifacts, same category as the
# ActivityLogger's daily log files.
SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "screenshots"


def _screenshot_failure(page: Page, tag: str) -> Path:
    """Saves a full-page screenshot to SCREENSHOTS_DIR and returns its path,
    for a failure message to point at - so a failed unattended run leaves
    behind a picture of exactly what the page looked like, not just a bare
    Playwright timeout/selector error. Best-effort: if the page itself is
    already gone (e.g. the browser closed mid-failure), the screenshot is
    skipped rather than raising a second error that would mask the first."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SCREENSHOTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{tag}.png"
    try:
        page.screenshot(path=str(out), full_page=True)
    except Exception:
        pass
    return out


def _id_cell(page: Page, salesforce_id: str):
    """The <td> whose text exactly matches salesforce_id - an exact match
    (not a substring one) so one student's ID can never accidentally match
    a different student whose ID happens to contain it."""
    return page.locator("td").filter(has_text=re.compile(rf"^{re.escape(salesforce_id)}$"))


def _row_for_student(page: Page, salesforce_id: str, max_scroll_attempts: int = 60):
    """The <tr> containing that student's ID cell, for actions (like the
    follow-up note button/textarea) scoped to the rest of their row.

    The roster has ~242 students in a virtualized grid - a row that isn't
    currently scrolled into view doesn't actually exist in the page yet,
    and which student ends up where isn't predictable (the roster
    reshuffles daily, and any given student could be anywhere in it). So
    if the row isn't there on the first check, this scrolls down inside
    the grid a bit at a time, re-checking after each step, until it
    appears - or gives up after a generous number of attempts (this
    student may no longer be on the roster at all, which has happened
    before - a student who passed and moved on)."""
    row = page.locator("tr").filter(has=_id_cell(page, salesforce_id))
    if row.count() > 0:
        return row

    # The developer scrolls this roster by dragging its scrollbar
    # directly, not a mouse wheel - mouse-wheel scrolling turned out not
    # to move anything here (whether because it's not wired up on this
    # custom grid, or the mouse just wasn't over the right element).
    # Setting scrollTop directly on the real scrollable container fires
    # the same native scroll event a scrollbar drag would, regardless of
    # how a human would trigger it or where the mouse happens to be.
    for _ in range(max_scroll_attempts):
        page.locator("tr").first.evaluate(
            """(el, dy) => {
                let node = el;
                while (node && node.scrollHeight <= node.clientHeight) {
                    node = node.parentElement;
                }
                if (node) node.scrollTop += dy;
            }""",
            600,
        )
        page.wait_for_timeout(150)
        if row.count() > 0:
            return row
    raise RuntimeError(f'Could not find a row for student "{salesforce_id}" after scrolling through the roster.')


def write_note_fn(page: Page, salesforce_id: str, subject: str, body: str, course_code: str) -> None:
    try:
        # This icon is one of a fixed set (email/call/program/note) always in
        # the same position on the far left of every row, unlike the student's
        # name or other columns that can reorder - far more reliable to target.
        _row_for_student(page, salesforce_id).get_by_title("Open Student Notes for Selected Student").click()

        # "Single Interaction" is a real radio button (not just clickable text)
        # that reveals the Interaction Type dropdown once selected.
        page.locator(".slds-radio__label > .slds-radio_faux").first.click()
        page.get_by_label("*Interaction Type").select_option("Email to Student")

        # The course typeahead only searches on real keystrokes - .fill() sets
        # the value in one shot, which doesn't reliably trigger it (Salesforce
        # itself can also be a bit laggy showing the dropdown even when typed
        # normally). press_sequentially() simulates actual per-character typing.
        course_field = page.get_by_placeholder("Enter here...")
        course_field.click()
        course_field.press_sequentially(course_code)
        page.get_by_label("Sub page").get_by_text(course_code, exact=True).click()

        page.get_by_label("*Subject").press("ControlOrMeta+a")
        page.get_by_label("*Subject").fill(subject)
        page.get_by_label("Compose text").click()
        page.get_by_label("Compose text").fill(body)

        page.get_by_text("Submit", exact=True).click()
        page.get_by_role("tab", name="Caseload").click()
    except Exception as e:
        path = _screenshot_failure(page, f"write_note_{salesforce_id}")
        raise RuntimeError(
            f"Failed writing note for student {salesforce_id}. Screenshot: {path}. Underlying: {e}"
        ) from e


def update_follow_up_fn(page: Page, salesforce_id: str, text: str) -> None:
    try:
        # The edit (pencil) icon's full title includes "...student and
        # course" - exact=True avoids colliding with a different column's
        # similarly-worded control ("Course Contact"). It also only seems to
        # attach once the row's been hovered, same as a real person would
        # before clicking.
        row = _row_for_student(page, salesforce_id)
        row.hover()
        row.get_by_title("Add followup note for this student and course", exact=True).click()
        textarea = row.locator("textarea")
        textarea.click()
        textarea.press("ControlOrMeta+a")
        # .fill() sets the value in one shot with no real keystrokes - same
        # issue the course code field had (see write_note_fn): the value
        # visibly changes but Salesforce's own save logic never notices it.
        textarea.press_sequentially(text)
        # Saves on losing focus to something else on the page - the ID cell
        # in this same row is a safe, always-present, inert thing to click
        # (it has no click behavior of its own), so it can only trigger the
        # blur/save here, nothing else.
        _id_cell(page, salesforce_id).click()
        # The save is a network call, not instant - PlaywrightNoteWriter
        # closes the whole browser right after this callback returns, which
        # could cut it off mid-flight otherwise.
        page.wait_for_timeout(1500)
    except Exception as e:
        path = _screenshot_failure(page, f"update_follow_up_{salesforce_id}")
        raise RuntimeError(
            f"Failed updating follow-up note for student {salesforce_id}. Screenshot: {path}. Underlying: {e}"
        ) from e
