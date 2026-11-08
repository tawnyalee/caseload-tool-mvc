import json
from types import SimpleNamespace

from src.models.group import Group
from src.services import oa_emails as oa


def _raw(**overrides):
    row = {
        "Id": "a5hEA1", "Name": "Student Passed Objective Assessment -Instructor",
        "Contact__c": "003ABC", "CourseCode__c": "D424", "Student_Preferred_Name__c": "",
        "StudentTimeZone__c": "PST",
        "Contact__r": {"StudentID__c": "000111", "Name": "JANE DOE", "WGUEmail__c": "jdoe@example.test"},
    }
    row.update(overrides)
    return row


def _course(**overrides):
    fields = dict(name="D424", is_course=True, course_code="D424", has_objective_assessment=True,
                  oa_email_template_id="T1")
    fields.update(overrides)
    return Group(**fields)


def _templates(template_id):
    return SimpleNamespace(name="OA congrats", body="<p>Great job!</p>") if template_id == "T1" else None


def test_any_reason_starting_with_the_oa_pass_wording_counts_whatever_the_role():
    rows = [_raw(Id="1"), _raw(Id="2", Name="Student Passed Objective Assessment - Mentor"),
            _raw(Id="3", Name="Student Failed Objective Assessment"), _raw(Id="1")]
    assert [r.ea_id for r in oa.oa_pass_rows(rows)] == ["1", "2"]


def test_rows_are_read_from_the_aura_envelope_list_or_nested():
    body = "while(1);" + json.dumps({"actions": [{"state": "SUCCESS", "returnValue": [_raw()]}]})
    assert len(oa.rows_from_ea_response(body)) == 1
    nested = json.dumps({"actions": [{"state": "SUCCESS", "returnValue": {"rows": [_raw()]}}]})
    assert len(oa.rows_from_ea_response(nested)) == 1
    assert oa.rows_from_ea_response("not json") == []


def test_greets_by_preferred_name_else_first_name():
    plain = oa.EssentialActionRow.from_salesforce(_raw()).as_student()
    assert plain.first_name == "Jane" and plain.salesforce_id == "000111"
    preferred = oa.EssentialActionRow.from_salesforce(_raw(Student_Preferred_Name__c="Jo")).as_student()
    assert preferred.first_name == "Jo"


def test_the_email_is_hello_plus_the_course_template_and_the_note_names_the_course():
    row = oa.oa_pass_rows([_raw()])[0]
    email = oa.build_oa_email(row, [_course()], _templates)
    assert not email.problem
    assert email.subject == "Congrats!"
    assert email.body == "<p>Hello Jane,</p><p>Great job!</p>"
    assert email.note_body == "Congratulated ST on passing OA"


def test_students_it_cant_email_are_listed_with_the_reason():
    row = oa.oa_pass_rows([_raw()])[0]
    assert "isn't a course" in oa.build_oa_email(row, [], _templates).problem
    assert "objective assessment" in oa.build_oa_email(
        row, [_course(has_objective_assessment=False)], _templates).problem
    assert "No OA passed email" in oa.build_oa_email(row, [_course(oa_email_template_id="")], _templates).problem
    assert "no longer exists" in oa.build_oa_email(row, [_course(oa_email_template_id="gone")], _templates).problem
    no_contact = oa.oa_pass_rows([_raw(Contact__c="")])[0]
    assert "no Salesforce contact" in oa.build_oa_email(no_contact, [_course()], _templates).problem


# --- running: email, then the note with the Essential Action closed --------

from unittest.mock import MagicMock

from src.services.action_runner import ActionRunner
from src.services.email_sender import FakeEmailSender
from src.services.essential_actions import EaNotClosed, FakeEssentialActions
from src.services.note_writer import FakeNoteWriter
from src.services.text_sender import FakeTextSender


def _runner(rows, email_sender=None):
    templates = MagicMock()
    templates.get_by_id.side_effect = _templates
    runner = ActionRunner(MagicMock(), email_sender or FakeEmailSender(), FakeTextSender(), FakeNoteWriter(),
                          templates, MagicMock())
    return runner, FakeEssentialActions(rows)


def test_each_oa_pass_gets_the_email_then_a_note_that_closes_its_essential_action():
    runner, eas = _runner([_raw(), _raw(Id="a5hOther", Name="Missed appointment")])
    found = runner.get_oa_emails([_course()], eas)

    summary = runner.run_oa_emails(found, "Sig", eas)

    assert [(r.step_type, r.outcome) for r in summary.results] == [("email", "success"), ("note", "success")]
    sent = runner.email_sender.sent[0]
    assert (sent["to"], sent["subject"], sent["signature"]) == ("jdoe@example.test", "Congrats!", "Sig")
    assert eas.closed == [{"ea_id": "a5hEA1", "subject": "OA Pass",
                           "body": "Congratulated ST on passing OA"}]
    assert runner.note_writer.written == []  # the note goes through the Essential Action, no follow-up


def test_a_failed_email_leaves_the_essential_action_open():
    runner, eas = _runner([_raw()])
    runner.email_sender = MagicMock()
    runner.email_sender.send.side_effect = RuntimeError("Outlook said no")
    summary = runner.run_oa_emails(runner.get_oa_emails([_course()], eas), "Sig", eas)
    assert [(r.step_type, r.outcome) for r in summary.results] == [("email", "failed"), ("note", "skipped")]
    assert eas.closed == []


def test_unsendable_passes_are_listed_and_the_review_selection_is_respected():
    runner, eas = _runner([_raw(), _raw(Id="a5h2", Contact__r={"StudentID__c": "222", "Name": "Al Bo",
                                                            "WGUEmail__c": "al@example.test"}),
                           _raw(Id="a5h3", CourseCode__c="C999")])
    found = runner.get_oa_emails([_course()], eas)
    key = found[0].email_name

    summary = runner.run_oa_emails(found, "Sig", eas, included_ids_by_key={key: {"222"}})

    assert [e["to"] for e in runner.email_sender.sent] == ["al@example.test"]
    skipped = [r for r in summary.results if r.outcome == "skipped"]
    assert len(skipped) == 1 and "C999" in skipped[0].detail


def test_a_note_saved_with_the_essential_action_still_open_is_a_failure_to_fix_by_hand():
    runner, eas = _runner([_raw()])
    eas.save_note_and_close = MagicMock(side_effect=EaNotClosed("Note saved, but the Essential Action is still open"))
    summary = runner.run_oa_emails(runner.get_oa_emails([_course()], eas), "Sig", eas)
    note = summary.results[1]
    assert (note.step_type, note.outcome) == ("note", "failed") and "still open" in note.detail
