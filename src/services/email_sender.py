# src/services/email_sender.py
"""Abstract email delivery, plus a local fake that records what would have
been sent instead of actually emailing anyone. The real adapter (Outlook,
via COM automation) implements this same interface later — nothing that
calls send() needs to change when that happens.
"""
import os
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
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


class SmtpEmailSender(EmailSender):
    """TEMPORARY testing tool, not the real adapter. The real adapter will
    be Outlook via COM automation (see module docstring) - this exists only
    to prove the app's send pipeline (AddActionView/DashboardView ->
    ActionRunner -> EmailSender.send()) actually delivers a real email
    somewhere, using a personal Gmail account, before Outlook is available
    to test against (needs a work account, not being used in this phase).

    Ignores `signature` entirely on purpose - signature handling is an
    Outlook-specific concern (see CLAUDE.md) not worth building here.

    Credentials are read from environment variables, never hardcoded:
        TEST_SMTP_EMAIL          - the sending Gmail address
        TEST_SMTP_APP_PASSWORD   - a Gmail App Password (not the account
                                    password - generated in Google Account
                                    settings), set locally by whoever runs
                                    this, never committed to the repo.
    """

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(self, email_env_var: str = "TEST_SMTP_EMAIL", password_env_var: str = "TEST_SMTP_APP_PASSWORD"):
        self.sender_email = os.environ.get(email_env_var)
        self.app_password = os.environ.get(password_env_var)
        if not self.sender_email or not self.app_password:
            raise RuntimeError(
                f"SmtpEmailSender needs {email_env_var} and {password_env_var} set as "
                f"environment variables (a Gmail address and an App Password for it)."
            )

    def send(self, to_email: str, subject: str, body: str, signature: str = "") -> None:
        message = MIMEText(body, "html")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = to_email

        with smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT) as server:
            server.starttls()
            server.login(self.sender_email, self.app_password)
            server.sendmail(self.sender_email, [to_email], message.as_string())
