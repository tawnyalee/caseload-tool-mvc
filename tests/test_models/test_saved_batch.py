from src.models.saved_batch import SavedBatch


def test_saved_batch_generates_id_when_not_provided():
    batch = SavedBatch(name="Weekly Follow-ups")
    assert batch.id
    assert isinstance(batch.id, str)


def test_saved_batch_uses_provided_id():
    batch = SavedBatch(name="Weekly Follow-ups", batch_id="batch-123")
    assert batch.id == "batch-123"


def test_saved_batch_action_ids_default_empty_list():
    batch = SavedBatch(name="Weekly Follow-ups")
    assert batch.action_ids == []


def test_saved_batch_preserves_action_id_order():
    batch = SavedBatch(name="Weekly Follow-ups", action_ids=["a3", "a1", "a2"])
    assert batch.action_ids == ["a3", "a1", "a2"]
