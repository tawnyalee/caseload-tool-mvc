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
from src.services.action_runner import RunControl
from unittest.mock import ANY
from src.services.note_writer import FakeNoteWriter, PlaywrightNoteWriter
from src.services.outlook_email_sender import OutlookEmailSender
from src.services.test_mode import RedirectingEmailSender, TestModeNoteWriter
from src.services.mongoose_text_sender import DRY_RUN, REVIEW, MongooseTextSender



def _runs_synchronously(controller):
    """Stand-in for the background worker in tests that drive a handler
    against a MagicMock controller: nothing is busy, and work runs right
    away on this thread so the test can check the result directly. The
    real threading is covered by test_background_worker.py."""
    controller._is_busy_and_told_user = lambda: False
    controller._caseload_missing_and_told_user = lambda: False

    def run_now(title, work, on_finished, on_failed=None, stoppable=True, status=""):
        try:
            result = work(RunControl())
        except Exception as exc:
            if on_failed is None:
                raise
            on_failed(exc)
            return
        on_finished(result)

    controller._run_in_background = run_now
    return controller

def test_handle_add_action_clicked_reads_nav_panel_group():
    # Arrange: Setup mock controller with nav_panel
    controller = _runs_synchronously(MagicMock())
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
    controller = _runs_synchronously(MagicMock())
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
        included_student_ids={"SF1", "SF2"}, control=ANY,
    )
    mock_showinfo.assert_called_once()


@patch("controllers.app_controller.RunSummaryModal")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_send_ad_hoc_email_shows_results_window_on_failures(mock_modal, mock_results):
    controller = _runs_synchronously(MagicMock())
    failed_summary = ActionRunSummary(
        results=[StepResult(student=MagicMock(), step_type="email", outcome="failed")]
    )
    controller.action_runner.send_ad_hoc_email.return_value = failed_summary
    controller.action_runner.student_provider.get_students.return_value = []

    handle_send = AppController.handle_send_ad_hoc_email.__get__(controller, AppController)
    handle_send(subject="Class Canceled", body="<p>No class today.</p>")

    _, kwargs = mock_modal.call_args
    kwargs["on_confirm"]({"SF1"}, "Class Canceled", "<p>No class today.</p>")

    mock_results.assert_called_once()
    assert len(mock_results.call_args.kwargs["issue_lines"]) == 1


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_run_action_opens_review_dialog_with_matches_then_runs_on_confirm(mock_modal, mock_showinfo):
    controller = _runs_synchronously(MagicMock())
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
        email_subject_override="Edited Subject", email_body_override="Edited body", control=ANY,
    )
    mock_showinfo.assert_called_once()


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.ReviewSendModal")
def test_handle_run_action_non_email_action_does_not_pass_content_overrides(mock_modal, mock_showinfo):
    controller = _runs_synchronously(MagicMock())
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
        email_subject_override=None, email_body_override=None, control=ANY,
    )


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_shows_showinfo_when_everything_succeeds(mock_modal, mock_showinfo):
    """_handle_run_batch no longer runs immediately - it opens the
    multi-item review dialog first (patched here for the same
    module-identity reason as the other modal-opening tests in this file)
    and only runs once its on_confirm callback fires."""
    controller = _runs_synchronously(MagicMock())
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
        [(action, "Group A")], included_ids_by_index={0: {"SF1"}}, control=ANY
    )
    mock_showinfo.assert_called_once()


@patch("controllers.app_controller.RunSummaryModal")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_shows_results_window_when_an_action_errors(mock_modal, mock_results):
    controller = _runs_synchronously(MagicMock())
    batch_summary = BatchRunSummary(items=[
        BatchItemResult(action_name="Broken", group_name="Group A", summary=ActionRunSummary(), error="boom"),
    ])
    controller.action_runner.run_batch.return_value = batch_summary

    handle_run_batch = AppController._handle_run_batch.__get__(controller, AppController)
    handle_run_batch([MagicMock()], ["Group A"])

    _, kwargs = mock_modal.call_args
    kwargs["on_confirm"]({"0": {"SF1"}})

    mock_results.assert_called_once()
    assert "Broken" in mock_results.call_args.kwargs["message"]
    assert any("boom" in line for line in mock_results.call_args.kwargs["issue_lines"])


