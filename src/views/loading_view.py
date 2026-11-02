# src/views/loading_view.py
"""Fills the app window while startup logs in and loads the roster, so the
professor doesn't finish logging in and see nothing happen (developer's ask,
2026-10-31). AppController swaps it for the real views when loading ends."""
import customtkinter as ctk

LOGGING_IN_TEXT = "Waiting for you to log in. Use the Edge window that opened."
LOADING_CASELOAD_TEXT = "Logged in. Loading your caseload, this can take a minute or two..."


class LoadingView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(center, text="TouchPoint", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(0, 12))
        self.status_label = ctk.CTkLabel(center, text=LOGGING_IN_TEXT, font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(0, 12))
        self.progress_bar = ctk.CTkProgressBar(center, width=360, mode="indeterminate")
        self.progress_bar.pack()
        self.progress_bar.start()

    def set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def destroy(self) -> None:
        self.progress_bar.stop()
        super().destroy()
