"""Project native rules compose with library tweaks into one loader patch.

The executable itself is never written: rules and library tweaks are one
description the loader applies in memory (plugins/ds1/runtime/).
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_ds1_band_composition import original  # noqa: F401: synthetic PE fixture
from ds1_native_fixture import make_native_archive
from plugins.ds1 import exe_patches, load_bands, load_bands_patch, tweak_mods, deployment
from plugins.ds1.map_store import MapStore
from plugins.ds1.tae_store import TaeStore
from plugins.ds1.native_rules import NativeRules, DEFAULTS, SETTINGS_FILE, LEGACY_FILE
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds1.formats import ItemDocument
from plugins.ds1.effects import TABLE, RECOVERY_KEY

@pytest.fixture
def project(tmp_path, monkeypatch, original):
    game, mod, library = (tmp_path / name for name in ("game", "mod", "library"))
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_native_archive())
    (game / exe_patches.EXECUTABLE).write_bytes(original)
    mod.mkdir(); (mod / MARKER).touch(); library.mkdir()
    monkeypatch.setenv(tweak_mods.MODS_ENV, str(library))
    monkeypatch.setattr(tweak_mods, "ensure_game_closed", lambda: None)
    store = ItemStore(game, mod, False)
    store.save()
    # Project native rules patch the executable, so they need the loader on.
    loader = tweak_mods.ensure_loader_mod(library)
    data = json.loads((loader / "mod.json").read_text(encoding="utf-8"))
    (loader / "mod.json").write_text(json.dumps({**data, "enabled": True}), encoding="utf-8")
    return game, mod, store, NativeRules(game, mod, False), original


def edit_rules(rules):
    rules.edit_row(0, "baseRecovery", 70)
    rules.band_action("add", 1001, revision=rules.band_revision(), at=12.5)
    rules.edit_row(1005, "recovery", 125)
    rules.save()


def other_spec(original):
    return exe_patches.validate({"version": 1,
        "islands": [{"name": "independent", "code": "c3" * 4096}],
        "hooks": [{"rva": 0x1600, "original": original[0xa00:0xa01].hex(), "bytes": "c3"}]},
        "Independent library tweak")


def image(game):
    return (game / exe_patches.EXECUTABLE).read_bytes()


def runtime(game):
    """The patch description the loader reads, or None when none is installed."""
    path = game / tweak_mods.RUNTIME_PATCH
    return path.read_bytes() if path.is_file() else None


def test_new_projects_have_no_baked_balance_preset(project):
    game, mod, store, rules, original = project
    assert rules.value["baseRecovery"] == 45
    assert not {"enabled", "shieldRecovery", "encumbranceEnabled"} & rules.value.keys()
    assert not rules.read_row(0)["fields"][0]["disabled"]
    assert len(rules.list_rows("encumbrance")) == 4
    rules.apply(store)
    assert image(game) == original
    assert not (game / tweak_mods.BACKUP_FILE).exists()


def test_project_and_library_tweaks_share_one_composed_image(project, monkeypatch):
    game, mod, store, rules, original = project
    other = other_spec(original)
    monkeypatch.setattr(tweak_mods, "build_specs", lambda root=None, game_root=None, **kwargs: [other])
    edit_rules(rules)
    status = rules.apply(store)
    spec = exe_patches.validate(rules._contribution(original)["spec"], "Project native rules")
    assert image(game) == original
    assert runtime(game) == exe_patches.runtime_patch(original, [other, spec])
    assert status["nativeProjectActive"] and not status["stale"]
    assert status["native"]["applied"] == ["Independent library tweak"]
    assert not (game / tweak_mods.BACKUP_FILE).exists()
    assert not (game / "DarkSoulsRemastered.exe.lexeditor-stamina-original").exists()
    assert ItemDocument((game / RELATIVE).read_bytes()).value(TABLE, 6890, RECOVERY_KEY) == 10


def test_library_apply_preserves_last_applied_project_rules(project, monkeypatch):
    game, mod, store, rules, original = project
    edit_rules(rules)
    rules.apply(store)
    monkeypatch.setattr(tweak_mods, "build_specs", lambda root=None, game_root=None, **kwargs: [other_spec(original)])
    tweak_mods.apply(game)
    contribution = rules._contribution(original)
    expected = exe_patches.runtime_patch(original, [other_spec(original),
        exe_patches.validate(contribution["spec"], "Project native rules")])
    assert runtime(game) == expected and image(game) == original
    # Removing the library mod does not remove native rules.
    monkeypatch.setattr(tweak_mods, "build_specs", lambda root=None, game_root=None, **kwargs: [])
    tweak_mods.apply(game)
    assert runtime(game) == exe_patches.runtime_patch(original, [
        exe_patches.validate(contribution["spec"], "Project native rules")])


def test_reset_project_rules_preserves_library_mod_and_full_restore_is_exact(project, monkeypatch):
    game, mod, store, rules, original = project
    other = other_spec(original)
    monkeypatch.setattr(tweak_mods, "build_specs", lambda root=None, game_root=None, **kwargs: [other])
    edit_rules(rules); rules.apply(store)
    rules.value = deepcopy(DEFAULTS); rules.save(); rules.apply(store)
    assert runtime(game) == exe_patches.runtime_patch(original, [other])
    assert tweak_mods.status(game)["project"] is None
    rules.restore()
    assert image(game) == original and runtime(game) is None
    assert not (game / tweak_mods.RUNTIME_DLL).exists()
    assert not (game / tweak_mods.MANIFEST_FILE).exists()


def test_hook_conflict_changes_neither_installed_file(project, monkeypatch):
    game, mod, store, rules, original = project
    before_param = (game / RELATIVE).read_bytes()
    edit_rules(rules)
    conflict = exe_patches.validate({"version": 1, "hooks": [{
        "rva": load_bands_patch.CLASS_RVA,
        "original": original[load_bands_patch.CLASS_OFFSET:load_bands_patch.CLASS_OFFSET+5].hex(),
        "bytes": "90" * 5}]}, "Conflicting mod")
    monkeypatch.setattr(tweak_mods, "build_specs", lambda root=None, game_root=None, **kwargs: [conflict])
    with pytest.raises(ValueError, match="both patch"):
        rules.apply(store)
    assert image(game) == original and (game / RELATIVE).read_bytes() == before_param
    assert not (game / tweak_mods.BACKUP_FILE).exists()
    assert not deployment._backup_path(game).exists()


@pytest.mark.parametrize("interrupted_file", [tweak_mods.RUNTIME_PATCH, tweak_mods.RUNTIME_RECORD,
                                              tweak_mods.RUNTIME_DLL])
def test_an_interrupted_loader_install_is_undone_and_retryable(project, monkeypatch, interrupted_file):
    game, mod, store, rules, original = project
    edit_rules(rules)
    atomic = tweak_mods.atomic_write
    def interrupted(path, content):
        if Path(path).name == interrupted_file:
            raise OSError("interrupted")
        return atomic(path, content)
    monkeypatch.setattr(tweak_mods, "atomic_write", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        rules.apply(store)
    # What was written is taken back: no half-installed loader is left.
    status = tweak_mods.status(game)
    assert not status["problem"] and status["state"] == "vanilla"
    assert runtime(game) is None and not (game / tweak_mods.RUNTIME_DLL).exists()
    assert image(game) == original
    monkeypatch.setattr(tweak_mods, "atomic_write", atomic)
    rules.apply(store)
    assert not tweak_mods.status(game)["pendingRecovery"]
    rules.restore()
    assert image(game) == original


def test_parameter_failure_rolls_back_the_entire_previous_native_recipe(project, monkeypatch):
    game, mod, store, rules, original = project
    edit_rules(rules); rules.apply(store)
    previous_patch, previous_project = runtime(game), tweak_mods.status(game)["project"]
    rules.edit_row(0, "baseRecovery", 80); rules.save()
    def fail(*args, **kwargs):
        raise OSError("archive write failed")
    monkeypatch.setattr(deployment, "apply", fail)
    with pytest.raises(OSError, match="archive"):
        rules.apply(store)
    assert runtime(game) == previous_patch and image(game) == original
    assert tweak_mods.status(game)["project"] == previous_project


def test_rollback_never_touches_somebody_elses_executable(project, monkeypatch):
    game, mod, store, rules, original = project
    edit_rules(rules)
    foreign = original[:-1] + b"x"
    def fail(*args, **kwargs):
        (game / exe_patches.EXECUTABLE).write_bytes(foreign)
        raise OSError("archive write failed")
    monkeypatch.setattr(deployment, "apply", fail)
    with pytest.raises(OSError, match="archive"):
        rules.apply(store)
    # The loader files are taken back; the executable is not Lexeditor's to write.
    assert image(game) == foreign and runtime(game) is None


def test_bad_archive_and_stale_settings_fail_before_any_native_write(project):
    game, mod, store, rules, original = project
    edit_rules(rules)
    (mod / RELATIVE).write_bytes(b"not a parameter archive")
    with pytest.raises(ValueError, match="outside"):
        rules.apply(store)
    assert image(game) == original and not (game / tweak_mods.BACKUP_FILE).exists()
    (mod / SETTINGS_FILE).write_text("{}")
    with pytest.raises(ValueError):
        rules.save()


def test_split_merge_revision_and_persistence(project):
    game, mod, store, rules, original = project
    rev = rules.band_revision()
    row = rules.band_action("add", 1001, revision=rev, at=12.5)
    assert row["id"] == 1005
    with pytest.raises(ValueError, match="changed"):
        rules.band_action("add", 1001, revision=rev, at=6)
    rules.edit_row(1005, "name", "Feather")
    rules.edit_row(1005, "recovery", 125)
    rules.save()
    reopened = NativeRules(game, mod, False)
    assert reopened.read_row(1005)["name"] == "Feather"
    reopened.band_action("delete", 1005, revision=reopened.band_revision(),
                         neighbour=1001, keep="selected")
    assert reopened.read_row(1001)["name"] == "Feather"
    reopened.discard()
    assert len(reopened.value["bands"]) == 5
    with pytest.raises(PermissionError):
        NativeRules(game).band_action("add", 1001, revision=rev, at=12.5)


@pytest.mark.parametrize("target", ["mod-root", "mod-param", "library-root", "library-entry"])
def test_linked_paths_are_refused_before_read_or_write(project, monkeypatch, tmp_path, target):
    game, mod, store, rules, original = project
    linked = tmp_path / "linked"
    if target == "mod-root":
        linked.symlink_to(mod, target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            ItemStore(game, linked, False)
    elif target == "mod-param":
        source = mod / RELATIVE
        source.unlink()
        source.symlink_to(game / RELATIVE)
        with pytest.raises(ValueError, match="symlink"):
            store.load()
    elif target == "library-root":
        linked.symlink_to(tmp_path / "library", target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            tweak_mods.tweak_rows(linked)
    else:
        foreign = tmp_path / 'library' / 'foreign'
        foreign.symlink_to(mod, target_is_directory=True)
        assert all(Path(row['path']) != foreign for row in tweak_mods.tweak_rows())
        from core import mods_service
        row = mods_service.mod_row(foreign)
        assert row['enabled'] is False and 'symlink' in row['error']
    assert image(game) == original


def test_legacy_native_values_import_without_a_new_balance_preset(project):
    game, mod, store, rules, original = project
    value = {**deepcopy(DEFAULTS), "enabled": False, "encumbranceEnabled": False, "shieldRecovery": 5}
    del value["levelupGains"]  # legacy files predate level-up gains
    value.update(enabled=True, encumbranceEnabled=True, baseRecovery=72)
    value["bands"], _ = load_bands.split(value["bands"], 1, 12.5)
    value["nextBandId"] = 6
    raw = json.dumps({"schema": 2, "stamina-rebalance": value}).encode()
    (mod / LEGACY_FILE).write_bytes(raw)
    migrated = NativeRules(game, mod, False)
    assert migrated.value["baseRecovery"] == 72 and len(migrated.value["bands"]) == 5
    assert "not applied automatically" in migrated.snapshot()["migration"]
    assert (mod / LEGACY_FILE).read_bytes() == raw
    # An authored shield value is respected even when it differs from the old preset.
    store.edit(TABLE, 6890, RECOVERY_KEY, 13); store.save()
    migrated.edit_row(0, "baseRecovery", 74); migrated.save(); migrated.apply(store)
    assert (mod / LEGACY_FILE).read_bytes() == raw
    assert runtime(game) is not None and image(game) == original
    assert ItemDocument((game / RELATIVE).read_bytes()).value(TABLE, 6890, RECOVERY_KEY) == 13
    reopened = NativeRules(game, mod, False)
    reopened.apply(store)
    assert ItemDocument((game / RELATIVE).read_bytes()).value(TABLE, 6890, RECOVERY_KEY) == 13


def test_current_server_keeps_effects_attacks_and_library_tweaks(project, monkeypatch):
    from http.server import ThreadingHTTPServer
    import threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from plugins.ds1 import server
    game, mod, store, rules, original = project
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "RULES", rules)
    monkeypatch.setattr(server, "MAPSTORE", MapStore(game, mod, False, store))
    monkeypatch.setattr(server, "TAESTORE", TaeStore(game, mod, False, store))
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{http.server_port}"
    def call(path, body=None, origin=None):
        headers={"Content-Type":"application/json"}
        if origin: headers["Origin"]=origin
        request=Request(base+path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        with urlopen(request) as response: return json.load(response)
    try:
        state=call("/api/state")
        assert state["effectTabs"] and state["attackTabs"]
        assert call("/api/tweaks")["tweaks"] == []
        edit={"table":"NativeRules","id":0,"field":"baseRecovery","value":70}
        assert call("/api/edit",edit)["dirtyCount"]==1
        assert call("/api/save",{})["dirtyCount"]==0
        revision=call("/api/state")["nativeRules"]["bandRevision"]
        add={"id":1001,"revision":revision,"at":12.5}
        assert call("/api/bands/add",add)["row"]["id"]==1005
        with pytest.raises(HTTPError) as error: call("/api/bands/add",add)
        assert error.value.code==400
        with pytest.raises(HTTPError) as error: call("/api/edit",edit,"http://outside.invalid")
        assert error.value.code==403
        call("/api/discard",{})
        assert len(call("/api/table?tab=encumbrance")["rows"])==4
        call("/api/deployment/apply",{})
        assert runtime(game) is not None and image(game)==original
        before = (game / tweak_mods.RUNTIME_PATCH).read_bytes()
        call("/api/save",{})
        assert (game / tweak_mods.RUNTIME_PATCH).read_bytes() == before
        assert tweak_mods.status(game)["project"] is not None
        call("/api/deployment/disable",{})
        assert image(game)==original and runtime(game) is None
        monkeypatch.setattr(server,"RULES",NativeRules(game))
        with pytest.raises(HTTPError) as error: call("/api/edit",edit)
        assert error.value.code==403
    finally:
        http.shutdown();http.server_close();thread.join()


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_schema_is_explicit_and_inactive_values_stay_in_the_old_file(project, version):
    from plugins.ds1 import legacy_stamina, stamina_patch
    game, mod, store, rules, original = project
    value = ({"enabled": False, "encumbranceEnabled": False, "shieldRecovery": 9,
              **stamina_patch.DEFAULT_RULES} if version == 1 else
             {"enabled": False, "encumbranceEnabled": False, "shieldRecovery": 9, **deepcopy(DEFAULTS)})
    if version == 2:
        del value["levelupGains"]  # legacy files predate level-up gains
    value["baseRecovery"] = 99
    raw = json.dumps({"schema": version, "stamina-rebalance": value}).encode()
    (mod / LEGACY_FILE).write_bytes(raw)
    migrated = NativeRules(game, mod, False)
    assert migrated.value == DEFAULTS
    assert (mod / LEGACY_FILE).read_bytes() == raw
    with pytest.raises(ValueError, match="schema"):
        legacy_stamina.parse({"schema": 3 - version, "stamina-rebalance": value})
    with pytest.raises(ValueError):
        legacy_stamina.parse({"schema": True, "stamina-rebalance": value})


def test_legacy_file_change_before_migration_save_is_not_lost(project):
    game, mod, store, rules, original = project
    value = {**deepcopy(DEFAULTS), "enabled": True, "encumbranceEnabled": False, "shieldRecovery": 5}
    del value["levelupGains"]  # legacy files predate level-up gains
    old = mod / LEGACY_FILE
    old.write_text(json.dumps({"schema": 2, "stamina-rebalance": value}))
    migrated = NativeRules(game, mod, False)
    migrated.edit_row(0, "baseRecovery", 71)
    old.write_text(json.dumps({"schema": 2, "stamina-rebalance": {**value, "baseRecovery": 73}}))
    with pytest.raises(ValueError, match="Legacy settings changed"):
        migrated.save()
    assert not (mod / SETTINGS_FILE).exists()


def test_legacy_executable_is_read_only_then_shared_apply_after_steam_verification(project):
    from plugins.ds1 import stamina_patch
    game, mod, store, rules, original = project
    built = stamina_patch.transform(original,{**stamina_patch.DEFAULT_RULES,'baseRecovery':67})
    (game/stamina_patch.EXECUTABLE).write_bytes(built)
    (game/stamina_patch.BACKUP).write_bytes(original)
    status = rules.deployment_status()
    assert not status['everApplied'] and 'Verify' in status['native']['problem']
    rules.restore()
    assert image(game) == built
    (game/stamina_patch.EXECUTABLE).write_bytes(original)  # Simulated Steam verification.
    edit_rules(rules)
    rules.apply(store)
    assert tweak_mods.status(game)["project"] is not None
    assert (game / stamina_patch.BACKUP).read_bytes() == original
