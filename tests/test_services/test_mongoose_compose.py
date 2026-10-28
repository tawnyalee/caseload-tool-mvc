from src.services.mongoose_compose import department_matches


def test_department_label_matches_on_its_first_word_ignoring_case():
    assert department_matches("D424", "D424")
    assert department_matches("d424 Capstone", "D424")
    assert not department_matches("D4240", "D424")
    assert not department_matches("C769", "D424")
    assert not department_matches("", "D424")
