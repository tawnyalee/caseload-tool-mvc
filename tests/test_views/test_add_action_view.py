import pytest
import customtkinter as ctk
from src.views.add_action_view import AddActionView

class MockController:
    """A minimal mock controller to satisfy the view's requirements."""
    pass

def test_add_action_view_initialization():
    # Setup a temporary parent window
    app = ctk.CTk()
    mock_controller = MockController()
    
    # Attempt to initialize our newly structured view
    try:
        view = AddActionView(master=app, controller=mock_controller)
        assert view is not None
        # Verify our scrollable container was successfully created
        assert hasattr(view, 'scrollable_container')
        assert isinstance(view.scrollable_container, ctk.CTkScrollableFrame)
    finally:
        # Clean up the Tkinter window safely
        app.destroy()