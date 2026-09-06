from unittest.mock import patch

from kikiwake_cms.audio_utils import mp3_duration_seconds


def test_mp3_duration_seconds_truncates_to_int():
    with patch("kikiwake_cms.audio_utils.MP3") as mock_mp3:
        mock_mp3.return_value.info.length = 12.9
        duration = mp3_duration_seconds(b"fake-mp3-bytes")

    assert duration == 12
