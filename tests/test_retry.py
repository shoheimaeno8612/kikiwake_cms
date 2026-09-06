import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai._gaos.lib import compat_errors

from kikiwake_cms.retry import (
    _retry_after_seconds,
    genai_retry,
    is_transient_genai_error,
    is_transient_storage_error,
    is_transient_supabase_error,
)

_REQUEST = httpx.Request(
    "POST", "https://generativelanguage.googleapis.com/v1beta/interactions"
)


def _rate_limit_error(retry_after=None, message="rate limited"):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    response = httpx.Response(429, request=_REQUEST, headers=headers, json={})
    return compat_errors.RateLimitError(message, response=response, body={})


def _internal_server_error():
    response = httpx.Response(500, request=_REQUEST, json={})
    return compat_errors.InternalServerError("server error", response=response, body={})


def _bad_request_error():
    response = httpx.Response(400, request=_REQUEST, json={})
    return compat_errors.BadRequestError("bad request", response=response, body={})


def _client_error(code):
    return genai_errors.ClientError(code, {"error": {"message": "boom"}})


def _server_error(code=500):
    return genai_errors.ServerError(code, {"error": {"message": "boom"}})


def test_genai_retries_on_rate_limit():
    assert is_transient_genai_error(_client_error(429)) is True


def test_genai_does_not_retry_on_bad_request():
    assert is_transient_genai_error(_client_error(400)) is False


def test_genai_does_not_retry_on_auth_error():
    assert is_transient_genai_error(_client_error(401)) is False


def test_genai_retries_on_server_error():
    assert is_transient_genai_error(_server_error(503)) is True


def test_genai_retries_on_connection_error():
    assert is_transient_genai_error(ConnectionError("boom")) is True


def test_supabase_retries_on_connection_error():
    assert is_transient_supabase_error(ConnectionError("boom")) is True


def test_supabase_does_not_retry_on_unrelated_error():
    assert is_transient_supabase_error(ValueError("bad data")) is False


def test_storage_does_not_retry_on_unrelated_error():
    assert is_transient_storage_error(ValueError("bad data")) is False


def test_genai_retry_eventually_succeeds_after_transient_errors():
    attempts = {"n": 0}

    @genai_retry()
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _server_error(503)
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 3


def test_genai_retry_does_not_retry_permanent_error():
    attempts = {"n": 0}

    @genai_retry()
    def always_bad_request():
        attempts["n"] += 1
        raise _client_error(400)

    with pytest.raises(genai_errors.ClientError):
        always_bad_request()

    assert attempts["n"] == 1


# client.interactions.create() (本プロジェクトが実際に使うAPI) が送出する
# google.genai._gaos.lib.compat_errors 階層に対するテスト。
# 実運用で429 RateLimitErrorがリトライされない不具合が発生したため追加した。


def test_genai_retries_on_compat_rate_limit_error():
    assert is_transient_genai_error(_rate_limit_error()) is True


def test_genai_retries_on_compat_internal_server_error():
    assert is_transient_genai_error(_internal_server_error()) is True


def test_genai_does_not_retry_on_compat_bad_request_error():
    assert is_transient_genai_error(_bad_request_error()) is False


def test_retry_after_seconds_reads_header():
    exc = _rate_limit_error(retry_after=55)
    assert _retry_after_seconds(exc) == 55.0


def test_retry_after_seconds_returns_none_when_absent():
    exc = _rate_limit_error()
    assert _retry_after_seconds(exc) is None


def test_retry_after_seconds_parses_message_when_header_missing():
    # 実運用のGemini APIは Retry-After ヘッダを付与せず、エラーメッセージ本文の
    # "Please retry in 31.27s." にのみ待機秒数を含めてくることを確認したため、
    # そのフォールバック解析が正しく動くことを検証する。
    exc = _rate_limit_error(
        message=(
            "Error code: 429 - {'error': {'message': 'Quota exceeded. "
            "Please retry in 31.278365724s.', 'code': 'too_many_requests'}}"
        )
    )
    # サーバー指定の秒数 + 2秒のバッファ
    assert _retry_after_seconds(exc) == pytest.approx(33.278365724)


def test_genai_retry_honors_retry_after_header():
    # retry_after=0 を指定し、テストを高速に保ちつつヘッダ経由のwait計算が
    # 例外を起こさず正しくリトライにつながることを確認する。
    attempts = {"n": 0}

    @genai_retry()
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise _rate_limit_error(retry_after=0)
        return "ok"

    assert flaky() == "ok"
    assert attempts["n"] == 2
