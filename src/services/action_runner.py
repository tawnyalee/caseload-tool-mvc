# src/services/action_runner.py
"""Orchestrates running an Action against every student from a
StudentDataProvider.

Per student: email and text are attempted independently of each other (one
failing doesn't block the other). A note step is attempted only if the email
succeeded — if it didn't, the note is skipped, not attempted. Texts never
trigger a note: Mongoose writes its own note for every text at the end of
the day, so a text-only action has no note step at all. The note
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
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

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
from src.services.task_utils import is_latest_task_passed
from src.services.text_sender import TextSender, TextSkipped


class RunControl:
    """Lets the app follow a run from another thread and stop it. The runner
    calls report() before each student and checks stop_requested between
    students - a stop finishes the current student, then marks everyone
    left as not started (so the results window shows exactly who wasn't
    done). Thread-safe: request_stop() is called from the UI thread while
    the run happens on the background worker."""

    def __init__(self, on_progress: Optional[Callable[[int, int, str], None]] = None):
        self.on_progress = on_progress
        self.context = ""  # e.g. "D424 — Welcome Action (2 of 3)", set by batch-style runs
        self._stop = threading.Event()

    def request_stop(self) -> None:
        self._stop.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    def report(self, position: int, total: int, student_name: str) -> None:
        if self.on_progress:
            prefix = f"{self.context}: " if self.context else ""
            self.on_progress(position, total, f"{prefix}{student_name}")


STOPPED_DETAIL = "Run was stopped before this student"
# Characters in one standard text message; longer ones may arrive in parts.
SINGLE_TEXT_LENGTH = 160

def in_group_course(student: Student, course_code: str) -> bool:
    """An action in a COURSE group only reaches students in that course
    (developer's call, 2026-10-27). `course_code` is the group's configured
    course (Group.scoped_course_code), or "" for a group that isn't a course
    - those reach every course, like General. Case and surrounding spaces
    are ignored."""
    if not course_code:
        return True
    return student.course_code.strip().upper() == course_code.strip().upper()


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
        group_lookup: Optional[Callable[[str], Optional[Group]]] = None,
    ):
        """`group_lookup(group_id)` finds an action's group (for its course
        settings); without it every action reaches every course."""
        self.group_lookup = group_lookup
        self.student_provider = student_provider
        self.email_sender = email_sender
        self.text_sender = text_sender
        self.note_writer = note_writer
        self.template_repo = template_repo
        self.activity_logger = activity_logger

    def course_code_for(self, action: Action) -> str:
        """The course an action is limited to: its own group's (looked up by
        ID, never by name) configured course code, or "" if the group isn't
        a course or no longer exists (such actions show under General)."""
        group = self.group_lookup(action.group_id) if self.group_lookup and action.group_id else None
        return group.scoped_course_code if group else ""

    def get_matching_students(self, action: Action) -> List[Student]:
        """Students an action would contact, before running anything - used
        by the pre-send review dialog. Same rule as run(): limited to the
        action's course (see in_group_course), then action.filters."""
        course_code = self.course_code_for(action)
        all_students = self.student_provider.get_students()
        return [
            s for s in all_students
            if in_group_course(s, course_code) and matches_student(s, action.filters)
        ]

    def run(
        self,
        action: Action,
        group_name: str,
        included_student_ids: Optional[Set[str]] = None,
        email_subject_override: Optional[str] = None,
        email_body_override: Optional[str] = None,
        control: Optional[RunControl] = None,
    ) -> ActionRunSummary:
        """`control`, when given, receives progress and can stop the run
        between students (see RunControl). `included_student_ids`, when given, further restricts the
        filter-matched students to just those IDs - how the pre-send review
        dialog's checkbox deselection actually takes effect. None (the
        default) means every filter-matched student runs, same as before
        that dialog existed. `email_subject_override`/`email_body_override`
        are that same dialog's last-minute content edits - see
        _attempt_email."""
        self.activity_logger.log(f"Starting run — Group: '{group_name}', Action: '{action.name}'")
        self.activity_logger.log(
            f"Action settings (id={action.id}): email={'on' if action.is_email else 'off'}, "
            f"text={'on' if action.is_text else 'off'}, "
            f"task emails={'on' if getattr(action, 'use_task_emails', False) else 'off'}, "
            f"filters={action.filters or 'none'}"
        )

        template = self.template_repo.get_by_id(action.template_id) if action.template_id else None
        if action.is_email:
            template_label = template.name if template else "MISSING/UNKNOWN"
            self.activity_logger.log(f"Using email template: '{template_label}' (id={action.template_id})")

        course_code = self.course_code_for(action)
        all_students = self.student_provider.get_students()
        in_course = [s for s in all_students if in_group_course(s, course_code)]
        if course_code:
            self.activity_logger.log(f"Limited to course '{course_code}': {len(in_course)} of {len(all_students)} students")
        students = [s for s in in_course if matches_student(s, action.filters)]
        matched_count = len(students)
        if included_student_ids is not None:
            students = [s for s in students if s.salesforce_id in included_student_ids]
        if action.filters:
            self.activity_logger.log(f"Filters matched {matched_count} of {len(all_students)} students")
        self.activity_logger.log(f"'{action.name}' is currently running for {len(students)} students")
        if action.is_email and students:
            self.email_sender.ensure_ready()  # e.g. Outlook not open: stop now, not once per student
        texting = action.is_text and bool(students)
        if texting:
            if len(action.text_body) > SINGLE_TEXT_LENGTH:
                self.activity_logger.log(
                    f"[TEXT LENGTH] The text is {len(action.text_body)} characters before personalizing "
                    f"(one text holds about {SINGLE_TEXT_LENGTH}); it may arrive in parts"
                )
            self.text_sender.ensure_ready()  # e.g. log in to Mongoose once, before the first student
        has_note_content = bool(action.note_subject or action.note_body or action.follow_up_note)
        # Only email gets a note: Mongoose writes its own note for every text
        # at the end of the day, so a text-only action never writes one here.
        writes_note = has_note_content and action.is_email
        if has_note_content and not action.is_email:
            self.activity_logger.log(
                "Note step not run — this action doesn't send email, and texts are noted automatically by Mongoose"
            )
        summary = ActionRunSummary()
        try:
            for position, student in enumerate(students, start=1):
                if self._stopped(control, students[position - 1:], summary):
                    break
                if control:
                    control.report(position, len(students), student.full_name)
                self.activity_logger.log(f"[PROCESSING] {student.full_name} (ID: {student.salesforce_id})")
                email_ok = False

                if action.is_email:
                    result = self._attempt_email(
                        student, action, template,
                        subject_override=email_subject_override, body_override=email_body_override,
                    )
                    summary.results.append(result)
                    email_ok = result.outcome == "success"

                if action.is_text:
                    summary.results.append(self._attempt_text(student, action))

                if writes_note:
                    if email_ok:
                        summary.results.append(
                            self._attempt_note(
                                student, action.note_subject, action.note_body, action.follow_up_note,
                                course_code=course_code,
                            )
                        )
                    else:
                        detail = "Email was not sent successfully"
                        self.activity_logger.log(f"[SKIPPED] Note for {student.full_name} — {detail}")
                        summary.results.append(
                            StepResult(student=student, step_type="note", outcome="skipped", detail=detail)
                        )
        finally:
            if texting:
                self.text_sender.finish()

        self.activity_logger.log(
            f"Run complete — {summary.succeeded} succeeded, {summary.failed} failed, {summary.skipped} skipped"
        )
        return summary

    def run_welcome_emails(
        self,
        groups: List[Group],
        actions_by_id: Dict[str, Action],
        included_ids_by_group_id: Optional[Dict[str, Set[str]]] = None,
        control: Optional[RunControl] = None,
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
            if control:
                control.context = f"{group.name} — {action.name}"
            group_summary = self.run(action, group_name=group.name, included_student_ids=included_ids, control=control)
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
        control: Optional[RunControl] = None,
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
            if control:
                control.context = f"{group_name} — {action.name} ({i + 1} of {len(items)})"
            try:
                summary = self.run(action, group_name=group_name, included_student_ids=included_ids, control=control)
                batch_summary.items.append(
                    BatchItemResult(action_name=action.name, group_name=group_name, summary=summary)
                )
            except Exception as exc:
                self.activity_logger.log_failure(
                    f"[BATCH ITEM FAILED] Action '{action.name}' (Group: '{group_name}'): {exc}", exc
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
        control: Optional[RunControl] = None,
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
        if students:
            self.email_sender.ensure_ready()
        has_note_content = bool(note_subject or note_body or follow_up_note)
        summary = ActionRunSummary()

        for position, student in enumerate(students, start=1):
            if self._stopped(control, students[position - 1:], summary):
                break
            if control:
                control.report(position, len(students), student.full_name)
            self.activity_logger.log(f"[PROCESSING] {student.full_name} (ID: {student.salesforce_id})")
            result = self._send_email(student, subject, body, signature)
            summary.results.append(result)

            if has_note_content:
                if result.outcome == "success":
                    summary.results.append(
                        self._attempt_note(student, note_subject, note_body, follow_up_note)
                    )
                else:
                    detail = "Email was not sent successfully"
                    self.activity_logger.log(f"[SKIPPED] Note for {student.full_name} — {detail}")
                    summary.results.append(
                        StepResult(student=student, step_type="note", outcome="skipped", detail=detail)
                    )

        self.activity_logger.log(
            f"Ad-hoc send complete — {summary.succeeded} succeeded, "
            f"{summary.failed} failed, {summary.skipped} skipped"
        )
        return summary

    def _stopped(self, control: Optional[RunControl], remaining: List[Student], summary: ActionRunSummary) -> bool:
        """If a stop was requested, marks every remaining student as not
        started (one skipped result each, so the results window lists them)
        and returns True."""
        if not control or not control.stop_requested:
            return False
        self.activity_logger.log(f"[STOPPED] Run stopped by the user - {len(remaining)} student(s) not started")
        for student in remaining:
            summary.results.append(
                StepResult(student=student, step_type="stopped", outcome="skipped", detail=STOPPED_DETAIL)
            )
        return True

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
        if action.use_task_emails:
            return self._attempt_task_email(student, action)
        subject = subject_override if subject_override is not None else action.email_subject
        body = body_override if body_override is not None else (template.body if template else "")
        return self._send_email(student, subject, body, action.email_signature)

    def _attempt_task_email(self, student: Student, action: Action) -> StepResult:
        """The email set up in Settings for the task this student just passed,
        in this action's course. Skipped (with the reason, so it shows in the
        results) when there's nothing safe to send."""
        group = self.group_lookup(action.group_id) if self.group_lookup and action.group_id else None
        task = student.latest_task_number

        def skip(detail: str) -> StepResult:
            self.activity_logger.log(f"[SKIPPED] Email for {student.full_name} — {detail}")
            return StepResult(student=student, step_type="email", outcome="skipped", detail=detail)

        if group is None or not group.is_course:
            return skip("This Action uses course task emails, but its group isn't a course (see Settings)")
        if task is None:
            return skip("No task submitted yet")
        if not is_latest_task_passed(student):
            # Guard even if a filter was forgotten: never send "on to the next
            # task" to someone whose latest task came back for revisions.
            status = student.latest_task_status.strip() or "unknown"
            return skip(f"Latest task (Task {task}) hasn't passed (status: {status})")
        email = group.task_email_for(task)
        if email is None:
            return skip(f"No task email set up for {group.course_code} Task {task} (see Settings)")
        template = self.template_repo.get_by_id(email["template_id"])
        if template is None:
            self.activity_logger.log(f"[EMAIL FAILED] {student.full_name}: task email template is missing")
            return StepResult(
                student=student, step_type="email", outcome="failed",
                detail=f"The template chosen for {group.course_code} Task {task} no longer exists (see Settings)",
            )
        return self._send_email(student, email.get("subject", ""), template.body, action.email_signature)

    def _send_email(self, student: Student, subject: str, body: str, signature: str) -> StepResult:
        try:
            rendered_subject = render_merge_fields(subject, student)
            rendered_body = render_merge_fields(body, student)
            self.email_sender.send(
                to_email=student.email, subject=rendered_subject, body=rendered_body, signature=signature
            )
            self.activity_logger.log(
                f"[EMAIL] {self.email_sender.describe_sent(f'{student.full_name} <{student.email}>')}"
            )
            return StepResult(student=student, step_type="email", outcome="success")
        except Exception as exc:
            self.activity_logger.log_failure(f"[EMAIL FAILED] {student.full_name} <{student.email}>: {exc}", exc)
            return StepResult(student=student, step_type="email", outcome="failed", detail=str(exc))

    def _attempt_text(self, student: Student, action: Action) -> StepResult:
        # The action's text subject is the platform's label for the text
        # (Mongoose's "Message Name"); merge fields work in both.
        body = render_merge_fields(action.text_body, student)
        message_name = render_merge_fields(action.text_subject, student) or action.name
        try:
            what = self.text_sender.send(student, body, message_name)
            self.activity_logger.log(f"[TEXT] {what} - {student.full_name}")
            return StepResult(student=student, step_type="text", outcome="success")
        except TextSkipped as exc:
            self.activity_logger.log(f"[TEXT SKIPPED] {student.full_name}: {exc}")
            return StepResult(student=student, step_type="text", outcome="skipped", detail=str(exc))
        except Exception as exc:
            self.activity_logger.log_failure(f"[TEXT FAILED] {student.full_name}: {exc}", exc)
            return StepResult(student=student, step_type="text", outcome="failed", detail=str(exc))

    def _attempt_note(
        self,
        student: Student,
        note_subject: str,
        note_body: str,
        follow_up_note: str,
        course_code: str = "",
    ) -> StepResult:
        # Merge fields work in notes too (2026-10-27), e.g. a follow-up note of
        # "{{last_passed_task}} tips sent" that a DoesNotContain filter checks.
        note_subject = render_merge_fields(note_subject, student)
        note_body = render_merge_fields(note_body, student)
        follow_up_note = render_merge_fields(follow_up_note, student)
        record = NoteInsertRecord(
            salesforce_id=student.salesforce_id,
            # The action's course group's code; otherwise the student's own.
            course_code=resolve_course_code(student, course_code),
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
                    salesforce_id=student.salesforce_id, subject=note_subject, body=note_body,
                    course_code=record.course_code,
                )
            if follow_up_note:
                self.note_writer.update_follow_up_note(
                    salesforce_id=student.salesforce_id, text=follow_up_note
                )
            self.activity_logger.log(f"[NOTE] {self.note_writer.describe_written(student.full_name)}")
            return StepResult(student=student, step_type="note", outcome="success")
        except Exception as exc:
            self.activity_logger.log_failure(f"[NOTE FAILED] {student.full_name}: {exc}", exc)
            return StepResult(student=student, step_type="note", outcome="failed", detail=str(exc))
