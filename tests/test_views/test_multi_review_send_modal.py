import customtkinter as ctk
import pytest

from src.models.student import Student
from src.views.multi_review_send_modal import MultiReviewSendModal, ReviewItem


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def _student(sid, first, last):
    return Student(salesforce_id=sid, first_name=first, last_name=last, email=f"{first.lower()}@example.test")


def _items():
    return [
        ReviewItem(
            key="G1", label="D424 — Welcome Action",
            students=[_student("SF1", "Jane", "Doe"), _student("SF2", "John", "Roe")],
        ),
        ReviewItem(
            key="G2", label="C769 — Welcome Action",
            students=[_student("SF3", "Amy", "Lee")],
        ),
    ]


def test_confirm_and_cancel_are_anchored_to_the_bottom_of_the_window(ctk_root):
    """Regression coverage for the same class of bug fixed in
    ReviewSendModal: with multiple items each potentially having many
    students, the confirm/cancel row must claim its space before the
    scrollable item sections, not after."""
    modal = MultiReviewSendModal(master=ctk_root, title="Run Batch", items=_items())

    assert modal.confirm_button.master.pack_info()["side"] == "bottom"
    assert modal.cancel_button.master.pack_info()["side"] == "bottom"

    modal.destroy()


def test_select_all_and_select_none_are_scoped_to_one_item(ctk_root):
    modal = MultiReviewSendModal(master=ctk_root, title="Run Batch", items=_items())

    modal._select_none("G1")
    assert all(var.get() == "off" for var in modal._check_vars["G1"].values())
    assert all(var.get() == "on" for var in modal._check_vars["G2"].values())

    modal._select_all("G1")
    assert all(var.get() == "on" for var in modal._check_vars["G1"].values())

    modal.destroy()


def test_item_with_zero_students_has_no_checkboxes_and_does_not_crash(ctk_root):
    items = [ReviewItem(key="G1", label="Empty Group — Action", students=[])]
    modal = MultiReviewSendModal(master=ctk_root, title="Run Batch", items=items)

    assert modal._check_vars["G1"] == {}

    modal.destroy()


def test_confirm_with_nothing_selected_anywhere_warns_and_does_not_confirm(ctk_root, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "src.views.multi_review_send_modal.messagebox.showwarning",
        lambda title, msg: warnings.append((title, msg)),
    )
    confirmed = []
    modal = MultiReviewSendModal(
        master=ctk_root, title="Run Batch", items=_items(), on_confirm=lambda s: confirmed.append(s)
    )
    modal._select_none("G1")
    modal._select_none("G2")

    modal._on_confirm()

    assert confirmed == []
    assert len(warnings) == 1


def test_confirm_calls_on_confirm_with_a_selections_dict_keyed_by_item(ctk_root):
    confirmed = []
    modal = MultiReviewSendModal(
        master=ctk_root, title="Run Batch", items=_items(), on_confirm=lambda s: confirmed.append(s)
    )
    modal._check_vars["G1"]["SF2"].set("off")  # deselect John, keep Jane
    modal._select_none("G2")  # deselect all of C769

    modal._on_confirm()

    assert len(confirmed) == 1
    assert confirmed[0] == {"G1": {"SF1"}, "G2": set()}


def test_confirm_closes_the_dialog_before_on_confirm_runs(ctk_root):
    """Same regression as ReviewSendModal's: on_confirm opens the progress
    window, which would try to re-focus a button of this (by then closed)
    dialog."""
    still_open_during_confirm = []
    modal = MultiReviewSendModal(
        master=ctk_root, title="Run Batch", items=_items(),
        on_confirm=lambda s: still_open_during_confirm.append(bool(modal.winfo_exists())),
    )

    modal._on_confirm()

    assert still_open_during_confirm == [False]
