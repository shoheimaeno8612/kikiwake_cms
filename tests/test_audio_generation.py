from unittest.mock import patch

from kikiwake_cms.clients.tts_client import TtsOutput
from kikiwake_cms.services.audio_generation import generate_and_save_audio


class FakeTtsClient:
    def __init__(self, output: TtsOutput):
        self._output = output

    def synthesize(self, text):
        return self._output


def test_generate_and_save_audio_does_not_refetch_from_storage(
    fake_storage_client, fake_supabase_client
):
    output = TtsOutput(
        bytes=b"fake-mp3-bytes",
        language="en",
        country="us",
        text="hello",
        gender=1,
        name="en-US-Chirp3-HD-Test",
    )
    tts_client = FakeTtsClient(output)

    with patch(
        "kikiwake_cms.services.audio_generation.mp3_duration_seconds",
        return_value=7,
    ) as mock_duration:
        param = generate_and_save_audio(
            tts_client,
            fake_storage_client,
            fake_supabase_client,
            content_id=42,
            text="hello",
        )

    # durationはTTS生成直後のメモリ上のバイト列から計算されるため、
    # R2へアップロードしたファイルを再取得(fetch_public)する必要はない。
    assert fake_storage_client.fetch_calls == []
    mock_duration.assert_called_once_with(b"fake-mp3-bytes")

    assert param["content_id"] == 42
    assert param["duration"] == 7
    assert param["country"] == "us"
    assert param["speaker"] == "en-US-Chirp3-HD-Test"
    assert fake_storage_client.uploaded[0][0] == param["audio_path"]
    assert fake_supabase_client.table_state["audio"] == [param]
