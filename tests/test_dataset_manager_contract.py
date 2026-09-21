from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from utils.manage_dataset import DatasetManager


@pytest.fixture
def manager(tmp_path: Path) -> DatasetManager:
    return DatasetManager(
        temp_dir=str(tmp_path / "active"),
        archive_dir=str(tmp_path / "archive"),
        merged_dir=str(tmp_path / "merged"),
    )


def test_delete_rejects_external_absolute_path(manager: DatasetManager, tmp_path: Path) -> None:
    external = tmp_path / "outside.csv"
    external.write_text("value\nkeep\n", encoding="utf-8")

    assert manager.delete_dataset(str(external)) is False
    assert external.exists()


def test_archive_rejects_external_absolute_path(manager: DatasetManager, tmp_path: Path) -> None:
    external = tmp_path / "outside.csv"
    external.write_text("value\nkeep\n", encoding="utf-8")

    assert manager.archive_dataset(str(external)) is False
    assert external.exists()
    assert not (manager.archive_dir / external.name).exists()


def test_managed_absolute_path_can_be_archived_and_restored(manager: DatasetManager) -> None:
    frame = pd.DataFrame({"value": ["one", "two"]})
    manager.save_csv_file(frame, "sample.csv")
    active = manager.temp_dir / "sample.csv"

    assert manager.archive_dataset(str(active)) is True
    archived = manager.archive_dir / "sample.csv"
    assert not active.exists()
    assert archived.exists()

    assert manager.restore_archived_dataset(str(archived)) is True
    assert active.exists()
    assert not archived.exists()
    pd.testing.assert_frame_equal(pd.read_csv(active), frame)


def test_archive_does_not_overwrite_existing_dataset(manager: DatasetManager) -> None:
    active = manager.temp_dir / "sample.csv"
    archived = manager.archive_dir / "sample.csv"
    active.write_text("value\nnew\n", encoding="utf-8")
    archived.write_text("value\nexisting\n", encoding="utf-8")

    assert manager.archive_dataset("sample.csv") is False
    assert active.read_text(encoding="utf-8") == "value\nnew\n"
    assert archived.read_text(encoding="utf-8") == "value\nexisting\n"


def test_relative_nested_paths_are_rejected(manager: DatasetManager) -> None:
    assert manager.load_dataset("../outside.csv") is None
    assert manager.delete_dataset("../outside.csv") is False
    assert manager.archive_dataset("../outside.csv") is False


def test_save_round_trip_leaves_no_staging_files(manager: DatasetManager) -> None:
    frame = pd.DataFrame({"number": [1, 2], "label": ["a", "b"]})

    manager.save_json_file(frame, "roundtrip.json")
    loaded = manager.load_dataset("roundtrip.json")

    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, frame)
    assert not list(manager.temp_dir.glob(".*.tmp.*"))


def test_delete_accepts_only_managed_dataset_suffixes(manager: DatasetManager) -> None:
    non_dataset = manager.temp_dir / "notes.txt"
    non_dataset.write_text("do not delete", encoding="utf-8")

    assert manager.delete_dataset(str(non_dataset)) is False
    assert non_dataset.exists()
