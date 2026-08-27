# src/views/dashboard_view.py
import customtkinter as ctk
import tkinter.messagebox as messagebox
from src.services import html_richtext as rt
from src.services.outlook_signature_provider import get_signature_names_or_fallback


class DashboardView(ctk.CTkFrame):
    """Three sections, top to bottom: Welcome Emails, Run Action Batch, then
    Send Email to All Students (with an identical note section to a regular
    Action's note step - not a separate dialog, per developer feedback
    after manual testing). Batch sits right under Welcome Emails, above the
    much longer ad-hoc email section, so it's never scrolled out of view -
    also feedback from manual testing."""

    def __init__(self, master=None, controller=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.controller = controller
        self._link_urls = {}

        title = ctk.CTkLabel(self, text="📊 Dashboard", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(anchor="w", padx=20, pady=(20, 10))

        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_container.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Section 1: Welcome Emails ---
        self._build_section_header("✉️ Welcome Emails")
        self.btn_send_welcome = ctk.CTkButton(
            self.scrollable_container,
            text="✉️ Send Welcome Emails",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self._on_send_welcome_clicked,
        )
        self.btn_send_welcome.pack(anchor="w", padx=20, pady=(0, 10))

        self._build_divider()

        # --- Section 2: Run Action Batch ---
        self._build_section_header("🗂️ Run Action Batch")
        batch_hint = ctk.CTkLabel(
            self.scrollable_container,
            text=(
                "To run multiple actions in one batch, select the actions "
                "you'd like to run and arrange the order, then confirm "
                "before clicking Run."
            ),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=500,
            justify="left",
        )
        batch_hint.pack(anchor="w", padx=20, pady=(0, 8))
        self.btn_run_batch = ctk.CTkButton(
            self.scrollable_container,
            text="🗂️ Run Action Batch",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self._on_run_batch_clicked,
        )
        self.btn_run_batch.pack(anchor="w", padx=20, pady=(0, 20))

        self._build_divider()

        # --- Section 3: Send Email to All Students (inline, not a modal) ---
        self._build_section_header("📢 Send Email to All Students")
        signature_provider = getattr(controller, "signature_provider", None)
        self._build_ad_hoc_email_section(get_signature_names_or_fallback(signature_provider))

    # =========================================================================
    # LAYOUT HELPERS
    # =========================================================================
    def _build_section_header(self, text: str) -> None:
        lbl = ctk.CTkLabel(self.scrollable_container, text=text, font=ctk.CTkFont(size=16, weight="bold"))
        lbl.pack(anchor="w", padx=20, pady=(10, 8))

    def _build_divider(self) -> None:
        divider = ctk.CTkFrame(self.scrollable_container, height=2, fg_color=("gray70", "gray30"))
        divider.pack(fill="x", padx=20, pady=15)

    def _build_ad_hoc_email_section(self, signature_names) -> None:
        c = self.scrollable_container

        ctk.CTkLabel(c, text="Subject", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(0, 2))
        self.adhoc_subject = ctk.CTkEntry(c, placeholder_text="e.g., Class Canceled Today", width=400)
        self.adhoc_subject.pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(c, text="Select Outlook Signature:", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=20, pady=(0, 2)
        )
        self.adhoc_signature_dropdown = ctk.CTkComboBox(
            c, values=signature_names or ["No Outlook signatures found"], width=220
        )
        self.adhoc_signature_dropdown.pack(anchor="w", padx=20, pady=(0, 10))

        toolbar = ctk.CTkFrame(c, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(0, 5))

        self.adhoc_btn_bold = ctk.CTkButton(
            toolbar, text="B", width=30, font=ctk.CTkFont(weight="bold"), command=self._on_adhoc_bold_click
        )
        self.adhoc_btn_bold.pack(side="left", padx=(0, 2))
        self.adhoc_btn_italic = ctk.CTkButton(
            toolbar, text="I", width=30, font=ctk.CTkFont(slant="italic"), command=self._on_adhoc_italic_click
        )
        self.adhoc_btn_italic.pack(side="left", padx=2)
        self.adhoc_btn_underline = ctk.CTkButton(
            toolbar, text="U", width=30, font=ctk.CTkFont(underline=True), command=self._on_adhoc_underline_click
        )
        self.adhoc_btn_underline.pack(side="left", padx=2)
        self.adhoc_btn_highlight = ctk.CTkButton(
            toolbar, text="🖍 Highlight", width=90, command=self._on_adhoc_highlight_click
        )
        self.adhoc_btn_highlight.pack(side="left", padx=2)
        self.adhoc_btn_link = ctk.CTkButton(toolbar, text="🔗 Link", width=60, command=self._on_adhoc_insert_link)
        self.adhoc_btn_link.pack(side="left", padx=2)

        ctk.CTkLabel(c, text="Message", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.adhoc_body_text = ctk.CTkTextbox(c, height=200, wrap="word")
        self.adhoc_body_text.pack(fill="x", padx=20, pady=(0, 10))
        rt.configure_base_tags(self.adhoc_body_text)

        # Note section - identical fields to a regular Action's note step
        # (AddActionView's note_subject/note_body/followup_note), so a
        # broadcast email can always be logged the same way any other
        # student contact is.
        ctk.CTkLabel(c, text="📝 Note Details (optional):", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=20, pady=(10, 5)
        )

        ctk.CTkLabel(c, text="Enter Subject Line for Note:").pack(anchor="w", padx=20, pady=(0, 2))
        self.adhoc_note_subject = ctk.CTkEntry(c, placeholder_text="Note Subject", width=320)
        self.adhoc_note_subject.pack(anchor="w", padx=20, pady=(0, 5))

        ctk.CTkLabel(c, text="Enter Body of Note:").pack(anchor="w", padx=20, pady=(0, 2))
        self.adhoc_note_body = ctk.CTkTextbox(c, height=60)
        self.adhoc_note_body.pack(fill="x", padx=20, pady=(0, 5))

        ctk.CTkLabel(c, text="Enter Follow-up Note for Main Roster View:").pack(anchor="w", padx=20, pady=(0, 2))
        self.adhoc_followup_note = ctk.CTkEntry(c, placeholder_text="Follow-up Note", width=320)
        self.adhoc_followup_note.pack(anchor="w", padx=20, pady=(0, 10))

        self.btn_send_all = ctk.CTkButton(
            c, text="📤 Send Email to All Students", height=40,
            font=ctk.CTkFont(weight="bold"), command=self._on_send_all_clicked,
        )
        self.btn_send_all.pack(anchor="w", padx=20, pady=(0, 20))

    # =========================================================================
    # WYSIWYG TOOLBAR (mirrors AdHocEmailModal / template editor)
    # =========================================================================
    def _get_adhoc_selection_range(self):
        try:
            return self.adhoc_body_text.index("sel.first"), self.adhoc_body_text.index("sel.last")
        except Exception:
            return None, None

    def _on_adhoc_bold_click(self) -> None:
        sel_first, sel_last = self._get_adhoc_selection_range()
        if sel_first and sel_last:
            rt.toggle_bold(self.adhoc_body_text, sel_first, sel_last)

    def _on_adhoc_italic_click(self) -> None:
        sel_first, sel_last = self._get_adhoc_selection_range()
        if sel_first and sel_last:
            rt.toggle_italic(self.adhoc_body_text, sel_first, sel_last)

    def _on_adhoc_underline_click(self) -> None:
        sel_first, sel_last = self._get_adhoc_selection_range()
        if sel_first and sel_last:
            rt.toggle_underline(self.adhoc_body_text, sel_first, sel_last)

    def _on_adhoc_highlight_click(self) -> None:
        sel_first, sel_last = self._get_adhoc_selection_range()
        if sel_first and sel_last:
            rt.toggle_highlight(self.adhoc_body_text, sel_first, sel_last)

    def _on_adhoc_insert_link(self) -> None:
        sel_first, sel_last = self._get_adhoc_selection_range()
        default_text = self.adhoc_body_text.get(sel_first, sel_last) if sel_first and sel_last else ""

        dialog = ctk.CTkInputDialog(text="Enter the URL for this link:", title="Insert Link")
        url = dialog.get_input()
        if not url:
            return

        if sel_first and sel_last:
            self.adhoc_body_text.delete(sel_first, sel_last)

        link_text = default_text if default_text else url
        start = self.adhoc_body_text.index("insert")
        self.adhoc_body_text.insert("insert", link_text)
        end = self.adhoc_body_text.index("insert")
        rt.add_link(self.adhoc_body_text, start, end, url, self._link_urls)

    # =========================================================================
    # BUTTON HANDLERS
    # =========================================================================
    def _on_send_welcome_clicked(self) -> None:
        if self.controller and hasattr(self.controller, "handle_send_welcome_emails"):
            self.controller.handle_send_welcome_emails()

    def _on_send_all_clicked(self) -> None:
        subject = self.adhoc_subject.get().strip()
        if not subject:
            messagebox.showwarning("Validation Error", "Subject cannot be empty.")
            return

        body = rt.extract_html(self.adhoc_body_text, self._link_urls)
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

        if self.controller and hasattr(self.controller, "handle_send_ad_hoc_email"):
            self.controller.handle_send_ad_hoc_email(
                subject=subject,
                body=body,
                signature=self.adhoc_signature_dropdown.get(),
                note_subject=self.adhoc_note_subject.get(),
                note_body=self.adhoc_note_body.get("0.0", "end-1c"),
                follow_up_note=self.adhoc_followup_note.get(),
            )

    def _on_run_batch_clicked(self) -> None:
        if self.controller and hasattr(self.controller, "handle_open_batch_runner"):
            self.controller.handle_open_batch_runner()
