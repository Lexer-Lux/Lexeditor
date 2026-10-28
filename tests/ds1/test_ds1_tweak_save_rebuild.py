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
    # These phase tests inject parsers and count imports in this process.
    # Real child exit/timeout behavior is covered by editor_failure_boundaries.
    from core import script_mods
    monkeypatch.setattr(tweak_mods.BuildContext, 'run_script',
                        lambda self, root, values: script_mods.execute_script(root, values, self))


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


def install_fixture_menu(game, monkeypatch):
    from test_ds1_menu_layout import STAMINA, dcx, drb
    from plugins.ds1 import menu_layout
    layout = game / "menu" / "menu.drb.dcx"
    layout.parent.mkdir(parents=True)
    vanilla_layout = dcx(drb())
    layout.write_bytes(vanilla_layout)
    monkeypatch.setattr(menu_layout, "VANILLA_SIZE", len(vanilla_layout))
    monkeypatch.setattr(menu_layout, "VANILLA_SHA256", hashlib.sha256(vanilla_layout).hexdigest())
    return {"version": 1, "nodes": STAMINA}


def test_a_layout_only_tweak_keeps_its_record_and_rebuilds(game, library, tmp_path, monkeypatch):
    nodes = install_fixture_menu(game, monkeypatch)
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


def test_save_rebuilds_only_the_changed_script_after_context_restart(game, library, api, monkeypatch):
    from core import script_mods
    tweak_mods.apply(game, library)
    loads = []
    load = script_mods.load_script
    def counted(root):
        loads.append(Path(root).name)
        return load(root)
    monkeypatch.setattr(script_mods, 'load_script', counted)
    tweak_mods.save({'alpha': {'values': {'step': 2}}}, library)
    post, _, saved = api
    status, result = post('/api/save', {})
    assert status == 200 and result['tweaksRebuilt']
    assert loads == ['Alpha']  # Beta's expensive script was never imported/run.
    assert not result['tweaksNeedRebuild']
    assert saved == ['saved']
    loads.clear()
    # A fresh BuildContext reuses the persisted manifest, not process memory.
    tweak_mods.apply(game, library)
    assert loads == []


@pytest.mark.parametrize('change', ['source', 'settings', 'output', 'missing', 'compiler'])
def test_script_build_reuse_invalidates_changed_inputs(game, library, monkeypatch, change):
    from core import script_mods
    tweak_mods.apply(game, library)
    root = library / 'Alpha'
    if change == 'source':
        path = root / 'script/tweak.py'
        path.write_text(path.read_text() + '\n# source changed\n')
    elif change == 'settings':
        tweak_mods.save({'alpha': {'values': {'step': 3}}}, library)
    elif change == 'output':
        (root / 'native/alpha.json').write_bytes(b'corrupt')
    elif change == 'missing':
        (root / 'native/alpha.json').unlink()
    else:
        monkeypatch.setattr(tweak_mods, '_script_compiler_revision', lambda: 'new compiler')
        assert tweak_mods.needs_rebuild(game, library)['needed']
    loads = []
    load = script_mods.load_script
    monkeypatch.setattr(script_mods, 'load_script', lambda folder: loads.append(Path(folder).name) or load(folder))
    tweak_mods.apply(game, library)
    assert loads == (['Alpha', 'Beta'] if change == 'compiler' else ['Alpha'])
    assert not tweak_mods.needs_rebuild(game, library)['needed']


