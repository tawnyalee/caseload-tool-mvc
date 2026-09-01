# src/services/action_runner.py
"""Orchestrates running an Action against every student from a
StudentDataProvider.

Per student: email and text are attempted independently of each other (one
failing doesn't block the other). A note step is attempted only if at least
one of them succeeded — if none did, it's skipped, not attempted. The note
step covers both writing an interaction note (if note_subject/note_body are
set) and updating the student's roster-visible follow-up-note field (if
follow_up_note is set) as a single unit. No single student's failure stops
the run; every step (success, failure, or skip) is logged via ActivityLogger
and collected into the final summary.

run_welcome_emails() runs every group's designated welcome action and
aggregates them into one summary. run_batch() is the general form of that
same pattern — any professor-selected list of (action, group_name) pairs,
run in order, one action's failure isolated from the rest exactly like a
single student's failure is isolated within run(). send_ad_hoc_email()
sends a one-off, non-template email to every student (e.g. a class
cancellation notice).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.models.action import Action
from src.models.group import Group
from src.models.student import Student
from src.services.activity_logger import ActivityLogger
from src.services.email_sender import EmailSender
from src.services.filter_engine import matches_student
from src.services.merge_fields import render_merge_fields
from src.services.note_records import NoteInsertRecord, resolve_course_code, validate_note_record
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


@dataclass
class BatchItemResult:
    action_name: str
    group_name: str
    summary: ActionRunSummary
    error: Optional[str] = None  # set only if the action's run() itself raised, not per-student failures


@dataclass
class BatchRunSummary:
    """Itemized per action, not just one blended total — batch members
    typically target different groups/subsets, so a combined-only number
    would hide which specific action needs attention."""
    items: List[BatchItemResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(item.summary.succeeded for item in self.items)

    @property
    def failed(self) -> int:
        return sum(item.summary.failed for item in self.items)

    @property
    def skipped(self) -> int:
        return sum(item.summary.skipped for item in self.items)


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

    def get_matching_students(self, action: Action) -> List[Student]:
        """Students matching action.filters, before running anything - used
        by the pre-send review dialog to show who would be contacted."""
        all_students = self.student_provider.get_students()
        return [s for s in all_students if matches_student(s, action.filters)]

    def run(
        self,
        action: Action,
        group_name: str,
        included_student_ids: Optional[Set[str]] = None,
        email_subject_override: Optional[str] = None,
        email_body_override: Optional[str] = None,
    ) -> ActionRunSummary:
        """`included_student_ids`, when given, further restricts the
        filter-matched students to just those IDs - how the pre-send review
        dialog's checkbox deselection actually takes effect. None (the
        default) means every filter-matched student runs, same as before
        that dialog existed. `email_subject_override`/`email_body_override`
        are that same dialog's last-minute content edits - see
        _attempt_email."""
        self.activity_logger.log(f"Starting run — Group: '{group_name}', Action: '{action.name}'")

        template = self.template_repo.get_by_id(action.template_id) if action.template_id else None
        if action.is_email:
            template_label = template.name if template else "MISSING/UNKNOWN"
            self.activity_logger.log(f"Using email template: '{template_label}' (id={action.template_id})")

        all_students = self.student_provider.get_students()
        students = [s for s in all_students if matches_student(s, action.filters)]
        matched_count = len(students)
        if included_student_ids is not None:
            students = [s for s in students if s.salesforce_id in included_student_ids]
        if action.filters:
            self.activity_logger.log(f"Filters matched {matched_count} of {len(all_students)} students")
        self.activity_logger.log(f"'{action.name}' is currently running for {len(students)} students")
        has_note_content = bool(action.note_subject or action.note_body or action.follow_up_note)
        summary = ActionRunSummary()

        for student in students:
            self.activity_logger.log(f"[PROCESSING] {student.full_name} (ID: {student.salesforce_id})")
            email_ok = False
            text_ok = False

            if action.is_email:
                result = self._attempt_email(
                    student, action, template,
                    subject_override=email_subject_override, body_override=email_body_override,
                )
                summary.results.append(result)
                email_ok = result.outcome == "success"

            if action.is_text:
                result = self._attempt_text(student, action)
                summary.results.append(result)
                text_ok = result.outcome == "success"

            if has_note_content:
                if email_ok or text_ok:
                    summary.results.append(
                        self._attempt_note(
                            student, action.note_subject, action.note_body, action.follow_up_note,
                            group_name=group_name,
                        )
                    )
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

    def run_welcome_emails(
        self,
        groups: List[Group],
        actions_by_id: Dict[str, Action],
        included_ids_by_group_id: Optional[Dict[str, Set[str]]] = None,
    ) -> ActionRunSummary:
        """Runs every group's designated welcome action (Group.welcome_action_id)
        and aggregates all of them into a single combined summary.
        `included_ids_by_group_id`, when given, restricts each group's run to
        just those student IDs - how the multi-item pre-send review dialog's
        per-group deselection takes effect (see run())."""
        self.activity_logger.log("Starting welcome-email run across all groups")
        combined = ActionRunSummary()

        for group in groups:
            if not group.welcome_action_id:
                continue

            action = actions_by_id.get(group.welcome_action_id)
            if not action:
                self.activity_logger.log(
                    f"[SKIPPED] Group '{group.name}' has a welcome_action_id with no matching action"
                )
                continue

            included_ids = included_ids_by_group_id.get(group.id) if included_ids_by_group_id else None
            group_summary = self.run(action, group_name=group.name, included_student_ids=included_ids)
            combined.results.extend(group_summary.results)

        self.activity_logger.log(
            f"Welcome-email run complete — {combined.succeeded} succeeded, "
            f"{combined.failed} failed, {combined.skipped} skipped"
        )
        return combined

    def run_batch(
        self,
        items: List[Tuple[Action, str]],
        included_ids_by_index: Optional[Dict[int, Set[str]]] = None,
    ) -> BatchRunSummary:
        """Runs each (action, group_name) pair in `items`, in the order
        given, one action's failure isolated from the rest — same
        philosophy as run()'s per-student isolation, just one level up.
        Per-student failures within a single action are already caught
        inside run() and never raise; this additionally guards against an
        action's run() itself raising unexpectedly, so one broken action
        can't stop the whole batch. `included_ids_by_index`, when given,
        restricts item i's run to just those student IDs - keyed by
        position rather than action.id since the same action could appear
        more than once in a batch against different groups."""
        self.activity_logger.log(f"Starting batch run — {len(items)} action(s)")
        batch_summary = BatchRunSummary()

        for i, (action, group_name) in enumerate(items):
            included_ids = included_ids_by_index.get(i) if included_ids_by_index else None
            try:
                summary = self.run(action, group_name=group_name, included_student_ids=included_ids)
                batch_summary.items.append(
                    BatchItemResult(action_name=action.name, group_name=group_name, summary=summary)
                )
            except Exception as exc:
                self.activity_logger.log(
                    f"[BATCH ITEM FAILED] Action '{action.name}' (Group: '{group_name}'): {exc}"
                )
                batch_summary.items.append(
                    BatchItemResult(
                        action_name=action.name, group_name=group_name,
                        summary=ActionRunSummary(), error=str(exc),
                    )
                )

        self.activity_logger.log(
            f"Batch run complete — {batch_summary.succeeded} succeeded, "
            f"{batch_summary.failed} failed, {batch_summary.skipped} skipped "
            f"across {len(items)} action(s)"
        )
        return batch_summary

    def send_ad_hoc_email(
        self,
        subject: str,
        body: str,
        signature: str = "",
        note_subject: str = "",
        note_body: str = "",
        follow_up_note: str = "",
        included_student_ids: Optional[Set[str]] = None,
    ) -> ActionRunSummary:
        """Sends a one-off email (not tied to any saved Action or template) to
        every student from the provider — e.g. a class cancellation notice.
        Note handling is identical to a regular Action's note step: only
        attempted for a student the email succeeded for, skipped (not
        attempted) otherwise, and only if note_subject/note_body/
        follow_up_note actually has content. `included_student_ids`, when
        given, restricts the send to just those IDs - see run()."""
        self.activity_logger.log(f"Starting ad-hoc email send — Subject: '{subject}'")
        students = self.student_provider.get_students()
        if included_student_ids is not None:
            students = [s for s in students if s.salesforce_id in included_student_ids]
        self.activity_logger.log(f"Ad-hoc email is currently running for {len(students)} students")
        has_note_content = bool(note_subject or note_body or follow_up_note)
        summary = ActionRunSummary()

        for student in students:
            self.activity_logger.log(f"[PROCESSING] {student.full_name} (ID: {student.salesforce_id})")
            result = self._send_email(student, subject, body, signature)
            summary.results.append(result)

            if has_note_content:
                if result.outcome == "success":
                    summary.results.append(
                        self._attempt_note(student, note_subject, note_body, follow_up_note)
                    )
                else:
                    detail = "No successful communication for this student"
                    self.activity_logger.log(f"[SKIPPED] Note for {student.full_name} — {detail}")
                    summary.results.append(
                        StepResult(student=student, step_type="note", outcome="skipped", detail=detail)
                    )

        self.activity_logger.log(
            f"Ad-hoc send complete — {summary.succeeded} succeeded, "
            f"{summary.failed} failed, {summary.skipped} skipped"
        )
        return summary

    def _attempt_email(
        self,
        student: Student,
        action: Action,
        template,
        subject_override: Optional[str] = None,
        body_override: Optional[str] = None,
    ) -> StepResult:
        """`subject_override`/`body_override`, when given, replace
        action.email_subject / the template's body for this call only - how
        the pre-send review dialog's last-minute edits take effect, without
        touching the saved Action or template."""
        subject = subject_override if subject_override is not None else action.email_subject
        body = body_override if body_override is not None else (template.body if template else "")
        return self._send_email(student, subject, body, action.email_signature)

    def _send_email(self, student: Student, subject: str, body: str, signature: str) -> StepResult:
        try:
            rendered_subject = render_merge_fields(subject, student)
            rendered_body = render_merge_fields(body, student)
            self.email_sender.send(
                to_email=student.email, subject=rendered_subject, body=rendered_body, signature=signature
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

    def _attempt_note(
        self,
        student: Student,
        note_subject: str,
        note_body: str,
        follow_up_note: str,
        group_name: str = "",
    ) -> StepResult:
        record = NoteInsertRecord(
            salesforce_id=student.salesforce_id,
            course_code=resolve_course_code(student, group_name),
            note_subject=note_subject,
            note_body=note_body,
            follow_up_note=follow_up_note,
        )
        problems = validate_note_record(record)
        if problems:
            self.activity_logger.log(f"[NOTE RECORD ISSUE] {student.full_name}: {'; '.join(problems)} — {record}")
        else:
            self.activity_logger.log(f"[NOTE RECORD] {student.full_name}: {record}")

        try:
            if note_subject or note_body:
                self.note_writer.write_note(
                    salesforce_id=student.salesforce_id, subject=note_subject, body=note_body
                )
            if follow_up_note:
                self.note_writer.update_follow_up_note(
                    salesforce_id=student.salesforce_id, text=follow_up_note
                )
            self.activity_logger.log(f"[NOTE] Written for {student.full_name}")
            return StepResult(student=student, step_type="note", outcome="success")
        except Exception as exc:
            self.activity_logger.log(f"[NOTE FAILED] {student.full_name}: {exc}")
            return StepResult(student=student, step_type="note", outcome="failed", detail=str(exc))
