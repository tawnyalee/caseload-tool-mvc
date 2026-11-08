from src.services.mongoose_compose import department_matches


def test_department_label_matches_on_its_first_word_ignoring_case():
    assert department_matches("D424", "D424")
    assert department_matches("d424 Capstone", "D424")
    assert not department_matches("D4240", "D424")
    assert not department_matches("C769", "D424")
    assert not department_matches("", "D424")


from unittest.mock import MagicMock

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.services.mongoose_compose import confirm_scheduled


def test_schedule_counts_once_mongoose_closes_the_form():
    name_box = MagicMock()
    confirm_scheduled(MagicMock(), name_box)
    assert name_box.wait_for.call_args.kwargs["state"] == "hidden"


def test_a_form_left_open_after_schedule_is_a_failure_not_a_success():
    name_box = MagicMock()
    name_box.wait_for.side_effect = PlaywrightTimeoutError("still there")
    with pytest.raises(RuntimeError, match="may not be scheduled"):
        confirm_scheduled(MagicMock(), name_box)
