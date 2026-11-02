# src/views/first_steps_window.py
"""The first-steps window a new professor sees at startup. Deliberately not
modal (no grab_set), so it stays open beside the app while they work through
the steps; a plain popup would have to be closed first (developer, 2026-11-02).
Shown by AppController._show_startup_messages.
"""
import customtkinter as ctk


class FirstStepsWindow(ctk.CTkToplevel):
    def __init__(self, master, text: str):
        super().__init__(master)
        self.title("Welcome to TouchPoint")
        self.transient(master)
        self.geometry(f"560x{min(520, self.winfo_screenheight() - 120)}")
        self.minsize(420, 320)

        # Packed side="bottom" before the text, so it can never push the
        # button out of view (same lesson as ReviewSendModal).
        self.close_button = ctk.CTkButton(self, text="Close", command=self.destroy)
        self.close_button.pack(side="bottom", anchor="e", padx=15, pady=15)

        self.text_box = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=14))
        self.text_box.pack(fill="both", expand=True, padx=15, pady=(15, 0))
        self.text_box.insert("0.0", text)
        self.text_box.configure(state="disabled")  # read-only, still selectable
