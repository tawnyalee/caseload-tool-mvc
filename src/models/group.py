# src/models/group.py - this group is equivalent to a course code usually. Group is assigned an ID so renaming doesn't break logic

import uuid
from typing import Optional

class Group:
    def __init__(
        self,
        name: str,
        scenarios: list[str] = None,
        group_id: str = None,
        welcome_action_id: Optional[str] = None,
        has_tasks: bool = False,
        has_objective_assessment: bool = False,
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

    def add_scenario(self, scenario_name: str):
        """Adds a scenario name to this group if it isn't already there."""
        if scenario_name not in self.scenarios:
            self.scenarios.append(scenario_name)

    def remove_scenario(self, scenario_name: str):
        """Removes a scenario name from this group."""
        if scenario_name in self.scenarios:
            self.scenarios.remove(scenario_name)