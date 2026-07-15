# tests/test_models/test_core_models.py
from src.models.group import Group
from src.models.student import Student
from src.models.action import Action

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
        email="jane@example.com"
    )
    assert student.full_name == "Jane Doe"

def test_action_draft_detection():
    """Verify actions correctly identify if they have emails or texts."""
    action = Action(name="Follow Up", email_draft="Hello!", text_draft="  ")
    
    assert action.has_email is True
    assert action.has_text is False  # Should be False because text is just empty spaces