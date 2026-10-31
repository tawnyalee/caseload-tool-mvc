# src/services/app_settings_repository.py
"""App-wide settings that don't belong to a group or action. So far just the
default Outlook signature, which is optional for Actions and required by
Send Task Emails (those have no Action to hold a signature)."""
import json
from typing import Optional

from src.services import app_paths


class AppSettingsRepository:
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or app_paths.app_settings_file()

    def _load(self) -> dict:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    @property
    def default_signature(self) -> str:
        return self._load().get("default_signature", "")

    def save_default_signature(self, name: str) -> None:
        settings = self._load()
        settings["default_signature"] = name
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
