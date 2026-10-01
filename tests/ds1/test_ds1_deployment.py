"""DS1 deployment: native in-place param replacement with byte-exact restore.

Everything here runs against synthetic tmp_path game/project directories;
nothing touches an installed game.
"""
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1 import deployment
from plugins.ds1.store import ItemStore, MARKER, RELATIVE


def project(tmp_path, name="mod"):
    game, mod = tmp_path / "game", tmp_path / name
    live = game / RELATIVE
    if not live.is_file():
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def backup_path(game):
    return deployment._backup_path(game)


def marker_path(game):
    return deployment._marker_path(game)


def read_marker(game):
    return json.loads(marker_path(game).read_text())


class CrashAfter:
    """Monkeypatches deployment.atomic_write to perform the real write, then raise
    immediately after the call targeting `trigger`, simulating a process crash that
    happens after those bytes hit disk but before the next marker commit."""

    def __init__(self, monkeypatch, trigger):
        self.trigger = Path(trigger)
        self.original = deployment.atomic_write
        self.fired = False

        def fake(path, data):
            self.original(path, data)
            if Path(path) == self.trigger and not self.fired:
                self.fired = True
                raise RuntimeError("simulated crash")
        monkeypatch.setattr(deployment, "atomic_write", fake)


def _make_junction(link: Path, target: Path) -> bool:
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, text=True)
    return result.returncode == 0 and link.is_dir()


def _make_symlink(link: Path, target: Path) -> bool:
    result = subprocess.run(["cmd", "/c", "mklink", str(link), str(target)],
                            capture_output=True, text=True)
    return result.returncode == 0 and link.is_file()


# --- Baseline apply/disable/reapply lifecycle ---

def test_apply_preserves_original_once_and_installs_the_saved_archive(tmp_path):
    game, mod = project(tmp_path)
    original = (game / RELATIVE).read_bytes()
    ItemStore(game, mod, False).save()

    before = deployment.status(game, mod)
    assert before["isProject"] and before["sourceReady"] and before["liveReady"]
    assert not before["everApplied"]
    assert not before["matchesOriginal"] and not before["backupOk"]
    assert not before["enabled"] and not before["changedExternally"] and not before["stale"]

    store = ItemStore(game, mod, False)
    store.edit("EquipParamGoods", 100, "sellValue", 42)
    store.save()
    after = deployment.apply(game, mod)
    assert after["enabled"] and after["backupOk"] and not after["stale"]
    assert (game / RELATIVE).read_bytes() == (mod / RELATIVE).read_bytes()
    assert backup_path(game).read_bytes() == original
    marker = read_marker(game)
    assert marker["modId"] == "lexeditor-ds1" and marker["enabled"] is True
    assert marker["originalHash"] == deployment._hash_file(backup_path(game))
    assert marker["pendingHash"] is None and marker["pendingKind"] is None


def test_disable_restores_byte_exact_original_and_keeps_backup_for_reapply(tmp_path):
    game, mod = project(tmp_path)
    original = (game / RELATIVE).read_bytes()
    store = ItemStore(game, mod, False)
    store.edit("EquipParamGoods", 100, "sellValue", 7)
    store.save()
    deployment.apply(game, mod)
    assert (game / RELATIVE).read_bytes() != original

    disabled = deployment.disable(game)
    assert not disabled["enabled"]
    assert (game / RELATIVE).read_bytes() == original
    assert backup_path(game).is_file()

    reapplied = deployment.apply(game, mod)
    assert reapplied["enabled"]
    assert (game / RELATIVE).read_bytes() == (mod / RELATIVE).read_bytes() != original


def test_reapply_after_a_later_save_installs_the_newest_edit(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, False)
    store.save()
    deployment.apply(game, mod)
    assert not deployment.status(game, mod)["stale"]

    store.edit("EquipParamGoods", 100, "sellValue", 9)
    store.save()
    assert deployment.status(game, mod)["stale"]
    assert (game / RELATIVE).read_bytes() != (mod / RELATIVE).read_bytes()

    deployment.apply(game, mod)
    status = deployment.status(game, mod)
    assert not status["stale"]
    assert (game / RELATIVE).read_bytes() == (mod / RELATIVE).read_bytes()


