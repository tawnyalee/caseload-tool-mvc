import json
from pathlib import Path

from src.services import app_paths
from typing import List, Optional
from src.models.group import Group

class GroupRepository:
    def __init__(self, data_file: Optional[Path] = None) -> None:
        if data_file is None:
            data_file = app_paths.groups_file()  # %LOCALAPPDATA%\CaseloadTool - see app_paths.py
            
        self.data_file = data_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures the parent directory and groups.json file exist."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_groups(self) -> List[Group]:
        """Loads all groups from groups.json into Group objects."""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return [self._from_dict(item) for item in raw_data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    @staticmethod
    def _from_dict(item: dict) -> Group:
        has_tasks = item.get("has_tasks", False)
        has_oa = item.get("has_objective_assessment", False)
        if "is_course" in item:
            is_course, course_code = item["is_course"], item.get("course_code", "")
        else:
            # Saved before course settings existed (2026-10-27): a group with
            # tasks or an OA was a course named by its course code - the
            # assumption the app made everywhere until then - so it becomes
            # one automatically and nothing changes for the professor.
            is_course = bool(has_tasks or has_oa)
            course_code = item["name"] if is_course else ""
        return Group(
            name=item["name"],
            scenarios=item.get("scenarios", []),
            welcome_action_id=item.get("welcome_action_id"),
            group_id=item.get("id"),
            has_tasks=has_tasks,
            has_objective_assessment=has_oa,
            is_course=is_course,
            course_code=course_code,
            task_count=item.get("task_count", 0),
            task_emails=item.get("task_emails", {}),
        )

    def save_groups(self, groups: List[Group]) -> None:
        """Saves a list of Group objects to groups.json."""
        serialized = [
            {
                "id": g.id,
                "name": g.name,
                "scenarios": g.scenarios,
                "welcome_action_id": g.welcome_action_id,
                "has_tasks": g.has_tasks,
                "has_objective_assessment": g.has_objective_assessment,
                "is_course": g.is_course,
                "course_code": g.course_code,
                "task_count": g.task_count,
                "task_emails": g.task_emails,
            }
            for g in groups
        ]
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=4)

    def add_group(
        self,
        group_name: str,
        has_tasks: bool = False,
        has_objective_assessment: bool = False,
        is_course: bool = False,
    ) -> Optional[Group]:
        """Creates a new Group, saves it to groups.json, and returns the new Group."""
        groups = self.load_groups()

        # Check if group name already exists (case-insensitive)
        if any(g.name.strip().lower() == group_name.strip().lower() for g in groups):
            return None

        new_group = Group(
            name=group_name.strip(),
            has_tasks=has_tasks,
            has_objective_assessment=has_objective_assessment,
            is_course=is_course,
            course_code=group_name.strip() if is_course else "",
        )
        groups.append(new_group)
        self.save_groups(groups)
        return new_group

    def delete_group(self, group_name: str) -> bool:
        """Removes a group by name and updates the JSON storage."""
        groups = self.load_groups()
        updated_groups = [g for g in groups if g.name != group_name]
        
        # If lengths match, no group was found to delete
        if len(groups) == len(updated_groups):
            return False
            
        self.save_groups(updated_groups)
        return True

    def clear_welcome_action_id(self, action_id: str) -> None:
        """
        Scans all groups and resets welcome_action_id to None if it matches action_id.
        """
        groups = self.load_groups()
        updated = False

        for group in groups:
            if group.welcome_action_id == action_id:
                group.welcome_action_id = None
                updated = True

        if updated:
            self.save_groups(groups)