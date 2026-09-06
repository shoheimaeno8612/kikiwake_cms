-- contents 1件とその sentences をアトミックに保存する RPC 関数。
--
-- 従来はPython側で「contents insert → sentencesを1件ずつループinsert」としていたため、
-- sentencesの途中でエラーが起きるとcontentsだけが残る不整合が起こり得た。
-- この関数はPostgres関数本体全体が1トランザクションとして実行されるため、
-- sentencesのinsertが失敗すればcontentsのinsertも自動的にロールバックされる。
--
-- 適用方法: SupabaseのSQL Editorでこのファイルの内容を実行してください。
-- (このセッションからはSupabaseに接続できないため、適用はユーザー側で行う必要があります)

create or replace function insert_content_with_sentences(
  p_content jsonb,
  p_sentences jsonb
) returns int
language plpgsql
as $$
declare
  v_content_id int;
begin
  insert into contents (
    title,
    content,
    genre,
    structure,
    level_id,
    target_id,
    category_id,
    gen_model,
    lang
  )
  values (
    p_content->>'title',
    p_content->>'content',
    p_content->>'genre',
    p_content->>'structure',
    (p_content->>'level_id')::int,
    (p_content->>'target_id')::int,
    (p_content->>'category_id')::int,
    p_content->>'gen_model',
    p_content->>'lang'
  )
  returning content_id into v_content_id;

  insert into sentences (
    content_id,
    sentence,
    translation,
    sentence_index
  )
  select
    v_content_id,
    s->>'sentence',
    s->>'translation',
    (s->>'sentence_index')::int
  from jsonb_array_elements(p_sentences) as s;

  return v_content_id;
end;
$$;
