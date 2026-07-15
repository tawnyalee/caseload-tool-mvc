# src/models/action.py
import uuid

class Action:
    def __init__(self, name: str, email_draft: str = "", text_draft: str = "", 
                 leave_salesforce_note: bool = False, action_id: str = None):
        self.id = action_id if action_id is not None else str(uuid.uuid4())
        self.name = name
        
        # Communication Drafts
        self.email_draft = email_draft
        self.text_draft = text_draft
        self.leave_salesforce_note = leave_salesforce_note

    @property
    def has_email(self) -> bool:
        """Returns True if this action includes an email component."""
        return bool(self.email_draft.strip())

    @property
    def has_text(self) -> bool:
        """Returns True if this action includes a text component."""
        return bool(self.text_draft.strip())