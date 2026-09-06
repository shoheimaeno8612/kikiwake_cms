import json
import random

import pytest

from kikiwake_cms.services.content_generation import (
    fix_missing_period,
    generate_contents,
    sample_specifications,
)


class FakeInteraction:
    def __init__(self, output_text):
        self.output_text = output_text


class FakeGenaiClient:
    def __init__(self, output_text):
        self._output_text = output_text

    def generate_json(self, **kwargs):
        return FakeInteraction(self._output_text)


def test_generate_contents_raises_and_dumps_debug_on_invalid_json(tmp_path, monkeypatch):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    genai_client = FakeGenaiClient("{not valid json")

    with pytest.raises(json.JSONDecodeError):
        generate_contents(genai_client, specifications=[{"level": "a1"}], gen_model="test-model")

    debug_files = list((tmp_path / "debug" / "content_generation").glob("*.txt"))
    assert len(debug_files) == 1
    assert debug_files[0].read_text() == "{not valid json"


def test_fix_missing_period_adds_period():
    assert fix_missing_period("Hello world") == "Hello world."


def test_fix_missing_period_keeps_existing_period():
    assert fix_missing_period("Hello world.") == "Hello world."


def test_sample_specifications_returns_requested_count():
    level_summary = [{"code": "a1", "level_id": 1, "count": 10}]
    target_summary = [{"code": "TOEIC", "target_id": 1, "count": 10}]
    category_summary = [{"code": "daily_life", "category_id": 1, "count": 10}]

    specs = sample_specifications(level_summary, target_summary, category_summary, 5)

    assert len(specs) == 5
    for spec in specs:
        assert spec["level"] == "a1"
        assert spec["target"] == "TOEIC"
        assert spec["category"] == "daily_life"
        assert spec["level_id"] == 1
        assert spec["target_id"] == 1
        assert spec["category_id"] == 1


def test_sample_specifications_prefers_less_frequent_parameters():
    # category "daily_life" は出現回数1、"business" は出現回数1000。
    # 逆数重み付けにより "daily_life" が高確率で選ばれるはず。
    # (category codeはcontent_data.GENRESのキーに存在する必要がある)
    random.seed(0)
    level_summary = [{"code": "a1", "level_id": 1, "count": 1}]
    target_summary = [{"code": "TOEIC", "target_id": 1, "count": 1}]
    category_summary = [
        {"code": "daily_life", "category_id": 1, "count": 1},
        {"code": "business", "category_id": 2, "count": 1000},
    ]

    specs = sample_specifications(level_summary, target_summary, category_summary, 100)
    rare_count = sum(1 for spec in specs if spec["category"] == "daily_life")

    assert rare_count > 90


def test_sample_specifications_does_not_mutate_input():
    level_summary = [{"code": "a1", "level_id": 1, "count": 5}]
    target_summary = [{"code": "TOEIC", "target_id": 1, "count": 5}]
    category_summary = [{"code": "daily_life", "category_id": 1, "count": 5}]

    sample_specifications(level_summary, target_summary, category_summary, 10)

    assert level_summary[0]["count"] == 5
    assert target_summary[0]["count"] == 5
    assert category_summary[0]["count"] == 5
