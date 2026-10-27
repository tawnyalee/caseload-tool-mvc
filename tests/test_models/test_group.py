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

# --- Task emails (2026-10-27) ------------------------------------------------

def test_tasks_only_course_has_no_row_for_the_last_task():
    group = Group(name="D424", is_course=True, course_code="D424", has_tasks=True, task_count=5)
    assert group.task_email_rows() == [1, 2, 3, 4]


def test_course_with_tasks_and_an_oa_gets_a_row_after_the_last_task_for_oa_prep():
    group = Group(name="C769", is_course=True, course_code="C769", has_tasks=True, task_count=5,
                  has_objective_assessment=True)
    assert group.task_email_rows() == [1, 2, 3, 4, 5]


def test_no_rows_unless_a_course_with_tasks():
    assert Group(name="General").task_email_rows() == []
    assert Group(name="X", is_course=True, course_code="X", has_objective_assessment=True).task_email_rows() == []


def test_task_email_for_returns_the_email_only_when_a_template_is_chosen():
    group = Group(name="D424", is_course=True, course_code="D424", has_tasks=True, task_count=3, task_emails={
        "1": {"template_id": "T2", "subject": "On to Task 2"},
        "2": {"template_id": "", "subject": "unfinished"},
    })
    assert group.task_email_for(1) == {"template_id": "T2", "subject": "On to Task 2"}
    assert group.task_email_for(2) is None   # no template chosen
    assert group.task_email_for(3) is None   # last task, tasks-only course
    assert group.task_email_for(None) is None
