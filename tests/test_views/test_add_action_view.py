from unittest.mock import patch

import pytest
import customtkinter as ctk
from src.views.add_action_view import AddActionView
from src.models.email_template import EmailTemplate
from src.models.group import Group
from src.services.template_repository import TemplateRepository
from src.services.student_data_provider import FakeStudentDataProvider


class MockController:
    """A minimal mock controller to satisfy the view's requirements."""
    pass


class MockControllerWithTemplates:
    """A mock controller carrying a real (tmp_path-backed) template repository."""
    def __init__(self, template_repo):
        self.template_repo = template_repo


class MockControllerWithStudents:
    """A mock controller carrying a real (tmp_path-backed) student provider,
    for testing that live-dropdown filter fields pull from real data."""
    def __init__(self, student_data_provider):
        self.student_data_provider = student_data_provider


@pytest.fixture(scope="session")
def ctk_root():
    """Creates a single shared CTk root instance for all view tests."""
    app = ctk.CTk()
    app.withdraw()  # Hide window during test execution
    yield app
    app.destroy()


def test_add_action_view_initialization(ctk_root):
    mock_controller = MockController()
    view = AddActionView(master=ctk_root, controller=mock_controller)
    assert view is not None
    assert hasattr(view, 'scrollable_container')
    assert isinstance(view.scrollable_container, ctk.CTkScrollableFrame)


def test_add_action_view_selects_initial_group_on_add(ctk_root):
    """Verify that initial_group_name is selected when adding a new action."""
    mock_controller = MockController()
    groups = ["Group A", "Group B", "Group C"]
    
    view = AddActionView(
        master=ctk_root,
        controller=mock_controller,
        groups=groups,
        initial_group_name="Group B"
    )
    assert view.group_dropdown.get() == "Group B"


def test_new_action_starts_with_one_blank_filter_row(ctk_root):
    view = AddActionView(master=ctk_root, controller=MockController())
    assert len(view.filter_rows) == 1


def test_get_action_data_omits_incomplete_filter_rows(ctk_root):
    """A blank/never-touched default row shouldn't produce a filter condition."""
    view = AddActionView(master=ctk_root, controller=MockController())
    assert view.get_action_data()["filters"] == []


def test_get_action_data_includes_a_completed_filter_row(ctk_root):
    view = AddActionView(master=ctk_root, controller=MockController())
    row = view.filter_rows[0]
    row.field_dropdown.set("salesforce_id")
    row._on_field_changed("salesforce_id")
    row.operator_dropdown.set("Equals")
    row._on_operator_changed("Equals")
    row._value_widgets[0].insert(0, "000000001")

    assert view.get_action_data()["filters"] == [
        {"field": "salesforce_id", "operator": "Equals", "value": "000000001"}
    ]


def test_editing_an_action_repopulates_its_saved_filters(ctk_root):
    """Regression test: editing an action used to silently drop its saved
    filters (populate_fields never read them), which would now silently
    widen an action back to the full roster on the next save."""
    action_data = {
        "group_name": "Group A",
        "filters": [
            {"field": "salesforce_id", "operator": "Equals", "value": "000000001"},
            {"field": "momentum", "operator": "IsOneOf", "value": ["Low", "Med"]},
        ],
    }
    view = AddActionView(
        master=ctk_root, controller=MockController(), groups=["Group A"], action_data=action_data
    )

    assert len(view.filter_rows) == 2
    assert view.get_action_data()["filters"] == action_data["filters"]


def test_live_dropdown_filter_field_pulls_from_real_student_data(ctk_root, tmp_path):
    fixture = tmp_path / "fake_students.json"
    fixture.write_text(
        '[{"salesforce_id": "SF1", "first_name": "Jane", "last_name": "Doe", '
        '"email": "jane@example.test", "course_code": "D424"},'
        '{"salesforce_id": "SF2", "first_name": "John", "last_name": "Roe", '
        '"email": "john@example.test", "course_code": "D370"}]',
        encoding="utf-8",
    )
    controller = MockControllerWithStudents(FakeStudentDataProvider(file_path=str(fixture)))
    view = AddActionView(master=ctk_root, controller=controller)

    assert view._get_live_field_values("course_code") == ["D370", "D424"]


def test_editing_an_action_with_no_saved_filters_still_shows_one_blank_row(ctk_root):
    action_data = {"group_name": "Group A"}
    view = AddActionView(
        master=ctk_root, controller=MockController(), groups=["Group A"], action_data=action_data
    )
    assert len(view.filter_rows) == 1
    assert view.get_action_data()["filters"] == []


