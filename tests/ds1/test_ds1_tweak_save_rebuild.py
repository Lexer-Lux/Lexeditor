"""Changed tweaks rebuild on Save, and flag their mod until they do.

A tweak whose settings, script, switch or order changed since its last build
flags its mod in the Mods tab and the mod selector; Save rebuilds it (or the
Tweaks page installs it straight away when no mod project is open).
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ds1_exe_patches import HOOK_A, HOOK_B, VANILLA, island  # noqa: E402
from plugins.ds1 import exe_patches, tweak_mods  # noqa: E402
from plugins.ds1 import server as ds1_server  # noqa: E402
from plugins.ds1.mod_support import Ds1ModAdapter  # noqa: E402

TWEAK = '''import json

def build(settings, context):
    return {"native/%s.json": json.dumps(%s)}
'''
SPECS = {
    "alpha": {"version": 1, "islands": [island("payload", rva=0x10000)],
              "hooks": [{"rva": HOOK_A, "original": "E800000000",
                         "branch": {"opcode": "E8", "island": "payload", "offset": 4}}]},
    "beta": {"version": 1, "islands": [island("display")],
             "hooks": [{"rva": HOOK_B, "original": "488D1500000000",
                        "branch": {"opcode": "E9", "island": "display", "offset": 4}, "pad": "9090"}]},
}
SCHEMA = {"fields": [{"key": "step", "type": "int", "default": 1, "min": 0, "max": 10}]}


def make_mod(library, mod_id, name, spec, *, enabled=True, order=10, values=None):
    root = Path(library) / name
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(TWEAK % (mod_id, repr(spec)), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    if values is not None:
        (root / "settings.json").write_text(json.dumps({"values": values}), encoding="utf-8")
    (root / "mod.json").write_text(json.dumps(
        {"id": mod_id, "name": name, "enabled": enabled, "order": order, "script": {"version": 1}}),
        encoding="utf-8")
    return root


def record_of(game):
    return json.loads((Path(game) / tweak_mods.RUNTIME_RECORD).read_text(encoding="utf-8"))


@pytest.fixture
def game(tmp_path, monkeypatch):
    root = tmp_path / "game"
    root.mkdir()
    (root / exe_patches.EXECUTABLE).write_bytes(VANILLA)
    monkeypatch.setattr(exe_patches, "VANILLA_SIZE", len(VANILLA))
    monkeypatch.setattr(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest())
    monkeypatch.setattr(tweak_mods, "ensure_game_closed", lambda: None)
    return root


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "library"
    make_mod(root, "alpha", "Alpha", SPECS["alpha"], enabled=True, order=10, values={"step": 1})
    make_mod(root, "beta", "Beta", SPECS["beta"], enabled=True, order=20, values={"step": 1})
    return root


@pytest.fixture
def api(game, library, monkeypatch, tmp_path):
    monkeypatch.setenv(tweak_mods.MODS_ENV, str(library))
    saved = []
    store = SimpleNamespace(game_root=game, project=tmp_path / "mod", read_only=False,
                            validate_save=lambda: None, save=lambda: saved.append("saved") or {},
                            discard=lambda: {},
                            get=lambda: SimpleNamespace(dirty_count=0, pending_changes=lambda: []))
    rules = SimpleNamespace(validate_save=lambda: None, save=lambda: None, discard=lambda: {},
                            dirty_count=0, pending_changes=lambda: [], snapshot=lambda: {})
    maps = SimpleNamespace(validate_save=lambda: None, save=lambda: None, discard=lambda: {},
                           dirty_count=0, pending_changes=lambda: [])
    taes = SimpleNamespace(validate_save=lambda: None, save=lambda: None, discard=lambda: {},
                           dirty_count=0, pending_changes=lambda: [])
    monkeypatch.setattr(ds1_server, "STORE", store)
    monkeypatch.setattr(ds1_server, "RULES", rules)
    monkeypatch.setattr(ds1_server, "MAPSTORE", maps)
    monkeypatch.setattr(ds1_server, "TAESTORE", taes)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ds1_server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"

        def post(path, payload):
            request = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read().decode())

        yield post, store, saved
    finally:
        httpd.shutdown()
        thread.join()


def test_a_fresh_apply_needs_no_rebuild_and_records_fingerprints(game, library):
    tweak_mods.apply(game, library)
    assert tweak_mods.needs_rebuild(game, library) == {"needed": False, "stale": [], "debug": False, "set": False}
    assert sorted(record_of(game)["built"]) == ["alpha", "beta"]


def test_a_settings_change_flags_only_that_mod_until_the_next_apply(game, library):
    tweak_mods.apply(game, library)
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    assert tweak_mods.needs_rebuild(game, library)["stale"] == ["alpha"]
    tweak_mods.apply(game, library)
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False


def test_a_script_change_and_a_reorder_flag_the_mod(game, library):
    tweak_mods.apply(game, library)
    with (library / "Alpha" / "script" / "tweak.py").open("a", encoding="utf-8") as handle:
        handle.write("\n# a comment\n")
    assert tweak_mods.needs_rebuild(game, library)["stale"] == ["alpha"]
    tweak_mods.apply(game, library)
    metadata = json.loads((library / "Alpha" / "mod.json").read_text(encoding="utf-8"))
    metadata["order"] = 5
    (library / "Alpha" / "mod.json").write_text(json.dumps(metadata), encoding="utf-8")
    assert tweak_mods.needs_rebuild(game, library)["stale"] == ["alpha"]


def test_restore_needs_no_rebuild_and_keeps_the_switches(game, library):
    tweak_mods.apply(game, library)
    tweak_mods.restore(game, library)
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False
    assert sorted(row["id"] for row in tweak_mods.tweak_rows(library) if row["enabled"]) == ["alpha", "beta"]


def test_a_debug_toggle_with_a_record_needs_a_rebuild_without_stale_mods(game, library):
    tweak_mods.apply(game, library)
    tweak_mods.set_debug_mode(True, library)
    assert tweak_mods.needs_rebuild(game, library) == {"needed": True, "stale": [], "debug": True, "set": False}
    tweak_mods.apply(game, library)
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False


def test_a_record_from_before_fingerprints_needs_one_rebuild(game, library):
    tweak_mods.apply(game, library)
    record = record_of(game)
    del record["built"]
    (game / tweak_mods.RUNTIME_RECORD).write_text(json.dumps(record), encoding="utf-8")
    assert tweak_mods.needs_rebuild(game, library)["stale"] == ["alpha", "beta"]
    tweak_mods.apply(game, library)
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False


def test_rollback_restores_the_previous_fingerprints(game, library):
    tweak_mods.apply(game, library)
    before = record_of(game)["built"]
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    plan = tweak_mods.prepare(game, library)
    tweak_mods.rollback(game, plan)
    assert record_of(game)["built"] == before
    assert tweak_mods.needs_rebuild(game, library)["stale"] == ["alpha"]


def test_status_names_the_stale_mods(game, library):
    tweak_mods.apply(game, library)
    assert tweak_mods.status(game, library)["needsRebuild"] is False
    tweak_mods.save({"beta": {"values": {"step": 3}}}, library)
    status = tweak_mods.status(game, library)
    assert status["needsRebuild"] is True
    assert status["staleMods"] == ["Beta"]


def test_the_adapter_flags_only_the_changed_mod(game, library):
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    tweak_mods.apply(game, library)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {}
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): [Ds1ModAdapter.ALERT_CHANGED]}


def _require(library, folder, *needs):
    path = Path(library) / folder / "mod.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**data, "requires": list(needs)}), encoding="utf-8")


def _switch(library, folder, on):
    path = Path(library) / folder / "mod.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**data, "enabled": on}), encoding="utf-8")


def test_the_adapter_flags_a_mod_whose_requirement_is_off_or_missing(game, library):
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    tweak_mods.apply(game, library)
    _require(library, "Alpha", "beta", "ghost")
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): ["Requires ghost, which is not installed."]}
    _switch(library, "Beta", False)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): ["Requires beta, which is switched off.",
                                             "Requires ghost, which is not installed."]}


def test_build_refuses_an_unmet_mod_requirement(game, library):
    _require(library, "Alpha", "ghost")
    with pytest.raises(tweak_mods.TweakError, match="Alpha requires ghost, which is not installed"):
        tweak_mods.build_specs(library)


def test_save_rebuilds_stale_tweaks(game, library, api):
    post, _store, _saved = api
    tweak_mods.apply(game, library)
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    status, result = post("/api/save", {})
    assert status == 200
    assert result["tweaksRebuilt"] is True
    assert result["tweaksNeedRebuild"] is False
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False


def test_save_saves_the_project_but_defers_tweaks_while_the_game_runs(game, library, api, monkeypatch):
    post, _store, saved = api
    tweak_mods.apply(game, library)
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    before = (game / tweak_mods.RUNTIME_RECORD).read_bytes()
    monkeypatch.setattr(tweak_mods, "game_closed", lambda: False)
    status, result = post("/api/save", {})
    assert status == 200
    assert saved == ["saved"]
    assert result["tweaksDeferred"] is True
    assert result["tweaksNeedRebuild"] is True
    assert (game / tweak_mods.RUNTIME_RECORD).read_bytes() == before


def test_save_reports_a_broken_tweak_without_failing(game, library, api):
    post, _store, saved = api
    tweak_mods.apply(game, library)
    (library / "Beta" / "script" / "tweak.py").write_text(
        "def build(settings, context):\n    raise ValueError('boom')\n", encoding="utf-8")
    status, result = post("/api/save", {})
    assert status == 200
    assert saved == ["saved"]
    assert "Beta" in result["tweaksError"]
    assert result["tweaksNeedRebuild"] is True


def test_a_session_without_save_installs_tweak_settings_straight_away(game, library, api):
    post, store, _saved = api
    store.read_only = True
    tweak_mods.apply(game, library)
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    assert tweak_mods.needs_rebuild(game, library)["needed"] is True
    status, result = post("/api/tweaks/save", {"tweaks": {"alpha": {"values": {"step": 2}}}})
    assert status == 200
    assert result["needsRebuild"] is False
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False


def test_a_session_with_a_project_defers_tweak_settings_to_save(game, library, api):
    post, store, _saved = api
    tweak_mods.apply(game, library)
    before = (game / tweak_mods.RUNTIME_RECORD).read_bytes()
    status, result = post("/api/tweaks/save", {"tweaks": {"alpha": {"values": {"step": 2}}}})
    assert status == 200
    assert result["needsRebuild"] is True
    assert (game / tweak_mods.RUNTIME_RECORD).read_bytes() == before


def test_a_layout_only_tweak_keeps_its_record_and_rebuilds(game, library, tmp_path, monkeypatch):
    from test_ds1_menu_layout import STAMINA, dcx, drb
    from plugins.ds1 import menu_layout
    layout = game / "menu" / "menu.drb.dcx"
    layout.parent.mkdir(parents=True)
    vanilla_layout = dcx(drb())
    layout.write_bytes(vanilla_layout)
    monkeypatch.setattr(menu_layout, "VANILLA_SIZE", len(vanilla_layout))
    monkeypatch.setattr(menu_layout, "VANILLA_SHA256", hashlib.sha256(vanilla_layout).hexdigest())
    nodes = {"version": 1, "nodes": STAMINA}
    root = library / "Details"
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(
        "import json\n\ndef build(settings, context):\n    return {'layout/details.json': json.dumps(%s)}\n"
        % repr(nodes), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    (root / "mod.json").write_text(json.dumps(
        {"id": "details", "name": "Details", "enabled": True, "order": 30, "script": {"version": 1}}),
        encoding="utf-8")
    for mod_id in ("alpha", "beta"):
        tweak_mods.save({mod_id: {"enabled": False}}, library)
    tweak_mods.apply(game, library)
    assert record_of(game)["built"] == {"details": tweak_mods.build_fingerprint(root)}
    assert (game / tweak_mods.RUNTIME_PATCH).read_bytes() == b""
    tweak_mods.save({"details": {"values": {"step": 4}}}, library)
    assert tweak_mods.needs_rebuild(game, library)["stale"] == ["details"]
    tweak_mods.apply(game, library)
    assert tweak_mods.needs_rebuild(game, library)["needed"] is False
