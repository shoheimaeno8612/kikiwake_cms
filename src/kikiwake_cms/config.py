import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

# find_dotenv()はカレントディレクトリに依存せず、呼び出し元から上位ディレクトリを
# 遡って.envを探す。実行時のcwdに依存していた旧 load_dotenv("../../.env") の問題を解消する。
load_dotenv(find_dotenv())


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    r2_endpoint_url: str
    r2_access_key_id: str
    r2_secret_access_key: str
    gemini_api_key: str

    r2_bucket: str = "personalized-dictation"
    r2_public_base_url: str = "https://pub-e4cda8c8642a464f92027ed892aa44e4.r2.dev"
    tts_voice_filter: str = "Chirp3-HD"

    # コンテンツ生成バッチのページングサイズ
    translation_batch_size: int = 50
    audio_alignment_limit: int = 500
    json_export_limit: int = 1000
    json_export_chunk_size: int = 100


def load_settings() -> Settings:
    return Settings(
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_key=os.environ["SUPABASE_SECRET_KEY"],
        r2_endpoint_url=os.environ["R2_ENDPOINT_URL"],
        r2_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        r2_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        gemini_api_key=os.environ["GEMINI_API_KEY"],
    )
