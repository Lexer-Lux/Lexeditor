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


@pytest.fixture(autouse=True)
def isolated_conflict_report(tmp_path, monkeypatch):
    monkeypatch.setattr(Ds1ModAdapter, "_report_path", staticmethod(lambda: tmp_path / "conflicts.json"))


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


def enable_loader(library, on=True):
    """Switch the loader mod on or off, creating it on first use."""
    folder = tweak_mods.ensure_loader_mod(Path(library))
    data = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
    (folder / "mod.json").write_text(json.dumps({**data, "enabled": on}), encoding="utf-8")


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
    enable_loader(root)
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
    assert tweak_mods.needs_rebuild(game, library) == {"needed": False, "stale": [], "set": False}
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


def test_the_adapter_flags_the_changed_mod(game, library):
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    tweak_mods.apply(game, library)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): [Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_OFFLINE]}
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): [Ds1ModAdapter.ALERT_CHANGED, Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_OFFLINE]}


def test_the_adapter_flags_executable_mods_while_the_loader_is_off(game, library):
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    tweak_mods.apply(game, library)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): [Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_OFFLINE]}
    enable_loader(library, False)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): [Ds1ModAdapter.ALERT_NEEDS_LOADER, Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_NEEDS_LOADER, Ds1ModAdapter.ALERT_OFFLINE]}


def test_the_adapter_flags_executable_mods_while_the_loader_is_missing(game, library):
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    tweak_mods.apply(game, library)
    loader = tweak_mods.ensure_loader_mod(library)
    (loader / "mod.json").unlink()
    loader.rmdir()
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): [Ds1ModAdapter.ALERT_LOADER_MISSING, Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_LOADER_MISSING, Ds1ModAdapter.ALERT_OFFLINE]}


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
        str((library / "Alpha").resolve()): ["Requires ghost, which is not installed.",
                                             Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_OFFLINE]}
    _switch(library, "Beta", False)
    assert adapter.alerts([library / "Alpha", library / "Beta"], game) == {
        str((library / "Alpha").resolve()): ["Requires beta, which is switched off.",
                                             "Requires ghost, which is not installed.",
                                             Ds1ModAdapter.ALERT_OFFLINE],
        str((library / "Beta").resolve()): [Ds1ModAdapter.ALERT_OFFLINE]}


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


def test_data_deployment_backup_does_not_claim_tweak_ownership(game, library):
    managed = tweak_mods.ESD_COMMON
    managed.live(game).parent.mkdir(parents=True, exist_ok=True)
    managed.live(game).write_bytes(b"data mod installed menu")
    managed.backup(game).write_bytes(b"original menu")
    tweak_mods.apply(game, library)
    assert managed.live(game).read_bytes() == b"data mod installed menu"
    assert not managed.manifest(game).exists()


def test_composition_reads_only_files_the_mods_change(game, monkeypatch):
    from plugins.ds1 import deployment, mod_loader
    relative = Path("script/talk/bonfire.talkesdbnd.dcx")
    live = game / relative
    live.parent.mkdir(parents=True)
    live.write_bytes(b"original")
    unrelated = game / "chr/unrelated.anibnd.dcx"
    unrelated.parent.mkdir()
    unrelated.write_bytes(b"must not be read")
    read = []
    def original(game_root, path):
        read.append(path)
        assert path == relative
        return game_root / path
    monkeypatch.setattr(deployment, "vanilla_source", original)
    result = mod_loader.compose_installed(game, [mod_loader.Mod("Talk mod", game, {relative: b"changed"})])
    assert read == [relative]
    assert result.files == {relative: b"changed"}


def test_conflict_inspection_does_not_compress_deployment_files(monkeypatch):
    from copy import deepcopy
    from test_ds1_talk_composition import fixture, command
    from ds1_fixture import pack_text_members
    from plugins.ds1 import mod_loader
    base = fixture()
    first, second = deepcopy(base), deepcopy(base)
    first.state_groups[1][1].entry_commands = [command(50, 1)]
    second.state_groups[1][1].entry_commands = [command(50, 2)]
    relative = Path("script/talk/test.talkesdbnd.dcx")
    def archive(script):
        return pack_text_members([(1, "bonfire.esd", script.to_bytes())])
    vanilla = {relative: archive(base)}
    mods = [mod_loader.Mod("First", Path("first"), {relative: archive(first)}),
            mod_loader.Mod("Second", Path("second"), {relative: archive(second)})]
    expected = mod_loader.compose(vanilla, mods)
    assert expected.conflicts
    def forbidden(*args, **kwargs):
        pytest.fail("Conflict inspection must not compress deployment files")
    monkeypatch.setattr(mod_loader, "deflate", forbidden)
    actual = mod_loader.compose(vanilla, mods, conflicts_only=True)
    assert actual.conflicts == expected.conflicts
    assert actual.files == {}


