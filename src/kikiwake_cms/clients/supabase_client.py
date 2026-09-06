from supabase import Client, create_client

from ..config import Settings
from ..retry import supabase_retry


class SupabaseClient:
    """Supabaseへの薄いラッパー。

    各サービスで必要なクエリはテーブル構成に応じて多岐にわたるため、全てを
    個別メソッド化はせず `.raw` (supabase-pyの生クライアント) を任意のクエリに
    使えるようにしつつ、アトミック性が重要な操作(content+sentencesの同時insert)
    のみ専用メソッドとして提供する。
    """

    def __init__(self, settings: Settings):
        self.raw: Client = create_client(settings.supabase_url, settings.supabase_key)

    @supabase_retry()
    def insert_content_with_sentences(self, content: dict, sentences: list[dict]) -> int:
        """content 1件とその sentences をアトミックに保存する。

        sql/0001_insert_content_with_sentences.sql で定義された RPC 関数を使う。
        sentences の insert が失敗した場合、content の insert も含めて
        Postgres 側でロールバックされる。
        """
        response = self.raw.rpc(
            "insert_content_with_sentences",
            {"p_content": content, "p_sentences": sentences},
        ).execute()
        return response.data
