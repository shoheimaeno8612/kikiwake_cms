import uuid

from tqdm import tqdm

from ..audio_utils import mp3_duration_seconds
from ..clients.storage_client import StorageClient
from ..clients.supabase_client import SupabaseClient
from ..clients.tts_client import TtsClient
from ..config import Settings
from ..logging_config import get_logger

logger = get_logger(__name__)


def generate_and_save_audio(
    tts_client: TtsClient,
    storage_client: StorageClient,
    supabase_client: SupabaseClient,
    content_id: int,
    text: str,
) -> dict:
    """TTS生成→R2アップロード→duration計算→audioテーブル保存を行う。

    duration計算はTTS生成直後にメモリ上にあるバイト列に対して直接行うため、
    アップロード済みファイルをR2から再取得するネットワーク往復は発生しない
    (旧AudioFile経由の実装ではこの再取得が無駄に発生していた)。
    """
    output = tts_client.synthesize(text)
    audio_path = f"audio/en/{output.country}/{uuid.uuid4()}.mp3"
    storage_client.upload(audio_path, output.bytes, "audio/mpeg")
    duration = mp3_duration_seconds(output.bytes)

    param = {
        "content_id": content_id,
        "gender": output.gender,
        "country": output.country,
        "speaker": output.name,
        "audio_path": audio_path,
        "duration": duration,
    }
    supabase_client.raw.table("audio").insert(param).execute()
    return param


def run(settings: Settings) -> None:
    """audioが未生成のcontentsからaudioを生成する(旧save_audio.py)。"""
    supabase_client = SupabaseClient(settings)
    tts_client = TtsClient(settings)
    storage_client = StorageClient(settings)

    response = (
        supabase_client.raw.table("contents")
        .select("*, audio()")
        .is_("audio", "null")
        .execute()
    )

    for obj in tqdm(response.data):
        content_id = obj["content_id"]
        try:
            generate_and_save_audio(
                tts_client, storage_client, supabase_client, content_id, obj["content"]
            )
        except Exception:
            logger.exception(
                "Failed to generate/save audio for content_id=%s", content_id
            )
            continue
