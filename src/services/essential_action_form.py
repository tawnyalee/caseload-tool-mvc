# src/services/essential_action_form.py
"""The form route for saving an OA note with its Essential Action closed:
the clicks the developer recorded on the Essential Actions page (2026-11-08).
Used when direct saves are off or a direct save fails (essential_actions.py).

The recording: the student's row -> "Show actions" -> "Add Note & Close EA",
then the same note form the Caseload page uses (Single Interaction, "Email to
Student", course, subject, text), so the form steps are shared with
salesforce_callbacks.write_note_fn. Submit wasn't clicked while recording (the
EA was left open on purpose); it's the same form's "Submit" button.
"""
import re

from playwright.sync_api import Page

from src.services.oa_emails import EssentialActionRow, OA_PASS_REASON_PREFIX
from src.services.salesforce_callbacks import _choose_single_interaction, _screenshot_failure

ROW_WAIT_MS = 30_000


def _ea_row(page: Page, row: EssentialActionRow):
    """The table row for this one Essential Action. Salesforce data tables
    usually key each <tr> by the record id, which is exact. If not, the row is
    found by the student's name, narrowed by course and OA reason, and it must
    be exactly one row: a wrong guess would close someone else's EA."""
    keyed = page.locator(f'tr[data-row-key-value="{row.ea_id}"]')
    by_name = page.locator("tr").filter(has_text=row.full_name)
    try:
        keyed.or_(by_name).first.wait_for(timeout=ROW_WAIT_MS)
    except Exception:
        raise RuntimeError(f"{row.full_name}'s Essential Action isn't on the Essential Actions page")
    if keyed.count() == 1:
        return keyed
    candidates = by_name
    for narrower in (row.course_code, re.compile(re.escape(OA_PASS_REASON_PREFIX), re.I)):
        if candidates.count() <= 1:
            break
        narrowed = candidates.filter(has_text=narrower)
        if narrowed.count() >= 1:
            candidates = narrowed
    if candidates.count() != 1:
        raise RuntimeError(
            f"Found {candidates.count()} rows for {row.full_name} on the Essential Actions page, "
            "so none was closed - close it by hand"
        )
    return candidates


def fill_essential_action_form(page: Page, row: EssentialActionRow, subject: str, body: str) -> None:
    try:
        _ea_row(page, row).locator("button").filter(has_text="Show actions").click()
        page.locator("a").filter(has_text="Add Note & Close EA").click()

        _choose_single_interaction(page)
        page.get_by_label("*Interaction Type").select_option("Email to Student")

        # Real keystrokes: the course search ignores .fill() (see write_note_fn).
        course_field = page.get_by_placeholder("Enter here...")
        course_field.click()
        course_field.press_sequentially(row.course_code)
        page.get_by_label("Sub page").get_by_text(row.course_code, exact=True).click()

        page.get_by_label("*Subject").press("ControlOrMeta+a")
        page.get_by_label("*Subject").fill(subject)
        page.get_by_label("Compose text").click()
        page.get_by_label("Compose text").fill(body)

        page.get_by_text("Submit", exact=True).click()
        page.wait_for_timeout(1500)  # let the save finish before anything reloads
    except Exception as e:
        path = _screenshot_failure(page, f"close_ea_{row.ea_id}")
        raise RuntimeError(
            f"Failed closing the Essential Action for {row.full_name}. Screenshot: {path}. Underlying: {e}"
        ) from e
