import customtkinter as ctk
import pytest

from src.views.first_steps_window import FirstStepsWindow


@pytest.fixture(scope="module")
def ctk_root():
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()


def test_the_text_shows_and_stays_read_only(ctk_root):
    window = FirstStepsWindow(ctk_root, "1. Create groups")
    window.update()
    assert window.text_box.get("0.0", "end").strip() == "1. Create groups"
    assert window.text_box.cget("state") == "disabled"
    window.destroy()


def test_it_leaves_the_app_usable_behind_it(ctk_root):
    window = FirstStepsWindow(ctk_root, "Steps")
    window.update()
    assert window.grab_current() is None
    window.close_button.invoke()
