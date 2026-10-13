# src/views/run_summary_modal.py
"""End-of-run results window, shown instead of a plain warning popup when a
run has any failed or skipped steps. Lists every one by student so the
professor can handle them manually. A messagebox can't scroll, so a long
list of failures would run off the screen; this can.

The daily log file is the backup if this window gets closed by accident.
"""
from typing import List

import customtkinter as ctk


class RunSummaryModal(ctk.CTkToplevel):
    def __init__(self, master, title: str, message: str, issue_lines: List[str]):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.geometry(f"640x{min(520, self.winfo_screenheight() - 120)}")
        self.minsize(420, 320)

        self.report_text = "\n".join(issue_lines)

        ctk.CTkLabel(self, text=message, justify="left", anchor="w").pack(fill="x", padx=15, pady=(15, 5))

        # Packed side="bottom" before the list, so a long list can never
        # push the buttons out of view (same lesson as ReviewSendModal).
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=15, pady=15)
        self.close_button = ctk.CTkButton(btn_row, text="Close", command=self.destroy)
        self.close_button.pack(side="right")
        self.copy_button = ctk.CTkButton(
            btn_row, text="📋 Copy List", fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self._copy_to_clipboard,
        )
        self.copy_button.pack(side="right", padx=(0, 8))

        ctk.CTkLabel(
            self, text="Needs manual follow-up:", font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(10, 2))

        self.issues_box = ctk.CTkTextbox(self, wrap="word")
        self.issues_box.pack(fill="both", expand=True, padx=15)
        self.issues_box.insert("0.0", self.report_text)
        self.issues_box.configure(state="disabled")  # read-only, still selectable

    def _copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.report_text)
        self.copy_button.configure(text="✔ Copied")
