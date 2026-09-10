"""レート制限時にAPIキーを切り替えるフォールバック挙動のテスト。"""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai._gaos.lib import compat_errors

from kikiwake_cms.clients import genai_client as genai_client_module
from kikiwake_cms.clients.genai_client import GenaiClient
from kikiwake_cms.config import Settings
from kikiwake_cms.retry import _GENAI_MAX_ATTEMPTS

_REQUEST = httpx.Request(
    "POST", "https://generativelanguage.googleapis.com/v1beta/interactions"
)


def _rate_limit_error():
    # retry-after: 0 を返してテスト中のバックオフ待機をゼロにする。
    response = httpx.Response(429, request=_REQUEST, headers={"retry-after": "0"}, json={})
    return compat_errors.RateLimitError("rate limited", response=response, body={})


def _bad_request_error():
    response = httpx.Response(400, request=_REQUEST, json={})
    return compat_errors.BadRequestError("bad request", response=response, body={})


class FakeSDKClient:
    """google.genai.Client の最小限のフェイク。

    behaviors に積んだ値を呼び出しごとに返す(Exceptionなら送出する)。
    末尾の要素は以降の呼び出しで繰り返し使われる。
    """

    def __init__(self, api_key):
        self.api_key = api_key
        self.calls = []
        self.behaviors = [None]
        self.interactions = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.behaviors) - 1)
        behavior = self.behaviors[index]
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


@pytest.fixture
def fake_sdk_clients(monkeypatch):
    """genai.Client をフェイクに差し替え、APIキーごとのインスタンスを返す。"""
    created = {}

    def fake_client_factory(api_key):
        client = FakeSDKClient(api_key)
        created[api_key] = client
        return client

    monkeypatch.setattr(
        genai_client_module.genai, "Client", lambda api_key: fake_client_factory(api_key)
    )
    return created


def _settings(*gemini_api_keys):
    return Settings(
        supabase_url="https://example.test",
        supabase_key="supabase-key",
        r2_endpoint_url="https://r2.example.test",
        r2_access_key_id="r2-id",
        r2_secret_access_key="r2-secret",
        gemini_api_keys=tuple(gemini_api_keys),
    )


def _generate(client):
    return client.generate_json(
        model="gemini-3.6-flash", input=[], response_schema={"type": "object"}
    )


def test_uses_first_key_when_it_succeeds(fake_sdk_clients):
    client = GenaiClient(_settings("key1", "key2", "key3"))
    fake_sdk_clients["key1"].behaviors = ["ok-1"]

    assert _generate(client) == "ok-1"
    assert len(fake_sdk_clients["key1"].calls) == 1
    assert fake_sdk_clients["key2"].calls == []
    assert fake_sdk_clients["key3"].calls == []


def test_falls_back_to_next_key_on_rate_limit(fake_sdk_clients):
    client = GenaiClient(_settings("key1", "key2", "key3"))
    fake_sdk_clients["key1"].behaviors = [_rate_limit_error()]
    fake_sdk_clients["key2"].behaviors = ["ok-2"]

    assert _generate(client) == "ok-2"
    assert len(fake_sdk_clients["key1"].calls) == 1
    assert len(fake_sdk_clients["key2"].calls) == 1
    assert fake_sdk_clients["key3"].calls == []


def test_falls_back_through_all_keys_until_one_succeeds(fake_sdk_clients):
    client = GenaiClient(_settings("key1", "key2", "key3"))
    fake_sdk_clients["key1"].behaviors = [_rate_limit_error()]
    fake_sdk_clients["key2"].behaviors = [_rate_limit_error()]
    fake_sdk_clients["key3"].behaviors = ["ok-3"]

    assert _generate(client) == "ok-3"
    assert len(fake_sdk_clients["key3"].calls) == 1


def test_keeps_using_the_key_that_succeeded(fake_sdk_clients):
    # 一度レート制限に達したキーへ毎回リクエストを投げ直さないことを確認する。
    client = GenaiClient(_settings("key1", "key2", "key3"))
    fake_sdk_clients["key1"].behaviors = [_rate_limit_error()]
    fake_sdk_clients["key2"].behaviors = ["ok-2"]

    _generate(client)
    _generate(client)

    assert len(fake_sdk_clients["key1"].calls) == 1
    assert len(fake_sdk_clients["key2"].calls) == 2


def test_does_not_switch_key_on_non_rate_limit_error(fake_sdk_clients):
    # スキーマ不正のような恒久的エラーはキーを変えても解消しないため、
    # 他のキーを消費せずにそのまま送出する。
    client = GenaiClient(_settings("key1", "key2", "key3"))
    fake_sdk_clients["key1"].behaviors = [_bad_request_error()]

    with pytest.raises(compat_errors.BadRequestError):
        _generate(client)

    assert len(fake_sdk_clients["key1"].calls) == 1
    assert fake_sdk_clients["key2"].calls == []
    assert fake_sdk_clients["key3"].calls == []


def test_raises_when_every_key_is_rate_limited(fake_sdk_clients):
    client = GenaiClient(_settings("key1", "key2", "key3"))
    for fake in fake_sdk_clients.values():
        fake.behaviors = [_rate_limit_error()]

    with pytest.raises(compat_errors.RateLimitError):
        _generate(client)

    # 全キー枯渇時はgenai_retry()のバックオフ再試行に委ねられ、
    # 試行のたびに3本すべてが順に試される。
    for fake in fake_sdk_clients.values():
        assert len(fake.calls) == _GENAI_MAX_ATTEMPTS


def test_falls_back_on_legacy_client_error_429(fake_sdk_clients):
    # 旧API(google.genai.errors)の429でも同様に切り替わること。
    client = GenaiClient(_settings("key1", "key2"))
    fake_sdk_clients["key1"].behaviors = [
        genai_errors.ClientError(429, {"error": {"message": "quota"}})
    ]
    fake_sdk_clients["key2"].behaviors = ["ok-2"]

    assert _generate(client) == "ok-2"


def test_works_with_a_single_key(fake_sdk_clients):
    client = GenaiClient(_settings("key1"))
    fake_sdk_clients["key1"].behaviors = ["ok-1"]

    assert _generate(client) == "ok-1"


def test_requires_at_least_one_key(fake_sdk_clients):
    with pytest.raises(ValueError):
        GenaiClient(_settings())
