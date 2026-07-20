import json
from pathlib import Path
from typing import List, Optional
from src.models.email_template import EmailTemplate


class TemplateRepository:
    def __init__(self, file_path: str = "data/templates.json"):
        self.file_path = Path(file_path)
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        # Initialize empty file if it doesn't exist
        if not self.file_path.exists():
            self._save_raw([])

    def _save_raw(self, data: List[dict]) -> None:
        """Helper to write raw dictionary list to JSON file."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def load_all(self) -> List[EmailTemplate]:
        """Loads all email templates from the JSON file."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return [
                    EmailTemplate(
                        name=item["name"],
                        body=item["body"],
                        template_id=item.get("id"),
                    )
                    for item in raw_data
                ]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_all(self, templates: List[EmailTemplate]) -> None:
        """Saves a list of EmailTemplate objects to the JSON file."""
        data = [
            {"id": t.id, "name": t.name, "body": t.body}
            for t in templates
        ]
        self._save_raw(data)

    def save(self, template: EmailTemplate) -> None:
        """Saves or updates a single template."""
        templates = self.load_all()
        # Check if template already exists to update it
        existing_index = next(
            (i for i, t in enumerate(templates) if t.id == template.id), None
        )

        if existing_index is not None:
            templates[existing_index] = template
        else:
            templates.append(template)

        self.save_all(templates)