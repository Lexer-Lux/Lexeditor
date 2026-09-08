from types import SimpleNamespace

from games.ff7r.raw_asset_probe import (
    extract_interesting_strings,
    extract_object_evidence,
    select_shadowed_assets,
)


def test_raw_asset_selection_is_case_insensitive_and_later_paks_shadow_earlier_files():
    rows = select_shadowed_assets(
        [
            ("End/Content/Paks/pakchunk0.pak", [
                "End/Content/Menu/Resident/Battle/LockOnMarker.uasset",
                "End/Content/Menu/Resident/Battle/LockOnMarker.uexp",
                "End/Content/Menu/Resident/Battle/Unrelated.uasset",
            ]),
            ("End/Content/Paks/pakchunk99_P.pak", [
                "End/Content/Menu/Resident/Battle/LOCKONMARKER.uasset",
            ]),
        ],
        terms=["lockonmarker"],
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["asset"].casefold().endswith("/lockonmarker")
    assert row["files"][".uasset"]["pak"].endswith("pakchunk99_P.pak")
    assert row["files"][".uexp"]["pak"].endswith("pakchunk0.pak")


def test_raw_asset_selection_requires_a_search_term():
    try:
        select_shadowed_assets([], terms=[])
    except ValueError as error:
        assert "at least one" in str(error)
    else:
        raise AssertionError("empty raw-asset search terms must fail closed")


def test_binary_string_probe_reports_lockon_text_and_visual_property_names():
    utf16 = "ReticleImage SetColorAndOpacity".encode("utf-16-le")
    data = (
        b"\x00garbage\x00LOCK ON\x00WidgetTree\x00BrushColor\x00"
        + utf16
        + b"\x00SomeTotallyUnrelatedSentence\x00"
    )
    rows = extract_interesting_strings(data)
    strings = {(row["encoding"], row["text"]) for row in rows}
    assert ("ascii", "LOCK ON") in strings
    assert ("ascii", "WidgetTree") in strings
    assert ("ascii", "BrushColor") in strings
    assert ("utf16le", "ReticleImage SetColorAndOpacity") in strings
    assert not any("TotallyUnrelated" in row["text"] for row in rows)


def test_binary_string_probe_can_be_limited():
    data = b"LockA\x00LockB\x00LockC\x00"
    rows = extract_interesting_strings(data, tokens=["lock"], limit=2)
    assert len(rows) == 2


def test_object_evidence_prefers_specific_resolved_owner_when_bounded(monkeypatch):
    import games.ff7r.raw_asset_probe as module

    class FakeTable:
        imports = (
            SimpleNamespace(
                index=0,
                object_name=SimpleNamespace(display="TextBlock"),
                outer_index=0,
                class_package=SimpleNamespace(display="/Script/UMG"),
                class_name=SimpleNamespace(display="Class"),
            ),
        )

        def resolve_path(self, package_index):
            return "WidgetTree.TextBlock" if package_index == -1 else None

        def export_rows(self):
            return [
                {
                    "index": 0,
                    "packageIndex": 1,
                    "objectName": "BattleLockonMarker",
                    "objectPath": "WidgetTree.BattleLockonMarker",
                    "outerIndex": 0,
                    "outerPath": "WidgetTree",
                    "classIndex": -2,
                    "className": "EndBattleLockonMarkerIcon",
                    "classPath": "/Script/EndGame.EndBattleLockonMarkerIcon",
                    "superIndex": 0,
                    "templateIndex": 0,
                    "serialSize": 64,
                    "serialOffset": 256,
                },
                {
                    "index": 1,
                    "packageIndex": 2,
                    "objectName": "TextBlock",
                    "objectPath": "WidgetTree.TextBlock",
                    "outerIndex": 0,
                    "outerPath": "WidgetTree",
                    "classIndex": -3,
                    "className": "TextBlock",
                    "classPath": "/Script/UMG.TextBlock",
                    "superIndex": 0,
                    "templateIndex": 0,
                    "serialSize": 64,
                    "serialOffset": 320,
                },
            ]

        def summary(self):
            return {"importCount": 1, "exportCount": 2}

    monkeypatch.setattr(module, "parse_object_table", lambda data, label: FakeTable())
    evidence = extract_object_evidence(
        b"fixture",
        tokens=["EndBattleLockonMarkerIcon", "Text"],
        limit=1,
    )
    assert evidence["objectTableParsed"] is True
    assert evidence["objectTableSummary"]["exportCount"] == 2
    assert len(evidence["resolvedExports"]) == 1
    assert evidence["resolvedExports"][0]["objectName"] == "BattleLockonMarker"
    assert "EndBattleLockonMarkerIcon" in evidence["resolvedExports"][0]["matchedTokens"]
