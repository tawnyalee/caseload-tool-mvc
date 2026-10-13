from src.models.student import Student
from src.services.action_runner import ActionRunSummary, BatchItemResult, BatchRunSummary, StepResult
from src.services.run_report import batch_issue_lines, describe_step, issue_lines

JANE = Student(salesforce_id="000123", first_name="Jane", last_name="Doe", email="jane@example.test")
JOHN = Student(salesforce_id="000456", first_name="John", last_name="Roe", email="john@example.test")


def test_describe_step_names_student_step_and_reason():
    result = StepResult(student=JANE, step_type="email", outcome="failed", detail="SMTP timeout")
    assert describe_step(result) == "❌ Jane Doe (ID 000123) — Email failed: SMTP timeout"


def test_describe_step_keeps_only_the_first_line_of_a_long_error():
    detail = "Note write failed for 000123\nCall log:\n  - waiting for locator..."
    result = StepResult(student=JANE, step_type="note", outcome="failed", detail=detail)
    assert describe_step(result) == "❌ Jane Doe (ID 000123) — Note failed: Note write failed for 000123"


def test_describe_step_truncates_a_very_long_first_line():
    result = StepResult(student=JANE, step_type="email", outcome="failed", detail="x" * 500)
    assert describe_step(result).endswith("x…")
    assert len(describe_step(result)) < 300


def test_describe_step_with_no_detail_has_no_trailing_colon():
    result = StepResult(student=JANE, step_type="text", outcome="failed")
    assert describe_step(result) == "❌ Jane Doe (ID 000123) — Text failed"


def test_issue_lines_lists_failures_and_skips_but_not_successes_in_run_order():
    summary = ActionRunSummary(results=[
        StepResult(student=JANE, step_type="email", outcome="failed", detail="boom"),
        StepResult(student=JANE, step_type="note", outcome="skipped", detail="Email was not sent successfully"),
        StepResult(student=JOHN, step_type="email", outcome="success"),
    ])
    assert issue_lines(summary) == [
        "❌ Jane Doe (ID 000123) — Email failed: boom",
        "⏭ Jane Doe (ID 000123) — Note skipped: Email was not sent successfully",
    ]


def test_issue_lines_is_empty_for_a_clean_run():
    summary = ActionRunSummary(results=[StepResult(student=JANE, step_type="email", outcome="success")])
    assert issue_lines(summary) == []


def test_batch_issue_lines_groups_by_item_and_omits_clean_items():
    batch = BatchRunSummary(items=[
        BatchItemResult(action_name="Clean", group_name="D424", summary=ActionRunSummary(results=[
            StepResult(student=JOHN, step_type="email", outcome="success"),
        ])),
        BatchItemResult(action_name="Welcome", group_name="D425", summary=ActionRunSummary(results=[
            StepResult(student=JANE, step_type="email", outcome="failed", detail="boom"),
        ])),
        BatchItemResult(action_name="Broken", group_name="D426", summary=ActionRunSummary(), error="Template missing"),
    ])
    assert batch_issue_lines(batch) == [
        "D425 — Welcome",
        "    ❌ Jane Doe (ID 000123) — Email failed: boom",
        "",
        "D426 — Broken",
        "    ⚠ Action could not run: Template missing",
    ]
