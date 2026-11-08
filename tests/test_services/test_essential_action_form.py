"""The Essential Action form route's row finding, on a local page in Edge
(no Salesforce). Only the row lookup is tested this way: the note form
itself is the one write_note_fn already fills."""
import pytest

from src.services.browser_launch import launch_browser, playwright_session
from src.services.essential_action_form import _ea_row, fill_essential_action_form
from src.services.oa_emails import EssentialActionRow


def _row(ea_id="a5hEA1", name="Jo Smith", course="D413") -> EssentialActionRow:
    return EssentialActionRow(
        ea_id=ea_id, contact_id="003X", student_id="111", full_name=name, preferred_name="",
        email="jo@wgu.edu", course_code=course, reason="Student Passed Objective Assessment-Instructor",
    )


def _tr(name, course, reason, key=None):
    keyed = f' data-row-key-value="{key}"' if key else ""
    return (f"<tr{keyed}><td>{name}</td><td>{course}</td><td>{reason}</td>"
            f"<td><button>Show actions</button></td></tr>")


OA = "Student Passed Objective Assessment-Instructor"


@pytest.fixture(scope="module")
def page():
    with playwright_session() as playwright:
        browser = launch_browser(playwright)
        try:
            yield browser.new_page()
        finally:
            browser.close()


def _load(page, *rows):
    page.set_content("<table>" + "".join(rows) + "</table>")


def test_a_row_keyed_by_the_ea_id_is_used_even_with_the_same_name_elsewhere(page):
    _load(page, _tr("Jo Smith", "D413", OA, key="a5hOTHER"), _tr("Jo Smith", "D413", OA, key="a5hEA1"))
    assert _ea_row(page, _row()).get_attribute("data-row-key-value") == "a5hEA1"


def test_without_keys_the_name_row_is_narrowed_by_course_and_oa_reason(page):
    _load(
        page,
        _tr("Jo Smith", "D413", "Student Needs Help"),
        _tr("Jo Smith", "C769", OA),
        _tr("Jo Smith", "D413", OA),
        _tr("Al Brown", "D413", OA),
    )
    found = _ea_row(page, _row())
    assert "D413" in found.inner_text() and "Objective" in found.inner_text()


def test_two_rows_that_cant_be_told_apart_close_nothing(page):
    _load(page, _tr("Jo Smith", "D413", OA), _tr("Jo Smith", "D413", OA))
    with pytest.raises(RuntimeError, match="Found 2 rows"):
        _ea_row(page, _row())


def test_a_student_not_on_the_page_fails_plainly(page, monkeypatch):
    monkeypatch.setattr("src.services.essential_action_form.ROW_WAIT_MS", 500)
    _load(page, _tr("Al Brown", "D413", OA))
    with pytest.raises(RuntimeError, match="isn't on the Essential Actions page"):
        _ea_row(page, _row())


def test_a_form_failure_names_the_student_and_saves_a_screenshot(page, monkeypatch, tmp_path):
    monkeypatch.setattr("src.services.essential_action_form.ROW_WAIT_MS", 500)
    monkeypatch.setattr("src.services.salesforce_callbacks.screenshots_dir", lambda: tmp_path)
    _load(page, _tr("Al Brown", "D413", OA))
    with pytest.raises(RuntimeError, match="Failed closing the Essential Action for Jo Smith. Screenshot"):
        fill_essential_action_form(page, _row(), "Congrats!", "body")
    assert list(tmp_path.glob("*close_ea_a5hEA1.png"))
