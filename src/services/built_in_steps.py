# src/services/built_in_steps.py
"""The Dashboard's three sends, offered as batch steps (developer, 2026-11-17).
A batch can hold them next to Actions; each runs exactly what its Dashboard
button runs. Their ids are fixed strings, saved in a Saved Batch's action_ids
like an Action's id, and can never clash with an Action's (uuid) id."""

WELCOME_EMAILS = "built-in:welcome-emails"
TASK_EMAILS = "built-in:task-emails"
OA_EMAILS = "built-in:oa-emails"

# id -> name shown in the batch window and in the results
BUILT_IN_STEPS = {
    WELCOME_EMAILS: "Welcome Emails",
    TASK_EMAILS: "Task Emails",
    OA_EMAILS: "OA Emails",
}

BUILT_IN_GROUP_LABEL = "Dashboard"


def is_built_in(step) -> bool:
    return isinstance(step, str) and step in BUILT_IN_STEPS
