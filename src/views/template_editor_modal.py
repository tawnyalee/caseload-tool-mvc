# src/views/template_editor_modal.py
import customtkinter as ctk
import tkinter.messagebox as messagebox
import win32clipboard
from src.services import html_richtext as rt


def _get_clipboard_html():
    """Reads the Windows 'HTML Format' clipboard flavor and returns the copied
    HTML fragment as a string, or None if no HTML content is on the clipboard."""
    try:
        win32clipboard.OpenClipboard()
        cf_html = win32clipboard.RegisterClipboardFormat("HTML Format")
        if not win32clipboard.IsClipboardFormatAvailable(cf_html):
            return None
        raw = win32clipboard.GetClipboardData(cf_html)
    except Exception:
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass

    if raw is None:
        return None

    raw_bytes = raw.encode("utf-8", errors="replace") if isinstance(raw, str) else raw
    header_text = raw_bytes.decode("utf-8", errors="replace")

    def _find_offset(marker):
        idx = header_text.find(marker)
        if idx == -1:
            return None
        line_end = header_text.find("\n", idx)
        return int(header_text[idx + len(marker):line_end].strip())

    start_idx = _find_offset("StartFragment:")
    end_idx = _find_offset("EndFragment:")
    if start_idx is None or end_idx is None:
        return None

    return raw_bytes[start_idx:end_idx].decode("utf-8", errors="replace")


