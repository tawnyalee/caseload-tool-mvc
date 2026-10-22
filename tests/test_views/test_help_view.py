import pytest
import customtkinter as ctk

from src.views import help_view
from src.views.help_view import HelpView


@pytest.fixture(scope="module")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def test_shows_the_whole_guide_formatted_and_read_only(ctk_root):
    view = HelpView(ctk_root)
    try:
        shown = view.textbox.get("1.0", "end")
        assert "Caseload Tool — Professor Guide" in shown
        assert "Stay on Outlook (classic)" in shown
        assert "**" not in shown  # markdown markers are rendered, not shown
        assert view.textbox.cget("state") == "disabled"
        heading_ranges = view.textbox._textbox.tag_ranges("h2")
        assert heading_ranges  # section headings got the heading style
    finally:
        view.destroy()


def test_printable_version_from_source_is_generated_into_the_data_folder(ctk_root, monkeypatch):
    opened = []
    monkeypatch.setattr(help_view.webbrowser, "open", opened.append)
    view = HelpView(ctk_root)
    try:
        view.open_printable()
    finally:
        view.destroy()
    assert opened and opened[0].startswith("file:///")
    assert opened[0].endswith("Professor%20Guide.html")
    generated = help_view.app_paths.data_dir() / "Professor Guide.html"  # the per-test temp data folder
    assert "<h2>Stay on Outlook (classic)</h2>" in generated.read_text(encoding="utf-8")


def test_missing_guide_file_shows_a_plain_message(monkeypatch, tmp_path):
    monkeypatch.setattr(help_view.app_paths, "resource_path", lambda rel: tmp_path / "nope.md")
    assert "couldn't be found" in help_view.load_guide_text()
