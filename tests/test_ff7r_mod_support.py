from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plugins.ff7r import tooling
from plugins.ff7r.mod_support import PakModAdapter
from plugins.ff7r.project_deployment import (
    deploy_built_pak,
    deployed_pak_path,
    marker_path,
    remove_deployed_pak,
)


def _install_repak(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LEXEDITOR_REPAK", raising=False)
    monkeypatch.setattr(tooling, "helper_root", lambda: tmp_path / "repak-helper")

    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("FF7R mod compatibility tests must not use the network")

    monkeypatch.setattr(tooling.urllib.request, "urlopen", network_forbidden)
    status = tooling.helper_install()
    assert status["installed"] is True
    assert status["integrity"] == "verified"
    assert status["packageIntegrity"] == "verified"


def _pack(root: Path, name: str, assets: dict[str, bytes], output: Path | None = None) -> Path:
    source = root / (name + "-content")
    for relative, data in assets.items():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    destination = output or (root / name / (name + "_P.pak"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    return tooling.pack_directory(source, destination, version="V4")


def _game(root: Path) -> Path:
    game = root / "game"
    executable = game / "End/Binaries/Win64/ff7remake_.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"synthetic executable marker")
    return game


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_verified_mod_library_uses_real_paks_and_preserves_external_mod(monkeypatch, tmp_path):
    _install_repak(monkeypatch, tmp_path)
    game = _game(tmp_path)
    mods_root = game / "End/Content/Paks/~mods"
    external = _pack(
        tmp_path,
        "external",
        {"End/Content/GameContents/DataObject/Resident/Equipment.uasset": b"external"},
        mods_root / "ThirdPartyEquipment_P.pak",
    )
    external_sha = _sha(external)

    conflicting = _pack(
        tmp_path,
        "conflicting",
        {"End/Content/GameContents/DataObject/Resident/Equipment.uasset": b"mine"},
    ).parent
    adapter = PakModAdapter()
    assert adapter.verified is True
    report = adapter.inspect(conflicting, [Path("conflicting_P.pak")])
    assert report["valid"] is True
    with pytest.raises(ValueError, match="installed mod also changes"):
        adapter.activate([conflicting], game)
    assert _sha(external) == external_sha

    compatible = _pack(
        tmp_path,
        "compatible",
        {"End/Content/GameContents/DataObject/Resident/Item.uasset": b"mine"},
    ).parent
    plan = adapter.activate([compatible], game)
    deployed = Path(plan["destination"]) / "compatible_P.pak"
    assert deployed.is_file()
    assert adapter.active_mod_ids(game) == ["compatible"]
    assert _sha(external) == external_sha

    adapter.activate([], game)
    assert not deployed.exists()
    assert external.is_file()
    assert _sha(external) == external_sha


def test_real_pak_selected_mod_collision_is_rejected_before_deploy(monkeypatch, tmp_path):
    _install_repak(monkeypatch, tmp_path)
    game = _game(tmp_path)
    asset = "End/Content/GameContents/DataObject/Resident/Equipment.uasset"
    first = _pack(tmp_path, "first", {asset: b"first"}).parent
    second = _pack(tmp_path, "second", {asset: b"second"}).parent

    with pytest.raises(ValueError, match="Conflicting asset"):
        PakModAdapter().activate([first, second], game)

    assert not (game / "End/Content/Paks/~mods/LexeditorLibrary").exists()


def test_direct_project_deploy_refuses_real_pak_collision_and_restores_cleanly(
    monkeypatch, tmp_path
):
    _install_repak(monkeypatch, tmp_path)
    game = _game(tmp_path)
    mods_root = game / "End/Content/Paks/~mods"
    external = _pack(
        tmp_path,
        "external-direct",
        {"End/Content/GameContents/DataObject/Resident/Equipment.uasset": b"external"},
        mods_root / "ExternalBalance_P.PAK",
    )
    external_sha = _sha(external)

    built = _pack(
        tmp_path,
        "project-conflict",
        {"End/Content/GameContents/DataObject/Resident/Equipment.uasset": b"project"},
        tmp_path / "project/build/Lexeditor-FF7R_P.pak",
    )
    with pytest.raises(RuntimeError, match="conflicts with another active mod"):
        deploy_built_pak(game, built)
    assert not deployed_pak_path(game).exists()
    assert not marker_path(game).exists()
    assert _sha(external) == external_sha

    built = _pack(
        tmp_path,
        "project-compatible",
        {"End/Content/GameContents/DataObject/Resident/Item.uasset": b"project"},
        built,
    )
    status = deploy_built_pak(game, built)
    assert status["managed"] is True
    assert _sha(external) == external_sha

    removed = remove_deployed_pak(game)
    assert removed["removed"] is True
    assert not deployed_pak_path(game).exists()
    assert external.is_file()
    assert _sha(external) == external_sha

def test_mod_library_recovers_interrupted_owned_deployment(monkeypatch, tmp_path):
    _install_repak(monkeypatch, tmp_path)
    game = _game(tmp_path)
    recoverable = _pack(
        tmp_path,
        "recoverable",
        {"End/Content/GameContents/DataObject/Resident/Item.uasset": b"recoverable"},
    ).parent
    adapter = PakModAdapter()
    plan = adapter.activate([recoverable], game)

    destination = Path(plan["destination"])
    deployed = destination / "recoverable_P.pak"
    deployed_sha = _sha(deployed)
    deployment_bytes = (destination / "deployment.json").read_bytes()
    backup = destination.parent / ".LexeditorLibrary-recovery"

    destination.rename(backup)
    assert not destination.exists()
    assert backup.is_dir()

    adapter.recover(game)

    restored = destination / "recoverable_P.pak"
    assert destination.is_dir()
    assert not backup.exists()
    assert _sha(restored) == deployed_sha
    assert (destination / "deployment.json").read_bytes() == deployment_bytes
    assert adapter.active_mod_ids(game) == ["recoverable"]

