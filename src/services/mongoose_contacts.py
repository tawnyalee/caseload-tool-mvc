# src/services/mongoose_contacts.py
"""Join a Mongoose (Cadence) contacts/segment CSV export to the roster so a
text can be addressed by Mongoose Contact Id instead of phone number.

Why: `Student.phone` (MobilePhone) can be blank even for a student Mongoose
already has on file - matching by phone alone silently drops those students
from any texting automation. Mongoose's own recipient search also accepts
the Salesforce Contact Id as a search term, which is unique and blank-phone-
proof (unlike a name, which can collide across students). This module is the
concrete answer to the `phone` field's open question in
docs/filter_engine_requirements.md ("blocked on...Cadence-ID-based texting
integration").

The export's column names below come from another WGU-caseload-automation
project's working Mongoose integration (github.com/ashejim/caseload-tool) -
the developer has used that project's texting feature daily for weeks and
confirms the underlying logic (this Contact-Id matching included) is solid;
their complaint with that project is UI/UX polish, not functionality. Since
Mongoose/Cadence is a third-party product both projects integrate with
rather than something either institution built, its export format is
unlikely to differ per org the way a bespoke Salesforce page would. Still,
this hasn't been run against a real export from THIS org yet - if one ever
turns out different, check it against the actual header and adjust the
*_COLUMN constants below. Nothing here is wired into TextSender/ActionRunner
yet - same "build it, test it, swap in only when ready" pattern as the
Salesforce work in salesforce_browser_session.py / salesforce_callbacks.py.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.services import app_paths
from typing import Dict, List, Optional

from src.models.student import Student

# Column names in a Mongoose contacts/segment export. Unconfirmed against a
# real export from this org yet - see module docstring.
CONTACT_ID_COLUMN = "contactId"
MOBILE_COLUMN = "mobileNumber"
FIRST_NAME_COLUMN = "firstName"
LAST_NAME_COLUMN = "lastName"
OPTED_OUT_COLUMN = "optedOut"

# The persisted StudentID -> Mongoose Contact Id map lives with the rest of
# the per-user data (%LOCALAPPDATA%\CaseloadTool - see app_paths.py).

_NON_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """Strips `raw` to bare digits and drops a leading US country code, so
    the caseload's MobilePhone and Mongoose's mobileNumber can be compared
    on equal footing regardless of formatting ("(336) 213-2291" vs.
    "3362132291"). Returns "" if the result isn't a plain 10-digit number -
    an unusable value should never accidentally match another unusable one."""
    digits = _NON_DIGITS.sub("", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


def is_contacts_export(path) -> bool:
    """True if `path` looks like a Mongoose contacts export (cheap header
    sniff), so it can be told apart from a Salesforce caseload CSV sitting
    in the same folder."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            header = f.readline()
        return CONTACT_ID_COLUMN.lower() in header.lower()
    except OSError:
        return False


@dataclass
class MongooseContact:
    contact_id: str
    first_name: str
    last_name: str
    mobile: str  # normalized 10-digit, "" if unusable
    opted_out: bool


def load_contacts(path) -> List[MongooseContact]:
    """Parses a Mongoose contacts/segment export into MongooseContact rows.
    Rows without a contact id are dropped - there's nothing to join them by."""
    contacts: List[MongooseContact] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            contact_id = (row.get(CONTACT_ID_COLUMN) or "").strip()
            if not contact_id:
                continue
            contacts.append(MongooseContact(
                contact_id=contact_id,
                first_name=(row.get(FIRST_NAME_COLUMN) or "").strip(),
                last_name=(row.get(LAST_NAME_COLUMN) or "").strip(),
                mobile=normalize_phone(row.get(MOBILE_COLUMN) or ""),
                opted_out=(row.get(OPTED_OUT_COLUMN) or "").strip().lower()
                in ("true", "1", "yes", "y"),
            ))
    return contacts


def _full_name(first: str, last: str) -> str:
    return f"{first} {last}".strip().lower()


def build_contact_id_map(
    students: List[Student],
    contacts: List[MongooseContact],
    *,
    include_opted_out: bool = False,
) -> Dict[str, str]:
    """Maps Student.salesforce_id -> Mongoose contact_id.

    Joins by normalized phone first (unique, unambiguous), then by full name
    as a fallback for students whose caseload phone is blank - the whole
    reason this join exists. A name that isn't unique across the export is
    never used for the fallback, since there'd be no way to tell which
    student it actually means."""
    usable = [c for c in contacts if include_opted_out or not c.opted_out]

    by_mobile: Dict[str, MongooseContact] = {}
    by_name: Dict[str, MongooseContact] = {}
    name_counts: Dict[str, int] = {}
    for c in usable:
        if c.mobile:
            by_mobile.setdefault(c.mobile, c)
        name = _full_name(c.first_name, c.last_name)
        if name:
            name_counts[name] = name_counts.get(name, 0) + 1
            by_name.setdefault(name, c)

    mapping: Dict[str, str] = {}
    for student in students:
        if not student.salesforce_id:
            continue
        match = None
        mobile = normalize_phone(student.phone)
        if mobile:
            match = by_mobile.get(mobile)
        if match is None:
            name = _full_name(student.first_name, student.last_name)
            if name and name_counts.get(name, 0) == 1:
                match = by_name.get(name)
        if match:
            mapping[student.salesforce_id] = match.contact_id
    return mapping


def load_and_map(path, students: List[Student], **kwargs) -> Dict[str, str]:
    """Convenience: parses the export at `path` and joins it to `students` in
    one call. Returns {} if the file is missing/unreadable rather than
    raising - a missing export shouldn't crash whatever's calling this, just
    leave the map empty for that run."""
    try:
        contacts = load_contacts(Path(path))
    except OSError:
        return {}
    return build_contact_id_map(students, contacts, **kwargs)


class MongooseContactIdRepository:
    """Persists the Student.salesforce_id -> Mongoose contact_id map to a
    local JSON file, same load/save pattern as GroupRepository/
    ActionRepository. Lets the app reuse a previously loaded mapping on
    startup instead of requiring a fresh segment export every session - the
    map only needs refreshing when Mongoose's own contact list changes
    (a student added/removed, a phone number corrected)."""

    def __init__(self, data_file: Optional[Path] = None) -> None:
        self.data_file = data_file or app_paths.mongoose_contact_ids_file()
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def load(self) -> Dict[str, str]:
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save(self, mapping: Dict[str, str]) -> None:
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=4)

    def merge(self, mapping: Dict[str, str]) -> Dict[str, str]:
        """Loads the persisted map, overlays `mapping` on top (new/changed
        ids win, nothing already-correct is rewritten), saves, and returns
        the merged result - so a re-load only touches what actually moved."""
        current = self.load()
        current.update(mapping)
        self.save(current)
        return current
