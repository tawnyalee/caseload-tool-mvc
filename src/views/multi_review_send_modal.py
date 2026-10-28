# src/views/multi_review_send_modal.py
"""Pre-run review dialog for a multi-item send - batch runs and welcome
emails, both of which fire across several (Action, group) pairs in one
operation. Unlike ReviewSendModal (the single-item version used for a
single Action run or ad-hoc email), there's no email-content editing here
- if the content needs changing, that's done on the Action itself
beforehand (the developer's explicit call: this dialog is just "who's
about to be contacted by course code, deselect anyone who shouldn't be").

Students are shown grouped under one section per item (each item already
targets one course/group), with per-section Select All/None. Confirming
hands back a {key: {selected student IDs}} dict the caller passes through
to ActionRunner.run_batch()'s included_ids_by_index or
run_welcome_emails()'s included_ids_by_group_id.
"""
import tkinter.messagebox as messagebox
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from src.models.student import Student


@dataclass
class ReviewItem:
    key: str  # batch: str(index); welcome emails: group.id
    label: str  # e.g. "D424 — Welcome Action"
    students: List[Student]


class MultiReviewSendModal(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        title: str,
        items: List[ReviewItem],
        on_confirm: Optional[Callable[[Dict[str, set]], None]] = None,
    ):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()

        self.on_confirm = on_confirm
        self._items = items
        # {item.key: {student.salesforce_id: ctk.StringVar}}
        self._check_vars: Dict[str, Dict[str, ctk.StringVar]] = {}

        target_height = min(650, self.winfo_screenheight() - 120)
        self.geometry(f"620x{target_height}")
        self.minsize(420, 320)

        total_students = sum(len(item.students) for item in items)
        ctk.CTkLabel(
            self, text=f"{title} — {total_students} student(s) across {len(items)} item(s)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))

        # Packed side="bottom" first, before the scrollable content below,
        # so Confirm/Cancel always claim their space and stay visible
        # regardless of how many items/students are being reviewed (see
        # the same fix in review_send_modal.py for why this matters).
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=15, pady=15)
        self.cancel_button = ctk.CTkButton(
            btn_row, text="Cancel", fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self.destroy,
        )
        self.cancel_button.pack(side="left")
        self.confirm_button = ctk.CTkButton(btn_row, text="Run", command=self._on_confirm)
        self.confirm_button.pack(side="right")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        for item in items:
            self._build_item_section(scroll, item)

    def _build_item_section(self, parent, item: ReviewItem) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 2))
        ctk.CTkLabel(
            header, text=f"{item.label} — {len(item.students)} student(s)",
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left")

        if not item.students:
            self._check_vars[item.key] = {}
            return

        select_row = ctk.CTkFrame(section, fg_color="transparent")
        select_row.pack(fill="x", padx=10)
        ctk.CTkButton(
            select_row, text="Select All", width=90, command=lambda k=item.key: self._select_all(k)
        ).pack(side="left")
        ctk.CTkButton(
            select_row, text="Select None", width=90, command=lambda k=item.key: self._select_none(k)
        ).pack(side="left", padx=(5, 0))

        self._check_vars[item.key] = {}
        for student in item.students:
            var = ctk.StringVar(value="on")
            self._check_vars[item.key][student.salesforce_id] = var
            ctk.CTkCheckBox(
                section, text=f"{student.full_name}  (ID: {student.salesforce_id})",
                variable=var, onvalue="on", offvalue="off",
            ).pack(anchor="w", padx=20, pady=2)

    def _select_all(self, key: str) -> None:
        for var in self._check_vars[key].values():
            var.set("on")

    def _select_none(self, key: str) -> None:
        for var in self._check_vars[key].values():
            var.set("off")

    def _on_confirm(self) -> None:
        selections = {
            key: {sid for sid, var in vars_by_id.items() if var.get() == "on"}
            for key, vars_by_id in self._check_vars.items()
        }
        if not any(selections.values()):
            messagebox.showwarning("No Students Selected", "Select at least one student, or Cancel.")
            return

        # Close first; see ReviewSendModal._on_send for why.
        self.destroy()
        if self.on_confirm:
            self.on_confirm(selections)
