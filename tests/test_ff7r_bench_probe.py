from games.ff7r.bench_probe import pair_spatial_vectors, rank_bench_candidates


def test_bench_probe_ranks_map_with_bench_and_vending_above_single_evidence_files():
    rows = rank_bench_candidates([
        {
            "path": "End/Content/slum7/foo.uasset",
            "interestingStrings": [
                {"encoding": "ascii", "offset": 1, "text": "objCmn_ProgBench"},
            ],
        },
        {
            "path": "End/Content/slum7/bar.umap",
            "interestingStrings": [
                {"encoding": "ascii", "offset": 2, "text": "EndFieldActionActorBenchBreak"},
                {"encoding": "ascii", "offset": 3, "text": "objCmn_ProgVendingMachine"},
            ],
        },
        {
            "path": "End/Content/slum7/baz.uasset",
            "interestingStrings": [
                {"encoding": "ascii", "offset": 4, "text": "VendingMachine"},
            ],
        },
    ])
    assert rows[0]["path"].endswith("bar.umap")
    assert rows[0]["containsBenchAndVending"] is True
    assert rows[0]["score"] > rows[1]["score"]
    assert any("BenchBreak" in evidence["text"] for evidence in rows[0]["benchEvidence"])
    assert any("Vending" in evidence["text"] for evidence in rows[0]["vendingEvidence"])


def test_bench_probe_ignores_files_without_bench_or_vending_evidence():
    rows = rank_bench_candidates([
        {
            "path": "End/Content/slum7/irrelevant.umap",
            "interestingStrings": [
                {"encoding": "ascii", "offset": 1, "text": "PersistentLevel"},
            ],
        }
    ])
    assert rows == []


def test_bench_probe_recognizes_common_program_ids_not_only_class_names():
    rows = rank_bench_candidates([
        {
            "path": "End/Content/slum7/layout.uexp",
            "interestingStrings": [
                {"encoding": "ascii", "offset": 1, "text": "objCmn_ProgBench"},
                {"encoding": "ascii", "offset": 2, "text": "objCmn_ProgVendingMachine"},
            ],
        }
    ])
    assert len(rows) == 1
    assert rows[0]["containsBenchAndVending"] is True


def test_bench_probe_prefers_resolved_same_outer_exports_over_string_only_pair():
    string_only = {
        "path": "End/Content/slum7/string-only.umap",
        "interestingStrings": [
            {"encoding": "ascii", "offset": 1, "text": "EndFieldActionActorBenchBreak"},
            {"encoding": "ascii", "offset": 2, "text": "VendingMachine"},
        ],
    }
    resolved = {
        "path": "End/Content/slum7/resolved.umap",
        "interestingStrings": [],
        "benchExports": [{
            "index": 10,
            "objectName": "BenchActor_0",
            "classPath": "/Script/EndGame.EndFieldActionActorBenchBreak",
            "outerPath": "PersistentLevel",
        }],
        "vendingExports": [{
            "index": 11,
            "objectName": "VendingActor_0",
            "classPath": "/Script/EndGame.EndFieldActionActorVendingMachine",
            "outerPath": "PersistentLevel",
        }],
        "sharedOuterPairs": [{
            "outerPath": "PersistentLevel",
            "benchExportIndex": 10,
            "vendingExportIndex": 11,
        }],
    }

    rows = rank_bench_candidates([string_only, resolved])
    assert rows[0]["path"].endswith("resolved.umap")
    assert rows[0]["containsBenchAndVending"] is False
    assert rows[0]["containsBenchAndVendingExports"] is True
    assert rows[0]["score"] > rows[1]["score"]


def test_spatial_vector_pairs_rank_numeric_nearest_without_claiming_world_space():
    bench = [
        {
            "ownerExportIndex": 10,
            "ownerObjectName": "BenchNear",
            "propertyName": "RelativeLocation",
            "vector": {"x": 100.0, "y": 100.0, "z": 0.0},
        },
        {
            "ownerExportIndex": 12,
            "ownerObjectName": "BenchFar",
            "propertyName": "RelativeLocation",
            "vector": {"x": 1000.0, "y": 1000.0, "z": 0.0},
        },
    ]
    vending = [{
        "ownerExportIndex": 11,
        "ownerObjectName": "Vending",
        "propertyName": "RelativeLocation",
        "vector": {"x": 103.0, "y": 104.0, "z": 0.0},
    }]

    pairs = pair_spatial_vectors(bench, vending)

    assert len(pairs) == 2
    assert pairs[0]["bench"]["ownerObjectName"] == "BenchNear"
    assert pairs[0]["numericDistance"] == 5.0
    assert pairs[0]["samePropertyName"] is True
    assert pairs[0]["coordinateSpaceValidated"] is False
    assert pairs[0]["worldSpaceAdjacencyValidated"] is False


def test_serialized_spatial_pair_outranks_same_outer_only_but_remains_unvalidated():
    same_outer = {
        "path": "End/Content/slum7/same-outer.umap",
        "interestingStrings": [],
        "benchExports": [{"index": 10, "objectName": "BenchA", "outerPath": "PersistentLevel"}],
        "vendingExports": [{"index": 11, "objectName": "VendA", "outerPath": "PersistentLevel"}],
        "sharedOuterPairs": [{"benchExportIndex": 10, "vendingExportIndex": 11}],
    }
    spatial = {
        "path": "End/Content/slum7/spatial.umap",
        "interestingStrings": [],
        "benchExports": [{"index": 20, "objectName": "BenchB", "outerPath": "PersistentLevel"}],
        "vendingExports": [{"index": 21, "objectName": "VendB", "outerPath": "PersistentLevel"}],
        "sharedOuterPairs": [{"benchExportIndex": 20, "vendingExportIndex": 21}],
        "serializedSpatialPairs": [{
            "bench": {"ownerObjectName": "BenchB", "propertyName": "RelativeLocation"},
            "vending": {"ownerObjectName": "VendB", "propertyName": "RelativeLocation"},
            "samePropertyName": True,
            "numericDistance": 42.0,
            "coordinateSpaceValidated": False,
            "worldSpaceAdjacencyValidated": False,
        }],
    }

    rows = rank_bench_candidates([same_outer, spatial])

    assert rows[0]["path"].endswith("spatial.umap")
    assert rows[0]["containsSerializedSpatialPair"] is True
    assert rows[0]["nearestSerializedSpatialPair"]["numericDistance"] == 42.0
    assert rows[0]["nearestSerializedSpatialPair"]["worldSpaceAdjacencyValidated"] is False
