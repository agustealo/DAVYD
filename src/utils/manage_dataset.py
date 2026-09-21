from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable, List, Optional
from uuid import uuid4

import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED_DATASET_SUFFIXES = {".csv", ".json", ".parquet"}


class DatasetManager:
    """Canonical local dataset storage for active, archived, and merged data."""

    def __init__(self, temp_dir: str, archive_dir: str, merged_dir: str) -> None:
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
            path.name
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_DATASET_SUFFIXES
            and path.stat().st_size > 0
        )

    def list_datasets(self) -> List[str]:
        return self._list(self.temp_dir)

    def list_archived_datasets(self) -> List[str]:
        return self._list(self.archive_dir)

    def list_merged_datasets(self) -> List[str]:
        return self._list(self.merged_dir)

    @staticmethod
    def _validate_dataset_suffix(path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED_DATASET_SUFFIXES:
            raise ValueError(f"Unsupported dataset format: {path.suffix.lower() or '<none>'}")

    def _resolve_named_dataset(self, name: str, directory: Path) -> Path:
        raw = Path(str(name))
        if raw.is_absolute() or len(raw.parts) != 1 or raw.name in {"", ".", ".."}:
            raise ValueError("Dataset name must be a single file name")

        candidate = (directory / raw.name).resolve()
        root = directory.resolve()
        if candidate.parent != root:
            raise ValueError("Dataset path escapes managed directory")

        self._validate_dataset_suffix(candidate)
        return candidate

    def _resolve_dataset_reference(self, value: str, directory: Path) -> Path:
        raw = Path(str(value)).expanduser()
        if not raw.is_absolute():
            return self._resolve_named_dataset(str(value), directory)

        candidate = raw.resolve()
        root = directory.resolve()
        if candidate.parent != root:
            raise ValueError("Dataset path is outside the managed directory")

        self._validate_dataset_suffix(candidate)
        return candidate

    def _load_path(self, path: Path) -> pd.DataFrame:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)

        self._validate_dataset_suffix(path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            frame = pd.read_csv(path)
        elif suffix == ".json":
            frame = pd.read_json(path)
        else:
            frame = pd.read_parquet(path)

        memory_mb = frame.memory_usage(deep=True).sum() / (1024 * 1024)
        if memory_mb > self._memory_limit_mb:
            raise MemoryError(
                f"Dataset requires {memory_mb:.1f} MB, above the configured "
                f"{self._memory_limit_mb} MB limit"
            )
        return frame

    def load_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        try:
            return self._load_path(self._resolve_dataset_reference(dataset_name, self.temp_dir))
        except Exception:
            logger.exception("Failed to load dataset %s", dataset_name)
            return None

    def load_archived_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        try:
            return self._load_path(
                self._resolve_dataset_reference(dataset_name, self.archive_dir)
            )
        except Exception:
            logger.exception("Failed to load archived dataset %s", dataset_name)
            return None

    def load_merged_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        try:
            return self._load_path(self._resolve_dataset_reference(dataset_name, self.merged_dir))
        except Exception:
            logger.exception("Failed to load merged dataset %s", dataset_name)
            return None

    def _save(self, df: pd.DataFrame, filename: str, directory: Path) -> Path:
        if df is None:
            raise ValueError("DataFrame is required")

        path = self._resolve_named_dataset(filename, directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        staging = path.with_name(f".{path.stem}.{uuid4().hex}.tmp{suffix}")

        try:
            if suffix == ".csv":
                df.to_csv(staging, index=False)
            elif suffix == ".json":
                df.to_json(staging, orient="records", indent=2, date_format="iso")
            else:
                df.to_parquet(staging, index=False)
            staging.replace(path)
        finally:
            staging.unlink(missing_ok=True)

        return path

    def save_csv_file(self, df: pd.DataFrame, filename: str) -> None:
        self._save(df, filename if filename.endswith(".csv") else f"{filename}.csv", self.temp_dir)

    def save_json_file(self, df: pd.DataFrame, filename: str) -> None:
        self._save(df, filename if filename.endswith(".json") else f"{filename}.json", self.temp_dir)

    def save_parquet_file(self, df: pd.DataFrame, filename: str) -> None:
        self._save(
            df,
            filename if filename.endswith(".parquet") else f"{filename}.parquet",
            self.temp_dir,
        )

    def archive_dataset(self, dataset_path: str) -> bool:
        try:
            source = self._resolve_dataset_reference(dataset_path, self.temp_dir)
            if not source.exists() or not source.is_file():
                raise FileNotFoundError(source)

            target = self._resolve_named_dataset(source.name, self.archive_dir)
            if target.exists():
                raise FileExistsError(target)

            shutil.move(str(source), str(target))
            return True
        except Exception:
            logger.exception("Failed to archive dataset %s", dataset_path)
            return False

    def restore_archived_dataset(self, dataset_name: str) -> bool:
        try:
            source = self._resolve_dataset_reference(dataset_name, self.archive_dir)
            if not source.exists() or not source.is_file():
                raise FileNotFoundError(source)

            target = self._resolve_named_dataset(source.name, self.temp_dir)
            if target.exists():
                raise FileExistsError(target)

            shutil.move(str(source), str(target))
            return True
        except Exception:
            logger.exception("Failed to restore dataset %s", dataset_name)
            return False

    def delete_dataset(self, dataset_name: str) -> bool:
        try:
            raw = Path(str(dataset_name)).expanduser()
            if raw.is_absolute():
                candidate = raw.resolve()
                managed_roots = {
                    self.temp_dir.resolve(),
                    self.archive_dir.resolve(),
                    self.merged_dir.resolve(),
                }
                if candidate.parent not in managed_roots:
                    raise ValueError("Dataset path is outside DAVYD-managed storage")
                self._validate_dataset_suffix(candidate)
                candidates = [candidate]
            else:
                candidates = [
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
            normalized_output = output_name
            if not Path(normalized_output).suffix:
                normalized_output += ".csv"
            self._save(merged, normalized_output, self.merged_dir)
            return True
        except Exception:
            logger.exception("Failed to merge datasets")
            return False

    def get_temp_filename(self, prefix: str) -> str:
        safe_prefix = "".join(character for character in str(prefix) if character.isalnum() or character in {"-", "_"})
        safe_prefix = safe_prefix.strip("-_ ") or "dataset"
        return f"{safe_prefix}_{uuid4().hex}.csv"

    def cleanup(self) -> None:
        """No destructive cleanup on normal shutdown; storage is persistent by design."""
        return
