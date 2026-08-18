# src/services/name_utils.py
"""Shared name-resolution logic for turning a caseload export row's Name and
preferred-name fields into what a student should actually be addressed as
in communications (emails, texts) — a mail-merge-style "first name" pick.

Used by the Sample.csv -> fake_students.json conversion today, and will be
needed again by the real Salesforce adapter once it's built, since the same
stuprename/Name fields and the same casing problem (some students enter
their name in all caps or all lowercase) exist in the real data too.
"""


def resolve_first_last_name(name: str, preferred_name: str = "") -> tuple[str, str]:
    """Given a raw "Name" value (e.g. "JOHN SMITH") and an optional raw
    preferred-name value (e.g. "johnny"), returns (first_name, last_name)
    to address the student by.

    The preferred name wins for the first name when present; otherwise the
    first name is everything before the first space in Name. The chosen
    first name is normalized to a single capital letter regardless of how
    it was entered, since there's no data-entry validation on these fields
    upstream. last_name is left as-is (not used for greetings, and blindly
    capitalizing it risks mangling multi-word or hyphenated surnames).
    """
    name = (name or "").strip()
    preferred_name = (preferred_name or "").strip()

    parts = name.split(" ", 1)
    default_first = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    first_name = preferred_name if preferred_name else default_first
    return first_name.capitalize(), last_name
