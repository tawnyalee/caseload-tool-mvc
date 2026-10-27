# src/views/settings_view.py
"""The ⚙ Settings screen. For now one section, Courses: for each group
(except General), whether it's a course, its course code, whether it has
tasks (and how many) and an objective assessment. Tasks and an OA are
independent - a course can have either, both, or neither.

Why it matters: an action in a course group only reaches that course's
students (action_runner.in_group_course), and a group that isn't a course
reaches every course, like General. The task count is what the upcoming
per-task "next task" emails are built from.

Nothing is saved until "Save Settings"; invalid entries (a course with no
code, a task count that isn't a whole number of at least 1) are pointed
out instead of saved.
"""
from typing import Callable, Dict, List

import customtkinter as ctk

from src.models.group import Group


class _GroupCard(ctk.CTkFrame):
    """One group's settings."""

    def __init__(self, master, group: Group):
        super().__init__(master, border_width=1, border_color=("gray75", "gray30"))
        self.group = group

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
            onvalue="on", offvalue="off",
        )
        self.has_oa_box.grid(row=3, column=0, columnspan=3, sticky="w", padx=32, pady=(3, 10))

        self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        is_course = self.is_course_var.get() == "on"
        course_state = "normal" if is_course else "disabled"
        for widget in (self.course_code_entry, self.has_tasks_box, self.has_oa_box):
            widget.configure(state=course_state)
        tasks_on = is_course and self.has_tasks_var.get() == "on"
        self.task_count_entry.configure(state="normal" if tasks_on else "disabled")

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
        return {
            "is_course": is_course,
            "course_code": code if is_course else self.group.course_code,
            "has_tasks": has_tasks,
            "task_count": task_count if has_tasks else self.group.task_count,
            "has_objective_assessment": is_course and self.has_oa_var.get() == "on",
            "problems": problems,
        }


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, groups: List[Group], on_save: Callable[[Dict[str, Dict]], None], **kwargs):
        """`on_save({group_id: settings})` is called only when every card is valid."""
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_save = on_save

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
            card = _GroupCard(scroller, group)
            card.pack(fill="x", pady=5, padx=2)
            self.cards.append(card)
        if not groups:
            ctk.CTkLabel(scroller, text="No groups yet - add one with + Add Group.").pack(pady=20)

    def save(self) -> bool:
        values = {card.group.id: card.read() for card in self.cards}
        problems = [p for v in values.values() for p in v["problems"]]
        if problems:
            self.problems_label.configure(text="\n".join(problems))
            return False
        self.problems_label.configure(text="")
        self.on_save({gid: {k: v for k, v in val.items() if k != "problems"} for gid, val in values.items()})
        return True
