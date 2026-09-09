# パーソナライズドディクテーションアプリのデータ生成

Gemini(コンテンツ生成・翻訳・言語特徴抽出)、Google Cloud TTS(音声合成)、Supabase(永続化)、
Cloudflare R2(音声/JSONホスティング)を使ったデータ生成パイプライン。

## セットアップ

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

リポジトリルートに `.env` を用意する(`.env.example` を参照)。

GeminiのAPIキーは `GEMINI_API_KEY` / `GEMINI_API_KEY_2` / `GEMINI_API_KEY_3` に最大3本まで設定できる。
レート制限(429)に達したキーがあれば、待機せずに次のキーへ切り替えてリクエストする。
必須は `GEMINI_API_KEY` のみで、2本目以降は設定されていれば使う。

## 実行方法

インストール後は `kikiwake-cms` コマンドで各処理を実行できる。

```
kikiwake-cms generate-content -c 10 -m gemini-3.6-flash   # コンテンツ+音声をバッチ生成
kikiwake-cms generate-audio                                 # audio未生成のcontentsに音声を生成
kikiwake-cms backfill-audio-duration                        # duration未設定のaudioを再計算
kikiwake-cms analyze-audio-alignment                        # 文ごとの発話区間をGeminiで特定
kikiwake-cms translate-sentences                            # 未翻訳のsentencesを翻訳
kikiwake-cms extract-features -c 50 -m gemini-3.6-flash    # 言語的特徴を抽出
kikiwake-cms extract-audio-features -c 20 -m gemini-3.6-flash  # 音声特徴(連結音声現象)を解析(要: 発話区間の事前解析)
kikiwake-cms export-json                                    # アプリ配信用JSONをR2に出力
```

各サブコマンドの詳細は `kikiwake-cms <subcommand> --help` を参照。

## データベースマイグレーション

`sql/` ディレクトリにSupabase(PostgreSQL)へ適用するSQLを置いている。
`0001_insert_content_with_sentences.sql` は、コンテンツ生成時に `contents` と `sentences` を
アトミックに保存するためのRPC関数。SupabaseのSQL Editorで適用すること。

## テスト

```
pytest
```

## ディレクトリ構成

```
src/kikiwake_cms/
├── config.py          # 環境変数・定数の一元管理
├── retry.py            # Gemini/Supabase/R2向けのリトライポリシー
├── content_data.py     # コンテンツ生成用の定数(GENRES, STRUCTURES, SYSTEM_INSTRUCTION)
├── audio_utils.py      # 音声関連の純粋関数(duration計算等)
├── clients/            # 外部サービスへの薄いラッパー(Supabase, R2, TTS, Gemini)
├── services/           # 各バッチ処理のビジネスロジック
└── cli.py              # 統一CLIエントリポイント
```