def test_switching_the_active_project_replaces_the_installed_archive(tmp_path):
    game, mod_a = project(tmp_path, "mod-a")
    _, mod_b = project(tmp_path, "mod-b")
    store_a, store_b = ItemStore(game, mod_a, False), ItemStore(game, mod_b, False)
    store_a.edit("EquipParamGoods", 100, "sellValue", 11)
    store_a.save()
    store_b.edit("EquipParamGoods", 100, "sellValue", 22)
    store_b.save()

    deployment.apply(game, mod_a)
    assert (game / RELATIVE).read_bytes() == (mod_a / RELATIVE).read_bytes()
    after_b = deployment.apply(game, mod_b)
    assert (game / RELATIVE).read_bytes() == (mod_b / RELATIVE).read_bytes()
    assert after_b["activeProjectRoot"] == str(mod_b.resolve())


def test_no_mod_selected_fails_closed_and_disable_is_a_no_op(tmp_path):
    game, _ = project(tmp_path)
    with pytest.raises(ValueError, match="Select or create"):
        deployment.apply(game, None)
    status = deployment.status(game, None)
    assert not status["enabled"] and not status["isProject"]
    disabled = deployment.disable(game)
    assert not disabled["enabled"]


def test_fails_closed_on_missing_prerequisites(tmp_path):
    game, mod = project(tmp_path)
    with pytest.raises(ValueError, match="valid Dark Souls mod project"):
        deployment.apply(game, tmp_path / "not-a-project")
    with pytest.raises(FileNotFoundError, match="Save the project"):
        deployment.apply(game, mod)
    (game / RELATIVE).unlink()
    mod_saved = tmp_path / "mod-saved"
    mod_saved.mkdir(); (mod_saved / MARKER).touch()
    (mod_saved / RELATIVE).parent.mkdir(parents=True)
    (mod_saved / RELATIVE).write_bytes(make_archive())
    with pytest.raises(FileNotFoundError, match="installed game has no"):
        deployment.apply(game, mod_saved)


