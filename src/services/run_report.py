# src/services/run_report.py
"""Turns run results into the per-student "what needs manual follow-up"
lines shown in the end-of-run summary window. Kept separate from the view
so the wording can be unit-tested without building any Tk widgets.

The Live Application Log / daily log file still has the full detail
(including complete error text); this is the at-a-glance list, so each
error is cut to its first line.
"""
from typing import List

from src.services.action_runner import ActionRunSummary, BatchRunSummary, StepResult

_MAX_DETAIL_LENGTH = 200
_STEP_LABELS = {"email": "Email", "text": "Text", "note": "Note"}
_OUTCOME_ICONS = {"failed": "❌", "skipped": "⏭"}


def _short_detail(detail: str) -> str:
    first_line = detail.strip().splitlines()[0] if detail.strip() else ""
    if len(first_line) > _MAX_DETAIL_LENGTH:
        first_line = first_line[:_MAX_DETAIL_LENGTH - 1] + "…"
    return first_line


def describe_step(result: StepResult) -> str:
    """e.g. '❌ Jane Doe (ID 000123) — Email failed: SMTP timeout'."""
    icon = _OUTCOME_ICONS.get(result.outcome, "•")
    if result.step_type == "stopped":  # see ActionRunner._stopped
        return f"{icon} {result.student.full_name} (ID {result.student.salesforce_id}) — Not started (run was stopped)"
    step = _STEP_LABELS.get(result.step_type, result.step_type)
    line = f"{icon} {result.student.full_name} (ID {result.student.salesforce_id}) — {step} {result.outcome}"
    detail = _short_detail(result.detail)
    return f"{line}: {detail}" if detail else line


def issue_lines(summary: ActionRunSummary) -> List[str]:
    """One line per failed or skipped step, in run order. Empty if the run
    was clean."""
    return [describe_step(r) for r in summary.results if r.outcome in _OUTCOME_ICONS]


def batch_issue_lines(batch_summary: BatchRunSummary) -> List[str]:
    """Same as issue_lines, grouped under a header per batch item that had
    any issues. An item whose whole run raised gets its error under its
    header instead."""
    lines: List[str] = []
    for item in batch_summary.items:
        item_lines = issue_lines(item.summary)
        if item.error:
            item_lines = [f"⚠ Action could not run: {_short_detail(item.error)}"] + item_lines
        if item_lines:
            if lines:
                lines.append("")
            lines.append(f"{item.group_name} — {item.action_name}")
            lines.extend(f"    {line}" for line in item_lines)
    return lines
