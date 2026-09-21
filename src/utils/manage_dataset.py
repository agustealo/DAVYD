from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable, List, Optional
from uuid import uuid4

import pandas as pd

logger = logging.getLogger(__name__)


class DatasetManager:
    """Canonical local dataset storage for active, archived, and merged data."""

    def __init__(self, temp_dir: str, archive_dir: str, merged_dir: str = "data_bin/merged_datasets") -> None:
        self.temp_dir = Path(temp_dir)
        self.archive_dir = Path(archive_dir)
        self.merged_dir = Path(merged_dir)
        self._memory_limit_mb = 1024
        self._ensure_directories_exist()

    def _ensure_directories_exist(self) -> None:
        for path in (self.temp_dir, self.archive_dir, self.merged_dir):
            path.mkdir(parents=True, exist_ok=True)

    def set_memory_limit(self, megabytes: int) -> None:
        if megabytes < 128:
            raise ValueError("Dataset memory limit must be at least 128 MB")
        self._memory_limit_mb = int(megabytes)
        logger.info("DatasetManager memory limit set to %s MB", self._memory_limit_mb)

    def _list(self, directory: Path) -> List[str]:
        return sorted(
            p.name for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in {".csv", ".json", ".parquet"} and p.stat().st_size > 0
        )

    def list_datasets(self) -> List[str]:
        return self._list(self.temp_dir)

    def list_archived_datasets(self) -> List[str]:
        return self._list(self.archive_dir)

    def list_merged_datasets(self) -> List[str]:
        return self._list(self.merged_dir)

    def _resolve_named_dataset(self, name: str, directory: Path) -> Path:
        candidate = (directory / Path(name).name).resolve()
        root = directory.resolve()
        if root not in candidate.parents and candidate != root:
            raise ValueError("Dataset path escapes managed directory")
        return candidate

    def _load_path(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            frame = pd.read_csv(path)
        elif suffix == ".json":
            frame = pd.read_json(path)
        elif suffix == ".parquet":
            frame = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported dataset format: {suffix}")
        memory_mb = frame.memory_usage(deep=True).sum() / (1024 * 1024)
        if memory_mb > self._memory_limit_mb:
            raise MemoryError(
                f"Dataset requires {memory_mb:.1f} MB, above the configured {self._memory_limit_mb} MB limit"
            )
        return frame

    def load_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        try:
            return self._load_path(self._resolve_named_dataset(dataset_name, self.temp_dir))
        except Exception:
            logger.exception("Failed to load dataset %s", dataset_name)
            return None

    def load_archived_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        try:
            return self._load_path(self._resolve_named_dataset(dataset_name, self.archive_dir))
        except Exception:
            logger.exception("Failed to load archived dataset %s", dataset_name)
            return None

    def load_merged_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        try:
            return self._load_path(self._resolve_named_dataset(dataset_name, self.merged_dir))
        except Exception:
            logger.exception("Failed to load merged dataset %s", dataset_name)
            return None

    def _save(self, df: pd.DataFrame, filename: str, directory: Path) -> Path:
        if df is None:
            raise ValueError("DataFrame is required")
        path = self._resolve_named_dataset(filename, directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df.to_csv(path, index=False)
        elif suffix == ".json":
            df.to_json(path, orient="records", indent=2, date_format="iso")
        elif suffix == ".parquet":
            df.to_parquet(path, index=False)
        else:
            raise ValueError(f"Unsupported dataset format: {suffix}")
        return path

    def save_csv_file(self, df: pd.DataFrame, filename: str) -> None:
        self._save(df, filename if filename.endswith(".csv") else f"{filename}.csv", self.temp_dir)

    def save_json_file(self, df: pd.DataFrame, filename: str) -> None:
        self._save(df, filename if filename.endswith(".json") else f"{filename}.json", self.temp_dir)

    def save_parquet_file(self, df: pd.DataFrame, filename: str) -> None:
        self._save(df, filename if filename.endswith(".parquet") else f"{filename}.parquet", self.temp_dir)

    def archive_dataset(self, dataset_path: str) -> bool:
        try:
            source = Path(dataset_path)
            if not source.is_absolute():
                source = self._resolve_named_dataset(dataset_path, self.temp_dir)
            if not source.exists():
                raise FileNotFoundError(source)
            target = self._resolve_named_dataset(source.name, self.archive_dir)
            shutil.move(str(source), str(target))
            return True
        except Exception:
            logger.exception("Failed to archive dataset %s", dataset_path)
            return False

    def restore_archived_dataset(self, dataset_name: str) -> bool:
        try:
            source = self._resolve_named_dataset(dataset_name, self.archive_dir)
            target = self._resolve_named_dataset(dataset_name, self.temp_dir)
            if not source.exists():
                raise FileNotFoundError(source)
            shutil.move(str(source), str(target))
            return True
        except Exception:
            logger.exception("Failed to restore dataset %s", dataset_name)
            return False

    def delete_dataset(self, dataset_name: str) -> bool:
        try:
            raw = Path(dataset_name)
            candidates = [raw] if raw.is_absolute() else [
                self._resolve_named_dataset(dataset_name, self.temp_dir),
                self._resolve_named_dataset(dataset_name, self.archive_dir),
                self._resolve_named_dataset(dataset_name, self.merged_dir),
            ]
            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    candidate.unlink()
                    return True
            raise FileNotFoundError(dataset_name)
        except Exception:
            logger.exception("Failed to delete dataset %s", dataset_name)
            return False

    def merge_datasets(self, dataset_names: Iterable[str], output_name: str) -> bool:
        frames: List[pd.DataFrame] = []
        try:
            for name in dataset_names:
                frame = self.load_dataset(name)
                if frame is None:
                    frame = self.load_archived_dataset(name)
                if frame is None:
                    frame = self.load_merged_dataset(name)
                if frame is not None:
                    frames.append(frame)
            if not frames:
                raise ValueError("No valid datasets selected for merge")
            merged = pd.concat(frames, ignore_index=True, sort=False)
            if not Path(output_name).suffix:
                output_name += ".csv"
            self._save(merged, output_name, self.merged_dir)
            return True
        except Exception:
            logger.exception("Failed to merge datasets")
            return False

    def get_temp_filename(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}.csv"

    def cleanup(self) -> None:
        """No destructive cleanup on normal shutdown; storage is persistent by design."""
        return
