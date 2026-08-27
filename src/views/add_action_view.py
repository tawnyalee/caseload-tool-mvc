# src/views/add_action_view.py
import uuid
import customtkinter as ctk
from src.views.template_editor_modal import TemplateEditorModal
from src.views.filter_row import FilterRow
from src.views.date_picker import DatePickerEntry
from src.services.filterable_fields import FILTERABLE_FIELDS, Operator
from src.services.outlook_signature_provider import get_signature_names_or_fallback
import tkinter.messagebox as messagebox

class AddActionView(ctk.CTkFrame):
    def __init__(self, master=None, parent=None, controller=None, groups=None, initial_group_name="", action_data=None, **kwargs):
        # Prefer master, fallback to parent if passed
        container = master if master is not None else parent
        super().__init__(container, **kwargs)

        self.controller = controller
        self.groups = groups if groups is not None else []
        self.initial_group_name = initial_group_name
        self.action_data = action_data
        # This action's real, stable ID — generated now (not deferred to Save) so the
        # welcome-email conflict check can use a real ID even on a brand-new action.
        self.action_id = action_data.get("id") if action_data else str(uuid.uuid4())
        # The template this action was originally loaded with, kept stable across
        # dropdown changes so a delete of some OTHER template can restore this one.
        self.action_template_id = (action_data or {}).get("template_id")

        # Extract group names for dropdown values
        self.group_names = [g.name if hasattr(g, 'name') else str(g) for g in self.groups]
        
        # Load existing templates map from controller if available
        self.template_repo = getattr(controller, "template_repo", None)
        self.template_map = {}  # display name -> template id, rebuilt whenever the list changes

        # Real Outlook signature names from the controller, if available
        self.signature_provider = getattr(controller, "signature_provider", None)

        # Used to populate live-dropdown filter fields (e.g. course_code)
        # with whatever values actually exist in the current roster.
        self.student_data_provider = getattr(controller, "student_data_provider", None)

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
        self.id_display = ctk.CTkLabel(meta_frame, text=str(self.action_id), text_color="gray")
        self.id_display.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="w")

        # --- Dynamic Filters Header ---
        # Button sits directly under the title, left-aligned with it, and
        # above the filter list — a small hint label explains that
        # placement, since a "grows downward" list would normally push an
        # append button off-screen if it sat below the (scrollable) list.
        filter_header_frame = ctk.CTkFrame(meta_frame, fg_color="transparent")
        filter_header_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=(10, 2), sticky="ew")

        filter_title = ctk.CTkLabel(filter_header_frame, text="Select Filters for Roster:", font=ctk.CTkFont(size=12, weight="bold"))
        filter_title.pack(anchor="w")

        filter_controls_frame = ctk.CTkFrame(filter_header_frame, fg_color="transparent")
        filter_controls_frame.pack(fill="x", pady=(4, 0))

        self.btn_add_filter = ctk.CTkButton(
            filter_controls_frame,
            text="➕ Add Filter Rule",
            width=110,
            height=22,
            font=ctk.CTkFont(size=11),
            command=self._add_filter_row
        )
        self.btn_add_filter.pack(side="left")

        filter_hint = ctk.CTkLabel(
            filter_controls_frame,
            text="Click above to add a filter — it appears in the list below.",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        )
        filter_hint.pack(side="left", padx=(10, 0))

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
        self._refresh_template_dropdown()

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
    def populate_fields(self, data: dict) -> None:
        """Populates form values when editing an existing Action and auto-expands sections."""
        if not data:
            return

        # 1. Action Name
        name_val = data.get("name") or (data.get("metadata", {}).get("action_name", ""))
        if name_val:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, name_val)

        # 5. Populate Welcome Email Checkbox State
        is_welcome = False
        action_group_id = data.get("group_id")
        action_id = data.get("id")
        if action_group_id and action_id:
            matched_group = next((g for g in self.groups if g.id == action_group_id), None)
            if matched_group and matched_group.welcome_action_id == action_id:
                is_welcome = True
        self.is_welcome_email_var.set("on" if is_welcome else "off")

        # 3. Action ID
        if "id" in data:
            self.id_display.configure(text=str(data["id"]))

        # 4. Email Channel Setup & Auto-Expand
        email_config = data.get("email_config") or {
            "subject": data.get("email_subject", ""),
            "template_name": data.get("template_id", ""),
            "signature": data.get("email_signature", "")
        }
        
        has_email_data = bool(
            email_config.get("subject") or 
            email_config.get("template_name") or 
            email_config.get("body_template_selected")
        )
        
        # Check all possible email active flags (boolean True or string "on")
        should_send_email = (
            data.get("send_email") is True or 
            data.get("is_email") is True or 
            data.get("send_email") == "on" or 
            data.get("is_email") == "on" or 
            has_email_data
        )

        if should_send_email:
            self.send_email_var.set("on")
            self._toggle_email_section()  # Now send_email_var is guaranteed "on"
            self.update_idletasks()
                
            if "subject" in email_config and email_config["subject"]:
                self.email_subject.delete(0, "end")
                self.email_subject.insert(0, email_config["subject"])

            template_id = data.get("template_id")
            if template_id:
                self._refresh_template_dropdown(select_id=template_id)

            if "signature" in email_config and email_config["signature"]:
                self.email_signature_dropdown.set(email_config["signature"])
        else:
            self.send_email_var.set("off")
            self._toggle_email_section()

        # 6. Text Channel Setup & Auto-Expand
        text_config = data.get("text_config") or {
            "subject": data.get("text_subject", ""),
            "body": data.get("text_body", "")
        }
        
        has_text_data = bool(text_config.get("subject") or text_config.get("body"))
        
        should_send_text = (
            data.get("send_text") is True or 
            data.get("is_text") is True or 
            data.get("send_text") == "on" or 
            data.get("is_text") == "on" or 
            has_text_data
        )

        if should_send_text:
            self.send_text_var.set("on")
            self._toggle_text_section()  # Now send_text_var is guaranteed "on"
            self.update_idletasks()
                
            if "subject" in text_config and text_config["subject"]:
                self.text_subject.delete(0, "end")
                self.text_subject.insert(0, text_config["subject"])
                
            if "body" in text_config and text_config["body"]:
                self.text_body.delete("0.0", "end")
                self.text_body.insert("0.0", text_config["body"])
        else:
            self.send_text_var.set("off")
            self._toggle_text_section()

        # 7. Salesforce Note Setup
        note_config = data.get("note_config") or data.get("salesforce_note_config") or {
            "subject": data.get("note_subject", ""),
            "body": data.get("note_body", ""),
            "interaction_type": data.get("interaction_type", "Email"),
            "followup_note": data.get("follow_up_note", "")
        }
        
        if note_config or data.get("create_note"):
            if "subject" in note_config and note_config["subject"]:
                self.note_subject.delete(0, "end")
                self.note_subject.insert(0, note_config["subject"])
                
            body_val = note_config.get("body") or note_config.get("note_body", "")
            if body_val:
                self.note_body.delete("0.0", "end")
                self.note_body.insert("0.0", body_val)
                
            if "interaction_type" in note_config and note_config["interaction_type"]:
                raw_interaction_type = note_config["interaction_type"]
                interaction_type_str = (
                    raw_interaction_type.value
                    if hasattr(raw_interaction_type, "value")
                        else raw_interaction_type
                    )
                self.interaction_type_var.set(interaction_type_str)
                    
            if "followup_note" in note_config and note_config["followup_note"]:
                self.followup_note.delete(0, "end")
                self.followup_note.insert(0, note_config["followup_note"])

        # 8. Filters — replace the default blank row with one row per saved
        # condition, so editing an action doesn't silently drop its filters.
        for row in list(self.filter_rows):
            row._handle_remove()

        saved_filters = data.get("filters") or []
        if saved_filters:
            for condition in saved_filters:
                self._add_filter_row()
                self._apply_saved_condition_to_row(self.filter_rows[-1], condition)
        else:
            self._add_filter_row()

    def _apply_saved_condition_to_row(self, row: FilterRow, condition: dict) -> None:
        """Reconstructs a FilterRow's field/operator/value selection from a
        previously saved condition dict."""
        field_name = condition.get("field")
        if not field_name or field_name not in FILTERABLE_FIELDS:
            return
        row.field_dropdown.set(field_name)
        row._on_field_changed(field_name)

        operator = condition.get("operator")
        valid_operators = [op.value for op in FILTERABLE_FIELDS[field_name].operators]
        if operator and operator in valid_operators:
            row.operator_dropdown.set(operator)
            row._on_operator_changed(operator)

        value = condition.get("value")
        if operator in (Operator.IS_EMPTY.value, Operator.IS_NOT_EMPTY.value) or value is None:
            return

        if operator == Operator.IS_ONE_OF.value:
            if not row._value_widgets:
                return
            listbox = row._value_widgets[0]
            wanted = set(value) if isinstance(value, list) else {value}
            for index, item in enumerate(listbox.get(0, "end")):
                if item in wanted:
                    listbox.selection_set(index)
            return

        if operator == Operator.BETWEEN.value and isinstance(value, list) and len(value) == 2:
            if len(row._value_widgets) >= 3:
                row._value_widgets[0].entry.insert(0, str(value[0]))
                row._value_widgets[2].entry.insert(0, str(value[1]))
            return

        if not row._value_widgets:
            return
        widget = row._value_widgets[0]
        if isinstance(widget, DatePickerEntry):
            widget.entry.insert(0, str(value))
        elif hasattr(widget, "set"):
            widget.set(str(value))
        else:
            widget.insert(0, str(value))

    def get_action_data(self) -> dict:
        """Gathers all current form field values into a dictionary compatible with both View and Controller schemas."""
        return {
            # --- Metadata ---
            "id": self.action_id,
            "name": self.name_entry.get().strip(),
            "group_name": self.group_dropdown.get(),
            "is_welcome_email": self.is_welcome_email_var.get() == "on",

            # --- Channel Toggles ---
            "send_email": self.send_email_var.get() == "on",
            "is_email": self.send_email_var.get() == "on",
            "send_text": self.send_text_var.get() == "on",
            "is_text": self.send_text_var.get() == "on",

            # --- Flat Keys for app_controller.py ---
            "email_subject": self.email_subject.get(),
            "template_id": self.template_map.get(self.email_body_dropdown.get()),
            "email_signature": self.email_signature_dropdown.get(),
            "text_subject": self.text_subject.get(),
            "text_body": self.text_body.get("0.0", "end-1c"),  # "0.0" starting index for CustomTkinter
            "note_subject": self.note_subject.get(),
            "note_body": self.note_body.get("0.0", "end-1c"),  # "0.0" starting index for CustomTkinter
            "follow_up_note": self.followup_note.get(),
            "interaction_type": self.interaction_type_var.get(),

            # --- Nested Configs for View Re-population ---
            "email_config": {
                "subject": self.email_subject.get(),
                "template_name": self.email_body_dropdown.get(),  # display only — template_id above is canonical
                "signature": self.email_signature_dropdown.get()
            },
            "text_config": {
                "subject": self.text_subject.get(),
                "body": self.text_body.get("0.0", "end-1c")
            },
            "note_config": {
                "subject": self.note_subject.get(),
                "body": self.note_body.get("0.0", "end-1c"),
                "interaction_type": self.interaction_type_var.get(),
                "followup_note": self.followup_note.get()
            },

            # --- Dynamic Filters ---
            "filters": [
                condition
                for row in self.filter_rows
                for condition in [row.to_condition()]
                if condition is not None
            ]
        }

    # =========================================================================
    # DYNAMIC FILTER & UI SECTION HELPERS
    # =========================================================================
    def _add_filter_row(self):
        """Adds a filter rule row (FilterRow) inside the filters container."""
        row = FilterRow(
            master=self.filters_container,
            get_live_values=self._get_live_field_values,
            on_remove=self._handle_filter_row_removed,
        )
        row.pack(fill="x", pady=2)
        self.filter_rows.append(row)

    def _handle_filter_row_removed(self, row):
        """FilterRow destroys its own widget on remove - just drop our reference."""
        self.filter_rows = [r for r in self.filter_rows if r is not row]

    def _get_live_field_values(self, field_name):
        """Returns the sorted, deduplicated, non-blank values currently
        present in the roster for `field_name` - what a SET_VALUE_LIVE
        filter field's multi-select options are built from."""
        if self.student_data_provider is None:
            return []
        values = {
            getattr(student, field_name, "").strip()
            for student in self.student_data_provider.get_students()
            if getattr(student, field_name, "").strip()
        }
        return sorted(values)

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

    def _refresh_template_dropdown(self, select_id: str = None):
        """Rebuilds the template dropdown values and name->id map from the repository."""
        self.template_map = {}
        values = ["New / Custom Template"]
        if self.template_repo:
            for t in self.template_repo.load_all():
                values.append(t.name)
                self.template_map[t.name] = t.id
        self.email_body_dropdown.configure(values=values)

        if select_id:
            selected_name = next((name for name, tid in self.template_map.items() if tid == select_id), "New / Custom Template")
            self.email_body_dropdown.set(selected_name)
        else:
            self.email_body_dropdown.set("New / Custom Template")

        self._update_delete_template_button_state()

    def _on_template_dropdown_changed(self, selected_name: str):
        self._update_delete_template_button_state()

    def _update_delete_template_button_state(self):
        """Enables the delete button only when an existing (non-new) template is selected."""
        selected_name = self.email_body_dropdown.get()
        if selected_name in self.template_map:
            self.btn_delete_template.configure(state="normal")
        else:
            self.btn_delete_template.configure(state="disabled")

    def _get_selected_group(self):
        """Resolves the currently selected group in the dropdown to its Group
        object — same by-name resolution the rest of this form already uses
        for the group dropdown (there's no ID-based selector for it). Some
        tests pass plain strings for `groups` instead of Group objects, so
        skip anything without the attributes we need rather than erroring."""
        group_name = self.group_dropdown.get()
        return next(
            (g for g in self.groups if hasattr(g, "name") and hasattr(g, "welcome_action_id") and g.name == group_name),
            None
        )

    def _find_action_name_by_id(self, action_id: str):
        """Looks up an existing action's display name for the conflict dialog.
        Returns None if it can't be resolved (no controller/action_repo, or
        the id doesn't match anything) — the dialog falls back to generic text."""
        action_repo = getattr(self.controller, "action_repo", None)
        if not action_repo:
            return None
        match = next((a for a in action_repo.load_actions() if a.id == action_id), None)
        return match.name if match else None

    def _on_welcome_checkbox_toggled(self):
        """Fires live when the checkbox is clicked (not deferred to Save).
        Checking it while another action already owns the group's welcome
        slot prompts for confirmation; declining reverts the check. Only
        updates the in-memory Group object — self.groups is the same list
        the controller holds, so this is visible immediately, but nothing
        touches disk until the professor clicks Save Action."""
        matched_group = self._get_selected_group()
        if not matched_group:
            return

        if self.is_welcome_email_var.get() != "on":
            if matched_group.welcome_action_id == self.action_id:
                matched_group.welcome_action_id = None
            return

        current_welcome_id = matched_group.welcome_action_id
        if current_welcome_id and current_welcome_id != self.action_id:
            existing_name = self._find_action_name_by_id(current_welcome_id)
            existing_label = f"'{existing_name}'" if existing_name else "another action"
            confirm = messagebox.askyesno(
                "Replace Welcome Email?",
                f"Group '{matched_group.name}' already has {existing_label} designated "
                f"as its welcome email.\n\nDo you want to replace it with this action?"
            )
            if not confirm:
                self.is_welcome_email_var.set("off")
                return

        matched_group.welcome_action_id = self.action_id

    def _build_email_ui(self):
        lbl = ctk.CTkLabel(self.email_container, text="✉️ Email Details", font=ctk.CTkFont(weight="bold"))
        lbl.pack(anchor="w", padx=10, pady=5)
        #checkbox to set email as welcome email
        self.chk_welcome_email = ctk.CTkCheckBox(
            self.email_container,
            text="Is Group Welcome Email",
            variable=self.is_welcome_email_var,
            onvalue="on",
            offvalue="off",
            command=self._on_welcome_checkbox_toggled
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

        self.email_body_dropdown = ctk.CTkComboBox(template_row, values=["New / Custom Template"], width=220, command=self._on_template_dropdown_changed)
        self.email_body_dropdown.pack(side="left", padx=(0, 5))

        self.btn_new_template = ctk.CTkButton(template_row, text="➕ New", width=60, command=self._on_new_template_click)
        self.btn_new_template.pack(side="left", padx=2)

        self.btn_edit_template = ctk.CTkButton(template_row, text="✏️ Edit", width=60, command=self._on_edit_template_click)
        self.btn_edit_template.pack(side="left", padx=2)

        self.btn_delete_template = ctk.CTkButton(
            template_row, text="❌ Delete", width=90, command=self._on_delete_template_click
        )
        self.btn_delete_template.pack(side="left", padx=(2, 0))

        lbl = ctk.CTkLabel(self.email_container, text="Select Outlook Signature:")
        lbl.pack(anchor="w", padx=10, pady=(5, 0))

        self.email_signature_dropdown = ctk.CTkComboBox(
            self.email_container,
            # No "None" option — signatures are required, and offering one invites
            # accidentally sending an unsigned email.
            values=get_signature_names_or_fallback(self.signature_provider),
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
        form_data = self.get_action_data()

        if self.controller and hasattr(self.controller, "save_action"):
            self.controller.save_action(form_data)

    def _on_new_template_click(self):
        """Opens the template editor dialog for creating a new template."""
        TemplateEditorModal(
            master=self.winfo_toplevel(),
            template_id=None,
            on_save_callback=self._handle_template_saved
        )

    def _on_edit_template_click(self):
        """Opens the template editor dialog for the selected template."""
        selected_name = self.email_body_dropdown.get()
        template_id = self.template_map.get(selected_name)

        if not template_id:
            self._on_new_template_click()
            return

        body_content = ""
        if self.template_repo:
            template_obj = self.template_repo.get_by_id(template_id)
            if template_obj:
                body_content = template_obj.body

        TemplateEditorModal(
            master=self.winfo_toplevel(),
            template_id=template_id,
            template_name=selected_name,
            template_body=body_content,
            on_save_callback=self._handle_template_saved
        )

    def _on_delete_template_click(self):
        """Deletes the selected template after confirmation. If some OTHER
        template is deleted, this action's own assigned template is restored
        in the dropdown afterward instead of resetting to New/Custom."""
        selected_name = self.email_body_dropdown.get()
        template_id = self.template_map.get(selected_name)
        if not template_id:
            return

        is_this_action_s_template = template_id == self.action_template_id
        warning = (
            f"⚠️ This template is currently assigned to this action.\n\n"
            f"Deleting it will leave this action without an email template "
            f"until you pick a new one.\n\n"
        ) if is_this_action_s_template else ""

        confirm = messagebox.askokcancel(
            "Delete Template",
            f"❌ Are you sure you want to delete this template?\n\n"
            f"{warning}"
            f"Template: {selected_name}\n\n"
            f"This action cannot be undone!"
        )
        if not confirm:
            return

        if self.template_repo:
            self.template_repo.delete(template_id)

        if is_this_action_s_template:
            self.action_template_id = None  # it's genuinely gone now
            self._refresh_template_dropdown()
        else:
            self._refresh_template_dropdown(select_id=self.action_template_id)

    def _handle_template_saved(self, template_id, name, body):
        """Callback executed when a template is saved inside the editor.
        Runs on the pywebview background thread, so UI updates are marshaled
        back onto the main Tkinter thread via .after()."""
        def _apply():
            saved_id = None
            if self.controller and hasattr(self.controller, "save_template"):
                saved_id = self.controller.save_template(template_id, name, body)
            self._refresh_template_dropdown(select_id=saved_id)

        self.after(0, _apply)