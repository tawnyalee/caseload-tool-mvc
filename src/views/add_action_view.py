# src/views/add_action_view.py
import customtkinter as ctk
from src.views.template_editor_modal import TemplateEditorModal

class AddActionView(ctk.CTkFrame):
    def __init__(self, master=None, parent=None, controller=None, groups=None, initial_group_name="", action_data=None, **kwargs):
        # Prefer master, fallback to parent if passed
        container = master if master is not None else parent
        super().__init__(container, **kwargs)
        
        self.controller = controller
        self.groups = groups if groups is not None else []
        self.initial_group_name = initial_group_name
        self.action_data = action_data
        
        # Extract group names for dropdown values
        self.group_names = [g.name if hasattr(g, 'name') else str(g) for g in self.groups]
        
        # Load existing templates map from controller if available
        self.template_repo = getattr(controller, "template_repo", None)

        # Determine header title based on mode
        self.mode_title = "Edit Action" if self.action_data else "Add New Action"

        # Initialize UI State and Tracking Variables
        self.filter_rows = []
        self.send_email_var = ctk.StringVar(value="off")
        self.send_text_var = ctk.StringVar(value="off")
        self.create_note_var = ctk.StringVar(value="off")
        self.interaction_category_var = ctk.StringVar(value="single")

        # Build interface
        self._setup_ui()
        
        # Populate fields if editing an existing action
        if self.action_data:
            self.populate_fields(self.action_data)

        # Pack save controls frame at bottom
        self.controls_frame.pack(side="bottom", fill="x", padx=15, pady=(15, 30))

    # =========================================================================
    # UI SETUP
    # =========================================================================

    def _setup_ui(self):
        prefix = "✏️" if self.action_data else "➕"

        self.title_lbl = ctk.CTkLabel(
            self, 
            text=f"{prefix} {self.mode_title}", 
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        self.title_lbl.pack(fill="x", padx=15, pady=(10, 15))

        #initialize the variable to set an email template as the welcome email for the selected group
        self.is_welcome_email_var = ctk.StringVar(value="off")

        # --- Metadata Section ---
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

        # --- Group Dropdown Setup ---
        
        self.group_dropdown = ctk.CTkComboBox(meta_frame, values=self.group_names, width=220)
        self.group_dropdown.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="w")

        # Set dropdown value from action_data or initial_group_name
        selected_group = ""
        if self.action_data and isinstance(self.action_data, dict):
            selected_group = self.action_data.get("group_name", "")

        if not selected_group and self.initial_group_name:
            selected_group = self.initial_group_name

        if selected_group:
            self.group_dropdown.set(selected_group)

        # Action ID
        id_lbl = ctk.CTkLabel(meta_frame, text="Action ID (Auto)", font=ctk.CTkFont(weight="bold"))
        id_lbl.grid(row=0, column=2, padx=10, pady=(10, 2), sticky="w")
        self.id_display = ctk.CTkLabel(meta_frame, text="ACT-AUTO-TEMP", text_color="gray")
        self.id_display.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="w")

        # --- Dynamic Filters Header ---
        filter_header_frame = ctk.CTkFrame(meta_frame, fg_color="transparent")
        filter_header_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(10, 2), sticky="ew")
        
        filter_title = ctk.CTkLabel(filter_header_frame, text="Select Filters for Roster:", font=ctk.CTkFont(size=12, weight="bold"))
        filter_title.pack(side="left")

        self.btn_add_filter = ctk.CTkButton(
            filter_header_frame, 
            text="➕ Add Filter Rule", 
            width=110, 
            height=22, 
            font=ctk.CTkFont(size=11),
            command=self._add_filter_row
        )
        self.btn_add_filter.pack(side="right")

        # --- Scrollable Container ---
        self.scrollable_container = ctk.CTkScrollableFrame(self, orientation="vertical", fg_color="transparent")
        self.scrollable_container.pack(fill="both", expand=True, padx=15, pady=5)

        self.filters_container = ctk.CTkFrame(self.scrollable_container, fg_color="transparent")
        self.filters_container.pack(fill="x", padx=15, pady=(0, 15))

        # Initial filter row
        self._add_filter_row()

        # --- Channels Selector ---
        channels_frame = ctk.CTkFrame(self.scrollable_container)
        channels_frame.pack(fill="x", padx=15, pady=10)
        
        chan_title = ctk.CTkLabel(channels_frame, text="Select Communication Method(s):", font=ctk.CTkFont(weight="bold"))
        chan_title.pack(anchor="w", padx=10, pady=(10, 5))

        chk_row = ctk.CTkFrame(channels_frame, fg_color="transparent")
        chk_row.pack(fill="x", padx=10, pady=(0, 10))

        self.chk_email = ctk.CTkCheckBox(chk_row, text="Send Email", variable=self.send_email_var, onvalue="on", offvalue="off", command=self._toggle_email_section)
        self.chk_email.pack(side="left", padx=(0, 20))

        self.chk_text = ctk.CTkCheckBox(chk_row, text="Send Text", variable=self.send_text_var, onvalue="on", offvalue="off", command=self._toggle_text_section)
        self.chk_text.pack(side="left", padx=20)

        # --- Dynamic Channels Containers ---
        self.email_container = ctk.CTkFrame(
            self.scrollable_container, 
            border_width=1, 
            border_color=("gray70", "gray30")
        )
        self._build_email_ui()

        self.text_container = ctk.CTkFrame(
            self.scrollable_container, 
            border_width=1, 
            border_color=("gray70", "gray30")
        )
        self._build_text_ui()

        # --- Note Configuration ---
        self.note_container = ctk.CTkFrame(
            self.scrollable_container, 
            border_width=1, 
            border_color=("gray70", "gray30")
        )
        self.note_container.pack(fill="x", padx=5, pady=(5, 15))

        lbl = ctk.CTkLabel(self.note_container, text="📝 Note Details:", font=ctk.CTkFont(weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=5)

        self.interaction_type_var = ctk.StringVar(value="Email")
        interaction_lbl = ctk.CTkLabel(self.note_container, text="Interaction Type:")
        interaction_lbl.pack(anchor="w", padx=10, pady=(2, 0))

        self.interaction_menu = ctk.CTkOptionMenu(
            self.note_container,
            values=["Email", "Text", "Email & Text"],
            variable=self.interaction_type_var,
            width=220
        )
        self.interaction_menu.pack(anchor="w", padx=10, pady=(2, 5))

        lbl = ctk.CTkLabel(self.note_container, text="Enter Subject Line for Note:")
        lbl.pack(anchor="w", padx=10, pady=(10, 5))

        self.note_subject = ctk.CTkEntry(self.note_container, placeholder_text="Note Subject", width=320)
        self.note_subject.pack(anchor="w", padx=10, pady=2)

        lbl = ctk.CTkLabel(self.note_container, text="Enter Body of Note:")
        lbl.pack(anchor="w", padx=10, pady=(10, 5))

        self.note_body = ctk.CTkTextbox(self.note_container, height=60)
        self.note_body.pack(fill="x", padx=10, pady=(2, 5))

        lbl = ctk.CTkLabel(self.note_container, text="Enter Follow-up Note for Main Roster View:")
        lbl.pack(anchor="w", padx=10, pady=(10, 5))

        self.followup_note = ctk.CTkEntry(self.note_container, placeholder_text="Follow-up Note", width=320)
        self.followup_note.pack(anchor="w", padx=10, pady=(2, 10))

        # --- Bottom Controls Frame ---
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        self.save_btn = ctk.CTkButton(
            self.controls_frame,
            text="💾 Save Action", 
            height=40, 
            font=ctk.CTkFont(weight="bold"),
            command=self._on_save_clicked
        )
        self.save_btn.pack(side="right", padx=(5, 0))

    # =========================================================================
    # DATA LOADING & POPULATION
    # =========================================================================
    def populate_fields(self, data: dict) -> None:
        """Populates form values when editing an existing Action."""
        if not data:
            return

        # 1. Action Name
        if "name" in data:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, data["name"])
        elif "metadata" in data and "action_name" in data["metadata"]:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, data["metadata"]["action_name"])

        # 2. Group Name Selection
        group_to_select = data.get("group_name")
        if not group_to_select and "metadata" in data:
            group_to_select = data["metadata"].get("assigned_group")

        if group_to_select and group_to_select in self.group_names:
            self.group_dropdown.set(group_to_select)

        # 3. Action ID
        if "id" in data:
            self.id_display.configure(text=data["id"])

        # 4. Email Channel Setup
        email_config = data.get("email_config", {})
        if email_config or data.get("send_email"):
            self.send_email_var.set("on")
            self._toggle_email_section()
            
            if "subject" in email_config:
                self.email_subject.delete(0, "end")
                self.email_subject.insert(0, email_config["subject"])

            template_name = email_config.get("template_name") or email_config.get("body_template_selected")
            if template_name:
                current_values = list(self.email_body_dropdown.cget("values"))
                if template_name not in current_values:
                    current_values.append(template_name)
                    self.email_body_dropdown.configure(values=current_values)
                
                self.email_body_dropdown.set(template_name)

        # 5. Text Channel Setup
        text_config = data.get("text_config", {})
        if text_config or data.get("send_text"):
            self.send_text_var.set("on")
            self._toggle_text_section()
            if "subject" in text_config:
                self.text_subject.delete(0, "end")
                self.text_subject.insert(0, text_config["subject"])
            if "body" in text_config:
                self.text_body.delete("1.0", "end")
                self.text_body.insert("1.0", text_config["body"])

        # 6. Salesforce Note Setup
        note_config = data.get("note_config") or data.get("salesforce_note_config", {})
        if note_config or data.get("create_note"):
            if "subject" in note_config:
                self.note_subject.delete(0, "end")
                self.note_subject.insert(0, note_config["subject"])
            if "body" in note_config or "note_body" in note_config:
                body_val = note_config.get("body") or note_config.get("note_body", "")
                self.note_body.delete("1.0", "end")
                self.note_body.insert("1.0", body_val)

    def get_action_data(self) -> dict:
        """Gathers all current form field values into a dictionary."""
        return {
            "id": self.id_display.cget("text"),
            "name": self.name_entry.get(),
            "group_name": self.group_dropdown.get(),
            "send_email": self.send_email_var.get() == "on",
            "email_config": {
                "subject": self.email_subject.get(),
                "template_name": self.email_body_dropdown.get(),
            },
            "send_text": self.send_text_var.get() == "on",
            "text_config": {
                "subject": self.text_subject.get(),
                "body": self.text_body.get("1.0", "end-1c")
            },
            "note_config": {
                "subject": self.note_subject.get(),
                "body": self.note_body.get("1.0", "end-1c"),
                "interaction_type": self.interaction_type_var.get(),
                "followup_note": self.followup_note.get()
            }
        }

    # =========================================================================
    # DYNAMIC FILTER & UI SECTION HELPERS
    # =========================================================================
    def _add_filter_row(self):
        """Dynamically adds a filter rule row inside the filters container."""
        row_frame = ctk.CTkFrame(self.filters_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        field_dropdown = ctk.CTkComboBox(row_frame, values=["Lead Status", "State", "Account Type"], width=140)
        field_dropdown.pack(side="left", padx=(0, 5))

        op_dropdown = ctk.CTkComboBox(row_frame, values=["Equals", "Contains", "Not Equals"], width=110)
        op_dropdown.pack(side="left", padx=5)

        val_entry = ctk.CTkEntry(row_frame, width=150, placeholder_text="Value...")
        val_entry.pack(side="left", padx=5)

        btn_remove = ctk.CTkButton(
            row_frame, 
            text="❌", 
            width=30, 
            fg_color="transparent", 
            hover_color="#331111",
            command=lambda rf=row_frame: self._remove_filter_row(rf)
        )
        btn_remove.pack(side="right", padx=(5, 0))

        self.filter_rows.append({
            "frame": row_frame,
            "field": field_dropdown,
            "operator": op_dropdown,
            "value": val_entry
        })

    def _remove_filter_row(self, row_frame):
        """Removes a filter rule row from UI and tracking list."""
        self.filter_rows = [r for r in self.filter_rows if r["frame"] != row_frame]
        row_frame.destroy()

    def _toggle_email_section(self):
        """Packs email section BEFORE note_container to keep notes at the bottom."""
        if self.send_email_var.get() == "on":
            self.email_container.pack(fill="x", padx=15, pady=5, before=self.note_container)
        else:
            self.email_container.pack_forget()

    def _toggle_text_section(self):
        """Packs text section BEFORE note_container to keep notes at the bottom."""
        if self.send_text_var.get() == "on":
            self.text_container.pack(fill="x", padx=15, pady=5, before=self.note_container)
        else:
            self.text_container.pack_forget()

    def _build_email_ui(self):
        lbl = ctk.CTkLabel(self.email_container, text="✉️ Email Details", font=ctk.CTkFont(weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=5)
        #checkbox to set email as welcome email
        self.chk_welcome_email = ctk.CTkCheckBox(
            self.email_container, 
            text="Is Group Welcome Email", 
            variable=self.is_welcome_email_var, 
            onvalue="on", 
            offvalue="off"
        )
        self.chk_welcome_email.pack(anchor="w", padx=10, pady=(5, 10))
        
        lbl = ctk.CTkLabel(self.email_container, text="Subject Line:")
        lbl.pack(anchor="w", padx=10, pady=5)

        self.email_subject = ctk.CTkEntry(self.email_container, placeholder_text="Email Subject", width=320)
        self.email_subject.pack(anchor="w", padx=10, pady=2)

        lbl = ctk.CTkLabel(self.email_container, text="Select or Create Template Below:")
        lbl.pack(anchor="w", padx=10, pady=5)

        template_row = ctk.CTkFrame(self.email_container, fg_color="transparent")
        template_row.pack(anchor="w", padx=10, pady=(2, 10))

        self.email_body_dropdown = ctk.CTkComboBox(template_row, values=["New / Custom Template"], width=220)
        self.email_body_dropdown.pack(side="left", padx=(0, 5))

        self.btn_new_template = ctk.CTkButton(template_row, text="➕ New", width=60, command=self._on_new_template_click)
        self.btn_new_template.pack(side="left", padx=2)

        self.btn_edit_template = ctk.CTkButton(template_row, text="✏️ Edit", width=60, command=self._on_edit_template_click)
        self.btn_edit_template.pack(side="left", padx=2)

        self.btn_delete_template = ctk.CTkButton(
            template_row, text="🗑️", width=35, fg_color="transparent", hover_color="#331111", command=self._on_delete_template_click
        )
        self.btn_delete_template.pack(side="left", padx=(2, 0))

        lbl = ctk.CTkLabel(self.email_container, text="Select Outlook Signature:")
        lbl.pack(anchor="w", padx=10, pady=(5, 0))

        self.email_signature_dropdown = ctk.CTkComboBox(
            self.email_container, 
            values=["Default Outlook Signature", "None", "Custom Signature 1"],
            width=220
        )
        self.email_signature_dropdown.pack(anchor="w", padx=10, pady=(2, 10))

    def _build_text_ui(self):
        lbl = ctk.CTkLabel(self.text_container, text="💬 Text Details:", font=ctk.CTkFont(weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=5)

        lbl = ctk.CTkLabel(self.text_container, text="Enter Text pySubject (required for Cadence Scheduling):")
        lbl.pack(anchor="w", padx=10, pady=5)

        self.text_subject = ctk.CTkEntry(self.text_container, placeholder_text="Text Subject", width=320)
        self.text_subject.pack(anchor="w", padx=10, pady=2)

        lbl = ctk.CTkLabel(self.text_container, text="Enter Text Message:")
        lbl.pack(anchor="w", padx=10, pady=5)

        self.text_body = ctk.CTkTextbox(self.text_container, height=60)
        self.text_body.pack(fill="x", padx=10, pady=(2, 10))

    # =========================================================================
    # EVENT HANDLERS & DIALOGS
    # =========================================================================
    def _on_save_clicked(self):
        """Callback executed when the save button is clicked."""
        import json
        form_data = self.get_action_data()
        json_output = json.dumps(form_data, indent=4)

    def _on_new_template_click(self):
        """Opens the template editor dialog for creating a new template."""
        TemplateEditorModal(
            master=self,
            on_save_callback=self._handle_template_saved
        )

    def _on_edit_template_click(self):
        """Opens the template editor dialog for the selected template."""
        selected_name = self.email_body_dropdown.get()
        
        if not selected_name or selected_name == "New / Custom Template":
            self._on_new_template_click()
            return

        body_content = ""

        if self.template_repo and hasattr(self.template_repo, "get_template_by_name"):
            template_obj = self.template_repo.get_template_by_name(selected_name)
            if template_obj:
                body_content = getattr(template_obj, "body", "")

        if not body_content and self.action_data:
            email_cfg = self.action_data.get("email_config", {})
            body_content = email_cfg.get("body", "")

        TemplateEditorModal(
            master=self,
            template_name=selected_name,
            template_body=body_content,
            on_save_callback=self._handle_template_saved
        )

    def _on_delete_template_click(self):
        """Deletes the selected template from repository and dropdown."""
        selected_name = self.email_body_dropdown.get()
        if not selected_name or selected_name == "New / Custom Template":
            return

        if self.template_repo and hasattr(self.template_repo, "delete_template"):
            self.template_repo.delete_template(selected_name)

        current_values = list(self.email_body_dropdown.cget("values"))
        if selected_name in current_values:
            current_values.remove(selected_name)
            self.email_body_dropdown.configure(values=current_values)

        self.email_body_dropdown.set("New / Custom Template")

    def _handle_template_saved(self, name: str, body: str):
        """Callback executed when a template is saved inside the editor."""
        if self.template_repo and hasattr(self.template_repo, "save_template"):
            self.template_repo.save_template(name, body)

        current_values = list(self.email_body_dropdown.cget("values"))
        if name not in current_values:
            current_values.append(name)
            self.email_body_dropdown.configure(values=current_values)

        self.email_body_dropdown.set(name)