class TemplateEditorModal(ctk.CTkToplevel):
    def __init__(self, master, template_id=None, template_name="", template_body="", on_save_callback=None):
        super().__init__(master)
        self.title("Template Editor")
        self.geometry("600x520")
        self.template_id = template_id
        self.on_save_callback = on_save_callback
        self._link_urls = {}
        self._raw_mode = False

        self.transient(master)
        self.grab_set()

        # Title / Name Entry
        lbl_name = ctk.CTkLabel(self, text="Template Name", font=ctk.CTkFont(weight="bold"))
        lbl_name.pack(anchor="w", padx=15, pady=(15, 2))

        self.name_entry = ctk.CTkEntry(self, placeholder_text="e.g., Welcome Email Body")
        self.name_entry.pack(fill="x", padx=15, pady=(0, 10))
        if template_name:
            self.name_entry.insert(0, template_name)

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(0, 5))

        self.btn_bold = ctk.CTkButton(
            toolbar, text="B", width=30, font=ctk.CTkFont(weight="bold"),
            command=self._on_bold_click
        )
        self.btn_bold.pack(side="left", padx=(0, 2))

        self.btn_italic = ctk.CTkButton(
            toolbar, text="I", width=30, font=ctk.CTkFont(slant="italic"),
            command=self._on_italic_click
        )
        self.btn_italic.pack(side="left", padx=2)

        self.btn_underline = ctk.CTkButton(
            toolbar, text="U", width=30, font=ctk.CTkFont(underline=True),
            command=self._on_underline_click
        )
        self.btn_underline.pack(side="left", padx=2)

        self.btn_highlight = ctk.CTkButton(toolbar, text="🖍 Highlight", width=90, command=self._on_highlight_click)
        self.btn_highlight.pack(side="left", padx=2)

        self.btn_link = ctk.CTkButton(toolbar, text="🔗 Link", width=60, command=self._insert_link)
        self.btn_link.pack(side="left", padx=2)

        self.font_size_var = ctk.StringVar(value="Font Size")
        self.font_size_menu = ctk.CTkOptionMenu(
            toolbar, values=["10pt", "12pt", "14pt", "18pt", "24pt"],
            variable=self.font_size_var, width=100, command=self._apply_font_size
        )
        self.font_size_menu.pack(side="left", padx=2)

        self.btn_toggle_html = ctk.CTkButton(
            toolbar, text="🔤 View HTML", width=100, fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self._on_toggle_raw_html
        )
        self.btn_toggle_html.pack(side="left", padx=(10, 2))

        # Body Textbox — shows formatted (WYSIWYG) text by default; "View HTML"
        # toggles to the raw markup for HTML-literate professors.
        lbl_body = ctk.CTkLabel(self, text="Template Content", font=ctk.CTkFont(weight="bold"))
        lbl_body.pack(anchor="w", padx=15, pady=(5, 2))

        self.body_text = ctk.CTkTextbox(self, height=300, wrap="word")
        self.body_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        rt.configure_base_tags(self.body_text)
        rt.render_html(self.body_text, template_body, self._link_urls)

        self.body_text.bind("<<Paste>>", self._on_paste)
        self.body_text.bind("<Control-v>", self._on_paste)
        self.body_text.bind("<Control-V>", self._on_paste)

        # Save / Cancel
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self.destroy
        )
        btn_cancel.pack(side="left")

        btn_save = ctk.CTkButton(btn_frame, text="💾 Save Template", command=self._on_save)
        btn_save.pack(side="right")

    # ---- Selection helpers ----
    def _get_selection_range(self):
        try:
            return self.body_text.index("sel.first"), self.body_text.index("sel.last")
        except Exception:
            return None, None

    # ---- WYSIWYG formatting (no-ops without a selection — nothing to format) ----
    def _on_bold_click(self):
        sel_first, sel_last = self._get_selection_range()
        if sel_first and sel_last:
            rt.toggle_bold(self.body_text, sel_first, sel_last)

    def _on_italic_click(self):
        sel_first, sel_last = self._get_selection_range()
        if sel_first and sel_last:
            rt.toggle_italic(self.body_text, sel_first, sel_last)

    def _on_underline_click(self):
        sel_first, sel_last = self._get_selection_range()
        if sel_first and sel_last:
            rt.toggle_underline(self.body_text, sel_first, sel_last)

    def _on_highlight_click(self):
        sel_first, sel_last = self._get_selection_range()
        if sel_first and sel_last:
            rt.toggle_highlight(self.body_text, sel_first, sel_last)

    def _apply_font_size(self, size_choice: str):
        sel_first, sel_last = self._get_selection_range()
        if sel_first and sel_last:
            size_pt = int(size_choice.rstrip("pt"))
            rt.set_font_size(self.body_text, sel_first, sel_last, size_pt)
        self.font_size_var.set("Font Size")

    def _insert_link(self):
        if self._raw_mode:
            return  # link tagging only applies to the formatted view

        sel_first, sel_last = self._get_selection_range()
        default_text = self.body_text.get(sel_first, sel_last) if sel_first and sel_last else ""

        dialog = ctk.CTkInputDialog(text="Enter the URL for this link:", title="Insert Link")
        url = dialog.get_input()
        if not url:
            return

        if sel_first and sel_last:
            self.body_text.delete(sel_first, sel_last)

        link_text = default_text if default_text else url
        start = self.body_text.index("insert")
        self.body_text.insert("insert", link_text)
        end = self.body_text.index("insert")
        rt.add_link(self.body_text, start, end, url, self._link_urls)

    # ---- Raw HTML toggle (for HTML-literate professors) ----
    def _set_toolbar_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.btn_bold, self.btn_italic, self.btn_underline, self.btn_highlight,
                       self.btn_link, self.font_size_menu):
            widget.configure(state=state)

    def _on_toggle_raw_html(self):
        if self._raw_mode:
            raw_html = self.body_text.get("1.0", "end-1c")
            rt.render_html(self.body_text, raw_html, self._link_urls)
            self._raw_mode = False
            self.btn_toggle_html.configure(text="🔤 View HTML")
            self._set_toolbar_enabled(True)
        else:
            html_str = rt.extract_html(self.body_text, self._link_urls)
            self.body_text.delete("1.0", "end")
            self.body_text.insert("1.0", html_str)
            self._raw_mode = True
            self.btn_toggle_html.configure(text="🖋 View Formatted")
            self._set_toolbar_enabled(False)

    # ---- Clipboard paste (preserves formatting/links from Outlook/OneNote/etc.) ----
    def _on_paste(self, event=None):
        if self._raw_mode:
            return None  # plain-text paste is fine while viewing raw HTML

        html_fragment = _get_clipboard_html()
        if html_fragment:
            sel_first, sel_last = self._get_selection_range()
            if sel_first and sel_last:
                self.body_text.delete(sel_first, sel_last)
            rt.insert_html(self.body_text, html_fragment, self._link_urls)
            return "break"  # prevent the default plain-text paste from also firing

        return None  # no HTML on clipboard — let normal plain-text paste happen

    # ---- Save ----
    def _on_save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Validation Error", "Template name cannot be empty.")
            return

        if self._raw_mode:
            body = self.body_text.get("1.0", "end-1c")
        else:
            body = rt.extract_html(self.body_text, self._link_urls)

        if self.on_save_callback:
            self.on_save_callback(self.template_id, name, body)
        self.destroy()