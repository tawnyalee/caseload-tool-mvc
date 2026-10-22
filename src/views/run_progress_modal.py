# src/views/run_progress_modal.py
"""Shown while a run (or a caseload refresh) works in the background:
what's happening, a progress bar, and a Stop button. Deliberately NOT
modal (no grab_set) so the main window - including its ⛔ STOP button and
the Live Application Log - stays usable; AppController refuses to start a
second run while one is going instead.

Closing the window with its X counts as pressing Stop: the window can't be
dismissed while work is still running, only asked to stop.
"""
from typing import Callable, Optional

import customtkinter as ctk


class RunProgressModal(ctk.CTkToplevel):
    def __init__(self, master, title: str, on_stop: Optional[Callable[[], None]] = None):
        """No `on_stop` = nothing to stop (e.g. a caseload refresh): the bar
        just animates and there's no Stop button."""
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.geometry(self._centered_over(master, 460, 170))
        self.resizable(False, False)
        self.on_stop = on_stop
        self._closed = False

        self.status_label = ctk.CTkLabel(self, text="Starting…", anchor="w", justify="left", wraplength=420)
        self.status_label.pack(fill="x", padx=20, pady=(20, 8))

        self.progress_bar = ctk.CTkProgressBar(self, width=420)
        self.progress_bar.pack(padx=20, pady=(0, 6))

        self.count_label = ctk.CTkLabel(self, text="", anchor="w", text_color=("gray40", "gray60"))
        self.count_label.pack(fill="x", padx=20)

        self.stop_button = None
        if on_stop:
            self.progress_bar.set(0)
            self.stop_button = ctk.CTkButton(
                self, text="⛔ Stop after this student", fg_color="#b22222", hover_color="#8b1a1a",
                command=self.request_stop,
            )
            self.stop_button.pack(pady=(10, 15))
        else:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()

        self.protocol("WM_DELETE_WINDOW", self.request_stop)

    @staticmethod
    def _centered_over(master, width: int, height: int) -> str:
        """Geometry string placing this window over the middle of the app
        window (left to the OS, it opened in the screen's top-left corner)."""
        try:
            master.update_idletasks()
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
            return f"{width}x{height}+{max(x, 0)}+{max(y, 0)}"
        except Exception:
            return f"{width}x{height}"

    def update_progress(self, position: int, total: int, text: str) -> None:
        """Called (on the UI thread) just before student `position` of `total`."""
        if self._closed:
            return
        self.status_label.configure(text=f"Sending to {text}")
        self.count_label.configure(text=f"{position} of {total}")
        self.progress_bar.set((position - 1) / total if total else 0)

    def set_status(self, text: str) -> None:
        if not self._closed:
            self.status_label.configure(text=text)

    def request_stop(self) -> None:
        if not self.on_stop or self._closed:
            return  # nothing stoppable (refresh) - the window closes itself when done
        self.on_stop()
        if self.stop_button:
            self.stop_button.configure(state="disabled", text="Stopping after this student…")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self.on_stop:
            self.progress_bar.stop()
        self.destroy()
