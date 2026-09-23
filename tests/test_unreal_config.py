from __future__ import annotations

import os
from pathlib import Path

import pytest

import unreal_config
from unreal_config import (
    ConfigError,
    ExternalEditError,
    apply_settings,
    catalogue,
    discover_config_file,
    game_definition,
    managed_overrides,
    observed_values,
    read_document,
    refresh_snapshot,
    reset_all,
    setting,
    settings_for_game,
    status,
    use_game_default,
    validate_value,
)


@pytest.fixture()
def project(tmp_path, monkeypatch):
    game_ini = tmp_path / "Engine.ini"
    monkeypatch.setenv("LEXEDITOR_FF7R2_ENGINE_INI", str(game_ini))
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(tmp_path / "ff7r.ini"))
    return tmp_path / "project", game_ini


def test_catalogue_entries_carry_help_and_bounds():
    entries = catalogue()
    assert len(entries) >= 10
    for entry in entries:
        assert entry["name"] and entry["description"]
        assert entry["type"] in ("int", "float", "choice")
        assert isinstance(entry["restart_required"], bool)
        if entry["type"] == "choice":
            assert len(entry["choices"] or []) >= 2
        else:
            assert entry["minimum"] is not None and entry["maximum"] is not None
        for game_id, evidence in entry["verification"].items():
            assert {"defined", "accepted", "demonstrated", "tested_version"} <= set(evidence)
            if evidence["demonstrated"]:
                assert evidence["tested_version"], entry["key"]


def test_normal_view_holds_only_demonstrated_settings(project):
    root, _ini = project
    normal = settings_for_game("ff7r2")
    advanced = settings_for_game("ff7r2", include_unverified=True)
    assert all(item["verification"]["demonstrated"] for item in normal)
    assert len(advanced) >= len(normal) + 1
    assert all("unverified_note" in item for item in advanced if item not in normal)


def test_ff7r_markers_match_legacy_graphics_module():
    from plugins.ff7r import graphics_tweaks

    assert unreal_config.FF7R_MANAGED_BEGIN == graphics_tweaks.MANAGED_BEGIN
    assert unreal_config.FF7R_MANAGED_END == graphics_tweaks.MANAGED_END


def test_ff7r2_config_starts_undiscovered(project, monkeypatch):
    root, ini = project
    assert game_definition("ff7r2")["config_verified"] is False
    monkeypatch.delenv("LEXEDITOR_FF7R2_ENGINE_INI")
    monkeypatch.setattr("unreal_config._documents", lambda: Path("/nonexistent-lexeditor"))
    assert discover_config_file("ff7r2") is None
    report = status("ff7r2", root)
    assert report["configDiscovered"] is False
    assert "undiscovered" in report["notes"]


def test_discovery_prefers_env_override(project):
    root, ini = project
    ini.write_text("[SystemSettings]\n", encoding="utf-8")
    assert discover_config_file("ff7r2") == ini


def test_apply_preserves_unrelated_content_bom_and_endings(project):
    root, ini = project
    body = ("; user comment\n[SystemSettings]\r\nr.MotionBlurQuality=4\r\n"
            "\n[/Script/Engine.GameUserSettings]\nResolutionSizeX=2560\r\n")
    ini.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    report = apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    assert report["overrides"]["r.BloomQuality"] == "3"
    raw = ini.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "\r\n" in text
    assert "; user comment" in text
    assert "r.MotionBlurQuality=4" in text
    assert "ResolutionSizeX=2560" in text
    assert text.count("LEXEDITOR UNREAL CONFIG (ff7r2)") == 2


def test_reapply_stays_idempotent_and_last(project):
    root, ini = project
    apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    apply_settings("ff7r2", root, {"r.MotionBlurQuality": 0})
    text = ini.read_text(encoding="utf-8")
    assert text.count("BEGIN LEXEDITOR UNREAL CONFIG") == 1
    assert text.rstrip().endswith("END LEXEDITOR UNREAL CONFIG (ff7r2)")
    overrides = managed_overrides(read_document(ini), "ff7r2")
    assert overrides == {"r.BloomQuality": "3", "r.MotionBlurQuality": "0"}


def test_validation_rejects_bad_values(project):
    root, _ini = project
    with pytest.raises(ConfigError, match="whole number from 0 to 4"):
        apply_settings("ff7r2", root, {"r.MotionBlurQuality": 9})
    with pytest.raises(ConfigError, match="one of"):
        apply_settings("ff7r2", root, {"r.Shadow.MaxResolution": 3000})
    with pytest.raises(ConfigError, match="whole number"):
        apply_settings("ff7r2", root, {"r.BloomQuality": True})
    with pytest.raises(ConfigError, match="not a supported Unreal setting"):
        apply_settings("ff7r2", root, {"r.NoSuchCVar": 1})
    assert validate_value("r.ViewDistanceScale", 2) == "2"
    with pytest.raises(ConfigError, match="from 0.1 to 10.0"):
        validate_value("r.ViewDistanceScale", 99.0)


