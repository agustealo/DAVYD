from __future__ import annotations

import json
import re

import pytest

from dataset_generation import DatasetGenerator, FieldSpec, FieldType, GenerationCancelled


class FakeJsonClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_text(self, prompt: str, **_kwargs) -> str:
        self.calls += 1
        count = int(re.search(r"Generate exactly (\d+) new records", prompt).group(1))
        return json.dumps(
            [
                {
                    "name": f"person-{self.calls}-{index}",
                    "age": 20 + index,
                    "active": index % 2 == 0,
                }
                for index in range(count)
            ]
        )


FIELDS = [
    FieldSpec("name", FieldType.TEXT, constraints={"required": True}),
    FieldSpec("age", FieldType.NUMBER, constraints={"min": 18, "max": 90}),
    FieldSpec("active", FieldType.BOOLEAN),
]


def test_generation_streams_real_batches_and_reaches_exact_row_count() -> None:
    batches = []
    progress = []
    dataframe = DatasetGenerator(
        FakeJsonClient(),
        "fake",
        23,
        batch_size=10,
        batch_callback=batches.append,
        progress_callback=lambda percent, message: progress.append((percent, message)),
    ).generate_dataset(FIELDS)

    assert dataframe.shape == (23, 3)
    assert [len(batch) for batch in batches] == [10, 10, 3]
    assert progress[-1][0] == 100


def test_pipe_delimiter_is_literal_not_regex() -> None:
    class DelimitedClient:
        def generate_text(self, _prompt: str) -> str:
            return '"a"|"21"|"true"\n"b"|"22"|"false"'

    dataframe = DatasetGenerator(
        DelimitedClient(),
        "fake",
        2,
        batch_size=2,
    ).generate_dataset(FIELDS)

    assert dataframe["name"].tolist() == ["a", "b"]
    assert dataframe["active"].tolist() == [True, False]


def test_cancellation_is_checked_before_provider_work() -> None:
    with pytest.raises(GenerationCancelled):
        DatasetGenerator(
            FakeJsonClient(),
            "fake",
            1,
            cancel_check=lambda: True,
        ).generate_dataset(FIELDS)
