# tests/test_views/test_note_subject_entry_exists.py
import customtkinter as ctk
from src.views.add_action_view import AddActionView


def test_note_subject_entry_exists():
    """Verify that the note_subject entry widget exists on AddActionView."""
    app = ctk.CTk()
    app.withdraw()  # Keeps the window hidden during execution
    try:
        view = AddActionView(master=app)
        assert hasattr(view, "note_subject")
        assert isinstance(view.note_subject, ctk.CTkEntry)
    finally:
        app.destroy()