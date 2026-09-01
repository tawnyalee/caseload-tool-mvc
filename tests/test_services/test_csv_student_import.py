from src.services.csv_student_import import csv_row_to_student_fields


def test_maps_known_columns_to_student_field_names():
    row = {"StudentID": "SF1", "StudentEmail": "jane@example.test", "CourseCode": "D424"}
    fields = csv_row_to_student_fields(row)

    assert fields["salesforce_id"] == "SF1"
    assert fields["email"] == "jane@example.test"
    assert fields["course_code"] == "D424"


def test_ignores_unknown_columns():
    row = {"StudentID": "SF1", "SomeColumnNotInTheMap": "whatever"}
    fields = csv_row_to_student_fields(row)

    assert "SomeColumnNotInTheMap" not in fields
    assert "some_column_not_in_the_map" not in fields


def test_prefers_preferred_name_when_present():
    row = {"Name": "Robert Smith", "stuprename": "Bob"}
    fields = csv_row_to_student_fields(row)

    assert fields["first_name"] == "Bob"
    assert fields["last_name"] == "Smith"


def test_falls_back_to_name_when_no_preferred_name():
    row = {"Name": "Robert Smith", "stuprename": ""}
    fields = csv_row_to_student_fields(row)

    assert fields["first_name"] == "Robert"
    assert fields["last_name"] == "Smith"


def test_texting_preference_opted_in_sets_has_signed_up_for_text():
    assert csv_row_to_student_fields({"TextingPreference": "Opted In"})["has_signed_up_for_text"] is True
    assert csv_row_to_student_fields({"TextingPreference": "Opted Out"})["has_signed_up_for_text"] is False
    assert csv_row_to_student_fields({})["has_signed_up_for_text"] is False
