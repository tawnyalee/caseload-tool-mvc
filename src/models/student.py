# src/models/student.py

class Student:
    def __init__(self, salesforce_id: str, first_name: str, last_name: str, 
                 email: str, phone: str = "", has_signed_up_for_text: bool = False):
        self.salesforce_id = salesforce_id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone = phone
        self.has_signed_up_for_text = has_signed_up_for_text

    @property
    def full_name(self) -> str:
        """Returns the student's full name."""
        return f"{self.first_name} {self.last_name}"