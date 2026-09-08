import json

import pytest

from games.ff7r.runtime_heartbeat import (
    KNOWN_FEATURES,
    RUNTIME_STATUS_NAME,
    load_runtime_status,
    runtime_activation_state,
    status_path,
    validate_runtime_status,
)


def _status(**overrides):
    value = {
        "statusVersion": 1,
        "processId": 1234,
        "exeTimestamp": 0x12345678,
        "loaded": True,
        "features": {
            "cutsceneSpeed": True,
            "minimapTapHold": True,
            "minimapState": True,
        },
        "notes": "fixture",
    }
    value.update(overrides)
    return value


def test_runtime_status_path_lives_next_to_native_mods_runtime(tmp_path):
    assert status_path(tmp_path) == tmp_path / "NativeMods" / RUNTIME_STATUS_NAME


def test_runtime_status_validation_expands_missing_known_features_to_false():
    value = validate_runtime_status(_status())
    assert value["features"]["cutsceneSpeed"] is True
    assert value["features"]["hpRebalance"] is False
    assert value["features"]["atbTweaks"] is False
    assert set(value["features"]) == KNOWN_FEATURES


def test_runtime_status_rejects_unknown_features_and_invalid_process_identity():
    value = _status()
    value["features"]["madeUpHook"] = True
    with pytest.raises(ValueError, match="unsupported"):
        validate_runtime_status(value)

    with pytest.raises(ValueError, match="positive integer"):
        validate_runtime_status(_status(processId=0))
    with pytest.raises(ValueError, match="PE timestamp"):
        validate_runtime_status(_status(exeTimestamp=-1))


def test_activation_requires_live_matching_process_and_every_requested_feature():
    value = _status()
    active = runtime_activation_state(
        value,
        installed_timestamp=0x12345678,
        requested_features=["cutsceneSpeed", "minimapTapHold", "minimapState"],
        alive=lambda pid: pid == 1234,
    )
    assert active["runtimeLoaded"] is True
    assert active["requestedFeaturesActive"] is True

    dead = runtime_activation_state(
        value,
        installed_timestamp=0x12345678,
        requested_features=["cutsceneSpeed"],
        alive=lambda _pid: False,
    )
    assert dead["runtimeProcessAlive"] is False
    assert dead["runtimeLoaded"] is False
    assert dead["requestedFeaturesActive"] is False

    stale = runtime_activation_state(
        value,
        installed_timestamp=0x87654321,
        requested_features=["cutsceneSpeed"],
        alive=lambda _pid: True,
    )
    assert stale["heartbeatTimestampMatches"] is False
    assert stale["runtimeLoaded"] is False

    missing = runtime_activation_state(
        value,
        installed_timestamp=0x12345678,
        requested_features=["hpRebalance"],
        alive=lambda _pid: True,
    )
    assert missing["runtimeLoaded"] is True
    assert missing["requestedFeaturesActive"] is False


def test_no_heartbeat_never_counts_as_loaded_even_with_no_requested_features():
    result = runtime_activation_state(
        None,
        installed_timestamp=0x12345678,
        requested_features=[],
        alive=lambda _pid: True,
    )
    assert result["heartbeatPresent"] is False
    assert result["runtimeLoaded"] is False
    assert result["requestedFeaturesActive"] is False


def test_runtime_status_file_round_trips(tmp_path):
    target = status_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(_status()), encoding="utf-8")
    loaded = load_runtime_status(tmp_path)
    assert loaded["processId"] == 1234
    assert loaded["exeTimestamp"] == 0x12345678
