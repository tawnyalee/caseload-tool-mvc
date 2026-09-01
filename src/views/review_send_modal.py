# src/views/review_send_modal.py
"""Pre-send review dialog for a single Action run or the dashboard's ad-hoc
email: shows who a send would reach before it actually goes out, lets the
professor deselect individual students, and (when the send includes email
content) lets them make a last-minute edit to the subject/body for this
send only - it does not touch the saved Action or template. The
multi-item batch/welcome-emails version (grouped by course code, no
editable email content - see src/CLAUDE.md) is a separate, simpler dialog.
"""
import tkinter.messagebox as messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

from src.models.student import Student
from src.services import html_richtext as rt


class ReviewSendModal(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        title: str,
        students: List[Student],
        is_email: bool,
        initial_subject: str = "",
        initial_body: str = "",
        on_confirm: Optional[Callable[[set, str, str], None]] = None,
    ):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()

        self.on_confirm = on_confirm
        self._link_urls = {}
        self._check_vars = {}
        self.subject_entry = None
        self.body_text = None
        self.send_button = None
        self.cancel_button = None

        if not students:
            self.geometry("420x160")
            ctk.CTkLabel(
                self, text="0 students currently meet these conditions",
                font=ctk.CTkFont(size=14, weight="bold"), justify="center",
            ).pack(expand=True, padx=20, pady=20)
            ctk.CTkButton(self, text="Close", command=self.destroy).pack(pady=(0, 15))
            return

        # Capped against the actual screen height (minus room for the
        # taskbar/title bar) so this can never request a window taller than
        # what physically fits - a fixed 680px request was taller than
        # every other modal in this app (BatchRunModal: 550, TemplateEditorModal:
        # 520) and could run off the bottom of a smaller/laptop screen with
        # the Send/Cancel row along with it.
        target_height = min(600, self.winfo_screenheight() - 120) if is_email else min(450, self.winfo_screenheight() - 120)
        self.geometry(f"600x{target_height}" if is_email else f"500x{target_height}")
        self.minsize(420, 320)

        ctk.CTkLabel(
            self, text=f"{title} — {len(students)} student(s) will be contacted",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))

        # Packed with side="bottom" right after the header, BEFORE the
        # scrollable list / email fields below - this claims its space at
        # the bottom of the window first, so Cancel/Send stay visible even
        # if the rest of the content overflows or an error interrupts
        # building it (see _on_send below and the html_richtext rendering
        # of a real template body, which is far less predictable than the
        # simple test fixtures this was built against).
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=15, pady=15)
        self.cancel_button = ctk.CTkButton(
            btn_row, text="Cancel", fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self.destroy,
        )
        self.cancel_button.pack(side="left")
        self.send_button = ctk.CTkButton(btn_row, text="Send", command=self._on_send)
        self.send_button.pack(side="right")

        select_row = ctk.CTkFrame(self, fg_color="transparent")
        select_row.pack(fill="x", padx=15)
        ctk.CTkButton(select_row, text="Select All", width=90, command=self._select_all).pack(side="left")
        ctk.CTkButton(select_row, text="Select None", width=90, command=self._select_none).pack(
            side="left", padx=(5, 0)
        )

        list_frame = ctk.CTkScrollableFrame(self, height=120)
        list_frame.pack(fill="both", expand=not is_email, padx=15, pady=(5, 10))

        for student in students:
            var = ctk.StringVar(value="on")
            self._check_vars[student.salesforce_id] = var
            ctk.CTkCheckBox(
                list_frame, text=f"{student.full_name}  (ID: {student.salesforce_id})",
                variable=var, onvalue="on", offvalue="off",
            ).pack(anchor="w", pady=2)

        if is_email:
            ctk.CTkLabel(self, text="Subject", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15)
            self.subject_entry = ctk.CTkEntry(self, width=400)
            self.subject_entry.pack(fill="x", padx=15, pady=(0, 10))
            if initial_subject:
                self.subject_entry.insert(0, initial_subject)

            ctk.CTkLabel(self, text="Body", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15)
            self.body_text = ctk.CTkTextbox(self, height=180, wrap="word")
            self.body_text.pack(fill="both", expand=True, padx=15, pady=(0, 2))
            rt.configure_base_tags(self.body_text)
            rt.render_html(self.body_text, initial_body, self._link_urls)

            ctk.CTkLabel(
                self,
                text="Fields like {{student_name}} will be personalized for each student when sent.",
                text_color=("gray40", "gray60"), font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=15, pady=(2, 5))

    def _select_all(self):
        for var in self._check_vars.values():
            var.set("on")

    def _select_none(self):
        for var in self._check_vars.values():
            var.set("off")

    def _on_send(self):
        selected_ids = {sid for sid, var in self._check_vars.items() if var.get() == "on"}
        if not selected_ids:
            messagebox.showwarning("No Students Selected", "Select at least one student, or Cancel.")
            return

        subject = self.subject_entry.get() if self.subject_entry else ""
        body = rt.extract_html(self.body_text, self._link_urls) if self.body_text else ""

        if self.on_confirm:
            self.on_confirm(selected_ids, subject, body)
        self.destroy()
