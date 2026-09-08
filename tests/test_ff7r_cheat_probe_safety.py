from games.ff7r.cheat_probe_safety import assess_menu_candidate_removals, assess_target_removal


def _target(*, rows, text_ids=("$Gift",), key="giftBox", total_rows=None):
    target = {
        "key": key,
        "label": "Gift Box",
        "textIds": list(text_ids),
        "rowCandidates": rows,
    }
    if total_rows is not None:
        target["rowCandidateCount"] = total_rows
    return target


def _row(asset="MenuData", *, type_code=11, controls=True, index=0, value="$Gift"):
    return {
        "asset": asset,
        "entryIndex": 4,
        "record": "SystemMenu",
        "matches": [{"property": f"MenuEntries[{index}]", "value": value, "match": "text-id"}],
        "controlFields": [{"name": "MenuVisible", "value": True}] if controls else [],
        "arrayElementCandidates": [{"property": "MenuEntries", "index": index, "typeCode": type_code}],
        "evidenceScore": 126,
    }


def test_unique_exact_fixed_width_owner_is_actionable():
    decision = assess_target_removal(_target(rows=[_row()]))

    assert decision["status"] == "ready"
    assert decision["actionable"] is True
    assert decision["reasonCodes"] == ["unique-exact-structural-owner"]
    assert decision["selector"] == {
        "asset": "MenuData",
        "entryIndex": 4,
        "record": "SystemMenu",
        "property": "MenuEntries",
        "index": 0,
        "typeCode": 11,
        "matchedTextIds": ["$Gift"],
        "fixedWidthDeleteSupported": True,
        "menuControlEvidence": True,
        "controlFields": ["MenuVisible"],
    }


def test_duplicate_exact_owners_fail_closed_as_ambiguous():
    decision = assess_target_removal(_target(rows=[_row("MenuDataA"), _row("MenuDataB")]))

    assert decision["actionable"] is False
    assert decision["selector"] is None
    assert "ambiguous-structural-owner" in decision["reasonCodes"]


def test_variable_width_or_missing_menu_context_blocks_removal():
    variable = assess_target_removal(_target(rows=[_row(type_code=10)]))
    contextless = assess_target_removal(_target(rows=[_row(controls=False)]))

    assert variable["actionable"] is False
    assert "unsupported-structural-type" in variable["reasonCodes"]
    assert contextless["actionable"] is False
    assert "missing-menu-control-evidence" in contextless["reasonCodes"]


def test_scan_errors_or_truncated_candidate_set_blocks_uniqueness():
    scan_error = assess_target_removal(_target(rows=[_row()]), scan_errors=["Unsupported.uasset"])
    truncated = assess_target_removal(_target(rows=[_row()], total_rows=2))

    assert scan_error["actionable"] is False
    assert "scan-errors" in scan_error["reasonCodes"]
    assert truncated["actionable"] is False
    assert "row-candidates-truncated" in truncated["reasonCodes"]


def test_report_assessment_never_mutates_probe_evidence():
    report = {"targets": [_target(rows=[_row()])], "scanErrors": []}
    original = repr(report)

    assessment = assess_menu_candidate_removals(report)

    assert assessment["allTargetsActionable"] is True
    assert assessment["targets"][0]["actionable"] is True
    assert repr(report) == original


def test_unresolved_text_ids_and_implicit_probe_cap_block_actionability():
    unresolved = assess_target_removal(_target(rows=[_row()], text_ids=("$Gift", "$GiftAlt")))
    capped = assess_target_removal(_target(rows=[_row(f"MenuData{i}") for i in range(128)]))

    assert unresolved["actionable"] is False
    assert "unresolved-installed-text-ids" in unresolved["reasonCodes"]
    assert capped["actionable"] is False
    assert "row-candidates-truncated" in capped["reasonCodes"]
