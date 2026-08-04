# src/views/template_editor_modal.py
import customtkinter as ctk
import tkinter.messagebox as messagebox
import win32clipboard


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
            command=lambda: self._wrap_selection("<b>", "</b>")
        )
        self.btn_bold.pack(side="left", padx=(0, 2))

        self.btn_italic = ctk.CTkButton(
            toolbar, text="I", width=30, font=ctk.CTkFont(slant="italic"),
            command=lambda: self._wrap_selection("<i>", "</i>")
        )
        self.btn_italic.pack(side="left", padx=2)

        self.btn_underline = ctk.CTkButton(
            toolbar, text="U", width=30, font=ctk.CTkFont(underline=True),
            command=lambda: self._wrap_selection("<u>", "</u>")
        )
        self.btn_underline.pack(side="left", padx=2)

        self.btn_highlight = ctk.CTkButton(toolbar, text="🖍 Highlight", width=90, command=self._apply_highlight)
        self.btn_highlight.pack(side="left", padx=2)

        self.btn_link = ctk.CTkButton(toolbar, text="🔗 Link", width=60, command=self._insert_link)
        self.btn_link.pack(side="left", padx=2)

        self.font_size_var = ctk.StringVar(value="Font Size")
        self.font_size_menu = ctk.CTkOptionMenu(
            toolbar, values=["10pt", "12pt", "14pt", "18pt", "24pt"],
            variable=self.font_size_var, width=100, command=self._apply_font_size
        )
        self.font_size_menu.pack(side="left", padx=2)

        # Body Textbox — always shows raw HTML directly (no separate preview mode)
        lbl_body = ctk.CTkLabel(self, text="Template Content (HTML)", font=ctk.CTkFont(weight="bold"))
        lbl_body.pack(anchor="w", padx=15, pady=(5, 2))

        self.body_text = ctk.CTkTextbox(self, height=300, wrap="word")
        self.body_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        if template_body:
            self.body_text.insert("1.0", template_body)

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

    def _wrap_selection(self, open_tag, close_tag):
        sel_first, sel_last = self._get_selection_range()
        if sel_first and sel_last:
            selected_text = self.body_text.get(sel_first, sel_last)
            self.body_text.delete(sel_first, sel_last)
            self.body_text.insert(sel_first, f"{open_tag}{selected_text}{close_tag}")
        else:
            self.body_text.insert("insert", f"{open_tag}{close_tag}")

    def _apply_highlight(self):
        self._wrap_selection('<span style="background-color: yellow;">', "</span>")

    def _apply_font_size(self, size_choice: str):
        self._wrap_selection(f'<span style="font-size: {size_choice};">', "</span>")
        self.font_size_var.set("Font Size")

    def _insert_link(self):
        sel_first, sel_last = self._get_selection_range()
        default_text = self.body_text.get(sel_first, sel_last) if sel_first and sel_last else ""

        dialog = ctk.CTkInputDialog(text="Enter the URL for this link:", title="Insert Link")
        url = dialog.get_input()
        if not url:
            return

        link_text = default_text if default_text else url
        html_link = f'<a href="{url}">{link_text}</a>'

        if sel_first and sel_last:
            self.body_text.delete(sel_first, sel_last)
            self.body_text.insert(sel_first, html_link)
        else:
            self.body_text.insert("insert", html_link)

    # ---- Clipboard paste (preserves formatting/links from Outlook/OneNote/etc.) ----
    def _on_paste(self, event=None):
        html_fragment = _get_clipboard_html()
        if html_fragment:
            sel_first, sel_last = self._get_selection_range()
            if sel_first and sel_last:
                self.body_text.delete(sel_first, sel_last)
            self.body_text.insert("insert", html_fragment)
            return "break"  # prevent the default plain-text paste from also firing

        return None  # no HTML on clipboard — let normal plain-text paste happen

    # ---- Save ----
    def _on_save(self):
        name = self.name_entry.get().strip()
        body = self.body_text.get("1.0", "end-1c")

        if not name:
            messagebox.showwarning("Validation Error", "Template name cannot be empty.")
            return

        if self.on_save_callback:
            self.on_save_callback(self.template_id, name, body)
        self.destroy()