from games.ff7r.bench_probe import rank_bench_candidates


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
