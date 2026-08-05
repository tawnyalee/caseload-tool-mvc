# src/services/email_sender.py
"""Abstract email delivery, plus a local fake that records what would have
been sent instead of actually emailing anyone. The real adapter (Outlook,
via COM automation) implements this same interface later — nothing that
calls send() needs to change when that happens.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Set


class EmailSender(ABC):
    @abstractmethod
    def send(self, to_email: str, subject: str, body: str, signature: str = "") -> None:
        """Sends an email. Raises an exception if sending fails."""
        raise NotImplementedError


class FakeEmailSender(EmailSender):
    """Records every send() call instead of emailing anyone. `fail_for` lets
    tests/dev simulate specific addresses failing, deterministically."""

    def __init__(self, fail_for: Optional[Set[str]] = None):
        self.fail_for = fail_for or set()
        self.sent: List[dict] = []

    def send(self, to_email: str, subject: str, body: str, signature: str = "") -> None:
        if to_email in self.fail_for:
            raise RuntimeError(f"Simulated email failure for {to_email}")
        self.sent.append({"to": to_email, "subject": subject, "body": body, "signature": signature})