@patch("controllers.app_controller.RunSummaryModal")
@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_shows_results_window_when_a_step_failed(mock_modal, mock_results):
    controller = _runs_synchronously(MagicMock())
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

    mock_results.assert_called_once()


@patch("controllers.app_controller.MultiReviewSendModal")
def test_handle_run_batch_builds_review_items_with_each_actions_matches(mock_modal):
    controller = _runs_synchronously(MagicMock())
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
    controller = _runs_synchronously(MagicMock())
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
        controller.groups, {"ACT-1": action}, included_ids_by_group_id={"G1": {"s1"}}, control=ANY
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
    controller = _runs_synchronously(AppController.__new__(AppController))
    controller.saved_batch_repo = SavedBatchRepository(data_file=tmp_path / "saved_batches.json")

    saved = controller._handle_save_batch("Weekly Follow-ups", ["A1", "A2"])

    assert saved.name == "Weekly Follow-ups"
    assert saved.action_ids == ["A1", "A2"]
    assert [b.id for b in controller.saved_batch_repo.load_batches()] == [saved.id]


def test_handle_delete_batch_removes_via_saved_batch_repo(tmp_path):
    controller = _runs_synchronously(AppController.__new__(AppController))
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


@patch.object(AppController, "_log_in_to_salesforce")  # never open a real login window
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch.object(PlaywrightStudentDataProvider, "get_students")
def test_refresh_caseload_at_startup_populates_the_cache(mock_get_students, mock_ctk, mock_init_views, mock_login):
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


@patch.object(AppController, "_log_in_to_salesforce")  # never open a real login window
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
@patch.object(PlaywrightStudentDataProvider, "get_students", side_effect=RuntimeError("session expired"))
def test_refresh_caseload_at_startup_failure_does_not_crash_app_construction(
    mock_get_students, mock_ctk, mock_init_views, mock_login
):
    """A failed fetch at startup (e.g. an expired session on first launch
    of the day) must be logged, not left to crash AppController() entirely -
    the professor should still get a usable app and can retry via Refresh
    Caseload once the session is fixed."""
    controller = AppController()  # must not raise

    assert controller.student_data_provider._cache is None


def test_handle_refresh_requested_shows_the_new_student_count_on_success():
    controller = _runs_synchronously(AppController.__new__(AppController))
    controller.activity_logger = MagicMock()
    controller._log_in_to_salesforce = MagicMock()  # never open a real login window
    fake_provider = MagicMock()
    fake_provider.refresh.return_value = [MagicMock(), MagicMock()]
    controller.student_data_provider = fake_provider

    with patch("src.controllers.app_controller.messagebox.showinfo") as mock_showinfo:
        controller.handle_refresh_requested()

    fake_provider.refresh.assert_called_once()
    mock_showinfo.assert_called_once()
    assert "2" in mock_showinfo.call_args[0][1]


def test_handle_refresh_requested_shows_an_error_on_failure():
    controller = _runs_synchronously(AppController.__new__(AppController))
    controller.activity_logger = MagicMock()
    controller._log_in_to_salesforce = MagicMock()  # never open a real login window
    fake_provider = MagicMock()
    fake_provider.refresh.side_effect = RuntimeError("session expired")
    controller.student_data_provider = fake_provider

    with patch("src.controllers.app_controller.messagebox.showerror") as mock_showerror:
        controller.handle_refresh_requested()

    mock_showerror.assert_called_once()
    assert "session expired" in mock_showerror.call_args[0][1]

# --- Email sender / test mode wiring ----------------------------------------

