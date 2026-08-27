import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add project 'src' folder to Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from controllers.app_controller import AppController
from models.group import Group
from models.action import Action
from services.group_repository import GroupRepository
from services.action_repository import ActionRepository
from services.action_runner import ActionRunSummary, BatchRunSummary, BatchItemResult, StepResult


def test_handle_add_action_clicked_reads_nav_panel_group():
    # Arrange: Setup mock controller with nav_panel
    controller = MagicMock()
    controller.groups = [MagicMock(name="Group 1")]
    
    # Mock nav_panel and its group dropdown selection
    mock_nav_panel = MagicMock()
    mock_nav_panel.group_dropdown.get.return_value = "Selected Group Name"
    controller.nav_panel = mock_nav_panel

    handle_add_action = AppController.handle_add_action_clicked.__get__(controller, AppController)

    # Act
    handle_add_action()

    # Assert
    controller.switch_workspace_view.assert_called_once()
    _, kwargs = controller.switch_workspace_view.call_args
    assert kwargs["initial_group_name"] == "Selected Group Name"


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_save_action_sets_welcome_action_id(mock_ctk, mock_init_views):
    """Verify that saving an action with is_welcome_email=True sets group.welcome_action_id."""
    controller = AppController()
    group = Group(name="Test Group")
    controller.groups = [group]

    action_data = {
        "id": "ACT-100",
        "name": "Welcome Action",
        "group_name": "Test Group",
        "is_welcome_email": True
    }

    success = controller.save_action(action_data)

    assert success is True
    assert group.welcome_action_id == "ACT-100"


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_save_action_unchecking_clears_welcome_action_id(mock_ctk, mock_init_views):
    """Verify that unchecking clears group.welcome_action_id back to None."""
    controller = AppController()
    group = Group(name="Test Group", welcome_action_id="ACT-100")
    controller.groups = [group]

    action_data = {
        "id": "ACT-100",
        "name": "Welcome Action",
        "group_name": "Test Group",
        "is_welcome_email": False
    }

    success = controller.save_action(action_data)

    assert success is True
    assert group.welcome_action_id is None


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.askyesno", return_value=True)
def test_save_action_replaces_existing_welcome_action_confirmed(mock_askyesno, mock_ctk, mock_init_views):
    """Verify replacing an existing welcome action when user confirms the popup."""
    controller = AppController()
    group = Group(name="Test Group", welcome_action_id="ACT-100")
    controller.groups = [group]

    action_data = {
        "id": "ACT-200",
        "name": "New Welcome Action",
        "group_name": "Test Group",
        "is_welcome_email": True
    }

    success = controller.save_action(action_data)

    assert success is True
    assert mock_askyesno.called
    assert group.welcome_action_id == "ACT-200"


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.askyesno", return_value=False)
def test_save_action_replaces_existing_welcome_action_cancelled(mock_askyesno, mock_ctk, mock_init_views):
    """Verify save is aborted if user cancels the replacement prompt."""
    controller = AppController()
    group = Group(name="Test Group", welcome_action_id="ACT-100")
    controller.groups = [group]

    action_data = {
        "id": "ACT-200",
        "name": "New Welcome Action",
        "group_name": "Test Group",
        "is_welcome_email": True
    }

    success = controller.save_action(action_data)

    assert success is False
    assert mock_askyesno.called
    assert group.welcome_action_id == "ACT-100"  # Unchanged


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.askokcancel", return_value=True)
@patch("src.controllers.app_controller.messagebox.showinfo")
def test_delete_group_cascades_to_its_actions(mock_showinfo, mock_askokcancel, mock_ctk, mock_init_views, tmp_path):
    """Deleting a group must also delete the actions assigned to it, rather
    than leaving them pointing at a group_id that no longer exists."""
    controller = AppController()
    # Isolate this test from the developer's real local data/*.json files.
    controller.group_repo = GroupRepository(data_file=tmp_path / "groups.json")
    controller.action_repo = ActionRepository(data_file=tmp_path / "actions.json")

    group = controller.group_repo.add_group("Group To Delete")
    controller.groups = [group]

    doomed_action = Action(name="Orphan Candidate", group_id=group.id)
    kept_action = Action(name="Unrelated Action", group_id="some-other-group-id")
    controller.action_repo.save_action(doomed_action)
    controller.action_repo.save_action(kept_action)

    controller.nav_panel = MagicMock()

    controller.handle_delete_group(group.name)

    remaining_action_ids = {a.id for a in controller.action_repo.load_actions()}
    assert doomed_action.id not in remaining_action_ids
    assert kept_action.id in remaining_action_ids

    remaining_group_names = {g.name for g in controller.group_repo.load_groups()}
    assert group.name not in remaining_group_names


