import uuid
from typing import List, Optional
from src.models.enums import InteractionType

class Action:
    def __init__(
        self,
        name: str,
        group_id: str = "",
        filters: Optional[List[str]] = None,
        is_email: bool = False,
        is_text: bool = False,
        template_id: Optional[str] = None,
        email_subject: str = "",
        email_signature: str = "",
        text_subject: str = "",
        text_body: str = "",
        note_subject: str = "",
        note_body: str = "",
        follow_up_note: str = "",
        interaction_type: Optional[InteractionType] = None,
        action_id: Optional[str] = None,
    ):
        self.id = action_id if action_id is not None else str(uuid.uuid4())
        self.name = name
        self.group_id = group_id
        self.filters = filters if filters is not None else []
        self.is_email = is_email
        self.is_text = is_text
        self.template_id = template_id
        self.email_subject = email_subject
        self.email_signature = email_signature
        self.text_subject = text_subject
        self.text_body = text_body
        self.note_subject = note_subject
        self.note_body = note_body
        self.follow_up_note = follow_up_note
        self.interaction_type = interaction_type

    @property
    def has_email(self) -> bool:
        """Returns True if this action is flagged for email."""
        return self.is_email

    @property
    def has_text(self) -> bool:
        """Returns True if this action is flagged for text."""
        return self.is_text