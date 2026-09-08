import json
from pathlib import Path
import struct

import pytest

from games.ff7r.runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    RUNTIME_CONFIG_NAME,
    RUNTIME_DLL_NAME,
    RUNTIME_MANIFEST_NAME,
    deploy_runtime,
    load_runtime_config,
    runtime_status,
    save_runtime_config,
    validate_runtime_config,
    validate_runtime_manifest,
)


FIXTURE_TIMESTAMP = 0x12345678


def write_fixture_exe(game: Path, timestamp: int = FIXTURE_TIMESTAMP):
    target = game / "End" / "Binaries" / "Win64" / "ff7remake_.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(0x200)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<I", data, 0x88, timestamp)
    target.write_bytes(data)
    return target


def write_manifest(project: Path, *, timestamp=FIXTURE_TIMESTAMP, hooks=None):
    runtime = project / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifestVersion": 1,
        "hooks": hooks or {
            "cutsceneSpeed": True,
            "minimapTapHold": True,
            "minimapState": True,
        },
        "supportedExeTimestamps": [f"0x{timestamp:08X}"],
        "notes": "synthetic validated fixture",
    }
    (runtime / RUNTIME_MANIFEST_NAME).write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_runtime_defaults_encode_requested_cutscene_and_minimap_contract(tmp_path):
    config = load_runtime_config(tmp_path)
    assert config["cutsceneSpeed"]["baseMultiplier"] > 1.0
    assert config["cutsceneSpeed"]["r2Behavior"] == "multiply-native"
    assert config["minimap"]["tapBehavior"] == "open-map"
    assert config["minimap"]["holdBehavior"] == "toggle-minimap"
    assert config["minimap"]["persistChosenState"] is True


def test_cutscene_multiplier_must_be_above_one_and_finite():
    for invalid in (1.0, 0.5, float("inf"), float("nan")):
        value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
        value["cutsceneSpeed"]["baseMultiplier"] = invalid
        with pytest.raises(ValueError):
            validate_runtime_config(value)


def test_minimap_hold_threshold_is_bounded():
    for invalid in (149, 1501, 350.5, True):
        value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
        value["minimap"]["holdMilliseconds"] = invalid
        with pytest.raises(ValueError):
            validate_runtime_config(value)


def test_runtime_config_save_is_atomic_and_round_trips(tmp_path):
    value = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    value["cutsceneSpeed"].update(enabled=True, baseMultiplier=1.75)
    value["minimap"].update(enabled=True, holdMilliseconds=420)
    saved = save_runtime_config(tmp_path, value)
    assert saved == load_runtime_config(tmp_path)
    assert saved["cutsceneSpeed"]["baseMultiplier"] == 1.75
    assert saved["minimap"]["holdMilliseconds"] == 420
    assert (tmp_path / "runtime" / RUNTIME_CONFIG_NAME).is_file()


def test_runtime_manifest_requires_every_hook_and_supported_build():
    with pytest.raises(ValueError, match="exactly the required"):
        validate_runtime_manifest({
            "manifestVersion": 1,
            "hooks": {"cutsceneSpeed": True},
            "supportedExeTimestamps": [FIXTURE_TIMESTAMP],
        })
    with pytest.raises(ValueError, match="at least one"):
        validate_runtime_manifest({
            "manifestVersion": 1,
            "hooks": {
                "cutsceneSpeed": True,
                "minimapTapHold": True,
                "minimapState": True,
            },
            "supportedExeTimestamps": [],
        })


def test_runtime_status_never_claims_active_without_dll_loader_manifest_and_supported_exe(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    status = runtime_status(game, project)
    assert status["runtimeReady"] is False
    assert status["active"] is False
    assert status["projectDllPresent"] is False
    assert status["loaderCandidatePresent"] is False
    assert status["manifestPresent"] is False
    assert status["hooksValidated"] is False
    assert status["buildSupported"] is False


def test_runtime_deploy_fails_closed_without_dll_loader_or_manifest(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    with pytest.raises(RuntimeError, match="native runtime DLL is not built"):
        deploy_runtime(game, project)

    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    with pytest.raises(RuntimeError, match="native loader proxy"):
        deploy_runtime(game, project)

    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")
    write_fixture_exe(game)
    with pytest.raises(RuntimeError, match="manifest is missing"):
        deploy_runtime(game, project)


def test_runtime_deploy_rejects_unvalidated_hook_and_wrong_exe_timestamp(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")
    write_fixture_exe(game)

    write_manifest(project, hooks={
        "cutsceneSpeed": False,
        "minimapTapHold": True,
        "minimapState": True,
    })
    with pytest.raises(RuntimeError, match="not all validated"):
        deploy_runtime(game, project)

    write_manifest(project, timestamp=0xDEADBEEF)
    with pytest.raises(RuntimeError, match="not validated for installed executable timestamp"):
        deploy_runtime(game, project)


def test_runtime_deploy_copies_dll_config_and_manifest_only_for_validated_build(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")
    write_fixture_exe(game)
    write_manifest(project)

    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["cutsceneSpeed"].update(enabled=True, baseMultiplier=1.5)
    config["minimap"].update(enabled=True, holdMilliseconds=300)
    save_runtime_config(project, config)

    result = deploy_runtime(game, project)
    assert Path(result["dll"]).read_bytes() == b"fixture-runtime"
    assert json.loads(Path(result["config"]).read_text(encoding="utf-8"))["minimap"]["enabled"] is True
    assert json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))["hooks"]["minimapState"] is True
    assert result["exeTimestamp"] == FIXTURE_TIMESTAMP
    status = runtime_status(game, project)
    assert status["hooksValidated"] is True
    assert status["buildSupported"] is True
    assert status["runtimeReady"] is True
    assert status["active"] is True
