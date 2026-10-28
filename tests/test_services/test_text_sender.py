import pytest

from src.models.student import Student
from src.services.text_sender import FakeTextSender, UnavailableTextSender


def _student(phone):
    return Student(salesforce_id="S1", first_name="Jane", last_name="Doe", email="j@example.test", phone=phone)


def test_fake_text_sender_records_sent_text():
    sender = FakeTextSender()
    sender.send(_student("555-0101"), body="Hello there", message_name="Hi")

    assert len(sender.sent) == 1
    assert sender.sent[0] == {"to": "555-0101", "subject": "Hi", "body": "Hello there"}


def test_fake_text_sender_raises_for_configured_failure():
    sender = FakeTextSender(fail_for={"555-0102"})

    with pytest.raises(RuntimeError):
        sender.send(_student("555-0102"), body="body", message_name="Hi")

    assert sender.sent == []


def test_unavailable_text_sender_always_fails_with_a_plain_reason():
    with pytest.raises(RuntimeError, match="Texting isn't set up in this app yet - no text was sent."):
        UnavailableTextSender().send(_student("555-0001"), "Welcome", "Hi")
