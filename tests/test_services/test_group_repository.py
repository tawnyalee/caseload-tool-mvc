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


def test_has_tasks_and_has_objective_assessment_round_trip(temp_group_repo: GroupRepository):
    """Both flags must survive a save/load cycle through JSON."""
    group = Group(name="D424", has_tasks=True, has_objective_assessment=False)
    temp_group_repo.save_groups([group])

    loaded_groups = temp_group_repo.load_groups()
    assert len(loaded_groups) == 1
    assert loaded_groups[0].has_tasks is True
    assert loaded_groups[0].has_objective_assessment is False


def test_add_group_sets_has_tasks_and_has_objective_assessment(temp_group_repo: GroupRepository):
    """add_group should accept and persist both flags for a brand-new group."""
    new_group = temp_group_repo.add_group("D370", has_tasks=True, has_objective_assessment=True)

    assert new_group.has_tasks is True
    assert new_group.has_objective_assessment is True

    loaded_groups = temp_group_repo.load_groups()
    assert loaded_groups[0].has_tasks is True
    assert loaded_groups[0].has_objective_assessment is True

# --- Course settings (2026-10-27) --------------------------------------------

import json as _json


def test_groups_saved_before_course_settings_become_courses_if_they_had_tasks_or_an_oa(tmp_path):
    path = tmp_path / "groups.json"
    path.write_text(_json.dumps([
        {"id": "1", "name": "D424", "has_tasks": True, "has_objective_assessment": False},
        {"id": "2", "name": "C960", "has_tasks": False, "has_objective_assessment": True},
        {"id": "3", "name": "Test Group", "has_tasks": False, "has_objective_assessment": False},
    ]), encoding="utf-8")

    groups = {g.name: g for g in GroupRepository(data_file=path).load_groups()}

    assert (groups["D424"].is_course, groups["D424"].course_code) == (True, "D424")
    assert (groups["C960"].is_course, groups["C960"].course_code) == (True, "C960")
    assert (groups["Test Group"].is_course, groups["Test Group"].scoped_course_code) == (False, "")


def test_course_settings_round_trip(tmp_path):
    repo = GroupRepository(data_file=tmp_path / "groups.json")
    group = Group(name="Capstone", is_course=True, course_code="D424", task_count=5,
                  has_tasks=True, has_objective_assessment=True)
    repo.save_groups([group])

    loaded = repo.load_groups()[0]

    assert (loaded.is_course, loaded.course_code, loaded.task_count) == (True, "D424", 5)
    assert (loaded.has_tasks, loaded.has_objective_assessment) == (True, True)


def test_an_explicitly_unmarked_group_stays_unmarked_even_with_tasks(tmp_path):
    path = tmp_path / "groups.json"
    path.write_text(_json.dumps([{"id": "1", "name": "D424", "has_tasks": True, "is_course": False}]), encoding="utf-8")
    assert GroupRepository(data_file=path).load_groups()[0].is_course is False


def test_task_emails_round_trip(tmp_path):
    repo = GroupRepository(data_file=tmp_path / "groups.json")
    repo.save_groups([Group(name="D424", is_course=True, course_code="D424", has_tasks=True, task_count=3,
                            task_emails={"1": {"template_id": "T2", "subject": "On to Task 2"}})])
    assert repo.load_groups()[0].task_emails == {"1": {"template_id": "T2", "subject": "On to Task 2"}}
