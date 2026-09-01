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
"""
import re

from playwright.sync_api import Page

CASELOAD_APP_URL = "https://srm.lightning.force.com/lightning/n/Caseload_App_Page?overrideNavRules=true"
EXPORT_BUTTON_SELECTOR = '[title="Download"]'


def _id_cell(page: Page, salesforce_id: str):
    """The <td> whose text exactly matches salesforce_id - an exact match
    (not a substring one) so one student's ID can never accidentally match
    a different student whose ID happens to contain it."""
    return page.locator("td").filter(has_text=re.compile(rf"^{re.escape(salesforce_id)}$"))


def _row_for_student(page: Page, salesforce_id: str):
    """The <tr> containing that student's ID cell, for actions (like the
    follow-up note button/textarea) scoped to the rest of their row."""
    return page.locator("tr").filter(has=_id_cell(page, salesforce_id))


def write_note_fn(page: Page, salesforce_id: str, subject: str, body: str, course_code: str) -> None:
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


def _followup_column_index(page: Page) -> int:
    """The position of the "Followup Note" column among its header's
    siblings - used to find the right <td> in a row structurally, since
    the cell itself has no reliable button/title to search by (an
    earlier attempt at that accidentally matched a *different* column,
    "Course Contact", which happens to have similarly-worded text). The
    header isn't a real <th>/columnheader-role element (neither found
    anything), so this locates it by its own text instead and asks the
    browser directly for its position among its parent's children -
    works regardless of what markup this custom grid's header uses."""
    header = page.get_by_text(re.compile(r"followup\s*note", re.IGNORECASE)).first
    return header.evaluate("el => Array.from(el.parentElement.children).indexOf(el)")


def update_follow_up_fn(page: Page, salesforce_id: str, text: str) -> None:
    row = _row_for_student(page, salesforce_id)
    # Some of this custom grid's row controls only activate once the row
    # has actually been hovered (a real person naturally does this before
    # clicking; a script doesn't unless told to) - hovering first may be
    # why the "Add followup note" button hasn't been found reliably.
    row.hover()
    row.get_by_title("Add followup note for this").click()
    textarea = row.locator("textarea")
    print(f"DEBUG: textarea value BEFORE editing = {textarea.input_value()!r}")
    textarea.click()
    textarea.press("ControlOrMeta+a")
    textarea.fill(text)
    print(f"DEBUG: textarea value immediately AFTER fill = {textarea.input_value()!r}")
    # The field saves on losing focus (confirmed: moving to a different
    # student's follow-up field saves the one just typed), not just on
    # Enter - Tab reliably triggers that same blur/save without leaving a
    # stray newline character in the saved text.
    textarea.press("Tab")
    # Whatever save this triggers is a network call to Salesforce, not
    # instant - PlaywrightNoteWriter closes the whole browser right after
    # this callback returns, which could cut that request off mid-flight.
    # Give it a moment to actually complete first.
    page.wait_for_timeout(1500)
