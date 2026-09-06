import io

import pandas as pd

from ..clients.storage_client import StorageClient
from ..clients.supabase_client import SupabaseClient
from ..config import Settings
from ..logging_config import get_logger

logger = get_logger(__name__)


def chunk_dataframe(df: pd.DataFrame, chunk_size: int) -> list[pd.DataFrame]:
    """DataFrameをchunk_size件ごとに分割する純粋関数。"""
    return [df.iloc[i : i + chunk_size] for i in range(0, len(df), chunk_size)]


def save_chunks(
    storage_client: StorageClient, df: pd.DataFrame, path_prefix: str, chunk_size: int
) -> None:
    for idx, chunk in enumerate(chunk_dataframe(df, chunk_size), start=1):
        json_buff = io.StringIO()
        chunk.to_json(json_buff, orient="records", indent=2)
        json_bytes = json_buff.getvalue().encode("utf-8")
        path = f"{path_prefix}/{idx}.json"
        storage_client.upload(path, json_bytes, "application/json")
        logger.info("Saved: %s", path)


def run(settings: Settings) -> None:
    """supabaseから取得したレコードをレベル、ターゲット、カテゴリーごとにjsonとしてR2に保存する(旧create_json.py)。"""
    supabase_client = SupabaseClient(settings)
    storage_client = StorageClient(settings)

    offset = 0
    rows = []
    while True:
        response = supabase_client.raw.rpc(
            "get_contents",
            {"p_limit": settings.json_export_limit, "p_offset": offset},
            count="exact",
        ).execute()
        rows.extend(response.data)
        if response.count < settings.json_export_limit:
            break
        offset += response.count
    df = pd.DataFrame(rows)

    levels = supabase_client.raw.table("levels").select("level_id,code").execute().data
    targets = (
        supabase_client.raw.table("targets").select("target_id,code").execute().data
    )
    categories = (
        supabase_client.raw.table("categories")
        .select("category_id,code")
        .execute()
        .data
    )

    for level in levels:
        level_id: int = int(level["level_id"])
        level_df = df[df["level"].str["level_id"] == level_id]
        level_df = level_df.sort_values(by="created_at", ascending=False)
        save_chunks(
            storage_client,
            level_df,
            f"json/contents/{level['code']}",
            settings.json_export_chunk_size,
        )

        for target in targets:
            target_id: int = int(target["target_id"])
            target_df = level_df[level_df["target"].str["target_id"] == target_id]
            target_df = target_df.sort_values(by="created_at", ascending=False)
            save_chunks(
                storage_client,
                target_df,
                f"json/contents/{level['code']}/{target['code']}",
                settings.json_export_chunk_size,
            )

            for category in categories:
                category_id: int = int(category["category_id"])
                category_df = target_df[
                    target_df["category"].str["category_id"] == category_id
                ]
                category_df = category_df.sort_values(
                    by="created_at", ascending=False
                )
                save_chunks(
                    storage_client,
                    category_df,
                    f"json/contents/{level['code']}/{target['code']}/{category['code']}",
                    settings.json_export_chunk_size,
                )
