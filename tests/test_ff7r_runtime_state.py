import json
from pathlib import Path

import pytest

from games.ff7r.atb_tweaks import DEFAULT_ATB_CONFIG, save_atb_config
from games.ff7r.runtime_config import DEFAULT_RUNTIME_CONFIG, save_runtime_config
from games.ff7r import runtime_state


def _base_status():
    return {
        "projectDllPresent": True,
        "deployedDllPresent": True,
        "loaderCandidatePresent": True,
        "buildSupported": True,
        "requestedHooksValidated": True,
        "installedExeTimestamp": 0x12345678,
        "active": True,
        "notes": "deployment candidate",
    }


def test_requested_features_include_only_enabled_runtime_behaviors(tmp_path):
    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["cutsceneSpeed"]["enabled"] = True
    config["minimap"]["enabled"] = True
    config["hpRebalance"]["enabled"] = True
    save_runtime_config(tmp_path, config)

    atb = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    atb.update(enabled=True, movementMultiplier=0.5, rollReduction=125.0)
    save_atb_config(tmp_path, atb)

    assert runtime_state.requested_runtime_features(tmp_path) == [
        "cutsceneSpeed", "minimapTapHold", "minimapState", "hpRebalance", "atbTweaks",
    ]


def test_data_only_atb_overrides_do_not_request_native_atb_hook(tmp_path):
    atb = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    atb["enabled"] = True
    atb["residentOverrides"] = {"ATB_Player|ParamFloat": 1.5}
    save_atb_config(tmp_path, atb)
    assert "atbTweaks" not in runtime_state.requested_runtime_features(tmp_path)


def test_public_runtime_active_is_false_without_live_heartbeat_even_if_files_look_active(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_state, "deployment_status", lambda *_args: _base_status())
    monkeypatch.setattr(runtime_state, "load_runtime_status", lambda *_args: None)
    monkeypatch.setattr(runtime_state, "_requested_manifest_hooks_valid", lambda *_args: True)

    status = runtime_state.runtime_status(tmp_path / "game", tmp_path / "project")
    assert status["deploymentCandidateActive"] is True
    assert status["heartbeatPresent"] is False
    assert status["runtimeLoaded"] is False
    assert status["active"] is False


def test_public_runtime_active_requires_requested_features_in_heartbeat(monkeypatch, tmp_path):
    project = tmp_path / "project"
    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["cutsceneSpeed"]["enabled"] = True
    save_runtime_config(project, config)

    monkeypatch.setattr(runtime_state, "deployment_status", lambda *_args: _base_status())
    monkeypatch.setattr(runtime_state, "_requested_manifest_hooks_valid", lambda *_args: True)
    monkeypatch.setattr(runtime_state, "load_runtime_status", lambda *_args: {
        "statusVersion": 1,
        "processId": 222,
        "exeTimestamp": 0x12345678,
        "loaded": True,
        "features": {"cutsceneSpeed": False},
        "notes": "loaded but hook inactive",
    })
    monkeypatch.setattr(
        runtime_state,
        "runtime_activation_state",
        lambda _status, *, installed_timestamp, requested_features: {
            "heartbeatPresent": True,
            "runtimeProcessAlive": True,
            "runtimeLoaded": True,
            "heartbeatTimestampMatches": installed_timestamp == 0x12345678,
            "activeFeatures": [],
            "requestedFeaturesActive": False,
        },
    )
    status = runtime_state.runtime_status(tmp_path / "game", project)
    assert status["requestedRuntimeFeatures"] == ["cutsceneSpeed"]
    assert status["runtimeLoaded"] is True
    assert status["active"] is False


def test_deploy_wrapper_rejects_requested_feature_missing_from_manifest(monkeypatch, tmp_path):
    project = tmp_path / "project"
    config = json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))
    config["cutsceneSpeed"]["enabled"] = True
    save_runtime_config(project, config)
    monkeypatch.setattr(runtime_state, "load_runtime_manifest", lambda *_args: {
        "hooks": {"cutsceneSpeed": False},
    })
    with pytest.raises(RuntimeError, match="cutsceneSpeed"):
        runtime_state.deploy_runtime(tmp_path / "game", project)


def test_deploy_wrapper_clears_stale_heartbeat_and_never_returns_active(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    monkeypatch.setattr(runtime_state, "_requested_manifest_hooks_valid", lambda *_args: True)
    monkeypatch.setattr(runtime_state, "deploy_runtime_files", lambda *_args: {"dll": "fixture"})
    target = game / "NativeMods" / "LexeditorFF7RRuntime.status.json"
    target.parent.mkdir(parents=True)
    target.write_text("stale", encoding="utf-8")

    result = runtime_state.deploy_runtime(game, project)
    assert result["active"] is False
    assert not target.exists()
