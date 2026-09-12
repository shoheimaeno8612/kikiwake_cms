import datetime
import json
import pathlib
from typing import List

from pydantic import BaseModel
from tqdm import tqdm

from ..clients.genai_client import GenaiClient
from ..clients.supabase_client import SupabaseClient
from ..config import Settings
from ..debug_utils import dump_debug_text
from ..logging_config import get_logger
from .feature_extraction_data import features, system_instruction

logger = get_logger(__name__)


# 特徴解析結果を格納するクラス
class SentenceFeature(BaseModel):
    content_id: int
    sentence_id: int
    feature_id: int
    start_index: int
    end_index: int
    translation: str | None


class SentenceFeatures(BaseModel):
    result: List[SentenceFeature]


def run(count: int, gen_model: str, settings: Settings) -> None:
    """文の言語的特徴を解析する(旧extract_linguistic_features.py)。"""
    genai_client = GenaiClient(settings)
    supabase_client = SupabaseClient(settings)

    for _ in tqdm(range(10)):
        # 特徴解析が未処理の文を取得
        # 未処理判定は content レベルの feature_extracted_at のみで行う。
        # sentence_features には音声特徴の行(audio_id あり)も入るため、
        # sentence 単位の "sentence_features is null" では音声特徴が先に付いた
        # sentence の言語特徴が抽出されなくなってしまう。
        response = (
            supabase_client.raw.table("contents")
            .select(
                "content_id,levels(level_id,code),sentences(sentence_id,sentence,sentence_index,sentence_features(*))",
                count="exact",
            )
            .is_("feature_extracted_at", "null")
            .not_.is_("sentences", "null")
            .order("content_id")
            .order("sentence_index", foreign_table="sentences")
            .limit(count)
            .execute()
        )

        # プロンプト用にコンテンツをまとめる
        contents = []
        for content in response.data:
            content["level"] = content["levels"]["code"]
            del content["levels"]
            for sentence in content["sentences"]:
                sentence["content_id"] = content["content_id"]
                del sentence["sentence_features"]
            contents.append(content)

        prompt = f"""
    以下の[Contents]に含まれるすべてのsentenceについて、事前に登録されているfeature master listを使用して言語的特徴を抽出してください。

    各contentは独立して解析してください。

    [Feature Master]
    {json.dumps(features, ensure_ascii=False)}

    [Contents]
    {json.dumps(contents, ensure_ascii=False)}

    各featureについて、以下を返してください。

    * content_id
    * sentence_id
    * feature_id
    * start_index
    * end_index
    * translation

    `start_index` と `end_index` はsentence内の単語インデックスです。
    0始まりで、`end_index` はexclusiveです。

    translationはsentence全体ではなく、featureとして抽出した範囲だけの日本語訳を返してください。

    featureの学習上、日本語訳が不要な場合は `null` としてください。

    入力されたsentenceに存在しないfeatureを作成してはいけません。
    feature master listに存在しないfeature_idを使用してはいけません。

    学習価値の低い特徴を過剰に抽出せず、英語学習者が復習する価値の高いfeatureを優先してください。

    """

        # 特徴解析
        interaction = genai_client.generate_json(
            model=gen_model,
            input=prompt,
            response_schema=SentenceFeatures.model_json_schema(),
            system_instruction=system_instruction,
        )
        try:
            result_dict = json.loads(interaction.output_text)
        except json.JSONDecodeError:
            debug_path = dump_debug_text("feature_extraction", interaction.output_text)
            logger.exception(
                "Failed to parse Gemini response as JSON (count=%d); "
                "raw response saved to %s. Skipping this batch.",
                count,
                debug_path,
            )
            continue
        result_dict["gen_model"] = gen_model
        result_dict["usage"] = interaction.usage.to_dict()

        # 未処理データとしてローカル保存
        day = datetime.datetime.now().strftime("%Y%m%d")
        new_folder_path = pathlib.Path(f"../sentence_features/new/{day}")
        done_folder_path = pathlib.Path(f"../sentence_features/done/{day}")
        new_folder_path.mkdir(parents=True, exist_ok=True)
        done_folder_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        filename = f"{timestamp}.json"
        with open(f"{new_folder_path}/{filename}", "w") as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)

        # supabaseに保存
        saved = []
        unsaved = []
        for sentence_feature in result_dict["result"]:
            try:
                supabase_client.raw.table("sentence_features").insert(
                    {
                        "sentence_id": sentence_feature["sentence_id"],
                        "feature_id": sentence_feature["feature_id"],
                        "start_index": sentence_feature["start_index"],
                        "end_index": sentence_feature["end_index"],
                        "translation": sentence_feature["translation"],
                        "model": gen_model,
                    }
                ).execute()

                saved.append(sentence_feature)
            except Exception:
                logger.exception(
                    "Failed to save sentence_feature for sentence_id=%s",
                    sentence_feature.get("sentence_id"),
                )
                unsaved.append(sentence_feature)

        for content in contents:
            supabase_client.raw.table("contents").update(
                {
                    "feature_extracted_at": datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }
            ).eq("content_id", content["content_id"]).execute()

        logger.info("%d sentence features were saved.", len(saved))
        logger.info("%d sentence features were not saved for the error.", len(unsaved))

        src = pathlib.Path(f"{new_folder_path.absolute()}/{filename}")
        if len(unsaved) == 0:
            # すべて保存したのでnewからdoneに移動
            dst = pathlib.Path(f"{done_folder_path.absolute()}/{filename}")
            src.rename(dst)
        else:
            # 一部保存に失敗したのでnewのファイルを未保存コンテンツで上書き
            with open(f"{src.absolute()}", "w") as f:
                json.dump(unsaved, f, indent=2)