@pytest.mark.parametrize('input_kind', ['enabled', 'settings', 'module'])
def test_script_build_rechecks_observed_mod_dependencies(game, library, monkeypatch, input_kind):
    from core import script_mods
    root = library / 'Beta'
    path = root / 'script/tweak.py'
    expression = f"context.{input_kind}('alpha'" + (", 'tweak')" if input_kind == 'module' else ')')
    path.write_text(path.read_text().replace('    return', f'    {expression}\n    return', 1))
    tweak_mods.apply(game, library)
    loads = []
    load = script_mods.load_script
    monkeypatch.setattr(script_mods, 'load_script', lambda folder: loads.append(Path(folder).name) or load(folder))
    tweak_mods.apply(game, library)
    assert loads == []
    if input_kind == 'enabled':
        tweak_mods.save({'alpha': {'enabled': False}}, library)
    else:
        tweak_mods.save({'alpha': {'values': {'step': 4}}}, library)
    tweak_mods.apply(game, library)
    assert 'Beta' in loads


def test_script_build_rechecks_combined_game_params(game, library, monkeypatch):
    from core import script_mods
    from plugins.ds1 import mod_loader
    path = library / 'Beta/script/tweak.py'
    path.write_text(path.read_text().replace('    return', '    context.game_params()\n    return', 1))
    source = game / mod_loader.RELATIVE
    source.parent.mkdir(parents=True)
    source.write_bytes(b'original parameter inputs')
    monkeypatch.setattr(mod_loader, 'active_mods', lambda root: [])
    monkeypatch.setattr(mod_loader, '_compose_params', lambda original, mods: (original, []))
    tweak_mods.apply(game, library)
    loads = []
    load = script_mods.load_script
    monkeypatch.setattr(script_mods, 'load_script', lambda folder: loads.append(Path(folder).name) or load(folder))
    tweak_mods.apply(game, library)
    assert loads == []
    source.write_bytes(b'changed parameter inputs!')
    tweak_mods.apply(game, library)
    assert loads == ['Beta']


