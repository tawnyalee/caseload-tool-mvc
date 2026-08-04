import json
from pathlib import Path
from typing import List, Optional
from src.models.action import Action
from src.models.enums import InteractionType


class ActionRepository:
    def __init__(self, data_file: Optional[Path] = None) -> None:
        if data_file is None:
            # Resolves dynamically to src/data/actions.json
            project_root = Path(__file__).resolve().parent.parent
            data_file = project_root / "data" / "actions.json"

        self.data_file = data_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures the parent directory and actions.json file exist."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_actions(self) -> List[Action]:
        """Loads all actions from JSON into Action objects."""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return [
                    Action(
                        action_id=item.get("id"),
                        name=item.get("name", ""),
                        group_id=item.get("group_id", ""),
                        filters=item.get("filters", []),
                        is_email=item.get("is_email", False),
                        is_text=item.get("is_text", False),
                        template_id=item.get("template_id"),
                        email_subject=item.get("email_subject", ""),
                        email_signature=item.get("email_signature", ""),
                        text_subject=item.get("text_subject", ""),
                        text_body=item.get("text_body", ""),
                        note_subject=item.get("note_subject", ""),
                        note_body=item.get("note_body", ""),
                        follow_up_note=item.get("follow_up_note", ""),
                        interaction_type=(
                            InteractionType(item["interaction_type"])
                            if item.get("interaction_type")
                            else None
                        ),
                    )
                    for item in raw_data
                ]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_action(self, action: Action) -> Action:
        """
        Saves an action. Updates the entry if action.id exists,
        otherwise appends it as a new Action.
        """
        actions = self.load_actions()
        found = False

        for i, existing_action in enumerate(actions):
            if existing_action.id == action.id:
                actions[i] = action
                found = True
                break

        if not found:
            actions.append(action)

        serialized = [
            {
                "id": a.id,
                "name": a.name,
                "group_id": a.group_id,
                "filters": a.filters,
                "is_email": a.is_email,
                "is_text": a.is_text,
                "template_id": a.template_id,
                "email_subject": a.email_subject,
                "email_signature": a.email_signature,
                "text_subject": a.text_subject,
                "text_body": a.text_body,
                "note_subject": a.note_subject,
                "note_body": a.note_body,
                "follow_up_note": a.follow_up_note,
                "interaction_type": (
                    a.interaction_type.value if a.interaction_type else None
                ),
            }
            for a in actions
        ]

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=4)

        return action

    def delete_action(self, action_id: str) -> bool:
        """
        Removes an action matching action_id and updates JSON storage.
        Returns True if deleted, False if not found.
        """
        actions = self.load_actions()
        updated_actions = [a for a in actions if a.id != action_id]

        if len(actions) == len(updated_actions):
            return False

        serialized = [
            {
                "id": a.id,
                "name": a.name,
                "group_id": a.group_id,
                "filters": a.filters,
                "is_email": a.is_email,
                "is_text": a.is_text,
                "template_id": a.template_id,
                "email_subject": a.email_subject,
                "email_signature": a.email_signature,
                "text_subject": a.text_subject,
                "text_body": a.text_body,
                "note_subject": a.note_subject,
                "note_body": a.note_body,
                "follow_up_note": a.follow_up_note,
                "interaction_type": (
                    a.interaction_type.value if a.interaction_type else None
                ),
            }
            for a in updated_actions
        ]

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=4)

        return True