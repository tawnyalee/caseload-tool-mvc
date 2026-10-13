# src/models/saved_batch.py - a named, reusable batch of actions (with run
# order), saved from BatchRunModal's "Save Batch" button so a professor can
# re-run a recurring combination without rebuilding the selection each time.
# A separate feature from BatchRunModal's existing ad-hoc "Run Batch" path,
# which never touches this - see src/CLAUDE.md's Design decisions.

import uuid
from typing import List, Optional


class SavedBatch:
    def __init__(
        self,
        name: str,
        action_ids: Optional[List[str]] = None,
        batch_id: Optional[str] = None,
    ):
        self.id = batch_id if batch_id is not None else str(uuid.uuid4())
        self.name = name
        self.action_ids = action_ids if action_ids is not None else []  # run order
