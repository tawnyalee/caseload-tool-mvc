# src/services/guide_markdown.py
"""Reads the professor guide (docs/professor_guide.md) for its two uses:
the in-app Help screen (HelpView) and the printable HTML handout that
build_exe.py puts next to CaseloadTool.exe. One source file, so the two
can never disagree.

Understands only the small Markdown subset the guide uses - no library
needed:

    # / ## / ###      headings
    - item            bullet list
    1. item           numbered list
    > text            callout
    `whole line`      a line to copy exactly (path, file contents)
    blank line        paragraph break
    **bold** *italic* `code`   inside any text
"""
import html
import re
from dataclasses import dataclass
from typing import List, Tuple

_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
_NUMBERED = re.compile(r"^\d+\.\s+")


@dataclass
class Block:
    kind: str  # "h1" | "h2" | "h3" | "p" | "ul" | "ol" | "quote" | "code"
    lines: List[str]  # one entry per list item; otherwise a single entry


def parse_blocks(markdown: str) -> List[Block]:
    blocks: List[Block] = []
    paragraph: List[str] = []

    def flush_paragraph():
        if paragraph:
            blocks.append(Block("p", [" ".join(paragraph)]))
            paragraph.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush_paragraph()
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            blocks.append(Block(f"h{len(heading.group(1))}", [heading.group(2)]))
        elif line.startswith("- "):
            flush_paragraph()
            if blocks and blocks[-1].kind == "ul":
                blocks[-1].lines.append(line[2:])
            else:
                blocks.append(Block("ul", [line[2:]]))
        elif _NUMBERED.match(line):
            flush_paragraph()
            item = _NUMBERED.sub("", line)
            if blocks and blocks[-1].kind == "ol":
                blocks[-1].lines.append(item)
            else:
                blocks.append(Block("ol", [item]))
        elif line.startswith("> "):
            flush_paragraph()
            blocks.append(Block("quote", [line[2:]]))
        elif line.startswith("`") and line.endswith("`") and line.count("`") == 2:
            flush_paragraph()
            blocks.append(Block("code", [line[1:-1]]))
        else:
            paragraph.append(line)
    flush_paragraph()
    return blocks


def inline_segments(text: str) -> List[Tuple[str, str]]:
    """Splits text into (piece, style) with style "", "bold", "italic" or "code"."""
    segments = []
    for piece in _INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            segments.append((piece[2:-2], "bold"))
        elif piece.startswith("`") and piece.endswith("`"):
            segments.append((piece[1:-1], "code"))
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            segments.append((piece[1:-1], "italic"))
        else:
            segments.append((piece, ""))
    return segments


def _inline_html(text: str) -> str:
    tags = {"bold": "strong", "italic": "em", "code": "code"}
    out = []
    for piece, style in inline_segments(text):
        escaped = html.escape(piece)
        out.append(f"<{tags[style]}>{escaped}</{tags[style]}>" if style else escaped)
    return "".join(out)


_HANDOUT_CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; max-width: 760px; margin: 32px auto; padding: 0 20px;
       color: #1f2328; line-height: 1.55; font-size: 15px; }
h1 { font-size: 28px; border-bottom: 3px solid #1f538d; padding-bottom: 8px; }
h2 { font-size: 21px; color: #1f538d; margin-top: 34px; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; }
h3 { font-size: 17px; margin-top: 22px; }
li { margin: 4px 0; }
code { background: #f2f4f7; padding: 1px 5px; border-radius: 4px; font-family: Consolas, monospace; }
pre { background: #f2f4f7; padding: 10px 14px; border-radius: 6px; font-family: Consolas, monospace; overflow-x: auto; }
blockquote { margin: 16px 0; padding: 10px 14px; background: #fff8e1; border-left: 4px solid #e0b400; }
@media print { body { margin: 0; max-width: none; } h2 { page-break-after: avoid; } }
"""


def to_html_document(markdown: str) -> str:
    """The standalone handout: one HTML file that opens in any browser and
    prints cleanly (browser Print -> Save as PDF for a paper copy)."""
    blocks = parse_blocks(markdown)
    title = next((b.lines[0] for b in blocks if b.kind == "h1"), "Professor Guide")
    body = []
    for block in blocks:
        if block.kind in ("h1", "h2", "h3"):
            body.append(f"<{block.kind}>{_inline_html(block.lines[0])}</{block.kind}>")
        elif block.kind in ("ul", "ol"):
            items = "".join(f"<li>{_inline_html(item)}</li>" for item in block.lines)
            body.append(f"<{block.kind}>{items}</{block.kind}>")
        elif block.kind == "quote":
            body.append(f"<blockquote>{_inline_html(block.lines[0])}</blockquote>")
        elif block.kind == "code":
            body.append(f"<pre>{html.escape(block.lines[0])}</pre>")
        else:
            body.append(f"<p>{_inline_html(block.lines[0])}</p>")
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html.escape(title)}</title><style>{_HANDOUT_CSS}</style></head>\n<body>\n"
        + "\n".join(body)
        + "\n</body></html>\n"
    )
