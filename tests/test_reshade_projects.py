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
