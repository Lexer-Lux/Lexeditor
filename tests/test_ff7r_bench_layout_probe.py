from types import SimpleNamespace

from games.ff7r.bench_layout_probe import (
    classify_object_layout_rows,
    correlate_object_layout_rows,
)


def _package(entries):
    return SimpleNamespace(
        asset="End/Content/GameContents/DataObject/Resident/ObjectLayout",
        properties=[
            SimpleNamespace(name=name)
            for name in (
                "UniqueIndex", "Priority", "NodeName", "LevelName",
                "BGActorName", "PushButtonActionID", "AttributeList_Array",
            )
        ],
        entries=entries,
    )


def _entry(index, tag, **values):
    defaults = {
        "UniqueIndex": index,
        "Priority": 0,
        "NodeName": "",
        "LevelName": "",
        "BGActorName": "",
        "PushButtonActionID": "",
        "AttributeList_Array": [],
    }
    defaults.update(values)
    return SimpleNamespace(index=index, tag=tag, values=defaults)


def test_object_layout_classification_requires_literal_bench_or_vending_evidence_and_tracks_sector7():
    result = classify_object_layout_rows(_package([
        _entry(
            0,
            "slum7_bench_layout",
            LevelName="slum7_03",
            BGActorName="BenchActor_42",
            AttributeList_Array=["objCmn_ProgBench"],
        ),
        _entry(
            1,
            "slum7_vending_layout",
            LevelName="slum7_03",
            BGActorName="VendingActor_9",
            AttributeList_Array=["objCmn_ProgVendingMachine"],
        ),
        _entry(
            2,
            "slum5_bench_layout",
            LevelName="slum5_01",
            BGActorName="BenchActor_Other",
            AttributeList_Array=["objCmn_ProgBench"],
        ),
        _entry(3, "slum7_unrelated", LevelName="slum7_03", BGActorName="Lamp_0"),
    ]))

    assert [row["tag"] for row in result["rows"]] == [
        "slum7_bench_layout", "slum7_vending_layout", "slum5_bench_layout",
    ]
    assert [row["bgActorName"] for row in result["sector7BenchRows"]] == ["BenchActor_42"]
    assert [row["bgActorName"] for row in result["sector7VendingRows"]] == ["VendingActor_9"]


def test_object_layout_correlation_requires_exact_actor_name_and_level_path_match():
    layout = classify_object_layout_rows(_package([
        _entry(
            0,
            "slum7_bench_layout",
            LevelName="slum7_03",
            BGActorName="BenchActor_42",
            AttributeList_Array=["objCmn_ProgBench"],
        ),
        _entry(
            1,
            "slum7_vending_layout",
            LevelName="slum7_03",
            BGActorName="VendingActor_9",
            AttributeList_Array=["objCmn_ProgVendingMachine"],
        ),
    ]))
    report = {
        "allEvidenceCandidates": [{
            "path": "End/Content/Maps/slum7/slum7_03.umap",
            "benchExports": [{
                "index": 10,
                "objectName": "BenchActor_42",
                "objectPath": "PersistentLevel.BenchActor_42",
            }],
            "vendingExports": [{
                "index": 11,
                "objectName": "VendingActor_9",
                "objectPath": "PersistentLevel.VendingActor_9",
            }],
            "serializedSpatialPairs": [{
                "bench": {"ownerExportIndex": 10},
                "vending": {"ownerExportIndex": 11},
                "numericDistance": 125.0,
                "coordinateSpaceValidated": False,
                "worldSpaceAdjacencyValidated": False,
            }],
        }],
    }

    rows = correlate_object_layout_rows(layout, report)

    assert len(rows) == 1
    row = rows[0]
    assert row["levelName"] == "slum7_03"
    assert row["benchBGActorName"] == "BenchActor_42"
    assert row["benchExportIndex"] == 10
    assert row["vendingBGActorName"] == "VendingActor_9"
    assert row["vendingExportIndex"] == 11
    assert row["exactActorIdentityCorrelation"] is True
    assert row["sameObjectLayoutLevel"] is True
    assert row["serializedSpatialPair"]["numericDistance"] == 125.0
    assert row["worldSpaceAdjacencyValidated"] is False
    assert row["suppressionAuthorized"] is False


def test_near_match_actor_name_is_rejected_instead_of_fuzzy_correlated():
    layout = classify_object_layout_rows(_package([
        _entry(
            0,
            "slum7_bench_layout",
            LevelName="slum7_03",
            BGActorName="BenchActor_42",
            AttributeList_Array=["objCmn_ProgBench"],
        ),
        _entry(
            1,
            "slum7_vending_layout",
            LevelName="slum7_03",
            BGActorName="VendingActor_9",
            AttributeList_Array=["objCmn_ProgVendingMachine"],
        ),
    ]))
    report = {
        "allEvidenceCandidates": [{
            "path": "End/Content/Maps/slum7/slum7_03.umap",
            "benchExports": [{"index": 10, "objectName": "BenchActor_420"}],
            "vendingExports": [{"index": 11, "objectName": "VendingActor_9"}],
        }],
    }

    assert correlate_object_layout_rows(layout, report) == []


def test_matching_actor_names_in_wrong_level_are_rejected():
    layout = classify_object_layout_rows(_package([
        _entry(
            0,
            "slum7_bench_layout",
            LevelName="slum7_03",
            BGActorName="BenchActor_42",
            AttributeList_Array=["objCmn_ProgBench"],
        ),
        _entry(
            1,
            "slum7_vending_layout",
            LevelName="slum7_03",
            BGActorName="VendingActor_9",
            AttributeList_Array=["objCmn_ProgVendingMachine"],
        ),
    ]))
    report = {
        "allEvidenceCandidates": [{
            "path": "End/Content/Maps/slum7/slum7_09.umap",
            "benchExports": [{"index": 10, "objectName": "BenchActor_42"}],
            "vendingExports": [{"index": 11, "objectName": "VendingActor_9"}],
        }],
    }

    assert correlate_object_layout_rows(layout, report) == []


def test_bench_and_vending_layout_rows_must_share_same_level_name():
    layout = classify_object_layout_rows(_package([
        _entry(
            0,
            "slum7_bench_layout",
            LevelName="slum7_03",
            BGActorName="BenchActor_42",
            AttributeList_Array=["objCmn_ProgBench"],
        ),
        _entry(
            1,
            "slum7_vending_layout",
            LevelName="slum7_04",
            BGActorName="VendingActor_9",
            AttributeList_Array=["objCmn_ProgVendingMachine"],
        ),
    ]))
    report = {
        "allEvidenceCandidates": [{
            "path": "End/Content/Maps/slum7/slum7_03.umap",
            "benchExports": [{"index": 10, "objectName": "BenchActor_42"}],
            "vendingExports": [{"index": 11, "objectName": "VendingActor_9"}],
        }],
    }

    assert correlate_object_layout_rows(layout, report) == []
