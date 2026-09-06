from kikiwake_cms.debug_utils import dump_debug_text


def test_dump_debug_text_writes_file_and_returns_path(tmp_path, monkeypatch):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    path = dump_debug_text("feature_extraction", "not valid json {")

    assert path.exists()
    assert path.read_text() == "not valid json {"
    assert path.resolve().parent == (tmp_path / "debug" / "feature_extraction").resolve()
