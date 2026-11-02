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


def _post(page, credentials: AuraCredentials, endpoint: str, action: dict, page_uri: str) -> None:
    message = json.dumps({"actions": [{"id": "1;a", **action}]})
    result = page.evaluate(_POST_AURA, [endpoint, message, credentials.context, credentials.token, page_uri])
    state = result_state(result.get("body") or "")
    if state != "SUCCESS":
        raise DirectSaveFailed(f"Salesforce answered state={state or 'none'} (HTTP {result.get('status')})")


def save_note(
    page, credentials: AuraCredentials, contact_id: str, course_code: str, subject: str, body: str,
    note_type: str = NOTE_TYPE_EMAIL_TO_STUDENT,
) -> None:
    note = {
        "Type__c": "", "Name": "",
        "CourseProgramInfoDiscussed__c": False, "CourseProgramInformationRequested__c": False,
        "SetAcademicGoals__c": False, "StudentLearningOccurred__c": False, "NonAcademicContentCovered__c": False,
    }
    params = {
        "contactId": contact_id, "note": note, "extNote": {}, "survey": {"Student__c": contact_id},
        "saveNoteEAs": [], "saveNoteAndCloseEAs": [], "saveExtNoteEAs": [], "saveExtNoteAndCloseEAs": [],
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
