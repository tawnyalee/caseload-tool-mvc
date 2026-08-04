import json
import pytest
from pathlib import Path
from src.models.action import Action
from src.services.action_repository import ActionRepository


@pytest.fixture
def temp_action_repo(tmp_path: Path) -> ActionRepository:
    """Fixture to provide an ActionRepository backed by a temporary JSON file."""
    test_file = tmp_path / "actions.json"
    return ActionRepository(data_file=test_file)


def test_save_action_create_new(temp_action_repo: ActionRepository):
    """Test saving a new action creates an entry in JSON."""
    new_action = Action(name="Send Welcome Email", is_email=True)
    
    saved_action = temp_action_repo.save_action(new_action)
    
    assert saved_action.id == new_action.id
    
    # Verify file contents
    loaded_actions = temp_action_repo.load_actions()
    assert len(loaded_actions) == 1
    assert loaded_actions[0].name == "Send Welcome Email"
    assert loaded_actions[0].is_email is True


def test_save_action_update_existing(temp_action_repo: ActionRepository):
    """Test saving an existing action updates it in place."""
    action = Action(name="Initial Name", is_text=False)
    temp_action_repo.save_action(action)
    
    # Modify the action name and update flag
    action.name = "Updated Name"
    action.is_text = True
    temp_action_repo.save_action(action)
    
    # Verify file contents updated, not appended
    loaded_actions = temp_action_repo.load_actions()
    assert len(loaded_actions) == 1
    assert loaded_actions[0].name == "Updated Name"
    assert loaded_actions[0].is_text is True

def test_delete_action(temp_action_repo: ActionRepository):
    """Test deleting an action removes it from JSON."""
    action1 = Action(name="Action One")
    action2 = Action(name="Action Two")
    
    temp_action_repo.save_action(action1)
    temp_action_repo.save_action(action2)
    
    # Delete the first action
    result = temp_action_repo.delete_action(action1.id)
    
    assert result is True
    
    # Verify only action2 remains
    loaded_actions = temp_action_repo.load_actions()
    assert len(loaded_actions) == 1
    assert loaded_actions[0].id == action2.id