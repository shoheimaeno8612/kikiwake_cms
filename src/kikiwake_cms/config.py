import os
import re
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

# find_dotenv()はカレントディレクトリに依存せず、呼び出し元から上位ディレクトリを
# 遡って.envを探す。実行時のcwdに依存していた旧 load_dotenv("../../.env") の問題を解消する。
load_dotenv(find_dotenv())

# Geminiの無料枠レート制限はAPIキー単位で課される。1本目が429で弾かれたときに
# 次のキーへフォールバックできるよう、.envには GEMINI_API_KEY_2, _3, _4 ... と
# 連番で何本でもキーを設定できる。本数をコード側で列挙しないので、キーを増やすときは
# .envに1行足すだけでよい。
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
_GEMINI_API_KEY_ENV_PATTERN = re.compile(rf"^{GEMINI_API_KEY_ENV_VAR}(?:_(\d+))?$")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    r2_endpoint_url: str
    r2_access_key_id: str
    r2_secret_access_key: str
    # レート制限時のフォールバック順に並んだGeminiのAPIキー。先頭が主キー。
    gemini_api_keys: tuple[str, ...]

    r2_bucket: str = "personalized-dictation"
    r2_public_base_url: str = "https://pub-e4cda8c8642a464f92027ed892aa44e4.r2.dev"
    tts_voice_filter: str = "Chirp3-HD"

    # コンテンツ生成バッチのページングサイズ
    translation_batch_size: int = 50
    audio_alignment_limit: int = 500
    # 発話区間の特定は軽量モデルで十分な精度が出るため 3.1-flash-lite を既定にする。
    # 精度の高い 3.5-flash-lite は音声特徴解析用に温存する。
    audio_alignment_model: str = "gemini-3.1-flash-lite"
    json_export_limit: int = 1000
    json_export_chunk_size: int = 100

    @property
    def gemini_api_key(self) -> str:
        """主キー(1本目)。単一キーを前提とする箇所からの参照用。"""
        return self.gemini_api_keys[0]


def gemini_api_key_env_vars() -> tuple[str, ...]:
    """設定済みのGeminiのAPIキー環境変数名をフォールバック順に返す。"""
    # 添字なしの GEMINI_API_KEY を主キー(1本目)とみなす。文字列ソートでは
    # _10 が _2 より前に来てしまうため、添字を整数に直して並べ替える。
    numbered = [
        (int(match.group(1) or 1), name)
        for name in os.environ
        if (match := _GEMINI_API_KEY_ENV_PATTERN.match(name))
    ]
    return tuple(name for _, name in sorted(numbered))


def load_gemini_api_keys() -> tuple[str, ...]:
    """.envに設定されたGeminiのAPIキーをフォールバック順に読み込む。

    GEMINI_API_KEY は必須。GEMINI_API_KEY_2 以降はレート制限時の切り替え先として
    使うだけなので任意とし、設定済みのものだけを順に採用する。途中の番号が空欄でも
    それ以降の番号は使う。同じキーを重複して設定してもフォールバック先としては
    機能しないため取り除く。
    """
    keys: list[str] = []
    for env_var in gemini_api_key_env_vars():
        key = os.environ.get(env_var, "").strip()
        if key and key not in keys:
            keys.append(key)

    if not keys:
        # 従来どおり必須の環境変数が無い場合はKeyErrorで落とす。
        raise KeyError(GEMINI_API_KEY_ENV_VAR)

    return tuple(keys)


def load_settings() -> Settings:
    return Settings(
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_key=os.environ["SUPABASE_SECRET_KEY"],
        r2_endpoint_url=os.environ["R2_ENDPOINT_URL"],
        r2_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        r2_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        gemini_api_keys=load_gemini_api_keys(),
    )
