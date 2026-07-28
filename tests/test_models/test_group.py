from src.models.group import Group

def test_group_welcome_action_id_default_none():
    """Verify welcome_action_id defaults to None when not provided."""
    group = Group(name="Math 101")
    assert group.welcome_action_id is None

def test_group_welcome_action_id_assignment():
    """Verify welcome_action_id can be assigned on initialization."""
    action_id = "action-123"
    group = Group(name="Math 101", welcome_action_id=action_id)
    assert group.welcome_action_id == action_id