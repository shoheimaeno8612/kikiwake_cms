import pandas as pd

from kikiwake_cms.services.json_export import chunk_dataframe, save_chunks


def test_chunk_dataframe_splits_by_size():
    df = pd.DataFrame({"value": list(range(25))})

    chunks = chunk_dataframe(df, 10)

    assert len(chunks) == 3
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5


def test_chunk_dataframe_empty():
    df = pd.DataFrame({"value": []})

    assert chunk_dataframe(df, 10) == []


def test_save_chunks_uploads_each_chunk_with_sequential_names(fake_storage_client):
    df = pd.DataFrame({"value": list(range(15))})

    save_chunks(fake_storage_client, df, "json/contents/a1", 10)

    uploaded_keys = [key for key, _, _ in fake_storage_client.uploaded]
    assert uploaded_keys == ["json/contents/a1/1.json", "json/contents/a1/2.json"]
    for _, _, content_type in fake_storage_client.uploaded:
        assert content_type == "application/json"
