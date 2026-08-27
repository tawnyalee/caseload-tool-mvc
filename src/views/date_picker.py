# src/views/date_picker.py
"""A lightweight calendar date picker with no third-party dependency (see
docs/filter_engine_requirements.md - both tkcalendar and the CustomTkinter-
specific alternatives were checked and found to be lightly maintained with
real open bugs, not worth depending on for something this small to build).

DatePickerEntry is a CTkEntry + button that opens a calendar popup on
click. month_grid() is the pure date math behind the popup - kept separate
from the widget code so it can be tested without touching any GUI code,
same principle used throughout this project's other filter-engine work.
"""
import calendar
from datetime import date, datetime
from typing import Callable, List, Optional

import customtkinter as ctk

_WEEKDAY_HEADERS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def month_grid(year: int, month: int) -> List[List[int]]:
    """Returns a week-by-week grid of day numbers for the given month.
    Days outside the month are 0, matching Python's `calendar` module
    convention - a pure function, no UI, easy to unit test on its own."""
    return calendar.monthcalendar(year, month)


def format_date(value: date) -> str:
    """M/D/YYYY - matches the date format used throughout Student's data
    and what filter_engine._parse_date() already knows how to read."""
    return f"{value.month}/{value.day}/{value.year}"


class DatePickerEntry(ctk.CTkFrame):
    """A text entry showing the selected date, plus a button that opens a
    calendar popup for picking one. The entry stays manually editable too,
    for anyone who'd rather just type a date."""

    def __init__(self, master, initial_date: Optional[date] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.entry = ctk.CTkEntry(self, width=110, placeholder_text="M/D/YYYY")
        self.entry.pack(side="left")
        if initial_date:
            self.entry.insert(0, format_date(initial_date))

        self.button = ctk.CTkButton(self, text="📅", width=30, command=self._open_popup)
        self.button.pack(side="left", padx=(4, 0))

    def get(self) -> str:
        """Returns whatever's in the entry - either picked from the
        popup or typed directly."""
        return self.entry.get().strip()

    def set_date(self, value: date) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, format_date(value))

    def _open_popup(self) -> None:
        start = self._parse_current_entry() or date.today()
        popup = _CalendarPopup(self, start.year, start.month, on_pick=self.set_date)
        popup.grab_set()

    def _parse_current_entry(self) -> Optional[date]:
        text = self.entry.get().strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None


class _CalendarPopup(ctk.CTkToplevel):
    def __init__(self, master, year: int, month: int, on_pick: Callable[[date], None]):
        super().__init__(master)
        self.title("")
        self.resizable(False, False)
        self.transient(master)
        self._year = year
        self._month = month
        self._on_pick = on_pick
        self._build_ui()

    def _build_ui(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkButton(header, text="◀", width=28, command=self._prev_month).pack(side="left")
        month_label = ctk.CTkLabel(
            header, text=f"{calendar.month_name[self._month]} {self._year}",
            font=ctk.CTkFont(weight="bold"),
        )
        month_label.pack(side="left", expand=True)
        ctk.CTkButton(header, text="▶", width=28, command=self._next_month).pack(side="right")

        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(padx=8, pady=(0, 8))

        for col, day_name in enumerate(_WEEKDAY_HEADERS):
            ctk.CTkLabel(grid_frame, text=day_name, width=32).grid(row=0, column=col)

        for row, week in enumerate(month_grid(self._year, self._month), start=1):
            for col, day in enumerate(week):
                if day == 0:
                    continue
                ctk.CTkButton(
                    grid_frame, text=str(day), width=32,
                    command=lambda d=day: self._pick(d),
                ).grid(row=row, column=col, padx=1, pady=1)

    def _prev_month(self) -> None:
        self._month -= 1
        if self._month == 0:
            self._month = 12
            self._year -= 1
        self._build_ui()

    def _next_month(self) -> None:
        self._month += 1
        if self._month == 13:
            self._month = 1
            self._year += 1
        self._build_ui()

    def _pick(self, day: int) -> None:
        self._on_pick(date(self._year, self._month, day))
        self.destroy()
