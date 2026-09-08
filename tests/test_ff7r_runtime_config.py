import json
from pathlib import Path

import pytest

from games.ff7r.runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    RUNTIME_CONFIG_NAME,
    RUNTIME_DLL_NAME,
    deploy_runtime,
    load_runtime_config,
    runtime_status,
    save_runtime_config,
    validate_runtime_config,
)


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


def test_runtime_status_never_claims_active_without_native_dll_and_loader(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    status = runtime_status(game, project)
    assert status["runtimeReady"] is False
    assert status["active"] is False
    assert status["projectDllPresent"] is False
    assert status["loaderCandidatePresent"] is False


def test_runtime_deploy_fails_closed_without_dll_or_loader(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    with pytest.raises(RuntimeError, match="native runtime DLL is not built"):
        deploy_runtime(game, project)

    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    with pytest.raises(RuntimeError, match="native loader proxy"):
        deploy_runtime(game, project)


def test_runtime_deploy_copies_dll_and_validated_config_when_loader_exists(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")

    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["cutsceneSpeed"].update(enabled=True, baseMultiplier=1.5)
    config["minimap"].update(enabled=True, holdMilliseconds=300)
    save_runtime_config(project, config)

    result = deploy_runtime(game, project)
    assert Path(result["dll"]).read_bytes() == b"fixture-runtime"
    assert json.loads(Path(result["config"]).read_text(encoding="utf-8"))["minimap"]["enabled"] is True
    status = runtime_status(game, project)
    assert status["runtimeReady"] is True
    assert status["active"] is True
