from typing import Dict, List, Optional
import customtkinter as ctk
import tkinter.messagebox as messagebox
from src.models.group import Group
from src.views.scenario_nav_panel import ScenarioNavPanel
from src.views.add_action_view import AddActionView
from src.services.group_repository import GroupRepository


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
        self.group_repo = GroupRepository()

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

    # region Data Loading - loading groups and actions
    def _load_data(self) -> None:
        """Loads groups from JSON repository."""
        self.groups = self.group_repo.load_groups()
        
        # If no groups exist yet, seed a default group so the UI isn't completely empty
        if not self.groups:
            default_group = self.group_repo.add_group("Active Cadence")
            if default_group:
                default_group.add_scenario("Day 3 Follow Up")
                self.group_repo.save_groups([default_group])
                self.groups = [default_group]

        self.scenarios_raw = {
            "Welcome Email": {"email": "Hello!", "text": ""},
            "Day 3 Follow Up": {"email": "Checking in", "text": "Hi!"},
        }
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

        # Right Side: The permanent Canvas Frame
        self.right_workspace = ctk.CTkFrame(self.root, fg_color="transparent")
        self.right_workspace.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        # Wire up the events
        self._wire_events()

        # Show the initial view on startup
        self.show_default_roster()

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

            # Wire up Group management buttons
            self.nav_panel.on_add_group_requested = self.handle_add_group
            self.nav_panel.on_rename_group_requested = self.handle_rename_group
            self.nav_panel.on_delete_group_requested = self.handle_delete_group
            
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
    # endregion

    # region Event Handlers
    def handle_edit_action(self, action_name: str) -> None:
        print(f"[Controller] Switching right panel to EDIT mode for: {action_name}")
    
        active_group = ""
        if hasattr(self, "nav_panel") and hasattr(self.nav_panel, "group_dropdown"):
            active_group = self.nav_panel.group_dropdown.get()

        dummy_action_data = {
            "metadata": {
                "action_name": action_name,
                "assigned_group": active_group if active_group else (self.groups[0].name if self.groups else ""),
                "filters": [
                    {"field": "Status", "operator": "equals", "value": "Active"},
                    {"field": "Program__c", "operator": "contains", "value": "Pathway"}
                ]
            },
            "channels_enabled": {
                "email": True,
                "text": True,
                "note": True
            },
            "email_config": {
                "subject": "Welcome to the Program! Your Day 3 Check-In",
                "body_template_selected": "Day 3 Welcome Email",
                "signature": "Professional Signature",
                "cc_mentor": True
            },
            "text_config": {
                "subject": "Day 3 SMS Check-in",
                "body": "Hey there! Just checking in on your Day 3 progress."
            },
            "salesforce_note_config": {
                "category": "single",
                "interaction_type": "Live Call",
                "followup_note": "Scheduled followup call for next Monday.",
                "subject": "Initial Live Discussion Note",
                "note_body": "Had a great discussion with student about course info and goals.",
                "live_call_checklist": {
                    "info_discussed": True,
                    "info_requested": False,
                    "goals_set": True,
                    "learning_occurred": True,
                    "obstacles_covered": False
                }
            }
        }
        
        self.switch_workspace_view(
            AddActionView,
            controller=self,
            groups=self.groups,
            initial_group_name=active_group,
            action_data=dummy_action_data
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
        print(f"[Controller] Run clicked for: {action_name}")
        self.switch_workspace_view(
            PlaceholderView,
            message=f"🚀 Run Action Panel\n\nExecuting: {action_name}\n[Running Logic Coming Soon]"
        )

    def handle_rename_action(self, old_name: str, new_name: str) -> None:
        """Handles the final save logic when an action is renamed inline."""
        print(f"[Controller] Action Renamed: '{old_name}' -> '{new_name}'")

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
                        
                        group_names = ["General"] + [g.name for g in self.groups]
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
                    group_names = ["General"] + [g.name for g in self.groups]
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
                    group_names = ["General"] + [g.name for g in self.groups]
                    self.nav_panel.group_dropdown.configure(values=group_names)
                    
                    # Switch selected group back to 'General' safely
                    self.nav_panel.group_dropdown.set("General")
                    self.nav_panel._on_group_selected("General")

                messagebox.showinfo("Success", f"Group '{group_name}' was successfully deleted.")
            else:
                messagebox.showerror("Error", f"Could not find group '{group_name}' to delete.")

    def save_action(self, action_data: dict, existing_action_names_by_id: Optional[Dict[str, str]] = None) -> bool:
        """
        Saves action data and manages group welcome email assignment.
        Returns True if saved successfully, False if cancelled by the user.
        """
        action_id = action_data.get("id")
        group_name = action_data.get("group_name")
        is_welcome_email = action_data.get("is_welcome_email", False)

        target_group = next((g for g in self.groups if g.name == group_name), None)

        if target_group:
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
                        print("[Controller] Save cancelled by user.")
                        return False

                target_group.welcome_action_id = action_id
                print(f"[Controller] Set group '{target_group.name}' welcome_action_id to '{action_id}'.")

            else:
                if current_welcome_id == action_id:
                    target_group.welcome_action_id = None
                    print(f"[Controller] Cleared welcome_action_id for group '{target_group.name}'.")

        print(f"[Controller] Successfully saved action: {action_data.get('name')}")
        return True

    def handle_delete_action(self, action_name: str) -> None:
        print(f"[Controller] Delete Action clicked for: {action_name}")
        mock_action_id = "ACT-1143"
        msg = f"❌ Are you sure you want to delete this action?\n\nAction: {action_name}\nAction ID: {mock_action_id}\n\nThis action cannot be undone!"
        confirm = messagebox.askokcancel("Delete Action Warning", msg)
        if confirm:
            print(f"[Controller] Confirmed deletion of action: {action_name}")

    def handle_stop_requested(self) -> None:
        """Emergency break: Alerts and halts active processes."""
        print("[Controller] ⛔ EMERGENCY STOP REQUESTED!")
        messagebox.showerror(
            "Emergency Stop",
            "⛔ Process Stopped!\n\nAll running automation streams have been immediately halted."
        )

    def handle_refresh_requested(self) -> None:
        print("[Controller] Refresh Caseload clicked")
        messagebox.showinfo(
            "Refresh Caseload",
            "↻ Refreshing Caseload...\n\nFetching the latest caseload rosters and syncing data views."
        )

    def handle_sync_ids_requested(self) -> None:
        print("[Controller] Sync Texting IDs clicked")
        messagebox.showinfo(
            "Sync Texting IDs",
            "⬇ Syncing Texting IDs...\n\nDownloading the latest texting configurations from the database."
        )

    def handle_restart_browser_requested(self) -> None:
        print("[Controller] Restart Browser clicked")
        confirm = messagebox.askyesno(
            "Restart Browser?",
            "↻ Would you like to restart the automation browser?\n\nThis will close any active browser sessions and launch a fresh instance."
        )
        if confirm:
            print("[Controller] Restarting browser engine...")
    # endregion

    def run(self) -> None:
        self.root.mainloop()