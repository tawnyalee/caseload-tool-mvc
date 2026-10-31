# src/services/task_emails.py
"""What Send Task Emails sends each student (developer's design, 2026-10-31):
the email set up in Settings for the task the student just passed. No Action
is involved. The app writes the wording around it:

  - email subject, note subject and follow-up note: "Task <next> Support"
  - a "Hello <first name>," line above the saved email
  - the Salesforce note's body: the text of the email that was sent

A student who already submitted the next task gets a short congratulations
instead. The follow-up note is also how a repeat run knows who's been done.
OAs are left out for now: Salesforce only shows an OA pass in its essential
actions list.
"""
import html
import re
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Callable, Dict, List, Optional, Tuple

from src.models.group import Group
from src.models.student import Student
from src.services.merge_fields import render_merge_fields
from src.services.task_utils import has_submitted_task, parse_task_date, passed_task_number

DEFAULT_LOOK_BACK_DAYS = 1  # yesterday
MAX_LOOK_BACK_DAYS = 365


def parse_look_back_days(text: str) -> Optional[int]:
    """The dashboard's days box: blank means the default, a whole number
    from 1 to MAX_LOOK_BACK_DAYS is used as is, anything else is None."""
    text = (text or "").strip()
    if not text:
        return DEFAULT_LOOK_BACK_DAYS
    if text.isascii() and text.isdigit() and 1 <= int(text) <= MAX_LOOK_BACK_DAYS:
        return int(text)
    return None


def passed_in_look_back(student: Student, days: int, today: Optional[date] = None) -> bool:
    """True if the latest task passed in the `days` days before today. Today
    doesn't count: 3 on a Monday is Friday through Sunday."""
    passed_on = parse_task_date(student.latest_task_date)
    if passed_task_number(student) is None or passed_on is None:
        return False
    today = today or date.today()
    return today - timedelta(days=days) <= passed_on < today


def support_label(next_task: int) -> str:
    return f"Task {next_task} Support"


class _PlainText(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_plain_text(body: str) -> str:
    parser = _PlainText()
    parser.feed(body)
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.parts)).strip()


@dataclass
class TaskEmail:
    student: Student
    group: Group
    passed_task: int
    subject: str
    body: str = ""
    problem: str = ""  # why it can't be sent; such students are listed as skipped
    email_name: str = ""  # what the review window calls this email

    def preview(self) -> str:
        return html_to_plain_text(render_merge_fields(self.body, self.student))


def batches_for_review(emails: List[TaskEmail]) -> List[List[TaskEmail]]:
    """Sendable emails, one batch per distinct email: students who passed the
    same task and get the same wording."""
    batches: Dict[Tuple[int, str], List[TaskEmail]] = {}
    for task_email in emails:
        if not task_email.problem:
            batches.setdefault((task_email.passed_task, task_email.email_name), []).append(task_email)
    return [batches[key] for key in sorted(batches)]


def build_task_email(student: Student, group: Group, get_template: Callable) -> Optional[TaskEmail]:
    """The email for a student who passed a task in `group`'s course, or None
    if they passed the last task, since there's nothing next."""
    passed = passed_task_number(student)
    if passed is None or passed >= group.task_count:
        return None
    next_task = passed + 1
    name = html.escape(student.first_name)
    task_email = TaskEmail(student, group, passed, subject=support_label(next_task))

    if has_submitted_task(student, next_task):
        task_email.body = (
            f"<p>Hi {name}, congrats on passing Task {passed}. I see you submitted the next task. "
            "Good luck! If you need to revise, I'll be here to help with that process.</p>"
        )
        task_email.email_name = "Congratulations (next task already submitted)"
        return task_email

    email = group.task_email_for(passed)
    if email is None:
        task_email.problem = f"No task email set up for {group.course_code} Task {passed} (see Settings)"
        return task_email
    template = get_template(email["template_id"])
    if template is None:
        task_email.problem = f"The template chosen for {group.course_code} Task {passed} no longer exists (see Settings)"
        return task_email
    task_email.body = f"<p>Hello {name},</p>{template.body}"
    task_email.email_name = template.name
    return task_email
