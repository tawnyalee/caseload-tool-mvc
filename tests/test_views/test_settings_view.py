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
    view = SettingsView(ctk_root, groups=groups, on_save=lambda values, _problems: saved.append(values))
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
                                 "task_count": 4, "has_objective_assessment": True, "task_emails": {}}}]
    finally:
        view.destroy()


def test_a_course_needs_a_code_and_a_task_count_before_saving(ctk_root):
    view, saved = _view(ctk_root, [Group(name="New Course", group_id="G1", is_course=True, course_code="")])
    try:
        card = view.cards[0]
        card.has_tasks_var.set("on"); card._refresh_enabled()
        card.task_count_entry.insert(0, "lots")
        assert view.save() is False
        assert saved == [{}]
        problems = view.problems_label.cget("text")
        assert "enter the course code" in problems and "how many tasks" in problems
    finally:
        view.destroy()


def test_an_incomplete_course_doesnt_stop_a_finished_one_from_saving(ctk_root):
    finished = Group(name="D424", group_id="G1", is_course=True, course_code="D424", has_tasks=True)
    incomplete = Group(name="C769", group_id="G2", is_course=True, course_code="C769", has_tasks=True)
    calls = []
    view = SettingsView(ctk_root, groups=[finished, incomplete], on_save=lambda *args: calls.append(args))
    try:
        view.cards[0].task_count_entry.insert(0, "5")
        assert view.save() is False
        values, problems = calls[0]
        assert list(values) == ["G1"] and values["G1"]["task_count"] == 5
        assert problems == ["C769: enter how many tasks (a whole number, 1 or more)."]
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



# --- Task email rows ---------------------------------------------------------

TEMPLATES = [("T2", "Task 2 tips"), ("T3", "Task 3 tips"), ("OA", "OA prep")]


def _course(task_count, has_oa=False, task_emails=None):
    return Group(name="D424", group_id="G1", is_course=True, course_code="D424", has_tasks=True,
                 task_count=task_count, has_objective_assessment=has_oa, task_emails=task_emails)


def test_tasks_only_course_shows_a_row_per_task_except_the_last(ctk_root):
    view = SettingsView(ctk_root, groups=[_course(4)], on_save=lambda *_: None, templates=TEMPLATES)
    try:
        assert sorted(view.cards[0]._email_widgets) == [1, 2, 3]
    finally:
        view.destroy()


def test_rows_say_which_task_passed_and_what_the_subject_will_be(ctk_root):
    view = SettingsView(ctk_root, groups=[_course(3, has_oa=True)], on_save=lambda *_: None, templates=TEMPLATES)
    try:
        card = view.cards[0]
        assert sorted(card._email_widgets) == [1, 2]
        labels = [w.cget("text") for w in card.emails_frame.winfo_children() if isinstance(w, ctk.CTkLabel)]
        assert "Passed Task 1" in labels and "Subject: Task 2 Support" in labels
    finally:
        view.destroy()


def test_a_saved_template_lands_in_its_row_and_every_dropdown(ctk_root):
    templates = list(TEMPLATES)

    def save_template(template_id, name, body):
        templates.append(("NEW", name))
        return "NEW"

    saved = []
    view = SettingsView(
        ctk_root, groups=[_course(3)], on_save=lambda values, _problems: saved.append(values),
        load_templates=lambda: templates, save_template=save_template,
    )
    try:
        view._template_saved(view.cards[0], 2, None, "Fresh email", "<p>Hi</p>")
        assert view.cards[0]._email_widgets[2].get() == "Fresh email"
        view.save()
        assert saved[0]["G1"]["task_emails"]["2"]["template_id"] == "NEW"
    finally:
        view.destroy()


def test_the_top_of_settings_explains_the_task_email_greeting(ctk_root):
    view = SettingsView(ctk_root, groups=[], on_save=lambda *_: None)
    try:
        assert "No need to set up a 'Hello, <<name>>'" in view.greeting_note.cget("text")
    finally:
        view.destroy()


def test_default_signature_shows_and_saves_and_none_clears_it(ctk_root):
    chosen = []
    view = SettingsView(
        ctk_root, groups=[], on_save=lambda *_: None, signature_names=["Mine", "Other"],
        default_signature="Mine", on_save_signature=chosen.append,
    )
    try:
        assert view.signature_dropdown.get() == "Mine"
        view.save()
        view.signature_dropdown.set("(none)")
        view.save()
        assert chosen == ["Mine", ""]
    finally:
        view.destroy()


def test_saved_choices_show_and_save_as_template_ids_with_default_subject(ctk_root):
    saved = []
    group = _course(3, task_emails={"1": {"template_id": "T2", "subject": "On to Task 2"}})
    view = SettingsView(ctk_root, groups=[group], on_save=lambda values, _problems: saved.append(values), templates=TEMPLATES)
    try:
        card = view.cards[0]
        assert card._email_widgets[1].get() == "Task 2 tips"
        card._email_widgets[2].set("Task 3 tips")
        assert view.save() is True
        emails = saved[0]["G1"]["task_emails"]
        assert emails["1"] == {"template_id": "T2", "subject": "On to Task 2"}
        assert emails["2"] == {"template_id": "T3", "subject": "Nice work on {{last_passed_task}}!"}
    finally:
        view.destroy()


def test_changing_the_task_count_rebuilds_rows_and_keeps_what_was_chosen(ctk_root):
    view = SettingsView(ctk_root, groups=[_course(3)], on_save=lambda *_: None, templates=TEMPLATES)
    try:
        card = view.cards[0]
        card._email_widgets[1].set("Task 2 tips")
        card.task_count_entry.delete(0, "end"); card.task_count_entry.insert(0, "5")
        card._rebuild_email_rows()
        assert sorted(card._email_widgets) == [1, 2, 3, 4]
        assert card._email_widgets[1].get() == "Task 2 tips"
    finally:
        view.destroy()


def test_the_direct_saves_box_shows_the_setting_and_saves_it(ctk_root):
    chosen = []
    view = SettingsView(
        ctk_root, groups=[], on_save=lambda *_: None, use_direct_saves=True, on_save_direct_saves=chosen.append,
    )
    try:
        assert view.direct_saves_var.get() == "on"
        view.save()
        view.direct_saves_var.set("off")
        view.save()
        assert chosen == [True, False]
    finally:
        view.destroy()
