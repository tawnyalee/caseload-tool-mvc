# src/views/settings_view.py
"""The ⚙ Settings screen: a default Outlook signature, then Courses: for each
group (except General), whether it's a course, its course code, whether it
has tasks (and how many) and an objective assessment. Tasks and an OA are
independent - a course can have either, both, or neither.

Why it matters: an action in a course group only reaches that course's
students (action_runner.in_group_course), and a group that isn't a course
reaches every course, like General. The task count is what the per-task
emails sent by Send Task Emails are built from (task_emails.py).

Nothing is saved until "Save Settings". Each group saves on its own: an
invalid card (a course with no code, a task count that isn't a whole number
of at least 1) is listed and left unsaved, and the rest still save, so a
professor can set up one course at a time.
"""
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from src.models.group import DEFAULT_TASK_EMAIL_SUBJECT, Group
from src.services.task_emails import support_label
from src.views.template_editor_modal import TemplateEditorModal

NO_EMAIL = "(no email)"
NO_DEFAULT_SIGNATURE = "(none)"


class _GroupCard(ctk.CTkFrame):
    """One group's settings."""

    def __init__(
        self, master, group: Group, templates: List[Tuple[str, str]],
        open_template_editor: Optional[Callable] = None,
    ):
        """`templates` is [(template_id, name)] for the task-email dropdowns.
        `open_template_editor(card, task_number, template_id)` is New/Edit."""
        super().__init__(master, border_width=1, border_color=("gray75", "gray30"))
        self.group = group
        self.open_template_editor = open_template_editor
        self._set_choices(templates)
        # What each task row holds, kept across rebuilds (count/OA changes).
        self._email_values: Dict[str, dict] = {k: dict(v) for k, v in group.task_emails.items()}
        self._email_widgets: Dict[int, ctk.CTkOptionMenu] = {}

        ctk.CTkLabel(self, text=group.name, font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4)
        )

        self.is_course_var = ctk.StringVar(value="on" if group.is_course else "off")
        ctk.CTkCheckBox(
            self, text="This group is a course", variable=self.is_course_var,
            onvalue="on", offvalue="off", command=self._refresh_enabled,
        ).grid(row=1, column=0, sticky="w", padx=12, pady=3)

        ctk.CTkLabel(self, text="Course code:").grid(row=1, column=1, sticky="e", padx=(12, 4))
        self.course_code_entry = ctk.CTkEntry(self, width=110, placeholder_text="e.g. D424")
        self.course_code_entry.insert(0, group.course_code)
        self.course_code_entry.grid(row=1, column=2, sticky="w", padx=(0, 12))

        self.has_tasks_var = ctk.StringVar(value="on" if group.has_tasks else "off")
        self.has_tasks_box = ctk.CTkCheckBox(
            self, text="Has tasks", variable=self.has_tasks_var,
            onvalue="on", offvalue="off", command=self._refresh_enabled,
        )
        self.has_tasks_box.grid(row=2, column=0, sticky="w", padx=32, pady=3)

        ctk.CTkLabel(self, text="How many:").grid(row=2, column=1, sticky="e", padx=(12, 4))
        self.task_count_entry = ctk.CTkEntry(self, width=60, placeholder_text="e.g. 5")
        if group.task_count:
            self.task_count_entry.insert(0, str(group.task_count))
        self.task_count_entry.grid(row=2, column=2, sticky="w", padx=(0, 12))

        self.has_oa_var = ctk.StringVar(value="on" if group.has_objective_assessment else "off")
        self.has_oa_box = ctk.CTkCheckBox(
            self, text="Has an objective assessment (OA)", variable=self.has_oa_var,
            onvalue="on", offvalue="off", command=self._refresh_enabled,
        )
        self.has_oa_box.grid(row=3, column=0, columnspan=3, sticky="w", padx=32, pady=(3, 10))

        self.emails_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.emails_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 10))
        self.task_count_entry.bind("<KeyRelease>", lambda _event: self._rebuild_email_rows())

        self._refresh_enabled()

    def _set_choices(self, templates: List[Tuple[str, str]]) -> None:
        # Dropdowns show names but store IDs (never look templates up by name).
        self._choice_to_id: Dict[str, str] = {}
        for template_id, name in templates:
            label = name if name not in self._choice_to_id else f"{name} ({template_id[:4]})"
            self._choice_to_id[label] = template_id
        self._id_to_choice = {tid: label for label, tid in self._choice_to_id.items()}

    def set_templates(self, templates: List[Tuple[str, str]]) -> None:
        """After a template is added or renamed, keeping what's chosen."""
        self._capture_email_rows()
        self._set_choices(templates)
        self._rebuild_email_rows()

    def choose_template(self, task_number: int, template_id: str) -> None:
        self._capture_email_rows()
        row = self._email_values.setdefault(str(task_number), {"subject": DEFAULT_TASK_EMAIL_SUBJECT})
        row["template_id"] = template_id
        self._email_widgets = {}  # so the rebuild keeps this choice, not the old dropdown's
        self._rebuild_email_rows()

    def _open_editor(self, task_number: int, is_new: bool) -> None:
        template_id = None if is_new else self._choice_to_id.get(self._email_widgets[task_number].get())
        if self.open_template_editor:
            self.open_template_editor(self, task_number, template_id)

    def _refresh_enabled(self) -> None:
        is_course = self.is_course_var.get() == "on"
        course_state = "normal" if is_course else "disabled"
        for widget in (self.course_code_entry, self.has_tasks_box, self.has_oa_box):
            widget.configure(state=course_state)
        tasks_on = is_course and self.has_tasks_var.get() == "on"
        self.task_count_entry.configure(state="normal" if tasks_on else "disabled")
        self._rebuild_email_rows()

    def _current_shape(self) -> Group:
        """A throwaway Group with what's on screen right now, to reuse
        Group.task_email_rows() for which rows to show."""
        count_text = self.task_count_entry.get().strip()
        return Group(
            name=self.group.name, is_course=self.is_course_var.get() == "on",
            has_tasks=self.has_tasks_var.get() == "on",
            task_count=int(count_text) if count_text.isdigit() else 0,
            has_objective_assessment=self.has_oa_var.get() == "on",
        )

    def _capture_email_rows(self) -> None:
        for number, dropdown in self._email_widgets.items():
            saved = self._email_values.get(str(number), {})
            self._email_values[str(number)] = {
                "template_id": self._choice_to_id.get(dropdown.get(), ""),
                "subject": saved.get("subject") or DEFAULT_TASK_EMAIL_SUBJECT,
            }

    def _rebuild_email_rows(self) -> None:
        self._capture_email_rows()
        for widget in self.emails_frame.winfo_children():
            widget.destroy()
        self._email_widgets = {}
        rows = self._current_shape().task_email_rows()
        if not rows:
            return

        ctk.CTkLabel(
            self.emails_frame, text="Task emails — sent to a student who just passed:",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(4, 2))
        choices = [NO_EMAIL] + list(self._choice_to_id)
        for i, number in enumerate(rows, start=1):
            ctk.CTkLabel(self.emails_frame, text=f"Passed Task {number}").grid(
                row=i, column=0, sticky="w", padx=(10, 6), pady=2
            )
            saved = self._email_values.get(str(number), {})
            dropdown = ctk.CTkOptionMenu(self.emails_frame, values=choices, width=135)
            dropdown.set(self._id_to_choice.get(saved.get("template_id", ""), NO_EMAIL))
            dropdown.grid(row=i, column=1, sticky="w", padx=4, pady=2)
            ctk.CTkButton(
                self.emails_frame, text="➕ New", width=60, command=lambda n=number: self._open_editor(n, True),
            ).grid(row=i, column=2, padx=2, pady=2)
            ctk.CTkButton(
                self.emails_frame, text="✏️ Edit", width=60, command=lambda n=number: self._open_editor(n, False),
            ).grid(row=i, column=3, padx=2, pady=2)
            ctk.CTkLabel(
                self.emails_frame, text=f"Subject: {support_label(number + 1)}",
                text_color=("gray40", "gray60"),
            ).grid(row=i, column=4, sticky="w", padx=(6, 0), pady=2)
            self._email_widgets[number] = dropdown

    def read(self) -> Dict:
        """The card's values, plus a list of problems (empty = valid)."""
        is_course = self.is_course_var.get() == "on"
        has_tasks = is_course and self.has_tasks_var.get() == "on"
        code = self.course_code_entry.get().strip()
        count_text = self.task_count_entry.get().strip()
        problems = []
        if is_course and not code:
            problems.append(f"{self.group.name}: enter the course code.")
        task_count = 0
        if has_tasks:
            if count_text.isdigit() and int(count_text) >= 1:
                task_count = int(count_text)
            else:
                problems.append(f"{self.group.name}: enter how many tasks (a whole number, 1 or more).")
        self._capture_email_rows()
        return {
            "task_emails": dict(self._email_values),
            "is_course": is_course,
            "course_code": code if is_course else self.group.course_code,
            "has_tasks": has_tasks,
            "task_count": task_count if has_tasks else self.group.task_count,
            "has_objective_assessment": is_course and self.has_oa_var.get() == "on",
            "problems": problems,
        }


