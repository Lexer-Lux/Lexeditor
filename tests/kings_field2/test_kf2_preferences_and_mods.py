"""Preservation, native-mod coexistence, and rollback for Verdite2 integration."""
import json
from pathlib import Path
import sys
import hashlib
import shutil
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.kings_field2.model import MODEL as model
from core import native_port_settings as native_settings
from plugins.kings_field2 import port
from plugins.kings_field2.mod_support import LEDGER, RECOVERY, VerditeModAdapter


def test_service_is_registered_for_normal_and_frozen_launches():
    from core.runtime_bootstrap import service_command
    assert "plugins.kings_field2.server" in service_command("plugins.kings_field2.server", owned=True)


def test_non_steam_game_validates_without_steam_discovery_or_art_requests(tmp_path, monkeypatch):
    from core.plugin_api import validate_plugin
    from core.game_installation import GameInstallationManager
    from core.cover_art import CoverArtCache
    from plugins.kings_field2.plugin import PLUGIN
    validate_plugin(PLUGIN)
    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("A non-Steam port must not request a Steam cover")

    manager = object.__new__(GameInstallationManager)
    monkeypatch.setattr(manager, "_steam_candidates", unexpected_fetch)
    monkeypatch.setattr(manager, "_uninstall_candidates", lambda _: [])
    monkeypatch.setattr(manager, "_epic_candidates", lambda _: [])
    assert list(PLUGIN.installation.default_roots) == manager._discover(PLUGIN)

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
    for name in port.CRITICAL:
        target = game / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(b"synthetic only")
    (game / "lexeditor-port.json").write_text(json.dumps(port.PIN))
    (game / port.RECEIPT).write_text(json.dumps({"repository": port.PIN["repository"],
                                               "files": port._tree(game)}))
    (data / "settings.json").write_text(json.dumps({"ActiveMods": ["external.map"], "Unmodeled": {"keep": 42}}))
    (data / "interface.ini").write_text("[RecompOne]\nmods.external.map.enabled=True\nkf2.mouse.turn=1\n[Docking][Data]\nDockNode=0x1\n")
    monkeypatch.setenv("VERDITE2_DATA", str(data))
    monkeypatch.setattr(native_settings, "live_processes", lambda _: [])
    return game, data, library


def mod(library, name="example"):
    root = library / name
    root.mkdir()
    (root / "mod.json").write_text(json.dumps({"id": name, "name": name}))
    (root / "Mod.cs").write_text("// synthetic source; never compiled or executed\n")
    return root


def test_ini_noop_is_byte_exact_and_changes_preserve_other_sections():
    raw = b"\xef\xbb\xbf; head\r\n[RecompOne]\r\n  kf2.mouse.turn =1\r\nMystery = keep\r\n[Window][Output]\r\nPos=12,34\r\n"
    assert native_settings.updated_ini(raw, {}) == raw
    output = native_settings.updated_ini(raw, {"kf2.mouse.turn": "2", "kf2.mouse.look": "3"})
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
            native_settings.ini_values(text)


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
    monkeypatch.setattr(native_settings, "live_processes", lambda _: [{"pid": 123}])
    with pytest.raises(ValueError, match="Close the game"):
        VerditeModAdapter().activate([source], game)
    with pytest.raises(ValueError, match="Close the game"):
        model.save_preferences(data, {}, model.fingerprint(b""))
    assert (data / "settings.json").read_bytes() == before
    assert not (data / LEDGER).exists()


