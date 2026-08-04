from unittest.mock import MagicMock
import pytest
from src.controllers.app_controller import AppController

def test_save_action_updates_active_group_and_reloads_dict():
    # Arrange
    controller = AppController.__new__(AppController)
    controller.groups = []
    controller.scenarios_raw = {}
    
    controller.group_repo = MagicMock()
    controller.group_repo.load_groups.return_value = []
    
    controller.action_repo = MagicMock()
    controller._reload_scenarios_dict = MagicMock()

    # Mock the nav_panel UI component
    mock_nav_panel = MagicMock()
    mock_nav_panel.group_dropdown.get.return_value = "Tier 1 Support"
    controller.nav_panel = mock_nav_panel

    action_data = {
        "id": "123",
        "name": "Test Action",
        "group_name": "Tier 1 Support"
    }

    # Mock messagebox to prevent popups during automated tests
    with pytest.MonkeyPatch.context() as m:
        m.setattr("tkinter.messagebox.showinfo", MagicMock())

        # Act
        result = controller.save_action(action_data)

    # Assert
    assert result is True
    controller._reload_scenarios_dict.assert_called_once()
    assert mock_nav_panel.groups == controller.groups
    assert mock_nav_panel.scenarios_raw == controller.scenarios_raw
    mock_nav_panel._on_group_selected.assert_called_once_with("Tier 1 Support")