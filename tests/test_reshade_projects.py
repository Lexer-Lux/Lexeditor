"""A mod's ReShade preset must stay usable without Lexeditor."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import reshade_projects as rp


def test_missing_folder_reports_nothing_rather_than_failing(tmp_path):
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["hasFolder"] is False
    assert snapshot["presets"] == []
    assert snapshot["ready"] is False
    assert snapshot["manifest"]["enabled"] is False


def test_manifest_round_trips_as_plain_json(tmp_path):
    rp.write_manifest(tmp_path, {
        "enabled": True, "preset": "Cinematic.ini", "renderer": "dxgi",
        "repositories": [{"name": "qUINT", "version": "3.0"}],
    })
    written = json.loads(rp.manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert written["preset"] == "Cinematic.ini"
    assert written["repositories"] == [{"name": "qUINT", "version": "3.0"}]
    assert rp.read_manifest(tmp_path)["enabled"] is True


def test_repositories_are_named_never_copied(tmp_path):
    """A mod must not carry shaders it is not allowed to redistribute."""
    rp.write_manifest(tmp_path, {"repositories": [
        {"name": "qUINT", "version": "3.0"},
        {"missing_name": True},
    ]})
    manifest = rp.read_manifest(tmp_path)
    assert manifest["repositories"] == [{"name": "qUINT", "version": "3.0"}]


def test_a_preset_that_is_not_there_is_reported_not_silently_ignored(tmp_path):
    (tmp_path / "reshade").mkdir()
    rp.write_manifest(tmp_path, {"enabled": True, "preset": "Gone.ini"})
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["presets"] == []
    assert snapshot["ready"] is False


def test_presets_and_authored_shaders_are_listed_separately(tmp_path):
    root = tmp_path / "reshade"
    (root / "shaders").mkdir(parents=True)
    (root / "Cinematic.ini").write_text("[preset]\n", encoding="utf-8")
    (root / "shaders" / "MyGrade.fx").write_text("// authored\n", encoding="utf-8")
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["presets"] == ["Cinematic.ini"]
    assert snapshot["shaders"] == ["MyGrade.fx"]
    # The manifest itself is not a preset.
    rp.write_manifest(tmp_path, {"enabled": True, "preset": "Cinematic.ini"})
    assert rp.manifest_path(tmp_path).name not in rp.snapshot(tmp_path)["presets"]


def test_ready_needs_reshade_actually_installed(tmp_path):
    root = tmp_path / "reshade"
    root.mkdir()
    (root / "Cinematic.ini").write_text("[preset]\n", encoding="utf-8")
    rp.write_manifest(tmp_path, {"enabled": True, "preset": "Cinematic.ini"})
    assert rp.snapshot(tmp_path, tmp_path / "nogame")["ready"] is False

    game = tmp_path / "game"
    game.mkdir()
    (game / "dxgi.dll").write_bytes(b"\x00" * 64 + b"ReShade" + b"\x00" * 64)
    live = rp.snapshot(tmp_path, game)
    assert live["installedRenderer"] == "dxgi"
    assert live["ready"] is True


def test_a_games_own_loader_dll_is_not_mistaken_for_reshade(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "d3d11.dll").write_bytes(b"\x00" * 256)
    assert rp.installed_renderer(game) == ""


def test_only_a_real_reshade_dll_is_adopted(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    fake = tmp_path / "NotReShade.dll"
    fake.write_bytes(b"\x00" * 128)
    try:
        rp.adopt(fake)
    except ValueError as error:
        assert "does not look like" in str(error)
    else:  # pragma: no cover - the guard must hold
        raise AssertionError("a non-ReShade DLL was adopted")


def test_install_never_overwrites_a_games_own_loader(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    (store / rp.STORE_DLL).write_bytes(b"ReShade" + b"\x00" * 64)
    monkeypatch.setattr(rp, "STORE", store)

    game = tmp_path / "game"
    game.mkdir()
    own = game / "d3d11.dll"
    own.write_bytes(b"\x00" * 256)
    try:
        rp.install(game, "dx11")
    except ValueError as error:
        assert "not ReShade" in str(error)
    else:  # pragma: no cover - the guard must hold
        raise AssertionError("a game's own loader was overwritten")
    assert own.read_bytes() == b"\x00" * 256


def test_install_and_uninstall_round_trip(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    (store / rp.STORE_DLL).write_bytes(b"ReShade" + b"\x00" * 64)
    monkeypatch.setattr(rp, "STORE", store)

    game = tmp_path / "game"
    game.mkdir()
    result = rp.install(game, "dxgi")
    assert result["installed"] is True
    assert (game / "dxgi.dll").is_file()
    assert rp.installed_renderer(game) == "dxgi"

    removed = rp.uninstall(game)
    assert [entry["renderer"] for entry in removed["removed"]] == ["dxgi"]
    assert not (game / "dxgi.dll").exists()


def test_uninstall_leaves_a_games_own_loader_alone(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    own = game / "opengl32.dll"
    own.write_bytes(b"\x00" * 256)
    assert rp.uninstall(game)["removed"] == []
    assert own.is_file()


def test_repository_list_is_one_per_machine_and_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    rp.add_repository("qUINT", "3.0", "https://example.invalid/quint")
    rp.add_repository("iMMERSE", "1.2")
    assert [entry["name"] for entry in rp.repositories()] == ["iMMERSE", "qUINT"]

    # Adding the same name again updates it rather than listing it twice.
    rp.add_repository("qUINT", "4.0")
    assert [entry["version"] for entry in rp.repositories()] == ["1.2", "4.0"]

    rp.remove_repository("iMMERSE")
    assert [entry["name"] for entry in rp.repositories()] == ["qUINT"]


def test_repository_status_separates_missing_from_a_version_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    rp.add_repository("qUINT", "3.0")
    status = rp.repository_status({"repositories": [
        {"name": "qUINT", "version": "2.0"},
        {"name": "qUINT", "version": "3.0"},
        {"name": "Nowhere", "version": "1"},
    ]})
    assert [entry["state"] for entry in status] == [
        "version-mismatch", "present", "missing"]


def test_export_note_names_the_loader_repositories_and_authored_shaders(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    project = tmp_path / "project"
    rp.write_manifest(project, {
        "enabled": True, "preset": "MyLook.ini", "renderer": "dx12",
        "repositories": [{"name": "qUINT", "version": "3.0"}]})
    (project / "reshade" / "MyLook.ini").write_text("x", encoding="utf-8")
    shaders = project / "reshade" / "shaders"
    shaders.mkdir(parents=True, exist_ok=True)
    (shaders / "MyGrain.fx").write_text("x", encoding="utf-8")

    note = rp.export_note(project)
    assert "d3d12.dll" in note
    assert "qUINT (version 3.0)" in note
    assert "MyLook.ini" in note
    assert "MyGrain.fx" in note
    # The reader may never have used the editor, so the note must not need it.
    assert "Lexeditor" in note and "You do not need Lexeditor" in note

    written = rp.write_export_note(project)
    assert Path(written).name == rp.EXPORT_NOTE_NAME
    assert Path(written).read_text(encoding="utf-8") == note


def test_snapshot_reports_repository_state_for_the_mods_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    rp.add_repository("qUINT", "3.0")
    project = tmp_path / "project"
    rp.write_manifest(project, {"repositories": [{"name": "qUINT", "version": "3.0"}]})
    state = rp.snapshot(project)
    assert [entry["state"] for entry in state["repositoryStatus"]] == ["present"]
    assert [entry["name"] for entry in state["repositories"]] == ["qUINT"]
