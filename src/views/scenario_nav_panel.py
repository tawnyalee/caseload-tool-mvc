# src/views/scenario_nav_panel.py
import customtkinter as ctk
from src.models.group import Group

class ScenarioNavPanel(ctk.CTkFrame):
    #region Initialization
    def __init__(self, master, groups: list[Group], scenarios_raw: dict, **kwargs):
        super().__init__(master, **kwargs)
        self.groups = groups
        self.scenarios_raw = scenarios_raw
        
        # --- Controller Callback Slots --- These set the buttons for the left-side nav
        self.on_stop_requested = None
        self.on_refresh_requested = None
        self.on_sync_ids_requested = None
        self.on_restart_browser_requested = None
        self.on_edit_requested = None
        self.on_run_requested = None
        self.on_add_action_requested = None
        self.on_settings_requested = None
        self.on_help_requested = None
        self.on_dashboard_requested = None
        self.on_rename_requested = None  # Rename Action
        self.on_add_group_requested = None
        self.on_rename_group_requested = None
        self.on_delete_group_requested = None
        self.on_delete_action_requested = None # Added for the ❌ action button
        self.on_group_selected = None  #  fires when the group dropdown selection changes
        self.group_names = [group.name for group in self.groups]
        self._setup_ui()
        
    #endregion

    #region Layout Setup
    def _setup_ui(self):
        """Builds the entire operational panel layout."""
        
        # 1. --- Live Operational Links ---
        self.sync_bar_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sync_bar_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.stop_link = ctk.CTkButton(
            self.sync_bar_frame, text="⛔ STOP Process", width=100,
            fg_color="transparent", text_color="#c0392b", hover=False,
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.on_stop_requested() if self.on_stop_requested else print("STOP clicked")
        )
        self.stop_link.pack(side="left", padx=(0, 10))

        self.refresh_link = ctk.CTkButton(
            self.sync_bar_frame, text="↻ Refresh Caseload", width=110,
            fg_color="transparent", text_color="#1f538d", hover=False,
            command=lambda: self.on_refresh_requested() if self.on_refresh_requested else print("Refresh clicked")
        )
        self.refresh_link.pack(side="left", padx=10)

        self.sync_ids_link = ctk.CTkButton(
            self.sync_bar_frame, text="⬇ Sync Texting IDs", width=110,
            fg_color="transparent", text_color="#1f538d", hover=False,
            command=lambda: self.on_sync_ids_requested() if self.on_sync_ids_requested else print("Sync IDs clicked")
        )
        self.sync_ids_link.pack(side="left", padx=10)

        self.browser_link = ctk.CTkButton(
            self.sync_bar_frame, text="↻ Restart Browser", width=110,
            fg_color="transparent", text_color="#1f538d", hover=False,
            command=lambda: self.on_restart_browser_requested() if self.on_restart_browser_requested else print("Browser restart clicked")
        )
        self.browser_link.pack(side="left", padx=10)

        self.separator = ctk.CTkFrame(self, height=2, fg_color=("#dbdbdb", "#2e2e2e"))
        self.separator.pack(fill="x", padx=10, pady=5)

        # 2. --- Groups Navigation ---
        self.label = ctk.CTkLabel(self, text="Scenario Groups", font=ctk.CTkFont(size=14, weight="bold"))
        self.label.pack(padx=10, pady=(5, 2), anchor="w")

        self.dropdown_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dropdown_frame.pack(fill="x", padx=10, pady=(0, 4))
        
        self.group_dropdown = ctk.CTkComboBox(self.dropdown_frame, values=self.group_names, command=self._on_group_selected)
        self.group_dropdown.pack(fill="x", expand=True)
        self.group_dropdown.set("General")
        self.active_group_name = "General"  # last CONFIRMED group (used to revert on cancel)

        self.crud_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.crud_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.add_group_btn = ctk.CTkButton(self.crud_frame, text="+ Add Group", width=90, command=self._add_group)
        self.add_group_btn.pack(side="left", padx=(0, 4))

        self.rename_group_btn = ctk.CTkButton(self.crud_frame, text="📝 Rename", width=90, command=self._rename_group)
        self.rename_group_btn.pack(side="left", padx=4)

        self.delete_group_btn = ctk.CTkButton(self.crud_frame, text="❌ Delete", width=90, command=self._delete_group)
        self.delete_group_btn.pack(side="left", padx=4)

        self.actions_header_label = ctk.CTkLabel(self, text="General - Actions", font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
        self.actions_header_label.pack(fill="x", padx=12, pady=(5, 2))

        # 3. --- Actions Table Container ---
        self.table_frame = ctk.CTkScrollableFrame(self, height=180)
        self.table_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(1, weight=0)
        self.table_frame.grid_columnconfigure(2, weight=0)
        self.table_frame.grid_columnconfigure(3, weight=0)
        self.table_frame.grid_columnconfigure(4, weight=0)

        self.action_controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_controls_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_add_action = ctk.CTkButton(self.action_controls_frame, text="+ Add Action", width=100, command=self._add_action)
        self.btn_add_action.pack(side="left")

        self._render_table("General")

        self.separator2 = ctk.CTkFrame(self, height=2, fg_color=("#dbdbdb", "#2e2e2e"))
        self.separator2.pack(fill="x", padx=10, pady=5)

        # 4. --- Live Log Console ---
        self.log_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.log_header_frame.pack(fill="x", padx=10, pady=(5, 2))
        
        self.log_label = ctk.CTkLabel(self.log_header_frame, text="Live Application Log", font=ctk.CTkFont(size=13, weight="bold"))
        self.log_label.pack(side="left")
        
        self.copy_log_btn = ctk.CTkButton(self.log_header_frame, text="📋 Copy Log", width=70, height=20, font=ctk.CTkFont(size=11), command=self._copy_log)
        self.copy_log_btn.pack(side="right")

        self.log_textbox = ctk.CTkTextbox(self, height=100, state="disabled", wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.pack(fill="both", expand=False, padx=10, pady=(0, 5))
        
        self.write_log_message("System initialized... Welcome!")

        # 5. --- Bottom Utility Links ---
        self.utility_frame = ctk.CTkFrame(self, height=35, fg_color="transparent")
        self.utility_frame.pack(side="bottom", fill="x", expand=False, padx=10, pady=(5, 10))
        self.utility_frame.pack_propagate(False)

        # Help on the far right
        self.help_btn = ctk.CTkButton(
            self.utility_frame, 
            text="❓ Help", 
            width=90, 
            fg_color="transparent", 
            text_color=("#1f538d", "#2cc98f"),
            hover_color=("#e0e0e0", "#2d2d2d"),
            command=self._on_help_clicked
        )
        self.help_btn.pack(side="right", padx=(5, 0))

        # Settings next to it (moving inward left)
        self.settings_btn = ctk.CTkButton(
            self.utility_frame, 
            text="⚙ Settings", 
            width=90, 
            fg_color="transparent", 
            text_color=("#1f538d", "#2cc98f"), 
            hover_color=("#e0e0e0", "#2d2d2d"),
            command=self._on_settings_clicked
        )
        self.settings_btn.pack(side="right", padx=5)

        # Dashboard next to Settings (moving inward left again)
        self.dashboard_btn = ctk.CTkButton(
            self.utility_frame,
            text="📊 Dashboard",
            width=100,
            fg_color="transparent",
            text_color=("#1f538d", "#2cc98f"),
            hover_color=("#e0e0e0", "#2d2d2d"),
            command=self._on_dashboard_clicked
        )
        self.dashboard_btn.pack(side="right", padx=5)
    #endregion

    def refresh_data(self, groups: list[Group], scenarios_raw: dict):
        """Updates internal state with fresh group/scenario data and re-renders the active table."""
        self.groups = groups
        self.scenarios_raw = scenarios_raw
        
        # 1. Update dropdown values list
        self.group_names = [group.name for group in self.groups]
        self.group_dropdown.configure(values=self.group_names)
        
        # 2. Preserve active selection (fallback to 'General' if selected group was deleted)
        current_selection = self.group_dropdown.get()
        if current_selection not in self.group_names:
            current_selection = "General"
            self.group_dropdown.set("General")
            self.actions_header_label.configure(text="General - Actions")

        # 3. Re-render the actions table for the selected group
        self._render_table(current_selection)

    #region Live Log Logic
    def write_log_message(self, message: str):
        """Allows external classes (like the Controller) to write safe log messages."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")

    def _copy_log(self):
        """Copies the log window text to the operating system clipboard and adds a status log."""
        log_content = self.log_textbox.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(log_content)
        
        # 1. Terminal print for development feedback
        print("[View] Log content copied to clipboard!")
        
        # 2. Sleek, inline feedback for the user right inside the app log
        self.write_log_message("[System] Log successfully copied to clipboard! 📋")
    #endregion

    #region Table Rendering Logic
    def _render_table(self, group_name: str):
        for widget in self.table_frame.winfo_children():
            widget.destroy()
                
        actions_to_show = []
        matched_group = next((g for g in self.groups if g.name == group_name), None)
        if matched_group:
            actions_to_show = list(matched_group.scenarios)

        # Fallback: catch any legacy actions saved before General was a real group
        if group_name == "General":
            assigned_actions = set()
            for g in self.groups:
                assigned_actions.update(g.scenarios)
            legacy_orphans = [name for name in self.scenarios_raw.keys() if name not in assigned_actions]
            for name in legacy_orphans:
                if name not in actions_to_show:
                    actions_to_show.append(name)

        for row_idx, action_name in enumerate(actions_to_show):
            # 1. Keep track of the label object
            lbl = ctk.CTkLabel(self.table_frame, text=action_name, anchor="w")
            lbl.grid(row=row_idx, column=0, padx=(10, 20), pady=5, sticky="ew")
                
            btn_run_action = ctk.CTkButton(self.table_frame, text="Run", width=60, command=lambda name=action_name: self._on_run_click(name))
            btn_run_action.grid(row=row_idx, column=1, padx=2, pady=5, sticky="e")

            btn_edit_action = ctk.CTkButton(self.table_frame, text="Edit", width=60, command=lambda name=action_name: self._on_edit_click(name))
            btn_edit_action.grid(row=row_idx, column=2, padx=2, pady=5, sticky="e")
                
            # 2. UPDATE THIS BUTTON: Pass the label and its coordinates to start inline renaming
            btn_rename_action = ctk.CTkButton(
                self.table_frame, 
                text="Rename", 
                width=60, 
                command=lambda name_lbl=lbl, r=row_idx, old_name=action_name: 
                    self._start_inline_rename(old_name, name_lbl, r, 0)
            )
            btn_rename_action.grid(row=row_idx, column=3, padx=2, pady=5, sticky="e")
                
            btn_delete_action = ctk.CTkButton(
                self.table_frame, text="❌", width=35, 
                fg_color="#8B0000", hover_color="#660000", 
                command=lambda name=action_name: self._on_delete_action_click(name)
            )
            btn_delete_action.grid(row=row_idx, column=4, padx=(2, 10), pady=5, sticky="e")

    def _start_inline_rename(self, old_name: str, name_label, row_index: int, col_index: int):
        """Swaps the label with an Entry box in the grid for inline renaming."""
        name_label.grid_forget()

        edit_entry = ctk.CTkEntry(self.table_frame, height=28)
        edit_entry.grid(row=row_index, column=col_index, padx=(10, 20), pady=5, sticky="ew")
        
        edit_entry.insert(0, old_name)
        edit_entry.focus()
        edit_entry.select_range(0, 'end')

        def save_inline_change(event=None):
            if not edit_entry.winfo_exists():
                return

            new_name = edit_entry.get().strip()
            
            # Unbind to prevent double-firing on destroy/focus loss
            edit_entry.unbind("<Return>")
            edit_entry.unbind("<FocusOut>")

            if new_name and new_name != old_name:
                if self.on_rename_requested:
                    self.on_rename_requested(old_name, new_name)
            else:
                # If name didn't change, manually restore entry/label without controller refresh
                if edit_entry.winfo_exists():
                    edit_entry.destroy()
                if name_label.winfo_exists():
                    name_label.grid(row=row_index, column=col_index, padx=(10, 20), pady=5, sticky="ew")

        # Bind events so pressing Enter or clicking away submits the rename
        edit_entry.bind("<Return>", save_inline_change)
        edit_entry.bind("<FocusOut>", save_inline_change)
    #endregion

    #region Event Callbacks
    def _on_settings_clicked(self):
        if self.on_settings_requested:
            self.on_settings_requested()

    def _on_dashboard_clicked(self):
        if self.on_dashboard_requested:
            self.on_dashboard_requested()

    def _on_help_clicked(self):
        if self.on_help_requested:
            self.on_help_requested()

    def _add_action(self):
        if self.on_add_action_requested:
            self.on_add_action_requested()

    def _on_run_click(self, action_name: str):
        if self.on_run_requested:
            self.on_run_requested(action_name)

    def _on_edit_click(self, action_name: str):
        if self.on_edit_requested:
            self.on_edit_requested(action_name)

    def _on_rename_click(self, action_name: str):
        if self.on_rename_requested:
            self.on_rename_requested(action_name)

    def _on_group_selected(self, selected_group_name: str):
        self.actions_header_label.configure(text=f"{selected_group_name} - Actions")
        self._render_table(selected_group_name)
        if self.on_group_selected:
            self.on_group_selected(selected_group_name)

    def confirm_group_change(self, group_name: str):
        """Called by the controller once a group switch is accepted (or didn't need confirming)."""
        self.active_group_name = group_name

    def revert_to_previous_group(self):
        """Called by the controller when the user cancels a group switch — restores prior state."""
        self.group_dropdown.set(self.active_group_name)
        self.actions_header_label.configure(text=f"{self.active_group_name} - Actions")
        self._render_table(self.active_group_name)

    def _add_group(self):
        if self.on_add_group_requested:
            self.on_add_group_requested()

    def _rename_group(self):
        # We grab the currently selected group from the dropdown to pass to the controller
        selected_group = self.group_dropdown.get()
        if self.on_rename_group_requested:
            self.on_rename_group_requested(selected_group)

    def _delete_group(self):
        selected_group = self.group_dropdown.get()
        if self.on_delete_group_requested:
            self.on_delete_group_requested(selected_group)

    def _on_delete_action_click(self, action_name: str):
        if self.on_delete_action_requested:
            self.on_delete_action_requested(action_name)
    #endregion
