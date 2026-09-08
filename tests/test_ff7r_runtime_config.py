import json
from pathlib import Path
import struct

import pytest

from games.ff7r.archive import _with_virtual_assets
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
from games.ff7r.runtime_dataobject import (
    NO_MORE_CHEATS_PROBE_ASSET,
    RUNTIME_PROBE_ASSET,
    RUNTIME_TWEAKS_ASSET,
    runtime_settings_package,
    save_runtime_edits,
)
from games.ff7r.storage import save_edits


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

    manifest = validate_runtime_manifest({
        "manifestVersion": 1,
        "hooks": {
            "cutsceneSpeed": False,
            "minimapTapHold": False,
            "minimapState": False,
            "atbTweaks": True,
        },
        "supportedExeTimestamps": [FIXTURE_TIMESTAMP],
    })
    assert manifest["hooks"]["atbTweaks"] is True


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


def test_runtime_deploy_rejects_unvalidated_requested_hook_and_wrong_exe_timestamp(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")
    write_fixture_exe(game)

    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["cutsceneSpeed"]["enabled"] = True
    save_runtime_config(project, config)
    write_manifest(project, hooks={
        "cutsceneSpeed": False,
        "minimapTapHold": True,
        "minimapState": True,
    })
    with pytest.raises(RuntimeError, match="requested runtime hooks are not validated: cutsceneSpeed"):
        deploy_runtime(game, project)

    write_manifest(project, timestamp=0xDEADBEEF)
    with pytest.raises(RuntimeError, match="not validated for installed executable timestamp"):
        deploy_runtime(game, project)


def test_runtime_deploy_allows_validated_hp_without_unrequested_core_hooks(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    (runtime / RUNTIME_DLL_NAME).write_bytes(b"fixture-runtime")
    binaries = game / "End" / "Binaries" / "Win64"
    binaries.mkdir(parents=True)
    (binaries / "dxgi.dll").write_bytes(b"fixture-proxy")
    write_fixture_exe(game)

    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["hpRebalance"]["enabled"] = True
    save_runtime_config(project, config)
    write_manifest(project, hooks={
        "cutsceneSpeed": False,
        "minimapTapHold": False,
        "minimapState": False,
        "hpRebalance": True,
    })

    status = runtime_status(game, project)
    assert status["hooksValidated"] is False
    assert status["requestedHooks"] == ["hpRebalance"]
    assert status["missingRequestedHooks"] == []
    assert status["requestedHooksValidated"] is True
    assert status["runtimeReady"] is True

    result = deploy_runtime(game, project)
    assert Path(result["dll"]).read_bytes() == b"fixture-runtime"
    assert result["validation"]["hooks"]["hpRebalance"] is True


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


def test_virtual_runtime_resources_are_catalogued_without_polluting_cached_assets():
    base = {
        "schema": 2,
        "assets": [{"asset": "End/Content/GameContents/DataObject/Item", "name": "Item", "group": "DataObject"}],
        "textAssets": [],
    }
    decorated = _with_virtual_assets(base)
    assert [row["asset"] for row in decorated["assets"]][-3:] == [
        RUNTIME_TWEAKS_ASSET, RUNTIME_PROBE_ASSET, NO_MORE_CHEATS_PROBE_ASSET,
    ]
    assert len(base["assets"]) == 1
    assert len(_with_virtual_assets(decorated)["assets"]) == len(decorated["assets"])


def test_runtime_tweaks_are_editable_through_standard_game_data_contract(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    package, source_sha, using_project = runtime_settings_package(game, project)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    properties = {prop["name"]: prop for prop in payload["properties"]}
    assert properties["CutsceneEnabled"]["editable"] is True
    assert properties["CutsceneBaseMultiplier"]["type"] == "FLOAT"
    assert properties["MinimapHoldMilliseconds"]["min"] == 150
    assert properties["MinimapHoldMilliseconds"]["max"] == 1500
    assert properties["RuntimeReady"]["editable"] is False
    assert payload["records"][0]["values"]["HooksValidated"] is False

    result = save_runtime_edits(
        project,
        source_sha256=payload["sourceSha256"],
        active_sha256=payload["activeSha256"],
        edits=[
            {"entry": 0, "property": "CutsceneEnabled", "value": True},
            {"entry": 0, "property": "CutsceneBaseMultiplier", "value": 1.75},
            {"entry": 0, "property": "MinimapEnabled", "value": True},
            {"entry": 0, "property": "MinimapHoldMilliseconds", "value": 420},
        ],
    )
    saved = load_runtime_config(project)
    assert result["saved"] == 4
    assert saved["cutsceneSpeed"] == {
        "enabled": True,
        "baseMultiplier": 1.75,
        "r2Behavior": "multiply-native",
    }
    assert saved["minimap"]["enabled"] is True
    assert saved["minimap"]["holdMilliseconds"] == 420


def test_runtime_tweaks_reject_stale_or_read_only_generic_edits(tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    package, source_sha, using_project = runtime_settings_package(game, project)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)

    with pytest.raises(ValueError, match="read-only or unknown"):
        save_runtime_edits(
            project,
            source_sha256=source_sha,
            active_sha256=payload["activeSha256"],
            edits=[{"entry": 0, "property": "RuntimeReady", "value": True}],
        )

    save_runtime_config(project, {
        **DEFAULT_RUNTIME_CONFIG,
        "cutsceneSpeed": {**DEFAULT_RUNTIME_CONFIG["cutsceneSpeed"], "baseMultiplier": 1.5},
    })
    with pytest.raises(RuntimeError, match="changed on disk"):
        save_runtime_edits(
            project,
            source_sha256=source_sha,
            active_sha256=payload["activeSha256"],
            edits=[{"entry": 0, "property": "CutsceneEnabled", "value": True}],
        )


def test_native_hook_probe_virtual_resource_is_read_only(tmp_path):
    with pytest.raises(ValueError, match="read-only"):
        save_edits(
            tmp_path / "game",
            tmp_path / "data",
            tmp_path / "project",
            {},
            RUNTIME_PROBE_ASSET,
            source_sha256="unused",
            active_sha256="unused",
            edits=[{"entry": 0, "property": "HitCount", "value": 1}],
        )


def test_no_more_cheats_probe_virtual_resource_is_read_only(tmp_path):
    with pytest.raises(ValueError, match="read-only"):
        save_edits(
            tmp_path / "game",
            tmp_path / "data",
            tmp_path / "project",
            {},
            NO_MORE_CHEATS_PROBE_ASSET,
            source_sha256="unused",
            active_sha256="unused",
            edits=[{"entry": 0, "property": "TextMatchCount", "value": 1}],
        )
