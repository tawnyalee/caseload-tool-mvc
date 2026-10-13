import pytest
import customtkinter as ctk

from src.views.run_summary_modal import RunSummaryModal


@pytest.fixture(scope="module")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def test_lists_every_issue_line_read_only(ctk_root):
    lines = ["❌ Jane Doe (ID 1) — Email failed: boom", "⏭ Jane Doe (ID 1) — Note skipped"]
    modal = RunSummaryModal(ctk_root, title="Run Complete — Review Needed", message="Run complete", issue_lines=lines)
    try:
        assert modal.issues_box.get("0.0", "end-1c") == "\n".join(lines)
        assert modal.issues_box.cget("state") == "disabled"
    finally:
        modal.destroy()


def test_copy_button_puts_the_list_on_the_clipboard(ctk_root):
    lines = ["❌ Jane Doe (ID 1) — Email failed: boom"]
    modal = RunSummaryModal(ctk_root, title="t", message="m", issue_lines=lines)
    try:
        modal._copy_to_clipboard()
        assert modal.clipboard_get() == lines[0]
        assert modal.copy_button.cget("text") == "✔ Copied"
    finally:
        modal.destroy()
