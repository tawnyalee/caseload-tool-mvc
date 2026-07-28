import pytest
import customtkinter as ctk
from src.views.add_action_view import AddActionView


class MockController:
    """A minimal mock controller to satisfy the view's requirements."""
    pass


@pytest.fixture(scope="session")
def ctk_root():
    """Creates a single shared CTk root instance for all view tests."""
    app = ctk.CTk()
    app.withdraw()  # Hide window during test execution
    yield app
    app.destroy()


def test_add_action_view_initialization(ctk_root):
    mock_controller = MockController()
    view = AddActionView(master=ctk_root, controller=mock_controller)
    assert view is not None
    assert hasattr(view, 'scrollable_container')
    assert isinstance(view.scrollable_container, ctk.CTkScrollableFrame)


def test_add_action_view_selects_initial_group_on_add(ctk_root):
    """Verify that initial_group_name is selected when adding a new action."""
    mock_controller = MockController()
    groups = ["Group A", "Group B", "Group C"]
    
    view = AddActionView(
        master=ctk_root,
        controller=mock_controller,
        groups=groups,
        initial_group_name="Group B"
    )
    assert view.group_dropdown.get() == "Group B"


def test_add_action_view_prioritizes_action_data_group_on_edit(ctk_root):
    """Verify that action_data's assigned group takes precedence when editing."""
    mock_controller = MockController()
    groups = ["Group A", "Group B", "Group C"]
    dummy_action_data = {
        "metadata": {
            "assigned_group": "Group C"
        }
    }
    
    view = AddActionView(
        master=ctk_root,
        controller=mock_controller,
        groups=groups,
        initial_group_name="Group A",  # Selected in nav, but editing Group C
        action_data=dummy_action_data
    )
    assert view.group_dropdown.get() == "Group C"