def test_refuses_when_the_installed_file_changed_externally(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    (game / RELATIVE).write_bytes(b"tampered by something else")
    with pytest.raises(RuntimeError, match="changed outside Lexeditor"):
        deployment.apply(game, mod)
    with pytest.raises(RuntimeError, match="changed outside Lexeditor"):
        deployment.disable(game)
    assert deployment.status(game, mod)["changedExternally"]


def test_refuses_when_the_preserved_backup_is_missing_or_changed(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    backup_path(game).write_bytes(b"corrupted backup")
    with pytest.raises(RuntimeError, match="preserved original copy is missing or changed"):
        deployment.apply(game, mod)
    with pytest.raises(RuntimeError, match="preserved original copy is missing or changed"):
        deployment.disable(game)


def test_refuses_an_unmanaged_backup_left_by_a_crash_or_another_tool(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    backup_path(game).parent.mkdir(parents=True, exist_ok=True)
    backup_path(game).write_bytes((game / RELATIVE).read_bytes())
    with pytest.raises(RuntimeError, match="unmanaged backup already exists"):
        deployment.apply(game, mod)
    assert deployment.status(game, mod)["everApplied"] is False


def test_service_exposes_apply_and_disable_routes(tmp_path):
    from urllib.request import Request, urlopen
    from plugins.ds1.plugin import DS1Session
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    original = (game / RELATIVE).read_bytes()
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                          "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0"})

    def request(path, payload=None):
        req = Request(session.url.rstrip("/") + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
        with urlopen(req) as reply:
            return json.load(reply)
    try:
        session.start()
        assert request("/api/deployment")["enabled"] is False
        applied = request("/api/deployment/apply", {})
        assert applied["enabled"] is True
        disabled = request("/api/deployment/disable", {})
        assert disabled["enabled"] is False
        assert (game / RELATIVE).read_bytes() == original
    finally:
        session.stop()


# --- Issue 1: disable() must validate live state even when already disabled ---

def test_disable_refuses_an_external_edit_made_after_a_prior_disable(tmp_path):
    game, mod = project(tmp_path)
    original = (game / RELATIVE).read_bytes()
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    deployment.disable(game)
    assert (game / RELATIVE).read_bytes() == original

    (game / RELATIVE).write_bytes(b"external edit after disable")
    with pytest.raises(RuntimeError, match="changed outside Lexeditor"):
        deployment.disable(game)
    assert (game / RELATIVE).read_bytes() == b"external edit after disable"
    assert deployment.status(game, mod)["changedExternally"]


def test_disable_is_a_safe_no_op_when_nothing_was_ever_applied(tmp_path):
    game, _ = project(tmp_path)
    disabled = deployment.disable(game)
    assert not disabled["enabled"] and not disabled["everApplied"]


# --- Issue 2: durable pending-transaction recovery across a simulated crash ---

def test_crash_between_live_write_and_marker_commit_on_initial_apply(tmp_path, monkeypatch):
    game, mod = project(tmp_path)
    original = (game / RELATIVE).read_bytes()
    store = ItemStore(game, mod, False)
    store.edit("EquipParamGoods", 100, "sellValue", 42)
    store.save()
    new_hash = deployment._hash_file(mod / RELATIVE)
    live = game / RELATIVE

    crash = CrashAfter(monkeypatch, live)
    with pytest.raises(RuntimeError, match="simulated crash"):
        deployment.apply(game, mod)
    assert crash.fired

    assert deployment._hash_file(live) == new_hash
    marker = read_marker(game)
    assert marker["pendingHash"] == new_hash and marker["pendingKind"] == "apply"
    assert marker["enabled"] is False and marker["activeHash"] is None

    status = deployment.status(game, mod)
    assert status["pendingRecovery"] is True
    assert status["changedExternally"] is False

    monkeypatch.undo()
    recovered = deployment.apply(game, mod)
    assert recovered["enabled"] is True and not recovered["pendingRecovery"]
    marker_after = read_marker(game)
    assert marker_after["activeHash"] == new_hash and marker_after["pendingHash"] is None
    assert (game / RELATIVE).read_bytes() == (mod / RELATIVE).read_bytes()
    assert backup_path(game).read_bytes() == original


def test_crash_between_live_write_and_marker_commit_on_reapply(tmp_path, monkeypatch):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, False)
    store.save()
    deployment.apply(game, mod)

    store.edit("EquipParamGoods", 100, "sellValue", 9)
    store.save()
    new_hash = deployment._hash_file(mod / RELATIVE)
    live = game / RELATIVE
    old_active = read_marker(game)["activeHash"]

    crash = CrashAfter(monkeypatch, live)
    with pytest.raises(RuntimeError, match="simulated crash"):
        deployment.apply(game, mod)
    assert crash.fired
    assert deployment._hash_file(live) == new_hash
    marker = read_marker(game)
    assert marker["pendingHash"] == new_hash and marker["activeHash"] == old_active

    monkeypatch.undo()
    recovered = deployment.apply(game, mod)
    assert recovered["enabled"] and not recovered["stale"]
    assert read_marker(game)["activeHash"] == new_hash
    assert (game / RELATIVE).read_bytes() == (mod / RELATIVE).read_bytes()


def test_crash_between_live_write_and_marker_commit_on_disable(tmp_path, monkeypatch):
    game, mod = project(tmp_path)
    original = (game / RELATIVE).read_bytes()
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    live = game / RELATIVE

    crash = CrashAfter(monkeypatch, live)
    with pytest.raises(RuntimeError, match="simulated crash"):
        deployment.disable(game)
    assert crash.fired
    assert live.read_bytes() == original
    marker = read_marker(game)
    assert marker["pendingHash"] is not None and marker["pendingKind"] == "disable"
    assert marker["enabled"] is True

    status = deployment.status(game, None)
    assert status["pendingRecovery"] is True

    monkeypatch.undo()
    disabled = deployment.disable(game)
    assert not disabled["enabled"]
    marker_after = read_marker(game)
    assert marker_after["enabled"] is False and marker_after["activeHash"] is None and marker_after["pendingHash"] is None
    assert (game / RELATIVE).read_bytes() == original


def test_a_pending_apply_is_finalized_even_if_disable_is_called_next(tmp_path, monkeypatch):
    """Whatever operation runs next must settle the true on-disk state first."""
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    live = game / RELATIVE

    crash = CrashAfter(monkeypatch, live)
    with pytest.raises(RuntimeError):
        deployment.apply(game, mod)
    monkeypatch.undo()

    deployment.disable(game)
    marker = read_marker(game)
    assert marker["enabled"] is False and marker["pendingHash"] is None
    assert deployment._hash_file(live) == marker["originalHash"]


# --- Issue 3: symlink / junction ancestors must be refused, not followed ---

def test_refuses_a_junction_standing_in_for_the_live_param_folder(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    decoy = tmp_path / "decoy-outside-game"
    decoy.mkdir()
    decoy_live = decoy / RELATIVE.name
    decoy_live.write_bytes(make_archive())  # a fake "live" file behind the junction
    junction = game / RELATIVE.parent  # param/GameParam
    (junction / RELATIVE.name).unlink()
    junction.rmdir()
    if not _make_junction(junction, decoy):
        pytest.skip("Could not create an NTFS junction in this environment")
    try:
        before = decoy_live.read_bytes()
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.apply(game, mod)
        assert decoy_live.read_bytes() == before  # the real write never happened
        assert not (decoy / (RELATIVE.name + ".lexeditor-original")).exists()
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)


def test_refuses_a_junction_standing_in_for_the_mod_project_param_folder(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    decoy = tmp_path / "decoy-outside-project"
    decoy.mkdir()
    (decoy / RELATIVE.name).write_bytes(make_archive())  # a fake "saved" file behind the junction
    junction = mod / RELATIVE.parent
    (junction / RELATIVE.name).unlink()
    junction.rmdir()
    if not _make_junction(junction, decoy):
        pytest.skip("Could not create an NTFS junction in this environment")
    try:
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.apply(game, mod)
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)


def test_refuses_a_project_rooted_inside_the_installed_game(tmp_path):
    game, _ = project(tmp_path)
    nested = game / "mod-inside-game"
    nested.mkdir()
    (nested / MARKER).touch()
    (nested / RELATIVE).parent.mkdir(parents=True)
    (nested / RELATIVE).write_bytes(make_archive())
    with pytest.raises(ValueError, match="outside the installed game"):
        deployment.apply(game, nested)


# --- Issue 4: Vanilla / a new project must read the true original, not a deployed mod ---

def test_vanilla_and_a_fresh_project_read_true_original_after_apply(tmp_path):
    from plugins.ds1.formats import ItemDocument
    game, mod_a = project(tmp_path, "mod-a")
    pristine_value = ItemDocument((game / RELATIVE).read_bytes()).value("EquipParamGoods", 100, "sellValue")

    store_a = ItemStore(game, mod_a, False)
    store_a.edit("EquipParamGoods", 100, "sellValue", pristine_value + 77)
    store_a.save()
    deployment.apply(game, mod_a)
    assert (game / RELATIVE).read_bytes() == (mod_a / RELATIVE).read_bytes()

    # Vanilla (no project) must still see the true original, not mod_a's deployed edit.
    vanilla_store = ItemStore(game, None, True)
    assert vanilla_store.get().value("EquipParamGoods", 100, "sellValue") == pristine_value

    # A brand-new project (never saved) must also start from the true original.
    _, mod_b = project(tmp_path, "mod-b")
    fresh_store = ItemStore(game, mod_b, False)
    assert fresh_store.get().value("EquipParamGoods", 100, "sellValue") == pristine_value


def test_vanilla_reads_the_original_across_a_project_switch_and_reopen(tmp_path):
    game, mod_a = project(tmp_path, "mod-a")
    _, mod_b = project(tmp_path, "mod-b")
    store_a, store_b = ItemStore(game, mod_a, False), ItemStore(game, mod_b, False)
    store_a.edit("EquipParamGoods", 100, "sellValue", 11)
    store_a.save()
    store_b.edit("EquipParamGoods", 100, "sellValue", 22)
    store_b.save()

    deployment.apply(game, mod_a)
    deployment.apply(game, mod_b)
    assert ItemStore(game, None, True).get().value("EquipParamGoods", 100, "sellValue") == 0

    reopened_a = ItemStore(game, mod_a, False)
    assert reopened_a.get().value("EquipParamGoods", 100, "sellValue") == 11


# --- Issue 1 (round 2): vanilla_source() must fail closed, never fall back to live ---

def test_vanilla_fails_closed_when_the_backup_is_missing_after_apply(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    backup_path(game).unlink()

    with pytest.raises(RuntimeError, match="preserved original copy"):
        ItemStore(game, None, True).get()

    _, mod_b = project(tmp_path, "mod-b")
    with pytest.raises(RuntimeError, match="preserved original copy"):
        ItemStore(game, mod_b, False).get()  # a fresh, unsaved project falls back the same way


def test_vanilla_fails_closed_when_the_backup_is_corrupt_after_apply(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    backup_path(game).write_bytes(b"corrupted")

    with pytest.raises(RuntimeError, match="preserved original copy"):
        ItemStore(game, None, True).get()
    _, mod_b = project(tmp_path, "mod-b")
    with pytest.raises(RuntimeError, match="preserved original copy"):
        ItemStore(game, mod_b, False).get()


def test_service_surfaces_the_vanilla_fail_closed_error_as_a_clean_400(tmp_path):
    from urllib.error import HTTPError
    from urllib.request import urlopen
    from plugins.ds1.plugin import DS1Session
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    deployment.apply(game, mod)
    backup_path(game).unlink()

    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1",
                          "LEXEDITOR_MOD_READ_ONLY": "1"})
    try:
        session.start()
        try:
            urlopen(session.url.rstrip("/") + "/api/state")
            raise AssertionError("Expected the missing-backup fail-closed error to surface")
        except HTTPError as error:
            assert error.code == 400
            body = json.loads(error.read())
            assert "preserved original copy" in body["error"]
    finally:
        session.stop()


# --- Issue 2 (round 2): reparse checks must run on the raw root, before .resolve() ---

def test_refuses_a_junction_standing_in_for_the_whole_game_root(tmp_path):
    decoy = tmp_path / "decoy-whole-game-root"
    decoy_live = decoy / RELATIVE
    decoy_live.parent.mkdir(parents=True)
    decoy_live.write_bytes(make_archive())
    junction = tmp_path / "game-root-link"
    if not _make_junction(junction, decoy):
        pytest.skip("Could not create an NTFS junction in this environment")
    mod = tmp_path / "mod"
    mod.mkdir(); (mod / MARKER).touch()
    (mod / RELATIVE).parent.mkdir(parents=True)
    (mod / RELATIVE).write_bytes(make_archive())
    try:
        before = decoy_live.read_bytes()
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.apply(junction, mod)  # game_root itself is the junction
        assert decoy_live.read_bytes() == before
        assert not deployment._backup_path(decoy).exists()
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.disable(junction)
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)


