import copy
import json
from types import SimpleNamespace

from conftest import FakeResponse, FakeSupabaseClient

from kikiwake_cms.services import feature_extraction


class FreshResponse(FakeResponse):
    """クエリのたびに新しいdictを返すレスポンス。

    feature_extraction.run() はプロンプト整形時に取得結果のdictを書き換えるため、
    同じオブジェクトを使い回すと2周目以降で壊れてしまう。実際のSupabaseと同じく
    クエリごとに独立したdictが返る状況を再現する。
    """

    @property
    def data(self):
        return copy.deepcopy(self._data)

    @data.setter
    def data(self, value):
        self._data = value


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


CONTENTS = [
    {
        "content_id": 1,
        "levels": {"level_id": 2, "code": "b1"},
        "sentences": [
            {
                "sentence_id": 10,
                "sentence": "I have been there.",
                "sentence_index": 0,
                "sentence_features": [],
            }
        ],
    }
]
RESULT = {
    "result": [
        {
            "content_id": 1,
            "sentence_id": 10,
            "feature_id": 3,
            "start_index": 1,
            "end_index": 3,
            "translation": None,
        }
    ]
}


def test_run_saves_model_used_for_extraction(tmp_path, monkeypatch):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    supabase_client = FakeSupabaseClient(
        table_results={"contents": FreshResponse(data=CONTENTS)}
    )
    genai_client = FakeGenaiClient(json.dumps(RESULT))
    monkeypatch.setattr(feature_extraction, "GenaiClient", lambda settings: genai_client)
    monkeypatch.setattr(
        feature_extraction, "SupabaseClient", lambda settings: supabase_client
    )

    feature_extraction.run(count=1, gen_model="test-model", settings=None)

    rows = supabase_client.table_state["sentence_features"]
    assert rows
    # 解析に使ったモデル名が全行に記録されている
    assert all(row["model"] == "test-model" for row in rows)
    assert genai_client.calls[0]["model"] == "test-model"
    # 既存カラムも従来どおり保存されている
    assert rows[0]["sentence_id"] == 10
    assert rows[0]["feature_id"] == 3