class SettingsView(ctk.CTkFrame):
    def __init__(
        self, master, groups: List[Group], on_save: Callable[[Dict[str, Dict], List[str]], None],
        templates: Optional[List[Tuple[str, str]]] = None,
        load_templates: Optional[Callable[[], List[Tuple[str, str]]]] = None,
        signature_names: Optional[List[str]] = None, default_signature: str = "",
        on_save_signature: Optional[Callable[[str], None]] = None,
        save_template: Optional[Callable[[Optional[str], str, str], str]] = None,
        get_template: Optional[Callable] = None,
        **kwargs,
    ):
        """`on_save({group_id: settings}, problems)` gets the valid cards plus
        what's wrong with the rest, whose settings are left out.
        `templates` = [(template_id, name)] for the task emails, or
        `load_templates` to read them (and reread after New/Edit).
        `save_template`/`get_template` back the New/Edit buttons, the same
        calls the Action editor's buttons use."""
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_save = on_save
        self.load_templates = load_templates
        self.on_save_signature = on_save_signature
        self.save_template = save_template
        self.get_template = get_template
        templates = load_templates() if load_templates else (templates or [])

        ctk.CTkLabel(self, text="⚙ Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 2)
        )

        # Footer packed before the scrolling list so it can never be pushed out of view.
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=10, pady=10)
        self.problems_label = ctk.CTkLabel(footer, text="", text_color="#b22222", justify="left", anchor="w")
        self.problems_label.pack(side="left", fill="x", expand=True)
        self.save_button = ctk.CTkButton(footer, text="💾 Save Settings", command=self.save)
        self.save_button.pack(side="right")

        ctk.CTkLabel(self, text="Default Outlook Signature", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 0)
        )
        ctk.CTkLabel(
            self, text="Optional. New Actions start with it, and Send Task Emails uses it.",
            text_color=("gray35", "gray65"), wraplength=420, justify="left",
        ).pack(anchor="w", padx=10)
        self.signature_dropdown = ctk.CTkOptionMenu(
            self, values=[NO_DEFAULT_SIGNATURE] + list(signature_names or []), width=260
        )
        self.signature_dropdown.set(default_signature or NO_DEFAULT_SIGNATURE)
        self.signature_dropdown.pack(anchor="w", padx=10, pady=(4, 6))

        ctk.CTkLabel(self, text="Courses", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 0))
        ctk.CTkLabel(
            self,
            text="An Action in a course group only reaches students in that course. "
                 "A group that isn't a course reaches every course, like General.",
            text_color=("gray35", "gray65"), wraplength=420, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        scroller = ctk.CTkScrollableFrame(self)
        scroller.pack(fill="both", expand=True, padx=10)
        self.cards: List[_GroupCard] = []
        for group in groups:
            card = _GroupCard(scroller, group, templates, open_template_editor=self._open_template_editor)
            card.pack(fill="x", pady=5, padx=2)
            self.cards.append(card)
        if not groups:
            ctk.CTkLabel(scroller, text="No groups yet - add one with + Add Group.").pack(pady=20)

    def _open_template_editor(self, card: _GroupCard, task_number: int, template_id: Optional[str]) -> None:
        template = self.get_template(template_id) if template_id and self.get_template else None
        TemplateEditorModal(
            master=self.winfo_toplevel(),
            template_id=template.id if template else None,
            template_name=template.name if template else "",
            template_body=template.body if template else "",
            # Saved on pywebview's thread, so back to Tk's before touching widgets.
            on_save_callback=lambda *saved: self.after(0, lambda: self._template_saved(card, task_number, *saved)),
        )

    def _template_saved(self, card: _GroupCard, task_number: int, template_id, name: str, body: str) -> None:
        """The new or edited template goes straight into the row; the row
        itself is saved by Save Settings, like every other choice here."""
        saved_id = self.save_template(template_id, name, body) if self.save_template else template_id
        if self.load_templates:
            templates = self.load_templates()
            for each in self.cards:
                each.set_templates(templates)
        if saved_id:
            card.choose_template(task_number, saved_id)

    def save(self) -> bool:
        if self.on_save_signature:
            choice = self.signature_dropdown.get()
            self.on_save_signature("" if choice == NO_DEFAULT_SIGNATURE else choice)
        values = {card.group.id: card.read() for card in self.cards}
        problems = [p for v in values.values() for p in v["problems"]]
        self.problems_label.configure(text="\n".join(problems))
        valid = {
            gid: {k: v for k, v in val.items() if k != "problems"}
            for gid, val in values.items() if not val["problems"]
        }
        self.on_save(valid, problems)
        return not problems
