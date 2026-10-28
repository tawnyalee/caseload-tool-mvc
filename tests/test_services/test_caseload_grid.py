import json

from src.models.student import Student
from src.services.caseload_grid import GridCapture, apply_contact_ids, rows_from_grid_response


def _envelope(rows, state="SUCCESS"):
    return json.dumps({"actions": [{"state": state, "returnValue": rows}]})


def _row(student_id, course="D424", contact_id="003AAA", total=3):
    return {"StudentID": student_id, "CourseCode": course, "contactID": contact_id, "CaseloadTotalRows": total}


def _student(student_id, first="Jane", last="Doe"):
    return Student(salesforce_id=student_id, first_name=first, last_name=last, email=f"{student_id}@example.test")


def test_reads_rows_from_a_successful_aura_response():
    rows = rows_from_grid_response(_envelope([_row("S1"), _row("S2")]))
    assert [r["StudentID"] for r in rows] == ["S1", "S2"]


def test_unreadable_or_failed_responses_give_no_rows():
    assert rows_from_grid_response("not json") == []
    assert rows_from_grid_response(_envelope([_row("S1")], state="ERROR")) == []
    assert rows_from_grid_response("[]") == []


def test_chunks_accumulate_and_a_repeated_chunk_isnt_counted_twice():
    grid = GridCapture()
    grid.add_rows([_row("S1"), _row("S2")])
    grid.add_rows([_row("S1"), _row("S2")])  # same chunk again
    assert len(grid.rows_by_key) == 2
    assert not grid.is_complete  # page says 3 rows in total

    grid.add_rows([_row("S3")])
    assert grid.is_complete


def test_same_student_in_two_courses_is_two_rows_with_one_contact_id():
    grid = GridCapture()
    grid.add_rows([_row("S1", course="D424", total=2), _row("S1", course="C769", total=2)])
    assert grid.is_complete
    assert grid.contact_ids_by_student_id() == {"S1": "003AAA"}


def test_only_real_contact_ids_are_used():
    grid = GridCapture()
    grid.add_rows([_row("S1", contact_id=""), _row("S2", contact_id="a0B123"), _row("S3", contact_id="003CCC")])
    assert grid.contact_ids_by_student_id() == {"S3": "003CCC"}


def test_apply_sets_each_students_texting_id_and_names_who_is_missing():
    grid = GridCapture()
    grid.add_rows([_row("S1", contact_id="003AAA", total=2), _row("S2", contact_id="", total=2)])
    jane, john = _student("S1"), _student("S2", first="John", last="Roe")

    report = apply_contact_ids([jane, john], grid)

    assert jane.texting_contact_id == "003AAA"
    assert john.texting_contact_id == ""
    assert report.with_contact_id == 1 and report.students == 2
    assert not report.grid_incomplete
    assert report.log_lines() == [
        "Texting IDs found for 1 of 2 students",
        "No texting ID (texts to them will be skipped): John Roe",
    ]


def test_report_warns_when_the_page_sent_fewer_rows_than_its_own_total():
    grid = GridCapture()
    grid.add_rows([_row("S1", total=269)])

    report = apply_contact_ids([_student("S1")], grid)

    assert report.grid_incomplete
    assert any("[TEXTING IDS INCOMPLETE]" in line and "1 of 269 rows" in line for line in report.log_lines())


def test_report_warns_when_no_grid_data_arrived_at_all():
    report = apply_contact_ids([_student("S1")], GridCapture())
    assert report.grid_incomplete
    assert any("0 of an unknown number of rows" in line for line in report.log_lines())


def test_a_broken_response_never_breaks_the_listener():
    class Exploding:
        url = "https://x/aura?getCaseLoadMainGridData=1"

        def text(self):
            raise RuntimeError("body gone")

    GridCapture().on_response(Exploding())  # no exception
