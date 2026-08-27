import customtkinter as ctk
import pytest

from src.models.action import Action
from src.models.group import Group
from src.views.batch_run_modal import BatchRunModal


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def _make_actions_and_groups():
    groups = [Group(name="D424", group_id="G1"), Group(name="D370", group_id="G2")]
    actions = [
        Action(name="Task 2 Passed", group_id="G1", action_id="A1"),
        Action(name="Task 2 Passed", group_id="G2", action_id="A2"),  # same name, different group
        Action(name="Welcome", group_id="G1", action_id="A3"),
    ]
    return actions, groups


def test_checking_a_box_adds_it_to_the_selected_list(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)

    modal._checkbox_vars["A1"].set("on")
    modal._on_checkbox_toggled(actions[0], modal._checkbox_vars["A1"])

    assert modal._selected_ids == ["A1"]
    modal.destroy()


def test_unchecking_removes_it(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)

    modal._checkbox_vars["A1"].set("on")
    modal._on_checkbox_toggled(actions[0], modal._checkbox_vars["A1"])
    modal._checkbox_vars["A1"].set("off")
    modal._on_checkbox_toggled(actions[0], modal._checkbox_vars["A1"])

    assert modal._selected_ids == []
    modal.destroy()


def test_selection_order_matches_check_order_not_list_order(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)

    for action_id in ("A3", "A1", "A2"):
        modal._checkbox_vars[action_id].set("on")
        modal._on_checkbox_toggled(modal._actions_by_id[action_id], modal._checkbox_vars[action_id])

    assert modal._selected_ids == ["A3", "A1", "A2"]
    modal.destroy()


def test_move_up_and_down_reorders(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)
    modal._selected_ids = ["A1", "A2", "A3"]
    modal._render_selected_list()

    modal._move(0, 1)  # swap A1 and A2
    assert modal._selected_ids == ["A2", "A1", "A3"]

    modal._move(0, -1)  # can't move the first item further up - no-op
    assert modal._selected_ids == ["A2", "A1", "A3"]

    modal._move(2, 1)  # can't move the last item further down - no-op
    assert modal._selected_ids == ["A2", "A1", "A3"]
    modal.destroy()


def test_remove_from_selected_panel_also_unchecks_the_box(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)
    modal._selected_ids = ["A1", "A2"]
    modal._render_selected_list()

    modal._remove_selected("A1")

    assert modal._selected_ids == ["A2"]
    assert modal._checkbox_vars["A1"].get() == "off"
    modal.destroy()


def test_run_with_nothing_selected_does_not_call_on_run(ctk_root):
    actions, groups = _make_actions_and_groups()
    calls = []
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups, on_run=lambda a, g: calls.append((a, g)))

    modal._handle_run_clicked()

    assert calls == []


def test_run_calls_on_run_with_actions_and_group_names_in_selected_order(ctk_root):
    actions, groups = _make_actions_and_groups()
    calls = []
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups, on_run=lambda a, g: calls.append((a, g)))
    modal._selected_ids = ["A2", "A1"]

    modal._handle_run_clicked()

    assert len(calls) == 1
    run_actions, run_group_names = calls[0]
    assert [a.id for a in run_actions] == ["A2", "A1"]
    assert run_group_names == ["D370", "D424"]