@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_without_test_mode_file_email_is_real_outlook_and_notes_are_real(mock_ctk, mock_init_views, mock_refresh, tmp_path):
    with patch.object(AppController, "TEST_MODE_FILE", tmp_path / "test_mode.json"):  # doesn't exist
        controller = AppController()

    assert controller.test_mode is False
    assert isinstance(controller.email_sender, OutlookEmailSender)
    assert isinstance(controller.note_writer, PlaywrightNoteWriter)
    assert controller.action_runner.email_sender is controller.email_sender
    # Live texts wait for the professor to click Schedule in Mongoose.
    assert isinstance(controller.text_sender, MongooseTextSender)
    assert controller.text_sender.mode == REVIEW


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_test_mode_file_redirects_email_and_fakes_notes(mock_ctk, mock_init_views, mock_refresh, tmp_path):
    test_mode_file = tmp_path / "test_mode.json"
    test_mode_file.write_text('{"redirect_email": "me@example.test"}', encoding="utf-8")
    with patch.object(AppController, "TEST_MODE_FILE", test_mode_file):
        controller = AppController()

    assert controller.test_mode is True
    assert isinstance(controller.email_sender, RedirectingEmailSender)
    assert controller.email_sender.redirect_to == "me@example.test"
    assert isinstance(controller.email_sender.inner, OutlookEmailSender)
    assert isinstance(controller.note_writer, TestModeNoteWriter)
    assert controller.action_runner.email_sender is controller.email_sender
    assert controller.action_runner.note_writer is controller.note_writer
    # Test mode never schedules a text: it fills each one in and throws it away.
    assert controller.text_sender.mode == DRY_RUN


# --- Salesforce login (in memory, asked for every launch) -------------------

from src.services import salesforce_browser_session as sbs


@patch.object(sbs, "has_session", return_value=False)
def test_loading_the_caseload_logs_in_first_when_nobody_has(mock_has_session):
    controller = _runs_synchronously(MagicMock())
    controller.student_data_provider.refresh.return_value = ["s1"]
    load = AppController._load_caseload_logging_in_if_needed.__get__(controller, AppController)

    assert load() == ["s1"]
    controller._log_in_to_salesforce.assert_called_once()


@patch.object(sbs, "has_session", return_value=True)
def test_loading_the_caseload_skips_login_when_already_logged_in(mock_has_session):
    controller = _runs_synchronously(MagicMock())
    controller.student_data_provider.refresh.return_value = ["s1"]
    load = AppController._load_caseload_logging_in_if_needed.__get__(controller, AppController)

    load()
    controller._log_in_to_salesforce.assert_not_called()


@patch.object(sbs, "clear_session")
@patch.object(sbs, "has_session", return_value=True)
def test_expired_login_asks_to_log_in_again_then_retries_once(mock_has_session, mock_clear):
    controller = _runs_synchronously(MagicMock())
    controller.student_data_provider.refresh.side_effect = [sbs.SessionExpiredError("expired"), ["s1"]]
    load = AppController._load_caseload_logging_in_if_needed.__get__(controller, AppController)

    assert load() == ["s1"]
    mock_clear.assert_called_once()
    controller._log_in_to_salesforce.assert_called_once()


def test_startup_failure_is_kept_for_a_popup_instead_of_only_the_log():
    controller = _runs_synchronously(MagicMock())
    controller._startup_problem = None
    controller._load_caseload_logging_in_if_needed.side_effect = RuntimeError("The Salesforce login window was closed before login finished.")
    startup = AppController._refresh_caseload_at_startup.__get__(controller, AppController)

    startup()  # must not raise - the app still opens

    assert "login window was closed" in controller._startup_problem


@patch("src.controllers.app_controller.messagebox.showinfo")
def test_refresh_caseload_button_logs_in_if_needed(mock_showinfo):
    controller = _runs_synchronously(MagicMock())
    controller._load_caseload_logging_in_if_needed.return_value = ["s1", "s2"]
    refresh = AppController.handle_refresh_requested.__get__(controller, AppController)

    refresh()

    controller._load_caseload_logging_in_if_needed.assert_called_once()
    assert "2 students" in mock_showinfo.call_args[0][1]


