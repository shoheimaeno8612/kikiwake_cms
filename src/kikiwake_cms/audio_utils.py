import io

from mutagen.mp3 import MP3


def mp3_duration_seconds(data: bytes) -> int:
    """MP3バイト列から長さ(秒)を計算する純粋関数。

    音声生成直後はバイト列がメモリ上に既にあるため、この関数を直接呼べば
    アップロード済みファイルをHTTP経由で再取得する必要がない。
    """
    audio = MP3(io.BytesIO(data))
    return int(audio.info.length)
