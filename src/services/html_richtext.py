# src/services/html_richtext.py
"""HTML <-> tkinter.Text rich-text conversion for the template editor.

Lets professors see actual bold/italic/underline/highlight/sized/linked text
in the editor instead of raw markup, while templates are still stored as
HTML on disk. Only understands the formatting this editor's own toolbar
produces, plus a best-effort subset of what Outlook/Word paste as HTML
(inline style attributes and b/i/u/a/p/div/br tags) — anything else is
still inserted as plain text rather than raising.

CTkTextbox forbids configuring a tag's `font` (it reserves that for its own
DPI-scaling system) and doesn't forward `.dump()` at all, so every function
here operates on the real tkinter.Text widget at `widget._textbox`.
"""
import html as html_lib
import re
from html.parser import HTMLParser

DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 13
HIGHLIGHT_COLOR = "yellow"
LINK_COLOR = "#1f538d"

_SIZE_RE = re.compile(r"([\d.]+)\s*(pt|px)", re.IGNORECASE)
_STYLE_PROP_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+)")

_link_counter = {"n": 0}


def _real(widget):
    """CTkTextbox wraps a real tkinter.Text at ._textbox; plain Text widgets
    (e.g. in tests) are returned as-is."""
    return getattr(widget, "_textbox", widget)


# ---------------------------------------------------------------------------
# Style application (toolbar-driven)
# ---------------------------------------------------------------------------

def configure_base_tags(widget) -> None:
    """Sets up the static, non-per-instance tags this editor uses."""
    text = _real(widget)
    text.tag_config("underline", underline=True)
    text.tag_config("highlight", background=HIGHLIGHT_COLOR)


def _combo_tag_name(weight: str, slant: str, size: int) -> str:
    return f"combo_{weight}_{slant}_{size}"


def _ensure_combo_tag(widget, weight: str, slant: str, size: int) -> str:
    text = _real(widget)
    name = _combo_tag_name(weight, slant, size)
    text.tag_config(name, font=(DEFAULT_FONT_FAMILY, size, f"{weight} {slant}".strip()))
    return name


def _current_style_at(widget, index: str) -> dict:
    """Reads the combo tag (if any) present at `index`."""
    text = _real(widget)
    for tag in text.tag_names(index):
        if tag.startswith("combo_"):
            _, weight, slant, size = tag.split("_")
            return {"weight": weight, "slant": slant, "size": int(size)}
    return {"weight": "normal", "slant": "roman", "size": DEFAULT_FONT_SIZE}


def apply_style(widget, start: str, end: str, **changes) -> None:
    """Merges `changes` (weight/slant/size) into the style at `start` and
    re-applies it as a single combo tag across [start, end), so bold+italic+
    size always compose correctly instead of fighting over tag priority."""
    text = _real(widget)
    current = _current_style_at(widget, start)
    current.update(changes)

    for tag in text.tag_names():
        if tag.startswith("combo_"):
            text.tag_remove(tag, start, end)

    if current["weight"] == "normal" and current["slant"] == "roman" and current["size"] == DEFAULT_FONT_SIZE:
        return  # baseline style — no tag needed

    tag_name = _ensure_combo_tag(widget, current["weight"], current["slant"], current["size"])
    text.tag_add(tag_name, start, end)


def toggle_bold(widget, start: str, end: str) -> None:
    current = _current_style_at(widget, start)
    apply_style(widget, start, end, weight="bold" if current["weight"] == "normal" else "normal")


def toggle_italic(widget, start: str, end: str) -> None:
    current = _current_style_at(widget, start)
    apply_style(widget, start, end, slant="italic" if current["slant"] == "roman" else "roman")


def set_font_size(widget, start: str, end: str, size_pt: int) -> None:
    apply_style(widget, start, end, size=size_pt)


def toggle_underline(widget, start: str, end: str) -> None:
    text = _real(widget)
    if "underline" in text.tag_names(start):
        text.tag_remove("underline", start, end)
    else:
        text.tag_add("underline", start, end)


