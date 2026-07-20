from src.models.group import Group
from src.models.student import Student
from src.models.action import Action
from src.models.email_template import EmailTemplate


def test_group_unique_id_and_scenarios():
    """Verify groups get unique IDs and can manage scenarios."""
    group_a = Group(name="Group A")
    group_b = Group(name="Group B")

    # Verify IDs are unique even if created back-to-back
    assert group_a.id != group_b.id

    # Test managing scenario names
    group_a.add_scenario("Welcome Email")
    assert "Welcome Email" in group_a.scenarios

    group_a.remove_scenario("Welcome Email")
    assert "Welcome Email" not in group_a.scenarios


def test_student_properties():
    """Verify student full name logic works in memory."""
    student = Student(
        salesforce_id="SF123",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
    )
    assert student.full_name == "Jane Doe"


def test_action_flags_and_properties():
    """Verify action flags and default values."""
    action = Action(name="Follow Up", is_email=True, is_text=False)

    assert action.has_email is True
    assert action.has_text is False
    assert action.filters == []
    assert action.interaction_types == {}


def test_email_template_creation():
    """Verify email template creation and unique ID generation."""
    template = EmailTemplate(name="Welcome Template", body="Hello {{first_name}}")

    assert template.name == "Welcome Template"
    assert template.body == "Hello {{first_name}}"
    assert template.id is not None