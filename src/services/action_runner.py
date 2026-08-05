# src/services/action_runner.py
"""Orchestrates running an Action against every student from a
StudentDataProvider.

Per student: email and text are attempted independently of each other (one
failing doesn't block the other). A note is attempted only if at least one
of them succeeded — if none did, the note is skipped, not attempted. No
single student's failure stops the run; every step (success, failure, or
skip) is logged via ActivityLogger and collected into the final summary.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from src.models.action import Action
from src.models.student import Student
from src.services.activity_logger import ActivityLogger
from src.services.email_sender import EmailSender
from src.services.note_writer import NoteWriter
from src.services.student_data_provider import StudentDataProvider
from src.services.template_repository import TemplateRepository
from src.services.text_sender import TextSender


@dataclass
class StepResult:
    student: Student
    step_type: str  # "email" | "text" | "note"
    outcome: str  # "success" | "failed" | "skipped"
    detail: str = ""


@dataclass
class ActionRunSummary:
    results: List[StepResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.outcome == "success")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.outcome == "failed")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.outcome == "skipped")

    @property
    def failed_steps(self) -> List[StepResult]:
        return [r for r in self.results if r.outcome == "failed"]

    @property
    def skipped_steps(self) -> List[StepResult]:
        return [r for r in self.results if r.outcome == "skipped"]


class ActionRunner:
    def __init__(
        self,
        student_provider: StudentDataProvider,
        email_sender: EmailSender,
        text_sender: TextSender,
        note_writer: NoteWriter,
        template_repo: TemplateRepository,
        activity_logger: ActivityLogger,
    ):
        self.student_provider = student_provider
        self.email_sender = email_sender
        self.text_sender = text_sender
        self.note_writer = note_writer
        self.template_repo = template_repo
        self.activity_logger = activity_logger

    def run(self, action: Action, group_name: str) -> ActionRunSummary:
        self.activity_logger.log(f"Starting run — Group: '{group_name}', Action: '{action.name}'")

        template = self.template_repo.get_by_id(action.template_id) if action.template_id else None
        if action.is_email:
            template_label = template.name if template else "MISSING/UNKNOWN"
            self.activity_logger.log(f"Using email template: '{template_label}' (id={action.template_id})")

        students = self.student_provider.get_students()
        has_note_content = bool(action.note_subject or action.note_body)
        summary = ActionRunSummary()

        for student in students:
            email_ok = False
            text_ok = False

            if action.is_email:
                result = self._attempt_email(student, action, template)
                summary.results.append(result)
                email_ok = result.outcome == "success"

            if action.is_text:
                result = self._attempt_text(student, action)
                summary.results.append(result)
                text_ok = result.outcome == "success"

            if has_note_content:
                if email_ok or text_ok:
                    summary.results.append(self._attempt_note(student, action))
                else:
                    detail = "No successful communication for this student"
                    self.activity_logger.log(f"[SKIPPED] Note for {student.full_name} — {detail}")
                    summary.results.append(
                        StepResult(student=student, step_type="note", outcome="skipped", detail=detail)
                    )

        self.activity_logger.log(
            f"Run complete — {summary.succeeded} succeeded, {summary.failed} failed, {summary.skipped} skipped"
        )
        return summary

    def _attempt_email(self, student: Student, action: Action, template) -> StepResult:
        body = template.body if template else ""
        try:
            self.email_sender.send(
                to_email=student.email, subject=action.email_subject, body=body, signature=action.email_signature
            )
            self.activity_logger.log(f"[EMAIL] Sent to {student.full_name} <{student.email}>")
            return StepResult(student=student, step_type="email", outcome="success")
        except Exception as exc:
            self.activity_logger.log(f"[EMAIL FAILED] {student.full_name} <{student.email}>: {exc}")
            return StepResult(student=student, step_type="email", outcome="failed", detail=str(exc))

    def _attempt_text(self, student: Student, action: Action) -> StepResult:
        try:
            self.text_sender.send(to_phone=student.phone, subject=action.text_subject, body=action.text_body)
            self.activity_logger.log(f"[TEXT] Sent to {student.full_name} <{student.phone}>")
            return StepResult(student=student, step_type="text", outcome="success")
        except Exception as exc:
            self.activity_logger.log(f"[TEXT FAILED] {student.full_name} <{student.phone}>: {exc}")
            return StepResult(student=student, step_type="text", outcome="failed", detail=str(exc))

    def _attempt_note(self, student: Student, action: Action) -> StepResult:
        try:
            self.note_writer.write_note(
                salesforce_id=student.salesforce_id, subject=action.note_subject, body=action.note_body
            )
            self.activity_logger.log(f"[NOTE] Written for {student.full_name}")
            return StepResult(student=student, step_type="note", outcome="success")
        except Exception as exc:
            self.activity_logger.log(f"[NOTE FAILED] {student.full_name}: {exc}")
            return StepResult(student=student, step_type="note", outcome="failed", detail=str(exc))
