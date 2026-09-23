"""Offline compatibility tests using metadata facts from real Memoria catalog mods.

These fixtures reproduce public ModDescription.xml fields and real package path
families; no third-party package or FF9 game bytes are stored in the repository.
"""
from pathlib import Path
import json
import pytest

from plugins.ff9 import mod_compat


def description(name, *, version="", minimum="", incompatible=""):
    fields = [f"<Name>{name}</Name>", f"<InstallationPath>{name.replace(' ', '')}</InstallationPath>"]
    if version:
        fields.append(f"<Version>{version}</Version>")
    if minimum:
        fields.append(f"<MinimumMemoriaVersion>{minimum}</MinimumMemoriaVersion>")
    if incompatible:
        fields.append(f"<IncompatibleWith>{incompatible}</IncompatibleWith>")
    return ("<Mod>" + "".join(fields) + "</Mod>").encode()


def write_mod(game: Path, folder: str, xml: bytes):
    root = game / folder
    root.mkdir(parents=True, exist_ok=True)
    (root / "ModDescription.xml").write_bytes(xml)
    return root


def test_real_catalog_metadata_and_overlap_boundary(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    game.mkdir(); project.mkdir()
    # Public Memoria catalog examples audited 2026-09-22:
    # Alternate Fantasy 6.8, Trance Seek 0.3.37.5, Ukrainian Translation 1.0,
    # Dualsense Buttons 1.1, CostumePack 2.1.
    alternate = write_mod(game, "AlternateFantasy", description(
        "Alternate Fantasy", version="6.8", minimum="2025-05-11",
        incompatible="Beatrix Mod, Trance Seek"))
    trance = write_mod(game, "TranceSeek", description(
        "Trance Seek", version="0.3.37.5", minimum="2025-05-17",
        incompatible="Alternate Fantasy, CostumePack"))
    ukrainian = write_mod(game, "TranslationUkr", description(
        "Ukrainian Translation", version="1.0", minimum="2024-11-17"))
    dualsense = write_mod(game, "DualsenseButtons", description(
        "Dualsense Buttons", version="1.1"))
    costume = write_mod(game, "CostumePack", description(
        "CostumePack", version="2.1", minimum="2026.07.21"))

    (game / "Memoria.ini").write_text(
        '[Mod]\n'
        'FolderNames = "Lexeditor", "AlternateFantasy", "TranceSeek", "TranslationUkr", "DualsenseButtons", "CostumePack"\n'
        'Priorities = "Lexeditor", "AlternateFantasy", "TranceSeek", "TranslationUkr", "DualsenseButtons", "CostumePack"\n'
        'MergeScripts = 1\n',
        encoding="utf-8",
    )

    # Lexeditor-generated gameplay path collides with a gameplay overhaul.
    item = project / "StreamingAssets/Data/Items/Items.csv"
    item.parent.mkdir(parents=True); item.write_bytes(b"lexeditor item fixture")
    other_item = alternate / "StreamingAssets/Data/Items/Items.csv"
    other_item.parent.mkdir(parents=True); other_item.write_bytes(b"external item fixture")
    walkmesh = project / "StreamingAssets/Assets/Resources/FieldMaps/FBG_N21_TEST/FBG_N21_TEST.bgi.bytes"
    walkmesh.parent.mkdir(parents=True); walkmesh.write_bytes(b"lexeditor walkmesh fixture")
    other_walkmesh = alternate / "StreamingAssets/Assets/Resources/FieldMaps/FBG_N21_TEST/FBG_N21_TEST.bgi.bytes"
    other_walkmesh.parent.mkdir(parents=True); other_walkmesh.write_bytes(b"external walkmesh fixture")

    # Real Ukrainian package family: StreamingAssets/Assets/Resources/FieldMaps.
    title = project / "StreamingAssets/Assets/Resources/FieldMaps/FIELD/Title_11.png"
    title.parent.mkdir(parents=True); title.write_bytes(b"lexeditor art fixture")
    other_title = ukrainian / "StreamingAssets/Assets/Resources/FieldMaps/FIELD/Title_11.png"
    other_title.parent.mkdir(parents=True); other_title.write_bytes(b"translation art fixture")

    # Real Dualsense package uses FF9_Data/EmbeddedAsset UI atlases, so it does
    # not collide with these project paths.
    ui = dualsense / "FF9_Data/EmbeddedAsset/UI/Atlas/Icon Atlas"
    ui.parent.mkdir(parents=True); ui.write_bytes(b"controller atlas fixture")

    report = mod_compat.audit(game, project)
    assert report["lexeditorRuntimePriority"] == 0
    assert report["lexeditorLauncherPriority"] == 0
    assert report["mergeScripts"] is True

    unsupported = {row["name"]: row["minimumMemoriaVersion"]
                   for row in report["unsupportedByPinnedMemoria"]}
    assert unsupported == {"CostumePack": "2026.07.21"}

    conflicts = {frozenset(row["mods"]) for row in report["declaredConflicts"]}
    assert frozenset({"Alternate Fantasy", "Trance Seek"}) in conflicts

    overlaps = {(row["mod"], row["path"]) for row in report["overlaps"]}
    assert ("Alternate Fantasy", "StreamingAssets/Data/Items/Items.csv") in overlaps
    assert ("Alternate Fantasy", "StreamingAssets/Assets/Resources/FieldMaps/FBG_N21_TEST/FBG_N21_TEST.bgi.bytes") in overlaps
    assert ("Ukrainian Translation", "StreamingAssets/Assets/Resources/FieldMaps/FIELD/Title_11.png") in overlaps
    assert not any(name == "Dualsense Buttons" for name, _ in overlaps)

    # Audit is read-only: external mod bytes are unchanged.
    assert other_item.read_bytes() == b"external item fixture"
    assert other_walkmesh.read_bytes() == b"external walkmesh fixture"
    assert other_title.read_bytes() == b"translation art fixture"
    assert ui.read_bytes() == b"controller atlas fixture"
    assert trance.joinpath("ModDescription.xml").is_file()
    assert costume.joinpath("ModDescription.xml").is_file()


def test_real_style_submod_paths_use_parent_metadata(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    game.mkdir(); project.mkdir()
    root = write_mod(game, "Chocobo Hot and Cold", description(
        "Chocobo Hot and Cold QoL", version="2.5"))
    sub = root / "Chocographer/StreamingAssets/assets/resources/commonasset/eventengine/eventbinary/field/us"
    sub.mkdir(parents=True)
    (sub / "evt_choco_ch_fst_0.eb.bytes").write_bytes(b"event fixture")
    (game / "Memoria.ini").write_text(
        '[Mod]\nFolderNames = "Chocobo Hot and Cold/Chocographer"\nPriorities = "Chocobo Hot and Cold"\n',
        encoding="utf-8",
    )
    report = mod_compat.audit(game, project)
    assert len(report["mods"]) == 1
    assert report["mods"][0]["name"] == "Chocobo Hot and Cold QoL"
    assert report["mods"][0]["activePaths"] == ["Chocobo Hot and Cold/Chocographer"]


def test_malformed_or_unsafe_external_metadata_is_reported_not_executed(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    game.mkdir(); project.mkdir()
    bad = game / "BadMod"; bad.mkdir()
    (bad / "ModDescription.xml").write_text("<Mod><Name>broken", encoding="utf-8")
    (game / "Memoria.ini").write_text(
        '[Mod]\nFolderNames = "BadMod", "../outside"\n',
        encoding="utf-8",
    )
    report = mod_compat.audit(game, project)
    by_folder = {row["folder"]: row for row in report["mods"]}
    assert by_folder["BadMod"]["metadata"] is False
    assert "error" in by_folder["BadMod"]
    assert by_folder[".."]["metadata"] is False or by_folder.get("../outside", {}).get("metadata") is False


def test_no_memoria_ini_is_an_empty_non_mutating_report(tmp_path):
    report = mod_compat.audit(tmp_path / "game", tmp_path / "project")
    assert report["folderNames"] == []
    assert report["mods"] == []
    assert report["declaredConflicts"] == []
    assert report["overlaps"] == []


def test_shared_mod_loading_metadata_uses_canonical_ff9_entry():
    root = Path(__file__).parents[1]
    data = json.loads((root / "ui/mod-loading.json").read_text(encoding="utf-8"))
    assert "ff9" not in data, "FF9 metadata belongs under plugins, not as a second top-level entry"
    ff9 = data["plugins"]["ff9"]
    assert "highest priority first" in ff9["overriding"]
    assert "walkmesh" in ff9["overriding"].lower()
    assert "Priorities" in ff9["overriding"]
    assert "MergeScripts" in ff9["overriding"]
    assert "newer than Lexeditor's pinned" in ff9["loader"]


@pytest.mark.parametrize("folder,name,minimum,supported", [
    ("DualsenseButtons", "Dualsense Buttons", "", None),
    ("TranslationUkr", "Ukrainian Translation", "2024-11-17", True),
    ("AlternateFantasy", "Alternate Fantasy", "2025-05-11", True),
    ("CostumePack", "CostumePack", "2026.07.21", False),
])
def test_real_catalog_examples_in_isolation(tmp_path, folder, name, minimum, supported):
    game, project = tmp_path / "game", tmp_path / "project"
    game.mkdir(); project.mkdir()
    write_mod(game, folder, description(name, minimum=minimum))
    (game / "Memoria.ini").write_text(
        f'[Mod]\nFolderNames = "{folder}"\nPriorities = "{folder}"\n',
        encoding="utf-8",
    )
    report = mod_compat.audit(game, project)
    assert len(report["mods"]) == 1
    assert report["mods"][0]["name"] == name
    assert report["mods"][0]["supportedByPinnedMemoria"] is supported
    if supported is None:
        assert report["mods"][0]["runtimeCompatibility"] == "unknown"
        assert report["unknownRuntimeCompatibility"] == [{"name": name, "folder": folder}]
    assert report["declaredConflicts"] == []
    assert report["overlaps"] == []


def test_unparseable_minimum_memoria_version_fails_closed(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    game.mkdir(); project.mkdir()
    write_mod(game, "UnknownRuntimeMod", description(
        "Unknown Runtime Mod", minimum="latest"))
    (game / "Memoria.ini").write_text(
        '[Mod]\nFolderNames = "UnknownRuntimeMod"\n',
        encoding="utf-8",
    )
    report = mod_compat.audit(game, project)
    mod = report["mods"][0]
    assert mod["minimumMemoriaVersionValid"] is False
    assert mod["supportedByPinnedMemoria"] is False
    assert report["unsupportedByPinnedMemoria"][0]["reason"] == "invalid MinimumMemoriaVersion metadata"


def test_unquoted_comma_is_one_compatibility_path(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    game.mkdir(); project.mkdir()
    folder = write_mod(game, "OtherMod, SecondMod", description("Comma Named Mod"))
    (game / "Memoria.ini").write_text(
        "[Mod]\nFolderNames = OtherMod, SecondMod\n",
        encoding="utf-8",
    )
    report = mod_compat.audit(game, project)
    assert report["folderNames"] == ["OtherMod, SecondMod"]
    assert [mod["name"] for mod in report["mods"]] == ["Comma Named Mod"]
