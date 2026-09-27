"""The last session's FFNx.log survives a relaunch, once."""
from plugins.ff8 import gameplay_settings


def test_the_previous_session_log_is_kept_and_replaced(tmp_path):
    (tmp_path / "FFNx.log").write_text("first session", encoding="utf-8")
    assert gameplay_settings.keep_previous_log(tmp_path) == tmp_path / "FFNx.previous.log"
    (tmp_path / "FFNx.log").write_text("second session", encoding="utf-8")
    gameplay_settings.keep_previous_log(tmp_path)
    assert (tmp_path / "FFNx.previous.log").read_text(encoding="utf-8") == "second session"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["FFNx.log", "FFNx.previous.log"]


def test_no_log_is_not_an_error(tmp_path):
    assert gameplay_settings.keep_previous_log(tmp_path) is None
