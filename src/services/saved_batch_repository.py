import json
from pathlib import Path

from src.services import app_paths
from typing import List, Optional
from src.models.saved_batch import SavedBatch


class SavedBatchRepository:
    def __init__(self, data_file: Optional[Path] = None) -> None:
        if data_file is None:
            data_file = app_paths.saved_batches_file()  # %LOCALAPPDATA%\CaseloadTool - see app_paths.py

        self.data_file = data_file
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensures the parent directory and saved_batches.json file exist."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_batches(self) -> List[SavedBatch]:
        """Loads all saved batches from saved_batches.json."""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return [
                    SavedBatch(
                        name=item["name"],
                        action_ids=item.get("action_ids", []),
                        batch_id=item.get("id"),
                    )
                    for item in raw_data
                ]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_batches(self, batches: List[SavedBatch]) -> None:
        """Saves a list of SavedBatch objects to saved_batches.json."""
        serialized = [
            {"id": b.id, "name": b.name, "action_ids": b.action_ids}
            for b in batches
        ]
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=4)

    def save_batch(self, name: str, action_ids: List[str]) -> SavedBatch:
        """Creates a new saved batch, or overwrites the existing one with the
        same name (case-insensitive) if there is one - saving again under an
        existing name is the v1 "edit" path, rather than a separate rename/
        edit flow. Returns the resulting SavedBatch."""
        batches = self.load_batches()
        existing = next(
            (b for b in batches if b.name.strip().lower() == name.strip().lower()), None
        )
        if existing:
            existing.action_ids = list(action_ids)
            self.save_batches(batches)
            return existing

        new_batch = SavedBatch(name=name.strip(), action_ids=list(action_ids))
        batches.append(new_batch)
        self.save_batches(batches)
        return new_batch

    def delete_batch(self, batch_id: str) -> bool:
        """Removes a saved batch by id. Returns False if no batch had that id."""
        batches = self.load_batches()
        updated = [b for b in batches if b.id != batch_id]

        if len(updated) == len(batches):
            return False

        self.save_batches(updated)
        return True
