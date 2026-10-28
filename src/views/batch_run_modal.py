# src/views/batch_run_modal.py
"""Modal for selecting an ordered batch of existing Actions (from any
groups) to run consecutively - a HandBrake-style job queue. Running a
batch is still purely ad hoc, decided at run time; nothing about a run
itself is persisted on Group or Action (see docs/filter_engine_requirements.md
and the CLAUDE.md design-decisions discussion of this feature).

Saved Batches are a separate, additive feature on top of that: a
professor can name the CURRENT selection and store it (SavedBatch /
SavedBatchRepository) to reuse later without rebuilding it, or load a
previously saved one back into the picker to run/edit/re-save. Saving
never runs anything, and running never saves anything - the "Save Batch"
and "Run Batch" buttons are deliberately separate, explained inline so
that distinction is obvious in the UI (not just in code comments).
"""
import customtkinter as ctk
import tkinter.messagebox as messagebox
from typing import Callable, Dict, List, Optional

from src.models.action import Action
from src.models.group import Group
from src.models.saved_batch import SavedBatch

_NO_SAVED_BATCH_SELECTED = "— Select a saved batch —"
_NO_SAVED_BATCHES_YET = "(no saved batches yet)"


class BatchRunModal(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        actions: List[Action],
        groups: List[Group],
        on_run: Optional[Callable[[List[Action], List[str]], None]] = None,
        saved_batches: Optional[List[SavedBatch]] = None,
        on_save_batch: Optional[Callable[[str, List[str]], SavedBatch]] = None,
        on_delete_batch: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(master)
        self.title("Run Action Batch")
        self.geometry("720x610")
        self.transient(master)
        self.grab_set()

        self._actions_by_id: Dict[str, Action] = {a.id: a for a in actions}
        self._group_name_by_id: Dict[str, str] = {g.id: g.name for g in groups}
        self._selected_ids: List[str] = []  # order here = run order
        self._checkbox_vars: Dict[str, ctk.StringVar] = {}
        self._on_run = on_run

        self._saved_batches: List[SavedBatch] = list(saved_batches or [])
        self._on_save_batch = on_save_batch
        self._on_delete_batch = on_delete_batch

        header = ctk.CTkLabel(
            self, text="Select actions to run, then arrange the order",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        header.pack(anchor="w", padx=15, pady=(15, 5))

        # Footer is packed here, before the body's scrollable sections are
        # built, so it always keeps its reserved space at the bottom of the
        # (fixed-size) window - a growing/scrollable middle section can
        # never push it out of view (same defensive lesson as
        # ReviewSendModal/MultiReviewSendModal - see src/CLAUDE.md).
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=15, pady=(0, 15))

        # --- Saved Batches: load a previous selection, or delete one ---
        saved_row = ctk.CTkFrame(self, fg_color="transparent")
        saved_row.pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkLabel(saved_row, text="Saved Batches:").pack(side="left", padx=(0, 8))

        self._saved_batch_var = ctk.StringVar(value=_NO_SAVED_BATCH_SELECTED)
        self.saved_batch_menu = ctk.CTkOptionMenu(
            saved_row, variable=self._saved_batch_var, values=self._saved_batch_menu_values(),
            command=self._on_saved_batch_selected, width=260,
        )
        self.saved_batch_menu.pack(side="left")

        self.delete_saved_batch_button = ctk.CTkButton(
            saved_row, text="🗑 Delete", width=90, fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self._handle_delete_saved_batch_clicked,
        )
        self.delete_saved_batch_button.pack(side="left", padx=(8, 0))
        self._refresh_saved_batch_menu()

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

        # --- Footer contents: an explanation, then Cancel / Save / Run ---
        ctk.CTkLabel(
            footer,
            text="💾 Save Batch stores this list under a name to run again later — nothing runs now.  "
                 "▶ Run Batch runs this selection once, immediately, without saving it.",
            font=ctk.CTkFont(size=11), text_color=("gray30", "gray70"), justify="left", anchor="w",
            wraplength=680,
        ).pack(anchor="w", pady=(0, 8))

        button_row = ctk.CTkFrame(footer, fg_color="transparent")
        button_row.pack(fill="x")

        ctk.CTkButton(
            button_row, text="Cancel", width=100, fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self.destroy,
        ).pack(side="left")
        self.run_button = ctk.CTkButton(
            button_row, text="▶ Run Batch", width=140, command=self._handle_run_clicked
        )
        self.run_button.pack(side="right")
        self.save_button = ctk.CTkButton(
            button_row, text="💾 Save Batch", width=140, fg_color="transparent", border_width=1,
            text_color=("black", "white"), command=self._handle_save_clicked,
        )
        self.save_button.pack(side="right", padx=(0, 8))

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
        # Close first; see ReviewSendModal._on_send for why.
        self.destroy()
        if self._on_run:
            self._on_run(selected_actions, group_names)

    # --- Saved Batches ---------------------------------------------------

    def _saved_batch_menu_values(self) -> List[str]:
        if not self._saved_batches:
            return [_NO_SAVED_BATCHES_YET]
        return [_NO_SAVED_BATCH_SELECTED] + [b.name for b in self._saved_batches]

    def _refresh_saved_batch_menu(self) -> None:
        values = self._saved_batch_menu_values()
        self.saved_batch_menu.configure(values=values)
        self.delete_saved_batch_button.configure(state="normal" if self._saved_batches else "disabled")
        if self._saved_batch_var.get() not in values:
            self._saved_batch_var.set(values[0])

    def _saved_batch_by_name(self, name: str) -> Optional[SavedBatch]:
        return next((b for b in self._saved_batches if b.name == name), None)

    def _on_saved_batch_selected(self, name: str) -> None:
        batch = self._saved_batch_by_name(name)
        if batch is None:
            return  # placeholder / "(no saved batches yet)" - nothing to load

        # An action referenced by the saved batch may since have been
        # deleted (Actions can be removed independently) - silently drop
        # anything that's no longer around rather than erroring, same
        # "one missing thing shouldn't block the rest" spirit as ActionRunner.
        self._selected_ids = [aid for aid in batch.action_ids if aid in self._actions_by_id]
        for action_id, var in self._checkbox_vars.items():
            var.set("on" if action_id in self._selected_ids else "off")
        self._render_selected_list()

    def _prompt_batch_name(self, default: str = "") -> Optional[str]:
        """Asks the user to name the batch being saved. A thin, overridable
        wrapper around CTkInputDialog so tests can stub this out instead of
        needing a real interactive dialog."""
        dialog = ctk.CTkInputDialog(text="Name this batch:", title="Save Batch")
        name = dialog.get_input()
        return name.strip() if name else None

    def _confirm_overwrite(self, name: str) -> bool:
        return messagebox.askyesno(
            "Overwrite Saved Batch?",
            f'A saved batch named "{name}" already exists. Overwrite it with the current selection?',
        )

    def _confirm_delete(self, name: str) -> bool:
        return messagebox.askyesno("Delete Saved Batch?", f'Delete the saved batch "{name}"? This cannot be undone.')

    def _handle_save_clicked(self) -> None:
        if not self._selected_ids:
            messagebox.showinfo("Nothing to Save", "Select at least one action before saving a batch.")
            return
        if self._on_save_batch is None:
            return

        name = self._prompt_batch_name()
        if not name:
            return  # cancelled

        existing = self._saved_batch_by_name(name)
        if existing and not self._confirm_overwrite(name):
            return

        saved = self._on_save_batch(name, list(self._selected_ids))
        self._saved_batches = [b for b in self._saved_batches if b.id != saved.id]
        self._saved_batches.append(saved)
        self._refresh_saved_batch_menu()
        self._saved_batch_var.set(saved.name)

    def _handle_delete_saved_batch_clicked(self) -> None:
        name = self._saved_batch_var.get()
        batch = self._saved_batch_by_name(name)
        if batch is None:
            return
        if not self._confirm_delete(name):
            return

        if self._on_delete_batch:
            self._on_delete_batch(batch.id)
        self._saved_batches = [b for b in self._saved_batches if b.id != batch.id]
        self._refresh_saved_batch_menu()