def test_script_build_rechecks_original_game_files(game, library, monkeypatch):
    from core import script_mods
    path = library / 'Alpha/script/tweak.py'
    path.write_text("import json\n\ndef build(settings, context):\n"
                    "    return {'script/talk/test.dcx': b'generated talk',\n"
                    "            'native/alpha.json': json.dumps(" + repr(SPECS['alpha']) + ")}\n")
    # Use the normal core build path without deploying this small fixture file.
    context = lambda: tweak_mods.BuildContext({'alpha': library / 'Alpha'}, game, library)
    source = game / 'script/talk/test.dcx'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'vanilla talk')
    root = library / 'Alpha'
    script_mods.build(root, context(), allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert script_mods.build(root, context(), allowed_roots=tweak_mods.ALLOWED_ROOTS)['cached']
    source.write_bytes(b'new vanilla talk')
    assert not script_mods.build(root, context(), allowed_roots=tweak_mods.ALLOWED_ROOTS).get('cached')


@pytest.mark.parametrize('managed', [tweak_mods.LAYOUT, *tweak_mods.ESD])
def test_unchanged_menu_archives_do_not_recompose_after_restart(tmp_path, monkeypatch, managed):
    calls = []
    def compose(original, specs, *args):
        calls.append((original, specs))
        return b'compiled:' + original + json.dumps(specs).encode()
    monkeypatch.setattr(tweak_mods.menu_layout, 'compose', compose)
    monkeypatch.setattr(tweak_mods.menu_scripts, 'compose', compose)
    monkeypatch.setattr(tweak_mods, '_script_compiler_revision', lambda: 'compiler-one')
    specs = [{'owner': 'example', 'changes': []}]
    expected = tweak_mods._compose_menu(b'vanilla', specs, managed, tmp_path)
    # No in-memory result cache is involved: reopen the persisted store.
    assert tweak_mods._compose_menu(b'vanilla', specs, managed, tmp_path) == expected
    assert len(calls) == 1
    tweak_mods._compose_menu(b'changed original', specs, managed, tmp_path)
    tweak_mods._compose_menu(b'vanilla', [{'owner': 'different', 'changes': []}], managed, tmp_path)
    monkeypatch.setattr(tweak_mods, '_script_compiler_revision', lambda: 'compiler-two')
    tweak_mods._compose_menu(b'vanilla', specs, managed, tmp_path)
    assert len(calls) == 4


def test_same_size_same_timestamp_script_edit_is_not_hidden_by_bytecode(game, library):
    import os
    from core import script_mods
    root = library / 'Alpha'
    path = root / 'script/tweak.py'
    path.write_text("def build(settings, context):\n    return {'native/value.json': b'first'}\n")
    context = lambda: tweak_mods.BuildContext({'alpha': root}, game, library)
    script_mods.build(root, context(), allowed_roots=tweak_mods.ALLOWED_ROOTS)
    before = path.stat()
    path.write_text(path.read_text().replace("b'first'", "b'other'"))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    script_mods.build(root, context(), allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert (root / 'native/value.json').read_bytes() == b'other'


def test_a_source_edit_during_build_remains_stale_until_rebuilt(game, library):
    root = library / 'Alpha'
    path = root / 'script/tweak.py'
    path.write_text('from pathlib import Path\n' + path.read_text().replace(
        '    return', "    source = Path(__file__)\n"
        "    if not source.read_text().endswith('# edited during build\\n'):\n"
        "        source.write_text(source.read_text() + '\\n# edited during build\\n')\n    return", 1))
    tweak_mods.apply(game, library)
    assert tweak_mods.needs_rebuild(game, library)['stale'] == ['alpha']
    tweak_mods.apply(game, library)
    assert not tweak_mods.needs_rebuild(game, library)['needed']


def test_full_save_reuses_unrelated_scripts_menu_and_data_composition(game, library, api, monkeypatch):
    from core import script_mods
    from plugins.ds1 import mod_loader, deployment
    nodes = install_fixture_menu(game, monkeypatch)
    path = library / 'Beta/script/tweak.py'
    path.write_text('import json\n\ndef build(settings, context):\n    return ' + repr({
        'native/beta.json': json.dumps(SPECS['beta']), 'layout/beta.json': json.dumps(nodes)}) + '\n')
    for folder in (library / 'Alpha', library / 'Beta'):
        Ds1ModAdapter().prepare_editable(folder)
    counts = {'scripts': [], 'menu': 0, 'data': 0}
    load, compose_menu = script_mods.load_script, tweak_mods.menu_layout.compose
    def counted_script(root):
        counts['scripts'].append(Path(root).name)
        return load(root)
    def counted_menu(*args):
        counts['menu'] += 1
        return compose_menu(*args)
    def counted_data(*args, **kwargs):
        counts['data'] += 1
        return mod_loader.Composition({}, [])
    monkeypatch.setattr(script_mods, 'load_script', counted_script)
    monkeypatch.setattr(tweak_mods.menu_layout, 'compose', counted_menu)
    monkeypatch.setattr(mod_loader, 'compose_installed', counted_data)
    monkeypatch.setattr(deployment, 'status', lambda *args: {})
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    adapter.activate([library / 'Alpha', library / 'Beta'], game)
    assert counts == {'scripts': ['Alpha', 'Beta'], 'menu': 1, 'data': 1}
    counts['scripts'].clear()
    tweak_mods.save({'alpha': {'values': {'step': 6}}}, library)
    status, result = api[0]('/api/save', {})
    assert status == 200 and result['tweaksRebuilt'] and not result['tweaksNeedRebuild']
    assert counts == {'scripts': ['Alpha'], 'menu': 1, 'data': 1}


def test_save_composes_validated_binary_menu_commands_and_keeps_mods_enabled(game, library, api, monkeypatch):
    from test_ds1_menu_scripts import archive, build_script, script, passes_of
    from plugins.ds1 import menu_scripts
    original = archive({'i02-00.esd': build_script().to_bytes()})
    managed = next(item for item in tweak_mods.ESD if tweak_mods.ESD_ARCHIVE[item] == 'ingame')
    installed = game / managed.relative
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.write_bytes(original)
    monkeypatch.setitem(menu_scripts.VANILLA, 'ingame', (len(original), hashlib.sha256(original).hexdigest()))
    path = library / 'Beta/script/tweak.py'
    path.write_text('def build(settings, context):\n    return ' + repr({
        'esd/beta.json': json.dumps(script())}) + '\n')
    assert isinstance(menu_scripts.validate(script(), 'Beta')['changes'][0]['after']['arg_bytes'][0], bytes)
    # Seed the installed runtime without running the new menu contribution.
    tweak_mods.save({'beta': {'enabled': False}}, library)
    tweak_mods.apply(game, library)
    tweak_mods.save({'beta': {'enabled': True}}, library)
    post, _, saved = api
    status, result = post('/api/save', {})
    assert status == 200 and result['tweaksRebuilt'] and not result['tweaksNeedRebuild']
    assert result['disabledMods'] == []
    assert saved == ['saved']
    assert [command.id for command in passes_of(installed.read_bytes())] == [15, 29, 20]
    # A later Save uses the cached validated-byte specification successfully.
    tweak_mods.save({'alpha': {'values': {'step': 2}}}, library)
    assert post('/api/save', {})[1]['disabledMods'] == []
    assert all(json.loads((library / name / 'mod.json').read_text())['enabled']
               for name in ('Alpha', 'Beta'))


def test_unsupported_optional_menu_cache_value_falls_back_to_composition(tmp_path, monkeypatch):
    monkeypatch.setattr(tweak_mods.menu_layout, 'compose', lambda original, specs: b'valid composed menu')
    result = tweak_mods._compose_menu(b'original', [{'internal': object()}], tweak_mods.LAYOUT, tmp_path)
    assert result == b'valid composed menu'


def test_unserializable_build_cache_record_does_not_fail_or_disable_mod(game, library, monkeypatch):
    monkeypatch.setattr(tweak_mods.BuildContext, 'build_record', lambda *args: {'unexpected': b'binary'})
    tweak_mods.apply(game, library)
    assert (library / 'Alpha/native/alpha.json').is_file()
    assert (library / 'Beta/native/beta.json').is_file()
    assert all(json.loads((library / name / 'mod.json').read_text())['enabled']
               for name in ('Alpha', 'Beta'))


@pytest.mark.parametrize('failure', ['missing member', 'unreadable member'])
def test_save_disables_only_the_mod_with_an_unusable_menu_target(game, library, api, monkeypatch, failure):
    from test_ds1_menu_scripts import archive, build_script, script
    from plugins.ds1 import menu_scripts
    data = build_script().to_bytes() if failure == 'missing member' else b'unsupported ESD layout'
    original = archive({'i02-00.esd': data})
    managed = next(item for item in tweak_mods.ESD if tweak_mods.ESD_ARCHIVE[item] == 'ingame')
    installed = game / managed.relative
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.write_bytes(original)
    monkeypatch.setitem(menu_scripts.VANILLA, 'ingame', (len(original), hashlib.sha256(original).hexdigest()))
    bad = script(member='missing.esd' if failure == 'missing member' else 'i02-00.esd')
    (library / 'Beta/script/tweak.py').write_text('def build(settings, context):\n    return ' +
                                               repr({'esd/beta.json': json.dumps(bad)}) + '\n')
    tweak_mods.save({'beta': {'enabled': False}}, library)
    tweak_mods.apply(game, library)
    tweak_mods.save({'beta': {'enabled': True}}, library)
    status, result = api[0]('/api/save', {})
    assert status == 200 and result['tweaksRebuilt'] and not result['tweaksNeedRebuild']
    assert 'tweaksError' not in result
    assert [mod['name'] for mod in result['disabledMods']] == ['Beta']
    assert not json.loads((library / 'Beta/mod.json').read_text())['enabled']
    assert json.loads((library / 'Alpha/mod.json').read_text())['enabled']
    assert installed.read_bytes() == original
    # The saved project and subsequent Save remain usable after recovery.
    assert api[0]('/api/save', {})[0] == 200
