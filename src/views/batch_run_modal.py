# src/views/batch_run_modal.py
"""Modal for selecting an ordered batch of existing Actions (from any
groups) to run consecutively - a HandBrake-style job queue. Selection is
purely ad hoc, decided at run time; nothing about it is persisted on
Group or Action - that's the point (see docs/filter_engine_requirements.md
and the CLAUDE.md design-decisions discussion of this feature).
"""
import customtkinter as ctk
from typing import Callable, Dict, List, Optional

from src.models.action import Action
from src.models.group import Group


class BatchRunModal(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        actions: List[Action],
        groups: List[Group],
        on_run: Optional[Callable[[List[Action], List[str]], None]] = None,
    ):
        super().__init__(master)
        self.title("Run Action Batch")
        self.geometry("700x550")
        self.transient(master)
        self.grab_set()

        self._actions_by_id: Dict[str, Action] = {a.id: a for a in actions}
        self._group_name_by_id: Dict[str, str] = {g.id: g.name for g in groups}
        self._selected_ids: List[str] = []  # order here = run order
        self._checkbox_vars: Dict[str, ctk.StringVar] = {}
        self._on_run = on_run

        header = ctk.CTkLabel(
            self, text="Select actions to run, then arrange the order",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        header.pack(anchor="w", padx=15, pady=(15, 5))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # --- Left: every available action, across all groups ---
        left_frame = ctk.CTkFrame(body)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(left_frame, text="Available Actions", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        self.available_list = ctk.CTkScrollableFrame(left_frame, fg_color="transparent")
        self.available_list.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        for action in actions:
            group_name = self._group_name_by_id.get(action.group_id, "Unknown Group")
            var = ctk.StringVar(value="off")
            checkbox = ctk.CTkCheckBox(
                self.available_list, text=f"{group_name} — {action.name}",
                variable=var, onvalue="on", offvalue="off",
                command=lambda a=action, v=var: self._on_checkbox_toggled(a, v),
            )
            checkbox.pack(anchor="w", pady=2)
            self._checkbox_vars[action.id] = var

        # --- Right: selected actions, in run order ---
        right_frame = ctk.CTkFrame(body)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(right_frame, text="Run Order", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        self.selected_list = ctk.CTkScrollableFrame(right_frame, fg_color="transparent")
        self.selected_list.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # --- Footer ---
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(
            footer, text="Cancel", width=100, fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self.destroy,
        ).pack(side="left")
        self.run_button = ctk.CTkButton(
            footer, text="▶ Run Batch", width=140, command=self._handle_run_clicked
        )
        self.run_button.pack(side="right")

    def _on_checkbox_toggled(self, action: Action, var: ctk.StringVar) -> None:
        if var.get() == "on":
            if action.id not in self._selected_ids:
                self._selected_ids.append(action.id)
        else:
            self._selected_ids = [aid for aid in self._selected_ids if aid != action.id]
        self._render_selected_list()

    def _render_selected_list(self) -> None:
        for widget in self.selected_list.winfo_children():
            widget.destroy()

        for index, action_id in enumerate(self._selected_ids):
            action = self._actions_by_id[action_id]
            group_name = self._group_name_by_id.get(action.group_id, "Unknown Group")

            row = ctk.CTkFrame(self.selected_list, fg_color="transparent")
            row.pack(fill="x", pady=2)

            label = ctk.CTkLabel(row, text=f"{index + 1}. {group_name} — {action.name}", anchor="w")
            label.pack(side="left", fill="x", expand=True)

            ctk.CTkButton(
                row, text="▲", width=26, command=lambda i=index: self._move(i, -1)
            ).pack(side="left", padx=(2, 0))
            ctk.CTkButton(
                row, text="▼", width=26, command=lambda i=index: self._move(i, 1)
            ).pack(side="left", padx=(2, 0))
            ctk.CTkButton(
                row, text="✖", width=26, fg_color="transparent", hover_color="#331111",
                command=lambda aid=action_id: self._remove_selected(aid),
            ).pack(side="left", padx=(2, 0))

    def _move(self, index: int, direction: int) -> None:
        new_index = index + direction
        if 0 <= new_index < len(self._selected_ids):
            self._selected_ids[index], self._selected_ids[new_index] = (
                self._selected_ids[new_index], self._selected_ids[index],
            )
            self._render_selected_list()

    def _remove_selected(self, action_id: str) -> None:
        self._selected_ids = [aid for aid in self._selected_ids if aid != action_id]
        if action_id in self._checkbox_vars:
            self._checkbox_vars[action_id].set("off")
        self._render_selected_list()

    def _handle_run_clicked(self) -> None:
        if not self._selected_ids:
            return
        selected_actions = [self._actions_by_id[aid] for aid in self._selected_ids]
        group_names = [self._group_name_by_id.get(a.group_id, "") for a in selected_actions]
        if self._on_run:
            self._on_run(selected_actions, group_names)
        self.destroy()
