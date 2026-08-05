import pytest

from src.services.note_writer import FakeNoteWriter


def test_fake_note_writer_records_written_note():
    writer = FakeNoteWriter()
    writer.write_note(salesforce_id="SF1", subject="Follow up", body="Called student")

    assert len(writer.written) == 1
    assert writer.written[0] == {"salesforce_id": "SF1", "subject": "Follow up", "body": "Called student"}


def test_fake_note_writer_raises_for_configured_failure():
    writer = FakeNoteWriter(fail_for={"SF2"})

    with pytest.raises(RuntimeError):
        writer.write_note(salesforce_id="SF2", subject="Follow up", body="body")

    assert writer.written == []


def test_fake_note_writer_records_follow_up_note_update():
    writer = FakeNoteWriter()
    writer.update_follow_up_note(salesforce_id="SF1", text="Sent welcome email")

    assert writer.follow_up_notes == {"SF1": "Sent welcome email"}


def test_fake_note_writer_follow_up_note_update_raises_for_configured_failure():
    writer = FakeNoteWriter(fail_for={"SF2"})

    with pytest.raises(RuntimeError):
        writer.update_follow_up_note(salesforce_id="SF2", text="Sent welcome email")

    assert writer.follow_up_notes == {}


def test_fake_note_writer_follow_up_note_overwrites_previous_value():
    writer = FakeNoteWriter()
    writer.update_follow_up_note(salesforce_id="SF1", text="First note")
    writer.update_follow_up_note(salesforce_id="SF1", text="Second note")

    assert writer.follow_up_notes == {"SF1": "Second note"}
