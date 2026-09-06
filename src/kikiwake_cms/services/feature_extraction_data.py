"""feature_extraction サービス用の静的データ(system_instruction, feature master list)。

旧 extract_linguistic_features.py のトップレベルにあった巨大な定数群を分離したもの。
"""

system_instruction = """
あなたは、英語学習コンテンツの言語的特徴を抽出する解析エンジンです。

入力として、複数の英語コンテンツが与えられます。
各コンテンツには `content_id` と複数の `sentence` 、コンテンツの学習レベル `level` が含まれます。学習レベルは CEFR の a1, a2, b1, b2, c1 が与えられます。
各sentenceには `sentence_id`、`sentence_index`、`sentence` が含まれます。

各コンテンツを独立した英語学習コンテンツとして解析し、各sentenceから学習価値の高い言語的特徴を抽出してください。

## 基本方針

目的は、英文に存在する言語的特徴を網羅的にアノテーションすることではありません。

**英語学習者が、その文を復習するときに学習する価値が高い特徴だけを抽出してください。**

文法的・語彙的・表現的に特徴が存在していても、一般的すぎる、容易すぎる、または学習上の価値が低い場合は抽出しないでください。

特徴が存在しないsentenceは結果に含めなくて構いません。

1つのsentenceに対して、通常は1〜3個程度の重要なfeatureを抽出してください。
ただし、学習価値の高い特徴が複数存在する場合は3個を超えても構いません。
逆に、重要なfeatureが1つもない場合は抽出しないでください。

## バッチ処理

入力には複数のcontentが含まれる場合があります。

各contentおよび各sentenceを混同しないでください。

* `content_id` は必ず入力されたcontent_idをそのまま使用する。
* `sentence_id` は必ず入力されたsentence_idをそのまま使用する。
* あるcontentのsentenceから得られたfeatureを、別のcontentのsentenceに関連付けてはいけない。
* 各contentは完全に独立して解析する。
* content間の比較や重複排除は行わない。
* 同じfeatureが複数のcontentに存在する場合、それぞれ独立して抽出する。

## Feature category

使用できるfeature categoryは以下の3種類です。

* grammar
* vocabulary
* expression

## 使用可能なfeature

入力として提供されたfeature master listに存在するfeature_id / feature_codeのみ使用してください。

feature master listに存在しないfeatureを新しく作成したり、feature_idを推測したりしてはいけません。

## Grammar

grammar featureは、文の構造や文法的な形式に明確な学習価値がある場合に抽出してください。

単に文法的に存在するという理由だけで抽出しないでください。

特に以下を意識してください。

* tense/aspect
* passive voice
* modal constructions
* questions
* conditionals
* infinitives
* gerunds
* participial phrases
* relative clauses
* noun clauses
* adverbial clauses
* reported speech
* articles
* pronouns
* prepositions
* conjunctions
* subject-verb agreement
* inversion
* ellipsis
* cleft constructions

ただし、非常に基本的で、文の中で特に学習価値がない場合は抽出しなくて構いません。

## Vocabulary

vocabularyは、学習者にとって学習価値の高い語彙のみ抽出してください。

### advanced_word

対象レベルの学習者にとって明確に難しく、習得する価値のある語を抽出してください。

単に、

* 長い単語
* 技術的な単語
* 正式な単語
* 文脈上重要な単語

という理由だけでadvanced_wordにしてはいけません。

### academic_word

academic Englishで特徴的に使用され、学習価値の高い語を抽出してください。

文章が大学・研究・科学などのacademic topicだからという理由だけでacademic_wordにしてはいけません。

単語そのものがacademic vocabularyとして学習価値を持つ場合に限定してください。

### phrasal_verb

典型的なphrasal verbのみ抽出してください。

基本的にはverb + particle/adverbによる慣用的な組み合わせを対象とします。

例:

* look up
* figure out
* carry out
* put off
* take over

通常のverb + prepositionはphrasal_verbとして扱わないでください。

例:

* focus on
* partner with
* depend on
* believe in

これらはphrasal_verbとして抽出しないでください。

### collocation

単に自然な単語の組み合わせや普通の名詞句をcollocationとして抽出してはいけません。

英語学習者が単語単体ではなく、まとまりとして習得する明確な価値がある、典型的かつ定着した組み合わせのみ抽出してください。

例:

* take responsibility
* make an effort
* meet a deadline
* raise awareness

以下のような単なる自然な名詞句は、原則として抽出しないでください。

* electric vehicles
* academic institutions
* technical specifications
* project timeline
* renewable energy

ただし、特定の表現として明確な学習価値がある場合は例外とします。

### idiom

文字通りの意味から容易に推測できない慣用表現など、学習価値の高いidiomのみ抽出してください。

### word_formation

接頭辞、接尾辞、語形変化など、語形成そのものが学習ポイントになる場合に抽出してください。

単に派生語であるという理由だけでは抽出しないでください。

## Expression

expressionは、単語単体ではなく、まとまりとして覚える価値がある表現を抽出してください。

### fixed_expression

定型的・慣用的に使用される表現を抽出してください。

### conversational_expression

会話で頻繁に使われる自然な表現を抽出してください。

### discourse_marker

話の流れ、論理関係、話題転換、追加、対比などを示す表現を抽出してください。

### polite_expression

依頼、提案、許可、謝意などに用いられる、学習価値の高い丁寧表現を抽出してください。

### functional_expression

特定のコミュニケーション機能を果たす表現を抽出してください。

例:

* asking for clarification
* making a suggestion
* expressing an opinion
* agreeing/disagreeing
* giving advice

単なる自然な単語の組み合わせはexpressionとして抽出しないでください。

## Feature selection

同じ箇所に複数のfeatureを付与できる場合でも、すべてを機械的に抽出しないでください。

より具体的で、学習価値の高いfeatureを優先してください。

例えば、単語がphrasal verbとして明確に成立している場合、単にadvanced_wordとしても重複して登録する必要はありません。

同様に、単なる一般的な単語をadvanced_wordとして抽出しないでください。

**「このfeatureをアプリで学習者に表示する価値があるか」**を最終判断基準としてください。

## Index

`start_index` と `end_index` は文字位置ではなく、sentence内の**単語インデックス**です。

単語インデックスは0から開始します。

`end_index` はexclusiveです。

例:

Sentence:
`We are looking for new opportunities.`

単語:

* 0 = We
* 1 = are
* 2 = looking
* 3 = for
* 4 = new
* 5 = opportunities

`looking for` を対象とする場合:

`start_index = 2`
`end_index = 4`

としてください。

featureの意味を構成するために必要な範囲を正確に指定してください。

featureに不要な単語を範囲に含めないでください。

## Translation

translationは、sentence全体の日本語訳ではありません。

**抽出したfeatureの該当範囲だけを日本語にしてください。**

例えば、

`We are proud to announce the new project.`

から

`proud to announce`

をfeatureとして抽出する場合、

`translation = "〜を誇りを持って発表する"`

のように、featureそのものを理解するための日本語訳を設定してください。

sentence全体の意味をtranslationに入れてはいけません。

また、文法構造そのものなど、日本語訳を付ける必要がないfeatureについては `null` を使用してください。

特にgrammar featureでは、feature名だけで意味が明確であり、該当範囲の日本語訳が学習上不要な場合はtranslationをnullにしてください。

translationが必要な場合は、入力sentenceの文脈を考慮して自然な日本語にしてください。

## Input fidelity

入力されたsentenceの文字列を変更・修正・正規化してはいけません。

sentenceの単語順、句読点、スペルなどをそのまま維持した上で、indexを計算してください。

## Output

各featureについて以下を返してください。

* content_id
* sentence_id
* feature_id
* start_index
* end_index
* translation

feature_idはfeature master listに存在するものを使用してください。

結果はJSON配列として返してください。

"""

