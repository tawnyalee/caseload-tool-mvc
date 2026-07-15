# src/views/add_action_view.py
import customtkinter as ctk

class AddActionView(ctk.CTkScrollableFrame):
    def __init__(self, master, groups: list, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.groups = groups
        
        # Track active filter row elements: list of dicts containing widgets
        self.filter_rows = []
        
        # Track checkbox states for conditional channel rendering
        self.send_email_var = ctk.StringVar(value="off")
        self.send_text_var = ctk.StringVar(value="off")
        self.create_note_var = ctk.StringVar(value="off")
        
        self._setup_ui()

    def _setup_ui(self):
        # --- TITLE ---
        title_lbl = ctk.CTkLabel(
            self, 
            text="➕ Configure New Action", 
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        title_lbl.pack(fill="x", padx=15, pady=(10, 15))

        # =====================================================================
        # 1. METADATA & FILTERS SECTION
        # =====================================================================
        meta_frame = ctk.CTkFrame(self)
        meta_frame.pack(fill="x", padx=15, pady=10)
        
        meta_frame.columnconfigure(0, weight=1)
        meta_frame.columnconfigure(1, weight=1)
        meta_frame.columnconfigure(2, weight=1)

        # Action Name
        name_lbl = ctk.CTkLabel(meta_frame, text="Action Name", font=ctk.CTkFont(weight="bold"))
        name_lbl.grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")
        self.name_entry = ctk.CTkEntry(meta_frame, placeholder_text="e.g., Day 3 Follow Up")
        self.name_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Associated Group ID
        group_lbl = ctk.CTkLabel(meta_frame, text="Assign to Group", font=ctk.CTkFont(weight="bold"))
        group_lbl.grid(row=0, column=1, padx=10, pady=(10, 2), sticky="w")
        group_names = [g.name for g in self.groups]
        self.group_dropdown = ctk.CTkComboBox(meta_frame, values=group_names)
        self.group_dropdown.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="ew")

        # Action ID
        id_lbl = ctk.CTkLabel(meta_frame, text="Action ID (Auto)", font=ctk.CTkFont(weight="bold"))
        id_lbl.grid(row=0, column=2, padx=10, pady=(10, 2), sticky="w")
        self.id_display = ctk.CTkLabel(meta_frame, text="ACT-AUTO-TEMP", text_color="gray")
        self.id_display.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="w")

        # --- Dynamic Filters Area ---
        filter_header_frame = ctk.CTkFrame(meta_frame, fg_color="transparent")
        filter_header_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(10, 2), sticky="ew")
        
        filter_title = ctk.CTkLabel(filter_header_frame, text="Target Filter Rules (Salesforce)", font=ctk.CTkFont(size=12, weight="bold"))
        filter_title.pack(side="left")

        # Button to append a new filter line
        self.btn_add_filter = ctk.CTkButton(
            filter_header_frame, 
            text="➕ Add Filter Rule", 
            width=110, 
            height=22, 
            font=ctk.CTkFont(size=11),
            command=self._add_filter_row
        )
        self.btn_add_filter.pack(side="right")

        # Container where dynamic filter rows will live
        self.filters_container = ctk.CTkFrame(meta_frame, fg_color="transparent")
        self.filters_container.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 15), sticky="ew")

        # Seed with one initial filter row by default so the interface doesn't look empty
        self._add_filter_row()

        # =====================================================================
        # 2. CHANNELS SELECTOR
        # =====================================================================
        channels_frame = ctk.CTkFrame(self)
        channels_frame.pack(fill="x", padx=15, pady=10)
        
        chan_title = ctk.CTkLabel(channels_frame, text="Select Channels to Execute", font=ctk.CTkFont(weight="bold"))
        chan_title.pack(anchor="w", padx=10, pady=(10, 5))

        chk_row = ctk.CTkFrame(channels_frame, fg_color="transparent")
        chk_row.pack(fill="x", padx=10, pady=(0, 10))

        self.chk_email = ctk.CTkCheckBox(chk_row, text="Send Email", variable=self.send_email_var, onvalue="on", offvalue="off", command=self._toggle_email_section)
        self.chk_email.pack(side="left", padx=(0, 20))

        self.chk_text = ctk.CTkCheckBox(chk_row, text="Send Text/SMS", variable=self.send_text_var, onvalue="on", offvalue="off", command=self._toggle_text_section)
        self.chk_text.pack(side="left", padx=20)

        self.chk_note = ctk.CTkCheckBox(chk_row, text="Create Salesforce Note", variable=self.create_note_var, onvalue="on", offvalue="off", command=self._toggle_note_section)
        self.chk_note.pack(side="left", padx=20)

        # =====================================================================
        # 3. EMAIL TEMPLATE CONFIGURATION CONTAINER
        # =====================================================================
        self.email_container = ctk.CTkFrame(self)
        self._build_email_ui()

        # =====================================================================
        # 4. TEXT/SMS CONFIGURATION CONTAINER
        # =====================================================================
        self.text_container = ctk.CTkFrame(self)
        self._build_text_ui()

        # =====================================================================
        # 5. NOTE/TASK CONFIGURATION CONTAINER
        # =====================================================================
        self.note_container = ctk.CTkFrame(self)
        self._build_note_ui()

        # =====================================================================
        # 6. ACTION SAVE CONTROLS
        # =====================================================================
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(fill="x", padx=15, pady=(15, 30))

        self.save_btn = ctk.CTkButton(controls_frame, text="💾 Save Action Configuration", height=40, font=ctk.CTkFont(weight="bold"))
        self.save_btn.pack(side="right", padx=(5, 0))
        self.save_btn = ctk.CTkButton(
                    controls_frame, 
                    text="💾 Save Action Configuration", 
                    height=40, 
                    font=ctk.CTkFont(weight="bold"),
                    command=self._on_save_clicked
                )
        self.save_btn.pack(side="right", padx=(5, 0))

    def _on_save_clicked(self):
        """Callback executed when the save button is clicked."""
        import json
        # Pull the complete data mapping dictionary we built in Step 8
        form_data = self.get_action_data()
        
        # Format the mapping as a beautiful, scannable JSON text block
        json_output = json.dumps(form_data, indent=4)
        
        # Output directly to your developer terminal to confirm data pipeline is 100% complete
        print("\n=== 💾 ACTION CONFIGURATION PIPELINE COMPLETE ===")
        print(json_output)
        print("=================================================\n")
    # --- Dynamic Filters Handler ---
    def _add_filter_row(self):
        """Appends a brand new rule row to the filters container."""
        row_frame = ctk.CTkFrame(self.filters_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        # Mock fields
        mock_sf_fields = ["Status", "State", "CreatedDate", "Program__c", "Is_Active__c"]
        field_dropdown = ctk.CTkComboBox(row_frame, values=mock_sf_fields, width=120)
        field_dropdown.pack(side="left", padx=(0, 5))
        field_dropdown.set("Select Field")

        operator_dropdown = ctk.CTkComboBox(row_frame, values=["equals", "contains", "starts with", "is null"], width=100)
        operator_dropdown.pack(side="left", padx=5)
        operator_dropdown.set("Operator")

        value_entry = ctk.CTkEntry(row_frame, placeholder_text="Value to match...", width=150)
        value_entry.pack(side="left", fill="x", expand=True, padx=5)

        # Delete Row button (allows users to clear a specific row)
        btn_delete_row = ctk.CTkButton(
            row_frame, 
            text="❌", 
            width=30, 
            fg_color="#8B0000", 
            hover_color="#660000",
            command=lambda: self._remove_filter_row(row_frame)
        )
        btn_delete_row.pack(side="right", padx=(5, 0))

        # Store references so we can query values on save
        self.filter_rows.append({
            "frame": row_frame,
            "field": field_dropdown,
            "operator": operator_dropdown,
            "value": value_entry
        })

    def _remove_filter_row(self, row_frame):
        """Removes a filter row visually and clears it from our memory list."""
        # Find the entry in our tracker list
        row_to_remove = next((r for r in self.filter_rows if r["frame"] == row_frame), None)
        if row_to_remove:
            self.filter_rows.remove(row_to_remove)
            row_frame.destroy()

    # --- Container Builders ---
    def _build_email_ui(self):
        lbl = ctk.CTkLabel(self.email_container, text="📧 Email Configuration", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=(10, 5))

        # 1. Subject Line Field
        sub_lbl = ctk.CTkLabel(self.email_container, text="Subject Line:")
        sub_lbl.pack(anchor="w", padx=10, pady=(2, 0))
        self.email_subject = ctk.CTkEntry(self.email_container, placeholder_text="Enter email subject...")
        self.email_subject.pack(fill="x", padx=10, pady=(0, 10))

        # 2. Email Body Dropdown and Edit Button Row
        body_lbl = ctk.CTkLabel(self.email_container, text="Email Body Template:")
        body_lbl.pack(anchor="w", padx=10, pady=(2, 0))
        
        body_row = ctk.CTkFrame(self.email_container, fg_color="transparent")
        body_row.pack(fill="x", padx=10, pady=(0, 10))

        # We'll populate this with your system's existing email bodies/templates
        mock_templates = ["New / Custom Template", "Day 3 Welcome Email", "Missed Call Follow Up", "Academic Check-In"]
        self.email_body_dropdown = ctk.CTkComboBox(
            body_row, 
            values=mock_templates, 
            command=self._on_email_template_changed
        )
        self.email_body_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.email_body_dropdown.set("New / Custom Template")

        # Edit button to open the rich text editor dialog
        self.btn_edit_email_body = ctk.CTkButton(
            body_row, 
            text="✏️ Edit / New", 
            width=90, 
            fg_color="#27ae60", 
            hover_color="#219a52",
            command=self._open_email_editor_dialog
        )
        self.btn_edit_email_body.pack(side="right")

        # 3 & 4. Options Row: Outlook Signature Dropdown (Left) & CC Mentor Checkbox (Right)
        opt_row = ctk.CTkFrame(self.email_container, fg_color="transparent")
        opt_row.pack(fill="x", padx=10, pady=(0, 10))

        sig_lbl = ctk.CTkLabel(opt_row, text="Outlook Signature:")
        sig_lbl.pack(side="left", padx=(0, 5))
        self.email_sig_dropdown = ctk.CTkComboBox(opt_row, values=["None", "Professional Signature", "Short Signature"])
        self.email_sig_dropdown.pack(side="left", padx=5)

        self.cc_mentor_chk = ctk.CTkCheckBox(opt_row, text="CC Program Mentor")
        self.cc_mentor_chk.pack(side="right", padx=10)

    def _open_email_editor_dialog(self):
        """Opens a Toplevel dialog with a rich text/HTML editor simulation."""
        current_selection = self.email_body_dropdown.get()
        
        # 1. Create a modal-like pop-up window
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Email Body Editor - {current_selection}")
        dialog.geometry("600x450")
        dialog.grab_set()  # Focus all events on this window
        
        # Header Label
        lbl_title = ctk.CTkLabel(
            dialog, 
            text=f"Editing: {current_selection}", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        # 2. Toggle for Rich Text / HTML Mode
        html_mode_var = ctk.StringVar(value="off")
        
        def toggle_mode():
            if html_mode_var.get() == "on":
                lbl_mode.configure(text="💻 HTML Editor Mode Enabled (<p>, <br>, etc.)", text_color="#3498db")
            else:
                lbl_mode.configure(text="📝 Standard Text Editor Mode", text_color="gray")
                
        mode_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=5)
        
        chk_html = ctk.CTkCheckBox(
            mode_frame, 
            text="Advanced: Edit as HTML / Rich Text", 
            variable=html_mode_var,
            onvalue="on",
            offvalue="off",
            command=toggle_mode
        )
        chk_html.pack(side="left")
        
        lbl_mode = ctk.CTkLabel(mode_frame, text="📝 Standard Text Editor Mode", text_color="gray", font=ctk.CTkFont(size=11))
        lbl_mode.pack(side="right", padx=10)

        # 3. Text Area
        editor_text = ctk.CTkTextbox(dialog, height=250)
        editor_text.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Determine initial content
        if current_selection == "New / Custom Template":
            initial_content = ""
        else:
            # Mock loading of existing template content
            initial_content = f"--- Template Content for '{current_selection}' ---\n\nHello [Student Name],\n\nThis is a pre-configured message content block for the {current_selection}.\n\nBest regards,\n[Your Name]"
            
        editor_text.insert("1.0", initial_content)
        
        # 4. Action Buttons (Save / Cancel)
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(10, 15))
        
        def save_changes():
            # In a later step, we will wire this back to the Controller / Model
            updated_text = editor_text.get("1.0", "end-1c")
            print(f"[Debug] Saved text for {current_selection} (HTML={html_mode_var.get()}):\n{updated_text}")
            dialog.destroy()
            
        btn_save = ctk.CTkButton(btn_frame, text="✔️ Save changes", fg_color="#27ae60", hover_color="#219a52", command=save_changes)
        btn_save.pack(side="right", padx=(5, 0))
        
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", hover_color="#555555", command=dialog.destroy)
        btn_cancel.pack(side="right", padx=(0, 5))

    def _build_text_ui(self):
        lbl = ctk.CTkLabel(self.text_container, text="📱 Text/SMS Configuration", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=(10, 5))

        # 1. Subject Line Input (Required for tracking/restrictions)
        sub_lbl = ctk.CTkLabel(self.text_container, text="Subject Line:")
        sub_lbl.pack(anchor="w", padx=10, pady=(2, 0))
        self.text_subject = ctk.CTkEntry(self.text_container, placeholder_text="Enter tracking subject line...")
        self.text_subject.pack(fill="x", padx=10, pady=(0, 10))

        # 2. Text Message Body Input
        body_lbl = ctk.CTkLabel(self.text_container, text="Message Body:")
        body_lbl.pack(anchor="w", padx=10, pady=(2, 0))
        self.text_body = ctk.CTkTextbox(self.text_container, height=80)
        self.text_body.pack(fill="x", padx=10, pady=(0, 10))

    def _build_note_ui(self):
        lbl = ctk.CTkLabel(self.note_container, text="📝 Salesforce Note Configuration", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=(10, 5))

        # Define the two Salesforce interaction lists
        self.single_interactions = [
            "Email to Student", "Live Call", "Email from Student", "Video Call", 
            "Course Chatter Response", "Voicemail to Student", "Instant Message", 
            "Voicemail from Student", "Webinar Attendance Noted", "Admin Note", 
            "Mass Email", "Cohort Event"
        ]
        
        self.multiple_interactions = [
            "Live Call and Email to Student", "Email Exchange with Student", 
            "Voicemail and Email to Student", "Voicemail/Email and Text to Student", 
            "Voicemail to Student and Text to Student", "Video Call and Email to Student", 
            "Voicemail from Student and Email to Student", "Voicemail Full/Email to Student"
        ]

        # 1a. Radio Buttons for Single vs. Multiple Interactions
        radio_frame = ctk.CTkFrame(self.note_container, fg_color="transparent")
        radio_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        self.interaction_category_var = ctk.StringVar(value="single")
        
        r_single = ctk.CTkRadioButton(
            radio_frame, 
            text="Single Interaction", 
            variable=self.interaction_category_var, 
            value="single",
            command=self._on_interaction_category_changed
        )
        r_single.pack(side="left", padx=(0, 20))
        
        r_multiple = ctk.CTkRadioButton(
            radio_frame, 
            text="Multiple Interactions", 
            variable=self.interaction_category_var, 
            value="multiple",
            command=self._on_interaction_category_changed
        )
        r_multiple.pack(side="left", padx=20)

        # 1b. Interaction Type Dropdown Row
        row1 = ctk.CTkFrame(self.note_container, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(0, 5))

        type_lbl = ctk.CTkLabel(row1, text="Interaction Type:")
        type_lbl.pack(side="left", padx=(0, 5))
        
        # Initialize dropdown with the "Single" interaction list by default
        self.note_type_dropdown = ctk.CTkComboBox(
            row1, 
            values=self.single_interactions, 
            command=self._on_note_type_changed
        )
        self.note_type_dropdown.pack(side="left", padx=5)
        self.note_type_dropdown.set(self.single_interactions[0])

        # 2. Dynamic Checklist Frame (Packs directly below row1 when a Live Call option is selected)
        self.checklist_frame = ctk.CTkFrame(self.note_container, fg_color="transparent")
        self._build_live_call_checklist()

        # 3. Followup Note Input Field
        followup_lbl = ctk.CTkLabel(self.note_container, text="Followup Note Field:")
        followup_lbl.pack(anchor="w", padx=10, pady=(5, 0))
        self.followup_note_entry = ctk.CTkEntry(self.note_container, placeholder_text="Enter followup notes text to save...")
        self.followup_note_entry.pack(fill="x", padx=10, pady=(0, 10))

        # 4. Note Body with Text Formatting Toolkit
        body_lbl = ctk.CTkLabel(self.note_container, text="Note Body (Rich Text / Formatting Enabled):")
        body_lbl.pack(anchor="w", padx=10, pady=(5, 0))

        # Format Toolbar
        toolbar_frame = ctk.CTkFrame(self.note_container, fg_color="transparent", height=26)
        toolbar_frame.pack(fill="x", padx=10, pady=(0, 2))
        
        btn_bold = ctk.CTkButton(toolbar_frame, text="B", width=25, height=20, font=ctk.CTkFont(weight="bold"), 
                                 command=lambda: self.note_body.insert("insert", "**bold**"))
        btn_bold.pack(side="left", padx=2)
        
        btn_bullet = ctk.CTkButton(toolbar_frame, text="• List", width=45, height=20, font=ctk.CTkFont(size=11), 
                                   command=lambda: self.note_body.insert("insert", "\n* "))
        btn_bullet.pack(side="left", padx=2)

        # Note Body
        self.note_body = ctk.CTkTextbox(self.note_container, height=120)
        self.note_body.pack(fill="x", padx=10, pady=(0, 15))

    def _build_live_call_checklist(self):
        chk_title = ctk.CTkLabel(self.checklist_frame, text="Live Call Checklist (Salesforce Sync Fields):", font=ctk.CTkFont(size=11, weight="bold"))
        chk_title.pack(anchor="w", pady=(0, 5))

        self.cb_info_discussed = ctk.CTkCheckBox(self.checklist_frame, text="Course/Program Info Discussed")
        self.cb_info_discussed.pack(anchor="w", padx=10, pady=2)

        self.cb_info_requested = ctk.CTkCheckBox(self.checklist_frame, text="Course/Program Info Requested")
        self.cb_info_requested.pack(anchor="w", padx=10, pady=2)

        self.cb_goals_set = ctk.CTkCheckBox(self.checklist_frame, text="Set Academic Goals")
        self.cb_goals_set.pack(anchor="w", padx=10, pady=2)

        self.cb_learning_occurred = ctk.CTkCheckBox(self.checklist_frame, text="Student Learning Occurred")
        self.cb_learning_occurred.pack(anchor="w", padx=10, pady=2)

        self.cb_obstacles_covered = ctk.CTkCheckBox(self.checklist_frame, text="Personal obstacles/non-academic content covered")
        self.cb_obstacles_covered.pack(anchor="w", padx=10, pady=2)

    # --- Toggle Handlers ---
    def _toggle_email_section(self):
        if self.send_email_var.get() == "on":
            self.email_container.pack(fill="x", padx=15, pady=10, before=self.text_container)
        else:
            self.email_container.pack_forget()

    def _toggle_text_section(self):
        if self.send_text_var.get() == "on":
            self.text_container.pack(fill="x", padx=15, pady=10, before=self.note_container)
        else:
            self.text_container.pack_forget()

    def _toggle_note_section(self):
        if self.create_note_var.get() == "on":
            self.note_container.pack(fill="x", padx=15, pady=10, before=self.save_btn.master)
        else:
            self.note_container.pack_forget()

    def _on_interaction_category_changed(self):
        """Swaps the dropdown options based on the chosen category radio button."""
        category = self.interaction_category_var.get()
        
        if category == "single":
            self.note_type_dropdown.configure(values=self.single_interactions)
            self.note_type_dropdown.set(self.single_interactions[0])
            self._on_note_type_changed(self.single_interactions[0])
        else:
            self.note_type_dropdown.configure(values=self.multiple_interactions)
            self.note_type_dropdown.set(self.multiple_interactions[0])
            self._on_note_type_changed(self.multiple_interactions[0])

    def _on_note_type_changed(self, selected_type: str):
        """Packs or unpacks the checklist frame if either Live Call option is selected."""
        if selected_type in ["Live Call", "Live Call and Email to Student"]:
            # Inserts the checklist directly above the followup note input
            self.checklist_frame.pack(fill="x", padx=10, pady=(5, 10), before=self.followup_note_entry)
        else:
            self.checklist_frame.pack_forget()
    def get_action_data(self) -> dict:
        """Gathers every single input field on this form into a single dictionary."""
        # 1. Gather dynamic filter rules
        filters = []
        for row in self.filter_rows:
            filters.append({
                "field": row["field"].get(),
                "operator": row["operator"].get(),
                "value": row["value"].get()
            })

        # 2. Compile the full state payload
        data = {
            "metadata": {
                "action_name": self.name_entry.get(),
                "assigned_group": self.group_dropdown.get(),
                "filters": filters
            },
            "channels_enabled": {
                "email": self.send_email_var.get() == "on",
                "text": self.send_text_var.get() == "on",
                "note": self.create_note_var.get() == "on"
            },
            "email_config": {
                "subject": self.email_subject.get(),
                "body_template_selected": self.email_body_dropdown.get(),
                "signature": self.email_sig_dropdown.get(),
                "cc_mentor": self.cc_mentor_chk.get() == 1
            },
            "text_config": {
                "subject": self.text_subject.get(),
                "body": self.text_body.get("1.0", "end-1c")
            },
            "salesforce_note_config": {
                "category": self.interaction_category_var.get(),
                "interaction_type": self.note_type_dropdown.get(),
                "followup_note": self.followup_note_entry.get(),
                "note_body": self.note_body.get("1.0", "end-1c"),
                "live_call_checklist": {
                    "info_discussed": self.cb_info_discussed.get() == 1,
                    "info_requested": self.cb_info_requested.get() == 1,
                    "goals_set": self.cb_goals_set.get() == 1,
                    "learning_occurred": self.cb_learning_occurred.get() == 1,
                    "obstacles_covered": self.cb_obstacles_covered.get() == 1
                }
            }
        }
        return data

    def _on_email_template_changed(self, selected_template: str):
        """Pre-populates the Subject Line field based on the selected email template."""
        # Define mock subjects matching our templates
        subjects = {
            "New / Custom Template": "",
            "Day 3 Welcome Email": "Welcome to the Program! Your Day 3 Check-In",
            "Missed Call Follow Up": "Sorry I missed you! Let's connect soon",
            "Academic Check-In": "How are classes going? Academic Progress Update"
        }
        
        # Grab the appropriate subject and insert it
        new_subject = subjects.get(selected_template, "")
        self.email_subject.delete(0, "end")
        self.email_subject.insert(0, new_subject)
        
        print(f"[Debug] Template changed to '{selected_template}'. Subject line pre-populated.")