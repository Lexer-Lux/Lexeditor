"""The gameplay patch check counts its 20 seconds from the game starting.

Lexer: Lexeditor showed "FFNx patch check timed out" unless he pressed Play in
the FF8 launcher at once. FFNx starts with the game, not the launcher, so the
editor asks whether the game itself (FF8_EN.exe) is running and only starts
its clock then.
"""
from pathlib import Path

from plugins.ff8 import gameplay_settings

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_status_reports_whether_the_game_itself_started(tmp_path):
    for started in (False, True):
        status = gameplay_settings.runtime_status(
            tmp_path, tmp_path, runtime_root=tmp_path,
            game_running=lambda: True, game_started=lambda value=started: value)
        assert status["gameStarted"] is started
        assert status["loaded"] is False


def test_the_editor_waits_in_the_launcher_and_times_from_the_game():
    source = (ROOT / "plugins" / "ff8" / "boot.js").read_text(encoding="utf-8")
    start = source.index("async function confirmGameplayPatch(){")
    body = source[start:source.index("showAlert({title:\"FFNx patch check timed out\"", start)]
    assert "status.gameStarted&&startedAt===null" in body
    assert "attempt-startedAt>=40" in body, "20 seconds of 500 ms polls after the game starts"
    assert "startedAt===null&&!status.gameRunning" in body, "closing the launcher stops the check quietly"
