from contextlib import contextmanager
from pathlib import Path
import pytest
from plugins.ff9 import features


@pytest.fixture
def env(tmp_path, monkeypatch):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = tmp_path / "runtime.dll"
    game.mkdir()
    project.mkdir()
    runtime.write_bytes(b"compiled-runtime")
    (game / "Memoria.ini").write_bytes(
        b'; keep\r\n[Mod]\r\nFolderNames = "OtherMod", "SecondMod"\r\n'
        b'Priorities = "OtherMod", "SecondMod"\r\nMergeScripts = 1\r\n'
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
    expected = {"ImprovedInterface": True, "BetterEat": True, "XPBars": True, "HPMPBars": True, "RowRework": True}
    saved = features.save(expected, first["sha256"], project)
    assert saved["features"] == expected
    with pytest.raises(RuntimeError):
        features.save({"BetterEat": False}, "", project)


def test_deploy_preserves_ini_and_activates_first(env):
    game, project, runtime = env
    features.save({"ImprovedInterface": True, "BetterEat": True, "XPBars": True, "HPMPBars": True, "RowRework": True}, "", project)
    battle = project / "StreamingAssets/Assets/Resources/BattleMap/BattleScene/EVT_BATTLE_B3_001/dbfile0000.raw16.bytes"
    battle.parent.mkdir(parents=True)
    battle.write_bytes(b"canonical raw16 fixture")
    state = features.deploy(game, project, runtime)
    assert state["deployed"] and state["runtimeCurrent"]
    ini = (game / "Memoria.ini").read_bytes()
    assert b'[Unknown]\r\nThing = 7 ; keep\r\n' in ini
    assert b'FolderNames = "Lexeditor", "OtherMod", "SecondMod"' in ini
    assert b'Priorities = "Lexeditor", "OtherMod", "SecondMod"' in ini
    assert b'MergeScripts = 1\r\n' in ini
    assert (game / "Lexeditor/StreamingAssets/Data/Items/Items.csv").read_bytes() == b"data"
    assert (game / "Lexeditor/StreamingAssets/Scripts/Memoria.Scripts.Lexeditor.dll").read_bytes() == runtime.read_bytes()
    assert (game / "Lexeditor/StreamingAssets/Assets/Resources/BattleMap/BattleScene/EVT_BATTLE_B3_001/dbfile0000.raw16.bytes").read_bytes() == b"canonical raw16 fixture"
    config = (game / "Lexeditor/lexeditor-ff9.ini").read_text()
    assert "XPBars = 1" in config and "HPMPBars = 1" in config and "RowRework = 1" in config
    description = (game / "Lexeditor/ModDescription.xml").read_text(encoding="utf-8")
    assert "<Name>Lexeditor</Name>" in description
    assert "<InstallationPath>Lexeditor</InstallationPath>" in description
    state = features.revert(game, project, runtime)
    assert not state["deployed"]
    reverted = (game / "Memoria.ini").read_bytes()
    assert b'FolderNames = "OtherMod", "SecondMod"' in reverted
    assert b'Priorities = "OtherMod", "SecondMod"' in reverted
    assert b'MergeScripts = 1\r\n' in reverted
    assert b'[Unknown]\r\nThing = 7 ; keep\r\n' in reverted


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


def test_deploy_never_rewrites_external_mod_on_exact_path_collision(env):
    game, project, runtime = env
    external = game / "OtherMod/StreamingAssets/Data/Items/Items.csv"
    external.parent.mkdir(parents=True)
    external.write_bytes(b"external-real-style-mod-bytes")
    before = external.read_bytes()

    features.deploy(game, project, runtime)

    assert external.read_bytes() == before
    assert (game / "Lexeditor/StreamingAssets/Data/Items/Items.csv").read_bytes() == b"data"
    ini = (game / "Memoria.ini").read_text(encoding="utf-8")
    assert 'FolderNames = "Lexeditor", "OtherMod", "SecondMod"' in ini
    assert 'Priorities = "Lexeditor", "OtherMod", "SecondMod"' in ini


def test_missing_priorities_setting_is_not_invented(env):
    game, project, runtime = env
    original = (game / "Memoria.ini").read_bytes().replace(
        b'Priorities = "OtherMod", "SecondMod"\r\n', b""
    )
    (game / "Memoria.ini").write_bytes(original)

    features.deploy(game, project, runtime)
    assert b"Priorities" not in (game / "Memoria.ini").read_bytes()

    features.revert(game, project, runtime)
    reverted = (game / "Memoria.ini").read_bytes()
    assert b"Priorities" not in reverted
    assert b'FolderNames = "OtherMod", "SecondMod"' in reverted


def test_single_unquoted_memoria_mod_entry_is_preserved(env):
    game, project, runtime = env
    (game / "Memoria.ini").write_bytes(
        b"[Mod]\r\nFolderNames = OtherMod\r\nPriorities = OtherMod\r\n"
    )
    features.deploy(game, project, runtime)
    deployed = (game / "Memoria.ini").read_bytes()
    assert b'FolderNames = "Lexeditor", "OtherMod"' in deployed
    assert b'Priorities = "Lexeditor", "OtherMod"' in deployed
    features.revert(game, project, runtime)
    reverted = (game / "Memoria.ini").read_bytes()
    assert b'FolderNames = "OtherMod"' in reverted
    assert b'Priorities = "OtherMod"' in reverted


@pytest.mark.parametrize("setting", ["FolderNames", "Priorities"])
def test_duplicate_memoria_order_settings_fail_closed(env, setting):
    game, project, runtime = env
    data = (game / "Memoria.ini").read_bytes()
    needle = (setting + ' = "OtherMod", "SecondMod"\r\n').encode()
    data = data.replace(needle, needle + needle)
    (game / "Memoria.ini").write_bytes(data)
    before = (game / "Memoria.ini").read_bytes()
    with pytest.raises(RuntimeError, match="duplicate"):
        features.deploy(game, project, runtime)
    assert (game / "Memoria.ini").read_bytes() == before
    assert not (game / "Lexeditor").exists()


def test_revert_restores_owned_mod_when_ini_update_fails(env):
    game, project, runtime = env
    features.deploy(game, project, runtime)
    target = game / "Lexeditor"
    deployed_runtime = target / "StreamingAssets/Scripts/Memoria.Scripts.Lexeditor.dll"
    before_runtime = deployed_runtime.read_bytes()
    ini = game / "Memoria.ini"
    before = ini.read_bytes()
    duplicate = before.replace(
        b'Priorities = "Lexeditor", "OtherMod", "SecondMod"\r\n',
        b'Priorities = "Lexeditor", "OtherMod", "SecondMod"\r\n'
        b'Priorities = "Lexeditor", "OtherMod", "SecondMod"\r\n',
    )
    ini.write_bytes(duplicate)

    with pytest.raises(RuntimeError, match="duplicate"):
        features.revert(game, project, runtime)

    assert target.is_dir()
    assert deployed_runtime.read_bytes() == before_runtime
    assert ini.read_bytes() == duplicate


def test_unquoted_comma_is_one_memoria_path(env):
    game, project, runtime = env
    folder = game / "OtherMod, SecondMod"
    folder.mkdir()
    (game / "Memoria.ini").write_bytes(
        b"[Mod]\r\nFolderNames = OtherMod, SecondMod\r\n"
    )
    features.deploy(game, project, runtime)
    deployed = (game / "Memoria.ini").read_bytes()
    assert b'FolderNames = "Lexeditor", "OtherMod, SecondMod"' in deployed
