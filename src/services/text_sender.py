# src/services/text_sender.py
"""Abstract text delivery, plus a local fake that records what would have
been sent (for tests), and the placeholder the app uses until the real
Mongoose adapter exists. The real adapter implements this same interface.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Set


class TextSender(ABC):
    @abstractmethod
    def send(self, to_phone: str, subject: str, body: str) -> None:
        """Sends a text message. Raises an exception if sending fails."""
        raise NotImplementedError


class FakeTextSender(TextSender):
    """Records every send() call instead of texting anyone. `fail_for` lets
    tests/dev simulate specific numbers failing, deterministically."""

    def __init__(self, fail_for: Optional[Set[str]] = None):
        self.fail_for = fail_for or set()
        self.sent: List[dict] = []

    def send(self, to_phone: str, subject: str, body: str) -> None:
        if to_phone in self.fail_for:
            raise RuntimeError(f"Simulated text failure for {to_phone}")
        self.sent.append({"to": to_phone, "subject": subject, "body": body})


class UnavailableTextSender(TextSender):
    """What the app uses until real Mongoose texting is built. Every send
    fails with a plain explanation, so a run with "Send Text" checked shows
    each text as failed in the results window - instead of FakeTextSender's
    quiet "success" for a text that never went out."""

    MESSAGE = "Texting isn't set up in this app yet - no text was sent."

    def send(self, to_phone: str, subject: str, body: str) -> None:
        raise RuntimeError(self.MESSAGE)
