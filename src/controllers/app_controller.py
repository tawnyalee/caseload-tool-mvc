from pathlib import Path
from typing import Dict, List, Optional
import customtkinter as ctk
import tkinter.messagebox as messagebox
from src.models.group import Group
from src.views.scenario_nav_panel import ScenarioNavPanel
from src.views.add_action_view import AddActionView
from src.services.group_repository import GroupRepository
from src.services.action_repository import ActionRepository
from src.models.enums import InteractionType
from src.services.template_repository import TemplateRepository
from src.services.saved_batch_repository import SavedBatchRepository
from src.models.email_template import EmailTemplate
from src.services.activity_logger import ActivityLogger, purge_old_logs
from src.services.student_data_provider import (
    CachingStudentDataProvider,
    FakeStudentDataProvider,
    PlaywrightStudentDataProvider,
)
from src.services.outlook_email_sender import OutlookEmailSender
from src.services import app_paths
from src.services.test_mode import RedirectingEmailSender, load_redirect_email
from src.services.text_sender import UnavailableTextSender
from src.services.note_writer import FakeNoteWriter, PlaywrightNoteWriter
from src.services import salesforce_browser_session
from src.services.salesforce_callbacks import (
    CASELOAD_APP_URL, EXPORT_BUTTON_SELECTOR, update_follow_up_fn, write_note_fn,
)
from src.services.outlook_signature_provider import LocalOutlookSignatureProvider
from src.services.action_runner import ActionRunner, RunControl
from src.services.background_worker import BackgroundWorker, UiDispatcher
from src.views.dashboard_view import DashboardView
from src.views.batch_run_modal import BatchRunModal
from src.views.review_send_modal import ReviewSendModal
from src.views.multi_review_send_modal import MultiReviewSendModal, ReviewItem as MultiReviewItem
from src.views.run_summary_modal import RunSummaryModal
from src.views.run_progress_modal import RunProgressModal
from src.views.help_view import HelpView
from src.services.run_report import batch_issue_lines, issue_lines


def _show_run_results(master, clean_title: str, issues_title: str, message: str, lines: List[str]) -> None:
    """End-of-run results: a plain info popup for a clean run, otherwise
    the scrollable RunSummaryModal listing every failed/skipped step by
    student. A module-level function, not a method, so tests that run real
    handler methods against a MagicMock controller still reach it."""
    if lines:
        RunSummaryModal(master, title=issues_title, message=message, issue_lines=lines)
    else:
        messagebox.showinfo(clean_title, message)


