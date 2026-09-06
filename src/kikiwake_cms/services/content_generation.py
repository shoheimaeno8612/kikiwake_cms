import datetime
import json
import pathlib
import random
from typing import List

from pydantic import BaseModel
from tqdm import tqdm

from ..clients.genai_client import GenaiClient
from ..clients.storage_client import StorageClient
from ..clients.supabase_client import SupabaseClient
from ..clients.tts_client import TtsClient
from ..config import Settings
from ..content_data import GENRES, STRUCTURES, SYSTEM_INSTRUCTION
from ..debug_utils import dump_debug_text
from ..logging_config import get_logger
from .audio_generation import generate_and_save_audio

logger = get_logger(__name__)


# バッチコンテンツ生成レスポンス: 文とその翻訳
class Sentence(BaseModel):
    sentence: str
    translation: str


# バッチコンテンツ生成レスポンス: コンテンツ
class Content(BaseModel):
    title: str
    sentences: List[Sentence]
    genre: str
    structure: str
    level: str
    target: str
    category: str
    level_id: int
    target_id: int
    category_id: int


# バッチコンテンツ生成レスポンス: 複数コンテンツ
class Contents(BaseModel):
    contents: List[Content]


def _weighted_index(counts: list[int]) -> int:
    inverse_weights = [1 / count for count in counts]
    return random.choices(list(range(len(counts))), weights=inverse_weights, k=1)[0]


def sample_specifications(
    level_summary: list[dict],
    target_summary: list[dict],
    category_summary: list[dict],
    batch_count: int,
) -> list[dict]:
    """出現数が少ないパラメータほど優先的に選ばれる重み付きサンプリング(純粋関数)。

    level_summary/target_summary/category_summaryは破壊的に変更されないよう
    呼び出し元のリストのコピーを内部で保持する。
    """
    level_counts = [row["count"] for row in level_summary]
    target_counts = [row["count"] for row in target_summary]
    category_counts = [row["count"] for row in category_summary]

    specifications = []
    for _ in range(batch_count):
        level_index = _weighted_index(level_counts)
        target_index = _weighted_index(target_counts)
        category_index = _weighted_index(category_counts)

        # バッチ処理では各パラメータの選択回数を毎回取得しないため、パラメータ生成時に更新する
        level_counts[level_index] += 1
        target_counts[target_index] += 1
        category_counts[category_index] += 1

        level = level_summary[level_index]
        target = target_summary[target_index]
        category = category_summary[category_index]
        genre = random.choice(GENRES[category["code"]])
        structure = random.choice(STRUCTURES)

        specifications.append(
            {
                "level": level["code"],
                "target": target["code"],
                "category": category["code"],
                "genre": genre,
                "structure": structure,
                "level_id": level["level_id"],
                "target_id": target["target_id"],
                "category_id": category["category_id"],
            }
        )
    return specifications


def fix_missing_period(sentence: str) -> str:
    """稀に末尾のピリオドが抜けている場合があるため救済する(純粋関数)。"""
    return sentence if sentence.endswith(".") else sentence + "."


def generate_contents(
    genai_client: GenaiClient, specifications: list[dict], gen_model: str
) -> list[dict]:
    batch_input = f"""
Generate one English listening content for each parameter set provided below.

For each content:
- Follow the specified level, target, category, genre, and structure.
- Generate the English passage and a Japanese translation for every sentence.
- The Japanese translation must follow the Translation Requirements in the system instructions.

[Content Specifications]

{json.dumps(specifications, ensure_ascii=False)}
"""
    interaction = genai_client.generate_json(
        model=gen_model,
        input=batch_input,
        response_schema=Contents.model_json_schema(),
        system_instruction=SYSTEM_INSTRUCTION,
    )
    try:
        result_dict = json.loads(interaction.output_text)
    except json.JSONDecodeError:
        debug_path = dump_debug_text("content_generation", interaction.output_text)
        logger.error(
            "Failed to parse Gemini response as JSON; raw response saved to %s",
            debug_path,
        )
        raise

    contents = []
    for content in result_dict["contents"]:
        content["gen_model"] = gen_model
        content["lang"] = "en"
        contents.append(content)
    return contents


def run(count: int, gen_model: str, settings: Settings) -> None:
    supabase_client = SupabaseClient(settings)
    genai_client = GenaiClient(settings)
    tts_client = TtsClient(settings)
    storage_client = StorageClient(settings)

    level_summary = supabase_client.raw.table("level_summary").select("*").execute().data
    target_summary = supabase_client.raw.table("target_summary").select("*").execute().data
    category_summary = (
        supabase_client.raw.table("category_summary").select("*").execute().data
    )

    specifications = sample_specifications(
        level_summary, target_summary, category_summary, count
    )
    contents = generate_contents(genai_client, specifications, gen_model)

    # 未処理データとしてローカル保存
    day = datetime.datetime.now().strftime("%Y%m%d")
    new_folder_path = pathlib.Path(f"../contents/new/{day}")
    done_folder_path = pathlib.Path(f"../contents/done/{day}")
    new_folder_path.mkdir(parents=True, exist_ok=True)
    done_folder_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%H%M%S")
    filename = f"{timestamp}.json"
    with open(f"{new_folder_path}/{filename}", "w") as f:
        json.dump(contents, f, indent=2, ensure_ascii=False)

    logger.info("%d contents generated.", len(contents))

    # 学習コンテンツと音声ファイルを生成
    saved = []
    unsaved = []
    saved_audio = []
    for content in tqdm(contents):
        for sentence in content["sentences"]:
            sentence["sentence"] = fix_missing_period(sentence["sentence"])

        content_text = "\n".join(
            sentence["sentence"] for sentence in content["sentences"]
        )
        param = {
            "title": content["title"],
            "content": content_text,
            "genre": content["genre"],
            "structure": content["structure"],
            "level_id": content["level_id"],
            "target_id": content["target_id"],
            "category_id": content["category_id"],
            "gen_model": content["gen_model"],
            "lang": content["lang"],
        }
        sentences_payload = [
            {
                "sentence": sentence["sentence"],
                "translation": sentence["translation"],
                "sentence_index": index,
            }
            for index, sentence in enumerate(content["sentences"])
        ]

        try:
            content_id = supabase_client.insert_content_with_sentences(
                param, sentences_payload
            )
        except Exception:
            logger.exception("Failed to save content: %s", content.get("title"))
            unsaved.append(content)
            continue

        saved.append(content)

        # 音声コンテンツ生成
        try:
            audio_param = generate_and_save_audio(
                tts_client, storage_client, supabase_client, content_id, content_text
            )
            saved_audio.append(audio_param["audio_path"])
        except Exception:
            logger.exception(
                "Failed to generate/save audio for content_id=%s", content_id
            )
            continue

    logger.info("%d contents were saved.", len(saved))
    logger.info("%d audio were saved.", len(saved_audio))
    logger.info("%d contents were not saved for the error.", len(unsaved))

    src = pathlib.Path(f"{new_folder_path.absolute()}/{filename}")
    if len(saved) == len(contents):
        # すべて保存したのでnewからdoneに移動
        dst = pathlib.Path(f"{done_folder_path.absolute()}/{filename}")
        src.rename(dst)
    else:
        # 一部保存に失敗したのでnewのファイルを未保存コンテンツで上書き
        with open(f"{src.absolute()}", "w") as f:
            json.dump(unsaved, f, indent=2)
