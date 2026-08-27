import tkinter as tk

import customtkinter as ctk
import pytest

from src.services.filterable_fields import MOMENTUM_VALUES
from src.views.date_picker import DatePickerEntry
from src.views.filter_row import FilterRow


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def _select_field(row: FilterRow, field_name: str) -> None:
    """CTkComboBox's command doesn't fire on .set(), so drive the row the
    same way FilterRow itself has to internally."""
    row.field_dropdown.set(field_name)
    row._on_field_changed(field_name)


def _select_operator(row: FilterRow, operator: str) -> None:
    row.operator_dropdown.set(operator)
    row._on_operator_changed(operator)


def test_starts_with_a_field_and_matching_operators_selected(ctk_root):
    row = FilterRow(master=ctk_root)
    assert row.field_dropdown.get() != ""
    assert row.operator_dropdown.get() != ""


def test_numeric_field_gets_a_plain_text_entry(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "days_since_last_course_contact")
    _select_operator(row, "GreaterThan")
    assert len(row._value_widgets) == 1
    assert isinstance(row._value_widgets[0], ctk.CTkEntry)


def test_date_field_gets_a_date_picker(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "term_end_date")
    _select_operator(row, "Equals")
    assert len(row._value_widgets) == 1
    assert isinstance(row._value_widgets[0], DatePickerEntry)


def test_date_field_between_gets_two_date_pickers(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "term_end_date")
    _select_operator(row, "Between")
    assert isinstance(row._value_widgets[0], DatePickerEntry)
    assert isinstance(row._value_widgets[2], DatePickerEntry)


def test_is_empty_has_no_value_widget(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "term_end_date")
    _select_operator(row, "IsEmpty")
    assert row._value_widgets == []


def test_fixed_set_value_field_gets_a_multiselect_listbox_with_fixed_options(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "momentum")
    _select_operator(row, "IsOneOf")
    assert len(row._value_widgets) == 2
    listbox = row._value_widgets[0]
    assert isinstance(listbox, tk.Listbox)
    assert str(listbox.cget("selectmode")) == "extended"
    assert list(listbox.get(0, "end")) == MOMENTUM_VALUES


def test_live_set_value_field_populates_listbox_from_callback(ctk_root):
    row = FilterRow(master=ctk_root, get_live_values=lambda field_name: ["D424", "D370"])
    _select_field(row, "course_code")
    _select_operator(row, "IsOneOf")
    listbox = row._value_widgets[0]
    assert list(listbox.get(0, "end")) == ["D424", "D370"]


def test_boolean_field_gets_a_true_false_dropdown(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "latest_task_date_yesterday")
    _select_operator(row, "Equals")
    assert isinstance(row._value_widgets[0], ctk.CTkComboBox)
    assert set(row._value_widgets[0].cget("values")) == {"TRUE", "FALSE"}


def test_to_condition_single_value(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "salesforce_id")
    _select_operator(row, "Equals")
    row._value_widgets[0].insert(0, "000000001")
    assert row.to_condition() == {"field": "salesforce_id", "operator": "Equals", "value": "000000001"}


def test_to_condition_no_value_operator(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "term_end_date")
    _select_operator(row, "IsNotEmpty")
    assert row.to_condition() == {"field": "term_end_date", "operator": "IsNotEmpty"}


def test_to_condition_is_one_of_reads_listbox_selection(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "momentum")
    _select_operator(row, "IsOneOf")
    listbox = row._value_widgets[0]
    listbox.selection_set(0)
    listbox.selection_set(2)
    condition = row.to_condition()
    assert condition["field"] == "momentum"
    assert condition["operator"] == "IsOneOf"
    assert condition["value"] == ["Low", "Med"]


def test_to_condition_is_one_of_with_nothing_selected_is_none(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "momentum")
    _select_operator(row, "IsOneOf")
    assert row.to_condition() is None


def test_to_condition_between_reads_both_date_pickers(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "term_end_date")
    _select_operator(row, "Between")
    row._value_widgets[0].entry.insert(0, "6/1/2026")
    row._value_widgets[2].entry.insert(0, "6/30/2026")
    assert row.to_condition() == {
        "field": "term_end_date", "operator": "Between", "value": ["6/1/2026", "6/30/2026"],
    }


def test_to_condition_with_empty_required_value_is_none(ctk_root):
    row = FilterRow(master=ctk_root)
    _select_field(row, "salesforce_id")
    _select_operator(row, "Equals")
    assert row.to_condition() is None


def test_remove_button_calls_callback_and_destroys_row(ctk_root):
    removed = []
    row = FilterRow(master=ctk_root, on_remove=lambda r: removed.append(r))
    row._handle_remove()
    assert removed == [row]
