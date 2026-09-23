from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from games.ffx_x2 import launch


def _installation(tmp_path: Path) -> Path:
    root = tmp_path / "FINAL FANTASY FFX&FFX-2 HD Remaster"
    for relative in (
        "FFX.exe", "FFX-2.exe",
        "fahrenheit/bin/fhstage0.exe", "fahrenheit/bin/fhstage1.dll",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")
    return root


def test_launch_command_uses_stage0_bin_as_cwd_and_space_safe_relative_targets(tmp_path: Path):
    root = _installation(tmp_path)
    ffx, cwd = launch.command(root, "x")
    x2, cwd2 = launch.command(root, "x2")

    assert cwd == root / "fahrenheit" / "bin"
    assert cwd2 == cwd
    assert ffx == [str(cwd / "fhstage0.exe"), r"..\..\FFX.exe"]
    assert x2 == [str(cwd / "fhstage0.exe"), r"..\..\FFX-2.exe"]
    assert "FINAL FANTASY" not in ffx[1]
    assert "FINAL FANTASY" not in x2[1]


def test_launch_status_reports_stage_and_game_readiness_independently(tmp_path: Path):
    root = _installation(tmp_path)
    state = launch.status(root)
    assert state["ready"] is True
    assert state["stage0Ready"] is True
    assert state["stage1Ready"] is True
    assert state["games"]["x"]["ready"] is True
    assert state["games"]["x2"]["ready"] is True

    (root / "FFX-2.exe").unlink()
    state = launch.status(root)
    assert state["ready"] is True
    assert state["games"]["x"]["ready"] is True
    assert state["games"]["x2"]["ready"] is False


def test_launch_command_fails_closed_when_loader_or_target_is_missing(tmp_path: Path):
    root = _installation(tmp_path)
    (root / "fahrenheit" / "bin" / "fhstage1.dll").unlink()
    with pytest.raises(launch.LaunchError, match="Stage 1"):
        launch.command(root, "x")

    (root / "fahrenheit" / "bin" / "fhstage1.dll").write_bytes(b"fixture")
    (root / "FFX.exe").unlink()
    with pytest.raises(launch.LaunchError, match="Game executable"):
        launch.command(root, "x")


def test_launch_rejects_unknown_collection_key(tmp_path: Path):
    root = _installation(tmp_path)
    with pytest.raises(ValueError, match="game must"):
        launch.command(root, "launcher")


def test_non_windows_launch_refuses_before_spawning(tmp_path: Path):
    if launch.os.name == "nt":
        pytest.skip("non-Windows guard is exercised on the Linux CI leg")
    root = _installation(tmp_path)
    with pytest.raises(launch.LaunchError, match="only on Windows"):
        launch.launch(root, "x")


def test_windows_launch_uses_no_console_creation_flag(monkeypatch: pytest.MonkeyPatch):
    argv = [r"C:\Fixture\fahrenheit\bin\fhstage0.exe", r"..\..\FFX.exe"]
    cwd = Path(r"C:\Fixture\fahrenheit\bin")
    captured = {}

    class Process:
        pid = 4321

    monkeypatch.setattr(launch, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(launch, "command", lambda _root, _game: (argv, cwd))
    monkeypatch.setattr(launch.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Process()

    monkeypatch.setattr(launch.subprocess, "Popen", fake_popen)
    result = launch.launch("fixture", "x")

    assert captured["args"] == argv
    assert captured["kwargs"] == {
        "cwd": str(cwd),
        "close_fds": True,
        "creationflags": 0x08000000,
    }
    assert result["pid"] == 4321
    assert result["target"] == "FFX.exe"
