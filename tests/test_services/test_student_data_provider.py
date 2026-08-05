from src.models.student import Student
from src.services.student_data_provider import FakeStudentDataProvider


def test_fake_provider_loads_fixture_students(tmp_path):
    fixture = tmp_path / "fake_students.json"
    fixture.write_text(
        '[{"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", '
        '"email": "jane@example.test", "phone": "555-1111", "has_signed_up_for_text": true}]',
        encoding="utf-8",
    )

    provider = FakeStudentDataProvider(file_path=str(fixture))
    students = provider.get_students()

    assert len(students) == 1
    assert isinstance(students[0], Student)
    assert students[0].full_name == "Jane Doe"
    assert students[0].email == "jane@example.test"
    assert students[0].has_signed_up_for_text is True


def test_fake_provider_creates_empty_fixture_if_missing(tmp_path):
    fixture = tmp_path / "does_not_exist_yet.json"
    provider = FakeStudentDataProvider(file_path=str(fixture))

    assert fixture.exists()
    assert provider.get_students() == []


def test_fake_provider_returns_empty_list_on_malformed_json(tmp_path):
    fixture = tmp_path / "broken.json"
    fixture.write_text("{not valid json", encoding="utf-8")

    provider = FakeStudentDataProvider(file_path=str(fixture))
    assert provider.get_students() == []


def test_shipped_fake_fixture_loads_cleanly():
    """Sanity-checks the actual data/fake_students.json fixture committed to the repo."""
    provider = FakeStudentDataProvider()
    students = provider.get_students()

    assert len(students) >= 1
    assert all(isinstance(s, Student) for s in students)
    assert all(s.email for s in students)
