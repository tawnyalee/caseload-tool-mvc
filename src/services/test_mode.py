# src/services/test_mode.py
"""Test mode: run the real app against the real roster without contacting
any real student or touching Salesforce. While it's on:

  - every email goes to ONE address you choose (RedirectingEmailSender),
    with the student it was meant for shown at the top of the email and
    in the subject, so personalization can still be checked
  - notes go to the fake note writer, not Salesforce
  - texts are unaffected (still fake regardless, for now)
  - the app shows a TEST MODE banner and window title

Turned on by a small settings file, data/test_mode.json (gitignored, per
machine):

    {"redirect_email": "you@example.com"}

A file rather than an environment variable on purpose: if someone forgets
about it, the forgotten state is the SAFE one (still redirecting), and
going live means deliberately deleting the file. An unreadable or invalid
file also counts as ON, but with no usable address every send fails -
better a run that fails loudly than one that quietly emails students.
"""
import html
import json
from pathlib import Path
from typing import Optional

from src.services.email_sender import EmailSender

DEFAULT_TEST_MODE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "test_mode.json"

# Sentinel for "file exists but has no usable address" - test mode stays on.
INVALID_REDIRECT = ""


def load_redirect_email(path: Path = DEFAULT_TEST_MODE_FILE) -> Optional[str]:
    """None = test mode off (no file). Otherwise test mode is on, and the
    return value is the address to redirect to (INVALID_REDIRECT if the
    file can't be read or has no address)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        address = json.loads(path.read_text(encoding="utf-8")).get("redirect_email", "")
    except (OSError, ValueError, AttributeError):
        return INVALID_REDIRECT
    return address.strip() if isinstance(address, str) and "@" in address else INVALID_REDIRECT


class RedirectingEmailSender(EmailSender):
    """Wraps the real sender and sends everything to `redirect_to` instead,
    marked with who it was really for. Same wrapper idea as
    CachingStudentDataProvider: callers can't tell the difference."""

    def __init__(self, inner: EmailSender, redirect_to: str):
        self.inner = inner
        self.redirect_to = redirect_to

    def send(self, to_email: str, subject: str, body: str, signature: str = "") -> None:
        # Same failures as a real send would hit, so test runs report them too.
        if not to_email:
            raise RuntimeError("Student has no email address")
        if not self.redirect_to:
            raise RuntimeError(
                "TEST MODE is on but data/test_mode.json has no valid redirect_email - nothing was sent"
            )
        banner = (
            '<p style="background:#fff3cd;border:1px solid #e0b400;padding:8px;font-family:Arial">'
            f"<b>TEST MODE</b> - this email would have been sent to <b>{html.escape(to_email)}</b></p>"
        )
        self.inner.send(self.redirect_to, f"[TEST -> {to_email}] {subject}", banner + body, signature)