class PlaceholderView(ctk.CTkFrame):
    """A generic, reusable view for features still in development."""
    def __init__(self, master, message: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.label = ctk.CTkLabel(
            self, 
            text=message, 
            font=ctk.CTkFont(size=16, weight="bold"), 
            justify="center"
        )
        self.label.pack(expand=True)


class AppController:
    # None = the real per-user locations (app_paths.py). Class attributes
    # only so tests can point them elsewhere.
    LOG_DIR = None
    TEST_MODE_FILE = None

    # region Initialization
    def __init__(self) -> None:
        self.root: ctk.CTk = ctk.CTk()
        # Any error escaping a button/menu callback lands here instead of
        # vanishing into a console the packaged .exe doesn't have.
        self.root.report_callback_exception = self._on_unexpected_error

        # Sends, notes and caseload loads run on one background thread so
        # the window keeps responding (see background_worker.py). Only one
        # job at a time: _active_run is set while one is going.
        self.ui = UiDispatcher(self.root)
        self.worker = BackgroundWorker(dispatch=self.ui.call_soon)
        self._active_run: Optional[RunControl] = None
        self._progress_window: Optional[RunProgressModal] = None
        self.root.title("Caseload Management Tool")
        self.root.geometry("1100x650")

        # Initialize Repository Service
        # Initialize Repository Services
        self.group_repo = GroupRepository()
        self.action_repo = ActionRepository()
        self.template_repo = TemplateRepository()
        self.saved_batch_repo = SavedBatchRepository()
        # Before the logger opens today's file. Logs/screenshots can hold
        # student names, so nothing older than today is kept (see purge_old_logs).
        log_dir = self.LOG_DIR or app_paths.logs_dir()
        removed_count = purge_old_logs(log_dir, Path(log_dir) / "screenshots")
        # ui_callback is wired up in _init_views() once nav_panel exists
        self.activity_logger = ActivityLogger(log_dir=str(log_dir))
        if removed_count:
            self.activity_logger.log(f"Cleared {removed_count} log file(s)/screenshot(s) from previous days")

        # Fake/local implementations for now — real Salesforce/Cadence/Outlook
        # adapters will implement these same interfaces later without any
        # other code here needing to change.
        # Wrapped in CachingStudentDataProvider so the many call sites that
        # each independently call get_students() (a review dialog, EVERY
        # item in a batch review, running an action) share one fetch per
        # session instead of each triggering their own ~20s+ live browser
        # round trip - confirmed painfully slow without this. "Refresh
        # Caseload" (handle_refresh_requested) forces a new fetch; the
        # roster is also fetched once eagerly at startup, below.
        self.student_data_provider = CachingStudentDataProvider(
            PlaywrightStudentDataProvider(
                report_url=CASELOAD_APP_URL,
                export_button_selector=EXPORT_BUTTON_SELECTOR,
            )
        )
        # Test mode (test_mode.json in the data folder, see test_mode.py): every email goes
        # to one test address and notes skip Salesforce, so the real app can
        # be tried against the real roster without contacting any student.
        self.test_mode_file = self.TEST_MODE_FILE or app_paths.test_mode_file()
        self.test_mode_redirect = load_redirect_email(self.test_mode_file)
        self.test_mode = self.test_mode_redirect is not None

        # Real Outlook (Classic) sending - Outlook is only contacted on the
        # first send, so construction is safe even if it isn't set up.
        self.email_sender = OutlookEmailSender()
        if self.test_mode:
            self.email_sender = RedirectingEmailSender(self.email_sender, self.test_mode_redirect)
        # Not FakeTextSender: that one reports every text as sent. Until real
        # Mongoose texting exists, a text step must show as failed.
        self.text_sender = UnavailableTextSender()

        # Confirmed working end-to-end against production Salesforce (see
        # src/CLAUDE.md's Salesforce integration plan). Construction never
        # fails even when not logged in; write_note()/update_follow_up_note()
        # raise a clear "not logged in" / "login expired" error at call time
        # instead, which ActionRunner already catches and logs per student
        # like any other failure - so this is safe to wire in unconditionally.
        self.note_writer = PlaywrightNoteWriter(
            student_record_url_template=CASELOAD_APP_URL,
            write_note_fn=write_note_fn,
            update_follow_up_fn=update_follow_up_fn,
        )
        if self.test_mode:
            self.note_writer = FakeNoteWriter()
            self.activity_logger.log(
                f"TEST MODE ON - all email goes to {self.test_mode_redirect or '(no valid address - sends will fail)'}; "
                f"notes are not written to Salesforce. Delete {self.test_mode_file} to go live."
            )

        # Real, not fake — this just lists files under the local Outlook
        # signatures folder, so it works today without a full Outlook adapter.
        self.signature_provider = LocalOutlookSignatureProvider()
        self.action_runner = ActionRunner(
            student_provider=self.student_data_provider,
            email_sender=self.email_sender,
            text_sender=self.text_sender,
            note_writer=self.note_writer,
            template_repo=self.template_repo,
            activity_logger=self.activity_logger,
        )

        # Strongly typed references
        self.groups: List[Group] = []
        self.scenarios_raw: Dict[str, dict] = {}
        self.nav_panel: Optional[ScenarioNavPanel] = None
        self.right_workspace: Optional[ctk.CTkFrame] = None
        
        # Keeps track of whatever active view is showing on the right
        self.current_workspace_view: Optional[ctk.CTkFrame] = None

        # Set by _refresh_caseload_at_startup if login/loading failed, and
        # shown as a popup once the window exists (it doesn't yet, at that
        # point - which is why it used to go only to the log file).
        self._startup_problem: Optional[str] = None

        self._load_data()
        self._init_views()
        if self._startup_problem:
            self.root.after(300, lambda: messagebox.showwarning("Salesforce", self._startup_problem))
    # endregion

    def _reload_scenarios_dict(self) -> None:
        """Helper to reload actions from repository and convert list -> dict keyed by name."""
        if hasattr(self.action_repo, "load_actions"):
            actions_list = self.action_repo.load_actions()
            if isinstance(actions_list, list):
                self.scenarios_raw = {
                    (getattr(a, "name", None) or a.get("name")): a 
                    for a in actions_list 
                    if getattr(a, "name", None) or (isinstance(a, dict) and a.get("name"))
                }
            elif isinstance(actions_list, dict):
                self.scenarios_raw = actions_list
        else:
            self.scenarios_raw = {}

    # region Data Loading - loading groups and actions
    def _load_data(self) -> None:
        """Loads groups and actions from JSON repositories."""
        self.groups = self.group_repo.load_groups()

        # Guarantee a real, persisted "General" group always exists
        if not any(g.name == "General" for g in self.groups):
            general_group = self.group_repo.add_group("General")
            if general_group:
                self.groups.append(general_group)

        # Use helper to populate self.scenarios_raw as a Dictionary
        self._reload_scenarios_dict()
        self._refresh_caseload_at_startup()
    # endregion

    def _refresh_caseload_at_startup(self) -> None:
        """Every launch: open the Salesforce login window, then load the
        roster (the developer's explicit choice over a lazy first-use fetch
        - the roster changes throughout the day at the source). Nothing is
        remembered between launches, so this always asks to log in. A failure
        (window closed, login not finished) is logged and shown as a popup
        once the window is up, never a crash - the app still opens, and
        "Refresh Caseload" is the retry path.

        A separate method (not inlined in _load_data) specifically so tests
        that construct a real AppController can patch this out the same way
        they already patch _init_views, instead of every such test opening a
        real login window."""
        try:
            students = self._load_caseload_logging_in_if_needed()
            self.activity_logger.log(f"Caseload loaded at startup: {len(students)} students")
        except Exception as exc:
            self.activity_logger.log(f"[CASELOAD NOT LOADED AT STARTUP] {exc}")
            self._startup_problem = f"The caseload couldn't be loaded:\n\n{exc}"

    def _log_in_to_salesforce(self) -> None:
        """Opens the visible login window and waits for the professor to log
        in themselves. The session is kept in memory only (see
        salesforce_browser_session.py)."""
        from playwright.sync_api import sync_playwright

        self.activity_logger.log("Opening the Salesforce login window...")
        with sync_playwright() as playwright:
            salesforce_browser_session.log_in_interactively(
                playwright, target_url=CASELOAD_APP_URL, logged_in_selector=EXPORT_BUTTON_SELECTOR,
            )
        self.activity_logger.log("Logged in to Salesforce")

    def _load_caseload_logging_in_if_needed(self):
        """Refreshes the roster, opening the login window first if nobody has
        logged in yet this app session, or again if the login has expired."""
        if not salesforce_browser_session.has_session():
            self._log_in_to_salesforce()
        try:
            return self.student_data_provider.refresh()
        except salesforce_browser_session.SessionExpiredError:
            self.activity_logger.log("Salesforce login expired - asking to log in again")
            salesforce_browser_session.clear_session()
            self._log_in_to_salesforce()
            return self.student_data_provider.refresh()

    # region View Management
    def _init_views(self) -> None:
        # Packed first with side="top" so it spans the whole window above
        # both panels - impossible to miss while test mode is on.
        if self.test_mode:
            self.root.title("Caseload Management Tool — TEST MODE")
            target = self.test_mode_redirect or "NO VALID ADDRESS (sends will fail)"
            ctk.CTkLabel(
                self.root,
                text=f"🧪 TEST MODE — all email goes to {target}, notes are NOT written to Salesforce. "
                     f"Delete {self.test_mode_file} to go live.",
                fg_color="#e0b400", text_color="black", corner_radius=0,
                font=ctk.CTkFont(weight="bold"), height=32,
            ).pack(side="top", fill="x")

        # Left Side: Navigation Panel
        self.nav_panel = ScenarioNavPanel(
            master=self.root, 
            groups=self.groups, 
            scenarios_raw=self.scenarios_raw,
            width=350
        )
        self.nav_panel.pack(side="left", fill="y", padx=(10, 5), pady=10)
        # Through the dispatcher: log lines also come from the background
        # worker during a run, and Tk widgets may only be touched from the
        # UI thread.
        self.activity_logger.ui_callback = lambda message: self.ui.call_soon(self.nav_panel.write_log_message, message)

        # Right Side: The permanent Canvas Frame
        self.right_workspace = ctk.CTkFrame(self.root, fg_color="transparent")
        self.right_workspace.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        # Wire up the events
        self._wire_events()

        # Show the initial view on startup
        self.handle_dashboard_requested()

    def _wire_events(self) -> None:
        """Centralized place to wire up view callbacks to controller actions."""
        if self.nav_panel:
            # Wire up the Action Buttons
            self.nav_panel.on_add_action_requested = self.handle_add_action_clicked
            self.nav_panel.on_edit_requested = self.handle_edit_action
            
            # Wire up Run and Rename buttons
            self.nav_panel.on_run_requested = self.handle_run_action
            self.nav_panel.on_rename_requested = self.handle_rename_action
            
            # Wire up Settings and Help callbacks
            self.nav_panel.on_settings_requested = self.handle_settings_requested
            self.nav_panel.on_help_requested = self.handle_help_requested
            self.nav_panel.on_dashboard_requested = self.handle_dashboard_requested

            # Wire up Group management buttons
            self.nav_panel.on_add_group_requested = self.handle_add_group
            self.nav_panel.on_rename_group_requested = self.handle_rename_group
            self.nav_panel.on_delete_group_requested = self.handle_delete_group
            self.nav_panel.on_group_selected = self.handle_group_selected
            
            # Wire up Action Delete button
            self.nav_panel.on_delete_action_requested = self.handle_delete_action

            # Wire up top header utility links
            self.nav_panel.on_stop_requested = self.handle_stop_requested
            self.nav_panel.on_refresh_requested = self.handle_refresh_requested
            self.nav_panel.on_sync_ids_requested = self.handle_sync_ids_requested
            self.nav_panel.on_restart_browser_requested = self.handle_restart_browser_requested

    def switch_workspace_view(self, new_view_class, **kwargs) -> None:
        """Clears the right side completely and loads a brand new view."""
        if self.current_workspace_view is not None:
            self.current_workspace_view.destroy()

        self.current_workspace_view = new_view_class(master=self.right_workspace, **kwargs)
        self.current_workspace_view.pack(fill="both", expand=True)

    def show_default_roster(self) -> None:
        """Loads the initial Caseload Roster view."""
        self.switch_workspace_view(
            PlaceholderView, 
            message="[Caseload Roster View Goes Here]"
        )

    def handle_group_selected(self, group_name: str) -> None:
        """Clears the right-hand workspace when the group changes, confirming first if an
        open AddActionView would lose unsaved changes."""
        if isinstance(self.current_workspace_view, AddActionView):
            confirm = messagebox.askyesno(
                "Switch Group?",
                f"Switching to '{group_name}' will discard unsaved changes to this action.\n\n"
                f"Continue?"
            )
            if not confirm:
                if self.nav_panel:
                    self.nav_panel.revert_to_previous_group()
                return

        if self.nav_panel:
            self.nav_panel.confirm_group_change(group_name)

        self.switch_workspace_view(
            PlaceholderView,
            message=f"Group {group_name} is now selected. \nPlease select an action to work with."
        )
    # endregion

    # region Event Handlers
    def handle_edit_action(self, action_name: str) -> None:
        active_group = ""
        if hasattr(self, "nav_panel") and hasattr(self.nav_panel, "group_dropdown"):
            active_group = self.nav_panel.group_dropdown.get()

        # 1. Fetch real action data from scenarios_raw
        real_action_data = self.scenarios_raw.get(action_name, {})

        # 2. Convert model object to dictionary if necessary
        if hasattr(real_action_data, "__dict__"):
            real_action_data = real_action_data.__dict__

        # 3. Load the workspace view with real action data
        self.switch_workspace_view(
            AddActionView,
            controller=self,
            groups=self.groups,
            initial_group_name=active_group,
            action_data=real_action_data
        )

    def handle_add_action_clicked(self) -> None:
        """Loads the rich form configuration panel on the right side."""
        active_group = ""
        if hasattr(self, "nav_panel") and hasattr(self.nav_panel, "group_dropdown"):
            active_group = self.nav_panel.group_dropdown.get()

        self.switch_workspace_view(
            AddActionView,
            controller=self,
            groups=self.groups,
            initial_group_name=active_group
        )

    def handle_dashboard_requested(self) -> None:
        self.activity_logger.log("Dashboard opened")
        self.switch_workspace_view(DashboardView, controller=self)

    def handle_send_welcome_emails(self) -> None:
        if self._is_busy_and_told_user() or self._caseload_missing_and_told_user():
            return
        actions_by_id = {a.id: a for a in self.action_repo.load_actions()}
        eligible_groups = [g for g in self.groups if g.welcome_action_id and g.welcome_action_id in actions_by_id]
        review_items = [
            MultiReviewItem(
                key=group.id, label=f"{group.name} — {actions_by_id[group.welcome_action_id].name}",
                students=self.action_runner.get_matching_students(actions_by_id[group.welcome_action_id]),
            )
            for group in eligible_groups
        ]

        def _on_confirm(selections):
            self._run_in_background(
                "Sending Welcome Emails",
                lambda control: self.action_runner.run_welcome_emails(
                    self.groups, actions_by_id, included_ids_by_group_id=selections, control=control,
                ),
                on_finished=_show_results,
            )

        def _show_results(summary):
            message = (
                f"Welcome emails complete:\n\n"
                f"✅ Succeeded: {summary.succeeded}\n"
                f"❌ Failed: {summary.failed}\n"
                f"⏭ Skipped: {summary.skipped}\n\n"
                f"Full details are in the Live Application Log."
            )
            _show_run_results(
                self.right_workspace.winfo_toplevel(), "Welcome Emails Sent",
                "Welcome Emails — Review Needed", message, issue_lines(summary),
            )

        MultiReviewSendModal(
            master=self.right_workspace.winfo_toplevel(),
            title="Send Welcome Emails",
            items=review_items,
            on_confirm=_on_confirm,
        )

    def handle_send_ad_hoc_email(
        self,
        subject: str,
        body: str,
        signature: str = "",
        note_subject: str = "",
        note_body: str = "",
        follow_up_note: str = "",
    ) -> None:
        """Called directly by DashboardView's inline compose section (no
        modal - the email and note fields live on the dashboard itself).
        Opens the pre-send review dialog first; the actual send only
        happens if the professor confirms it there."""
        if self._is_busy_and_told_user() or self._caseload_missing_and_told_user():
            return
        students = self.action_runner.student_provider.get_students()

        def _on_confirm(selected_ids, reviewed_subject, reviewed_body):
            self._run_in_background(
                "Sending Email",
                lambda control: self.action_runner.send_ad_hoc_email(
                    reviewed_subject, reviewed_body, signature,
                    note_subject=note_subject, note_body=note_body, follow_up_note=follow_up_note,
                    included_student_ids=selected_ids, control=control,
                ),
                on_finished=_show_results,
            )

        def _show_results(summary):
            message = (
                f"Ad-hoc email complete:\n\n"
                f"✅ Succeeded: {summary.succeeded}\n"
                f"❌ Failed: {summary.failed}\n"
                f"⏭ Skipped: {summary.skipped}\n\n"
                f"Full details are in the Live Application Log."
            )
            _show_run_results(
                self.right_workspace.winfo_toplevel(), "Send Complete",
                "Send Complete — Review Needed", message, issue_lines(summary),
            )

        ReviewSendModal(
            master=self.right_workspace.winfo_toplevel(),
            title="Send Email to All Students",
            students=students,
            is_email=True,
            initial_subject=subject,
            initial_body=body,
            on_confirm=_on_confirm,
        )

    def handle_open_batch_runner(self) -> None:
        if self._is_busy_and_told_user():
            return
        main_win = self.right_workspace.winfo_toplevel()
        actions = self.action_repo.load_actions()
        BatchRunModal(
            master=main_win,
            actions=actions,
            groups=self.groups,
            on_run=self._handle_run_batch,
            saved_batches=self.saved_batch_repo.load_batches(),
            on_save_batch=self._handle_save_batch,
            on_delete_batch=self._handle_delete_batch,
        )

    def _handle_save_batch(self, name: str, action_ids: List[str]):
        return self.saved_batch_repo.save_batch(name, action_ids)

    def _handle_delete_batch(self, batch_id: str) -> None:
        self.saved_batch_repo.delete_batch(batch_id)

    def _handle_run_batch(self, actions, group_names) -> None:
        if self._is_busy_and_told_user() or self._caseload_missing_and_told_user():
            return
        items = list(zip(actions, group_names))
        review_items = [
            MultiReviewItem(
                key=str(i), label=f"{group_name} — {action.name}",
                students=self.action_runner.get_matching_students(action),
            )
            for i, (action, group_name) in enumerate(items)
        ]

        def _on_confirm(selections):
            included_ids_by_index = {int(key): ids for key, ids in selections.items()}
            self._run_in_background(
                "Running Batch",
                lambda control: self.action_runner.run_batch(
                    items, included_ids_by_index=included_ids_by_index, control=control,
                ),
                on_finished=_show_results,
            )

        def _show_results(batch_summary):
            lines = []
            for item in batch_summary.items:
                if item.error:
                    lines.append(f"⚠ {item.action_name} ({item.group_name}): ERROR — {item.error}")
                else:
                    lines.append(
                        f"• {item.action_name} ({item.group_name}): "
                        f"✅ {item.summary.succeeded}  ❌ {item.summary.failed}  ⏭ {item.summary.skipped}"
                    )

            message = (
                f"Batch run complete — {len(batch_summary.items)} action(s):\n\n"
                + "\n".join(lines)
                + f"\n\nCombined: ✅ {batch_summary.succeeded}  ❌ {batch_summary.failed}  "
                f"⏭ {batch_summary.skipped}\n\nFull details are in the Live Application Log."
            )
            _show_run_results(
                self.right_workspace.winfo_toplevel(), "Batch Run Complete",
                "Batch Run — Review Needed", message, batch_issue_lines(batch_summary),
            )

        MultiReviewSendModal(
            master=self.right_workspace.winfo_toplevel(),
            title="Run Batch",
            items=review_items,
            on_confirm=_on_confirm,
        )

    def handle_settings_requested(self) -> None:
        self.switch_workspace_view(
            PlaceholderView,
            message="⚙ Settings Panel\n\n[Settings Configuration View - Logic Coming Soon]"
        )

    def handle_help_requested(self) -> None:
        self.switch_workspace_view(HelpView)  # the professor guide - see help_view.py

    def handle_run_action(self, action_name: str) -> None:
        if self._is_busy_and_told_user() or self._caseload_missing_and_told_user():
            return
        action = self.scenarios_raw.get(action_name)
        if action is None or not hasattr(action, "id"):
            messagebox.showerror("Error", f"Could not find action '{action_name}' to run.")
            return

        active_group = ""
        if hasattr(self, "nav_panel") and hasattr(self.nav_panel, "group_dropdown"):
            active_group = self.nav_panel.group_dropdown.get()

        matches = self.action_runner.get_matching_students(action)
        template_body = ""
        if action.is_email and action.template_id:
            template = self.template_repo.get_by_id(action.template_id)
            template_body = template.body if template else ""

        def _on_confirm(selected_ids, reviewed_subject, reviewed_body):
            self._run_in_background(
                f"Running '{action_name}'",
                lambda control: self.action_runner.run(
                    action, group_name=active_group, included_student_ids=selected_ids,
                    email_subject_override=reviewed_subject if action.is_email else None,
                    email_body_override=reviewed_body if action.is_email else None,
                    control=control,
                ),
                on_finished=_show_results,
            )

        def _show_results(summary):
            message = (
                f"Run complete for '{action_name}':\n\n"
                f"✅ Succeeded: {summary.succeeded}\n"
                f"❌ Failed: {summary.failed}\n"
                f"⏭ Skipped: {summary.skipped}\n\n"
                f"Full details are in the Live Application Log."
            )
            _show_run_results(
                self.right_workspace.winfo_toplevel(), "Run Complete",
                "Run Complete — Review Needed", message, issue_lines(summary),
            )

        ReviewSendModal(
            master=self.right_workspace.winfo_toplevel(),
            title=f"Run '{action_name}'",
            students=matches,
            is_email=action.is_email,
            initial_subject=action.email_subject,
            initial_body=template_body,
            on_confirm=_on_confirm,
        )

    def handle_rename_action(self, old_name: str, new_name: str) -> None:
        """Handles the final save logic when an action is renamed inline."""
        if not new_name or old_name == new_name:
            return

        # 1. Update memory state for scenarios_raw
        if old_name in self.scenarios_raw:
            action_data = self.scenarios_raw.pop(old_name)
            if isinstance(action_data, dict):
                action_data["name"] = new_name
            elif hasattr(action_data, "name"):
                action_data.name = new_name
            self.scenarios_raw[new_name] = action_data

        # 2. Update group scenario lists
        for group in self.groups:
            if hasattr(group, "scenarios") and old_name in group.scenarios:
                idx = group.scenarios.index(old_name)
                group.scenarios[idx] = new_name

        self.group_repo.save_groups(self.groups)

        # 3. Persist via ActionRepository
        if hasattr(self.action_repo, "rename_action"):
            self.action_repo.rename_action(old_name, new_name)
        elif hasattr(self.action_repo, "save_scenarios"):
            self.action_repo.save_scenarios(self.scenarios_raw)

        # 4. Refresh UI State safely
        if self.nav_panel:
            self.nav_panel.refresh_data(self.groups, self.scenarios_raw)

        self.activity_logger.log(f"Renamed action '{old_name}' to '{new_name}'")

    def handle_add_group(self) -> None:
        main_win = self.right_workspace.winfo_toplevel()

        dialog = ctk.CTkToplevel(main_win)
        dialog.title("Group Manager")
        dialog.geometry("350x260")
        dialog.transient(main_win)
        dialog.grab_set()
        dialog.resizable(False, False)

        header_lbl = ctk.CTkLabel(
            dialog,
            text="Add New Group",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.pack(pady=(15, 10), padx=20, anchor="w")

        group_name_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Enter group name (e.g., Tier 1 Support)",
            width=310
        )
        group_name_entry.pack(pady=10, padx=20, fill="x")
        group_name_entry.focus()

        has_tasks_var = ctk.StringVar(value="off")
        has_tasks_checkbox = ctk.CTkCheckBox(
            dialog,
            text="This course has tasks",
            variable=has_tasks_var,
            onvalue="on",
            offvalue="off",
        )
        has_tasks_checkbox.pack(pady=(5, 5), padx=20, anchor="w")

        has_oa_var = ctk.StringVar(value="off")
        has_oa_checkbox = ctk.CTkCheckBox(
            dialog,
            text="This course has an objective assessment",
            variable=has_oa_var,
            onvalue="on",
            offvalue="off",
        )
        has_oa_checkbox.pack(pady=(0, 10), padx=20, anchor="w")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(15, 10), padx=20, fill="x")

        btn_cancel = ctk.CTkButton(
            btn_frame, 
            text="Cancel", 
            width=100, 
            fg_color="transparent", 
            border_width=1,
            text_color=("black", "white"),
            command=dialog.destroy
        )
        btn_cancel.pack(side="left")

        def save_new_group():
            entered_name = group_name_entry.get().strip()
            if entered_name:
                new_group = self.group_repo.add_group(
                    entered_name,
                    has_tasks=has_tasks_var.get() == "on",
                    has_objective_assessment=has_oa_var.get() == "on",
                )
                if new_group:
                    self.groups = self.group_repo.load_groups()
                    
                    if self.nav_panel:
                        self.nav_panel.groups = self.groups
                        
                        group_names = [g.name for g in self.groups]
                        self.nav_panel.group_dropdown.configure(values=group_names)
                        self.nav_panel.group_dropdown.set(new_group.name)

                        self.nav_panel.refresh_active_group_display(new_group.name)

                    self.activity_logger.log(f"Added group '{new_group.name}'")
                    dialog.destroy()
                else:
                    messagebox.showwarning(
                        "Duplicate Group",
                        f"A group named '{entered_name}' already exists."
                    )
            else:
                group_name_entry.configure(border_color="red")

        btn_save = ctk.CTkButton(
            btn_frame, 
            text="Save", 
            width=100,
            command=save_new_group
        )
        btn_save.pack(side="right")

    def handle_rename_group(self, group_name: str) -> None:
        """Opens the group editor — name plus has_tasks/has_objective_assessment,
        the only per-group settings the app has today."""
        if group_name == "General":
            messagebox.showwarning("Edit Group", "The default 'General' group cannot be edited.")
            return

        target_group = next((g for g in self.groups if g.name == group_name), None)
        if not target_group:
            messagebox.showerror("Error", f"Could not find group '{group_name}' to edit.")
            return

        main_win = self.right_workspace.winfo_toplevel()

        dialog = ctk.CTkToplevel(main_win)
        dialog.title("Group Manager")
        dialog.geometry("350x260")
        dialog.transient(main_win)
        dialog.grab_set()
        dialog.resizable(False, False)

        header_lbl = ctk.CTkLabel(
            dialog,
            text="Edit Group",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.pack(pady=(15, 10), padx=20, anchor="w")

        group_name_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Enter group name",
            width=310
        )
        group_name_entry.pack(pady=10, padx=20, fill="x")
        group_name_entry.insert(0, group_name)
        group_name_entry.focus()
        group_name_entry.select_range(0, 'end')

        has_tasks_var = ctk.StringVar(value="on" if target_group.has_tasks else "off")
        has_tasks_checkbox = ctk.CTkCheckBox(
            dialog,
            text="This course has tasks",
            variable=has_tasks_var,
            onvalue="on",
            offvalue="off",
        )
        has_tasks_checkbox.pack(pady=(5, 5), padx=20, anchor="w")

        has_oa_var = ctk.StringVar(value="on" if target_group.has_objective_assessment else "off")
        has_oa_checkbox = ctk.CTkCheckBox(
            dialog,
            text="This course has an objective assessment",
            variable=has_oa_var,
            onvalue="on",
            offvalue="off",
        )
        has_oa_checkbox.pack(pady=(0, 10), padx=20, anchor="w")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(15, 10), padx=20, fill="x")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            fg_color="transparent",
            border_width=1,
            text_color=("black", "white"),
            command=dialog.destroy
        )
        btn_cancel.pack(side="left")

        def save_edited_group():
            new_name = group_name_entry.get().strip()
            if not new_name:
                group_name_entry.configure(border_color="red")
                return

            target_group.name = new_name
            target_group.has_tasks = has_tasks_var.get() == "on"
            target_group.has_objective_assessment = has_oa_var.get() == "on"
            self.group_repo.save_groups(self.groups)

            if self.nav_panel:
                self.nav_panel.groups = self.groups
                group_names = [g.name for g in self.groups]
                self.nav_panel.group_dropdown.configure(values=group_names)
                self.nav_panel.group_dropdown.set(new_name)
                self.nav_panel.refresh_active_group_display(new_name)

            self.activity_logger.log(f"Edited group '{group_name}' (now '{new_name}')")
            dialog.destroy()

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Save",
            width=100,
            command=save_edited_group
        )
        btn_save.pack(side="right")

    def handle_delete_group(self, group_name: str) -> None:
        """Deletes a group and any actions assigned to it, after confirmation."""
        # Guard against deleting default/protected group
        if group_name == "General":
            messagebox.showwarning("Delete Group", "The default 'General' group cannot be deleted.")
            return

        target_group = next((g for g in self.groups if g.name == group_name), None)
        actions_in_group = (
            [a for a in self.action_repo.load_actions() if a.group_id == target_group.id]
            if target_group else []
        )

        warning = (
            f"❌ Are you sure you want to delete this group?\n\n"
            f"Group: {group_name}\n\n"
        )
        if actions_in_group:
            warning += (
                f"This will also permanently delete {len(actions_in_group)} "
                f"action(s) assigned to this group.\n\n"
            )
        warning += "This action cannot be undone!"

        confirm = messagebox.askokcancel("Delete Group Warning", warning)

        if confirm:
            success = self.group_repo.delete_group(group_name)
            if success:
                # Cascade: a deleted group's actions can't be reassigned to
                # another group without risking silent, confusing behavior,
                # so they're deleted along with it rather than orphaned.
                for action in actions_in_group:
                    self.action_repo.delete_action(action.id)
                    self.group_repo.clear_welcome_action_id(action.id)

                # Reload updated group/action data
                self.groups = self.group_repo.load_groups()
                self._reload_scenarios_dict()

                # Refresh Navigation Dropdown and View (falls back to
                # 'General' automatically since group_name is no longer
                # in the group list)
                if self.nav_panel:
                    self.nav_panel.refresh_data(self.groups, self.scenarios_raw)

                log_msg = f"Deleted group '{group_name}'"
                if actions_in_group:
                    log_msg += f" and {len(actions_in_group)} associated action(s)"
                self.activity_logger.log(log_msg)
                messagebox.showinfo("Success", f"Group '{group_name}' was successfully deleted.")
            else:
                messagebox.showerror("Error", f"Could not find group '{group_name}' to delete.")

    def save_action(self, action_data: dict, existing_action_names_by_id: Optional[Dict[str, str]] = None) -> bool:
        """
        Saves action data into JSON storage and manages group welcome email assignment.
        Returns True if saved successfully, False if cancelled by the user.
        """
        from src.models.action import Action

        action_id = action_data.get("id")
        action_name = action_data.get("name", "").strip()
        group_name = action_data.get("group_name")
        is_welcome_email = action_data.get("is_welcome_email", False)

        if not action_name:
            messagebox.showwarning("Validation Error", "Action name cannot be empty.")
            return False

        # 1. Manage Group Welcome Email Conflicts & Scenario Linking
        target_group = next((g for g in self.groups if g.name == group_name), None)

        if target_group:
            # Link action name to group scenarios list for UI rendering
            if action_name not in target_group.scenarios:
                target_group.scenarios.append(action_name)

            current_welcome_id = target_group.welcome_action_id

            if is_welcome_email:
                if current_welcome_id and current_welcome_id != action_id:
                    existing_name = "another action"
                    if existing_action_names_by_id and current_welcome_id in existing_action_names_by_id:
                        existing_name = f"'{existing_action_names_by_id[current_welcome_id]}'"

                    confirm = messagebox.askyesno(
                        "Replace Welcome Email?",
                        f"Group '{target_group.name}' already has {existing_name} designated as its welcome email.\n\n"
                        f"Do you want to replace it with this action?"
                    )

                    if not confirm:
                        self.activity_logger.log(f"Cancelled saving '{action_name}' — welcome email not replaced")
                        return False

                target_group.welcome_action_id = action_id
                self.activity_logger.log(f"Set '{action_name}' as the welcome email for group '{target_group.name}'")

            else:
                if current_welcome_id == action_id:
                    target_group.welcome_action_id = None
                    self.activity_logger.log(f"Cleared '{action_name}' as the welcome email for group '{target_group.name}'")

        # Save updated group so scenarios list persists
        self.group_repo.save_groups(self.groups)

        # 2. Build or Update the Action Model
        action_to_save = Action(
            action_id=action_id,
            name=action_name,
            group_id=target_group.id if target_group else "",
            filters=action_data.get("filters", []),
            is_email=action_data.get("is_email", False),
            is_text=action_data.get("is_text", False),
            template_id=action_data.get("template_id"),
            email_subject=action_data.get("email_subject", ""),
            email_signature=action_data.get("email_signature", ""),
            text_subject=action_data.get("text_subject", ""),
            text_body=action_data.get("text_body", ""),
            note_subject=action_data.get("note_subject", ""),
            note_body=action_data.get("note_body", ""),
            follow_up_note=action_data.get("follow_up_note", ""),
            interaction_type=(
                InteractionType(action_data.get("interaction_type"))
                if action_data.get("interaction_type")
                else None
            ),
        )

        # 3. Persist via ActionRepository
        self.action_repo.save_action(action_to_save)

        # 4. Refresh UI State & Keep Active Selection
        self.groups = self.group_repo.load_groups()
        self._reload_scenarios_dict()

        if self.nav_panel:
            active_group = self.nav_panel.group_dropdown.get()
            self.nav_panel.groups = self.groups
            self.nav_panel.scenarios_raw = self.scenarios_raw
            self.nav_panel.refresh_active_group_display(active_group)

        self.activity_logger.log(f"Saved action '{action_name}'")
        messagebox.showinfo("Success", "Action saved successfully!")
        return True

    def save_template(self, template_id: Optional[str], name: str, body: str) -> str:
        """
        Saves a template. If template_id is provided and the content changed from
        what's stored, asks the user whether to update it in place or save as a
        new template. Returns the id of the template that was actually saved.
        """
        existing = self.template_repo.get_by_id(template_id) if template_id else None

        if existing and existing.body == body and existing.name == name:
            # Nothing changed — no need to prompt, just confirm it's saved as-is.
            return existing.id

        if existing:
            update_in_place = messagebox.askyesno(
                "Update or Save as New?",
                f"You've modified '{existing.name}'.\n\n"
                f"Click Yes to update this template for everyone using it, "
                f"or No to save your changes as a brand new template instead."
            )
            if update_in_place:
                existing.name = name
                existing.body = body
                self.template_repo.save(existing)
                return existing.id
            else:
                new_template = EmailTemplate(name=name, body=body)
                self.template_repo.save(new_template)
                return new_template.id

        # No existing template — straightforward create
        new_template = EmailTemplate(name=name, body=body)
        self.template_repo.save(new_template)
        return new_template.id

    def handle_delete_action(self, action_name: str) -> None:
        """Deletes an action after user confirmation and updates the UI."""
        # 1. Fetch action objects list or dict
        actions = self.action_repo.load_actions()
        target_action = None

        if isinstance(actions, list):
            target_action = next((a for a in actions if getattr(a, "name", None) == action_name), None)
        elif isinstance(actions, dict):
            target_action = actions.get(action_name)

        # 2. Fallback check if not found directly in repo output
        action_id = None
        target_name = action_name

        if target_action:
            action_id = getattr(target_action, "id", None)
            target_name = getattr(target_action, "name", action_name)
        else:
            if isinstance(self.scenarios_raw, dict) and action_name in self.scenarios_raw:
                raw_item = self.scenarios_raw[action_name]
                action_id = getattr(raw_item, "id", None) if not isinstance(raw_item, dict) else raw_item.get("id")
            else:
                messagebox.showerror("Error", f"Could not find action '{action_name}' to delete.")
                return

        msg = (
            f"❌ Are you sure you want to delete this action?\n\n"
            f"Action: {target_name}\n"
            f"Action ID: {action_id if action_id else 'N/A'}\n\n"
            f"This action cannot be undone!"
        )

        confirm = messagebox.askokcancel("Delete Action Warning", msg)
        if confirm:
            # 1. Delete action from repo using ID or name
            delete_key = action_id if action_id else action_name
            if hasattr(self.action_repo, "delete_action"):
                self.action_repo.delete_action(delete_key)

            # 2. Clear welcome email association if present
            if action_id and hasattr(self.group_repo, "clear_welcome_action_id"):
                self.group_repo.clear_welcome_action_id(action_id)

            # 3. Remove action name from group scenarios
            for group in self.groups:
                if hasattr(group, "scenarios") and action_name in group.scenarios:
                    group.scenarios.remove(action_name)
            if hasattr(self.group_repo, "save_groups"):
                self.group_repo.save_groups(self.groups)

            # 4. Reload state & refresh UI safely
            self.groups = self.group_repo.load_groups()
            self._reload_scenarios_dict()

            if self.nav_panel:
                self.nav_panel.refresh_data(self.groups, self.scenarios_raw)

            self.activity_logger.log(f"Deleted action '{target_name}'")
            messagebox.showinfo("Success", f"Action '{target_name}' was successfully deleted.")

    def handle_stop_requested(self) -> None:
        """The nav panel's ⛔ STOP button - same as the progress window's
        Stop: finish the current student, then stop."""
        if self._active_run is None:
            messagebox.showinfo("Stop", "Nothing is running right now.")
            return
        self.activity_logger.log("⛔ Stop requested - finishing the current student, then stopping")
        if self._progress_window is not None:
            self._progress_window.request_stop()  # also calls the run's request_stop
        else:
            self._active_run.request_stop()

    def handle_refresh_requested(self) -> None:
        if self._is_busy_and_told_user():
            return
        self.activity_logger.log("Refresh Caseload clicked")

        def _done(students):
            self.activity_logger.log(f"Caseload refreshed: {len(students)} students")
            messagebox.showinfo("Refresh Caseload", f"↻ Caseload refreshed — {len(students)} students loaded.")

        def _failed(exc):
            self.activity_logger.log(f"[REFRESH FAILED] {exc}")
            messagebox.showerror("Refresh Failed", f"Couldn't refresh the caseload:\n\n{exc}")

        self._run_in_background(
            "Refreshing Caseload",
            lambda control: self._load_caseload_logging_in_if_needed(),
            on_finished=_done, on_failed=_failed, stoppable=False,
            status="Loading the caseload from Salesforce… (a login window may open)",
        )

    def handle_sync_ids_requested(self) -> None:
        self.activity_logger.log("Sync Texting IDs clicked")
        messagebox.showinfo(
            "Sync Texting IDs",
            "⬇ Syncing Texting IDs...\n\nDownloading the latest texting configurations from the database."
        )

    def handle_restart_browser_requested(self) -> None:
        self.activity_logger.log("Restart Browser clicked")
        confirm = messagebox.askyesno(
            "Restart Browser?",
            "↻ Would you like to restart the automation browser?\n\nThis will close any active browser sessions and launch a fresh instance."
        )
        if confirm:
            self.activity_logger.log("Restarting browser engine...")
    # endregion

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self.root.mainloop()

    def _on_close_requested(self) -> None:
        """Closing the window mid-run would cut the background run off
        partway through a student - confirm first."""
        if self._active_run is not None and not messagebox.askyesno(
            "A run is still going",
            "A run is still in progress. Quit anyway?\n\n"
            "The student being processed right now may be left half-done "
            "(e.g. emailed but no note). Press Stop and wait instead to finish cleanly.",
        ):
            return
        self.root.destroy()

    def _on_unexpected_error(self, exc_type, exc, tb) -> None:
        """Tk's hook for errors escaping any callback (a button that hits a
        bug, a dialog that can't open). Without it the click just silently
        does nothing in the .exe - found 2026-10-22 when Edit did nothing
        for an action whose filter needed the (not loaded) roster."""
        import traceback

        details = "".join(traceback.format_exception(exc_type, exc, tb))
        logger = getattr(self, "activity_logger", None)
        if logger:
            logger.log(f"[UNEXPECTED ERROR] {exc_type.__name__}: {exc}\n{details}")
        messagebox.showerror(
            "Something went wrong",
            f"{exc}\n\nThe details were saved to today's log.",
        )

    # region Background runs
    def _caseload_missing_and_told_user(self) -> bool:
        """True (after explaining) if the roster isn't loaded - e.g. the
        Salesforce login failed or was skipped at startup. Only RUNNING
        needs the roster; every window (editing groups/actions/templates)
        works without it, so a first session can be all setup."""
        if getattr(self.student_data_provider, "is_loaded", True):
            return False
        messagebox.showinfo(
            "Caseload not loaded",
            "The caseload isn't loaded yet, so there's no one to send to.\n\n"
            "Click \"Refresh Caseload\" to log in to Salesforce, then try again.",
        )
        return True

    def _is_busy_and_told_user(self) -> bool:
        """True (after telling the professor) if a run or refresh is already
        going - only one at a time."""
        if self._active_run is None:
            return False
        messagebox.showinfo(
            "Already running",
            "Something is already running. Wait for it to finish, or press Stop.",
        )
        return True

    def _run_in_background(
        self,
        title: str,
        work,
        on_finished,
        on_failed=None,
        stoppable: bool = True,
        status: str = "Starting…",
    ) -> None:
        """Runs work(control) on the background worker while a progress
        window shows how it's going, then calls on_finished(result) - or
        on_failed(exc), default an error popup - back on the UI thread."""
        if self._is_busy_and_told_user():
            return
        control = RunControl()
        window = RunProgressModal(self.root, title, on_stop=control.request_stop if stoppable else None)
        window.set_status(status)
        control.on_progress = lambda position, total, text: self.ui.call_soon(
            window.update_progress, position, total, text
        )
        self._active_run = control
        self._progress_window = window

        def _end():
            self._active_run = None
            self._progress_window = None
            window.close()

        def _finished(result):
            _end()
            on_finished(result)

        def _failed(exc):
            _end()
            self.activity_logger.log(f"[{title.upper()} FAILED] {exc}")
            if on_failed:
                on_failed(exc)
            else:
                messagebox.showerror(title, f"Something went wrong, and the run stopped:\n\n{exc}")

        self.worker.submit(lambda: work(control), on_done=_finished, on_error=_failed)
    # endregion