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

def test_group_has_tasks_and_has_objective_assessment_default_false():
    """A course might use neither, either, or both - default is neither."""
    group = Group(name="Math 101")
    assert group.has_tasks is False
    assert group.has_objective_assessment is False

def test_group_has_tasks_and_has_objective_assessment_are_independent():
    """Both flags can be set independently, including both true at once."""
    group = Group(name="Math 101", has_tasks=True, has_objective_assessment=True)
    assert group.has_tasks is True
    assert group.has_objective_assessment is True