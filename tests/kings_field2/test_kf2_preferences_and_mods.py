"""Preservation, native-mod coexistence, and rollback for Verdite2 integration."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.kings_field2 import model
from plugins.kings_field2.mod_support import LEDGER, RECOVERY, VerditeModAdapter


def test_service_is_registered_for_normal_and_frozen_launches():
    from core.runtime_bootstrap import service_command
    assert "plugins.kings_field2.server" in service_command("plugins.kings_field2.server", owned=True)


def test_non_steam_game_validates_without_steam_discovery_or_art_requests(tmp_path):
    from core.plugin_api import validate_plugin
    from core.game_installation import GameInstallationManager
    from core.cover_art import CoverArtCache
    from plugins.kings_field2.plugin import PLUGIN
    validate_plugin(PLUGIN)
    assert GameInstallationManager._steam_candidates("", ("Verdite2",)) == []

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("A non-Steam port must not request a Steam cover")

    covers = CoverArtCache({PLUGIN.plugin_id: PLUGIN}, root=tmp_path,
                          fetcher=unexpected_fetch, steam_roots=())
    assert not covers._threads
    assert covers._states[PLUGIN.plugin_id]["state"] == "unavailable"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    game, data, library = (tmp_path / name for name in ("game", "data", "library"))
    for path in (game / "bin", game / "content/config", data / "mods", library):
        path.mkdir(parents=True)
    for name in ("Verdite2.exe", "RecompOne.Runtime.dll"):
        (game / "bin" / name).write_bytes(b"synthetic only")
    (game / "content/config/kf2.json").write_text('{"game":{"id":"SLUS-00158","name":"KingsField2"}}')
    (data / "settings.json").write_text(json.dumps({"ActiveMods": ["external.map"], "Unmodeled": {"keep": 42}}))
    monkeypatch.setenv("LEXEDITOR_KF2_DATA", str(data))
    monkeypatch.setattr(model, "live_processes", lambda _: [])
    return game, data, library


def mod(library, name="example"):
    root = library / name
    root.mkdir()
    (root / "mod.json").write_text(json.dumps({"id": name, "name": name}))
    (root / "Mod.cs").write_text("// synthetic source; never compiled or executed\n")
    return root


def test_ini_noop_is_byte_exact_and_changes_preserve_other_sections():
    raw = b"\xef\xbb\xbf; head\r\n[RecompOne]\r\n  kf2.mouse.turn =1\r\nMystery = keep\r\n[Window][Output]\r\nPos=12,34\r\n"
    assert model.updated_ini(raw, {}) == raw
    output = model.updated_ini(raw, {"kf2.mouse.turn": "2", "kf2.mouse.look": "3"})
    assert output == raw.replace(b"kf2.mouse.turn =1", b"kf2.mouse.turn =2").replace(b"[Window]", b"kf2.mouse.look=3\r\n[Window]")


def test_preferences_save_is_bounded_preserves_unknowns_and_refuses_stale(setup):
    _, data, _ = setup
    path = data / "interface.ini"
    path.write_bytes(b"[RecompOne]\nkf2.mouse.turn=1\nother=keep\n[Docking][Data]\nDockNode=0x1\n")
    before = model.preferences(data)
    result = model.save_preferences(data, {"kf2.mouse.turn": 2}, before["fingerprint"])
    assert result["fields"][0]["value"] == 2
    assert b"other=keep\n[Docking][Data]\nDockNode=0x1\n" in path.read_bytes()
    assert path.with_suffix(".ini.lexeditor-previous").read_bytes().startswith(b"[RecompOne]")
    with pytest.raises(ValueError, match="changed since"):
        model.save_preferences(data, {"kf2.mouse.turn": 3}, before["fingerprint"])
    for value in (-1, 6, float("nan"), True, "2"):
        with pytest.raises(ValueError):
            model.save_preferences(data, {"kf2.mouse.turn": value}, result["fingerprint"])


def test_duplicate_ini_facts_are_rejected():
    for text in ("[RecompOne]\na=1\na=2\n", "[RecompOne]\na=1\n[RecompOne]\na=2\n"):
        with pytest.raises(ValueError, match="repeat|duplicate"):
            model.ini_values(text)


def test_distance_and_smooth_fade_persist_independently(setup):
    _, data, _ = setup
    prefs = model.preferences(data)
    prefs = model.save_preferences(data, {"kf2.renderdistance": 14.5}, prefs["fingerprint"])
    prefs = model.save_preferences(data, {"kf2.distancefade.on": True}, prefs["fingerprint"])
    values = {field["key"]: field["value"] for field in prefs["fields"]}
    assert values["kf2.renderdistance"] == 14.5 and values["kf2.distancefade.on"] is True
    prefs = model.save_preferences(data, {"kf2.distancefade.on": False}, prefs["fingerprint"])
    values = {field["key"]: field["value"] for field in prefs["fields"]}
    assert values["kf2.renderdistance"] == 14.5 and values["kf2.distancefade.on"] is False
    with pytest.raises(ValueError, match="between"):
        model.save_preferences(data, {"kf2.renderdistance": 16}, prefs["fingerprint"])


def test_running_game_is_never_modified(setup, monkeypatch):
    game, data, library = setup
    source = mod(library)
    before = (data / "settings.json").read_bytes()
    monkeypatch.setattr(model, "live_processes", lambda _: [{"pid": 123}])
    with pytest.raises(ValueError, match="Close Verdite2"):
        VerditeModAdapter().activate([source], game)
    with pytest.raises(ValueError, match="Close Verdite2"):
        model.save_preferences(data, {}, model.fingerprint(b""))
    assert (data / "settings.json").read_bytes() == before
    assert not (data / LEDGER).exists()


def test_activation_and_removal_preserve_native_mods_and_settings(setup):
    game, data, library = setup
    source = mod(library)
    native = data / "mods/map"
    native.mkdir()
    (native / "mod.json").write_text('{"id":"external.map","name":"Native map"}')
    original = (native / "mod.json").read_bytes()
    adapter = VerditeModAdapter()
    result = adapter.activate([source], game)
    assert result["mods"] == ["external.map", "example"]
    assert (data / "mods/lexeditor-example/Mod.cs").read_bytes() == (source / "Mod.cs").read_bytes()
    assert not (data / RECOVERY).exists()
    adapter.activate([], game)
    assert not (data / "mods/lexeditor-example").exists()
    settings = json.loads((data / "settings.json").read_text())
    assert settings == {"ActiveMods": ["external.map"], "Unmodeled": {"keep": 42}}
    assert (native / "mod.json").read_bytes() == original


def test_external_mod_edits_refuse_replacement(setup):
    game, data, library = setup
    source = mod(library)
    adapter = VerditeModAdapter()
    adapter.activate([source], game)
    target = data / "mods/lexeditor-example/Mod.cs"
    target.write_text("// player's changes\n")
    with pytest.raises(ValueError, match="changed outside"):
        adapter.activate([], game)
    assert target.read_text() == "// player's changes\n"


def test_duplicate_native_id_and_binary_packages_are_refused(setup):
    game, data, library = setup
    source = mod(library)
    native = data / "mods/native-example"
    native.mkdir()
    (native / "mod.json").write_text('{"id":"example","name":"Existing native mod"}')
    with pytest.raises(ValueError, match="already exists"):
        VerditeModAdapter().activate([source], game)
    (source / "game.exe").write_bytes(b"synthetic")
    report = VerditeModAdapter().inspect(source, [Path("mod.json"), Path("Mod.cs"), Path("game.exe")])
    assert not report["valid"]


def test_failed_configuration_write_rolls_back_mod_files_and_active_ids(setup, monkeypatch):
    game, data, library = setup
    first, second = mod(library, "first"), mod(library, "second")
    adapter = VerditeModAdapter()
    adapter.activate([first], game)
    old_settings = (data / "settings.json").read_bytes()
    original_write = model.atomic_write
    failed = False

    def fail_once(path, raw):
        nonlocal failed
        if path == data / LEDGER and not failed:
            failed = True
            raise OSError("synthetic interrupted write")
        original_write(path, raw)

    monkeypatch.setattr(model, "atomic_write", fail_once)
    with pytest.raises(OSError, match="synthetic interrupted"):
        adapter.activate([second], game)
    assert (data / "mods/lexeditor-first/Mod.cs").is_file()
    assert not (data / "mods/lexeditor-second").exists()
    assert (data / "settings.json").read_bytes() == old_settings
    assert not (data / RECOVERY).exists()


def test_recovery_preserves_edited_backup_without_replacing_deployed_mod(setup, monkeypatch):
    game, data, library = setup
    first, second = mod(library, "first"), mod(library, "second")
    adapter = VerditeModAdapter()
    adapter.activate([first], game)
    original_write = model.atomic_write

    def interrupt_with_edited_backup(path, raw):
        if path == data / LEDGER:
            backup = data / RECOVERY / "mods/lexeditor-first/Mod.cs"
            backup.write_text("// recovered player edits\n")
            raise OSError("synthetic interrupted write")
        original_write(path, raw)

    monkeypatch.setattr(model, "atomic_write", interrupt_with_edited_backup)
    with pytest.raises(ValueError, match="Recovery copy.*edited"):
        adapter.activate([second], game)
    assert (data / RECOVERY / "mods/lexeditor-first/Mod.cs").read_text() == "// recovered player edits\n"
    assert (data / "mods/lexeditor-second/Mod.cs").is_file()
    assert not (data / "mods/lexeditor-first").exists()
