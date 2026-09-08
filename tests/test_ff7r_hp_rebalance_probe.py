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


def _native_hit(needle, function_rva, *next_hops, source="pdata"):
    return {
        "needle": needle,
        "hits": [{
            "leaRipXrefs": [{
                "candidateFunctionRva": function_rva,
                "candidateFunctionSource": source,
                "candidateFunctionCodeRefs": {
                    "refs": [
                        {"targetFunctionRva": target}
                        for target in next_hops
                    ],
                },
            }],
        }],
    }


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
    assert result["nativeAssessment"]["implementationReady"] is False


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


def test_hp_probe_native_needles_cover_exact_player_current_and_max_accessors():
    expected = {
        "BPGetPlayerStatus",
        "BPGetPlayerStatusWithEquipment",
        "BPGetPlayerStatusWithMateria",
        "BPGetPlayerHPMax",
        "BPGetPlayerHP",
        "BPSetPlayerHPMax",
        "BPSetPlayerHP",
        "GetCharaHPMax",
        "GetCharaHP",
        "GetHPMax",
        "GetHP",
    }
    assert expected.issubset(set(probe.NATIVE_NEEDLES))


def test_hp_native_assessment_correlates_exact_max_and_current_hp_paths():
    native = {
        "needles": [
            _native_hit("BPSetPlayerHPMax", 0x1000, 0x5000),
            _native_hit("BPGetPlayerHPMax", 0x2000, 0x5000),
            _native_hit("BPGetPlayerStatus", 0x3000, 0x5000),
            _native_hit("BPSetPlayerHP", 0x4000, 0x6000),
            _native_hit("BPGetPlayerHP", 0x4100, 0x6000),
            _native_hit("GetHPMax", 0x7000),
            _native_hit("GetHP", 0x7100),
        ]
    }

    result = probe.assess_hp_native_evidence(native)

    assert result["functionCorrelations"]["maxWriteToMaxRead"] == [0x5000]
    assert result["functionCorrelations"]["maxWriteToStatus"] == [0x5000]
    assert result["functionCorrelations"]["statusToMaxRead"] == [0x5000]
    assert result["functionCorrelations"]["currentWriteToCurrentRead"] == [0x6000]
    assert result["genericAnchorFunctions"] == [0x7000, 0x7100]
    assert "player-max-hp-setter-function-unresolved" not in result["blockers"]
    assert "player-current-hp-clamp-setter-function-unresolved" not in result["blockers"]
    assert result["implementationReady"] is False
    assert "authoritative-max-hp-recalculation-interception-unvalidated" in result["blockers"]


def test_generic_hp_names_cannot_satisfy_exact_player_api_roles():
    result = probe.assess_hp_native_evidence({
        "needles": [
            _native_hit("GetHPMax", 0x1000),
            _native_hit("GetHP", 0x1000),
        ]
    })

    assert result["genericAnchorFunctions"] == [0x1000]
    assert "player-max-hp-setter-function-unresolved" in result["blockers"]
    assert "player-current-hp-clamp-setter-function-unresolved" in result["blockers"]
    assert "player-max-hp-read-function-unresolved" in result["blockers"]
    assert "player-current-hp-read-function-unresolved" in result["blockers"]
    assert result["implementationReady"] is False


def test_hp_native_assessment_marks_multi_api_direct_owner_as_registration_collision():
    result = probe.assess_hp_native_evidence({
        "needles": [
            _native_hit("BPSetPlayerHPMax", 0x2000),
            _native_hit("BPGetPlayerHPMax", 0x2000),
        ]
    })
    cluster = next(
        row for row in result["functionClusters"]
        if row["functionRva"] == 0x2000
    )

    assert cluster["roles"] == ["max-read", "max-write"]
    assert cluster["directNeedles"] == ["BPGetPlayerHPMax", "BPSetPlayerHPMax"]
    assert cluster["crossRole"] is True
    assert cluster["registrationCollisionRisk"] is True
    assert result["implementationReady"] is False


def test_hp_native_assessment_ignores_padding_heuristic_function_owners():
    result = probe.assess_hp_native_evidence({
        "needles": [
            _native_hit("BPSetPlayerHPMax", 0x2000, 0x5000, source="padding-heuristic"),
            _native_hit("GetHPMax", 0x3000, source="padding-heuristic"),
        ]
    })

    assert result["functionEvidence"]["BPSetPlayerHPMax"]["expandedPdataFunctions"] == []
    assert result["genericAnchorFunctions"] == []
    assert "player-max-hp-setter-function-unresolved" in result["blockers"]
