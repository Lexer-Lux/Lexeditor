from types import SimpleNamespace

from games.ff7r.cheat_probe import scan_installed_menu_candidates


def _text_entry(key, text, subentries=()):
    return SimpleNamespace(key=key, text=text, subentries=[SimpleNamespace(id=i, text=t) for i, t in subentries])


def _data_package(properties, entries):
    return SimpleNamespace(
        properties=[SimpleNamespace(name=name) for name in properties],
        entries=[SimpleNamespace(tag=tag, values=values) for tag, values in entries],
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
        ["LabelTextId", "StreamlinedProgressionVisible"],
        [
            ("System_GiftBox", {"LabelTextId": "$System_GiftBox", "Enabled": True}),
            ("Options_Streamlined", {"LabelTextId": "$Options_Streamlined"}),
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
    assert result["scanErrors"] == ["BrokenTable: unsupported property"]