def test_ff7r_eye_adaptation_stays_with_legacy_group(project):
    root, _ini = project
    with pytest.raises(ConfigError, match="existing game tweaks group"):
        apply_settings("ff7r", root, {"r.EyeAdaptationQuality": 0})
    report = apply_settings("ff7r", root, {"r.MotionBlurQuality": 1})
    assert report["overrides"] == {"r.MotionBlurQuality": "1"}


def test_overrides_stay_separate_from_observed_values(project):
    root, ini = project
    ini.write_text("[SystemSettings]\nr.BloomQuality=5\n", encoding="utf-8")
    report = apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    assert report["overrides"] == {"r.BloomQuality": "3"}
    assert report["observed"] == {"r.BloomQuality": "5"}


def test_reset_lets_surviving_user_override_apply_again(project):
    root, ini = project
    ini.write_bytes(b"[SystemSettings]\nr.BloomQuality=5\n")
    apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    result = reset_all("ff7r2", root)
    assert result["managedPresent"] is False
    assert result["restored"] == []
    text = ini.read_bytes().decode("utf-8")
    assert "r.BloomQuality=5" in text
    assert "r.BloomQuality=3" not in text


def test_reset_restores_vanished_user_override_from_journal(project):
    root, ini = project
    ini.write_bytes(b"[SystemSettings]\nr.BloomQuality=5\n")
    apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    raw = ini.read_bytes().decode("utf-8")
    ini.write_bytes(raw.replace("r.BloomQuality=5\n", "").encode("utf-8"))
    refresh_snapshot("ff7r2", root)
    result = reset_all("ff7r2", root)
    assert result["restored"] == ["r.BloomQuality"]
    text = ini.read_bytes().decode("utf-8")
    assert "r.BloomQuality=5" in text
    assert "r.BloomQuality=3" not in text


def test_reset_without_prior_value_leaves_key_absent(project):
    root, ini = project
    apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    result = reset_all("ff7r2", root)
    assert result["restored"] == []
    assert "r.BloomQuality" not in ini.read_text(encoding="utf-8")


def test_use_game_default_inherits_and_keeps_siblings(project):
    root, ini = project
    apply_settings("ff7r2", root, {"r.BloomQuality": 3, "r.MotionBlurQuality": 0})
    report = use_game_default("ff7r2", root, "r.BloomQuality")
    assert report["overrides"] == {"r.MotionBlurQuality": "0"}
    report = use_game_default("ff7r2", root, "r.MotionBlurQuality")
    assert report["managedPresent"] is False


def test_external_edit_blocks_save_and_leaves_file(project):
    root, ini = project
    apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    before = ini.read_bytes()
    ini.write_bytes(before + b"; user note\n")
    with pytest.raises(ExternalEditError, match="changed outside Lexeditor"):
        apply_settings("ff7r2", root, {"r.MotionBlurQuality": 0})
    assert ini.read_bytes() == before + b"; user note\n"
    report = status("ff7r2", root)
    assert report["externalChange"] is True


def test_game_rewrite_needs_review_then_rebaseline(project):
    root, ini = project
    apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    document = read_document(ini)
    assert unreal_config.remove_managed_block(document, "ff7r2") is True
    unreal_config.write_document(ini, document)
    report = status("ff7r2", root)
    assert report["externalChange"] is True
    assert report["managedPresent"] is False
    reviewed = refresh_snapshot("ff7r2", root)
    assert reviewed["externalChange"] is False
    final = apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    assert final["overrides"]["r.BloomQuality"] == "3"


def test_backup_precedes_first_mutation(project):
    root, ini = project
    original = "[SystemSettings]\nr.BloomQuality=5\n"
    ini.write_text(original, encoding="utf-8")
    report = apply_settings("ff7r2", root, {"r.BloomQuality": 3})
    assert report["backup"]
    assert Path(report["backup"]).read_text(encoding="utf-8") == original


def test_malformed_markers_refuse_to_guess(project):
    root, ini = project
    ini.write_text(
        "; BEGIN LEXEDITOR UNREAL CONFIG (ff7r2)\n"
        "; BEGIN LEXEDITOR UNREAL CONFIG (ff7r2)\n"
        "[SystemSettings]\nr.BloomQuality=3\n"
        "; END LEXEDITOR UNREAL CONFIG (ff7r2)\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="malformed or duplicate"):
        managed_overrides(read_document(ini), "ff7r2")


def test_observed_never_claims_effective_value(project):
    root, ini = project
    ini.write_text("[SystemSettings]\nr.BloomQuality=5\n", encoding="utf-8")
    observed = observed_values(read_document(ini), "ff7r2")
    assert observed == {"r.BloomQuality": "5"}
    assert setting("r.BloomQuality")["key"] == "r.BloomQuality"
