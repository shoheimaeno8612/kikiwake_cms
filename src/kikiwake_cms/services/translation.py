import json
from typing import List

from pydantic import BaseModel, Field
from tqdm import tqdm

from ..clients.genai_client import GenaiClient
from ..clients.supabase_client import SupabaseClient
from ..config import Settings
from ..debug_utils import dump_debug_text
from ..logging_config import get_logger

logger = get_logger(__name__)


class Sentence(BaseModel):
    sentence_id: int = Field(description="Sentence ID")
    sentence: str = Field(description="Sentence")
    translation: str = Field(description="Translation")
    sentence_index: int = Field(description="Sentence Index")


class Sentences(BaseModel):
    sentences: List[Sentence]


def run(settings: Settings) -> None:
    """sentencesの翻訳を登録する(旧translate_sentences.py)。"""
    supabase_client = SupabaseClient(settings)
    genai_client = GenaiClient(settings)
    batch_size = settings.translation_batch_size

    while True:
        sentences_response = (
            supabase_client.raw.table("contents")
            .select(
                "content_id,sentences!inner(sentence_id,sentence,sentence_index)",
                count="exact",
            )
            .eq("sentences.translation", "")
            .order("sentence_index", foreign_table="sentences")
            .limit(batch_size)
            .execute()
        )

        batch = [json.dumps(row["sentences"]) for row in sentences_response.data]

        interaction = genai_client.generate_json(
            model="gemini-3.6-flash",
            response_schema=Sentences.model_json_schema(),
            input=[
                {
                    "type": "text",
                    "text": f"""
    入力の[Batch Sentences]は、一つの英語コンテンツを構成するsentence、sentence_id、sentence_indexの配列からなる複数のコンテンツの情報です。

    各コンテンツの全体を文脈として考慮し、それぞれのsentenceを自然な日本語に翻訳してください。

    翻訳時は以下のルールに従ってください。

    - 各sentenceは、それぞれ個別のtranslationとして翻訳してください。
    - sentence単体ではなく、前後のsentenceを含むコンテンツ全体の文脈を考慮してください。
    - 代名詞、省略表現、指示語などは、文脈から意味を適切に判断してください。
    - 日本語として自然で読みやすい表現にしてください。
    - 不自然な直訳や逐語訳は避けてください。
    - 原文の意味や情報を変更したり、原文にない情報を追加したりしないでください。
    - 英文の内容に忠実な翻訳にしてください。
    - sentenceごとの翻訳であるため、複数のsentenceを一つの日本語文にまとめないでください。

    [Batch Sentences]
    {'\n'.join(batch)}

    response_schemaに従ってJSONのみを出力してください。
        """,
                },
            ],
        )

        try:
            result_dict = json.loads(interaction.output_text)
        except json.JSONDecodeError:
            debug_path = dump_debug_text("translation", interaction.output_text)
            logger.error(
                "Failed to parse Gemini response as JSON; raw response saved to %s. "
                "Stopping here to avoid repeatedly re-fetching the same batch.",
                debug_path,
            )
            break

        logger.info("Gemini usage: %s", interaction.usage)

        for data in tqdm(result_dict["sentences"]):
            supabase_client.raw.table("sentences").update(
                {"translation": data["translation"]}
            ).eq("sentence_id", data["sentence_id"]).execute()

        if len(sentences_response.data) < batch_size:
            break
