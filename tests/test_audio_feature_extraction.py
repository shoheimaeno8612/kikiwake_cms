import json
from types import SimpleNamespace

import pytest

from conftest import FakeResponse, FakeStorageClient, FakeSupabaseClient

from kikiwake_cms.services import audio_feature_extraction
from kikiwake_cms.services.audio_feature_extraction import (
    SentenceAudioFeatures,
    build_prompt,
    parse_result,
)


CONTENT = {
    "content_id": 1,
    "level": "b1",
    "sentences": [
        {"sentence_id": 10, "sentence": "Can you pick it up?", "sentence_index": 0},
        {"sentence_id": 11, "sentence": "I drank some water.", "sentence_index": 1},
    ],
}
SEGMENTS = [
    {"sentence_id": 10, "start_seconds": 0.0, "end_seconds": 2.3},
    {"sentence_id": 11, "start_seconds": 2.9, "end_seconds": 5.1},
]


def test_build_prompt_includes_feature_master_sentences_and_segments():
    prompt = build_prompt(CONTENT, SEGMENTS)

    # feature master (音声特徴のcode) が埋め込まれている
    assert "linking" in prompt
    assert "flapping" in prompt
    assert "assimilation" in prompt
    # sentence が埋め込まれている
    assert "pick it up" in prompt
    assert '"sentence_id": 10' in prompt
    # 発話区間が入力として渡されている
    assert "[Audio Segments]" in prompt
    assert '"start_seconds": 2.9' in prompt


def test_response_schema_is_features_only():
    # 発話区間の特定は analyze-audio-alignment に分離済み。
    # このサービスのレスポンスは result のみ。
    schema = SentenceAudioFeatures.model_json_schema()
    assert set(schema["properties"]) == {"result"}


def test_parse_result_returns_dict_on_valid_json():
    payload = {"result": []}
    assert parse_result(json.dumps(payload)) == payload


def test_parse_result_dumps_debug_and_raises_on_invalid_json(tmp_path, monkeypatch):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    with pytest.raises(json.JSONDecodeError):
        parse_result("{not valid json")

    debug_files = list(
        (tmp_path / "debug" / "audio_feature_extraction").glob("*.txt")
    )
    assert len(debug_files) == 1
    assert debug_files[0].read_text() == "{not valid json"


class FakeGenaiClient:
    def __init__(self, output_text):
        self._output_text = output_text
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self._output_text,
            usage=SimpleNamespace(to_dict=lambda: {}),
        )


def test_run_saves_model_used_for_extraction(tmp_path, monkeypatch):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    contents = [
        {
            "content_id": 1,
            "levels": {"level_id": 2, "code": "b1"},
            "sentences": CONTENT["sentences"],
            "audio": [
                {
                    "audio_id": 100,
                    "audio_path": "audio/1.mp3",
                    "sentences": SEGMENTS,
                    "feature_extracted_at": None,
                }
            ],
        }
    ]
    result = {
        "result": [
            {
                "sentence_id": 10,
                "feature_id": 3,
                "start_index": 1,
                "end_index": 3,
                "translation": None,
            }
        ]
    }

    supabase_client = FakeSupabaseClient(
        table_results={"contents": FakeResponse(data=contents)}
    )
    genai_client = FakeGenaiClient(json.dumps(result))
    monkeypatch.setattr(
        audio_feature_extraction, "GenaiClient", lambda settings: genai_client
    )
    monkeypatch.setattr(
        audio_feature_extraction, "SupabaseClient", lambda settings: supabase_client
    )
    monkeypatch.setattr(
        audio_feature_extraction, "StorageClient", lambda settings: FakeStorageClient()
    )

    audio_feature_extraction.run(count=1, gen_model="test-model", settings=None)

    rows = supabase_client.table_state["sentence_features"]
    assert len(rows) == 1
    # 解析に使ったモデル名が記録されている
    assert rows[0]["model"] == "test-model"
    assert genai_client.calls[0]["model"] == "test-model"
    # 音声特徴の行は従来どおり audio_id 付きで入る
    assert rows[0]["audio_id"] == 100
