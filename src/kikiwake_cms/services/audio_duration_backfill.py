import datetime

from tqdm import tqdm

from ..audio_utils import mp3_duration_seconds
from ..clients.storage_client import StorageClient
from ..clients.supabase_client import SupabaseClient
from ..config import Settings


def backfill_duration(
    storage_client: StorageClient,
    supabase_client: SupabaseClient,
    audio_id: int,
    audio_path: str,
) -> None:
    data = storage_client.fetch_public(audio_path)
    duration = mp3_duration_seconds(data)
    (
        supabase_client.raw.table("audio")
        .update(
            {
                "duration": duration,
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        .eq("audio_id", audio_id)
        .execute()
    )


def run(settings: Settings) -> None:
    """duration未設定のaudioレコードを対象に長さを再計算する(旧save_audio_duration.py)。"""
    supabase_client = SupabaseClient(settings)
    storage_client = StorageClient(settings)

    audio_response = (
        supabase_client.raw.table("audio")
        .select("audio_id, audio_path")
        .eq("duration", 0)
        .execute()
    )

    for data in tqdm(audio_response.data):
        backfill_duration(
            storage_client, supabase_client, data["audio_id"], data["audio_path"]
        )
