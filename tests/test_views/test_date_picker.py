from datetime import date

import customtkinter as ctk
import pytest

from src.views.date_picker import DatePickerEntry, format_date, month_grid


def test_month_grid_matches_calendar_module_shape():
    # August 2026: 1st is a Saturday, spans 6 calendar-grid rows
    grid = month_grid(2026, 8)
    assert len(grid) == 6
    assert grid[0][5] == 1  # Saturday column, first row
    assert all(day == 0 for day in grid[0][:5])  # Mon-Fri before the 1st are padding
    assert grid[-1][0] == 31  # last day falls on a Monday


def test_month_grid_handles_february_leap_year():
    grid = month_grid(2024, 2)
    last_day = max(day for week in grid for day in week)
    assert last_day == 29  # 2024 is a leap year


def test_format_date_matches_app_convention():
    assert format_date(date(2026, 8, 7)) == "8/7/2026"


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def test_date_picker_entry_starts_empty_without_an_initial_date(ctk_root):
    picker = DatePickerEntry(master=ctk_root)
    assert picker.get() == ""


def test_date_picker_entry_shows_initial_date(ctk_root):
    picker = DatePickerEntry(master=ctk_root, initial_date=date(2026, 8, 7))
    assert picker.get() == "8/7/2026"


def test_set_date_updates_the_entry(ctk_root):
    picker = DatePickerEntry(master=ctk_root)
    picker.set_date(date(2026, 12, 25))
    assert picker.get() == "12/25/2026"


def test_entry_stays_manually_editable(ctk_root):
    picker = DatePickerEntry(master=ctk_root)
    picker.entry.insert(0, "1/1/2027")
    assert picker.get() == "1/1/2027"
