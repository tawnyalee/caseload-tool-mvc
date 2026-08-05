import customtkinter as ctk
import pytest
from src.services import html_richtext as rt


@pytest.fixture(scope="session")
def ctk_root():
    """Creates a single shared CTk root instance for all richtext tests."""
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


@pytest.fixture
def textbox(ctk_root):
    box = ctk.CTkTextbox(ctk_root)
    rt.configure_base_tags(box)
    return box


def test_toolbar_formatting_round_trips_through_html(textbox):
    link_urls = {}
    textbox.insert("1.0", "Hello world")

    rt.toggle_bold(textbox, "1.0", "1.5")  # "Hello"
    rt.toggle_italic(textbox, "1.6", "1.11")  # "world"
    rt.toggle_underline(textbox, "1.0", "1.11")

    html = rt.extract_html(textbox, link_urls)

    assert "<b>Hello</b>" in html
    assert "<i>world</i>" in html
    assert html.startswith("<u>")
    assert html.endswith("</u>")


def test_bold_italic_and_size_compose_on_the_same_run(textbox):
    link_urls = {}
    textbox.insert("1.0", "Important")
    rt.toggle_bold(textbox, "1.0", "1.9")
    rt.toggle_italic(textbox, "1.0", "1.9")
    rt.set_font_size(textbox, "1.0", "1.9", 18)

    html = rt.extract_html(textbox, link_urls)

    assert html == '<span style="font-size: 18pt;"><i><b>Important</b></i></span>'


def test_toggle_bold_off_removes_formatting(textbox):
    link_urls = {}
    textbox.insert("1.0", "Hello")
    rt.toggle_bold(textbox, "1.0", "1.5")
    rt.toggle_bold(textbox, "1.0", "1.5")  # toggle back off

    html = rt.extract_html(textbox, link_urls)
    assert html == "Hello"


def test_add_link_round_trips_href(textbox):
    link_urls = {}
    textbox.insert("1.0", "Click here")
    rt.add_link(textbox, "1.0", "1.10", "https://example.com", link_urls)

    html = rt.extract_html(textbox, link_urls)
    assert html == '<a href="https://example.com">Click here</a>'


def test_render_html_parses_editor_generated_markup_back_into_tags(textbox):
    link_urls = {}
    html_in = '<b>Bold</b> and <i>italic</i> and <a href="https://x.test">a link</a>'
    rt.render_html(textbox, html_in, link_urls)

    html_out = rt.extract_html(textbox, link_urls)
    assert html_out == html_in
    assert textbox.get("1.0", "end-1c") == "Bold and italic and a link"


def test_render_html_handles_outlook_style_spans_without_crashing(textbox):
    link_urls = {}
    messy_html = (
        '<p style="margin:0"><span style="font-weight:bold; color:#000">Reminder</span></p>\n'
        '<div><span style="font-style: italic">Please respond</span> by Friday.</div>\n'
        '<span>Unstyled tail</span>'
    )

    rt.render_html(textbox, messy_html, link_urls)
    text = textbox.get("1.0", "end-1c")

    assert "Reminder" in text
    assert "Please respond" in text
    assert "by Friday." in text
    assert "Unstyled tail" in text

    html_out = rt.extract_html(textbox, link_urls)
    assert "<b>Reminder</b>" in html_out
    assert "<i>Please respond</i>" in html_out


def test_render_html_ignores_unknown_tags_and_keeps_their_text(textbox):
    link_urls = {}
    rt.render_html(textbox, "<weirdtag>plain text survives</weirdtag>", link_urls)
    assert textbox.get("1.0", "end-1c") == "plain text survives"
