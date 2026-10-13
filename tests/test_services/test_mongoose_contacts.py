import csv
import json
from pathlib import Path

import pytest

from src.models.student import Student
from src.services.mongoose_contacts import (
    MongooseContact,
    MongooseContactIdRepository,
    build_contact_id_map,
    is_contacts_export,
    load_and_map,
    load_contacts,
    normalize_phone,
)


def make_student(salesforce_id, first_name, last_name, phone="") -> Student:
    return Student(
        salesforce_id=salesforce_id,
        first_name=first_name,
        last_name=last_name,
        email=f"{first_name}.{last_name}@example.com",
        phone=phone,
    )


def write_export_csv(path: Path, rows: list[dict]) -> Path:
    fieldnames = ["contactId", "firstName", "lastName", "mobileNumber", "optedOut", "department"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_normalize_phone_strips_formatting_and_country_code():
    assert normalize_phone("(336) 213-2291") == "3362132291"
    assert normalize_phone("13362132291") == "3362132291"
    assert normalize_phone("3362132291") == "3362132291"


def test_normalize_phone_rejects_unusable_values():
    assert normalize_phone("") == ""
    assert normalize_phone("12345") == ""
    assert normalize_phone(None) == ""


def test_is_contacts_export_detects_signature_column(tmp_path: Path):
    export = write_export_csv(tmp_path / "export.csv", [])
    assert is_contacts_export(export) is True

    not_export = tmp_path / "caseload.csv"
    not_export.write_text("StudentID,Name\n001,Jane Doe\n", encoding="utf-8")
    assert is_contacts_export(not_export) is False


def test_load_contacts_drops_rows_without_a_contact_id(tmp_path: Path):
    export = write_export_csv(tmp_path / "export.csv", [
        {"contactId": "003AAA", "firstName": "Jane", "lastName": "Doe",
         "mobileNumber": "3362132291", "optedOut": "false", "department": "C769"},
        {"contactId": "", "firstName": "No", "lastName": "Id",
         "mobileNumber": "5551234567", "optedOut": "false", "department": "C769"},
    ])

    contacts = load_contacts(export)

    assert len(contacts) == 1
    assert contacts[0] == MongooseContact(
        contact_id="003AAA", first_name="Jane", last_name="Doe",
        mobile="3362132291", opted_out=False,
    )


def test_build_contact_id_map_joins_by_phone_first():
    student = make_student("003STU", "Jane", "Doe", phone="(336) 213-2291")
    contacts = [MongooseContact("003AAA", "Jane", "Doe", "3362132291", opted_out=False)]

    mapping = build_contact_id_map([student], contacts)

    assert mapping == {"003STU": "003AAA"}


def test_build_contact_id_map_falls_back_to_name_when_phone_is_blank():
    student = make_student("003STU", "Jane", "Doe", phone="")
    contacts = [MongooseContact("003AAA", "Jane", "Doe", mobile="", opted_out=False)]

    mapping = build_contact_id_map([student], contacts)

    assert mapping == {"003STU": "003AAA"}


def test_build_contact_id_map_skips_ambiguous_names():
    student = make_student("003STU", "Jane", "Doe", phone="")
    contacts = [
        MongooseContact("003AAA", "Jane", "Doe", mobile="", opted_out=False),
        MongooseContact("003BBB", "Jane", "Doe", mobile="", opted_out=False),
    ]

    mapping = build_contact_id_map([student], contacts)

    assert mapping == {}


def test_build_contact_id_map_excludes_opted_out_contacts_by_default():
    student = make_student("003STU", "Jane", "Doe", phone="3362132291")
    contacts = [MongooseContact("003AAA", "Jane", "Doe", "3362132291", opted_out=True)]

    assert build_contact_id_map([student], contacts) == {}
    assert build_contact_id_map([student], contacts, include_opted_out=True) == {"003STU": "003AAA"}


def test_load_and_map_returns_empty_dict_for_missing_file(tmp_path: Path):
    student = make_student("003STU", "Jane", "Doe", phone="3362132291")

    mapping = load_and_map(tmp_path / "does_not_exist.csv", [student])

    assert mapping == {}


def test_load_and_map_end_to_end(tmp_path: Path):
    export = write_export_csv(tmp_path / "export.csv", [
        {"contactId": "003AAA", "firstName": "Jane", "lastName": "Doe",
         "mobileNumber": "3362132291", "optedOut": "false", "department": "C769"},
    ])
    student = make_student("003STU", "Jane", "Doe", phone="336-213-2291")

    mapping = load_and_map(export, [student])

    assert mapping == {"003STU": "003AAA"}


@pytest.fixture
def temp_contact_id_repo(tmp_path: Path) -> MongooseContactIdRepository:
    return MongooseContactIdRepository(data_file=tmp_path / "mongoose_contact_ids.json")


def test_repository_starts_empty(temp_contact_id_repo: MongooseContactIdRepository):
    assert temp_contact_id_repo.load() == {}


def test_repository_save_and_load_round_trip(temp_contact_id_repo: MongooseContactIdRepository):
    temp_contact_id_repo.save({"003STU": "003AAA"})

    assert temp_contact_id_repo.load() == {"003STU": "003AAA"}


def test_repository_merge_overlays_without_dropping_existing_entries(temp_contact_id_repo: MongooseContactIdRepository):
    temp_contact_id_repo.save({"003STU": "003AAA", "003OLD": "003OLDID"})

    merged = temp_contact_id_repo.merge({"003STU": "003NEW", "003NEXT": "003BBB"})

    assert merged == {"003STU": "003NEW", "003OLD": "003OLDID", "003NEXT": "003BBB"}
    assert temp_contact_id_repo.load() == merged


def test_repository_ensures_parent_dir_and_file_exist(tmp_path: Path):
    nested = tmp_path / "nested" / "dir" / "mongoose_contact_ids.json"

    repo = MongooseContactIdRepository(data_file=nested)

    assert nested.exists()
    assert json.loads(nested.read_text(encoding="utf-8")) == {}
