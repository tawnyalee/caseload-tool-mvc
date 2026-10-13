import customtkinter as ctk
import pytest

from src.models.action import Action
from src.models.group import Group
from src.models.saved_batch import SavedBatch
from src.views.batch_run_modal import BatchRunModal, _NO_SAVED_BATCH_SELECTED, _NO_SAVED_BATCHES_YET


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


# --- Saved Batches ---------------------------------------------------------

def test_saved_batch_menu_shows_placeholder_when_none_saved(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)

    assert modal._saved_batch_menu_values() == [_NO_SAVED_BATCHES_YET]
    modal.destroy()


def test_saved_batch_menu_lists_provided_batches(ctk_root):
    actions, groups = _make_actions_and_groups()
    batches = [SavedBatch(name="Weekly Follow-ups", action_ids=["A1"], batch_id="B1")]
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups, saved_batches=batches)

    assert modal._saved_batch_menu_values() == [_NO_SAVED_BATCH_SELECTED, "Weekly Follow-ups"]
    modal.destroy()


def test_selecting_a_saved_batch_loads_its_actions_in_order(ctk_root):
    actions, groups = _make_actions_and_groups()
    batches = [SavedBatch(name="Weekly Follow-ups", action_ids=["A3", "A1"], batch_id="B1")]
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups, saved_batches=batches)

    modal._on_saved_batch_selected("Weekly Follow-ups")

    assert modal._selected_ids == ["A3", "A1"]
    assert modal._checkbox_vars["A3"].get() == "on"
    assert modal._checkbox_vars["A1"].get() == "on"
    assert modal._checkbox_vars["A2"].get() == "off"
    modal.destroy()


def test_selecting_a_saved_batch_drops_action_ids_that_no_longer_exist(ctk_root):
    actions, groups = _make_actions_and_groups()
    batches = [SavedBatch(name="Stale Batch", action_ids=["A1", "does-not-exist"], batch_id="B1")]
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups, saved_batches=batches)

    modal._on_saved_batch_selected("Stale Batch")

    assert modal._selected_ids == ["A1"]
    modal.destroy()


def test_selecting_the_placeholder_does_nothing(ctk_root):
    actions, groups = _make_actions_and_groups()
    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups)
    modal._selected_ids = ["A1"]

    modal._on_saved_batch_selected(_NO_SAVED_BATCHES_YET)

    assert modal._selected_ids == ["A1"]  # untouched
    modal.destroy()


def test_save_with_nothing_selected_does_not_call_on_save_batch(ctk_root, monkeypatch):
    actions, groups = _make_actions_and_groups()
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *a, **k: None)
    calls = []
    modal = BatchRunModal(
        master=ctk_root, actions=actions, groups=groups,
        on_save_batch=lambda name, ids: calls.append((name, ids)),
    )

    modal._handle_save_clicked()

    assert calls == []
    modal.destroy()


def test_save_prompts_for_a_name_and_calls_on_save_batch(ctk_root, monkeypatch):
    actions, groups = _make_actions_and_groups()
    monkeypatch.setattr(BatchRunModal, "_prompt_batch_name", lambda self: "Weekly Follow-ups")
    calls = []

    def fake_on_save(name, ids):
        calls.append((name, ids))
        return SavedBatch(name=name, action_ids=ids, batch_id="B1")

    modal = BatchRunModal(master=ctk_root, actions=actions, groups=groups, on_save_batch=fake_on_save)
    modal._selected_ids = ["A1", "A3"]

    modal._handle_save_clicked()

    assert calls == [("Weekly Follow-ups", ["A1", "A3"])]
    assert modal._saved_batch_var.get() == "Weekly Follow-ups"
    assert modal._saved_batch_menu_values() == [_NO_SAVED_BATCH_SELECTED, "Weekly Follow-ups"]
    modal.destroy()


def test_save_over_an_existing_name_asks_to_confirm_and_aborts_if_declined(ctk_root, monkeypatch):
    actions, groups = _make_actions_and_groups()
    existing = SavedBatch(name="Weekly Follow-ups", action_ids=["A1"], batch_id="B1")
    monkeypatch.setattr(BatchRunModal, "_prompt_batch_name", lambda self: "Weekly Follow-ups")
    monkeypatch.setattr(BatchRunModal, "_confirm_overwrite", lambda self, name: False)
    calls = []
    modal = BatchRunModal(
        master=ctk_root, actions=actions, groups=groups, saved_batches=[existing],
        on_save_batch=lambda name, ids: calls.append((name, ids)),
    )
    modal._selected_ids = ["A2"]

    modal._handle_save_clicked()

    assert calls == []  # declined the overwrite - nothing saved
    modal.destroy()


def test_save_cancelled_name_prompt_does_not_call_on_save_batch(ctk_root, monkeypatch):
    actions, groups = _make_actions_and_groups()
    monkeypatch.setattr(BatchRunModal, "_prompt_batch_name", lambda self: None)
    calls = []
    modal = BatchRunModal(
        master=ctk_root, actions=actions, groups=groups,
        on_save_batch=lambda name, ids: calls.append((name, ids)),
    )
    modal._selected_ids = ["A1"]

    modal._handle_save_clicked()

    assert calls == []
    modal.destroy()


def test_delete_saved_batch_asks_to_confirm_and_removes_it(ctk_root, monkeypatch):
    actions, groups = _make_actions_and_groups()
    batch = SavedBatch(name="Weekly Follow-ups", action_ids=["A1"], batch_id="B1")
    monkeypatch.setattr(BatchRunModal, "_confirm_delete", lambda self, name: True)
    deleted_ids = []
    modal = BatchRunModal(
        master=ctk_root, actions=actions, groups=groups, saved_batches=[batch],
        on_delete_batch=lambda batch_id: deleted_ids.append(batch_id),
    )
    modal._saved_batch_var.set("Weekly Follow-ups")

    modal._handle_delete_saved_batch_clicked()

    assert deleted_ids == ["B1"]
    assert modal._saved_batches == []
    assert modal._saved_batch_menu_values() == [_NO_SAVED_BATCHES_YET]
    modal.destroy()


def test_delete_saved_batch_declined_leaves_it_in_place(ctk_root, monkeypatch):
    actions, groups = _make_actions_and_groups()
    batch = SavedBatch(name="Weekly Follow-ups", action_ids=["A1"], batch_id="B1")
    monkeypatch.setattr(BatchRunModal, "_confirm_delete", lambda self, name: False)
    deleted_ids = []
    modal = BatchRunModal(
        master=ctk_root, actions=actions, groups=groups, saved_batches=[batch],
        on_delete_batch=lambda batch_id: deleted_ids.append(batch_id),
    )
    modal._saved_batch_var.set("Weekly Follow-ups")

    modal._handle_delete_saved_batch_clicked()

    assert deleted_ids == []
    assert len(modal._saved_batches) == 1
    modal.destroy()
