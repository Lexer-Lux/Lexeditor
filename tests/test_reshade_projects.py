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
