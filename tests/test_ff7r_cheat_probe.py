from types import SimpleNamespace

from games.ff7r.cheat_probe import scan_installed_menu_candidates


def _text_entry(key, text, subentries=()):
    return SimpleNamespace(key=key, text=text, subentries=[SimpleNamespace(id=i, text=t) for i, t in subentries])


def _data_package(properties, entries):
    props = []
    for prop in properties:
        if isinstance(prop, str):
            prop = (prop, None, False)
        name, type_code, is_array = prop
        props.append(SimpleNamespace(name=name, type_code=type_code, is_array=is_array))
    return SimpleNamespace(
        properties=props,
        entries=[SimpleNamespace(index=index, tag=tag, values=values) for index, (tag, values) in enumerate(entries)],
    )


def test_probe_resolves_installed_labels_to_text_ids_and_dataobject_references():
    text = SimpleNamespace(entries=[
        _text_entry("$System_GiftBox", "Gift Box"),
        _text_entry("$Options_Streamlined", "Streamlined Progression"),
        _text_entry("$Difficulty_Easy", "Easy"),
        _text_entry("$NewGame_HeadStart", "Begin with Head Start bonuses"),
        _text_entry("$Noise", "An easy way to learn the controls"),
    ])
    data = _data_package(
        ["LabelTextId", "StreamlinedProgressionVisible", "Enabled"],
        [
            ("System_GiftBox", {"LabelTextId": "$System_GiftBox", "Enabled": True}),
            ("Options_Streamlined", {"LabelTextId": "$Options_Streamlined", "StreamlinedProgressionVisible": True}),
            ("Difficulty_Easy", {"LabelTextId": "$Difficulty_Easy", "Mode": "Easy"}),
            ("NewGame_HeadStart", {"Labels": ["$NewGame_HeadStart"]}),
        ],
    )

    result = scan_installed_menu_candidates(
        [("End/Text/Resident_US", text)],
        [("End/DataObject/Menu", data)],
        language="US",
    )
    targets = {target["key"]: target for target in result["targets"]}

    assert targets["giftBox"]["textIds"] == ["$System_GiftBox"]
    assert targets["streamlinedProgression"]["textIds"] == ["$Options_Streamlined"]
    assert targets["easyMode"]["textIds"] == ["$Difficulty_Easy"]
    assert targets["fastStart"]["textIds"] == ["$NewGame_HeadStart"]
    assert "$Noise" not in targets["easyMode"]["textIds"]

    gift_refs = targets["giftBox"]["dataReferences"]
    assert any(ref["record"] == "System_GiftBox" and ref["match"] == "text-id" for ref in gift_refs)
    assert any("StreamlinedProgressionVisible" in row for row in targets["streamlinedProgression"]["schemaMatches"])

    gift_row = targets["giftBox"]["rowCandidates"][0]
    assert gift_row["record"] == "System_GiftBox"
    assert any(match["property"] == "LabelTextId" and match["match"] == "text-id" for match in gift_row["matches"])
    assert any(field["name"] == "Enabled" and field["value"] is True for field in gift_row["controlFields"])
    assert gift_row["evidenceScore"] >= 100

    coverage = next(row for row in result["assetCoverage"] if row["asset"] == "End/DataObject/Menu")
    assert coverage["targets"] == ["easyMode", "fastStart", "giftBox", "streamlinedProgression"]
    assert coverage["textIdMatches"] >= 4
    assert result["textResourcesScanned"] == 1
    assert result["dataObjectsScanned"] == 1


def test_probe_handles_nested_values_markup_and_scan_errors_without_mutating():
    text = SimpleNamespace(entries=[
        _text_entry("$Gift", "<b>Gift Box</b>"),
        _text_entry("$Other", "Nothing relevant"),
    ])
    data = _data_package([], [
        ("ROW", {"Nested": {"Labels": ["$Gift"]}}),
    ])
    result = scan_installed_menu_candidates(
        [("Text", text)], [("Data", data)], scan_errors=["BrokenTable: unsupported property"]
    )
    gift = next(target for target in result["targets"] if target["key"] == "giftBox")
    assert gift["textIds"] == ["$Gift"]
    assert gift["dataReferences"][0]["property"] == "Nested.Labels[0]"
    assert gift["rowCandidates"][0]["arrayElementCandidates"] == []
    assert result["scanErrors"] == ["BrokenTable: unsupported property"]


def test_probe_marks_declared_array_element_as_structural_candidate_without_editing():
    text = SimpleNamespace(entries=[
        _text_entry("$Gift", "Gift Box"),
        _text_entry("$Other", "Other Option"),
    ])
    data = _data_package(
        [("MenuEntries", 11, True), ("MenuVisible", 1, False)],
        [("SystemMenu", {"MenuEntries": ["$Gift", "$Other"], "MenuVisible": True})],
    )

    result = scan_installed_menu_candidates([("Text", text)], [("MenuData", data)])
    gift = next(target for target in result["targets"] if target["key"] == "giftBox")
    row = gift["rowCandidates"][0]
    assert row["arrayElementCandidates"] == [{"property": "MenuEntries", "index": 0, "typeCode": 11}]
    assert any(field["name"] == "MenuVisible" for field in row["controlFields"])
    assert result["assetCoverage"][0]["arrayElementCandidates"] == 1


def test_probe_schema_details_preserve_property_shape_for_identifier_matches():
    data = _data_package(
        [("StreamlinedProgressionVisible", 1, False)],
        [("ROW", {"StreamlinedProgressionVisible": True})],
    )
    result = scan_installed_menu_candidates([], [("OptionsData", data)])
    streamlined = next(target for target in result["targets"] if target["key"] == "streamlinedProgression")
    assert streamlined["schemaDetails"] == [{
        "asset": "OptionsData",
        "name": "StreamlinedProgressionVisible",
        "typeCode": 1,
        "array": False,
    }]
