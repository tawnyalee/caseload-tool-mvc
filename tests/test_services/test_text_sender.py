import pytest

from src.services.text_sender import FakeTextSender


def test_fake_text_sender_records_sent_text():
    sender = FakeTextSender()
    sender.send(to_phone="555-0101", subject="Hi", body="Hello there")

    assert len(sender.sent) == 1
    assert sender.sent[0] == {"to": "555-0101", "subject": "Hi", "body": "Hello there"}


def test_fake_text_sender_raises_for_configured_failure():
    sender = FakeTextSender(fail_for={"555-0102"})

    with pytest.raises(RuntimeError):
        sender.send(to_phone="555-0102", subject="Hi", body="body")

    assert sender.sent == []
