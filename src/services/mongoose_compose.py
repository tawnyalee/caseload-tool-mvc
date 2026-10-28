# src/services/mongoose_compose.py
"""Drives Mongoose's web app to schedule one text to one student.

The route is the one the developer recorded scheduling a real text with
`playwright codegen` (2026-10-28): switch to the student's course department,
Tools > Scheduled Messages > Create, find the recipient, type the message,
Preview > Next, Message Name, date/time, Schedule. Pieces Mongoose is
known to need come from the reference project (ashejim/caseload-tool,
text_message.py), which the developer has used daily:

  - the recipient search ("Search by First, Last, ID, or Mobile") is given the
    student's Salesforce Contact Id, which matches exactly one contact; when
    duplicates exist, the result marked "Assigned to" (the professor's own) wins
  - Mongoose's loading overlay (#cw_loader) intercepts clicks while it's up,
    so every click waits it out first and retries once
  - the department switcher is `.department-name.department-dropdown`, and the
    current department is the `.department-name` label - also the "logged in"
    marker
  - date/time: three <select>s (hours, minutes, AM/PM with values "true"/
    "false") and a date box that only takes a typed date on Enter

Nothing here clicks the final Schedule button unless `commit=True`: the first
live runs stop there so the professor can check what Mongoose shows.
Not wired into the app's TextSender yet.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

LOGGED_IN_SELECTOR = ".department-name"
RECIPIENT_SEARCH_LABEL = "Search by First, Last, ID, or Mobile"


class NoMongooseMatch(RuntimeError):
    """The student couldn't be found in this department's contacts - e.g.
    they opted out, or aren't in Mongoose. The run skips them and lists them."""


@dataclass
class ScheduledText:
    course_code: str          # Mongoose department, e.g. "D424"
    contact_id: str           # Salesforce Contact Id ("003...")
    body: str
    message_name: str         # Mongoose's "Message Name" for the schedule
    send_at: datetime         # in the department's (team's) time zone, as Mongoose expects


def _noop(_message: str) -> None:
    pass


def wait_for_loader(page, timeout_ms: int = 20_000) -> None:
    try:
        page.locator("#cw_loader").wait_for(state="hidden", timeout=timeout_ms)
    except Exception:
        pass


def click(locator, page, timeout_ms: int = 10_000) -> None:
    """Clicks after the loading overlay clears, once more if the overlay
    popped up during the first click (a known Mongoose cold-start issue)."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    for attempt in range(2):
        wait_for_loader(page)
        try:
            locator.click(timeout=timeout_ms)
            return
        except PlaywrightTimeoutError:
            if attempt == 1:
                raise
            wait_for_loader(page, timeout_ms=25_000)


def current_department(page) -> str:
    try:
        label = page.locator(LOGGED_IN_SELECTOR).filter(visible=True).first
        return (label.inner_text() or "").strip() if label.count() else ""
    except Exception:
        return ""


def department_matches(shown: str, course_code: str) -> bool:
    """The sidebar label may carry more than the code (e.g. "D424 ..."), so
    compare its first word, ignoring case."""
    words = (shown or "").split()
    return bool(words) and words[0].lower() == course_code.strip().lower()


def switch_department(page, course_code: str, timeout_ms: int = 10_000) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    if department_matches(current_department(page), course_code):
        return
    click(page.locator(".department-name.department-dropdown").filter(visible=True).first, page, timeout_ms)
    item = page.locator(f'.team-list .v-list-item[aria-label^="{course_code}"]').filter(visible=True).first
    try:
        item.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        page.keyboard.press("Escape")
        raise RuntimeError(f"Mongoose has no {course_code} department to text from.") from None
    item.click()
    for _ in range(int(timeout_ms / 200)):
        if department_matches(current_department(page), course_code):
            page.wait_for_timeout(1200)  # let the department's page finish rendering
            return
        page.wait_for_timeout(200)
    raise RuntimeError(f"Mongoose didn't switch to the {course_code} department.")


def open_new_scheduled_message(page) -> None:
    click(page.get_by_role("button", name="Tools section"), page)
    click(page.get_by_role("link", name="Scheduled Messages"), page)
    click(page.get_by_role("button", name="Create", exact=True), page)


def add_recipient(page, contact_id: str, timeout_ms: int = 10_000) -> None:
    """Searches by Contact Id and picks the match. Typing the last character
    for real matters: Mongoose's search only runs on a keystroke."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    box = page.get_by_role("combobox", name=RECIPIENT_SEARCH_LABEL).filter(visible=True).first
    click(box, page)
    box.fill(contact_id[:-1])
    box.press_sequentially(contact_id[-1], delay=15)
    options = page.locator(
        '.v-overlay-container .v-list-item[role="option"], .v-autocomplete__content .v-list-item'
    ).filter(visible=True)
    try:
        options.first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        page.keyboard.press("Escape")
        raise NoMongooseMatch(
            "Not found in this Mongoose department (they may have opted out of texts)"
        ) from None
    exact = options.filter(has_text=contact_id)
    candidates = exact if exact.count() else options
    assigned = candidates.filter(has_text="Assigned to")
    (assigned if assigned.count() else candidates).first.click()


def set_message(page, body: str) -> None:
    area = page.get_by_test_id("compose-modal-message-area").get_by_test_id("compose-message-textarea")
    click(area, page)
    area.fill(body)


def fill_schedule(page, send_at: datetime) -> None:
    """Time first (the date's calendar pop-up can cover the time selects),
    then the date, committed with Enter."""
    page.locator("select.vc-time-select-hours").first.select_option(label=str(int(send_at.strftime("%I"))))
    page.locator("select.vc-time-select-minutes").first.select_option(label=f"{send_at.minute:02d}")
    page.locator('select:has(option[value="true"])').first.select_option(
        value="true" if send_at.strftime("%p") == "AM" else "false"
    )
    date_box = page.locator('input.dp__input[aria-label="Datepicker input"]').filter(visible=True).first
    date_box.click()
    date_box.fill("")
    date_box.press_sequentially(send_at.strftime("%m/%d/%Y"), delay=20)
    date_box.press("Enter")
    page.wait_for_timeout(300)


def compose_scheduled_text(page, text: ScheduledText, commit: bool = False,
                           say: Callable[[str], None] = _noop) -> None:
    """Fills in one scheduled text. Clicks the final Schedule only if
    `commit`; otherwise it stops with everything filled in for review."""
    say(f"Switching to {text.course_code}...")
    switch_department(page, text.course_code)
    say("Opening a new scheduled message...")
    open_new_scheduled_message(page)
    say("Finding the student...")
    add_recipient(page, text.contact_id)
    say("Typing the message...")
    set_message(page, text.body)
    click(page.get_by_role("button", name="Preview"), page)
    click(page.get_by_role("button", name="Next", exact=True), page)
    say("Naming and timing it...")
    name_box = page.get_by_role("textbox", name="Message Name")
    click(name_box, page)
    name_box.fill(text.message_name)
    fill_schedule(page, text.send_at)
    if commit:
        click(page.get_by_role("button", name="Schedule", exact=True), page)
        say("Scheduled.")
    else:
        say("Stopped before Schedule - nothing was sent.")
