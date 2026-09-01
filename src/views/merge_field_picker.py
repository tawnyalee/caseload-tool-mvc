# src/views/merge_field_picker.py
"""A small reusable "Insert Field" control: a dropdown that inserts a
mail-merge token (see src/services/merge_fields.py) into a target
Entry/Textbox at the current cursor position, then resets itself back to
its placeholder - same reset pattern TemplateEditorModal already uses for
its font-size menu.
"""
import customtkinter as ctk

from src.services.merge_fields import MERGE_FIELDS

PLACEHOLDER = "Insert Field"


def create_merge_field_menu(parent, target_widget, width: int = 150) -> ctk.CTkOptionMenu:
    """Builds (but doesn't pack/grid) an "Insert Field" CTkOptionMenu that
    inserts the chosen field's token into `target_widget` at its cursor
    position. `target_widget` must support .insert("insert", text) - true
    of both CTkEntry and CTkTextbox."""
    var = ctk.StringVar(value=PLACEHOLDER)

    def _on_choice(label: str):
        for field in MERGE_FIELDS.values():
            if field.label == label:
                target_widget.insert("insert", field.token)
                break
        var.set(PLACEHOLDER)

    labels = [field.label for field in MERGE_FIELDS.values()]
    return ctk.CTkOptionMenu(parent, values=labels, variable=var, command=_on_choice, width=width)
