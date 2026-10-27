import pytest
import customtkinter as ctk

from src.models.group import Group
from src.views.settings_view import SettingsView


@pytest.fixture(scope="module")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def _view(ctk_root, groups):
    saved = []
    view = SettingsView(ctk_root, groups=groups, on_save=saved.append)
    return view, saved


def test_shows_each_groups_current_settings(ctk_root):
    group = Group(name="Capstone", group_id="G1", is_course=True, course_code="D424",
                  has_tasks=True, task_count=5, has_objective_assessment=True)
    view, _ = _view(ctk_root, [group])
    try:
        card = view.cards[0]
        assert card.course_code_entry.get() == "D424"
        assert card.task_count_entry.get() == "5"
        assert card.has_oa_var.get() == "on"
    finally:
        view.destroy()


def test_saving_returns_settings_by_group_id_with_tasks_and_oa_together(ctk_root):
    view, saved = _view(ctk_root, [Group(name="D424", group_id="G1", is_course=True, course_code="D424")])
    try:
        card = view.cards[0]
        card.has_tasks_var.set("on"); card._refresh_enabled()
        card.task_count_entry.insert(0, "4")
        card.has_oa_var.set("on")
        assert view.save() is True
        assert saved == [{"G1": {"is_course": True, "course_code": "D424", "has_tasks": True,
                                 "task_count": 4, "has_objective_assessment": True}}]
    finally:
        view.destroy()


def test_a_course_needs_a_code_and_a_task_count_before_saving(ctk_root):
    view, saved = _view(ctk_root, [Group(name="New Course", group_id="G1", is_course=True, course_code="")])
    try:
        card = view.cards[0]
        card.has_tasks_var.set("on"); card._refresh_enabled()
        card.task_count_entry.insert(0, "lots")
        assert view.save() is False
        assert saved == []
        problems = view.problems_label.cget("text")
        assert "enter the course code" in problems and "how many tasks" in problems
    finally:
        view.destroy()


def test_unmarking_a_course_disables_its_details_and_saves_it_as_not_a_course(ctk_root):
    view, saved = _view(ctk_root, [Group(name="D424", group_id="G1", is_course=True, course_code="D424", has_tasks=True, task_count=3)])
    try:
        card = view.cards[0]
        card.is_course_var.set("off"); card._refresh_enabled()
        assert card.course_code_entry.cget("state") == "disabled"
        assert view.save() is True
        assert saved[0]["G1"]["is_course"] is False
        assert saved[0]["G1"]["has_tasks"] is False
    finally:
        view.destroy()