def test_refuses_a_junction_standing_in_for_the_whole_project_root(tmp_path):
    game, _ = project(tmp_path)
    decoy = tmp_path / "decoy-whole-project-root"
    (decoy / RELATIVE).parent.mkdir(parents=True)
    (decoy / RELATIVE).write_bytes(make_archive())
    (decoy / MARKER).touch()
    junction = tmp_path / "project-root-link"
    if not _make_junction(junction, decoy):
        pytest.skip("Could not create an NTFS junction in this environment")
    try:
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.apply(game, junction)  # project_root itself is the junction
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)


def test_refuses_a_junction_standing_in_for_an_ancestor_of_the_game_root(tmp_path):
    decoy = tmp_path / "decoy-ancestor"
    (decoy / "nested" / RELATIVE.parent).mkdir(parents=True)
    (decoy / "nested" / RELATIVE).write_bytes(make_archive())
    ancestor_link = tmp_path / "ancestor-link"
    if not _make_junction(ancestor_link, decoy):
        pytest.skip("Could not create an NTFS junction in this environment")
    game_root = ancestor_link / "nested"  # game_root itself is ordinary, but its parent is a junction
    mod = tmp_path / "mod"
    mod.mkdir(); (mod / MARKER).touch()
    (mod / RELATIVE).parent.mkdir(parents=True)
    (mod / RELATIVE).write_bytes(make_archive())
    try:
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.apply(game_root, mod)
    finally:
        subprocess.run(["cmd", "/c", "rmdir", str(ancestor_link)], capture_output=True)


def test_refuses_a_symlinked_project_marker_file(tmp_path):
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    decoy_target = tmp_path / "decoy-marker-target.txt"
    decoy_target.write_text("not a real project marker")
    marker_file = mod / MARKER
    marker_file.unlink()
    if not _make_symlink(marker_file, decoy_target):
        pytest.skip("Could not create a file symlink in this environment")
    try:
        with pytest.raises(RuntimeError, match="symlink or junction"):
            deployment.apply(game, mod)
    finally:
        marker_file.unlink(missing_ok=True)


def test_ordinary_absolute_paths_with_dot_segments_still_work(tmp_path):
    """Lexical normalization must not reject or mishandle a perfectly normal path."""
    game, mod = project(tmp_path)
    ItemStore(game, mod, False).save()
    noisy_game = game.parent / "." / game.name / ".." / game.name
    noisy_mod = mod.parent / "." / mod.name
    applied = deployment.apply(noisy_game, noisy_mod)
    assert applied["enabled"]
    assert (game / RELATIVE).read_bytes() == (mod / RELATIVE).read_bytes()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
