import datetime
import pathlib


def dump_debug_text(category: str, content: str) -> pathlib.Path:
    """デバッグ用に任意のテキストをローカルファイルへ保存し、そのパスを返す。

    Geminiの応答がJSONとしてパースできない場合など、原因調査のために
    生のレスポンステキストを残しておきたい場合に使う。
    """
    folder = pathlib.Path(f"../debug/{category}")
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = folder / f"{timestamp}.txt"
    path.write_text(content)
    return path
