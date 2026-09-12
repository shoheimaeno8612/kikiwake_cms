import pytest

from kikiwake_cms.config import gemini_api_key_env_vars, load_gemini_api_keys


@pytest.fixture(autouse=True)
def clear_gemini_env(monkeypatch):
    # 実行環境の.envが読み込まれている場合があるので、設定済みのキーを全て消してから始める。
    for env_var in gemini_api_key_env_vars():
        monkeypatch.delenv(env_var, raising=False)


def test_loads_all_keys_in_fallback_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key2")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key3")

    assert load_gemini_api_keys() == ("key1", "key2", "key3")


def test_optional_keys_can_be_omitted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key1")

    assert load_gemini_api_keys() == ("key1",)


def test_loads_keys_beyond_the_third(monkeypatch):
    # 本数に上限を設けていないので、連番を足すだけでフォールバック先が増える。
    for index, key in enumerate(["key2", "key3", "key4", "key5"], start=2):
        monkeypatch.setenv(f"GEMINI_API_KEY_{index}", key)
    monkeypatch.setenv("GEMINI_API_KEY", "key1")

    assert load_gemini_api_keys() == ("key1", "key2", "key3", "key4", "key5")


def test_orders_keys_numerically(monkeypatch):
    # 文字列順では "_10" が "_2" より前に来てしまうため、添字の数値順であることを確かめる。
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key2")
    monkeypatch.setenv("GEMINI_API_KEY_10", "key10")

    assert load_gemini_api_keys() == ("key1", "key2", "key10")


def test_ignores_blank_keys(monkeypatch):
    # .env.example をコピーしただけの空欄をフォールバック先に含めない。
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "  ")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key3")

    assert load_gemini_api_keys() == ("key1", "key3")


def test_skips_unset_numbers(monkeypatch):
    # 途中の番号を消しただけで以降のキーが無視されると、意図せず本数が減ってしまう。
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key3")

    assert load_gemini_api_keys() == ("key1", "key3")


def test_ignores_unrelated_env_vars(monkeypatch):
    # 添字が数値でないものは別用途の環境変数なのでキーとして拾わない。
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_ENV", "not-a-key")

    assert load_gemini_api_keys() == ("key1",)


def test_deduplicates_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key1")

    assert load_gemini_api_keys() == ("key1",)


def test_raises_when_primary_key_is_missing():
    with pytest.raises(KeyError):
        load_gemini_api_keys()
