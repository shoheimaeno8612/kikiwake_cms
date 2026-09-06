"""外部API呼び出し用のリトライポリシー。

サービスごとに「一時的エラー」を個別に判定する。全ての例外を一律リトライすると、
スキーマ不正や認証エラーのような恒久的なエラーまで無駄に再試行してしまうため、
それぞれのSDKが送出する例外の種類とステータスコードを見て判定する。
"""

import logging
import re

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .logging_config import get_logger

logger = get_logger(__name__)

_MAX_ATTEMPTS = 5
# Geminiのfree tierレート制限は約1分周期でリセットされ、429エラー時にリセットまでの
# 秒数がメッセージ本文に含まれる(例: "Please retry in 44.2s")が、実際の応答には
# Retry-Afterヘッダが付与されないことを実運用で確認した。そのためgenai向けだけは
# 通常よりリトライ回数を増やし、フォールバックの指数バックオフ上限も長めにする。
_GENAI_MAX_ATTEMPTS = 8

_RETRY_IN_PATTERN = re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE)


def _wait_policy(max_wait=30):
    return wait_exponential_jitter(initial=1, max=max_wait)


def _retry_after_seconds(exc: BaseException) -> float | None:
    """例外からリトライまでの待機秒数を読み取る。

    Retry-Afterヘッダがあればそれを優先する。実際のGemini APIの429応答には
    このヘッダが付与されず、"Please retry in 44.2s" のようなメッセージ本文に
    しか情報がないことが確認できたため、その形式もフォールバックとして解析する。
    """
    response = getattr(exc, "response", None)
    if response is not None:
        header_value = response.headers.get("retry-after")
        if header_value is not None:
            try:
                return float(header_value)
            except ValueError:
                pass

    match = _RETRY_IN_PATTERN.search(str(exc))
    if match:
        try:
            # サーバー側の秒数ちょうどで再試行すると再びレート制限に
            # 引っかかりやすいため、余裕を持って+2秒する。
            return float(match.group(1)) + 2
        except ValueError:
            return None

    return None


def _genai_wait(retry_state):
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc is not None:
        seconds = _retry_after_seconds(exc)
        if seconds is not None:
            return seconds
    return _wait_policy(max_wait=60)(retry_state)


def is_transient_genai_error(exc: BaseException) -> bool:
    # client.interactions.create() (本プロジェクトが使う新API) は
    # google.genai._gaos.lib.compat_errors 配下のOpenAI SDK風の例外階層を送出する。
    # RateLimitError/InternalServerErrorは常にリトライ、その他のAPIStatusError
    # (BadRequestError, AuthenticationError等の4xx)は再試行しても無駄なので対象外。
    try:
        from google.genai._gaos.lib import compat_errors

        if isinstance(
            exc, (compat_errors.RateLimitError, compat_errors.InternalServerError)
        ):
            return True
        if isinstance(exc, compat_errors.APIStatusError):
            return exc.status_code >= 500
        if isinstance(
            exc, (compat_errors.APIConnectionError, compat_errors.APITimeoutError)
        ):
            return True
    except ImportError:
        pass

    # client.models.generate_content() (旧API) は google.genai.errors 配下の
    # 例外(.code属性)を送出する。こちらも念のため対応しておく。
    try:
        from google.genai import errors as genai_errors

        if isinstance(exc, genai_errors.ServerError):
            return True
        if isinstance(exc, genai_errors.ClientError):
            return getattr(exc, "code", None) == 429
    except ImportError:
        pass

    return _is_transient_network_error(exc)


def is_transient_supabase_error(exc: BaseException) -> bool:
    # postgrest.exceptions.APIError (制約違反等のデータエラー) はリトライしない。
    # ネットワーク層のタイムアウト・接続エラーのみ対象。
    return _is_transient_network_error(exc)


_TRANSIENT_R2_ERROR_CODES = {
    "SlowDown",
    "RequestTimeout",
    "InternalError",
    "ServiceUnavailable",
}


def is_transient_storage_error(exc: BaseException) -> bool:
    # R2へのアップロード(boto3/botocore)
    try:
        from botocore.exceptions import ClientError, ConnectionError as BotoConnectionError
        from botocore.exceptions import EndpointConnectionError, ReadTimeoutError

        if isinstance(exc, (EndpointConnectionError, BotoConnectionError, ReadTimeoutError)):
            return True
        if isinstance(exc, ClientError):
            error_info = exc.response.get("Error", {})
            if error_info.get("Code") in _TRANSIENT_R2_ERROR_CODES:
                return True
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if isinstance(status, int) and status >= 500:
                return True
    except ImportError:
        pass

    # R2公開URLからのダウンロード(requests)
    try:
        import requests

        if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            if exc.response.status_code >= 500:
                return True
    except ImportError:
        pass

    return False


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    try:
        import httpx
    except ImportError:
        return False
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError))


def genai_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(_GENAI_MAX_ATTEMPTS),
        wait=_genai_wait,
        retry=retry_if_exception(is_transient_genai_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def supabase_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=_wait_policy(),
        retry=retry_if_exception(is_transient_supabase_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def storage_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=_wait_policy(),
        retry=retry_if_exception(is_transient_storage_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
