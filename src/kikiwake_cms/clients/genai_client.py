from google import genai

from ..config import Settings
from ..logging_config import get_logger
from ..retry import genai_retry, is_rate_limit_error

logger = get_logger(__name__)


class GenaiClient:
    """複数のAPIキーを切り替えながらGeminiを呼び出すクライアント。

    Geminiの無料枠レート制限はAPIキー単位で課されるため、429が返った場合は
    待機せずに次のキーへ切り替えて即座に再試行する。全てのキーが枯渇したときだけ
    例外を送出し、genai_retry() のバックオフ待機付きリトライに処理を委ねる。
    """

    def __init__(self, settings: Settings):
        api_keys = settings.gemini_api_keys
        if not api_keys:
            raise ValueError("Gemini APIキーが1つも設定されていません")

        self._clients = [genai.Client(api_key=api_key) for api_key in api_keys]
        # 直近で成功したキーの位置。次回以降はここを起点にすることで、
        # レート制限に達したキーへ毎回無駄なリクエストを投げるのを避ける。
        self._key_index = 0

    @genai_retry()
    def generate_json(
        self,
        model: str,
        input,
        response_schema: dict,
        system_instruction: str | None = None,
    ):
        kwargs = {}
        if system_instruction is not None:
            kwargs["system_instruction"] = system_instruction

        return self._create_interaction(
            model=model,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema,
            },
            input=input,
            **kwargs,
        )

    def _create_interaction(self, **kwargs):
        """レート制限に当たったらAPIキーを切り替えながらリクエストする。"""
        key_count = len(self._clients)

        for offset in range(key_count):
            key_index = (self._key_index + offset) % key_count
            try:
                response = self._clients[key_index].interactions.create(**kwargs)
            except Exception as exc:
                is_last_key = offset == key_count - 1
                # レート制限以外のエラーはキーを変えても解消しない。
                # 全キーが枯渇した場合も、待機して再試行できるよう呼び出し元に投げる。
                if is_last_key or not is_rate_limit_error(exc):
                    raise
                logger.warning(
                    "Gemini APIキー#%d がレート制限に達したため#%dに切り替えます: %s",
                    key_index + 1,
                    (key_index + 1) % key_count + 1,
                    exc,
                )
                continue

            self._key_index = key_index
            return response
