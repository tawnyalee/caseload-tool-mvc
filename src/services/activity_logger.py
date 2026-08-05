# src/services/activity_logger.py
"""Writes timestamped activity log lines to a daily file on disk and, if a
ui_callback is registered, forwards each message there too (e.g. the nav
panel's Live Application Log console) — one call site, both destinations
always agree.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class ActivityLogger:
    def __init__(self, log_dir: str = "logs", ui_callback: Optional[Callable[[str], None]] = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.ui_callback = ui_callback

        self._logger = logging.getLogger(f"activity_logger.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._file_handler = None
        self._current_log_date = None
        self._attach_handler_for_today()

    def _attach_handler_for_today(self) -> None:
        """(Re)points the file handler at today's log file, rolling over if
        the day has changed since the last write."""
        today = datetime.now().date()
        if today == self._current_log_date:
            return

        if self._file_handler:
            self._logger.removeHandler(self._file_handler)
            self._file_handler.close()

        log_path = self.log_dir / f"{today.isoformat()}.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        self._logger.addHandler(handler)
        self._file_handler = handler
        self._current_log_date = today

    def log(self, message: str) -> None:
        self._attach_handler_for_today()
        self._logger.info(message)

        if self.ui_callback:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.ui_callback(f"[{timestamp}] {message}")
