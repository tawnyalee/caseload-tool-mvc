# src/services/salesforce_direct_save.py
"""Saves a note or follow-up by sending Salesforce the same request its own
form sends, from inside the logged-in Caseload page, instead of clicking
through the form. That's one request instead of a page load, a roster search
and a form, and the course code goes in as plain text rather than through the
typed search box.

These are Salesforce's private Aura requests, not a supported API, so an update
could change them. PlaywrightNoteWriter falls back to the form on anything but
a clear success (see note_writer.py).

The approach and request details come from Jim Ashe's caseload-tool
(github.com/ashejim/caseload-tool), used with his permission (2026-11-02).

aura.token and aura.context ride in every Aura request the page makes, so
AuraCredentials reads them as the page loads. Kept in memory only.
"""
import html
import json
import re
from typing import Optional
from urllib.parse import parse_qs

NOTE_TYPE_EMAIL_TO_STUDENT = "Email to Student"

_POST_AURA = """async ([endpoint, message, context, token, pageUri]) => {
    const body = new URLSearchParams();
    body.set('message', message);
    body.set('aura.context', context);
    body.set('aura.pageURI', pageUri);
    body.set('aura.token', token);
    const response = await fetch(endpoint, {
        method: 'POST', credentials: 'include',
        headers: {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'},
        body: body.toString(),
    });
    return {status: response.status, body: await response.text()};
}"""


class DirectSaveFailed(RuntimeError):
    """Salesforce didn't clearly confirm the save, so the form should be used."""


class AuraCredentials:
    """Keeps the newest token and context seen in the page's Aura requests."""

    def __init__(self):
        self.token = ""
        self.context = ""

    @property
    def ready(self) -> bool:
        return bool(self.token and self.context)

    def on_request(self, request) -> None:
        """Playwright context "request" handler. Never raises: a listener
        error must not break the page."""
        try:
            if request.method.upper() != "POST" or "/aura" not in request.url:
                return
            fields = parse_qs(request.post_data or "")
            token = (fields.get("aura.token") or [""])[0]
            context = (fields.get("aura.context") or [""])[0]
            if token and context:
                self.token, self.context = token, context
        except Exception:
            pass


def note_body_as_html(text: str) -> str:
    """Each line a paragraph, like a note typed into the form."""
    lines = (text or "").split("\n")
    return "".join(f"<p>{html.escape(line)}</p>" if line.strip() else "<p><br></p>" for line in lines)


def result_state(body: str) -> str:
    """The first action's state in an Aura response, "" if there's none. Aura
    can put text such as while(1); before the JSON."""
    start = body.find("{")
    try:
        actions = json.loads(body[start:]).get("actions") or [] if start >= 0 else []
        return str(actions[0].get("state") or "") if actions else ""
    except (ValueError, AttributeError, TypeError):
        match = re.search(r'"state"\s*:\s*"([A-Z]+)"', body)
        return match.group(1) if match else ""


def return_value(body: str):
    """The first action's returnValue in an Aura response, or None."""
    start = (body or "").find("{")
    try:
        actions = json.loads(body[start:]).get("actions") or [] if start >= 0 else []
        return actions[0].get("returnValue") if actions else None
    except (ValueError, AttributeError, TypeError):
        return None


def _post(page, credentials: AuraCredentials, endpoint: str, action: dict, page_uri: str):
    """Sends one Aura action; returns its returnValue. Anything but SUCCESS
    raises DirectSaveFailed."""
    message = json.dumps({"actions": [{"id": "1;a", **action}]})
    result = page.evaluate(_POST_AURA, [endpoint, message, credentials.context, credentials.token, page_uri])
    body = result.get("body") or ""
    state = result_state(body)
    if state != "SUCCESS":
        raise DirectSaveFailed(f"Salesforce answered state={state or 'none'} (HTTP {result.get('status')})")
    return return_value(body)


def save_note(
    page, credentials: AuraCredentials, contact_id: str, course_code: str, subject: str, body: str,
    note_type: str = NOTE_TYPE_EMAIL_TO_STUDENT, close_eas: Optional[list] = None,
) -> None:
    """`close_eas`: full Essential Action records to close with this note,
    the way the form's Add Note & Close EA does (see close_ea_record)."""
    note = {
        "Type__c": "", "Name": "",
        "CourseProgramInfoDiscussed__c": False, "CourseProgramInformationRequested__c": False,
        "SetAcademicGoals__c": False, "StudentLearningOccurred__c": False, "NonAcademicContentCovered__c": False,
    }
    params = {
        "contactId": contact_id, "note": note, "extNote": {}, "survey": {"Student__c": contact_id},
        "saveNoteEAs": [], "saveNoteAndCloseEAs": list(close_eas or []), "saveExtNoteEAs": [], "saveExtNoteAndCloseEAs": [],
        "noteType": note_type, "courseCode": course_code, "subject": subject or note_type,
        "text": note_body_as_html(body), "removedEAJunctionIds": [],
    }
    _post(
        page, credentials, "/aura?other.Notes.saveNoteCmpValues=1",
        {
            "descriptor": "apex://NotesController/ACTION$saveNoteCmpValues",
            "callingDescriptor": "markup://c:NoteCmp", "params": params,
        },
        f"/lightning/r/Contact/{contact_id}/view",
    )


def save_follow_up(page, credentials: AuraCredentials, course_record_id: str, text: str) -> None:
    _post(
        page, credentials, "/aura?other.MentorForceAuraMethods.saveCourseFollowupNoteToSF=1",
        {
            "descriptor": "apex://MentorForceAuraMethods/ACTION$saveCourseFollowupNoteToSF",
            "callingDescriptor": "markup://c:MentoringCMUtilities",
            "params": {"theStudentAcaCourseId": course_record_id, "theCourseFollowupNote": text},
        },
        "/lightning/n/Caseload_App_Page",
    )


# What the form sends as the chosen note action when closing an EA (recorded
# 2026-11-04: NoteAction null, NoteActionDisplay 19 characters).
CLOSE_EA_DISPLAY = "Add Note & Close EA"


def get_essential_actions(page, credentials: AuraCredentials, contact_id: str) -> list:
    """The student's Essential Actions as full records, from the same request
    the Essential Action table makes (recorded 2026-11-04)."""
    value = _post(
        page, credentials, "/aura?other.EssentialActionDataTable.getEssentialActions=1",
        {
            "descriptor": "apex://EssentialActionDataTableController/ACTION$getEssentialActions",
            "callingDescriptor": "markup://c:EssentialActionDataTable", "params": {"contactId": contact_id},
        },
        f"/lightning/r/Contact/{contact_id}/view",
    )
    eas = value.get("eas") if isinstance(value, dict) else None
    if not isinstance(eas, list):
        raise DirectSaveFailed("Salesforce didn't return the student's Essential Actions")
    return [ea for ea in eas if isinstance(ea, dict)]


def close_ea_record(eas: list, ea_id: str) -> dict:
    """The record the save needs to close `ea_id`: the full EA plus the
    chosen note action, as the form sends it."""
    record = next((ea for ea in eas if str(ea.get("Id") or "") == ea_id), None)
    if record is None:
        raise DirectSaveFailed("That Essential Action wasn't in the student's list (already closed?)")
    return {**record, "NoteAction": None, "NoteActionDisplay": CLOSE_EA_DISPLAY}


def is_closed(eas: list, ea_id: str) -> bool:
    """After the save: closed means it has a completed date, or is gone."""
    record = next((ea for ea in eas if str(ea.get("Id") or "") == ea_id), None)
    return record is None or bool(record.get("CompletedDateTime__c"))
