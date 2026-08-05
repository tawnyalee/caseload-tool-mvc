# src/services/student_data_provider.py
"""Abstract source of student roster data, plus a local fake implementation.

Real adapters (Salesforce, Cadence) and the fake one both conform to
StudentDataProvider, so the rest of the app never depends on which is behind
it — swapping data sources later means writing a new class here, not
touching anything that calls get_students().

Filtering is intentionally NOT part of this yet — that's a separate, not-
yet-designed concern (field-type-aware operators, AND/OR grouping) that will
layer on top once it's been worked out. get_students() just returns
everything available from the source.
"""
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from src.models.student import Student


class StudentDataProvider(ABC):
    @abstractmethod
    def get_students(self) -> List[Student]:
        """Returns every student currently available from this data source."""
        raise NotImplementedError


class FakeStudentDataProvider(StudentDataProvider):
    """Loads students from a local, hand-editable JSON fixture — lets the app
    be built and tested end-to-end without touching real student data."""

    def __init__(self, file_path: str = "data/fake_students.json"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._save_raw([])

    def _save_raw(self, data: List[dict]) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def get_students(self) -> List[Student]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

        return [
            Student(
                salesforce_id=item.get("salesforce_id"),
                first_name=item.get("first_name", ""),
                last_name=item.get("last_name", ""),
                email=item.get("email", ""),
                phone=item.get("phone", ""),
                has_signed_up_for_text=item.get("has_signed_up_for_text", False),
            )
            for item in raw_data
        ]
