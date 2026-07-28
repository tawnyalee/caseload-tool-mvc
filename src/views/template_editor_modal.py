# src/views/template_editor_modal.py
import customtkinter as ctk

class TemplateEditorModal(ctk.CTkToplevel):
    def __init__(self, master, template_name="", template_body="", on_save_callback=None):
        super().__init__(master)
        self.title("Template Editor")
        self.geometry("500x400")
        self.on_save_callback = on_save_callback

        # Keep window on top of main app
        self.transient(master)
        self.grab_set()

        # Title / Name Entry
        lbl_name = ctk.CTkLabel(self, text="Template Name", font=ctk.CTkFont(weight="bold"))
        lbl_name.pack(anchor="w", padx=15, pady=(15, 2))
        
        self.name_entry = ctk.CTkEntry(self, placeholder_text="e.g., Welcome Email Body")
        self.name_entry.pack(fill="x", padx=15, pady=(0, 10))
        if template_name:
            self.name_entry.insert(0, template_name)

        # Simple Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(0, 5))
        
        btn_bold = ctk.CTkButton(toolbar, text="B", width=30, command=lambda: self._insert_tag("<b>", "</b>"))
        btn_bold.pack(side="left", padx=(0, 2))
        
        btn_italic = ctk.CTkButton(toolbar, text="I", width=30, command=lambda: self._insert_tag("<i>", "</i>"))
        btn_italic.pack(side="left", padx=2)

        # Body Textbox
        lbl_body = ctk.CTkLabel(self, text="Template Content (HTML/Text)", font=ctk.CTkFont(weight="bold"))
        lbl_body.pack(anchor="w", padx=15, pady=(5, 2))

        self.body_text = ctk.CTkTextbox(self, height=180)
        self.body_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        if template_body:
            self.body_text.insert("1.0", template_body)

        # Save Button
        btn_save = ctk.CTkButton(self, text="💾 Save Template", command=self._on_save)
        btn_save.pack(side="right", padx=15, pady=(0, 15))

    def _insert_tag(self, open_tag, close_tag):
        try:
            sel_first = self.body_text.index("sel.first")
            sel_last = self.body_text.index("sel.last")
            selected_text = self.body_text.get(sel_first, sel_last)
            self.body_text.delete(sel_first, sel_last)
            self.body_text.insert(sel_first, f"{open_tag}{selected_text}{close_tag}")
        except ctk.TclError:
            self.body_text.insert("insert", f"{open_tag}{close_tag}")

    def _on_save(self):
        name = self.name_entry.get().strip()
        body = self.body_text.get("1.0", "end-1c")
        if name and self.on_save_callback:
            self.on_save_callback(name, body)
        self.destroy()