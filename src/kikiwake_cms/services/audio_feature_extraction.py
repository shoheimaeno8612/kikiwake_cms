import base64
import datetime
import json
import pathlib
from typing import List

from pydantic import BaseModel
from tqdm import tqdm

from ..clients.genai_client import GenaiClient
from ..clients.storage_client import StorageClient
from ..clients.supabase_client import SupabaseClient
from ..config import Settings
from ..debug_utils import dump_debug_text
from ..logging_config import get_logger
from .audio_feature_extraction_data import audio_features, system_instruction

logger = get_logger(__name__)


# 音声的特徴の解析結果
class SentenceAudioFeature(BaseModel):
    sentence_id: int
    feature_id: int
    start_index: int
    end_index: int
    translation: str | None


class SentenceAudioFeatures(BaseModel):
    result: List[SentenceAudioFeature]


def build_prompt(content: dict, segments: list) -> str:
    """音声特徴解析用のプロンプトを組み立てる純粋関数。

    content には content_id / level / sentences(sentence_id, sentence, sentence_index) が
    含まれる想定。segments は audio.sentences(発話区間)で、各文が音声内のどこで発話される
    かを [Audio Segments] としてモデルに与える(発話区間の特定は別処理で済ませてある前提)。
    """
    return f"""
入力のaudioは、[Content]のsentenceを sentence_index の順に読み上げた音声ファイルです。
各sentenceが音声内のどこで発話されているかは [Audio Segments] に秒単位で与えられています。

音声を実際に聞き、各sentenceの音声的特徴(linking / flapping / weak_form / assimilation / elision)を抽出してください。

[Feature Master]
{json.dumps(audio_features, ensure_ascii=False)}

[Content]
{json.dumps(content, ensure_ascii=False)}

[Audio Segments]
{json.dumps(segments, ensure_ascii=False)}

各featureについて、以下を返してください。

* sentence_id
* feature_id
* start_index
* end_index
* translation

`start_index` と `end_index` はsentence内の単語インデックスです。
0始まりで、`end_index` はexclusiveです。

translationは原則 `null` としてください。聞こえ方の補足が学習上有用な場合のみ簡潔な日本語を入れてください。

入力されたsentenceに存在しないfeatureを作成してはいけません。
feature master listに存在しないfeature_idを使用してはいけません。
表記上起こり得ても、音声で実際に発音されていない現象は抽出しないでください。

学習価値の低い特徴を過剰に抽出せず、リスニングで学習者がつまずきやすいfeatureを優先してください。

response_schemaに従ってJSONのみを出力してください。
"""


def parse_result(output_text: str) -> dict:
    """Geminiのレスポンスをdictにパースする。失敗時はデバッグ保存してから再raiseする。"""
    try:
        return json.loads(output_text)
    except json.JSONDecodeError:
        debug_path = dump_debug_text("audio_feature_extraction", output_text)
        logger.error(
            "Failed to parse Gemini response as JSON; raw response saved to %s",
            debug_path,
        )
        raise


def run(count: int, gen_model: str, settings: Settings) -> None:
    """文の音声的特徴(connected speech)をGeminiで解析する。

    発話区間(audio.sentences)は analyze-audio-alignment で先に埋めておく前提。
    ここでは区間が確定済みのaudioだけを対象にし、音声特徴のみを抽出する。
    """
    genai_client = GenaiClient(settings)
    supabase_client = SupabaseClient(settings)
    storage_client = StorageClient(settings)

    # 音声特徴が未処理、かつ発話区間が確定済みのaudioを取得
    response = (
        supabase_client.raw.table("contents")
        .select(
            "content_id,levels(level_id,code),"
            "sentences(sentence_id,sentence,sentence_index),"
            "audio!inner(audio_id,audio_path,sentences,feature_extracted_at)",
            count="exact",
        )
        .is_("audio.feature_extracted_at", "null")
        .not_.is_("audio.sentences", "null")
        .neq("audio.sentences", "[]")
        .not_.is_("sentences", "null")
        .order("content_id")
        .order("sentence_index", foreign_table="sentences")
        .limit(count)
        .execute()
    )

    day = datetime.datetime.now().strftime("%Y%m%d")
    new_folder_path = pathlib.Path(f"../sentence_audio_features/new/{day}")
    done_folder_path = pathlib.Path(f"../sentence_audio_features/done/{day}")

    for content in tqdm(response.data):
        level = content["levels"]["code"] if content.get("levels") else None
        content_for_prompt = {
            "content_id": content["content_id"],
            "level": level,
            "sentences": [
                {
                    "sentence_id": s["sentence_id"],
                    "sentence": s["sentence"],
                    "sentence_index": s["sentence_index"],
                }
                for s in content["sentences"]
            ],
        }

        for audio in content["audio"]:
            audio_id = audio["audio_id"]
            segments = audio.get("sentences") or []

            try:
                audio_bytes = storage_client.fetch_public(audio["audio_path"])
            except Exception:
                logger.exception(
                    "Failed to fetch audio for audio_id=%s (path=%s)",
                    audio_id,
                    audio["audio_path"],
                )
                continue

            interaction = genai_client.generate_json(
                model=gen_model,
                input=[
                    {
                        "type": "text",
                        "text": build_prompt(content_for_prompt, segments),
                    },
                    {
                        "type": "audio",
                        "data": base64.b64encode(audio_bytes).decode("utf-8"),
                        "mime_type": "audio/mp3",
                    },
                ],
                response_schema=SentenceAudioFeatures.model_json_schema(),
                system_instruction=system_instruction,
            )

            try:
                result_dict = parse_result(interaction.output_text)
            except json.JSONDecodeError:
                logger.exception(
                    "Skipping audio_id=%s due to unparseable response.", audio_id
                )
                continue

            result_dict["content_id"] = content["content_id"]
            result_dict["audio_id"] = audio_id
            result_dict["gen_model"] = gen_model
            result_dict["usage"] = interaction.usage.to_dict()

            # 未処理データとしてローカル保存
            new_folder_path.mkdir(parents=True, exist_ok=True)
            done_folder_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%H%M%S_%f")
            filename = f"{timestamp}.json"
            with open(f"{new_folder_path}/{filename}", "w") as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)

            # 音声特徴をsupabaseに保存
            saved = []
            unsaved = []
            for audio_feature in result_dict["result"]:
                try:
                    supabase_client.raw.table("sentence_features").insert(
                        {
                            "sentence_id": audio_feature["sentence_id"],
                            "feature_id": audio_feature["feature_id"],
                            "audio_id": audio_id,
                            "start_index": audio_feature["start_index"],
                            "end_index": audio_feature["end_index"],
                            "translation": audio_feature["translation"],
                        }
                    ).execute()
                    saved.append(audio_feature)
                except Exception:
                    logger.exception(
                        "Failed to save audio feature for sentence_id=%s",
                        audio_feature.get("sentence_id"),
                    )
                    unsaved.append(audio_feature)

            supabase_client.raw.table("audio").update(
                {
                    "feature_extracted_at": datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }
            ).eq("audio_id", audio_id).execute()

            logger.info(
                "audio_id=%s: %d audio features saved, %d failed.",
                audio_id,
                len(saved),
                len(unsaved),
            )

            src = pathlib.Path(f"{new_folder_path.absolute()}/{filename}")
            if len(unsaved) == 0:
                dst = pathlib.Path(f"{done_folder_path.absolute()}/{filename}")
                src.rename(dst)
            else:
                with open(f"{src.absolute()}", "w") as f:
                    json.dump(unsaved, f, indent=2, ensure_ascii=False)
