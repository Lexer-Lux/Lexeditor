from types import SimpleNamespace

from games.ff7r import hp_rebalance_probe as probe


def _entry(index, tag, values):
    return SimpleNamespace(index=index, tag=tag, values=values)


def _package(asset, properties, entries):
    return SimpleNamespace(
        asset=asset,
        properties=[SimpleNamespace(name=name) for name in properties],
        entries=entries,
    )


def test_hp_probe_correlates_base_flat_percent_skill_and_weapon_upgrade_sources(monkeypatch):
    packages = {
        probe.PLAYER_PARAMETER: _package(
            "PlayerParameter", ["HPMax"],
            [_entry(0, "Cloud_L50", {"HPMax": 5000})],
        ),
        probe.EQUIPMENT: _package(
            "Equipment", ["ItemNameLabel", "HPMaxAdd", "HPMaxScale"],
            [
                _entry(0, "LeatherGloves", {"ItemNameLabel": "$Leather", "HPMaxAdd": 850, "HPMaxScale": 0}),
                _entry(1, "NoHp", {"ItemNameLabel": "$NoHp", "HPMaxAdd": 0, "HPMaxScale": 0}),
            ],
        ),
        probe.MATERIA: _package(
            "Materia", ["MateriaNameLabel", "HPMaxAdd", "HPMaxScale"],
            [_entry(0, "HPUp", {"MateriaNameLabel": "$HPUp", "HPMaxAdd": 0, "HPMaxScale": 100})],
        ),
        probe.EQUIPMENT_SKILL: _package(
            "EquipmentSkill", ["EffectType0", "EffectValue0", "EffectName0"],
            [
                _entry(0, "Skill_HP", {"EffectType0": 1, "EffectValue0": 200.0, "EffectName0": "None"}),
                _entry(1, "Skill_MP", {"EffectType0": 2, "EffectValue0": 200.0, "EffectName0": "None"}),
            ],
        ),
        probe.WEAPON_UPGRADE: _package(
            "WeaponUpgrade", ["WeaponID", "EquipmentSkillID", "OverrideParameter", "NodeName", "NodeDetail"],
            [
                _entry(0, "Node_HP", {"WeaponID": "LeatherGloves", "EquipmentSkillID": "Skill_HP", "OverrideParameter": 150.0, "NodeName": "", "NodeDetail": ""}),
                _entry(1, "Node_MP", {"WeaponID": "LeatherGloves", "EquipmentSkillID": "Skill_MP", "OverrideParameter": 150.0, "NodeName": "", "NodeDetail": ""}),
            ],
        ),
    }
    monkeypatch.setattr(probe, "_load", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "resident_text_map", lambda *_args, **_kwargs: {
        "$Leather": "Leather Gloves",
        "$NoHp": "Other",
        "$HPUp": "HP Up",
    })
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {
        "needles": [{"needle": name, "hits": []} for name in needles],
        "timestampHex": "0x12345678",
    })

    result = probe.probe_hp_rebalance_sources("game", "data", "project", {})
    assert result["playerParameter"]["rows"][0]["values"]["HPMax"] == 5000
    assert result["equipment"]["hpRows"] == [{
        "entry": 0,
        "tag": "LeatherGloves",
        "name": "Leather Gloves",
        "values": {"HPMaxAdd": 850, "HPMaxScale": 0},
    }]
    assert result["materia"]["hpRows"][0]["values"]["HPMaxScale"] == 100
    assert [row["tag"] for row in result["equipmentSkill"]["hpRows"]] == ["Skill_HP"]
    assert result["weaponUpgrade"]["hpUpgradeRows"] == [{
        "entry": 0,
        "tag": "Node_HP",
        "weaponId": "LeatherGloves",
        "equipmentSkillId": "Skill_HP",
        "overrideParameter": 150.0,
        "nodeName": "",
        "nodeDetail": "",
    }]
    assert result["knownContracts"]["equipmentSkillFlatEffect"].endswith("HPMaxAdd(1)")
    assert result["knownContracts"]["finalStatusType"] == "FEndPlayerStatus.HPMax"


def test_hp_probe_does_not_treat_percent_scale_as_flat_or_include_enemy_hp(monkeypatch):
    packages = {
        probe.PLAYER_PARAMETER: _package("PlayerParameter", ["HPMax"], []),
        probe.EQUIPMENT: _package(
            "Equipment", ["HPMaxAdd", "HPMaxScale"],
            [_entry(0, "PercentOnly", {"HPMaxAdd": 0, "HPMaxScale": 25})],
        ),
        probe.MATERIA: _package("Materia", ["HPMaxAdd", "HPMaxScale"], []),
        probe.EQUIPMENT_SKILL: _package("EquipmentSkill", ["EffectType0", "EffectValue0"], []),
        probe.WEAPON_UPGRADE: _package("WeaponUpgrade", ["WeaponID", "EquipmentSkillID", "OverrideParameter"], []),
    }
    monkeypatch.setattr(probe, "_load", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "resident_text_map", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {"needles": []})

    result = probe.probe_hp_rebalance_sources("g", "d", "p", {})
    assert result["equipment"]["hpRows"][0]["values"] == {"HPMaxAdd": 0, "HPMaxScale": 25}
    assert "EnemyParameter" not in str(result["knownContracts"])
    assert any("EnemyParameter.HPMax" in note for note in result["notes"])


def test_hp_probe_native_needles_cover_final_status_current_and_max_accessors():
    expected = {
        "BPGetPlayerStatus",
        "BPGetPlayerStatusWithEquipment",
        "BPGetPlayerStatusWithMateria",
        "BPGetPlayerHPMax",
        "BPGetPlayerHP",
        "BPSetPlayerHPMax",
        "GetHPMax",
        "GetHP",
    }
    assert expected.issubset(set(probe.NATIVE_NEEDLES))
