# src/views/help_view.py
"""The ❓ Help screen: the professor guide (docs/professor_guide.md),
formatted and scrollable, plus a button to open the same guide as a
printable page in the browser. Same source file as the handout that
build_exe.py ships next to the .exe (see guide_markdown.py).

CTkTextbox won't let a tag set its own font (it reserves fonts for DPI
scaling), so tags are configured on the real tkinter.Text underneath -
same approach as html_richtext.py.
"""
import sys
import webbrowser
from pathlib import Path

import customtkinter as ctk

from src.services import app_paths
from src.services.guide_markdown import inline_segments, parse_blocks, to_html_document

GUIDE_FILE = "docs/professor_guide.md"
HANDOUT_NAME = "Professor Guide.html"
_FONT = "Segoe UI"


def load_guide_text() -> str:
    path = app_paths.resource_path(GUIDE_FILE)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "# Professor Guide\n\nThe guide file couldn't be found. Ask whoever supports the app for a copy."


def handout_path():
    """The printable copy build_exe.py puts next to CaseloadTool.exe; when
    running from source (or if someone deleted it), a freshly generated copy
    in the data folder."""
    if getattr(sys, "frozen", False):
        beside_exe = Path(sys.executable).parent / HANDOUT_NAME
        if beside_exe.is_file():
            return beside_exe
    generated = app_paths.data_dir() / HANDOUT_NAME
    generated.write_text(to_html_document(load_guide_text()), encoding="utf-8")
    return generated


class HelpView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(header, text="❓ Help", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        self.print_button = ctk.CTkButton(
            header, text="🖨 Open printable version", width=190, command=self.open_printable,
        )
        self.print_button.pack(side="right")

        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._configure_tags()
        self.render(load_guide_text())

    def _configure_tags(self) -> None:
        text = self.textbox._textbox
        text.tag_config("h1", font=(_FONT, 20, "bold"), spacing1=4, spacing3=10)
        text.tag_config("h2", font=(_FONT, 16, "bold"), foreground="#1f538d", spacing1=16, spacing3=6)
        text.tag_config("h3", font=(_FONT, 13, "bold"), spacing1=10, spacing3=4)
        text.tag_config("body", font=(_FONT, 12), spacing3=8)
        text.tag_config("item", font=(_FONT, 12), lmargin1=18, lmargin2=36, spacing3=3)
        text.tag_config("quote", font=(_FONT, 12), background="#fff3cd", lmargin1=10, lmargin2=10, spacing3=8)
        text.tag_config("code_line", font=("Consolas", 12), background="#eef1f5", lmargin1=18, spacing3=8)
        text.tag_config("bold", font=(_FONT, 12, "bold"))
        text.tag_config("italic", font=(_FONT, 12, "italic"))
        text.tag_config("code", font=("Consolas", 11), background="#eef1f5")
        # Inline styles win over the block's base font.
        for tag in ("bold", "italic", "code"):
            text.tag_raise(tag)

    def _insert_inline(self, line: str, base_tag: str) -> None:
        text = self.textbox._textbox
        for piece, style in inline_segments(line):
            text.insert("end", piece, (base_tag, style) if style else (base_tag,))

    def render(self, markdown: str) -> None:
        text = self.textbox._textbox
        self.textbox.configure(state="normal")
        text.delete("1.0", "end")
        for block in parse_blocks(markdown):
            if block.kind in ("h1", "h2", "h3"):
                self._insert_inline(block.lines[0], block.kind)
                text.insert("end", "\n")
            elif block.kind in ("ul", "ol"):
                for number, item in enumerate(block.lines, start=block.start):
                    marker = "•  " if block.kind == "ul" else f"{number}.  "
                    text.insert("end", marker, ("item",))
                    self._insert_inline(item, "item")
                    text.insert("end", "\n", ("item",))
                text.insert("end", "\n", ("body",))
            elif block.kind == "quote":
                self._insert_inline(block.lines[0], "quote")
                text.insert("end", "\n\n", ("body",))
            elif block.kind == "code":
                text.insert("end", block.lines[0] + "\n\n", ("code_line",))
            else:
                self._insert_inline(block.lines[0], "body")
                text.insert("end", "\n\n", ("body",))
        self.textbox.configure(state="disabled")  # read-only, still selectable/copyable

    def open_printable(self) -> None:
        webbrowser.open(handout_path().as_uri())
