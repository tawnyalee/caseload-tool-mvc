# src/services/app_settings_repository.py
"""App-wide settings that don't belong to a group or action, kept per
computer: the default Outlook signature, which is optional for Actions and
required by Send Task Emails (those have no Action to hold a signature), and
whether notes save directly to Salesforce."""
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
        self._save("default_signature", name)

    @property
    def use_direct_saves(self) -> bool:
        """On unless turned off: notes and follow-ups try Salesforce's own
        save request before the form (see salesforce_direct_save.py). Off
        means the form only, in case WGU asks for that (developer,
        2026-11-04)."""
        return self._load().get("use_direct_saves", True) is not False

    def save_use_direct_saves(self, on: bool) -> None:
        self._save("use_direct_saves", bool(on))

    def _save(self, key: str, value) -> None:
        settings = self._load()
        settings[key] = value
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
