#!/usr/bin/env python3
# src/dataset_generation.py

"""Production dataset generation engine for DAVYD.

The generation engine is intentionally UI-agnostic. Qt integration lives in
``DatasetGenerationWorker`` and communicates exclusively through signals.
"""

from __future__ import annotations

import csv
import inspect
import io
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot

from model_providers.base import BaseModelClient
from model_providers_manager import ModelProviderRegistry

logger = logging.getLogger(__name__)

DEFAULT_SEPARATOR = "|"
DEFAULT_WRAPPER = '"'
DEFAULT_BATCH_SIZE = 25
MAX_RETRIES = 3


class GenerationError(RuntimeError):
    """Raised when generation cannot produce a valid batch."""


class GenerationCancelled(RuntimeError):
    """Raised when a running generation job is cancelled."""


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    CATEGORY = "category"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: FieldType = FieldType.TEXT
    description: Optional[str] = None
    constraints: Mapping[str, Any] = field(default_factory=dict)
    example: Optional[Any] = None

    def prompt_schema(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
        }
        if self.description:
            payload["description"] = self.description
        if self.constraints:
            payload["constraints"] = dict(self.constraints)
        if self.example is not None:
            payload["example"] = self.example
        return payload


@dataclass(frozen=True)
class QualityProfile:
    temperature: float
    max_tokens: int
    default_batch_size: int


ProgressCallback = Callable[[int, str], None]
BatchCallback = Callable[[List[List[Any]]], None]
CancelCheck = Callable[[], bool]


