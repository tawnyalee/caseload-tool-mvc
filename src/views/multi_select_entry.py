# src/views/multi_select_entry.py
"""A closed-until-clicked multi-select control for FilterRow's "Is One Of"
value picker. Built the same way as DatePickerEntry (a small field + button
that opens a floating CTkToplevel popup) instead of the original
persistently-open tk.Listbox, which pushed surrounding widgets around in
the layout whenever it appeared.
"""
import tkinter as tk
from typing import Iterable, List

import customtkinter as ctk


class MultiSelectEntry(ctk.CTkFrame):
    """A read-only summary field + button that opens a popup of checkboxes
    for choosing several values out of a fixed list of `options`."""

    def __init__(self, master, options: List[str], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._all_options = list(options)  # own copy - set_selected may add to it
        self._selected: set = set()

        self.summary = ctk.CTkEntry(self, width=150)
        self.summary.configure(state="disabled")
        self.summary.pack(side="left")
        self._refresh_summary()

        self.button = ctk.CTkButton(self, text="Select...", width=70, command=self._open_popup)
        self.button.pack(side="left", padx=(4, 0))

    def get_selected(self) -> List[str]:
        """Returns the selected values, in `options` order."""
        return [option for option in self._all_options if option in self._selected]

    def set_selected(self, values: Iterable[str]) -> None:
        """A value that isn't in the current options is KEPT (and added as
        an option), not dropped: options built from the live roster can be
        empty or missing a saved value (roster not loaded yet, or no current
        student has it today). Dropping it would silently erase that part of
        a saved filter on the next Save - found 2026-10-22."""
        values = list(values)
        for value in values:
            if value not in self._all_options:
                self._all_options.append(value)
        self._selected = set(values)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        text = ", ".join(self.get_selected()) if self._selected else "None selected"
        self.summary.configure(state="normal")
        self.summary.delete(0, "end")
        self.summary.insert(0, text)
        self.summary.configure(state="disabled")

    def _open_popup(self) -> None:
        popup = _MultiSelectPopup(self, self._all_options, self._selected, on_apply=self.set_selected)
        popup.grab_set()


class _MultiSelectPopup(ctk.CTkToplevel):
    def __init__(self, master, options: List[str], selected: set, on_apply):
        super().__init__(master)
        self.title("")
        self.resizable(False, False)
        self.transient(master)
        self._on_apply = on_apply
        self._vars = {}

        scroll = ctk.CTkScrollableFrame(
            self, width=200, height=min(220, 28 * max(3, len(options)))
        )
        scroll.pack(padx=8, pady=(8, 4), fill="both", expand=True)

        for option in options:
            var = tk.StringVar(value="on" if option in selected else "off")
            self._vars[option] = var
            ctk.CTkCheckBox(scroll, text=option, variable=var, onvalue="on", offvalue="off").pack(
                anchor="w", pady=2
            )

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(button_row, text="Select All", width=80, command=self._select_all).pack(side="left")
        ctk.CTkButton(button_row, text="Clear", width=60, command=self._clear).pack(side="left", padx=(5, 0))
        ctk.CTkButton(button_row, text="Done", width=60, command=self._apply).pack(side="right")

    def _select_all(self) -> None:
        for var in self._vars.values():
            var.set("on")

    def _clear(self) -> None:
        for var in self._vars.values():
            var.set("off")

    def _apply(self) -> None:
        self._on_apply({option for option, var in self._vars.items() if var.get() == "on"})
        self.destroy()
