import pytest

from kikiwake_cms.config import GEMINI_API_KEY_ENV_VARS, load_gemini_api_keys


@pytest.fixture(autouse=True)
def clear_gemini_env(monkeypatch):
    for env_var in GEMINI_API_KEY_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_loads_all_keys_in_fallback_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key2")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key3")

    assert load_gemini_api_keys() == ("key1", "key2", "key3")


def test_optional_keys_can_be_omitted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key1")

    assert load_gemini_api_keys() == ("key1",)


def test_ignores_blank_keys(monkeypatch):
    # .env.example をコピーしただけの空欄をフォールバック先に含めない。
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "  ")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key3")

    assert load_gemini_api_keys() == ("key1", "key3")


def test_deduplicates_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key1")

    assert load_gemini_api_keys() == ("key1",)


def test_raises_when_primary_key_is_missing():
    with pytest.raises(KeyError):
        load_gemini_api_keys()
