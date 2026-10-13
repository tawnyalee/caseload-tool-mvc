import pytest
from pathlib import Path
from src.models.saved_batch import SavedBatch
from src.services.saved_batch_repository import SavedBatchRepository


@pytest.fixture
def temp_saved_batch_repo(tmp_path: Path) -> SavedBatchRepository:
    """Fixture to provide a SavedBatchRepository backed by a temporary JSON file."""
    test_file = tmp_path / "saved_batches.json"
    return SavedBatchRepository(data_file=test_file)


def test_starts_empty(temp_saved_batch_repo: SavedBatchRepository):
    assert temp_saved_batch_repo.load_batches() == []


def test_save_batch_creates_a_new_batch(temp_saved_batch_repo: SavedBatchRepository):
    batch = temp_saved_batch_repo.save_batch("Weekly Follow-ups", ["a1", "a2"])

    assert batch.name == "Weekly Follow-ups"
    assert batch.action_ids == ["a1", "a2"]

    loaded = temp_saved_batch_repo.load_batches()
    assert len(loaded) == 1
    assert loaded[0].id == batch.id
    assert loaded[0].action_ids == ["a1", "a2"]


def test_save_batch_round_trips_action_id_order(temp_saved_batch_repo: SavedBatchRepository):
    temp_saved_batch_repo.save_batch("Term Start", ["a3", "a1", "a2"])

    loaded = temp_saved_batch_repo.load_batches()
    assert loaded[0].action_ids == ["a3", "a1", "a2"]


def test_save_batch_with_existing_name_overwrites_instead_of_duplicating(
    temp_saved_batch_repo: SavedBatchRepository,
):
    first = temp_saved_batch_repo.save_batch("Weekly Follow-ups", ["a1"])
    second = temp_saved_batch_repo.save_batch("weekly follow-ups", ["a2", "a3"])  # case-insensitive match

    assert second.id == first.id  # same batch, not a new one

    loaded = temp_saved_batch_repo.load_batches()
    assert len(loaded) == 1
    assert loaded[0].action_ids == ["a2", "a3"]


def test_save_batch_with_different_name_creates_a_second_batch(temp_saved_batch_repo: SavedBatchRepository):
    temp_saved_batch_repo.save_batch("Weekly Follow-ups", ["a1"])
    temp_saved_batch_repo.save_batch("Term Start", ["a2"])

    loaded = temp_saved_batch_repo.load_batches()
    assert len(loaded) == 2
    assert {b.name for b in loaded} == {"Weekly Follow-ups", "Term Start"}


def test_delete_batch_removes_it(temp_saved_batch_repo: SavedBatchRepository):
    batch = temp_saved_batch_repo.save_batch("Weekly Follow-ups", ["a1"])

    result = temp_saved_batch_repo.delete_batch(batch.id)

    assert result is True
    assert temp_saved_batch_repo.load_batches() == []


def test_delete_batch_returns_false_for_unknown_id(temp_saved_batch_repo: SavedBatchRepository):
    assert temp_saved_batch_repo.delete_batch("does-not-exist") is False


def test_delete_batch_leaves_other_batches_untouched(temp_saved_batch_repo: SavedBatchRepository):
    keep = temp_saved_batch_repo.save_batch("Keep Me", ["a1"])
    remove = temp_saved_batch_repo.save_batch("Remove Me", ["a2"])

    temp_saved_batch_repo.delete_batch(remove.id)

    loaded = temp_saved_batch_repo.load_batches()
    assert len(loaded) == 1
    assert loaded[0].id == keep.id