def test_add_action_view_prioritizes_action_data_group_on_edit(ctk_root):
    """Verify that action_data's assigned group takes precedence when editing."""
    mock_controller = MockController()
    groups = ["Group A", "Group B", "Group C"]
    dummy_action_data = {
        "group_name": "Group C"
    }

    view = AddActionView(
        master=ctk_root,
        controller=mock_controller,
        groups=groups,
        initial_group_name="Group A",  # Selected in nav, but editing Group C
        action_data=dummy_action_data
    )
    assert view.group_dropdown.get() == "Group C"


def test_delete_unrelated_template_restores_actions_own_template(ctk_root, tmp_path):
    """Deleting a template that ISN'T assigned to the open action should restore
    the action's own template in the dropdown, not reset to New/Custom."""
    repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    assigned = EmailTemplate(name="Hiya", body="<b>Hi</b>")
    other = EmailTemplate(name="Bye", body="Bye")
    repo.save(assigned)
    repo.save(other)

    controller = MockControllerWithTemplates(repo)
    action_data = {"id": "ACT-1", "name": "Test Action", "template_id": assigned.id}

    view = AddActionView(master=ctk_root, controller=controller, action_data=action_data)
    assert view.email_body_dropdown.get() == "Hiya"

    # User browses to a different template without intending to change anything...
    view.email_body_dropdown.set("Bye")

    # ...then deletes it.
    with patch("src.views.add_action_view.messagebox.askokcancel", return_value=True):
        view._on_delete_template_click()

    assert view.email_body_dropdown.get() == "Hiya"
    assert repo.get_by_id(assigned.id) is not None
    assert repo.get_by_id(other.id) is None


def test_delete_actions_own_template_warns_and_falls_back_to_new_custom(ctk_root, tmp_path):
    """Deleting the template that IS assigned to the open action should warn
    explicitly, then fall back to New/Custom since nothing is left to select."""
    repo = TemplateRepository(file_path=str(tmp_path / "templates.json"))
    assigned = EmailTemplate(name="Hiya", body="<b>Hi</b>")
    repo.save(assigned)

    controller = MockControllerWithTemplates(repo)
    action_data = {"id": "ACT-1", "name": "Test Action", "template_id": assigned.id}

    view = AddActionView(master=ctk_root, controller=controller, action_data=action_data)
    assert view.email_body_dropdown.get() == "Hiya"

    with patch("src.views.add_action_view.messagebox.askokcancel", return_value=True) as mock_confirm:
        view._on_delete_template_click()
        warning_text = mock_confirm.call_args[0][1]
        assert "currently assigned to this action" in warning_text

    assert view.email_body_dropdown.get() == "New / Custom Template"
    assert repo.get_by_id(assigned.id) is None
    assert view.action_template_id is None


def test_new_action_gets_a_real_id_immediately(ctk_root):
    """A brand-new (unsaved) action needs a real, stable id right away so the
    live welcome-checkbox conflict check has something to compare against."""
    view = AddActionView(master=ctk_root, controller=MockController())
    assert view.action_id
    assert view.get_action_data()["id"] == view.action_id


def test_checking_welcome_box_with_no_existing_claim_sets_it_silently(ctk_root):
    group = Group(name="Group A", welcome_action_id=None)
    view = AddActionView(master=ctk_root, controller=MockController(), groups=[group], initial_group_name="Group A")

    view.chk_welcome_email.toggle()  # simulates an actual user click, incl. firing `command`

    assert group.welcome_action_id == view.action_id
    assert view.is_welcome_email_var.get() == "on"


def test_checking_welcome_box_with_existing_claim_prompts_and_confirms(ctk_root):
    group = Group(name="Group A", welcome_action_id="some-other-action-id")
    view = AddActionView(master=ctk_root, controller=MockController(), groups=[group], initial_group_name="Group A")

    with patch("src.views.add_action_view.messagebox.askyesno", return_value=True) as mock_confirm:
        view.chk_welcome_email.toggle()
        assert mock_confirm.called

    assert group.welcome_action_id == view.action_id
    assert view.is_welcome_email_var.get() == "on"


def test_checking_welcome_box_with_existing_claim_reverts_on_cancel(ctk_root):
    group = Group(name="Group A", welcome_action_id="some-other-action-id")
    view = AddActionView(master=ctk_root, controller=MockController(), groups=[group], initial_group_name="Group A")

    with patch("src.views.add_action_view.messagebox.askyesno", return_value=False):
        view.chk_welcome_email.toggle()

    assert group.welcome_action_id == "some-other-action-id"
    assert view.is_welcome_email_var.get() == "off"


