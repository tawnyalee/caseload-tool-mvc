# src/services/note_writer.py
"""Abstract note-writing against a student's CRM record, plus a local fake
that records what would have been written. The real adapter (Salesforce)
implements this same interface later.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Set


class NoteWriter(ABC):
    @abstractmethod
    def write_note(self, salesforce_id: str, subject: str, body: str) -> None:
        """Writes a note against a student's record. Raises an exception if it fails."""
        raise NotImplementedError

    @abstractmethod
    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        """Overwrites the short follow-up-note field on a student's roster record
        (e.g. 'Sent welcome email'). Raises an exception if it fails."""
        raise NotImplementedError


class FakeNoteWriter(NoteWriter):
    """Records every write_note()/update_follow_up_note() call instead of touching
    Salesforce. `fail_for` lets tests/dev simulate specific students failing,
    deterministically, for either operation."""

    def __init__(self, fail_for: Optional[Set[str]] = None):
        self.fail_for = fail_for or set()
        self.written: List[dict] = []
        self.follow_up_notes: dict = {}  # salesforce_id -> latest text

    def write_note(self, salesforce_id: str, subject: str, body: str) -> None:
        if salesforce_id in self.fail_for:
            raise RuntimeError(f"Simulated note-write failure for {salesforce_id}")
        self.written.append({"salesforce_id": salesforce_id, "subject": subject, "body": body})

    def update_follow_up_note(self, salesforce_id: str, text: str) -> None:
        if salesforce_id in self.fail_for:
            raise RuntimeError(f"Simulated follow-up-note update failure for {salesforce_id}")
        self.follow_up_notes[salesforce_id] = text
