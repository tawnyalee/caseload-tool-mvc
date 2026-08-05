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