# 特徴項目一覧
features = [
    {
        "feature_id": 1,
        "feature_code": "present_simple",
        "category_code": "grammar",
    },
    {
        "feature_id": 2,
        "feature_code": "present_continuous",
        "category_code": "grammar",
    },
    {
        "feature_id": 3,
        "feature_code": "present_perfect",
        "category_code": "grammar",
    },
    {
        "feature_id": 4,
        "feature_code": "present_perfect_continuous",
        "category_code": "grammar",
    },
    {
        "feature_id": 5,
        "feature_code": "past_simple",
        "category_code": "grammar",
    },
    {
        "feature_id": 6,
        "feature_code": "past_continuous",
        "category_code": "grammar",
    },
    {
        "feature_id": 7,
        "feature_code": "past_perfect",
        "category_code": "grammar",
    },
    {
        "feature_id": 8,
        "feature_code": "past_perfect_continuous",
        "category_code": "grammar",
    },
    {
        "feature_id": 9,
        "feature_code": "future_will",
        "category_code": "grammar",
    },
    {
        "feature_id": 10,
        "feature_code": "be_going_to",
        "category_code": "grammar",
    },
    {
        "feature_id": 11,
        "feature_code": "future_continuous",
        "category_code": "grammar",
    },
    {
        "feature_id": 12,
        "feature_code": "future_perfect",
        "category_code": "grammar",
    },
    {
        "feature_id": 13,
        "feature_code": "future_perfect_continuous",
        "category_code": "grammar",
    },
    {
        "feature_id": 14,
        "feature_code": "passive_voice",
        "category_code": "grammar",
    },
    {
        "feature_id": 15,
        "feature_code": "modal_verb",
        "category_code": "grammar",
    },
    {
        "feature_id": 16,
        "feature_code": "modal_perfect",
        "category_code": "grammar",
    },
    {
        "feature_id": 17,
        "feature_code": "imperative",
        "category_code": "grammar",
    },
    {
        "feature_id": 18,
        "feature_code": "negative",
        "category_code": "grammar",
    },
    {
        "feature_id": 19,
        "feature_code": "yes_no_question",
        "category_code": "grammar",
    },
    {
        "feature_id": 20,
        "feature_code": "wh_question",
        "category_code": "grammar",
    },
    {
        "feature_id": 21,
        "feature_code": "tag_question",
        "category_code": "grammar",
    },
    {
        "feature_id": 22,
        "feature_code": "conditional",
        "category_code": "grammar",
    },
    {
        "feature_id": 23,
        "feature_code": "subjunctive",
        "category_code": "grammar",
    },
    {
        "feature_id": 24,
        "feature_code": "comparative",
        "category_code": "grammar",
    },
    {
        "feature_id": 25,
        "feature_code": "superlative",
        "category_code": "grammar",
    },
    {
        "feature_id": 26,
        "feature_code": "infinitive",
        "category_code": "grammar",
    },
    {
        "feature_id": 27,
        "feature_code": "gerund",
        "category_code": "grammar",
    },
    {
        "feature_id": 28,
        "feature_code": "participial_phrase",
        "category_code": "grammar",
    },
    {
        "feature_id": 29,
        "feature_code": "relative_clause",
        "category_code": "grammar",
    },
    {
        "feature_id": 30,
        "feature_code": "noun_clause",
        "category_code": "grammar",
    },
    {
        "feature_id": 31,
        "feature_code": "adverbial_clause",
        "category_code": "grammar",
    },
    {
        "feature_id": 32,
        "feature_code": "that_clause",
        "category_code": "grammar",
    },
    {
        "feature_id": 33,
        "feature_code": "reported_speech",
        "category_code": "grammar",
    },
    {
        "feature_id": 34,
        "feature_code": "article",
        "category_code": "grammar",
    },
    {
        "feature_id": 35,
        "feature_code": "countable_uncountable",
        "category_code": "grammar",
    },
    {
        "feature_id": 36,
        "feature_code": "pronoun",
        "category_code": "grammar",
    },
    {
        "feature_id": 37,
        "feature_code": "possessive",
        "category_code": "grammar",
    },
    {
        "feature_id": 38,
        "feature_code": "preposition",
        "category_code": "grammar",
    },
    {
        "feature_id": 39,
        "feature_code": "conjunction",
        "category_code": "grammar",
    },
    {
        "feature_id": 40,
        "feature_code": "subject_verb_agreement",
        "category_code": "grammar",
    },
    {
        "feature_id": 41,
        "feature_code": "there_is_are",
        "category_code": "grammar",
    },
    {
        "feature_id": 42,
        "feature_code": "it_extraposition",
        "category_code": "grammar",
    },
    {
        "feature_id": 43,
        "feature_code": "cleft_sentence",
        "category_code": "grammar",
    },
    {
        "feature_id": 44,
        "feature_code": "inversion",
        "category_code": "grammar",
    },
    {
        "feature_id": 45,
        "feature_code": "ellipsis",
        "category_code": "grammar",
    },
    {
        "feature_id": 46,
        "feature_code": "advanced_word",
        "category_code": "vocabulary",
    },
    {
        "feature_id": 47,
        "feature_code": "academic_word",
        "category_code": "vocabulary",
    },
    {
        "feature_id": 48,
        "feature_code": "phrasal_verb",
        "category_code": "vocabulary",
    },
    {
        "feature_id": 49,
        "feature_code": "collocation",
        "category_code": "vocabulary",
    },
    {
        "feature_id": 50,
        "feature_code": "idiom",
        "category_code": "vocabulary",
    },
    {
        "feature_id": 51,
        "feature_code": "word_formation",
        "category_code": "vocabulary",
    },
    {
        "feature_id": 52,
        "feature_code": "fixed_expression",
        "category_code": "expression",
    },
    {
        "feature_id": 53,
        "feature_code": "conversational_expression",
        "category_code": "expression",
    },
    {
        "feature_id": 54,
        "feature_code": "discourse_marker",
        "category_code": "expression",
    },
    {
        "feature_id": 55,
        "feature_code": "polite_expression",
        "category_code": "expression",
    },
    {
        "feature_id": 56,
        "feature_code": "functional_expression",
        "category_code": "expression",
    },
]
