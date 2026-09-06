import json

import pytest

from kikiwake_cms.services.audio_feature_extraction import build_prompt, parse_analysis


CONTENT = {
    "content_id": 1,
    "level": "b1",
    "sentences": [
        {"sentence_id": 10, "sentence": "Can you pick it up?", "sentence_index": 0},
        {"sentence_id": 11, "sentence": "I drank some water.", "sentence_index": 1},
    ],
}


def test_build_prompt_includes_feature_master_and_sentences():
    prompt = build_prompt(CONTENT, known_segments=None)

    # feature master (音声特徴のcode) が埋め込まれている
    assert "linking" in prompt
    assert "flapping" in prompt
    assert "assimilation" in prompt
    # sentence が埋め込まれている
    assert "pick it up" in prompt
    assert '"sentence_id": 10' in prompt


def test_build_prompt_omits_known_segments_block_when_none():
    assert "[Known Audio Segments]" not in build_prompt(CONTENT, known_segments=None)


def test_build_prompt_includes_known_segments_block_when_present():
    segments = [{"sentence_id": 10, "start_seconds": 0.0, "end_seconds": 2.3}]
    prompt = build_prompt(CONTENT, known_segments=segments)

    assert "[Known Audio Segments]" in prompt
    assert '"start_seconds": 0.0' in prompt


def test_parse_analysis_returns_dict_on_valid_json():
    payload = {"segments": [], "result": []}
    assert parse_analysis(json.dumps(payload)) == payload


def test_parse_analysis_dumps_debug_and_raises_on_invalid_json(tmp_path, monkeypatch):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    with pytest.raises(json.JSONDecodeError):
        parse_analysis("{not valid json")

    debug_files = list(
        (tmp_path / "debug" / "audio_feature_extraction").glob("*.txt")
    )
    assert len(debug_files) == 1
    assert debug_files[0].read_text() == "{not valid json"