def test_conflict_report_survives_restart_and_tracks_files_and_originals(game, library, monkeypatch):
    from plugins.ds1 import mod_loader, deployment
    relative = Path("script/talk/shared.talkesdbnd.dcx")
    paths = [library / name for name in ("Alpha", "Beta")]
    for folder in paths:
        Ds1ModAdapter().prepare_editable(folder)
        (folder / relative).parent.mkdir(parents=True, exist_ok=True)
        (folder / relative).write_bytes(folder.name.encode())
    calls = []
    def compare(*args, **kwargs):
        calls.append(kwargs)
        return mod_loader.Composition({}, [mod_loader.Conflict(relative, "command", ["Alpha", "Beta"])])
    monkeypatch.setattr(mod_loader, "compose_installed", compare)
    def adapter():
        fresh = Ds1ModAdapter()
        fresh.attach_context(library_root=library, game_root=game)
        return fresh
    initial = adapter().conflicts(paths, game)
    assert len(calls) == 1
    assert adapter().conflicts(paths, game) == initial
    assert len(calls) == 1
    metadata = library / "Beta/mod.json"
    stored = json.loads(metadata.read_text())
    metadata.write_text(json.dumps({**stored, "order": 5}))
    reordered = adapter().conflicts(paths, game)
    assert "overrides Beta" in reordered[str(paths[0].resolve())][0]
    assert len(calls) == 1
    (paths[1] / relative).write_bytes(b"external change")
    adapter().conflicts(paths, game)
    assert len(calls) == 2
    original = deployment._backup_path(game, relative)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"changed game original")
    adapter().conflicts(paths, game)
    assert len(calls) == 3
    Ds1ModAdapter._report_path().write_text("broken report")
    adapter().conflicts(paths, game)
    assert len(calls) == 4
    assert Ds1ModAdapter._report_path().stat().st_size <= Ds1ModAdapter.REPORT_LIMIT


def test_successful_build_publishes_conflicts_without_another_merge(game, library, monkeypatch):
    from plugins.ds1 import mod_loader, deployment
    paths = [library / name for name in ("Alpha", "Beta")]
    for folder in paths:
        Ds1ModAdapter().prepare_editable(folder)
    calls = []
    def compare(*args, **kwargs):
        calls.append(kwargs)
        return mod_loader.Composition({}, [mod_loader.Conflict(Path("param/test"), "field", ["Alpha", "Beta"])])
    monkeypatch.setattr(mod_loader, "compose_installed", compare)
    monkeypatch.setattr(deployment, "status", lambda *args: {})
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    adapter.conflicts(paths, game)
    assert len(calls) == 1
    # A report from inspection is not proof that data was installed.
    adapter.activate(paths, game)
    assert len(calls) == 2
    fresh = Ds1ModAdapter()
    fresh.attach_context(library_root=library, game_root=game)
    assert fresh.conflicts(paths, game)
    assert len(calls) == 2
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    fresh.activate(paths, game)
    assert len(calls) == 2
    assert not tweak_mods.needs_rebuild(game, library)["needed"]


def test_changed_inputs_during_comparison_do_not_publish_a_stale_report(game, library, monkeypatch):
    from plugins.ds1 import mod_loader
    relative = Path("script/talk/shared.talkesdbnd.dcx")
    paths = [library / name for name in ("Alpha", "Beta")]
    for folder in paths:
        Ds1ModAdapter().prepare_editable(folder)
        (folder / relative).parent.mkdir(parents=True, exist_ok=True)
        (folder / relative).write_bytes(folder.name.encode())
    calls = []
    def compare(*args, **kwargs):
        calls.append(None)
        if len(calls) == 1:
            (paths[0] / relative).write_bytes(b"changed during comparison")
        return mod_loader.Composition({}, [])
    monkeypatch.setattr(mod_loader, "compose_installed", compare)
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    adapter.conflicts(paths, game)
    assert not adapter._report_path().exists()
    adapter.conflicts(paths, game)
    adapter.conflicts(paths, game)
    assert len(calls) == 2


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


