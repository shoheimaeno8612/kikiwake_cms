import base64
import json
from typing import List

from pydantic import BaseModel, Field
from tqdm import tqdm

from ..clients.genai_client import GenaiClient
from ..clients.storage_client import StorageClient
from ..clients.supabase_client import SupabaseClient
from ..config import Settings
from ..debug_utils import dump_debug_text
from ..logging_config import get_logger

logger = get_logger(__name__)


class AudioSentence(BaseModel):
    sentence_id: int = Field(description="Sentence ID")
    start_seconds: float = Field(
        description="Start time of the corresponding sentence spoken."
    )
    end_seconds: float = Field(
        description="End time of the corresponding sentence spoken."
    )


class AudioSentences(BaseModel):
    sentences: List[AudioSentence]


def run(settings: Settings) -> None:
    """文の開始時間と終了時間をGeminiを使用して求める(旧analyze_audio.py)。"""
    supabase_client = SupabaseClient(settings)
    genai_client = GenaiClient(settings)
    storage_client = StorageClient(settings)

    response = (
        supabase_client.raw.table("contents")
        .select(
            "audio!inner(audio_id,audio_path),sentences(sentence_id,sentence,sentence_index)"
        )
        .eq("audio.sentences", "[]")
        .limit(settings.audio_alignment_limit)
        .execute()
    )

    for row in tqdm(response.data):
        audio_bytes = storage_client.fetch_public(row["audio"][0]["audio_path"])

        interaction = genai_client.generate_json(
            # 発話区間の特定は軽量モデルで十分な精度が出る(構造チェックは全通過、
            # 参照値との差は平均 0.1〜0.4 秒)。既定モデルは config.Settings で管理し、
            # 精度の高い 3.5-flash-lite は音声特徴解析用に温存する。
            model=settings.audio_alignment_model,
            response_schema=AudioSentences.model_json_schema(),
            input=[
                {
                    "type": "text",
                    "text": f"""
    入力のaudioは[Sentences]に記載された英文を読み上げた音声ファイルです。

    [Sentences]のsentenceは、記載された順番で音声内にすべて発話されています。
    sentenceを省略したり、順番を変更したりしないでください。

    音声を聞き、各sentenceの開始時間と終了時間を秒単位で特定してください。

    各sentenceについて、実際にそのsentenceが発話されている区間を指定してください。
    開始時間は、そのsentenceの発話が始まる時点です。
    終了時間は、そのsentenceの発話が終わる時点です。

    無音区間やsentence間のポーズは、前後のsentenceの発話時間には含めないでください。

    [Sentences]
    {row['sentences']}

    response_schemaに従ってJSONのみを出力してください。
        """,
                },
                {
                    "type": "audio",
                    "data": base64.b64encode(audio_bytes).decode("utf-8"),
                    "mime_type": "audio/mp3",
                },
            ],
        )

        audio_id = row["audio"][0]["audio_id"]
        try:
            result_dict = json.loads(interaction.output_text)
        except json.JSONDecodeError:
            debug_path = dump_debug_text("audio_alignment", interaction.output_text)
            logger.exception(
                "Failed to parse Gemini response as JSON for audio_id=%s; "
                "raw response saved to %s",
                audio_id,
                debug_path,
            )
            continue

        (
            supabase_client.raw.table("audio")
            .update({"sentences": result_dict["sentences"]})
            .eq("audio_id", audio_id)
            .execute()
        )