def toggle_highlight(widget, start: str, end: str) -> None:
    text = _real(widget)
    if "highlight" in text.tag_names(start):
        text.tag_remove("highlight", start, end)
    else:
        text.tag_add("highlight", start, end)


def add_link(widget, start: str, end: str, url: str, link_urls: dict) -> None:
    text = _real(widget)
    _link_counter["n"] += 1
    tag_name = f"link_{_link_counter['n']}"
    text.tag_config(tag_name, foreground=LINK_COLOR, underline=True)
    text.tag_add(tag_name, start, end)
    link_urls[tag_name] = url


# ---------------------------------------------------------------------------
# HTML -> Text widget
# ---------------------------------------------------------------------------

class _FragmentParser(HTMLParser):
    def __init__(self, widget, link_urls: dict):
        super().__init__(convert_charrefs=True)
        self.widget = widget
        self.link_urls = link_urls
        self.stack = []
        self.state = {"bold": 0, "italic": 0, "underline": 0, "highlight": 0, "size": None, "href": None}

    def _style_from_attrs(self, attrs) -> dict:
        style_attr = dict(attrs).get("style", "") or ""
        result = {}
        for prop, value in _STYLE_PROP_RE.findall(style_attr):
            prop = prop.strip().lower()
            value = value.strip().lower()
            if prop == "font-weight" and (value in ("bold", "bolder") or (value.isdigit() and int(value) >= 600)):
                result["bold"] = True
            elif prop == "font-style" and value == "italic":
                result["italic"] = True
            elif prop == "text-decoration" and "underline" in value:
                result["underline"] = True
            elif prop == "background-color" and value not in ("transparent", "#ffffff", "white"):
                result["highlight"] = True
            elif prop == "font-size":
                match = _SIZE_RE.search(value)
                if match:
                    num, unit = match.groups()
                    pt = float(num) if unit.lower() == "pt" else float(num) * 0.75
                    result["size"] = round(pt)
        return result

    def _frame_from_tag(self, tag, attrs) -> dict:
        style = self._style_from_attrs(attrs)
        frame = {"bold": 0, "italic": 0, "underline": 0, "highlight": 0, "size": None, "href": None}
        if tag in ("b", "strong") or style.get("bold"):
            frame["bold"] = 1
        if tag in ("i", "em") or style.get("italic"):
            frame["italic"] = 1
        if tag == "u" or style.get("underline"):
            frame["underline"] = 1
        if style.get("highlight"):
            frame["highlight"] = 1
        if "size" in style:
            frame["size"] = style["size"]
        if tag == "a":
            frame["href"] = dict(attrs).get("href")
        return frame

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self._insert_text("\n")
            return
        frame = self._frame_from_tag(tag, attrs)
        self.stack.append(frame)
        for key in ("bold", "italic", "underline", "highlight"):
            self.state[key] += frame[key]
        if frame["size"] is not None:
            self.state["size"] = frame["size"]
        if frame["href"] is not None:
            self.state["href"] = frame["href"]

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self._insert_text("\n")

    def handle_endtag(self, tag):
        if tag == "br" or not self.stack:
            return
        frame = self.stack.pop()
        for key in ("bold", "italic", "underline", "highlight"):
            self.state[key] -= frame[key]
        if tag in ("p", "div"):
            self._insert_text("\n")
        self.state["size"] = next((f["size"] for f in reversed(self.stack) if f["size"] is not None), None)
        self.state["href"] = next((f["href"] for f in reversed(self.stack) if f["href"] is not None), None)

    def handle_data(self, data):
        if data.strip() == "" and "\n" in data:
            return  # source-formatting whitespace between tags, not content
        self._insert_text(data)

    def _insert_text(self, text_value: str) -> None:
        if text_value == "":
            return
        widget = self.widget
        real = _real(widget)
        start = real.index("insert")
        real.insert("insert", text_value)
        end = real.index("insert")

        weight = "bold" if self.state["bold"] > 0 else "normal"
        slant = "italic" if self.state["italic"] > 0 else "roman"
        size = self.state["size"] if self.state["size"] is not None else DEFAULT_FONT_SIZE
        if weight != "normal" or slant != "roman" or size != DEFAULT_FONT_SIZE:
            tag_name = _ensure_combo_tag(widget, weight, slant, size)
            real.tag_add(tag_name, start, end)

        if self.state["underline"] > 0:
            real.tag_add("underline", start, end)
        if self.state["highlight"] > 0:
            real.tag_add("highlight", start, end)
        if self.state["href"]:
            _link_counter["n"] += 1
            link_tag = f"link_{_link_counter['n']}"
            real.tag_config(link_tag, foreground=LINK_COLOR, underline=True)
            real.tag_add(link_tag, start, end)
            self.link_urls[link_tag] = self.state["href"]


