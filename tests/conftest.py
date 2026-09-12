from types import SimpleNamespace

import pytest


class FakeResponse:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class FakeQueryBuilder:
    """supabase-pyのクエリビルダの最小限のフェイク。

    .select().eq().execute() のようなメソッドチェーンをすべて自分自身を
    返すことで許容し、テストで用意した戻り値を .execute() で返す。
    """

    def __init__(self, table_state, table_name, result):
        self._table_state = table_state
        self._table_name = table_name
        self._result = result
        self._pending_insert = None

    def __getattr__(self, name):
        # .not_.is_(...) のように、呼び出さずに繋ぐ修飾子も許容する。
        if name == "not_":
            return self

        def _chain(*args, **kwargs):
            if name == "insert" and args:
                self._pending_insert = args[0]
            return self

        return _chain

    def execute(self):
        if self._pending_insert is not None:
            self._table_state.setdefault(self._table_name, []).append(
                self._pending_insert
            )
        return self._result


class FakeSupabaseClient:
    """kikiwake_cms.clients.supabase_client.SupabaseClient の代わりに注入するフェイク。

    テストしたいメソッドだけを差し替えられるよう、コンストラクタで
    table_results / rpc_results を渡す。
    """

    def __init__(self, table_results=None, rpc_results=None, rpc_returns=None):
        self.table_results = table_results or {}
        self.rpc_results = rpc_results or {}
        self.rpc_returns = rpc_returns
        self.table_state = {}
        self.rpc_calls = []
        self.raw = SimpleNamespace(table=self._table, rpc=self._rpc)

    def _table(self, name):
        result = self.table_results.get(name, FakeResponse(data=[]))
        return FakeQueryBuilder(self.table_state, name, result)

    def _rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return SimpleNamespace(execute=lambda: FakeResponse(data=self.rpc_returns))

    def insert_content_with_sentences(self, content, sentences):
        self.rpc_calls.append(("insert_content_with_sentences", (content, sentences)))
        return self.rpc_returns


class FakeStorageClient:
    def __init__(self):
        self.uploaded = []
        self.fetch_calls = []
        self.fetch_return = b""

    def upload(self, key, data, content_type):
        self.uploaded.append((key, data, content_type))

    def public_url(self, key):
        return f"https://example.test/{key}"

    def fetch_public(self, key):
        self.fetch_calls.append(key)
        return self.fetch_return


@pytest.fixture
def fake_supabase_client():
    return FakeSupabaseClient()


@pytest.fixture
def fake_storage_client():
    return FakeStorageClient()
