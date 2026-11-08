import json

import pytest

from src.services import essential_actions as ea
from src.services.oa_emails import oa_pass_rows
from src.services.salesforce_direct_save import CLOSE_EA_DISPLAY, DirectSaveFailed, close_ea_record, is_closed


def _row():
    return oa_pass_rows([{
        "Id": "a5hEA1", "Name": "Student Passed Objective Assessment -Instructor", "Contact__c": "003ABC",
        "CourseCode__c": "D424", "Contact__r": {"StudentID__c": "1", "Name": "Jane Doe", "WGUEmail__c": "j@x.test"},
    }])[0]


class _SalesforcePage:
    """Answers the page's Aura posts like Salesforce: the student's EAs, and
    a note save that closes the EA (unless `closes` is False)."""

    def __init__(self, closes=True, save_state="SUCCESS"):
        self.closes, self.save_state = closes, save_state
        self.saved = []
        self.completed = False

    def evaluate(self, _script, args):
        action = json.loads(args[1])["actions"][0]
        if "getEssentialActions" in action["descriptor"]:
            record = {"Id": "a5hEA1", "Status__c": "Open", "CompletedDateTime__c": "2026-11-08" if self.completed else None}
            return {"status": 200, "body": json.dumps({"actions": [{"state": "SUCCESS", "returnValue": {"eas": [record]}}]})}
        self.saved.append(action["params"])
        if self.save_state == "SUCCESS":
            self.completed = self.closes
        return {"status": 200, "body": json.dumps({"actions": [{"state": self.save_state}]})}

    def is_closed(self):
        return False

    def wait_for_timeout(self, _ms):
        pass


def _service(page, form=None, direct=True):
    service = ea.PlaywrightEssentialActions(use_direct_saves=lambda: direct, fill_form=form)
    service._page = page
    service._aura = type("Creds", (), {"ready": True, "token": "t", "context": "c"})()
    service._open = lambda: None
    service._reload = lambda: None
    return service


def test_the_close_record_is_the_full_ea_plus_the_chosen_note_action():
    record = close_ea_record([{"Id": "a5h1", "Status__c": "Open"}], "a5h1")
    assert record == {"Id": "a5h1", "Status__c": "Open", "NoteAction": None, "NoteActionDisplay": CLOSE_EA_DISPLAY}
    assert len(CLOSE_EA_DISPLAY) == 19  # what the recorded form sent
    with pytest.raises(DirectSaveFailed):
        close_ea_record([], "a5h1")


def test_closed_means_a_completed_date_or_gone():
    assert is_closed([{"Id": "a5h1", "CompletedDateTime__c": "2026-11-08"}], "a5h1")
    assert is_closed([], "a5h1")
    assert not is_closed([{"Id": "a5h1", "CompletedDateTime__c": None}], "a5h1")


def test_direct_save_sends_the_note_with_the_ea_to_close_and_checks_it_closed():
    page = _SalesforcePage()
    how = _service(page).save_note_and_close(_row(), "Congrats!", "Sent ST email")
    assert how == "Written and closed (direct)"
    params = page.saved[0]
    assert params["contactId"] == "003ABC" and params["courseCode"] == "D424" and params["subject"] == "Congrats!"
    assert [r["Id"] for r in params["saveNoteAndCloseEAs"]] == ["a5hEA1"]


def test_a_saved_note_with_the_ea_still_open_is_never_sent_again_through_the_form():
    page = _SalesforcePage(closes=False)
    form_calls = []
    service = _service(page, form=lambda *args: form_calls.append(args))
    with pytest.raises(ea.EaNotClosed, match="still open"):
        service.save_note_and_close(_row(), "Congrats!", "Sent")
    assert form_calls == [] and len(page.saved) == 1


def test_a_direct_save_salesforce_refused_falls_back_to_the_form_and_checks_it_closed():
    page = _SalesforcePage(save_state="ERROR")
    form_calls = []

    def form(*args):
        form_calls.append(args)
        page.completed = True  # Submit closed the EA

    how = _service(page, form=form).save_note_and_close(_row(), "Congrats!", "Sent")
    assert how == "Written and closed (form)" and len(form_calls) == 1


def test_a_form_submit_that_leaves_the_ea_open_is_reported():
    page = _SalesforcePage(save_state="ERROR")
    with pytest.raises(ea.EaNotClosed, match="form, but the Essential Action is still open"):
        _service(page, form=lambda *args: None).save_note_and_close(_row(), "Congrats!", "Sent")


def test_with_direct_saves_off_only_the_form_is_used():
    page = _SalesforcePage()
    form_calls = []
    _service(page, form=lambda *args: form_calls.append(args), direct=False).save_note_and_close(_row(), "C", "S")
    assert page.saved == [] and len(form_calls) == 1


def test_test_mode_reads_the_real_list_but_writes_nothing():
    real = ea.FakeEssentialActions(rows=[{"Id": "x"}])
    test_mode = ea.TestModeEssentialActions(real)
    assert test_mode.read_rows() == [{"Id": "x"}]
    assert "TEST MODE" in test_mode.save_note_and_close(_row(), "C", "S")
    assert real.closed == []
