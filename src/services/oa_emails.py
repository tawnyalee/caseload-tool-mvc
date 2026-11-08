# src/services/oa_emails.py
"""What Send OA Emails sends (developer's design, 2026-11-04).

An OA pass only shows up in Salesforce's Essential Actions list, never on the
roster, so these students may not be on the professor's caseload at all.
Each Essential Action row whose Reason starts with "Student Passed Objective
Assessment" (the ending varies by role: "-Instructor", "- Mentor", ...) is
matched by its course code to that course's "OA passed email" in Settings.

  - email subject: "Congrats!"; note subject: "OA Pass" (developer, 2026-11-08)
  - the email: "Hello <preferred or first name>," above the saved template
  - the note: "Congratulated ST on passing OA" (the course is on the note itself),
    saved with the Essential Action closed (Add Note & Close EA)
  - no follow-up note (developer)

This module only reads rows and builds the emails. Reading the list from
Salesforce and closing the Essential Action live in essential_actions.py.
"""
import html
import json
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from src.models.group import Group
from src.models.student import Student
from src.services.name_utils import resolve_first_last_name
from src.services.task_emails import html_to_plain_text  # noqa: F401 (the review preview uses it)

OA_PASS_REASON_PREFIX = "Student Passed Objective Assessment"
OA_EMAIL_SUBJECT = "Congrats!"
OA_NOTE_SUBJECT = "OA Pass"
OA_NOTE_BODY = "Congratulated ST on passing OA"


@dataclass
class EssentialActionRow:
    """One row of the Essential Actions list, in the app's own words. The
    Salesforce field names stay in from_salesforce()."""
    ea_id: str            # the Essential Action's own record id ("a5h...")
    contact_id: str       # the student's Salesforce Contact Id ("003...")
    student_id: str
    full_name: str
    preferred_name: str
    email: str
    course_code: str
    reason: str
    timezone: str = ""

    @classmethod
    def from_salesforce(cls, row: dict) -> "EssentialActionRow":
        contact = row.get("Contact__r") if isinstance(row.get("Contact__r"), dict) else {}

        def text(value) -> str:
            return str(value or "").strip()

        return cls(
            ea_id=text(row.get("Id")),
            contact_id=text(row.get("Contact__c")),
            student_id=text(contact.get("StudentID__c")),
            full_name=text(contact.get("Name")),
            preferred_name=text(row.get("Student_Preferred_Name__c")),
            email=text(contact.get("WGUEmail__c")),
            course_code=text(row.get("CourseCode__c")),
            reason=text(row.get("Name")),
            timezone=text(row.get("StudentTimeZone__c")),
        )

    @property
    def is_oa_pass(self) -> bool:
        return self.reason.lower().startswith(OA_PASS_REASON_PREFIX.lower())

    def as_student(self) -> Student:
        """A Student for the email and note steps, greeted by preferred name,
        else first name (decided 2026-11-02)."""
        first, last = resolve_first_last_name(self.full_name, self.preferred_name)
        return Student(
            salesforce_id=self.student_id, first_name=first, last_name=last, email=self.email,
            phone="", has_signed_up_for_text=False, course_code=self.course_code,
            timezone=self.timezone, texting_contact_id=self.contact_id,
        )


def rows_from_ea_response(body: str) -> List[dict]:
    """The row dicts from a getEssentialActionRows response (an Aura envelope).
    The list may be the returnValue itself or sit one level inside it.
    Anything unreadable gives []."""
    start = (body or "").find("{")
    try:
        envelope = json.loads(body[start:]) if start >= 0 else {}
    except ValueError:
        return []
    rows: List[dict] = []
    for action in (envelope.get("actions") or []) if isinstance(envelope, dict) else []:
        if not isinstance(action, dict) or action.get("state") != "SUCCESS":
            continue
        value = action.get("returnValue")
        if isinstance(value, dict):
            value = next((v for v in value.values() if isinstance(v, list)), [])
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict) and "Contact__c" in row)
    return rows


def oa_pass_rows(rows: Iterable[dict]) -> List[EssentialActionRow]:
    """Only the OA passes, once each (by Essential Action id)."""
    seen, found = set(), []
    for raw in rows:
        row = EssentialActionRow.from_salesforce(raw)
        if row.is_oa_pass and row.ea_id and row.ea_id not in seen:
            seen.add(row.ea_id)
            found.append(row)
    return found


@dataclass
class OaEmail:
    row: EssentialActionRow
    student: Student
    group: Optional[Group]
    subject: str = OA_EMAIL_SUBJECT
    body: str = ""
    problem: str = ""     # why it can't be sent; listed as skipped
    email_name: str = ""  # what the review window calls this email

    @property
    def note_body(self) -> str:
        return OA_NOTE_BODY


def course_for(course_code: str, groups: Iterable[Group]) -> Optional[Group]:
    code = (course_code or "").strip().upper()
    for group in groups:
        if group.is_course and group.course_code.strip().upper() == code:
            return group
    return None


def build_oa_email(row: EssentialActionRow, groups: Iterable[Group], get_template: Callable) -> OaEmail:
    student = row.as_student()
    group = course_for(row.course_code, groups)
    oa_email = OaEmail(row=row, student=student, group=group)
    if not row.contact_id.startswith("003"):
        oa_email.problem = "Essential Action has no Salesforce contact, so no note can be saved"
    elif not row.email:
        oa_email.problem = "No WGU email on the Essential Action"
    elif group is None:
        oa_email.problem = f"{row.course_code or 'No course'} isn't a course in Settings"
    elif not group.has_objective_assessment:
        oa_email.problem = f"{group.course_code} doesn't have 'Has an objective assessment' checked in Settings"
    elif not group.oa_email_template_id:
        oa_email.problem = f"No OA passed email set up for {group.course_code} (see Settings)"
    else:
        template = get_template(group.oa_email_template_id)
        if template is None:
            oa_email.problem = f"The OA passed email chosen for {group.course_code} no longer exists (see Settings)"
        else:
            oa_email.body = f"<p>Hello {html.escape(student.first_name)},</p>{template.body}"
            oa_email.email_name = f"{group.course_code} — {template.name}"
    return oa_email


def build_oa_emails(rows: Iterable[EssentialActionRow], groups: List[Group], get_template: Callable) -> List[OaEmail]:
    return [build_oa_email(row, groups, get_template) for row in rows]


def batches_for_review(emails: List[OaEmail]) -> List[List[OaEmail]]:
    """Sendable emails, one batch per course."""
    batches: Dict[str, List[OaEmail]] = {}
    for oa_email in emails:
        if not oa_email.problem:
            batches.setdefault(oa_email.email_name, []).append(oa_email)
    return [batches[key] for key in sorted(batches)]
