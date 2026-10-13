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
from services.saved_batch_repository import SavedBatchRepository
from services.action_runner import ActionRunSummary, BatchRunSummary, BatchItemResult, StepResult
from models.student import Student

# AppController itself (imported above via 'controllers.app_controller', no
# src. prefix - see sys.path.insert above) internally imports these two
# classes via 'src.services.student_data_provider' - importing them the same
# way here (not 'services.student_data_provider') is required for
# isinstance()/@patch.object to target the SAME class object AppController
# actually uses, not a second, separately-loaded one - same module-identity
# footgun documented on test_handle_open_batch_runner_loads_actions_and_opens_modal_with_on_run_wired's
# BatchRunModal patch, below. Getting this wrong doesn't error - it silently
# no-ops the patch and lets the real (live, network-calling) code run instead.
from src.services.student_data_provider import CachingStudentDataProvider, PlaywrightStudentDataProvider
from src.services.salesforce_callbacks import CASELOAD_APP_URL, EXPORT_BUTTON_SELECTOR


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


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_save_action_sets_welcome_action_id(mock_ctk, mock_init_views, mock_refresh_caseload, mock_showinfo, tmp_path):
    """Verify that saving an action with is_welcome_email=True sets group.welcome_action_id.

    save_action() persists via self.group_repo.save_groups(self.groups) and
    self.action_repo.save_action(...) - without this tmp_path override, it
    was writing controller.groups (here, deliberately just one synthetic
    group) straight over the developer's real src/data/groups.json /
    src/data/actions.json, silently deleting every other real group each
    time this test ran (this is what wiped a real "D424" group out from
    under the developer during manual testing - see src/CLAUDE.md)."""
    controller = AppController()
    controller.group_repo = GroupRepository(data_file=tmp_path / "groups.json")
    controller.action_repo = ActionRepository(data_file=tmp_path / "actions.json")
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


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_save_action_unchecking_clears_welcome_action_id(
    mock_ctk, mock_init_views, mock_refresh_caseload, mock_showinfo, tmp_path
):
    """Verify that unchecking clears group.welcome_action_id back to None."""
    controller = AppController()
    controller.group_repo = GroupRepository(data_file=tmp_path / "groups.json")
    controller.action_repo = ActionRepository(data_file=tmp_path / "actions.json")
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


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.askyesno", return_value=True)
def test_save_action_replaces_existing_welcome_action_confirmed(
    mock_askyesno, mock_ctk, mock_init_views, mock_refresh_caseload, mock_showinfo, tmp_path
):
    """Verify replacing an existing welcome action when user confirms the popup."""
    controller = AppController()
    controller.group_repo = GroupRepository(data_file=tmp_path / "groups.json")
    controller.action_repo = ActionRepository(data_file=tmp_path / "actions.json")
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


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.askyesno", return_value=False)
def test_save_action_replaces_existing_welcome_action_cancelled(
    mock_askyesno, mock_ctk, mock_init_views, mock_refresh_caseload, tmp_path
):
    """Verify save is aborted if user cancels the replacement prompt."""
    controller = AppController()
    controller.group_repo = GroupRepository(data_file=tmp_path / "groups.json")
    controller.action_repo = ActionRepository(data_file=tmp_path / "actions.json")
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


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.askokcancel", return_value=True)
@patch("src.controllers.app_controller.messagebox.showinfo")
def test_delete_group_cascades_to_its_actions(
    mock_showinfo, mock_askokcancel, mock_ctk, mock_init_views, mock_refresh_caseload, tmp_path
):
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


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.showwarning")
def test_handle_rename_group_refuses_to_edit_general(mock_showwarning, mock_ctk, mock_init_views, mock_refresh_caseload):
    """'General' can't be edited at all (same protection as rename/delete) -
    execution must never reach real dialog construction for it."""
    controller = AppController()
    controller.groups = [Group(name="General", group_id="G1")]

    controller.handle_rename_group("General")

    mock_showwarning.assert_called_once()


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("src.controllers.app_controller.messagebox.showerror")
def test_handle_rename_group_reports_a_missing_group_without_opening_a_dialog(
    mock_showerror, mock_ctk, mock_init_views, mock_refresh_caseload
):
    controller = AppController()
    controller.groups = []  # the requested group doesn't exist

    controller.handle_rename_group("Nonexistent Group")

    mock_showerror.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_send_ad_hoc_email_opens_review_dialog_then_sends_on_confirm(mock_modal, mock_showinfo):
    """handle_send_ad_hoc_email no longer sends immediately - it opens the
    pre-send review dialog first (patched here, same module-identity reason
    documented on test_handle_open_batch_runner_loads_actions_and_opens_modal_with_on_run_wired
    above) and only sends once the dialog's on_confirm callback fires,
    simulating the professor clicking Send."""
    controller = MagicMock()
    controller.action_runner.send_ad_hoc_email.return_value = ActionRunSummary()
    controller.action_runner.student_provider.get_students.return_value = []

    handle_send = AppController.handle_send_ad_hoc_email.__get__(controller, AppController)
    handle_send(
        subject="Class Canceled", body="<p>No class today.</p>", signature="Sig",
        note_subject="Broadcast sent", note_body="Notified", follow_up_note="See broadcast",
    )

    controller.action_runner.send_ad_hoc_email.assert_not_called()
    mock_modal.assert_called_once()
    _, kwargs = mock_modal.call_args
    assert kwargs["is_email"] is True
    assert kwargs["initial_subject"] == "Class Canceled"

    kwargs["on_confirm"]({"SF1", "SF2"}, "Class Canceled", "<p>No class today.</p>")

    controller.action_runner.send_ad_hoc_email.assert_called_once_with(
        "Class Canceled", "<p>No class today.</p>", "Sig",
        note_subject="Broadcast sent", note_body="Notified", follow_up_note="See broadcast",
        included_student_ids={"SF1", "SF2"},
    )
    mock_showinfo.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showwarning")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_send_ad_hoc_email_shows_showwarning_on_failures(mock_modal, mock_showwarning):
    controller = MagicMock()
    failed_summary = ActionRunSummary(
        results=[StepResult(student=MagicMock(), step_type="email", outcome="failed")]
    )
    controller.action_runner.send_ad_hoc_email.return_value = failed_summary
    controller.action_runner.student_provider.get_students.return_value = []

    handle_send = AppController.handle_send_ad_hoc_email.__get__(controller, AppController)
    handle_send(subject="Class Canceled", body="<p>No class today.</p>")

    _, kwargs = mock_modal.call_args
    kwargs["on_confirm"]({"SF1"}, "Class Canceled", "<p>No class today.</p>")

    mock_showwarning.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_run_action_opens_review_dialog_with_matches_then_runs_on_confirm(mock_modal, mock_showinfo):
    controller = MagicMock()
    action = Action(name="Welcome Action", group_id="G1", is_email=True, email_subject="Welcome!")
    controller.scenarios_raw = {"Welcome Action": action}
    controller.action_runner.get_matching_students.return_value = ["s1", "s2"]
    controller.template_repo.get_by_id.return_value = None
    controller.action_runner.run.return_value = ActionRunSummary()
    controller.nav_panel.group_dropdown.get.return_value = "D424"

    handle_run_action = AppController.handle_run_action.__get__(controller, AppController)
    handle_run_action("Welcome Action")

    controller.action_runner.run.assert_not_called()
    mock_modal.assert_called_once()
    _, kwargs = mock_modal.call_args
    assert kwargs["students"] == ["s1", "s2"]
    assert kwargs["is_email"] is True
    assert kwargs["initial_subject"] == "Welcome!"

    kwargs["on_confirm"]({"SF1"}, "Edited Subject", "Edited body")

    controller.action_runner.run.assert_called_once_with(
        action, group_name="D424", included_student_ids={"SF1"},
        email_subject_override="Edited Subject", email_body_override="Edited body",
    )
    mock_showinfo.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_run_action_non_email_action_does_not_pass_content_overrides(mock_modal, mock_showinfo):
    controller = MagicMock()
    action = Action(name="Text Only", group_id="G1", is_email=False, is_text=True)
    controller.scenarios_raw = {"Text Only": action}
    controller.action_runner.get_matching_students.return_value = ["s1"]
    controller.action_runner.run.return_value = ActionRunSummary()
    controller.nav_panel.group_dropdown.get.return_value = "General"

    handle_run_action = AppController.handle_run_action.__get__(controller, AppController)
    handle_run_action("Text Only")

    _, kwargs = mock_modal.call_args
    assert kwargs["is_email"] is False

    kwargs["on_confirm"]({"SF1"}, "", "")

    controller.action_runner.run.assert_called_once_with(
        action, group_name="General", included_student_ids={"SF1"},
        email_subject_override=None, email_body_override=None,
    )


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_shows_showinfo_when_everything_succeeds(mock_modal, mock_showinfo):
    """_handle_run_batch no longer runs immediately - it opens the
    multi-item review dialog first (patched here for the same
    module-identity reason as the other modal-opening tests in this file)
    and only runs once its on_confirm callback fires."""
    controller = MagicMock()
    batch_summary = BatchRunSummary(items=[
        BatchItemResult(action_name="Action A", group_name="Group A", summary=ActionRunSummary()),
    ])
    controller.action_runner.run_batch.return_value = batch_summary
    action = MagicMock()

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([action], ["Group A"])

    controller.action_runner.run_batch.assert_not_called()
    _, kwargs = mock_modal.call_args
    kwargs["on_confirm"]({"0": {"SF1"}})

    controller.action_runner.run_batch.assert_called_once_with(
        [(action, "Group A")], included_ids_by_index={0: {"SF1"}}
    )
    mock_showinfo.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showwarning")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_shows_showwarning_when_an_action_errors(mock_modal, mock_showwarning):
    controller = MagicMock()
    batch_summary = BatchRunSummary(items=[
        BatchItemResult(action_name="Broken", group_name="Group A", summary=ActionRunSummary(), error="boom"),
    ])
    controller.action_runner.run_batch.return_value = batch_summary

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([MagicMock()], ["Group A"])

    _, kwargs = mock_modal.call_args
    kwargs["on_confirm"]({"0": {"SF1"}})

    mock_showwarning.assert_called_once()
    message = mock_showwarning.call_args[0][1]
    assert "Broken" in message
    assert "boom" in message


