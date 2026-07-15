# src/models/group.py - this group is equivalent to a course code usually. Group is assigned an ID so renaming doesn't break logic

import uuid

class Group:
    def __init__(self, name: str, scenarios: list[str] = None, group_id: str = None):
        # If a group_id is passed (e.g., loaded from database/file), use it.
        # Otherwise, generate a brand new unique ID.
        self.id = group_id if group_id is not None else str(uuid.uuid4())
        self.name = name
        self.scenarios = scenarios if scenarios is not None else []

    def add_scenario(self, scenario_name: str):
        """Adds a scenario name to this group if it isn't already there."""
        if scenario_name not in self.scenarios:
            self.scenarios.append(scenario_name)

    def remove_scenario(self, scenario_name: str):
        """Removes a scenario name from this group."""
        if scenario_name in self.scenarios:
            self.scenarios.remove(scenario_name)