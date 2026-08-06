import pytest
from unittest.mock import MagicMock, patch
from src.views.scenario_nav_panel import ScenarioNavPanel
from src.models.group import Group

@pytest.fixture
def mock_nav_panel():
    """Fixture to create a ScenarioNavPanel with mocked UI elements to avoid GUI rendering during tests."""
    with patch("customtkinter.CTkFrame.__init__", return_value=None), \
         patch("src.views.scenario_nav_panel.ScenarioNavPanel._setup_ui"):
        
        # Instantiate panel
        panel = ScenarioNavPanel(master=None, groups=[], scenarios_raw={})
        
        # Mock UI dependencies used in refresh_data
        panel.group_dropdown = MagicMock()
        panel.group_dropdown.get.return_value = "General"
        panel.actions_header_label = MagicMock()
        panel._render_table = MagicMock()
        
        return panel

def test_refresh_data_updates_state_and_rerenders(mock_nav_panel):
    # Arrange
    new_group = Group(name="Work", scenarios=["Task1"])
    new_scenarios = {"Task1": {}, "Task2": {}}
    
    # Act
    mock_nav_panel.refresh_data(groups=[new_group], scenarios_raw=new_scenarios)

    # Assert
    assert mock_nav_panel.groups == [new_group]
    assert mock_nav_panel.scenarios_raw == new_scenarios
    assert mock_nav_panel.group_names == ["General", "Work"]
    mock_nav_panel.group_dropdown.configure.assert_called_once_with(values=["General", "Work"])
    mock_nav_panel._render_table.assert_called_once_with("General")

def test_refresh_data_falls_back_to_general_if_group_deleted(mock_nav_panel):
    # Arrange: Simulate that 'DeletedGroup' was selected before refresh
    mock_nav_panel.group_dropdown.get.return_value = "DeletedGroup"
    
    # Act
    mock_nav_panel.refresh_data(groups=[], scenarios_raw={})

    # Assert
    mock_nav_panel.group_dropdown.set.assert_called_once_with("General")
    mock_nav_panel.actions_header_label.configure.assert_called_once_with(text="General - Actions")
    mock_nav_panel._render_table.assert_called_once_with("General")


def test_refresh_active_group_display_does_not_fire_group_selected_callback(mock_nav_panel):
    """A plain post-save/CRUD refresh must not trigger the controller's
    group-switch handling (unsaved-changes confirmation, workspace swap) —
    only an actual user-driven dropdown selection should do that."""
    mock_nav_panel.on_group_selected = MagicMock()

    mock_nav_panel.refresh_active_group_display("Work")

    mock_nav_panel.actions_header_label.configure.assert_called_once_with(text="Work - Actions")
    mock_nav_panel._render_table.assert_called_once_with("Work")
    mock_nav_panel.on_group_selected.assert_not_called()


def test_on_group_selected_still_fires_the_callback_for_real_switches(mock_nav_panel):
    """A genuine dropdown selection (the user clicking a different group)
    still needs to notify the controller so the unsaved-changes guard runs."""
    mock_nav_panel.on_group_selected = MagicMock()

    mock_nav_panel._on_group_selected("Work")

    mock_nav_panel._render_table.assert_called_once_with("Work")
    mock_nav_panel.on_group_selected.assert_called_once_with("Work")