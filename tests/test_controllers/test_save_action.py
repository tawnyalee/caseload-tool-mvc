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
    controller.activity_logger = MagicMock()
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
    # Uses the refresh-only path, not _on_group_selected — that one also fires
    # the controller's group-switch callback, which wrongly triggered the
    # "unsaved changes" confirmation dialog after every successful save.
    mock_nav_panel.refresh_active_group_display.assert_called_once_with("Tier 1 Support")
    mock_nav_panel._on_group_selected.assert_not_called()

def test_renaming_an_action_in_the_editor_replaces_its_old_name_in_the_group(tmp_path):
    """Regression: saving an existing action under a new name used to append
    the new name to its group's `scenarios` list and leave the old one there,
    so the nav panel showed two entries and the old one's Edit/Delete failed.
    Uses the real JSON repositories (in a temp folder) so the saved files are
    what's checked, not mocks."""
    from src.services.action_repository import ActionRepository
    from src.services.group_repository import GroupRepository
    from src.models.action import Action

    group_repo = GroupRepository(tmp_path / "groups.json")
    action_repo = ActionRepository(tmp_path / "actions.json")
    group = group_repo.add_group("D424")
    group.scenarios = ["First", "Old Name", "Last"]
    group_repo.save_groups([group])
    action_repo.save_action(Action(name="Old Name", group_id=group.id, action_id="a-1"))

    controller = AppController.__new__(AppController)
    controller.group_repo = group_repo
    controller.action_repo = action_repo
    controller.groups = group_repo.load_groups()
    controller._reload_scenarios_dict()
    controller.activity_logger = MagicMock()
    controller.nav_panel = None

    with pytest.MonkeyPatch.context() as m:
        m.setattr("tkinter.messagebox.showinfo", MagicMock())
        assert controller.save_action({"id": "a-1", "name": "New Name", "group_name": "D424"})

    # Same spot in the list, old name gone, nothing duplicated.
    assert group_repo.load_groups()[0].scenarios == ["First", "New Name", "Last"]
    # Still one action, same ID, so Edit/Delete (which read scenarios_raw) find it.
    saved = action_repo.load_actions()
    assert [(a.id, a.name) for a in saved] == [("a-1", "New Name")]
    assert list(controller.scenarios_raw) == ["New Name"]


def test_rename_button_saves_the_new_name_to_the_same_action(tmp_path):
    """Regression: the row's Rename button only renamed the action in memory.
    It called repository methods that don't exist, so actions.json kept the
    old name and it came back on the next reload."""
    from src.services.action_repository import ActionRepository
    from src.services.group_repository import GroupRepository
    from src.models.action import Action

    group_repo = GroupRepository(tmp_path / "groups.json")
    action_repo = ActionRepository(tmp_path / "actions.json")
    group = group_repo.add_group("D424")
    group.scenarios = ["Old Name"]
    group_repo.save_groups([group])
    action_repo.save_action(Action(name="Old Name", group_id=group.id, action_id="a-1"))

    controller = AppController.__new__(AppController)
    controller.group_repo = group_repo
    controller.action_repo = action_repo
    controller.groups = group_repo.load_groups()
    controller._reload_scenarios_dict()
    controller.activity_logger = MagicMock()
    controller.nav_panel = None

    controller.handle_rename_action("Old Name", "New Name")

    assert [(a.id, a.name) for a in action_repo.load_actions()] == [("a-1", "New Name")]
    assert group_repo.load_groups()[0].scenarios == ["New Name"]
    # What a reload would see: still one entry, under the new name.
    controller._reload_scenarios_dict()
    assert list(controller.scenarios_raw) == ["New Name"]
