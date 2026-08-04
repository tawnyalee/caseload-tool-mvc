import pytest
from pathlib import Path
from src.models.group import Group
from src.services.group_repository import GroupRepository


@pytest.fixture
def temp_group_repo(tmp_path: Path) -> GroupRepository:
    """Fixture to provide a GroupRepository backed by a temporary JSON file."""
    test_file = tmp_path / "groups.json"
    return GroupRepository(data_file=test_file)


def test_clear_welcome_action_id(temp_group_repo: GroupRepository):
    """Test resetting welcome_action_id to None when an action is deleted."""
    # Create a group with a welcome_action_id
    group = Group(name="VIP Group", welcome_action_id="action-123")
    temp_group_repo.save_groups([group])

    # Reset welcome_action_id for action-123
    temp_group_repo.clear_welcome_action_id("action-123")

    # Verify welcome_action_id is now None
    loaded_groups = temp_group_repo.load_groups()
    assert len(loaded_groups) == 1
    assert loaded_groups[0].welcome_action_id is None