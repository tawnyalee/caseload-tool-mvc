import pytest

from src.services.name_utils import resolve_first_last_name


@pytest.mark.parametrize("entered, shown", [
    ("JANE", "Jane"),
    ("jane", "Jane"),
    ("Jane", "Jane"),
    ("DeShawn", "DeShawn"),
    ("McKenzie", "McKenzie"),
    ("deShawn", "deShawn"),
])
def test_only_all_caps_or_all_lowercase_first_names_are_recapitalized(entered, shown):
    assert resolve_first_last_name(f"{entered} Doe")[0] == shown


@pytest.mark.parametrize("entered, shown", [("johnny", "Johnny"), ("JOHNNY", "Johnny"), ("JoJo", "JoJo")])
def test_preferred_name_wins_and_follows_the_same_rule(entered, shown):
    assert resolve_first_last_name("JOHN SMITH", entered) == (shown, "SMITH")


def test_blank_name_stays_blank():
    assert resolve_first_last_name("") == ("", "")