@patch("src.controllers.app_controller.messagebox.showinfo")
def test_handle_send_ad_hoc_email_passes_note_fields_through_and_shows_showinfo(mock_showinfo):
    controller = MagicMock()
    controller.action_runner.send_ad_hoc_email.return_value = ActionRunSummary()

    handle_send = AppController.handle_send_ad_hoc_email.__get__(controller, AppController)
    handle_send(
        subject="Class Canceled", body="<p>No class today.</p>", signature="Sig",
        note_subject="Broadcast sent", note_body="Notified", follow_up_note="See broadcast",
    )

    controller.action_runner.send_ad_hoc_email.assert_called_once_with(
        "Class Canceled", "<p>No class today.</p>", "Sig",
        note_subject="Broadcast sent", note_body="Notified", follow_up_note="See broadcast",
    )
    mock_showinfo.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showwarning")
def test_handle_send_ad_hoc_email_shows_showwarning_on_failures(mock_showwarning):
    controller = MagicMock()
    failed_summary = ActionRunSummary(
        results=[StepResult(student=MagicMock(), step_type="email", outcome="failed")]
    )
    controller.action_runner.send_ad_hoc_email.return_value = failed_summary

    handle_send = AppController.handle_send_ad_hoc_email.__get__(controller, AppController)
    handle_send(subject="Class Canceled", body="<p>No class today.</p>")

    mock_showwarning.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showinfo")
def test_handle_run_batch_shows_showinfo_when_everything_succeeds(mock_showinfo):
    controller = MagicMock()
    batch_summary = BatchRunSummary(items=[
        BatchItemResult(action_name="Action A", group_name="Group A", summary=ActionRunSummary()),
    ])
    controller.action_runner.run_batch.return_value = batch_summary
    action = MagicMock()

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([action], ["Group A"])

    controller.action_runner.run_batch.assert_called_once_with([(action, "Group A")])
    mock_showinfo.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showwarning")
def test_handle_run_batch_shows_showwarning_when_an_action_errors(mock_showwarning):
    controller = MagicMock()
    batch_summary = BatchRunSummary(items=[
        BatchItemResult(action_name="Broken", group_name="Group A", summary=ActionRunSummary(), error="boom"),
    ])
    controller.action_runner.run_batch.return_value = batch_summary

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([MagicMock()], ["Group A"])

    mock_showwarning.assert_called_once()
    message = mock_showwarning.call_args[0][1]
    assert "Broken" in message
    assert "boom" in message


@patch("src.controllers.app_controller.messagebox.showwarning")
def test_handle_run_batch_shows_showwarning_when_a_step_failed(mock_showwarning):
    controller = MagicMock()
    failed_summary = ActionRunSummary(
        results=[StepResult(student=MagicMock(), step_type="email", outcome="failed")]
    )
    batch_summary = BatchRunSummary(items=[
        BatchItemResult(action_name="Action A", group_name="Group A", summary=failed_summary),
    ])
    controller.action_runner.run_batch.return_value = batch_summary

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([MagicMock()], ["Group A"])

    mock_showwarning.assert_called_once()


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("controllers.app_controller.BatchRunModal")
def test_handle_open_batch_runner_loads_actions_and_opens_modal_with_on_run_wired(
    mock_modal, mock_ctk, mock_init_views, tmp_path
):
    """Uses a real AppController (same pattern as every other controller
    test here) rather than a bare MagicMock 'self' - handle_open_batch_runner
    calls winfo_toplevel() on right_workspace and hands the result to a real
    CTkToplevel subclass as its master, which needs a real (if hidden)
    widget behind it, not a MagicMock standing in for one.

    Patch target note: this file imports AppController via
    'controllers.app_controller' (no src. prefix - see sys.path.insert at
    the top of this file), so a project-local name like BatchRunModal must
    be patched on that exact module object to actually take effect; unlike
    ctk/messagebox (shared third-party modules, patchable from either
    prefix), patching 'src.controllers.app_controller.BatchRunModal'
    silently patches a *different* module instance and leaves the real
    class in place - which then tries to construct a real CTkToplevel with
    a MagicMock as its master and hangs Tk's internals indefinitely."""
    controller = AppController()
    controller.action_repo = ActionRepository(data_file=tmp_path / "actions.json")
    saved_action = controller.action_repo.save_action(Action(name="A1", group_id="G1"))
    controller.groups = [Group(name="Group A", group_id="G1")]
    controller.right_workspace = MagicMock()

    controller.handle_open_batch_runner()

    mock_modal.assert_called_once()
    _, kwargs = mock_modal.call_args
    assert [a.id for a in kwargs["actions"]] == [saved_action.id]
    assert kwargs["groups"] == controller.groups
    assert kwargs["on_run"] == controller._handle_run_batch