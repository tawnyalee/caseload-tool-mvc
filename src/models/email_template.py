import uuid

class EmailTemplate:
    def __init__(self, name: str, body: str = "", template_id: str = None):
        self.id = template_id if template_id is not None else str(uuid.uuid4())
        self.name = name
        self.body = body