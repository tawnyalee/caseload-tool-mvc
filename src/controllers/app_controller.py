# src/controllers/app_controller.py
from typing import Dict, List, Optional
import customtkinter as ctk
from src.models.group import Group
from src.views.scenario_nav_panel import ScenarioNavPanel
import tkinter.messagebox as messagebox
from src.views.add_action_view import AddActionView

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
    #region Initialization
    def __init__(self) -> None:
        self.root: ctk.CTk = ctk.CTk()
        self.root.title("Caseload Management Tool")
        self.root.geometry("1100x650")

        # Strongly typed references
        self.groups: List[Group] = []
        self.scenarios_raw: Dict[str, dict] = {}
        self.nav_panel: Optional[ScenarioNavPanel] = None
        self.right_workspace: Optional[ctk.CTkFrame] = None
        
        # Keeps track of whatever active view is showing on the right
        self.current_workspace_view: Optional[ctk.CTkFrame] = None

        self._load_mock_data()
        self._init_views()
    #endregion

    #region Data Loading
    def _load_mock_data(self) -> None:
        group_1 = Group(name="Active Cadence")
        group_1.add_scenario("Day 3 Follow Up")
        self.groups = [group_1]
        self.scenarios_raw = {
            "Welcome Email": {"email": "Hello!", "text": ""},
            "Day 3 Follow Up": {"email": "Checking in", "text": "Hi!"},
        }
    #endregion

    #region View Management
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

        # 🔗 Wire up the events
        self._wire_events()

        # Show the initial view on startup
        self.show_default_roster()

    def _wire_events(self) -> None:
        """Centralized place to wire up view callbacks to controller actions."""
        if self.nav_panel:
            # Wire up the Action Buttons
            self.nav_panel.on_add_action_requested = self.handle_add_action_clicked
            self.nav_panel.on_edit_requested = self.handle_edit_action
            
            # Wire up our new Run and Rename buttons!
            self.nav_panel.on_run_requested = self.handle_run_action
            self.nav_panel.on_rename_requested = self.handle_rename_action
            
            # Wire up our Stop Button callback
            self.nav_panel.on_stop_requested = self.handle_stop_requested

            # Wire up the Settings and Help callbacks
            self.nav_panel.on_settings_requested = self.handle_settings_requested
            self.nav_panel.on_help_requested = self.handle_help_requested

            # Wire up Group management buttons
            self.nav_panel.on_add_group_requested = self.handle_add_group
            self.nav_panel.on_rename_group_requested = self.handle_rename_group
            self.nav_panel.on_delete_group_requested = self.handle_delete_group
            
            # Wire up the Action Delete button
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

        # Instantiate inside our permanent right_workspace container
        self.current_workspace_view = new_view_class(master=self.right_workspace, **kwargs)
        self.current_workspace_view.pack(fill="both", expand=True)

    def show_default_roster(self) -> None:
        """Loads the initial Caseload Roster view."""
        self.switch_workspace_view(
            PlaceholderView, 
            message="[Caseload Roster View Goes Here]"
        )
    #endregion

    #region Event Handlers
    def handle_edit_action(self, action_name: str) -> None:
        print(f"[Controller] Switching right panel to EDIT mode for: {action_name}")
        
        # Temporary test payload structured EXACTLY like AddActionView.populate_fields expects
        dummy_action_data = {
            "metadata": {
                "action_name": action_name,
                "assigned_group": self.groups[0].name if self.groups else "",
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
        
        # We pass controller=self directly here so AddActionView gets its reference safely!
        self.switch_workspace_view(
            AddActionView,
            controller=self,
            groups=self.groups,
            action_data=dummy_action_data
        )

    def handle_add_action_clicked(self) -> None:
        """Loads the rich form configuration panel on the right side."""
        print("[Controller] Loading Add Action Form View")
        
        # We switch the active workspace view to our newly created form
        # We explicitly pass controller=self so it matches our new constructor signature!
        self.switch_workspace_view(
            AddActionView,
            controller=self,
            groups=self.groups
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

    def handle_stop_requested(self) -> None:
        """Emergency break: Alerts and halts any active background tasks/automations."""
        print("[Controller] ⛔ EMERGENCY STOP REQUESTED! Halting active processes...")

    def handle_run_action(self, action_name: str) -> None:
        print(f"[Controller] Run clicked for: {action_name}")
        self.switch_workspace_view(
            PlaceholderView,
            message=f"🚀 Run Action Panel\n\nExecuting: {action_name}\n[Running Logic Coming Soon]"
        )

    def handle_rename_action(self, old_name: str, new_name: str) -> None:
        """Handles the final save logic when an action is renamed inline."""
        print(f"[Controller] Action Renamed: '{old_name}' -> '{new_name}'")
        
        # This is where your future saving/data manipulation logic will go!
        # e.g., self.model.rename_action(old_name, new_name)

    def handle_add_group(self) -> None:
        print("[Controller] Add Group clicked")
        import customtkinter as ctk

        # Dynamically find the root main window from the workspace we know exists
        main_win = self.right_workspace.winfo_toplevel()

        # 1. Create the top-level pop-up window using the retrieved main window
        dialog = ctk.CTkToplevel(main_win)
        dialog.title("Group Manager")
        dialog.geometry("350x180")
        
        # Make the pop-up modal (keeps focus on this window until closed)
        dialog.transient(main_win)
        dialog.grab_set()
        dialog.resizable(False, False)

        # 2. Window Title/Header Label
        header_lbl = ctk.CTkLabel(
            dialog, 
            text="Add New Group", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.pack(pady=(15, 10), padx=20, anchor="w")

        # 3. Text Entry for Group Name
        group_name_entry = ctk.CTkEntry(
            dialog, 
            placeholder_text="Enter group name (e.g., Tier 1 Support)",
            width=310
        )
        group_name_entry.pack(pady=10, padx=20, fill="x")
        group_name_entry.focus()  # Auto-focus the text field for quick typing

        # Button Container (for horizontal layout)
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(15, 10), padx=20, fill="x")

        # 4. Cancel Button (Closes the window without doing anything)
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

        # 5. Save Button Stub (Prints to terminal for now, then closes)
        def stub_save():
            entered_name = group_name_entry.get().strip()
            if entered_name:
                print(f"[Controller Test] Save triggered for new group: '{entered_name}'")
                # When you're ready, the database saving logic goes here!
                dialog.destroy()
            else:
                # Turn the border red to show it's required
                group_name_entry.configure(border_color="red")

        btn_save = ctk.CTkButton(
            btn_frame, 
            text="Save", 
            width=100,
            command=stub_save
        )
        btn_save.pack(side="right")

    def handle_rename_group(self, group_name: str) -> None:
        print(f"[Controller] Rename Group clicked for: {group_name}")
        import customtkinter as ctk

        # Dynamically find the root main window from the workspace
        main_win = self.right_workspace.winfo_toplevel()

        # 1. Create the top-level pop-up window
        dialog = ctk.CTkToplevel(main_win)
        dialog.title("Group Manager")
        dialog.geometry("350x180")
        
        # Make the pop-up modal (keeps focus on this window until closed)
        dialog.transient(main_win)
        dialog.grab_set()
        dialog.resizable(False, False)

        # 2. Window Title/Header Label
        header_lbl = ctk.CTkLabel(
            dialog, 
            text="Rename Group", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.pack(pady=(15, 10), padx=20, anchor="w")

        # 3. Text Entry for Group Name
        group_name_entry = ctk.CTkEntry(
            dialog, 
            placeholder_text="Enter group name (e.g., Tier 1 Support)",
            width=310
        )
        group_name_entry.pack(pady=10, padx=20, fill="x")
        
        # Pre-populate with the current group name and select it
        group_name_entry.insert(0, group_name)
        group_name_entry.focus()  # Auto-focus the text field
        group_name_entry.select_range(0, 'end') # Highlight the text for easy replacement

        # Button Container (for horizontal layout)
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(15, 10), padx=20, fill="x")

        # 4. Cancel Button (Closes the window without doing anything)
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

        # 5. Save Button Stub (Prints both names to terminal, then closes)
        def stub_save():
            new_name = group_name_entry.get().strip()
            if new_name:
                print(f"[Controller Test] Rename triggered. Old: '{group_name}' -> New: '{new_name}'")
                # Future logic to update the data model and reload UI goes here!
                dialog.destroy()
            else:
                # Turn the border red to show it's required
                group_name_entry.configure(border_color="red")

        btn_save = ctk.CTkButton(
            btn_frame, 
            text="Save", 
            width=100,
            command=stub_save
        )
        btn_save.pack(side="right")

    def handle_delete_group(self, group_name: str) -> None:
        print(f"[Controller] Delete Group clicked for: {group_name}")
        mock_group_id = "GRP-9082"
        # Using askokcancel for a true delete-confirmation experience
        confirm = messagebox.askokcancel(
            "Delete Group Warning",
            f"❌ Are you sure you want to delete this group?\n\nGroup: {group_name}\nGroup ID: {mock_group_id}\n\nThis action cannot be undone!"
        )
        if confirm:
            print(f"[Controller] Confirmed deletion of group: {group_name}")

    def handle_delete_action(self, action_name: str) -> None:
        print(f"[Controller] Delete Action clicked for: {action_name}")
        mock_action_id = "ACT-1143"
        confirm = messagebox.askokcancel(
            "Delete Action Warning",
            f"❌ Are you sure you want to delete this action?\n\nAction: {action_name}\nAction ID: {mock_action_id}\n\nThis action cannot be undone!"
        )
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
    #endregion

    def run(self) -> None:
        self.root.mainloop()