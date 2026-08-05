# src/views/ad_hoc_email_modal.py
import customtkinter as ctk
import tkinter.messagebox as messagebox
from src.services import html_richtext as rt


class AdHocEmailModal(ctk.CTkToplevel):
    """One-off compose window for a broadcast email to every student — not
    tied to any saved Action or template. Reuses the same WYSIWYG editor as
    the template editor."""

    def __init__(self, master, on_send_callback=None):
        super().__init__(master)
        self.title("Send Email to All Students")
        self.geometry("600x520")
        self.on_send_callback = on_send_callback
        self._link_urls = {}

        self.transient(master)
        self.grab_set()

        lbl_subject = ctk.CTkLabel(self, text="Subject", font=ctk.CTkFont(weight="bold"))
        lbl_subject.pack(anchor="w", padx=15, pady=(15, 2))

        self.subject_entry = ctk.CTkEntry(self, placeholder_text="e.g., Class Canceled Today")
        self.subject_entry.pack(fill="x", padx=15, pady=(0, 10))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(0, 5))

        self.btn_bold = ctk.CTkButton(
            toolbar, text="B", width=30, font=ctk.CTkFont(weight="bold"), command=self._on_bold_click
        )
        self.btn_bold.pack(side="left", padx=(0, 2))

        self.btn_italic = ctk.CTkButton(
            toolbar, text="I", width=30, font=ctk.CTkFont(slant="italic"), command=self._on_italic_click
        )
        self.btn_italic.pack(side="left", padx=2)

        self.btn_underline = ctk.CTkButton(
            toolbar, text="U", width=30, font=ctk.CTkFont(underline=True), command=self._on_underline_click
        )
        self.btn_underline.pack(side="left", padx=2)

        self.btn_highlight = ctk.CTkButton(toolbar, text="🖍 Highlight", width=90, command=self._on_highlight_click)
        self.btn_highlight.pack(side="left", padx=2)

        self.btn_link = ctk.CTkButton(toolbar, text="🔗 Link", width=60, command=self._insert_link)
        self.btn_link.pack(side="left", padx=2)

        lbl_body = ctk.CTkLabel(self, text="Message", font=ctk.CTkFont(weight="bold"))
        lbl_body.pack(anchor="w", padx=15, pady=(5, 2))

        self.body_text = ctk.CTkTextbox(self, height=300, wrap="word")
        self.body_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        rt.configure_base_tags(self.body_text)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self.destroy
        )
        btn_cancel.pack(side="left")

        btn_send = ctk.CTkButton(btn_frame, text="📤 Send to All Students", command=self._on_send)
        btn_send.pack(side="right")

    def _get_selection_range(self):
        try:
            return self.body_text.index("sel.first"), self.body_text.index("sel.last")
        except Exception:
            return None, None

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

    def _insert_link(self):
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

    def _on_send(self):
        subject = self.subject_entry.get().strip()
        if not subject:
            messagebox.showwarning("Validation Error", "Subject cannot be empty.")
            return

        body = rt.extract_html(self.body_text, self._link_urls)
        if not body.strip():
            messagebox.showwarning("Validation Error", "Message body cannot be empty.")
            return

        confirm = messagebox.askokcancel(
            "Send to All Students?",
            f"❗ This will send this email to EVERY student on the roster.\n\n"
            f"Subject: {subject}\n\nAre you sure?"
        )
        if not confirm:
            return

        if self.on_send_callback:
            self.on_send_callback(subject, body)
        self.destroy()