def insert_html(widget, html_str: str, link_urls: dict) -> None:
    """Parses `html_str` and inserts it at the current cursor/selection."""
    parser = _FragmentParser(widget, link_urls)
    parser.feed(html_str or "")
    parser.close()


def render_html(widget, html_str: str, link_urls: dict) -> None:
    """Clears the widget and re-renders `html_str` as WYSIWYG content."""
    real = _real(widget)
    real.delete("1.0", "end")
    link_urls.clear()
    insert_html(widget, html_str, link_urls)


# ---------------------------------------------------------------------------
# Text widget -> HTML
# ---------------------------------------------------------------------------

def _open_close_for(tag: str, link_urls: dict):
    """Returns (open_html, close_html) for a known tag, or None to ignore it
    (e.g. tkinter's own "sel" tag)."""
    if tag.startswith("combo_"):
        _, weight, slant, size = tag.split("_")
        size = int(size)
        opens, closes = [], []
        if size != DEFAULT_FONT_SIZE:
            opens.append(f'<span style="font-size: {size}pt;">')
            closes.append("</span>")
        if slant == "italic":
            opens.append("<i>")
            closes.append("</i>")
        if weight == "bold":
            opens.append("<b>")
            closes.append("</b>")
        return "".join(opens), "".join(reversed(closes))
    if tag == "underline":
        return "<u>", "</u>"
    if tag == "highlight":
        return f'<span style="background-color: {HIGHLIGHT_COLOR};">', "</span>"
    if tag.startswith("link_"):
        url = html_lib.escape(link_urls.get(tag, "#"), quote=True)
        return f'<a href="{url}">', "</a>"
    return None


def extract_html(widget, link_urls: dict) -> str:
    """Walks the widget's tag ranges and serializes them to an HTML string,
    correctly re-nesting tags whose ranges overlap non-hierarchically."""
    real = _real(widget)
    events = real.dump("1.0", "end-1c", tag=True, text=True)

    stack = []  # list of (tk_tag, open_html, close_html), innermost last
    out = []

    for key, value, _index in events:
        if key == "tagon":
            pair = _open_close_for(value, link_urls)
            if pair is None:
                continue
            open_html, close_html = pair
            stack.append((value, open_html, close_html))
            out.append(open_html)
        elif key == "tagoff":
            pair = _open_close_for(value, link_urls)
            if pair is None:
                continue
            pos = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == value), None)
            if pos is None:
                continue
            to_reopen = []
            for i in range(len(stack) - 1, pos - 1, -1):
                out.append(stack[i][2])
                if i != pos:
                    to_reopen.append(stack[i])
            del stack[pos:]
            for item in reversed(to_reopen):
                out.append(item[1])
                stack.append(item)
        elif key == "text":
            out.append(html_lib.escape(value).replace("\n", "<br>\n"))

    # dump() doesn't emit a "tagoff" for a tag that runs all the way to the
    # end of the requested range — force-close anything still open.
    for _tk_tag, _open_html, close_html in reversed(stack):
        out.append(close_html)

    return "".join(out)