class DatasetGenerator:
    """Generate validated synthetic records through a ``BaseModelClient``."""

    QUALITY_PROFILES: Dict[int, QualityProfile] = {
        1: QualityProfile(temperature=0.85, max_tokens=1200, default_batch_size=10),
        2: QualityProfile(temperature=0.65, max_tokens=2400, default_batch_size=25),
        3: QualityProfile(temperature=0.45, max_tokens=4200, default_batch_size=40),
    }

    def __init__(
        self,
        client: BaseModelClient,
        model_name: str,
        num_entries: int,
        quality_level: int = 2,
        batch_size: Optional[int] = None,
        separator: str = DEFAULT_SEPARATOR,
        wrapper: str = DEFAULT_WRAPPER,
        max_retries: int = MAX_RETRIES,
        post_processors: Optional[Sequence[Callable[[pd.DataFrame], pd.DataFrame]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        batch_callback: Optional[BatchCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
    ) -> None:
        if quality_level not in self.QUALITY_PROFILES:
            raise ValueError(f"Unsupported quality level: {quality_level}")
        if not isinstance(num_entries, int) or num_entries <= 0:
            raise ValueError("num_entries must be a positive integer")
        if not model_name:
            raise ValueError("model_name is required")
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")

        self.client = client
        self.model_name = model_name
        self.num_entries = num_entries
        self.quality = self.QUALITY_PROFILES[quality_level]
        self.batch_size = int(batch_size or self.quality.default_batch_size)
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self.separator = separator or DEFAULT_SEPARATOR
        self.wrapper = wrapper or DEFAULT_WRAPPER
        self.max_retries = max_retries
        self.post_processors = list(post_processors or [])
        self.progress_callback = progress_callback
        self.batch_callback = batch_callback
        self.cancel_check = cancel_check or (lambda: False)

    def generate_dataset(
        self,
        fields: Sequence[FieldSpec],
        examples: Optional[Sequence[Any]] = None,
    ) -> pd.DataFrame:
        normalized_fields = self._validate_fields(fields)
        rows = self._generate_rows(normalized_fields, examples or [])
        dataframe = pd.DataFrame(rows, columns=[field.name for field in normalized_fields])

        for processor in self.post_processors:
            processed = processor(dataframe)
            if not isinstance(processed, pd.DataFrame):
                raise TypeError("Post-processors must return a pandas.DataFrame")
            dataframe = processed

        return dataframe

    def _generate_rows(
        self,
        fields: Sequence[FieldSpec],
        examples: Sequence[Any],
    ) -> List[List[Any]]:
        all_rows: List[List[Any]] = []
        seen: set[tuple[str, ...]] = set()
        batch_number = 0
        stagnant_batches = 0

        while len(all_rows) < self.num_entries:
            self._raise_if_cancelled()
            batch_number += 1
            remaining = self.num_entries - len(all_rows)
            requested = min(self.batch_size, remaining)

            self._emit_progress(
                int((len(all_rows) / self.num_entries) * 100),
                f"Generating batch {batch_number}",
            )

            prompt = self._build_prompt(fields, examples, requested, batch_number)
            parsed_records = self._request_valid_batch(prompt, fields, requested)

            accepted: List[List[Any]] = []
            for record in parsed_records:
                row_key = tuple(self._dedupe_value(value) for value in record)
                if row_key in seen:
                    continue
                seen.add(row_key)
                accepted.append(record)
                if len(all_rows) + len(accepted) >= self.num_entries:
                    break

            if not accepted:
                stagnant_batches += 1
                if stagnant_batches >= self.max_retries:
                    raise GenerationError(
                        "The model repeatedly returned no new valid rows. "
                        "Try a different model, lower batch size, or simplify field constraints."
                    )
                continue

            stagnant_batches = 0
            all_rows.extend(accepted)

            if self.batch_callback:
                self.batch_callback(accepted)

            completed = min(100, int((len(all_rows) / self.num_entries) * 100))
            self._emit_progress(
                completed,
                f"Generated {len(all_rows)} of {self.num_entries} rows",
            )

        return all_rows[: self.num_entries]

    def _request_valid_batch(
        self,
        prompt: str,
        fields: Sequence[FieldSpec],
        requested: int,
    ) -> List[List[Any]]:
        failures: List[str] = []

        for attempt in range(1, self.max_retries + 1):
            self._raise_if_cancelled()
            try:
                raw = self._invoke_model(prompt)
                self._raise_if_cancelled()
                rows = self._parse_response(raw, fields)
                if rows:
                    return rows[:requested]
                raise GenerationError("Model response contained no valid rows")
            except GenerationCancelled:
                raise
            except Exception as exc:
                failures.append(f"attempt {attempt}: {exc}")
                logger.warning(
                    "Generation batch attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )

        raise GenerationError("; ".join(failures))

    def _invoke_model(self, prompt: str) -> str:
        method = self.client.generate_text
        kwargs: Dict[str, Any] = {}

        try:
            signature = inspect.signature(method)
            parameters = signature.parameters
            supports_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )

            optional_values = {
                "model_name": self.model_name,
                "model": self.model_name,
                "temperature": self.quality.temperature,
                "max_tokens": self.quality.max_tokens,
            }
            for name, value in optional_values.items():
                if supports_kwargs or name in parameters:
                    kwargs[name] = value
        except (TypeError, ValueError):
            logger.debug("Could not inspect provider generate_text signature")

        try:
            response = method(prompt, **kwargs)
        except TypeError:
            if not kwargs:
                raise
            logger.debug("Provider rejected optional generation kwargs; retrying prompt-only call")
            response = method(prompt)

        if response is None:
            raise GenerationError("Model provider returned no response")
        if not isinstance(response, str):
            response = str(response)
        response = response.strip()
        if not response:
            raise GenerationError("Model provider returned an empty response")
        return response

    def _build_prompt(
        self,
        fields: Sequence[FieldSpec],
        examples: Sequence[Any],
        batch_size: int,
        batch_number: int,
    ) -> str:
        schema_json = json.dumps(
            [field.prompt_schema() for field in fields],
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        example_payload = self._normalize_examples(examples, fields)
        examples_json = json.dumps(example_payload, ensure_ascii=False, indent=2, default=str)

        return (
            "You are DAVYD's synthetic-data generation engine.\n"
            f"Generate exactly {batch_size} new records for batch {batch_number}.\n\n"
            "SCHEMA\n"
            f"{schema_json}\n\n"
            "REFERENCE EXAMPLES\n"
            f"{examples_json if example_payload else '[]'}\n\n"
            "OUTPUT CONTRACT\n"
            "1. Return only one valid JSON array. Do not use Markdown fences or commentary.\n"
            "2. Every array element must be a JSON object.\n"
            "3. Every object must contain every schema field exactly once.\n"
            "4. Respect field types, descriptions, examples, and constraints.\n"
            "5. Produce varied, realistic synthetic values. Never copy a reference example verbatim unless unavoidable.\n"
            "6. Do not add fields that are not present in the schema.\n"
            f"7. The array must contain exactly {batch_size} objects.\n"
        )

    def _normalize_examples(
        self,
        examples: Sequence[Any],
        fields: Sequence[FieldSpec],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        field_names = [field.name for field in fields]

        for example in examples[:10]:
            if isinstance(example, Mapping):
                normalized.append({name: example.get(name) for name in field_names})
                continue
            if isinstance(example, Sequence) and not isinstance(example, (str, bytes)):
                values = list(example)
                if len(values) == len(field_names):
                    normalized.append(dict(zip(field_names, values)))
                continue
            if isinstance(example, str):
                parsed = self._parse_delimited_line(example, len(fields))
                if parsed:
                    normalized.append(dict(zip(field_names, parsed)))

        return normalized

    def _parse_response(
        self,
        raw: str,
        fields: Sequence[FieldSpec],
    ) -> List[List[Any]]:
        payload = self._extract_json_payload(raw)
        records: Iterable[Any]

        if payload is not None:
            if isinstance(payload, dict):
                candidate = payload.get("records", payload.get("data"))
                records = candidate if isinstance(candidate, list) else [payload]
            elif isinstance(payload, list):
                records = payload
            else:
                records = []
        else:
            records = [
                row
                for row in (
                    self._parse_delimited_line(line, len(fields))
                    for line in raw.splitlines()
                    if line.strip()
                )
                if row is not None
            ]

        validated: List[List[Any]] = []
        for record in records:
            try:
                validated.append(self._normalize_record(record, fields))
            except (ValueError, TypeError) as exc:
                logger.debug("Rejected generated record: %s", exc)

        return validated

    def _extract_json_payload(self, raw: str) -> Optional[Any]:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        starts = [position for position in (cleaned.find("["), cleaned.find("{")) if position >= 0]
        if not starts:
            return None
        start = min(starts)

        for end in range(len(cleaned), start, -1):
            candidate = cleaned[start:end].strip()
            if not candidate or candidate[-1] not in "]}":
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return None

    def _parse_delimited_line(self, line: str, ncols: int) -> Optional[List[str]]:
        line = line.strip()
        if not line:
            return None

        if len(self.separator) == 1 and len(self.wrapper) == 1:
            reader = csv.reader(
                io.StringIO(line),
                delimiter=self.separator,
                quotechar=self.wrapper,
                skipinitialspace=True,
            )
            parts = next(reader, [])
        else:
            parts = [part.strip() for part in line.split(self.separator)]
            if self.wrapper:
                parts = [part.strip().strip(self.wrapper) for part in parts]

        if len(parts) != ncols:
            return None
        return [part.strip() for part in parts]

    def _normalize_record(
        self,
        record: Any,
        fields: Sequence[FieldSpec],
    ) -> List[Any]:
        if isinstance(record, Mapping):
            missing = [field.name for field in fields if field.name not in record]
            if missing:
                raise ValueError(f"missing fields: {', '.join(missing)}")
            values = [record[field.name] for field in fields]
        elif isinstance(record, Sequence) and not isinstance(record, (str, bytes)):
            values = list(record)
            if len(values) != len(fields):
                raise ValueError("record has incorrect column count")
        else:
            raise TypeError("record must be an object or array")

        return [self._coerce_value(value, field) for value, field in zip(values, fields)]

    def _coerce_value(self, value: Any, field: FieldSpec) -> Any:
        constraints = dict(field.constraints or {})
        required = bool(constraints.get("required", constraints.get("nullable") is False))

        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                raise ValueError(f"{field.name} is required")
            return None

        if field.type == FieldType.NUMBER:
            number = float(value)
            if number.is_integer():
                number = int(number)
            minimum = constraints.get("min", constraints.get("minimum"))
            maximum = constraints.get("max", constraints.get("maximum"))
            if minimum is not None and number < minimum:
                raise ValueError(f"{field.name} below minimum")
            if maximum is not None and number > maximum:
                raise ValueError(f"{field.name} above maximum")
            return number

        if field.type == FieldType.BOOLEAN:
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
            raise ValueError(f"{field.name} is not boolean")

        if field.type == FieldType.DATETIME:
            timestamp = pd.to_datetime(value, errors="raise")
            if isinstance(timestamp, pd.Timestamp):
                return timestamp.to_pydatetime()
            if isinstance(timestamp, datetime):
                return timestamp
            return timestamp

        text = str(value).strip()
        if field.type == FieldType.CATEGORY:
            choices = constraints.get("choices", constraints.get("enum", constraints.get("categories")))
            if choices and text not in {str(choice) for choice in choices}:
                raise ValueError(f"{field.name} is outside allowed categories")

        min_length = constraints.get("min_length")
        max_length = constraints.get("max_length")
        if min_length is not None and len(text) < int(min_length):
            raise ValueError(f"{field.name} is shorter than min_length")
        if max_length is not None and len(text) > int(max_length):
            raise ValueError(f"{field.name} exceeds max_length")
        return text

    def _validate_fields(self, fields: Sequence[FieldSpec]) -> List[FieldSpec]:
        if not fields:
            raise ValueError("At least one field is required")
        names = [field.name.strip() for field in fields]
        if any(not name for name in names):
            raise ValueError("Field names cannot be blank")
        if len(set(names)) != len(names):
            raise ValueError("Field names must be unique")
        return list(fields)

    def _raise_if_cancelled(self) -> None:
        if self.cancel_check():
            raise GenerationCancelled("Generation cancelled")

    def _emit_progress(self, percent: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(max(0, min(100, percent)), message)

    @staticmethod
    def _dedupe_value(value: Any) -> str:
        if value is None:
            return "<null>"
        return str(value).strip().casefold()


class DatasetGenerationWorker(QObject):
    """QThread worker that owns one generation run."""

    progress_updated = Signal(int, str)
    batch_generated = Signal(list)
    generation_complete = Signal(pd.DataFrame)
    generation_cancelled = Signal(str)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, config: Dict[str, Any], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.config = dict(config)
        self._cancelled = False
        self._cancel_lock = Lock()

    @Slot()
    def run(self) -> None:
        try:
            provider = str(self.config.get("model_provider", "")).strip().lower()
            model = str(self.config.get("model_name", "")).strip()
            if not provider:
                raise ValueError("model_provider is required")
            if not model:
                raise ValueError("model_name is required")

            api_key = self.config.get("api_key") or None
            client = ModelProviderRegistry.get_model_client(provider, api_key)
            fields = self._build_field_specs(self.config)

            generator = DatasetGenerator(
                client=client,
                model_name=model,
                num_entries=int(self.config.get("num_entries", 100)),
                quality_level=int(self.config.get("quality_level", 2)),
                batch_size=int(self.config.get("batch_size", DEFAULT_BATCH_SIZE)),
                separator=str(self.config.get("section_separator", DEFAULT_SEPARATOR)),
                wrapper=str(
                    self.config.get(
                        "data_wrapper",
                        self.config.get("data_separator", DEFAULT_WRAPPER),
                    )
                ),
                max_retries=int(self.config.get("max_retries", MAX_RETRIES)),
                post_processors=self.config.get("post_processors") or [],
                progress_callback=self._emit_progress,
                batch_callback=self._emit_batch,
                cancel_check=self.is_cancelled,
            )

            self.progress_updated.emit(0, "Preparing generation")
            dataframe = generator.generate_dataset(
                fields,
                examples=self.config.get("examples") or [],
            )
            if self.is_cancelled():
                raise GenerationCancelled("Generation cancelled")

            self.progress_updated.emit(100, "Complete")
            self.generation_complete.emit(dataframe)

        except GenerationCancelled as exc:
            logger.info("Dataset generation cancelled")
            self.generation_cancelled.emit(str(exc))
        except Exception as exc:
            logger.exception("Generation worker failed")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()

    def _emit_progress(self, percent: int, message: str) -> None:
        if not self.is_cancelled():
            self.progress_updated.emit(percent, message)

    def _emit_batch(self, batch: List[List[Any]]) -> None:
        if not self.is_cancelled():
            self.batch_generated.emit(batch)

    @Slot()
    def cancel(self) -> None:
        """Set the cancellation flag immediately and safely from any thread."""
        with self._cancel_lock:
            self._cancelled = True

    # Compatibility with older MainWindow.closeEvent implementations.
    stop = cancel

    def is_cancelled(self) -> bool:
        with self._cancel_lock:
            return self._cancelled

    @staticmethod
    def _build_field_specs(config: Mapping[str, Any]) -> List[FieldSpec]:
        schema = config.get("schema")
        raw_fields = config.get("fields") or []

        if isinstance(schema, Mapping) and schema:
            specs: List[FieldSpec] = []
            for name, definition in schema.items():
                specs.append(DatasetGenerationWorker._field_spec_from_definition(str(name), definition))
            return specs

        specs = []
        for raw_field in raw_fields:
            if isinstance(raw_field, Mapping):
                name = str(raw_field.get("name", "")).strip()
                specs.append(DatasetGenerationWorker._field_spec_from_definition(name, raw_field))
            else:
                specs.append(FieldSpec(name=str(raw_field).strip()))
        return specs

    @staticmethod
    def _field_spec_from_definition(name: str, definition: Any) -> FieldSpec:
        if not name:
            raise ValueError("Schema contains a field without a name")

        if not isinstance(definition, Mapping):
            if isinstance(definition, str) and definition.strip():
                inferred = DatasetGenerationWorker._parse_field_type(definition)
                return FieldSpec(name=name, type=inferred)
            return FieldSpec(name=name)

        raw_type = definition.get("type", definition.get("field_type", "text"))
        constraints = definition.get("constraints") or {}
        if not isinstance(constraints, Mapping):
            raise ValueError(f"Constraints for field '{name}' must be an object")

        return FieldSpec(
            name=name,
            type=DatasetGenerationWorker._parse_field_type(raw_type),
            description=definition.get("description"),
            constraints=dict(constraints),
            example=definition.get("example"),
        )

    @staticmethod
    def _parse_field_type(value: Any) -> FieldType:
        normalized = str(value).strip().lower()
        aliases = {
            "str": FieldType.TEXT,
            "string": FieldType.TEXT,
            "text": FieldType.TEXT,
            "int": FieldType.NUMBER,
            "integer": FieldType.NUMBER,
            "float": FieldType.NUMBER,
            "double": FieldType.NUMBER,
            "number": FieldType.NUMBER,
            "bool": FieldType.BOOLEAN,
            "boolean": FieldType.BOOLEAN,
            "date": FieldType.DATETIME,
            "datetime": FieldType.DATETIME,
            "timestamp": FieldType.DATETIME,
            "category": FieldType.CATEGORY,
            "categorical": FieldType.CATEGORY,
            "enum": FieldType.CATEGORY,
        }
        return aliases.get(normalized, FieldType.TEXT)