def test_shared_service_refuses_unpinned_port_and_does_not_claim_binding_edits(setup, monkeypatch):
    from http.server import ThreadingHTTPServer
    import threading
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    from core.native_port_http import data_map, handler

    game, data, _ = setup
    monkeypatch.setenv(model.descriptor["installation"]["rootEnv"], str(game))
    assert model.installation(game)["supported"]
    marker = json.loads((game / "lexeditor-port.json").read_text())
    marker["tag"] = "a-different-native-build"
    (game / "lexeditor-port.json").write_text(json.dumps(marker))
    assert not model.installation(game)["supported"]
    row = next(row for row in data_map(model)["rows"] if row["filename"] == "settings.json")
    assert row["status"] == "not-integrated" and not row["openable"]
    before = (data / "interface.ini").read_bytes()
    source = Path(__file__).resolve().parents[2] / "plugins/kings_field2/server.py"
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(model, str(source)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({"changes": {"kf2.mouse.turn": 2},
                              "fingerprint": model.preferences(data)["fingerprint"]}).encode()
        with pytest.raises(HTTPError) as error:
            urlopen(Request(f"http://127.0.0.1:{server.server_port}/api/preferences", data=payload,
                            headers={"Content-Type": "application/json"}), timeout=5)
        assert error.value.code == 400
        assert (data / "interface.ini").read_bytes() == before
        assert not (data / "interface.ini.lexeditor-previous").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


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
    values = native_settings.ini_values((data / "interface.ini").read_text())
    assert values["mods.external.map.enabled"] == "True"
    assert "mods.example.enabled" not in values
    assert values["kf2.mouse.turn"] == "1"
    assert adapter.active_mod_ids(game) == ["external.map"]
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
    old_settings = (data / "interface.ini").read_bytes()
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
    assert (data / "interface.ini").read_bytes() == old_settings
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


def pinned_archive(game, temporary, monkeypatch):
    archive = temporary / "fork.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for path in game.rglob("*"):
            if path.is_file() and path.name != port.RECEIPT:
                output.write(path, path.relative_to(game).as_posix())
    pin = {**port.PIN, "bytes": archive.stat().st_size,
           "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    monkeypatch.setattr(port, "PIN", pin)
    monkeypatch.setattr(port, "fetch_file", lambda url, target, **kwargs: shutil.copy2(archive, target))
    return archive


@pytest.mark.parametrize("edited", ["mods/lexeditor-first/Mod.cs", "interface.before", "personal-note.txt"])
def test_committed_recovery_never_deletes_edited_backup(setup, monkeypatch, edited):
    game, data, library = setup
    first, second = mod(library, "first"), mod(library, "second")
    adapter = VerditeModAdapter()
    adapter.activate([first], game)
    original_remove = shutil.rmtree

    def interrupt_cleanup(path, *args, **kwargs):
        if Path(path) == data / RECOVERY:
            (Path(path) / edited).write_text("player changes to preserve")
            raise OSError("synthetic interruption after commit")
        return original_remove(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", interrupt_cleanup)
    with pytest.raises(OSError, match="after commit"):
        adapter.activate([second], game)
    monkeypatch.setattr(shutil, "rmtree", original_remove)
    with pytest.raises(ValueError, match="Recovery copy"):
        adapter.recover(game)
    assert (data / RECOVERY / edited).read_text() == "player changes to preserve"
    assert (data / "mods/lexeditor-second/Mod.cs").is_file()


def test_fork_download_install_is_separate_and_hash_verified(setup, tmp_path, monkeypatch):
    game, _, _ = setup
    original = port._tree(game)
    archive = pinned_archive(game, tmp_path, monkeypatch)
    target = tmp_path / "new-fork"
    assert port.install(target)["installed"]
    assert port._tree(game) == original
    assert model.installation(target)["supported"]
    # A changed download cannot create a second installation.
    archive.write_bytes(b"truncated or tampered download")
    with pytest.raises(ValueError, match="pinned size and SHA-256"):
        port.install(tmp_path / "rejected-fork")
    assert not (tmp_path / "rejected-fork").exists()


def test_fork_updates_preserve_user_files_and_keep_bounded_backups(setup, tmp_path, monkeypatch):
    game, _, _ = setup
    target = tmp_path / "fork"
    pinned_archive(game, tmp_path, monkeypatch)
    port.install(target)
    (target / "bin/ReShade.ini").write_text("player preference")
    for version in ("old-one", "old-two", "old-three"):
        marker = json.loads((target / "lexeditor-port.json").read_text())
        marker["sourceRevision"] = version
        (target / "lexeditor-port.json").write_text(json.dumps(marker))
        # Simulate a legitimately installed earlier release's receipt.
        receipt = json.loads((target / port.RECEIPT).read_text())
        receipt["files"]["lexeditor-port.json"] = port.digest(target / "lexeditor-port.json")
        (target / port.RECEIPT).write_text(json.dumps(receipt))
        assert port.install(target)["installed"]
        assert (target / "bin/ReShade.ini").read_text() == "player preference"
    assert target.with_name("fork.lexeditor-original").is_dir()
    assert target.with_name("fork.lexeditor-previous").is_dir()
    assert not port._paths(target)[0].exists()


def test_fork_never_overwrites_unmanaged_or_modified_port_files(setup, tmp_path, monkeypatch):
    game, _, _ = setup
    pinned_archive(game, tmp_path, monkeypatch)
    target = tmp_path / "unmanaged"
    target.mkdir()
    (target / "player.txt").write_text("keep me")
    with pytest.raises(ValueError, match="not a managed"):
        port.install(target)
    assert (target / "player.txt").read_text() == "keep me"
    target = tmp_path / "fork"
    port.install(target)
    (target / "bin/Verdite2.dll").write_bytes(b"player build")
    with pytest.raises(ValueError, match="changed outside"):
        port.install(target)
    assert (target / "bin/Verdite2.dll").read_bytes() == b"player build"


def test_fork_swap_failure_restores_previous_installation(setup, tmp_path, monkeypatch):
    game, _, _ = setup
    pinned_archive(game, tmp_path, monkeypatch)
    target = tmp_path / "fork"
    port.install(target)
    marker = json.loads((target / "lexeditor-port.json").read_text())
    marker["sourceRevision"] = "older-installed-build"
    (target / "lexeditor-port.json").write_text(json.dumps(marker))
    receipt = json.loads((target / port.RECEIPT).read_text())
    receipt["files"]["lexeditor-port.json"] = port.digest(target / "lexeditor-port.json")
    (target / port.RECEIPT).write_text(json.dumps(receipt))
    before = port._tree(target)
    rename = Path.rename

    def fail_stage_move(path, destination):
        if path == port._paths(target)[1] and Path(destination) == target:
            raise OSError("synthetic failed folder swap")
        return rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_stage_move)
    with pytest.raises(OSError, match="failed folder swap"):
        port.install(target)
    assert port._tree(target) == before
    assert not port._paths(target)[0].exists()
    assert not port._paths(target)[1].exists()
