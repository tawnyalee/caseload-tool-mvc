# scripts/test_email_sender_live.py
"""One-off, run-by-hand tool: sends ONE email through the real
OutlookEmailSender, exactly as the app would, to an address you choose
(use your own - never a student's). Needs Outlook Classic set up on this
machine.

    python scripts/test_email_sender_live.py you@example.com "Signature Name"
    python scripts/test_email_sender_live.py you@example.com "Signature Name" --dry-run

The signature name is the file name without .htm, as listed in the app's
signature dropdown (or by scripts/outlook_check.py). Leave it out to send
with no signature.

--dry-run builds the email in Outlook exactly the same way, prints a
summary of what would be sent, then DISCARDS it - nothing is sent.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.outlook_email_sender import OutlookEmailSender, _connect_to_outlook

TEST_BODY = (
    "<p>Hi there,</p>"
    "<p>This is a test from the caseload tool's real Outlook sender.</p>"
    "<p><b>Bold</b>, <i>italic</i>, and a <a href='https://www.wgu.edu'>link</a>.</p>"
)


class _DiscardingMail:
    """Wraps a real Outlook mail item; Send() reports and discards it instead."""

    def __init__(self, mail):
        object.__setattr__(self, "_mail", mail)

    def __getattr__(self, name):
        return getattr(self._mail, name)

    def __setattr__(self, name, value):
        setattr(self._mail, name, value)

    def Send(self):
        html = self._mail.HTMLBody
        low = html.lower()
        print("DRY RUN - would send:")
        print(f"  To: {self._mail.To}   Subject: {self._mail.Subject}")
        print(f"  Attachments (signature images): {self._mail.Attachments.Count}")
        print(f"  <html> tags: {low.count('<html')}, message is inside <body>: "
              f"{low.find('<body') < low.find('this is a test')}")
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html[low.find('<body'):]))
        print(f"  Visible text: {text.strip()[:300]}")
        self._mail.Close(1)  # 1 = olDiscard - nothing is sent or saved
        print("Discarded - nothing was sent.")


class _DiscardingOutlook:
    def __init__(self):
        self._outlook = _connect_to_outlook()

    def CreateItem(self, item_type):
        return _DiscardingMail(self._outlook.CreateItem(item_type))


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv
    if not args:
        print(__doc__)
        return
    to_address = args[0]
    signature = args[1] if len(args) > 1 else ""

    sender = OutlookEmailSender(outlook_factory=_DiscardingOutlook) if dry_run else OutlookEmailSender()
    sender.send(to_address, "Caseload tool - real sender test", TEST_BODY, signature=signature)
    if not dry_run:
        print(f"Sent to {to_address} (signature: {signature or 'none'}). Check that inbox.")


if __name__ == "__main__":
    main()
