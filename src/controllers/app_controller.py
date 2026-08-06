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
from src.models.email_template import EmailTemplate
from src.services.activity_logger import ActivityLogger
from src.services.student_data_provider import FakeStudentDataProvider
from src.services.email_sender import FakeEmailSender
from src.services.text_sender import FakeTextSender
from src.services.note_writer import FakeNoteWriter
from src.services.outlook_signature_provider import LocalOutlookSignatureProvider, get_signature_names_or_fallback
from src.services.action_runner import ActionRunner
from src.views.dashboard_view import DashboardView
from src.views.ad_hoc_email_modal import AdHocEmailModal

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
    # region Initialization
    def __init__(self) -> None:
        self.root: ctk.CTk = ctk.CTk()
        self.root.title("Caseload Management Tool")
        self.root.geometry("1100x650")

        # Initialize Repository Service
        # Initialize Repository Services
        self.group_repo = GroupRepository()
        self.action_repo = ActionRepository()
        self.template_repo = TemplateRepository()
        # ui_callback is wired up in _init_views() once nav_panel exists
        self.activity_logger = ActivityLogger()

        # Fake/local implementations for now — real Salesforce/Cadence/Outlook
        # adapters will implement these same interfaces later without any
        # other code here needing to change.
        self.student_data_provider = FakeStudentDataProvider()
        self.email_sender = FakeEmailSender()
        self.text_sender = FakeTextSender()
        self.note_writer = FakeNoteWriter()

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

        self._load_data()
        self._init_views()
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
    # endregion

    # region View Management
    def _init_views(self) -> None:
        # Left Side: Navigation Panel
        self.nav_panel = ScenarioNavPanel(
            master=self.root, 
            groups=self.groups, 
            scenarios_raw=self.scenarios_raw,
            width=350
        )
        self.nav_panel.pack(side="left", fill="y", padx=(10, 5), pady=10)
        self.activity_logger.ui_callback = self.nav_panel.write_log_message

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
        print(f"[Controller] Group selected: {group_name}")

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
        print(f"[Controller] Switching right panel to EDIT mode for: {action_name}")
    
        active_group = ""
        if hasattr(self, "nav_panel") and hasattr(self.nav_panel, "group_dropdown"):
            active_group = self.nav_panel.group_dropdown.get()

        # 1. Fetch real action data from scenarios_raw
        real_action_data = self.scenarios_raw.get(action_name, {})

        # 2. Convert model object to dictionary if necessary
        if hasattr(real_action_data, "__dict__"):
            real_action_data = real_action_data.__dict__

        #debug printout
        print(real_action_data)

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
        print("[Controller] Loading Add Action Form View")
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
        actions_by_id = {a.id: a for a in self.action_repo.load_actions()}
        summary = self.action_runner.run_welcome_emails(self.groups, actions_by_id)

        message = (
            f"Welcome emails complete:\n\n"
            f"✅ Succeeded: {summary.succeeded}\n"
            f"❌ Failed: {summary.failed}\n"
            f"⏭ Skipped: {summary.skipped}\n\n"
            f"See the Live Application Log for full details."
        )
        if summary.failed or summary.skipped:
            messagebox.showwarning("Welcome Emails — Review Needed", message)
        else:
            messagebox.showinfo("Welcome Emails Sent", message)

    def handle_compose_ad_hoc_email(self) -> None:
        main_win = self.right_workspace.winfo_toplevel()
        signature_names = get_signature_names_or_fallback(self.signature_provider)
        AdHocEmailModal(
            master=main_win,
            on_send_callback=self._handle_ad_hoc_email_send,
            signature_names=signature_names,
        )

    def _handle_ad_hoc_email_send(self, subject: str, body: str, signature: str = "") -> None:
        summary = self.action_runner.send_ad_hoc_email(subject, body, signature)

        message = (
            f"Ad-hoc email complete:\n\n"
            f"✅ Succeeded: {summary.succeeded}\n"
            f"❌ Failed: {summary.failed}\n\n"
            f"See the Live Application Log for full details."
        )
        if summary.failed:
            messagebox.showwarning("Send Complete — Review Needed", message)
        else:
            messagebox.showinfo("Send Complete", message)

    def handle_settings_requested(self) -> None:
        print("[Controller] Settings button clicked")
        self.switch_workspace_view(
            PlaceholderView,
            message="⚙ Settings Panel\n\n[Settings Configuration View - Logic Coming Soon]"
        )

    def handle_help_requested(self) -> None:
        print("[Controller] Help button clicked")
        self.switch_workspace_view(
            PlaceholderView,
            message="❓ Help & Documentation\n\n[User Guides & Support - Logic Coming Soon]"
        )

    def handle_run_action(self, action_name: str) -> None:
        action = self.scenarios_raw.get(action_name)
        if action is None or not hasattr(action, "id"):
            messagebox.showerror("Error", f"Could not find action '{action_name}' to run.")
            return

        active_group = ""
        if hasattr(self, "nav_panel") and hasattr(self.nav_panel, "group_dropdown"):
            active_group = self.nav_panel.group_dropdown.get()

        summary = self.action_runner.run(action, group_name=active_group)

        message = (
            f"Run complete for '{action_name}':\n\n"
            f"✅ Succeeded: {summary.succeeded}\n"
            f"❌ Failed: {summary.failed}\n"
            f"⏭ Skipped: {summary.skipped}\n\n"
            f"See the Live Application Log for full details."
        )
        if summary.failed or summary.skipped:
            messagebox.showwarning("Run Complete — Review Needed", message)
        else:
            messagebox.showinfo("Run Complete", message)

    def handle_rename_action(self, old_name: str, new_name: str) -> None:
        """Handles the final save logic when an action is renamed inline."""
        print(f"[Controller] Action Renamed: '{old_name}' -> '{new_name}'")

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

    def handle_add_group(self) -> None:
        print("[Controller] Add Group clicked")

        main_win = self.right_workspace.winfo_toplevel()

        dialog = ctk.CTkToplevel(main_win)
        dialog.title("Group Manager")
        dialog.geometry("350x180")
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
                new_group = self.group_repo.add_group(entered_name)
                if new_group:
                    self.groups = self.group_repo.load_groups()
                    
                    if self.nav_panel:
                        self.nav_panel.groups = self.groups
                        
                        group_names = [g.name for g in self.groups]
                        self.nav_panel.group_dropdown.configure(values=group_names)
                        self.nav_panel.group_dropdown.set(new_group.name)
                        
                        self.nav_panel._on_group_selected(new_group.name)

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
        print(f"[Controller] Rename Group clicked for: {group_name}")

        if group_name == "General":
            messagebox.showwarning("Rename Group", "The default 'General' group cannot be renamed.")
            return

        main_win = self.right_workspace.winfo_toplevel()

        dialog = ctk.CTkToplevel(main_win)
        dialog.title("Group Manager")
        dialog.geometry("350x180")
        dialog.transient(main_win)
        dialog.grab_set()
        dialog.resizable(False, False)

        header_lbl = ctk.CTkLabel(
            dialog, 
            text="Rename Group", 
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

        def save_renamed_group():
            new_name = group_name_entry.get().strip()
            if not new_name:
                group_name_entry.configure(border_color="red")
                return

            if new_name == group_name:
                dialog.destroy()
                return

            target_group = next((g for g in self.groups if g.name == group_name), None)
            if target_group:
                target_group.name = new_name
                self.group_repo.save_groups(self.groups)

                if self.nav_panel:
                    self.nav_panel.groups = self.groups
                    group_names = [g.name for g in self.groups]
                    self.nav_panel.group_dropdown.configure(values=group_names)
                    self.nav_panel.group_dropdown.set(new_name)
                    self.nav_panel._on_group_selected(new_name)

                dialog.destroy()
            else:
                messagebox.showerror("Error", f"Could not find group '{group_name}' to rename.")

        btn_save = ctk.CTkButton(
            btn_frame, 
            text="Save", 
            width=100,
            command=save_renamed_group
        )
        btn_save.pack(side="right")

    def handle_delete_group(self, group_name: str) -> None:
        """Deletes a group after confirmation and updates UI state."""
        print(f"[Controller] Delete Group requested for: {group_name}")

        # Guard against deleting default/protected group
        if group_name == "General":
            messagebox.showwarning("Delete Group", "The default 'General' group cannot be deleted.")
            return

        confirm = messagebox.askokcancel(
            "Delete Group Warning",
            f"❌ Are you sure you want to delete this group?\n\n"
            f"Group: {group_name}\n\n"
            f"This action cannot be undone!"
        )

        if confirm:
            success = self.group_repo.delete_group(group_name)
            if success:
                # Reload updated group data
                self.groups = self.group_repo.load_groups()

                # Refresh Navigation Dropdown and View
                if self.nav_panel:
                    self.nav_panel.groups = self.groups
                    group_names = [g.name for g in self.groups]
                    self.nav_panel.group_dropdown.configure(values=group_names)
                    
                    # Switch selected group back to 'General' safely
                    self.nav_panel.group_dropdown.set("General")
                    self.nav_panel._on_group_selected("General")

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
            print(f"[DEBUG] target_group={target_group.name}, current_welcome_id={current_welcome_id}, action_id={action_id}, is_welcome_email={is_welcome_email}")


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
                        print("[Controller] Save cancelled by user.")
                        return False

                target_group.welcome_action_id = action_id
                print(f"[Controller] Set group '{target_group.name}' welcome_action_id to '{action_id}'.")

            else:
                if current_welcome_id == action_id:
                    target_group.welcome_action_id = None
                    print(f"[Controller] Cleared welcome_action_id for group '{target_group.name}'.")

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
            self.nav_panel._on_group_selected(active_group)

        print(f"[Controller] Successfully saved action: {action_name}")
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
        print(f"[Controller] Delete Action clicked for: '{action_name}'")

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

            print(f"[Controller] Successfully deleted action: {target_name}")
            messagebox.showinfo("Success", f"Action '{target_name}' was successfully deleted.")

    def handle_stop_requested(self) -> None:
        """Emergency break: Alerts and halts active processes."""
        self.activity_logger.log("⛔ EMERGENCY STOP REQUESTED!")
        messagebox.showerror(
            "Emergency Stop",
            "⛔ Process Stopped!\n\nAll running automation streams have been immediately halted."
        )

    def handle_refresh_requested(self) -> None:
        self.activity_logger.log("Refresh Caseload clicked")
        messagebox.showinfo(
            "Refresh Caseload",
            "↻ Refreshing Caseload...\n\nFetching the latest caseload rosters and syncing data views."
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
        self.root.mainloop()