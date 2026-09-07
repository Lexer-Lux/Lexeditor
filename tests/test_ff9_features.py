from contextlib import contextmanager
from pathlib import Path
import pytest
from games.ff9 import features


@pytest.fixture
def env(tmp_path, monkeypatch):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = tmp_path / "runtime.dll"
    game.mkdir()
    project.mkdir()
    runtime.write_bytes(b"compiled-runtime")
    (game / "Memoria.ini").write_bytes(
        b'; keep\r\n[Mod]\r\nFolderNames = "OtherMod"\r\nPriorities = \r\n'
        b'[Unknown]\r\nThing = 7 ; keep\r\n'
    )
    (project / "StreamingAssets/Data/Items").mkdir(parents=True)
    (project / "StreamingAssets/Data/Items/Items.csv").write_bytes(b"data")
    monkeypatch.setattr(features.memoria_manager, "status", lambda root: {"installed": True})

    @contextmanager
    def guard(root):
        yield

    monkeypatch.setattr(features.memoria_manager, "configuration_write", guard)
    return game, project, runtime


def test_feature_save_is_stale_safe(env):
    _, project, _ = env
    first = features.load(project)
    saved = features.save({"ImprovedInterface": True, "BetterEat": True}, first["sha256"], project)
    assert saved["features"] == {"ImprovedInterface": True, "BetterEat": True}
    with pytest.raises(RuntimeError):
        features.save({"BetterEat": False}, "", project)


def test_deploy_preserves_ini_and_activates_first(env):
    game, project, runtime = env
    features.save({"ImprovedInterface": True, "BetterEat": True}, "", project)
    state = features.deploy(game, project, runtime)
    assert state["deployed"] and state["runtimeCurrent"]
    ini = (game / "Memoria.ini").read_bytes()
    assert b'[Unknown]\r\nThing = 7 ; keep\r\n' in ini
    assert b'FolderNames = "Lexeditor", "OtherMod"' in ini
    assert (game / "Lexeditor/StreamingAssets/Data/Items/Items.csv").read_bytes() == b"data"
    assert (game / "Lexeditor/StreamingAssets/Scripts/Memoria.Scripts.Lexeditor.dll").read_bytes() == runtime.read_bytes()
    state = features.revert(game, project, runtime)
    assert not state["deployed"]
    assert b'FolderNames = "OtherMod"' in (game / "Memoria.ini").read_bytes()
    assert b'[Unknown]\r\nThing = 7 ; keep\r\n' in (game / "Memoria.ini").read_bytes()


def test_refuses_foreign_mod_folder(env):
    game, project, runtime = env
    (game / "Lexeditor").mkdir()
    (game / "Lexeditor/user.txt").write_text("mine")
    with pytest.raises(RuntimeError, match="not owned"):
        features.deploy(game, project, runtime)
    assert (game / "Lexeditor/user.txt").read_text() == "mine"


def test_refuses_project_symlink(env, tmp_path):
    game, project, runtime = env
    outside = tmp_path / "outside"
    outside.write_text("x")
    (project / "StreamingAssets/Data/link").symlink_to(outside)
    with pytest.raises(RuntimeError, match="linked"):
        features.deploy(game, project, runtime)
