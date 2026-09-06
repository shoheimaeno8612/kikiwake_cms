import json

import pytest

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