def test_unchecking_welcome_box_clears_own_claim(ctk_root):
    view = AddActionView(master=ctk_root, controller=MockController())
    group = Group(name="Group A", welcome_action_id=None)
    view.groups = [group]
    view.group_dropdown.configure(values=["Group A"])
    view.group_dropdown.set("Group A")

    view.chk_welcome_email.toggle()  # check it
    assert group.welcome_action_id == view.action_id

    view.chk_welcome_email.toggle()  # uncheck it
    assert group.welcome_action_id is None


def test_populate_fields_checks_box_when_action_is_groups_welcome_action(ctk_root):
    group = Group(name="Group A", group_id="grp-1", welcome_action_id="ACT-1")
    action_data = {"id": "ACT-1", "name": "Welcome Action", "group_id": "grp-1"}

    view = AddActionView(master=ctk_root, controller=MockController(), groups=[group], action_data=action_data)
    assert view.is_welcome_email_var.get() == "on"


def test_populate_fields_leaves_box_unchecked_when_action_is_not_the_welcome_action(ctk_root):
    group = Group(name="Group A", group_id="grp-1", welcome_action_id="ACT-OTHER")
    action_data = {"id": "ACT-1", "name": "Some Action", "group_id": "grp-1"}

    view = AddActionView(master=ctk_root, controller=MockController(), groups=[group], action_data=action_data)
    assert view.is_welcome_email_var.get() == "off"

def test_note_fields_are_disabled_until_send_email_is_checked(ctk_root):
    view = AddActionView(master=ctk_root, controller=MockController())
    assert view.note_subject.cget("state") == "disabled"
    assert view.followup_note.cget("state") == "disabled"

    view.send_email_var.set("on")
    view._toggle_email_section()

    assert view.note_subject.cget("state") == "normal"
    assert view.note_body.cget("state") == "normal"
    assert view.followup_note.cget("state") == "normal"
    assert view.interaction_menu.cget("state") == "normal"


def test_editing_a_text_only_action_keeps_its_saved_note_content(ctk_root):
    """Regression guard: a disabled entry silently ignores insert(), so the
    note fields must be enabled while populating, or a text-only action's
    saved note would be dropped and then wiped on the next save."""
    action_data = {
        "group_name": "Group A",
        "is_text": True,
        "text_body": "Hi there",
        "note_subject": "Old subject",
        "note_body": "Old body",
        "follow_up_note": "Old follow-up",
    }
    view = AddActionView(master=ctk_root, controller=MockController(), groups=["Group A"], action_data=action_data)

    assert view.note_subject.cget("state") == "disabled"
    data = view.get_action_data()
    assert data["note_subject"] == "Old subject"
    assert data["note_body"] == "Old body"
    assert data["follow_up_note"] == "Old follow-up"


class _NotLoggedInProvider:
    def get_students(self):
        raise RuntimeError('Not logged in to Salesforce. Click "Refresh Caseload" to log in.')


def test_editing_an_action_with_a_roster_filter_still_opens_when_roster_is_not_loaded(ctk_root):
    """Regression: with PingID down (roster never loaded), Edit silently did
    nothing for any action with a filter whose dropdown is filled from the
    roster."""
    action_data = {
        "group_name": "Group A",
        "filters": [{"field": "course_code", "operator": "IsOneOf", "value": ["C769"]}],
    }
    view = AddActionView(
        master=ctk_root, controller=MockControllerWithStudents(_NotLoggedInProvider()),
        groups=["Group A"], action_data=action_data,
    )
    assert len(view.filter_rows) == 1
    assert view.get_action_data()["filters"] == action_data["filters"]


def test_editing_an_action_repopulates_a_days_filter_and_does_not_contain(ctk_root):
    filters = [
        {"field": "latest_task_date", "operator": "WithinLastDays", "value": "3"},
        {"field": "course_followup_note", "operator": "DoesNotContain", "value": "Task 3 tips sent"},
    ]
    view = AddActionView(
        master=ctk_root, controller=MockController(), groups=["Group A"],
        action_data={"group_name": "Group A", "filters": filters},
    )
    assert view.get_action_data()["filters"] == filters


def test_task_emails_checkbox_greys_out_the_single_template_and_round_trips(ctk_root):
    view = AddActionView(
        master=ctk_root, controller=MockController(), groups=["Group A"],
        action_data={"group_name": "Group A", "is_email": True, "use_task_emails": True},
    )
    assert view.use_task_emails_var.get() == "on"
    assert view.email_subject.cget("state") == "disabled"
    assert view.email_body_dropdown.cget("state") == "disabled"
    assert view.btn_new_template.cget("state") == "normal"  # still make templates for Settings
    assert view.get_action_data()["use_task_emails"] is True

    view.use_task_emails_var.set("off"); view._update_task_email_state()
    assert view.email_subject.cget("state") == "normal"
    assert view.get_action_data()["use_task_emails"] is False
