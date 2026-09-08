import json
from pathlib import Path

import pytest

from games.ff7r.runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    RUNTIME_CONFIG_NAME,
    RUNTIME_DLL_NAME,
    RUNTIME_PROBE_REPORT_NAME,
    deploy_runtime,
    load_runtime_config,
    runtime_probe_status,
    runtime_status,
    save_runtime_config,
    validate_probe_report,
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
    assert status["probe"]["reportPresent"] is False


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


def _probe_report(*, map_matches=None, input_matches=None):
    return {
        "schemaVersion": 1,
        "probeOnly": True,
        "process": r"C:\Games\FF7R\End\Binaries\Win64\ff7remake_.exe",
        "processSize": 123456789,
        "textBase": "0x140001000",
        "textSize": 987654,
        "probes": [
            {"name": "knownMapControl", "matches": map_matches or ["0x1518D175"]},
            {"name": "knownRawInputRegistration", "matches": input_matches or ["0x15D0F290"]},
            {"name": "ascii:EventScene", "matches": ["0x145000000"]},
        ],
    }


def test_probe_report_requires_probe_only_schema_and_hex_addresses():
    report = _probe_report()
    assert validate_probe_report(report)["probeOnly"] is True

    bad = _probe_report()
    bad["probeOnly"] = False
    with pytest.raises(ValueError, match="probeOnly"):
        validate_probe_report(bad)

    bad = _probe_report()
    bad["probes"][0]["matches"] = ["not-an-address"]
    with pytest.raises(ValueError, match="address"):
        validate_probe_report(bad)


def test_probe_status_requires_unique_known_current_build_signatures(tmp_path):
    game = tmp_path / "game"
    native_mods = game / "NativeMods"
    native_mods.mkdir(parents=True)
    target = native_mods / RUNTIME_PROBE_REPORT_NAME
    target.write_text(json.dumps(_probe_report()), encoding="utf-8")

    status = runtime_probe_status(game)
    assert status["valid"] is True
    assert status["baselineCompatible"] is True
    assert status["knownMapControlMatches"] == ["0x1518D175"]
    assert status["candidateRuntimeStrings"]["EventScene"] == ["0x145000000"]

    target.write_text(
        json.dumps(_probe_report(map_matches=["0x1518D175", "0x1518D200"])),
        encoding="utf-8",
    )
    status = runtime_probe_status(game)
    assert status["valid"] is True
    assert status["baselineCompatible"] is False
    assert "do not apply runtime patches" in status["reason"]


def test_probe_status_fails_closed_on_malformed_report(tmp_path):
    game = tmp_path / "game"
    native_mods = game / "NativeMods"
    native_mods.mkdir(parents=True)
    target = native_mods / RUNTIME_PROBE_REPORT_NAME
    target.write_text("{broken", encoding="utf-8")
    status = runtime_probe_status(game)
    assert status["reportPresent"] is True
    assert status["valid"] is False
    assert status["baselineCompatible"] is False
