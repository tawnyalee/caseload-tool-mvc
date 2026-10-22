from src.services import app_paths
from src.services.guide_markdown import inline_segments, parse_blocks, to_html_document

SAMPLE = """# Title

Intro line one
continues here.

## Section

- first **bold**
- second

1. step one
2. step two

> A callout.

`%LOCALAPPDATA%\\CaseloadTool`
"""


def test_parses_each_kind_of_block():
    kinds = [(b.kind, b.lines) for b in parse_blocks(SAMPLE)]
    assert kinds == [
        ("h1", ["Title"]),
        ("p", ["Intro line one continues here."]),
        ("h2", ["Section"]),
        ("ul", ["first **bold**", "second"]),
        ("ol", ["step one", "step two"]),
        ("quote", ["A callout."]),
        ("code", ["%LOCALAPPDATA%\\CaseloadTool"]),
    ]


def test_inline_styles():
    assert inline_segments("Click **Run** then *wait* in `logs`.") == [
        ("Click ", ""), ("Run", "bold"), (" then ", ""), ("wait", "italic"), (" in ", ""), ("logs", "code"), (".", ""),
    ]


def test_handout_is_a_complete_escaped_html_page():
    page = to_html_document(SAMPLE + "\nUse <script> & stuff.\n")
    assert page.startswith("<!doctype html>")
    assert "<title>Title</title>" in page
    assert "<li>first <strong>bold</strong></li>" in page
    assert "<pre>%LOCALAPPDATA%\\CaseloadTool</pre>" in page
    assert "&lt;script&gt; &amp; stuff." in page
    assert "<script>" not in page


def test_the_real_guide_parses_and_covers_the_essentials():
    text = app_paths.resource_path("docs/professor_guide.md").read_text(encoding="utf-8")
    headings = [b.lines[0] for b in parse_blocks(text) if b.kind in ("h1", "h2")]
    for needed in ("Stay on Outlook (classic)", "Starting the app and logging in", "Test mode",
                   "Your data and privacy", "Troubleshooting"):
        assert needed in headings
