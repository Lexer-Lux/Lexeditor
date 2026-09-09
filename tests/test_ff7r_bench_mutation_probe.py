from types import SimpleNamespace

from games.ff7r.bench_mutation_probe import analyze_object_layout_mutation_surface
from games.ff7r.dataobject import BOOLEAN, INT32, NAME, STRING, Property


def _entry(index, tag, **values):
    return SimpleNamespace(index=index, tag=tag, values=values)


def _package():
    properties = [
        Property("UniqueIndex", INT32, False),
        Property("NodeName", STRING, False),
        Property("LevelName", STRING, False),
        Property("BGActorName", STRING, False),
        Property("PushButtonActionID", NAME, False),
        Property("AttributeList_Array", NAME, True),
        Property("bVisible", BOOLEAN, False),
        Property("DisableState", NAME, False),
        Property("InteractionState", STRING, False),
        Property("FlavorText", STRING, False),
    ]
    entries = [
        _entry(
            0,
            "bench-row",
            UniqueIndex=0,
            NodeName="slum7_node",
            LevelName="slum7_03",
            BGActorName="BenchActor_42",
            PushButtonActionID="BenchUse",
            AttributeList_Array=["objCmn_ProgBench"],
            bVisible=True,
            DisableState="Enabled",
            InteractionState="Active",
            FlavorText="bench",
        ),
        _entry(
            1,
            "vending-row",
            UniqueIndex=1,
            NodeName="slum7_node",
            LevelName="slum7_03",
            BGActorName="VendingActor_9",
            PushButtonActionID="VendingUse",
            AttributeList_Array=["objCmn_ProgVendingMachine"],
            bVisible=True,
            DisableState="Enabled",
            InteractionState="Active",
            FlavorText="vending",
        ),
        _entry(
            2,
            "disabled-other-row",
            UniqueIndex=2,
            NodeName="other",
            LevelName="slum7_09",
            BGActorName="OtherActor_1",
            PushButtonActionID="None",
            AttributeList_Array=[],
            bVisible=False,
            DisableState="Disabled",
            InteractionState="Inactive",
            FlavorText="other",
        ),
    ]
    return SimpleNamespace(
        asset="End/Content/GameContents/DataObject/Resident/ObjectLayout",
        properties=properties,
        entries=entries,
    )


def _layout():
    return {
        "sector7BenchRows": [{
            "entry": 0,
            "tag": "bench-row",
            "levelName": "slum7_03",
            "bgActorName": "BenchActor_42",
            "pushButtonActionID": "BenchUse",
            "attributeList": ["objCmn_ProgBench"],
        }],
        "sector7VendingRows": [{
            "entry": 1,
            "tag": "vending-row",
            "levelName": "slum7_03",
            "bgActorName": "VendingActor_9",
            "pushButtonActionID": "VendingUse",
            "attributeList": ["objCmn_ProgVendingMachine"],
        }],
    }


def test_mutation_inventory_ranks_semantic_name_leads_without_authorizing_edits():
    result = analyze_object_layout_mutation_surface(_package(), _layout())

    assert result["implementationReady"] is False
    assert result["suppressionAuthorized"] is False
    assert result["sector7BenchRowCount"] == 1
    row = result["benchRows"][0]
    assert row["bgActorName"] == "BenchActor_42"
    candidates = {candidate["property"]: candidate for candidate in row["fieldCandidates"]}

    assert "UniqueIndex" not in candidates
    assert "NodeName" not in candidates
    assert "LevelName" not in candidates
    assert "BGActorName" not in candidates
    assert "FlavorText" not in candidates
    assert candidates["bVisible"]["writerEditable"] is True
    assert candidates["PushButtonActionID"]["writerEditable"] is True
    assert candidates["InteractionState"]["writerEditable"] is False
    assert all(candidate["mutationAuthorized"] is False for candidate in candidates.values())
    assert all(candidate["semanticMeaningValidated"] is False for candidate in candidates.values())


def test_installed_alternatives_are_reported_as_evidence_not_recommendations():
    result = analyze_object_layout_mutation_surface(_package(), _layout())
    candidates = {
        candidate["property"]: candidate
        for candidate in result["benchRows"][0]["fieldCandidates"]
    }

    disable = candidates["DisableState"]
    disabled = next(
        row for row in disable["alternativeValues"]
        if row["value"] == "Disabled"
    )
    assert "disable" in disabled["literalStateTokens"]
    assert disabled["exampleEntries"] == [{"entry": 2, "tag": "disabled-other-row"}]
    assert disable["literalStateAlternativeCount"] == 1

    interaction = candidates["InteractionState"]
    inactive = next(
        row for row in interaction["alternativeValues"]
        if row["value"] == "Inactive"
    )
    assert "inactive" in inactive["literalStateTokens"]
    assert interaction["writerEditable"] is False

    # A False value is useful distribution evidence, but polarity is not inferred.
    visible = candidates["bVisible"]
    false_row = next(row for row in visible["alternativeValues"] if row["value"] is False)
    assert false_row["literalStateTokens"] == []
    assert visible["semanticMeaningValidated"] is False


def test_same_level_vending_values_are_compared_without_treating_difference_as_semantics():
    result = analyze_object_layout_mutation_surface(_package(), _layout())
    candidates = {
        candidate["property"]: candidate
        for candidate in result["benchRows"][0]["fieldCandidates"]
    }

    action = candidates["PushButtonActionID"]
    assert action["currentValue"] == "BenchUse"
    assert action["sameLevelVendingValues"] == ["VendingUse"]
    assert action["differsFromEverySameLevelVendingValue"] is True
    assert action["mutationAuthorized"] is False

    visible = candidates["bVisible"]
    assert visible["sameLevelVendingValues"] == [True]
    assert visible["differsFromEverySameLevelVendingValue"] is False