# --- Background runs: progress window, busy guard, Stop, quitting ---------

class _ImmediateWorker:
    """Runs submitted work right away on this thread (the real one uses a
    background thread - covered by test_background_worker.py)."""
    def submit(self, work, on_done, on_error):
        try:
            result = work()
        except Exception as exc:
            on_error(exc)
        else:
            on_done(result)


def _bare_controller():
    controller = AppController.__new__(AppController)
    controller.root = MagicMock()
    controller.ui = MagicMock()
    controller.ui.call_soon.side_effect = lambda fn, *args: fn(*args)
    controller.worker = _ImmediateWorker()
    controller.activity_logger = MagicMock()
    controller._active_run = None
    controller._progress_window = None
    return controller


@patch("controllers.app_controller.RunProgressModal")
def test_background_run_shows_progress_then_closes_it_and_delivers_the_result(mock_window_cls):
    controller = _bare_controller()
    seen = {}

    def work(control):
        seen["busy_during_work"] = controller._active_run is control
        control.report(1, 2, "Jane Doe")
        return "summary"

    controller._run_in_background("Run", work, on_finished=lambda r: seen.setdefault("result", r))

    window = mock_window_cls.return_value
    window.update_progress.assert_called_once_with(1, 2, "Jane Doe")
    window.close.assert_called_once()
    assert seen == {"busy_during_work": True, "result": "summary"}
    assert controller._active_run is None


@patch("controllers.app_controller.messagebox.showerror")
@patch("controllers.app_controller.RunProgressModal")
def test_background_run_failure_closes_progress_and_shows_the_error(mock_window_cls, mock_showerror):
    controller = _bare_controller()

    def work(control):
        raise RuntimeError("Outlook did not respond")

    controller._run_in_background("Run", work, on_finished=lambda r: None)

    mock_window_cls.return_value.close.assert_called_once()
    assert "Outlook did not respond" in mock_showerror.call_args[0][1]
    assert controller._active_run is None


@patch("controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.RunProgressModal")
def test_a_second_run_is_refused_while_one_is_going(mock_window_cls, mock_showinfo):
    controller = _bare_controller()
    controller._active_run = RunControl()  # something is already running
    work = MagicMock()

    controller._run_in_background("Run", work, on_finished=lambda r: None)

    work.assert_not_called()
    mock_window_cls.assert_not_called()
    assert "already running" in mock_showinfo.call_args[0][1]


@patch("controllers.app_controller.messagebox.showinfo")
def test_handlers_refuse_to_open_while_busy(mock_showinfo):
    controller = _bare_controller()
    controller._active_run = RunControl()
    controller.action_runner = MagicMock()

    AppController.handle_send_ad_hoc_email(controller, subject="S", body="B")

    controller.action_runner.student_provider.get_students.assert_not_called()
    mock_showinfo.assert_called_once()


@patch("controllers.app_controller.messagebox.showinfo")
def test_stop_button_with_nothing_running_just_says_so(mock_showinfo):
    controller = _bare_controller()
    AppController.handle_stop_requested(controller)
    assert "Nothing is running" in mock_showinfo.call_args[0][1]


def test_stop_button_stops_the_current_run_via_its_progress_window():
    controller = _bare_controller()
    controller._active_run = RunControl()
    controller._progress_window = MagicMock()

    AppController.handle_stop_requested(controller)

    controller._progress_window.request_stop.assert_called_once()


@patch("controllers.app_controller.messagebox.askyesno", return_value=False)
def test_closing_the_app_mid_run_asks_first_and_can_be_cancelled(mock_ask):
    controller = _bare_controller()
    controller._active_run = RunControl()

    AppController._on_close_requested(controller)

    mock_ask.assert_called_once()
    controller.root.destroy.assert_not_called()


@patch("controllers.app_controller.messagebox.askyesno")
def test_closing_the_app_when_idle_just_closes(mock_ask):
    controller = _bare_controller()
    AppController._on_close_requested(controller)
    mock_ask.assert_not_called()
    controller.root.destroy.assert_called_once()


