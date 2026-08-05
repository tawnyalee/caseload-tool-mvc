# src/views/dashboard_view.py
import customtkinter as ctk


class DashboardView(ctk.CTkFrame):
    def __init__(self, master=None, controller=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.controller = controller

        title = ctk.CTkLabel(self, text="📊 Dashboard", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(anchor="w", padx=20, pady=(20, 15))

        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(anchor="w", padx=20, pady=5, fill="x")

        self.btn_send_welcome = ctk.CTkButton(
            actions_frame,
            text="✉️ Send Welcome Emails",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self._on_send_welcome_clicked,
        )
        self.btn_send_welcome.pack(side="left", padx=(0, 10))

        self.btn_send_all = ctk.CTkButton(
            actions_frame,
            text="📢 Send Email to All Students",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self._on_send_all_clicked,
        )
        self.btn_send_all.pack(side="left", padx=10)

    def _on_send_welcome_clicked(self):
        if self.controller and hasattr(self.controller, "handle_send_welcome_emails"):
            self.controller.handle_send_welcome_emails()

    def _on_send_all_clicked(self):
        if self.controller and hasattr(self.controller, "handle_compose_ad_hoc_email"):
            self.controller.handle_compose_ad_hoc_email()
