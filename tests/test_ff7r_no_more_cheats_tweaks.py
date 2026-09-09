from __future__ import annotations

import struct

import pytest

from games.ff7r.dataobject import DataObjectPackage, parse_uasset
from games.ff7r.dataobject_structural import append_array_element
from games.ff7r.no_more_cheats_tweaks import (
    EXPECTED_TARGET_KEYS,
    NO_MORE_CHEATS_ASSET,
    has_enabled_no_more_cheats,
    load_config,
    load_virtual_package,
    materialize_no_more_cheats,
    removal_plan,
    save_config,
    save_virtual_edits,
    validate_config,
)
from games.ff7r.plugin import _test_package


def _assessment(*, blocked: str | None = None):
    values = [10, 20, 30, 40]
    targets = []
    for index, key in enumerate(EXPECTED_TARGET_KEYS):
        actionable = key != blocked
        targets.append({
            "key": key,
            "label": key,
            "actionable": actionable,
            "reasonCodes": ["unique-exact-structural-owner"] if actionable else ["ambiguous-structural-owner"],
            "selector": ({
                "asset": "Fixture",
                "entryIndex": 0,
                "record": "RowA",
                "property": "Values_Array",
                "index": index,
                "typeCode": 3,
                "matchedTextIds": [str(values[index])],
                "fixedWidthDeleteSupported": True,
                "menuControlEvidence": True,
                "controlFields": ["MenuMode"],
            } if actionable else None),
        })
    return {
        "allTargetsActionable": blocked is None,
        "targets": targets,
        "scanErrors": [],
        "notes": ["synthetic ownership fixture"],
    }


def _report():
    return {
        "language": "US",
        "targets": [],
        "assetCoverage": [],
        "textResourcesScanned": 1,
        "dataObjectsScanned": 1,
        "scanErrors": [],
        "notes": ["synthetic report"],
    }


def _source_pair(tmp_path):
    uasset, uexp = _test_package()
    header = parse_uasset(uasset)
    realistic_uasset = bytearray(uasset)
    struct.pack_into("<q", realistic_uasset, header.serial_size_offset, len(uexp))
    package = DataObjectPackage.from_bytes(bytes(realistic_uasset), uexp, asset="Fixture")
    append_array_element(package, 0, "Values_Array", 40)
    assert package.entries[0].values["Values_Array"] == [10, 20, 30, 40]
    root = tmp_path / "source"
    uasset_path = root / "Fixture.uasset"
    uexp_path = root / "Fixture.uexp"
    package.write_pair(uasset_path, uexp_path)
    return uasset_path, uexp_path


def test_config_defaults_and_strict_validation(tmp_path):
    assert load_config(tmp_path) == {"schemaVersion": 1, "enabled": False}
    assert save_config(tmp_path, {"enabled": True}) == {"schemaVersion": 1, "enabled": True}
    assert has_enabled_no_more_cheats(tmp_path) is True
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_config({"enabled": False, "mystery": 1})
    with pytest.raises(ValueError, match="must be boolean"):
        validate_config({"enabled": 1})


def test_removal_plan_requires_all_four_and_deletes_same_array_high_to_low():
    plan = removal_plan(_assessment())
    assert [row["key"] for row in plan] == list(reversed(EXPECTED_TARGET_KEYS))
    assert [row["index"] for row in plan] == [3, 2, 1, 0]

    with pytest.raises(RuntimeError, match="not fully validated"):
        removal_plan(_assessment(blocked="giftBox"))


def test_removal_plan_rejects_duplicate_structural_selector():
    assessment = _assessment()
    assessment["targets"][1]["selector"] = dict(assessment["targets"][0]["selector"])
    with pytest.raises(RuntimeError, match="same structural array element"):
        removal_plan(assessment)


def test_virtual_surface_exposes_enable_and_fail_closed_status(tmp_path, monkeypatch):
    import games.ff7r.no_more_cheats_tweaks as module

    assessment = _assessment(blocked="easyMode")
    monkeypatch.setattr(module, "collect_report", lambda *args, **kwargs: _report())
    monkeypatch.setattr(module, "assess_menu_candidate_removals", lambda report: assessment)
    package, source_sha, using_project = load_virtual_package(
        tmp_path, tmp_path, tmp_path, {})
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    values = payload["records"][0]["values"]
    assert payload["asset"] == NO_MORE_CHEATS_ASSET
    assert values["Enabled"] is False
    assert values["AllTargetsActionable"] is False
    assert values["FastStartReady"] is True
    assert values["EasyModeReady"] is False
    assert "BLOCKED" in values["EasyModeStatus"]


def test_virtual_save_round_trip_is_config_only(tmp_path, monkeypatch):
    import games.ff7r.no_more_cheats_tweaks as module

    assessment = _assessment()
    monkeypatch.setattr(module, "collect_report", lambda *args, **kwargs: _report())
    monkeypatch.setattr(module, "assess_menu_candidate_removals", lambda report: assessment)
    package, source_sha, using_project = load_virtual_package(
        tmp_path, tmp_path, tmp_path, {})
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    result = save_virtual_edits(
        tmp_path, tmp_path, tmp_path, {},
        source_sha256=payload["sourceSha256"],
        active_sha256=payload["activeSha256"],
        edits=[{"entry": 0, "property": "Enabled", "value": True}],
    )
    assert result["enabled"] is True
    assert load_config(tmp_path)["enabled"] is True
    assert not (tmp_path / "content").exists()


def test_materializer_deletes_all_four_proved_entries_in_staging_only(tmp_path, monkeypatch):
    import games.ff7r.archive as archive
    import games.ff7r.no_more_cheats_tweaks as module

    source_uasset, source_uexp = _source_pair(tmp_path)
    assessment = _assessment()
    save_config(tmp_path / "project", {"enabled": True})
    monkeypatch.setattr(module, "collect_report", lambda *args, **kwargs: _report())
    monkeypatch.setattr(module, "assess_menu_candidate_removals", lambda report: assessment)
    monkeypatch.setattr(archive, "extract_pair", lambda *args, **kwargs: (source_uasset, source_uexp))

    staging = tmp_path / "staging"
    result = materialize_no_more_cheats(
        tmp_path, tmp_path, tmp_path / "project", {}, staging)
    assert {row["key"] for row in result} == set(EXPECTED_TARGET_KEYS)

    staged = DataObjectPackage(
        staging / "Fixture.uasset", staging / "Fixture.uexp", asset="Fixture")
    assert staged.entries[0].values["Values_Array"] == []
    original = DataObjectPackage(source_uasset, source_uexp, asset="Fixture")
    assert original.entries[0].values["Values_Array"] == [10, 20, 30, 40]


def test_materializer_refuses_any_blocked_target(tmp_path, monkeypatch):
    import games.ff7r.no_more_cheats_tweaks as module

    save_config(tmp_path / "project", {"enabled": True})
    monkeypatch.setattr(module, "collect_report", lambda *args, **kwargs: _report())
    monkeypatch.setattr(
        module, "assess_menu_candidate_removals", lambda report: _assessment(blocked="streamlinedProgression"))
    with pytest.raises(RuntimeError, match="not fully validated"):
        materialize_no_more_cheats(
            tmp_path, tmp_path, tmp_path / "project", {}, tmp_path / "staging")
