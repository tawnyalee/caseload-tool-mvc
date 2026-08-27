import customtkinter as ctk
import pytest
from src.views.dashboard_view import DashboardView


class MockController:
    def __init__(self):
        self.welcome_clicked = False
        self.ad_hoc_clicked = False
        self.batch_runner_opened = False

    def handle_send_welcome_emails(self):
        self.welcome_clicked = True

    def handle_compose_ad_hoc_email(self):
        self.ad_hoc_clicked = True

    def handle_open_batch_runner(self):
        self.batch_runner_opened = True


@pytest.fixture(scope="session")
def ctk_root():
    app = ctk.CTk()
    app.withdraw()
    yield app
    app.destroy()


def test_dashboard_view_has_all_three_buttons(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    assert isinstance(view.btn_send_welcome, ctk.CTkButton)
    assert isinstance(view.btn_send_all, ctk.CTkButton)
    assert isinstance(view.btn_run_batch, ctk.CTkButton)


def test_send_welcome_button_calls_controller(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    view.btn_send_welcome.invoke()

    assert controller.welcome_clicked is True


def test_send_all_button_calls_controller(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    view.btn_send_all.invoke()

    assert controller.ad_hoc_clicked is True


def test_run_batch_button_calls_controller(ctk_root):
    controller = MockController()
    view = DashboardView(master=ctk_root, controller=controller)

    view.btn_run_batch.invoke()

    assert controller.batch_runner_opened is True
