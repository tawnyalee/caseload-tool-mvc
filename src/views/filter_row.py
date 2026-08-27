# src/views/filter_row.py
"""A single filter-condition row for AddActionView's filter builder.

Reads FILTERABLE_FIELDS to drive which fields/operators are selectable at
all - an invalid field+operator combination can never even be chosen -
and swaps its value-input widget based on the selected field's kind and
operator: a plain text entry, a DatePickerEntry (two, for Between), a
multi-select Listbox for IsOneOf (shift/ctrl-click, same as VB.NET's
SelectionMode.MultiExtended - see docs/filter_engine_requirements.md),
or nothing at all for IsEmpty/IsNotEmpty.
"""
import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from src.services.filterable_fields import FILTERABLE_FIELDS, FieldKind, Operator
from src.views.date_picker import DatePickerEntry

_NO_VALUE_OPERATORS = {Operator.IS_EMPTY.value, Operator.IS_NOT_EMPTY.value}
_MULTI_VALUE_OPERATORS = {Operator.IS_ONE_OF.value}
_TWO_VALUE_OPERATORS = {Operator.BETWEEN.value}

FIELD_NAMES_SORTED = sorted(FILTERABLE_FIELDS.keys())


class FilterRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        get_live_values: Optional[Callable[[str], List[str]]] = None,
        on_remove: Optional[Callable[["FilterRow"], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._get_live_values = get_live_values or (lambda field_name: [])
        self._on_remove = on_remove
        self._value_widgets: List = []

        self.field_dropdown = ctk.CTkComboBox(
            self, values=FIELD_NAMES_SORTED, width=180, command=self._on_field_changed
        )
        self.field_dropdown.pack(side="left", padx=(0, 5))

        self.operator_dropdown = ctk.CTkComboBox(self, width=170, command=self._on_operator_changed)
        self.operator_dropdown.pack(side="left", padx=5)

        self.value_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.value_frame.pack(side="left", padx=5)

        self.remove_button = ctk.CTkButton(
            self, text="❌", width=30, fg_color="transparent", hover_color="#331111",
            command=self._handle_remove,
        )
        self.remove_button.pack(side="right", padx=(5, 0))

        # CTkComboBox's `command` only fires on user interaction, not on
        # .set(), so the initial field/operator/value-widget state has to
        # be wired up manually here to avoid starting out empty/mismatched.
        if FIELD_NAMES_SORTED:
            self.field_dropdown.set(FIELD_NAMES_SORTED[0])
            self._on_field_changed(FIELD_NAMES_SORTED[0])

    def _handle_remove(self) -> None:
        if self._on_remove:
            self._on_remove(self)
        self.destroy()

    def _current_field_def(self):
        return FILTERABLE_FIELDS.get(self.field_dropdown.get())

    def _on_field_changed(self, _selected_field: str) -> None:
        field_def = self._current_field_def()
        operator_values = [op.value for op in field_def.operators] if field_def else []
        self.operator_dropdown.configure(values=operator_values)
        if operator_values:
            self.operator_dropdown.set(operator_values[0])
        else:
            self.operator_dropdown.set("")
        self._rebuild_value_widgets()

    def _on_operator_changed(self, _selected_operator: str) -> None:
        self._rebuild_value_widgets()

    def _rebuild_value_widgets(self) -> None:
        for widget in self._value_widgets:
            widget.destroy()
        self._value_widgets = []

        field_def = self._current_field_def()
        operator = self.operator_dropdown.get()
        if field_def is None or not operator:
            return

        if operator in _NO_VALUE_OPERATORS:
            return

        if operator in _MULTI_VALUE_OPERATORS:
            options = field_def.fixed_values or self._get_live_values(field_def.name)
            listbox = tk.Listbox(
                self.value_frame, selectmode=tk.EXTENDED,
                height=min(6, max(3, len(options))), exportselection=False,
            )
            for option in options:
                listbox.insert("end", option)
            listbox.pack(side="left")
            hint = ctk.CTkLabel(
                self.value_frame, text="Hold Shift/Ctrl to select multiple",
                font=ctk.CTkFont(size=10),
            )
            hint.pack(side="left", padx=(5, 0))
            self._value_widgets = [listbox, hint]
            return

        if operator in _TWO_VALUE_OPERATORS and field_def.kind == FieldKind.DATE:
            start = DatePickerEntry(self.value_frame)
            start.pack(side="left")
            to_label = ctk.CTkLabel(self.value_frame, text="to")
            to_label.pack(side="left", padx=5)
            end = DatePickerEntry(self.value_frame)
            end.pack(side="left")
            self._value_widgets = [start, to_label, end]
            return

        if field_def.kind == FieldKind.DATE:
            picker = DatePickerEntry(self.value_frame)
            picker.pack(side="left")
            self._value_widgets = [picker]
            return

        if field_def.kind == FieldKind.BOOLEAN:
            dropdown = ctk.CTkComboBox(self.value_frame, values=["TRUE", "FALSE"], width=100)
            dropdown.set("TRUE")
            dropdown.pack(side="left")
            self._value_widgets = [dropdown]
            return

        entry = ctk.CTkEntry(self.value_frame, width=150, placeholder_text="Value...")
        entry.pack(side="left")
        self._value_widgets = [entry]

    def to_condition(self) -> Optional[Dict]:
        """Returns this row as a filter-condition dict matching what
        filter_engine.matches_student() expects, or None if the row isn't
        usable yet (e.g. no field/operator selected, or a required value
        hasn't been filled in)."""
        field_def = self._current_field_def()
        operator = self.operator_dropdown.get()
        if field_def is None or not operator:
            return None

        condition = {"field": field_def.name, "operator": operator}

        if operator in _NO_VALUE_OPERATORS:
            return condition

        if operator in _MULTI_VALUE_OPERATORS:
            if not self._value_widgets:
                return None
            listbox = self._value_widgets[0]
            selected = [listbox.get(i) for i in listbox.curselection()]
            if not selected:
                return None
            condition["value"] = selected
            return condition

        if operator in _TWO_VALUE_OPERATORS:
            if len(self._value_widgets) < 3:
                return None
            start_value, end_value = self._value_widgets[0].get(), self._value_widgets[2].get()
            if not start_value or not end_value:
                return None
            condition["value"] = [start_value, end_value]
            return condition

        if not self._value_widgets:
            return None
        value = self._value_widgets[0].get()
        if not value:
            return None
        condition["value"] = value
        return condition
