import json
from pathlib import Path
import struct

import pytest

from games.ff7r.native_probe import DEFAULT_NEEDLES
from games.ff7r.runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    RUNTIME_DLL_NAME,
    RUNTIME_MANIFEST_NAME,
    deploy_runtime,
    load_runtime_config,
    runtime_status,
    save_runtime_config,
    validate_runtime_config,
    validate_runtime_manifest,
)
from games.ff7r.runtime_dataobject import runtime_settings_package, save_runtime_edits


FIXTURE_TIMESTAMP = 0x12345678


def _write_fixture_exe(game: Path):
    target = game / "End" / "Binaries" / "Win64" / "ff7remake_.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(0x200)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<I", data, 0x88, FIXTURE_TIMESTAMP)
    target.write_bytes(data)
    return target


def _write_manifest(project: Path, *, hp_rebalance=None):
    hooks = {
        "cutsceneSpeed": True,
        "minimapTapHold": True,
        "minimapState": True,
    }
    if hp_rebalance is not None:
        hooks["hpRebalance"] = hp_rebalance
    runtime = project / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifestVersion": 1,
        "hooks": hooks,
        "supportedExeTimestamps": [FIXTURE_TIMESTAMP],
        "notes": "synthetic HP Rebalance fixture",
    }
    (runtime / RUNTIME_MANIFEST_NAME).write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _ready_runtime_files(game: Path, project: Path):
    runtime = project / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True, exist_ok=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")
    _write_fixture_exe(game)


def test_hp_rebalance_defaults_to_half_party_hp_and_old_configs_upgrade_in_memory(tmp_path):
    defaults = load_runtime_config(tmp_path)
    assert defaults["hpRebalance"] == {"enabled": False, "hpMultiplier": 0.5}

    old_config = {
        "schemaVersion": 1,
        "cutsceneSpeed": dict(DEFAULT_RUNTIME_CONFIG["cutsceneSpeed"]),
        "minimap": dict(DEFAULT_RUNTIME_CONFIG["minimap"]),
    }
    validated = validate_runtime_config(old_config)
    assert validated["hpRebalance"] == {"enabled": False, "hpMultiplier": 0.5}


def test_hp_multiplier_accepts_one_as_vanilla_and_rejects_nonpositive_or_nonfinite():
    value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    value["hpRebalance"].update(enabled=True, hpMultiplier=1.0)
    assert validate_runtime_config(value)["hpRebalance"]["hpMultiplier"] == 1.0

    for invalid in (0, -0.5, float("inf"), float("nan"), True):
        value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
        value["hpRebalance"]["hpMultiplier"] = invalid
        with pytest.raises(ValueError):
            validate_runtime_config(value)


def test_hp_rebalance_is_editable_through_runtime_game_data_surface(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    package, source_sha, using_project = runtime_settings_package(game, project)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    properties = {prop["name"]: prop for prop in payload["properties"]}
    values = payload["records"][0]["values"]

    assert properties["HPRebalanceEnabled"]["editable"] is True
    assert properties["HPMultiplier"]["type"] == "FLOAT"
    assert values["HPRebalanceEnabled"] is False
    assert values["HPMultiplier"] == 0.5
    assert properties["HPRebalanceHookValidated"]["editable"] is False

    result = save_runtime_edits(
        project,
        source_sha256=payload["sourceSha256"],
        active_sha256=payload["activeSha256"],
        edits=[
            {"entry": 0, "property": "HPRebalanceEnabled", "value": True},
            {"entry": 0, "property": "HPMultiplier", "value": 0.65},
        ],
    )
    saved = load_runtime_config(project)
    assert result["saved"] == 2
    assert saved["hpRebalance"] == {"enabled": True, "hpMultiplier": 0.65}


def test_hp_rebalance_enabled_blocks_runtime_until_optional_hook_is_validated(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _ready_runtime_files(game, project)

    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["hpRebalance"]["enabled"] = True
    save_runtime_config(project, config)
    _write_manifest(project)

    status = runtime_status(game, project)
    assert status["hooksValidated"] is True
    assert status["hpRebalanceRequested"] is True
    assert status["hpRebalanceHookValidated"] is False
    assert status["requestedHooksValidated"] is False
    assert status["runtimeReady"] is False
    with pytest.raises(RuntimeError, match="HP Rebalance hook is enabled but not validated"):
        deploy_runtime(game, project)

    _write_manifest(project, hp_rebalance=True)
    status = runtime_status(game, project)
    assert status["hpRebalanceHookValidated"] is True
    assert status["requestedHooksValidated"] is True
    assert status["runtimeReady"] is True


def test_runtime_manifest_accepts_hp_rebalance_only_as_supported_optional_hook():
    payload = _write_manifest_payload = {
        "manifestVersion": 1,
        "hooks": {
            "cutsceneSpeed": True,
            "minimapTapHold": True,
            "minimapState": True,
            "hpRebalance": True,
        },
        "supportedExeTimestamps": [FIXTURE_TIMESTAMP],
        "notes": "validated HP hook",
    }
    validated = validate_runtime_manifest(payload)
    assert validated["hooks"]["hpRebalance"] is True

    payload["hooks"]["madeUpHook"] = True
    with pytest.raises(ValueError, match="supported optional hooks"):
        validate_runtime_manifest(payload)


def test_native_probe_includes_player_max_hp_api_research_needle():
    assert "BPSetPlayerHPMax" in DEFAULT_NEEDLES
