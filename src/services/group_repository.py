import json
from pathlib import Path
from typing import List, Optional
from src.models.group import Group

class GroupRepository:
    def __init__(self, data_file: Optional[Path] = None) -> None:
        if data_file is None:
            # Resolves dynamically to src/data/groups.json
            project_root = Path(__file__).resolve().parent.parent
            data_file = project_root / "data" / "groups.json"
            
        self.data_file = data_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures the parent directory and groups.json file exist."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_groups(self) -> List[Group]:
        """Loads all groups from src/data/groups.json into Group objects."""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return [
                    Group(
                        name=item["name"],
                        scenarios=item.get("scenarios", []),
                        welcome_action_id=item.get("welcome_action_id"),
                        group_id=item.get("id")
                    )
                    for item in raw_data
                ]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_groups(self, groups: List[Group]) -> None:
        """Saves a list of Group objects to src/data/groups.json."""
        serialized = [
            {
                "id": g.id,
                "name": g.name,
                "scenarios": g.scenarios,
                "welcome_action_id": g.welcome_action_id
            }
            for g in groups
        ]
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=4)

    def add_group(self, group_name: str) -> Optional[Group]:
        """Creates a new Group, saves it to groups.json, and returns the new Group."""
        groups = self.load_groups()
        
        # Check if group name already exists (case-insensitive)
        if any(g.name.strip().lower() == group_name.strip().lower() for g in groups):
            return None

        new_group = Group(name=group_name.strip())
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