@patch("src.controllers.app_controller.messagebox.showwarning")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_shows_showwarning_when_a_step_failed(mock_modal, mock_showwarning):
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

    _, kwargs = mock_modal.call_args
    kwargs["on_confirm"]({"0": {"SF1"}})

    mock_showwarning.assert_called_once()


@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_builds_review_items_with_each_actions_matches(mock_modal):
    controller = MagicMock()
    action_a = MagicMock()
    action_b = MagicMock()
    action_a.name = "Welcome"
    action_b.name = "Task 2"
    controller.action_runner.get_matching_students.side_effect = [["s1", "s2"], ["s3"]]

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([action_a, action_b], ["D424", "C769"])

    _, kwargs = mock_modal.call_args
    review_items = kwargs["items"]
    assert [item.key for item in review_items] == ["0", "1"]
    assert review_items[0].label == "D424 — Welcome"
    assert review_items[0].students == ["s1", "s2"]
    assert review_items[1].label == "C769 — Task 2"
    assert review_items[1].students == ["s3"]


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_send_welcome_emails_only_includes_groups_with_a_valid_welcome_action(mock_modal, mock_showinfo):
    controller = MagicMock()
    action = MagicMock()
    action.name = "Welcome"
    controller.action_repo.load_actions.return_value = [action]
    action.id = "ACT-1"
    controller.groups = [
        Group(name="D424", group_id="G1", welcome_action_id="ACT-1"),
        Group(name="No Welcome", group_id="G2", welcome_action_id=None),
        Group(name="Dangling", group_id="G3", welcome_action_id="ACT-MISSING"),
    ]
    controller.action_runner.get_matching_students.return_value = ["s1"]
    controller.action_runner.run_welcome_emails.return_value = ActionRunSummary()

    handle_send_welcome_emails = AppController.handle_send_welcome_emails.__get__(controller, AppController)
    handle_send_welcome_emails()

    controller.action_runner.run_welcome_emails.assert_not_called()
    _, kwargs = mock_modal.call_args
    review_items = kwargs["items"]
    assert [item.key for item in review_items] == ["G1"]
    assert review_items[0].label == "D424 — Welcome"

    kwargs["on_confirm"]({"G1": {"s1"}})

    controller.action_runner.run_welcome_emails.assert_called_once_with(
        controller.groups, {"ACT-1": action}, included_ids_by_group_id={"G1": {"s1"}}
    )
    mock_showinfo.assert_called_once()


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch("controllers.app_controller.BatchRunModal")
def test_handle_open_batch_runner_loads_actions_and_opens_modal_with_on_run_wired(
    mock_modal, mock_ctk, mock_init_views, mock_refresh_caseload, tmp_path
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
    controller.saved_batch_repo = SavedBatchRepository(data_file=tmp_path / "saved_batches.json")
    saved_batch = controller.saved_batch_repo.save_batch("Weekly Follow-ups", [saved_action.id])
    controller.groups = [Group(name="Group A", group_id="G1")]
    controller.right_workspace = MagicMock()

    controller.handle_open_batch_runner()

    mock_modal.assert_called_once()
    _, kwargs = mock_modal.call_args
    assert [a.id for a in kwargs["actions"]] == [saved_action.id]
    assert kwargs["groups"] == controller.groups
    assert kwargs["on_run"] == controller._handle_run_batch
    assert [b.id for b in kwargs["saved_batches"]] == [saved_batch.id]
    assert kwargs["on_save_batch"] == controller._handle_save_batch
    assert kwargs["on_delete_batch"] == controller._handle_delete_batch


def test_handle_save_batch_persists_via_saved_batch_repo(tmp_path):
    controller = AppController.__new__(AppController)
    controller.saved_batch_repo = SavedBatchRepository(data_file=tmp_path / "saved_batches.json")

    saved = controller._handle_save_batch("Weekly Follow-ups", ["A1", "A2"])

    assert saved.name == "Weekly Follow-ups"
    assert saved.action_ids == ["A1", "A2"]
    assert [b.id for b in controller.saved_batch_repo.load_batches()] == [saved.id]


def test_handle_delete_batch_removes_via_saved_batch_repo(tmp_path):
    controller = AppController.__new__(AppController)
    controller.saved_batch_repo = SavedBatchRepository(data_file=tmp_path / "saved_batches.json")
    saved = controller.saved_batch_repo.save_batch("Weekly Follow-ups", ["A1"])

    controller._handle_delete_batch(saved.id)

    assert controller.saved_batch_repo.load_batches() == []


# --- StudentDataProvider wiring ---------------------------------------------

@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_student_data_provider_is_a_caching_playwright_provider(mock_ctk, mock_init_views, mock_refresh_caseload):
    """The composition root must wrap the real (slow, live) provider in the
    cache, not use it bare - see CachingStudentDataProvider's docstring for
    why a bare PlaywrightStudentDataProvider would make batch reviews
    unusably slow."""
    controller = AppController()

    assert isinstance(controller.student_data_provider, CachingStudentDataProvider)
    real = controller.student_data_provider._real_provider
    assert isinstance(real, PlaywrightStudentDataProvider)
    assert real.report_url == CASELOAD_APP_URL
    assert real.export_button_selector == EXPORT_BUTTON_SELECTOR


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch.object(PlaywrightStudentDataProvider, "get_students")
def test_refresh_caseload_at_startup_populates_the_cache(mock_get_students, mock_ctk, mock_init_views):
    """_refresh_caseload_at_startup runs for real here (not patched out) -
    only the live Playwright call underneath it is faked, so this proves
    the eager-fetch-on-launch wiring actually populates the cache during
    __init__, not just that the method exists."""
    jane = Student(salesforce_id="SF1", first_name="Jane", last_name="Doe", email="jane@example.test")
    mock_get_students.return_value = [jane]

    controller = AppController()

    # A second get_students() call must be served from cache, not trigger
    # a second live fetch - proves _refresh_caseload_at_startup actually
    # populated CachingStudentDataProvider's cache, not just called through.
    assert controller.student_data_provider.get_students() == [jane]
    mock_get_students.assert_called_once()


@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch.object(PlaywrightStudentDataProvider, "get_students", side_effect=RuntimeError("session expired"))
def test_refresh_caseload_at_startup_failure_does_not_crash_app_construction(
    mock_get_students, mock_ctk, mock_init_views
):
    """A failed fetch at startup (e.g. an expired session on first launch
    of the day) must be logged, not left to crash AppController() entirely -
    the professor should still get a usable app and can retry via Refresh
    Caseload once the session is fixed."""
    controller = AppController()  # must not raise

    assert controller.student_data_provider._cache is None


def test_handle_refresh_requested_shows_the_new_student_count_on_success():
    controller = AppController.__new__(AppController)
    controller.activity_logger = MagicMock()
    fake_provider = MagicMock()
    fake_provider.refresh.return_value = [MagicMock(), MagicMock()]
    controller.student_data_provider = fake_provider

    with patch("src.controllers.app_controller.messagebox.showinfo") as mock_showinfo:
        controller.handle_refresh_requested()

    fake_provider.refresh.assert_called_once()
    mock_showinfo.assert_called_once()
    assert "2" in mock_showinfo.call_args[0][1]


def test_handle_refresh_requested_shows_an_error_on_failure():
    controller = AppController.__new__(AppController)
    controller.activity_logger = MagicMock()
    fake_provider = MagicMock()
    fake_provider.refresh.side_effect = RuntimeError("session expired")
    controller.student_data_provider = fake_provider

    with patch("src.controllers.app_controller.messagebox.showerror") as mock_showerror:
        controller.handle_refresh_requested()

    mock_showerror.assert_called_once()
    assert "session expired" in mock_showerror.call_args[0][1]