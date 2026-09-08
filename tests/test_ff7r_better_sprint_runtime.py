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


def _write_manifest(project: Path, *, better_sprint=None):
    hooks = {
        "cutsceneSpeed": True,
        "minimapTapHold": True,
        "minimapState": True,
    }
    if better_sprint is not None:
        hooks["betterSprint"] = better_sprint
    runtime = project / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifestVersion": 1,
        "hooks": hooks,
        "supportedExeTimestamps": [FIXTURE_TIMESTAMP],
        "notes": "synthetic Better Sprint fixture",
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


def test_better_sprint_defaults_to_vanilla_one_x_and_old_configs_upgrade_in_memory(tmp_path):
    defaults = load_runtime_config(tmp_path)
    assert defaults["betterSprint"] == {"enabled": False, "speedMultiplier": 1.0}

    old_config = {
        "schemaVersion": 1,
        "cutsceneSpeed": dict(DEFAULT_RUNTIME_CONFIG["cutsceneSpeed"]),
        "minimap": dict(DEFAULT_RUNTIME_CONFIG["minimap"]),
        "hpRebalance": dict(DEFAULT_RUNTIME_CONFIG["hpRebalance"]),
    }
    validated = validate_runtime_config(old_config)
    assert validated["betterSprint"] == {"enabled": False, "speedMultiplier": 1.0}


def test_sprint_multiplier_accepts_above_and_below_vanilla_but_rejects_nonpositive_or_nonfinite():
    for valid in (0.5, 1.0, 1.5, 3.0):
        value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
        value["betterSprint"].update(enabled=True, speedMultiplier=valid)
        assert validate_runtime_config(value)["betterSprint"]["speedMultiplier"] == valid

    for invalid in (0, -0.5, float("inf"), float("nan"), True):
        value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
        value["betterSprint"]["speedMultiplier"] = invalid
        with pytest.raises(ValueError):
            validate_runtime_config(value)


def test_better_sprint_is_editable_through_runtime_game_data_surface(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    package, source_sha, using_project = runtime_settings_package(game, project)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    properties = {prop["name"]: prop for prop in payload["properties"]}
    values = payload["records"][0]["values"]

    assert properties["BetterSprintEnabled"]["editable"] is True
    assert properties["SprintSpeedMultiplier"]["type"] == "FLOAT"
    assert values["BetterSprintEnabled"] is False
    assert values["SprintSpeedMultiplier"] == 1.0
    assert properties["BetterSprintHookValidated"]["editable"] is False

    result = save_runtime_edits(
        project,
        source_sha256=payload["sourceSha256"],
        active_sha256=payload["activeSha256"],
        edits=[
            {"entry": 0, "property": "BetterSprintEnabled", "value": True},
            {"entry": 0, "property": "SprintSpeedMultiplier", "value": 1.35},
        ],
    )
    saved = load_runtime_config(project)
    assert result["saved"] == 2
    assert saved["betterSprint"] == {"enabled": True, "speedMultiplier": 1.35}


def test_better_sprint_enabled_blocks_runtime_until_optional_hook_is_validated(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _ready_runtime_files(game, project)

    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["betterSprint"]["enabled"] = True
    config["betterSprint"]["speedMultiplier"] = 1.5
    save_runtime_config(project, config)
    _write_manifest(project)

    status = runtime_status(game, project)
    assert status["hooksValidated"] is True
    assert status["betterSprintRequested"] is True
    assert status["betterSprintHookValidated"] is False
    assert status["requestedHooksValidated"] is False
    assert status["runtimeReady"] is False
    with pytest.raises(RuntimeError, match="requested runtime hooks are not validated: betterSprint"):
        deploy_runtime(game, project)

    _write_manifest(project, better_sprint=True)
    status = runtime_status(game, project)
    assert status["betterSprintHookValidated"] is True
    assert status["requestedHooksValidated"] is True
    assert status["runtimeReady"] is True


def test_manifest_accepts_better_sprint_as_supported_optional_hook_and_rejects_unknown_hooks():
    payload = {
        "manifestVersion": 1,
        "hooks": {
            "cutsceneSpeed": True,
            "minimapTapHold": True,
            "minimapState": True,
            "betterSprint": True,
        },
        "supportedExeTimestamps": [FIXTURE_TIMESTAMP],
        "notes": "validated sprint hook",
    }
    validated = validate_runtime_manifest(payload)
    assert validated["hooks"]["betterSprint"] is True

    payload["hooks"]["notARealHook"] = True
    with pytest.raises(ValueError, match="supported optional hooks"):
        validate_runtime_manifest(payload)


def test_native_probe_includes_sprint_research_needles():
    assert "DashRootMotionTranslationScale" in DEFAULT_NEEDLES
    assert "RunToDashBlendInputThreshold" in DEFAULT_NEEDLES
