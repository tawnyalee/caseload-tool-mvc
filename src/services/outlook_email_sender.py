# src/services/outlook_email_sender.py
"""The real EmailSender: sends through the desktop Outlook (Classic) the
professor is already signed into, via COM automation (pywin32). Works the
same on Outlook 2016 and Microsoft 365 desktop Outlook (both are 16.0).
The "New Outlook" has no automation support at all, so it can't be used.

Signatures: Outlook does NOT add a signature to mail sent this way (only
when a compose window is shown), so this resolves the chosen signature
name to its .htm file under %APPDATA%\\Microsoft\\Signatures\\ and builds
it in. A signature .htm is a complete HTML page of its own, so the message
goes INSIDE the signature's <body>, right before the signature content,
rather than the two being glued end to end - gluing them puts the message
outside the page entirely (confirmed in a live test 2026-10-20: Gmail
happened to still show it, but that's not something to rely on).

Signature images (e.g. a logo) are referenced by the .htm as local files
("Name_files/image001.png"), which a recipient can't load - each one is
attached and pointed at by a cid: reference instead, the standard way to
embed an image in an email. Not yet verified live: the developer's test
signature has no images, so check this the first time a signature with a
logo is used (see src/CLAUDE.md).

Signatures are required at this organization (see CLAUDE.md), so a
signature name that can't be found fails the send loudly instead of
quietly sending an unsigned email.
"""
import os
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import unquote

from src.services.email_sender import EmailSender

_OL_MAIL_ITEM = 0
# MAPI property for an attachment's Content-ID, which is what a cid:
# reference in the HTML body matches against.
_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"

_BODY_TAG = re.compile(r"<body[^>]*>", re.IGNORECASE)
_IMG_SRC = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*")([^"]+)(")', re.IGNORECASE)


def default_signatures_folder() -> Optional[Path]:
    appdata = os.environ.get("APPDATA")
    return Path(appdata) / "Microsoft" / "Signatures" if appdata else None


def read_signature_html(path: Path) -> str:
    """Outlook usually saves signature .htm files as Windows-1252 (declared
    in a <meta charset>), sometimes UTF-8 - decode with whichever it says."""
    raw = path.read_bytes()
    match = re.search(rb'charset="?([\w-]+)', raw[:2000], re.IGNORECASE)
    candidates = ([match.group(1).decode("ascii")] if match else []) + ["utf-8", "cp1252"]
    for encoding in candidates:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("cp1252", errors="replace")


def combine_body_and_signature(body_html: str, signature_html: str) -> str:
    """Puts the message inside the signature's own HTML page, just after its
    <body> tag, so the result is one well-formed page: message first, then
    the signature, which keeps its own styles. No signature -> body as-is.
    A signature fragment with no <body> tag is simply appended."""
    if not signature_html:
        return body_html
    match = _BODY_TAG.search(signature_html)
    if not match:
        return f"{body_html}<br>{signature_html}"
    return signature_html[:match.end()] + body_html + "<br>" + signature_html[match.end():]


def embed_local_images(html: str, base_folder: Path) -> Tuple[str, List[Tuple[Path, str]]]:
    """Rewrites every <img src> that points at a local file (relative to
    base_folder) to a cid: reference. Returns the new HTML plus a list of
    (file_path, content_id) to attach. Web (http/https), data: and existing
    cid: images are left alone, as are references to files that don't exist."""
    attachments: List[Tuple[Path, str]] = []

    def replace(match: re.Match) -> str:
        src = match.group(2)
        if re.match(r"^(https?:|cid:|data:)", src, re.IGNORECASE):
            return match.group(0)
        path = (base_folder / unquote(src).replace("\\", "/")).resolve()
        if not path.is_file():
            return match.group(0)
        content_id = f"sigimg{len(attachments) + 1}"
        attachments.append((path, content_id))
        return f"{match.group(1)}cid:{content_id}{match.group(3)}"

    return _IMG_SRC.sub(replace, html), attachments


def _connect_to_outlook():
    import win32com.client  # imported here so the rest of the app never needs pywin32 just to start
    return win32com.client.Dispatch("Outlook.Application")


class OutlookEmailSender(EmailSender):
    """`outlook_factory` exists for tests (a fake standing in for Outlook);
    the app uses the default, which connects to the real one. Outlook is
    only contacted on the first send, never at construction, so the app
    starts normally even if Outlook isn't set up."""

    def __init__(
        self,
        signatures_folder: Optional[Path] = None,
        outlook_factory: Callable[[], object] = _connect_to_outlook,
    ):
        self.signatures_folder = Path(signatures_folder) if signatures_folder else default_signatures_folder()
        self._outlook_factory = outlook_factory
        self._outlook = None

    def _get_outlook(self):
        if self._outlook is None:
            self._outlook = self._outlook_factory()
        return self._outlook

    def _load_signature(self, name: str) -> str:
        if not name:
            return ""
        path = self.signatures_folder / f"{name}.htm" if self.signatures_folder else None
        if not path or not path.is_file():
            raise RuntimeError(
                f"Outlook signature '{name}' wasn't found in {self.signatures_folder}. "
                f"Pick a signature that exists on this computer in the Action's settings."
            )
        return read_signature_html(path)

    def send(self, to_email: str, subject: str, body: str, signature: str = "") -> None:
        if not to_email:
            raise RuntimeError("Student has no email address")
        html = combine_body_and_signature(body, self._load_signature(signature))
        html, images = embed_local_images(html, self.signatures_folder) if signature else (html, [])

        try:
            mail = self._get_outlook().CreateItem(_OL_MAIL_ITEM)
        except Exception:
            # The saved connection goes stale if Outlook was closed after the
            # first send - reconnect once (which reopens it) before giving up.
            self._outlook = None
            mail = self._get_outlook().CreateItem(_OL_MAIL_ITEM)
        mail.To = to_email
        mail.Subject = subject
        for path, content_id in images:
            attachment = mail.Attachments.Add(str(path))
            attachment.PropertyAccessor.SetProperty(_PR_ATTACH_CONTENT_ID, content_id)
        mail.HTMLBody = html
        mail.Send()
