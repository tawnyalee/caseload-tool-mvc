# src/models/group.py - this group is equivalent to a course code usually. Group is assigned an ID so renaming doesn't break logic

import uuid
from typing import Dict, List, Optional

DEFAULT_TASK_EMAIL_SUBJECT = "Nice work on {{last_passed_task}}!"

class Group:
    def __init__(
        self,
        name: str,
        scenarios: list[str] = None,
        group_id: str = None,
        welcome_action_id: Optional[str] = None,
        has_tasks: bool = False,
        has_objective_assessment: bool = False,
        is_course: bool = False,
        course_code: str = "",
        task_count: int = 0,
        task_emails: Optional[Dict[str, dict]] = None,
        sequential_tasks: bool = True,
    ):
        # If a group_id is passed (e.g., loaded from database/file), use it.
        # Otherwise, generate a brand new unique ID.
        self.id = group_id if group_id is not None else str(uuid.uuid4())
        self.name = name
        self.scenarios = scenarios if scenarios is not None else []
        self.welcome_action_id = welcome_action_id
        # A course can use tasks, an objective assessment (exam), both, or
        # neither - independent flags, not mutually exclusive. Set at group
        # creation since it can't be reliably inferred from student data
        # (a brand-new course with no submissions yet would look identical
        # to a course that doesn't use tasks at all).
        self.has_tasks = has_tasks
        self.has_objective_assessment = has_objective_assessment
        # Course settings (configured in Settings, 2026-10-27). A group can be
        # a course or not: a course group's actions only reach students whose
        # course matches course_code (see action_runner.in_group_course); any
        # other group reaches every course, like General. course_code is
        # separate from the name so a group can be named anything.
        self.is_course = is_course
        self.course_code = course_code
        self.task_count = task_count
        # "Next task" emails, keyed by the task just PASSED (as a string, for
        # JSON): {"2": {"template_id": "...", "subject": "..."}} = the email
        # for a student who just passed Task 2. See task_email_rows().
        self.task_emails: Dict[str, dict] = dict(task_emails or {})
        # Whether the course's tasks must be submitted in order (developer,
        # 2026-11-05). Most do. When not, a student can pass Task 3 with Task
        # 1 never submitted, so its emails are kept per task to support
        # ("support<N>" keys) instead of per task passed, and the app sends the
        # lowest task not yet submitted. Both sets are kept, so switching
        # back and forth never mixes them up.
        self.sequential_tasks = sequential_tasks

    def task_email_rows(self) -> List[int]:
        """The task numbers with an email row. In order: each task passed,
        except the last, since there's no next task to send (developer,
        2026-10-27). In any order: each task to support, 1 through N. OAs are
        left out for now, see task_emails.py."""
        if not (self.is_course and self.has_tasks and self.task_count > 0):
            return []
        if self.sequential_tasks:
            return list(range(1, self.task_count))
        return list(range(1, self.task_count + 1))

    @staticmethod
    def task_email_key(number: int, sequential: bool) -> str:
        """Where a row's email is kept in task_emails."""
        return str(number) if sequential else f"support{number}"

    def task_email_for(self, passed_task: Optional[int]) -> Optional[dict]:
        """For a course in order: the configured email for a student who just
        passed `passed_task`, or None if there isn't one (no row, or no
        template chosen)."""
        if not self.sequential_tasks or passed_task is None or passed_task not in self.task_email_rows():
            return None
        email = self.task_emails.get(self.task_email_key(passed_task, True)) or {}
        return email if email.get("template_id") else None

    def support_email_for(self, task: int) -> Optional[dict]:
        """For a course in any order: the email supporting `task`, or None."""
        if self.sequential_tasks or task not in self.task_email_rows():
            return None
        email = self.task_emails.get(self.task_email_key(task, False)) or {}
        return email if email.get("template_id") else None

    @property
    def scoped_course_code(self) -> str:
        """The course this group's actions are limited to, or "" for none."""
        return self.course_code.strip() if self.is_course else ""

    def add_scenario(self, scenario_name: str):
        """Adds a scenario name to this group if it isn't already there."""
        if scenario_name not in self.scenarios:
            self.scenarios.append(scenario_name)

    def remove_scenario(self, scenario_name: str):
        """Removes a scenario name from this group."""
        if scenario_name in self.scenarios:
            self.scenarios.remove(scenario_name)