# --- Safety net for errors behind buttons -----------------------------------

@patch("controllers.app_controller.messagebox.showerror")
def test_unexpected_callback_errors_are_logged_and_shown_not_silent(mock_showerror):
    controller = _bare_controller()
    try:
        raise RuntimeError('Not logged in to Salesforce. Click "Refresh Caseload" to log in.')
    except RuntimeError as exc:
        AppController._on_unexpected_error(controller, type(exc), exc, exc.__traceback__)

    logged = controller.activity_logger.log.call_args[0][0]
    assert logged.startswith("[UNEXPECTED ERROR] RuntimeError: Not logged in")
    assert "Traceback" in logged
    assert "Not logged in to Salesforce" in mock_showerror.call_args[0][1]


@patch.object(AppController, "_refresh_caseload_at_startup")
@patch.object(AppController, "_init_views")
@patch("src.controllers.app_controller.ctk.CTk")
def test_the_safety_net_is_installed_on_the_window(mock_ctk, mock_init_views, mock_refresh):
    controller = AppController()
    assert controller.root.report_callback_exception == controller._on_unexpected_error



# --- Only running needs the roster -------------------------------------------

@patch("controllers.app_controller.messagebox.showinfo")
def test_run_buttons_explain_when_the_caseload_is_not_loaded(mock_showinfo):
    controller = _bare_controller()
    controller.student_data_provider = MagicMock(is_loaded=False)
    controller.action_runner = MagicMock()

    AppController.handle_send_ad_hoc_email(controller, subject="S", body="B")

    controller.action_runner.student_provider.get_students.assert_not_called()
    assert "Refresh Caseload" in mock_showinfo.call_args[0][1]


@patch("controllers.app_controller.messagebox.showinfo")
def test_run_buttons_proceed_when_the_caseload_is_loaded(mock_showinfo):
    controller = _bare_controller()
    controller.student_data_provider = MagicMock(is_loaded=True)
    assert AppController._caseload_missing_and_told_user(controller) is False
    mock_showinfo.assert_not_called()


# --- Settings: course settings saved by group ID -------------------------------

@patch("controllers.app_controller.messagebox.showinfo")
def test_saving_course_settings_updates_groups_by_id_and_persists(mock_showinfo):
    controller = _bare_controller()
    d424 = Group(name="Capstone", group_id="G1")
    other = Group(name="Capstone", group_id="G2")  # same name - must not be touched
    controller.groups = [d424, other]
    controller.group_repo = MagicMock()

    AppController.handle_save_course_settings(controller, {"G1": {
        "is_course": True, "course_code": "D424", "has_tasks": True, "task_count": 5,
        "has_objective_assessment": True,
    }})

    assert (d424.is_course, d424.course_code, d424.task_count, d424.has_objective_assessment) == (True, "D424", 5, True)
    assert other.is_course is False
    controller.group_repo.save_groups.assert_called_once_with(controller.groups)


@patch("src.controllers.app_controller.messagebox.showinfo")
@patch("controllers.app_controller.ReviewSendModal")
def test_task_email_actions_review_only_the_student_list(mock_modal, mock_showinfo):
    controller = _runs_synchronously(MagicMock())
    action = Action(name="Next task", group_id="G1", is_email=True, use_task_emails=True, template_id="T1")
    controller.scenarios_raw = {"Next task": action}
    controller.action_runner.get_matching_students.return_value = ["s1"]
    controller.action_runner.run.return_value = ActionRunSummary()

    AppController.handle_run_action.__get__(controller, AppController)("Next task")
    _, kwargs = mock_modal.call_args
    assert kwargs["is_email"] is False  # nothing to edit - each student's email differs
    kwargs["on_confirm"]({"SF1"}, "ignored", "ignored")

    _, run_kwargs = controller.action_runner.run.call_args
    assert run_kwargs["email_subject_override"] is None and run_kwargs["email_body_override"] is None
