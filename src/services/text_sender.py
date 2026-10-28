# src/services/text_sender.py
"""Abstract text delivery, plus a local fake that records what would have
been sent (for tests), and the placeholder the app uses where texting isn't
available. The real adapter (mongoose_text_sender.py) implements this same
interface.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from src.models.student import Student


class TextSkipped(Exception):
    """A text deliberately not sent - e.g. the student isn't in the course's
    Mongoose department. The run lists it as skipped (to handle by hand),
    not as a failure."""


class TextSender(ABC):
    @abstractmethod
    def send(self, student: Student, body: str, message_name: str) -> str:
        """Sends or schedules a text to `student`, with `message_name` as the
        platform's label for it. Returns a short description of what
        happened, for the log. Raises TextSkipped when it deliberately
        didn't send, or any other exception if sending failed."""
        raise NotImplementedError

    def ensure_ready(self) -> None:
        """Called once before a run that sends texts (e.g. to log in), so a
        problem stops the run before the first student. No-op by default."""

    def finish(self) -> None:
        """Called once after such a run, even if it failed or was stopped
        (e.g. to close the browser). No-op by default."""


class FakeTextSender(TextSender):
    """Records every send() call instead of texting anyone. `fail_for` lets
    tests/dev simulate specific numbers failing, deterministically."""

    def __init__(self, fail_for: Optional[Set[str]] = None):
        self.fail_for = fail_for or set()
        self.sent: List[dict] = []

    def send(self, student: Student, body: str, message_name: str) -> str:
        if student.phone in self.fail_for:
            raise RuntimeError(f"Simulated text failure for {student.phone}")
        self.sent.append({"to": student.phone, "subject": message_name, "body": body})
        return "Sent"


class UnavailableTextSender(TextSender):
    """Every send fails with a plain explanation, so a run with "Send Text"
    checked shows each text as failed in the results window - instead of
    FakeTextSender's quiet "success" for a text that never went out."""

    MESSAGE = "Texting isn't set up in this app yet - no text was sent."

    def send(self, student: Student, body: str, message_name: str) -> str:
        raise RuntimeError(self.MESSAGE)