@pytest.mark.parametrize("failure", ["script", "output", "manifest"])
def test_save_disables_a_broken_tweak_and_rebuilds_the_others(game, library, api, failure):
    post, _store, saved = api
    tweak_mods.apply(game, library)
    if failure == "manifest":
        (library / "Beta" / ".lexeditor-generated.json").write_text(
            json.dumps({"version": 1, "files": {"unsupported/boom.bin": "0" * 64}}), encoding="utf-8")
        tweak_mods.save({"beta": {"values": {"step": 2}}}, library)
    else:
        source = ("def build(settings, context):\n    raise ValueError('boom')\n" if failure == "script"
                  else "def build(settings, context):\n    return {'unsupported/boom.bin': b'bad'}\n")
        (library / "Beta" / "script" / "tweak.py").write_text(source, encoding="utf-8")
    status, result = post("/api/save", {})
    assert status == 200
    assert saved == ["saved"]
    assert "tweaksError" not in result
    assert result["disabledMods"][0]["name"] == "Beta"
    assert "boom" in result["disabledMods"][0]["error"]
    assert not json.loads((library / "Beta/mod.json").read_text())["enabled"]
    assert json.loads((library / "Alpha/mod.json").read_text())["enabled"]
    assert result["tweaksNeedRebuild"] is False
    assert sorted(record_of(game)["built"]) == ["alpha"]


def test_save_disables_dependents_of_a_failed_mod(game, library, api):
    post, _store, _saved = api
    tweak_mods.apply(game, library)
    _require(library, "Alpha", "beta")
    (library / "Beta/script/tweak.py").write_text(
        "def build(settings, context):\n    raise ValueError('boom')\n", encoding="utf-8")
    status, result = post("/api/save", {})
    assert status == 200 and "tweaksError" not in result
    assert {row["name"] for row in result["disabledMods"]} == {"Alpha", "Beta"}
    assert record_of(game)["built"] == {}
    assert not result["tweaksNeedRebuild"]


def test_read_only_settings_save_also_recovers_failed_mods(game, library, api):
    post, store, _saved = api
    store.read_only = True
    tweak_mods.apply(game, library)
    (library / "Beta/script/tweak.py").write_text(
        "def build(settings, context):\n    raise ValueError('boom')\n", encoding="utf-8")
    status, result = post("/api/tweaks/save", {"tweaks": {"alpha": {"values": {"step": 2}}}})
    assert status == 200
    assert result["disabledMods"][0]["name"] == "Beta"
    assert sorted(record_of(game)["built"]) == ["alpha"]
    assert not result["needsRebuild"]


def test_save_does_not_disable_mods_for_an_unattributed_deployment_error(game, library, api, monkeypatch):
    post, _store, saved = api
    tweak_mods.apply(game, library)
    tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
    def fail(*args):
        raise OSError("The installed game folder is not writable")
    monkeypatch.setattr(Ds1ModAdapter, "activate", fail)
    status, result = post("/api/save", {})
    assert status == 200 and saved == ["saved"]
    assert "not writable" in result["tweaksError"]
    assert all(json.loads((library / name / "mod.json").read_text())["enabled"]
               for name in ("Alpha", "Beta"))


def test_failed_mod_notice_does_not_block_the_editor(tmp_path):
    from playwright.sync_api import sync_playwright
    root = Path(__file__).resolve().parents[2]
    source = (root / "plugins/ds1/editor.js").read_text(encoding="utf-8")
    report = source[source.index("function reportTweakRebuild("):source.index("async function save(){")]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 700})
            page.route("http://fixture/**", lambda route: route.fulfill(
                body='<body><main><button id="edit">Edit mod</button></main></body>',
                content_type="text/html"))
            page.goto("http://fixture/")
            page.add_style_tag(path=str(root / "ui/framework.css"))
            page.add_style_tag(path=str(root / "plugins/ds1/editor.css"))
            page.add_script_tag(path=str(root / "ui/framework.js"))
            page.add_script_tag(content=report)
            page.evaluate('''reportTweakRebuild({disabledMods: [{name: "Estus Rework",
              error: "Its build returned an unsupported file."}]})''')
            assert page.get_by_text('Changes saved. Other enabled mods rebuilt.', exact=False).is_visible()
            assert page.locator('.lex-dialog-backdrop').count() == 0
            assert not page.evaluate('document.body.inert')
            page.locator('#edit').click()
            page.screenshot(path=str(tmp_path / "disabled-mod-notice.png"))
        finally:
            browser.close()


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
def test_an_unreadable_mod_counts_as_unchanged_not_stale(game, library, monkeypatch):
    # tweak_rows just read this mod fine; a lock landing between that and
    # the fingerprint read is transient interference, not a change. Calling
    # it stale flashed "changed since the last build" on and off.
    tweak_mods.apply(game, library)
    real_fingerprint = tweak_mods.build_fingerprint

    def flaky(folder):
        if Path(folder).name == "Alpha":
            raise OSError("locked")
        return real_fingerprint(folder)

    monkeypatch.setattr(tweak_mods, "build_fingerprint", flaky)
    assert tweak_mods.needs_rebuild(game, library)["stale"] == []
