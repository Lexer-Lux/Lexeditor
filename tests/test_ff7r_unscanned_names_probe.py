from pathlib import Path

from games.ff7r import unscanned_names_probe as probe


def test_unscanned_probe_targets_both_enemy_name_surfaces_and_enemybook_identity():
    assert "EnemyBookID" in probe.EXE_NEEDLES
    assert "ShowBattleEnemyStatusWindow" in probe.EXE_NEEDLES
    assert "ShowBattleTargetIcon" in probe.EXE_NEEDLES
    assert any("enemystatus" in term for term in probe.ASSET_TERMS)
    assert any("battletarget_new" in term for term in probe.ASSET_TERMS)


def test_unscanned_probe_composes_native_and_widget_evidence_without_calling_viewstate_scan_state(monkeypatch):
    calls = {}

    def fake_native(game_root, *, needles):
        calls["native"] = (Path(game_root), tuple(needles))
        return {"timestampHex": "0x12345678", "needles": []}

    def fake_assets(game_root, *, terms, interesting_tokens):
        calls["assets"] = (Path(game_root), tuple(terms), tuple(interesting_tokens))
        return {"assets": [{"asset": "EnemyStatus"}], "scanErrors": []}

    monkeypatch.setattr(probe, "probe_installed_exe", fake_native)
    monkeypatch.setattr(probe, "probe_installed_assets", fake_assets)

    result = probe.probe_unscanned_name_surfaces(Path("C:/FF7R"))
    assert calls["native"][1] == probe.EXE_NEEDLES
    assert calls["assets"][1] == probe.ASSET_TERMS
    assert result["knownContracts"]["enemyIdentity"] == "BattleCharaSpec.EnemyBookID"
    warning = result["knownContracts"]["authoredEnemyBookWarning"]
    assert "not treated as proof" in warning
    assert "per-save" in result["notes"][0]
