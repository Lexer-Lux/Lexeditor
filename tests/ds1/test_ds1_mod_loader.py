"""The DS1 mod loader combines every enabled mod over the game's own files.

Two mods changing different fields of one row both apply; two mods setting
the same field to different values conflict, and the later one is used. A
bitfield is merged by its own bits. A change that cannot be merged by field
(a row added, a table that is not a PARAM) takes the whole table from the
last mod. Synthetic archives only.
"""
from pathlib import Path

import pytest

from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import mod_loader, texts
from plugins.ds1.formats import FormatError, ItemDocument, inflate, deflate, members, schema
from plugins.ds1.store import MARKER, RELATIVE

VANILLA = make_archive()
NAMES = make_text_archive()
GAME = {RELATIVE: VANILLA, texts.RELATIVE: NAMES}


def test_asset_binder_additions_compose_with_existing_member_edits():
    from dataclasses import replace
    relative = Path('sfx/common.ffxbnd.dcx')
    plain = inflate(VANILLA)
    base = texts.bnd3_entries(plain)
    a = texts.build_bnd3(plain, base + [texts.Entry(90001, 'model/new.flver', 0x40, b'model')])
    b = texts.build_bnd3(plain, [replace(e, data=b'changed') if e.name.endswith('Untouched.bin') else e
                               for e in base] + [texts.Entry(90002, 'tex/new.tpf', 0x40, b'texture')])
    result = mod_loader.compose({relative: VANILLA}, [
        mod_loader.Mod('A', Path('a'), {relative: deflate(VANILLA, a)}),
        mod_loader.Mod('B', Path('b'), {relative: deflate(VANILLA, b)})])
    assert not result.conflicts
    entries = {e.name.replace('\\', '/').rsplit('/', 1)[-1]: e.data
               for e in texts.bnd3_entries(inflate(result.files[relative]))}
    assert entries['new.flver'] == b'model' and entries['new.tpf'] == b'texture'
    assert entries['Untouched.bin'] == b'changed'


def test_asset_binder_member_removal_conflicts_with_an_edit():
    from dataclasses import replace
    relative = Path('sfx/common.ffxbnd.dcx')
    plain = inflate(VANILLA)
    base = texts.bnd3_entries(plain)
    a = texts.build_bnd3(plain, [e for e in base if not e.name.endswith('Untouched.bin')])
    b = texts.build_bnd3(plain, [replace(e, data=b'changed') if e.name.endswith('Untouched.bin') else e for e in base])
    result = mod_loader.compose({relative: VANILLA}, [
        mod_loader.Mod('A', Path('a'), {relative: deflate(VANILLA, a)}),
        mod_loader.Mod('B', Path('b'), {relative: deflate(VANILLA, b)})])
    assert [(c.part, c.mods) for c in result.conflicts] == [('Untouched.bin', ['A', 'B'])]


def test_dcx_callers_can_set_a_bounded_asset_size_limit():
    size = len(inflate(VANILLA))
    with pytest.raises(FormatError, match='length'):
        inflate(VANILLA, max_size=size-1)
    assert len(inflate(VANILLA, max_size=size)) == size


@pytest.mark.parametrize('conflicting', [False, True])
def test_added_asset_members_preserve_esd_state_composition(conflicting):
    from copy import deepcopy
    from plugins.ds1 import esd
    relative = Path('script/talk/example.talkesdbnd.dcx')
    def option(text):
        return esd.Command(1, 19, [esd.assemble(str(value)) for value in (1, text, -1)])
    base_script = esd.Esd(state_groups={1: {0: esd.State(id=0, entry_commands=[option(1500)])}})
    a, b = deepcopy(base_script), deepcopy(base_script)
    a.state_groups[1][1] = esd.State(id=1)
    if conflicting:
        a.state_groups[1][0].entry_commands = [option(1501)]
    b.state_groups[1][0].entry_commands = [option(1502)]
    template = inflate(VANILLA)
    base_entries = [texts.Entry(1, 'talk.esd', 0x40, base_script.to_bytes())]
    vanilla = deflate(VANILLA, texts.build_bnd3(template, base_entries))
    variant_a = deflate(VANILLA, texts.build_bnd3(template, [
        texts.Entry(1, 'talk.esd', 0x40, a.to_bytes()), texts.Entry(2, 'new.bin', 0x40, b'new')]))
    variant_b = deflate(VANILLA, texts.build_bnd3(template, [texts.Entry(1, 'talk.esd', 0x40, b.to_bytes())]))
    merged = mod_loader.compose({relative: vanilla}, [
        mod_loader.Mod('A', Path('a'), {relative: variant_a}),
        mod_loader.Mod('B', Path('b'), {relative: variant_b})])
    assert bool(merged.conflicts) == conflicting
    entries = texts.bnd3_entries(inflate(merged.files[relative]))
    script = esd.parse(next(e.data for e in entries if e.name == 'talk.esd'))
    assert 1 in script.state_groups[1]
    assert script.state_groups[1][0].entry_commands == b.state_groups[1][0].entry_commands


def edited(*edits):
    document = ItemDocument(VANILLA)
    for table, row, key, value in edits:
        document.edit(table, row, key, value)
    return document.export()


def renamed(*renames):
    document = texts.TextDocument(NAMES)
    for table, row, name in renames:
        document.rename(table, row, name)
    return document.export()


def mod(name, params=None, names=None, menu=None):
    files = {}
    if params is not None:
        files[RELATIVE] = params
    if names is not None:
        files[texts.RELATIVE] = names
    if menu is not None:
        files[texts.MENU_RELATIVE] = menu
    return mod_loader.Mod(name, Path(name), files)


def value(archive, table, row, key):
    return ItemDocument(archive).value(table, row, key)


def test_no_mods_change_nothing_and_one_mod_is_its_own_bytes():
    assert mod_loader.compose(GAME, []).files == {}
    alone = mod("A", edited(("EquipParamGoods", 100, "sellValue", 42)), renamed(("EquipParamGoods", 100, "Stone")))
    result = mod_loader.compose(GAME, [alone])
    assert result.files == alone.files and result.conflicts == []


def test_different_fields_of_one_row_both_apply():
    a = mod("A", edited(("EquipParamGoods", 100, "sellValue", 42)))
    b = mod("B", edited(("EquipParamGoods", 100, "maxNum", 7)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert value(result.files[RELATIVE], "EquipParamGoods", 100, "sellValue") == 42
    assert value(result.files[RELATIVE], "EquipParamGoods", 100, "maxNum") == 7


def test_the_same_field_conflicts_and_the_later_mod_is_used():
    a = mod("A", edited(("EquipParamGoods", 100, "sellValue", 7)))
    b = mod("B", edited(("EquipParamGoods", 100, "sellValue", 11)))
    result = mod_loader.compose(GAME, [a, b])
    # Not a blend of the two numbers' bits: B's value, whole.
    assert value(result.files[RELATIVE], "EquipParamGoods", 100, "sellValue") == 11
    assert [(c.part, c.mods) for c in result.conflicts] == [("Items 100, " + label("EquipParamGoods", "sellValue"), ["A", "B"])]
    lines = result.by_mod([a, b])
    assert "B changes this too and loads later" in lines["A"][0] and "overrides A" in lines["B"][0]


def test_the_same_value_from_two_mods_is_no_conflict():
    a = mod("A", edited(("EquipParamGoods", 100, "sellValue", 9)))
    b = mod("B", edited(("EquipParamGoods", 100, "sellValue", 9)))
    assert mod_loader.compose(GAME, [a, b]).conflicts == []


def test_bitfields_sharing_a_byte_merge_by_their_own_bits():
    first, second = two_bits_in_one_byte("EquipParamGoods")
    a = mod("A", edited(("EquipParamGoods", 101, first, 1)))
    b = mod("B", edited(("EquipParamGoods", 101, second, 1)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert value(result.files[RELATIVE], "EquipParamGoods", 101, first) == 1
    assert value(result.files[RELATIVE], "EquipParamGoods", 101, second) == 1


def test_a_member_that_is_not_a_param_is_taken_whole_from_the_last_mod():
    def with_member(payload):
        plain = bytearray(inflate(VANILLA))
        entry = members(plain)["Untouched.bin"]
        plain[entry.offset:entry.offset + entry.size] = payload
        return deflate(VANILLA, bytes(plain))
    a = mod("A", with_member(b"A-version payloa"[:18].ljust(18, b"!")))
    b = mod("B", with_member(b"B-version payloa"[:18].ljust(18, b"?")))
    result = mod_loader.compose(GAME, [a, b])
    plain = inflate(result.files[RELATIVE])
    entry = members(plain)["Untouched.bin"]
    assert plain[entry.offset:entry.offset + entry.size] == inflate(b.files[RELATIVE])[entry.offset:entry.offset + entry.size]
    assert [(c.part, c.mods) for c in result.conflicts] == [("Untouched.bin (whole table)", ["A", "B"])]


def test_item_names_merge_by_entry_and_conflict_on_the_same_one():
    a = mod("A", names=renamed(("EquipParamGoods", 100, "Alpha"), ("EquipParamWeapon", 100, "Blade")))
    b = mod("B", names=renamed(("EquipParamGoods", 101, "Beta"), ("EquipParamWeapon", 100, "Sword of B")))
    result = mod_loader.compose(GAME, [a, b])
    names = texts.TextDocument(result.files[texts.RELATIVE])
    assert names.name("EquipParamGoods", 100) == "Alpha" and names.name("EquipParamGoods", 101) == "Beta"
    assert names.name("EquipParamWeapon", 100) == "Sword of B"
    assert [c.mods for c in result.conflicts] == [["A", "B"]]


PLACE = {"Place_name_.fmg": {2000: "Firelink Shrine", 2003: "Chamber of the Princess"}}


def placed(archive):
    """Every copy of Place_name_ in the archive; they must always agree."""
    document = texts.TextDocument(archive)
    copies = [document.tables[position][1] for position, entry in enumerate(document.entries)
              if entry.name.rsplit(chr(92), 1)[-1] == "Place_name_.fmg"]
    assert copies, "the archive carries no Place_name_ table"
    assert all(copy == copies[0] for copy in copies), "Place_name_ copies disagree"
    return copies[0]


def test_place_names_merge_by_entry_and_conflict_on_the_same_one():
    game = {RELATIVE: VANILLA, texts.RELATIVE: make_text_archive(extra=dict(PLACE))}
    a = mod("A", names=make_text_archive(extra={"Place_name_.fmg": {2000: "Firelink Shrine", 2003: "Chamber (Anor Londo)"}}))
    b = mod("B", names=make_text_archive(extra={"Place_name_.fmg": {2000: "Firelink!", 2003: "Chamber of the Princess"}}))
    result = mod_loader.compose(game, [a, b])
    merged = placed(result.files[texts.RELATIVE])
    assert merged[2000] == "Firelink!" and merged[2003] == "Chamber (Anor Londo)"
    assert [(c.part, c.mods) for c in result.conflicts] == []


def test_the_same_place_name_conflicts_and_the_later_mod_is_used():
    game = {RELATIVE: VANILLA, texts.RELATIVE: make_text_archive(extra=dict(PLACE))}
    a = mod("A", names=make_text_archive(extra={"Place_name_.fmg": {2000: "Firelink A", 2003: "Chamber of the Princess"}}))
    b = mod("B", names=make_text_archive(extra={"Place_name_.fmg": {2000: "Firelink B", 2003: "Chamber of the Princess"}}))
    result = mod_loader.compose(game, [a, b])
    assert placed(result.files[texts.RELATIVE])[2000] == "Firelink B"
    assert [(c.part, c.mods) for c in result.conflicts] == [("Name 2000 (Place name)", ["A", "B"])]


def test_archives_without_place_names_merge_as_before():
    document = texts.TextDocument(NAMES)
    assert all(document._file(position) != "Place_name_.fmg" for position in document.tables)
    alone = mod("A", names=renamed(("EquipParamGoods", 100, "Stone")))
    result = mod_loader.compose(GAME, [alone])
    assert result.files == alone.files and result.conflicts == []


def test_a_library_lists_enabled_data_mods_in_order_and_the_open_project(tmp_path):
    import json
    for name, order, enabled in (("Late", 20, True), ("Early", 10, True), ("Off", 5, False), ("Open", 30, False)):
        folder = tmp_path / name
        (folder / RELATIVE).parent.mkdir(parents=True)
        (folder / MARKER).write_text("project", encoding="utf-8")
        (folder / RELATIVE).write_bytes(VANILLA)
        (folder / "mod.json").write_text(json.dumps({"name": name, "order": order, "enabled": enabled}), encoding="utf-8")
    (tmp_path / "Tweak").mkdir()
    (tmp_path / "Tweak" / "mod.json").write_text(json.dumps({"name": "Tweak", "enabled": True}), encoding="utf-8")
    names = [mod.name for mod in mod_loader.active_mods(tmp_path, tmp_path / "Open")]
    assert names == ["Early", "Late", "Open"]


def label(table, key):
    return next(item["spec"].label for item in schema(table)["fields"] if item["spec"].key == key)


def two_bits_in_one_byte(table):
    fields = [item for item in schema(table)["fields"] if item["editable"] and item["spec"].bit_size == 1]
    for item in fields:
        for other in fields:
            if other is not item and other["spec"].offset == item["spec"].offset:
                return item["spec"].key, other["spec"].key
    pytest.skip(f"{table} has no two editable one-bit fields in one byte")


# --- Rows added and removed ---------------------------------------------------
# Armor Rework adds thousands of effect rows and Repair Rework changes effect
# rows; taking that table whole from the last mod threw the other mod's
# effects away. Rows now merge by id. The fixture's tables are first laid out
# the way the game's own are (the writer rebuilds every real table exactly).

def game_layout(archive):
    plain = inflate(archive)
    entries = []
    for entry in texts.bnd3_entries(plain):
        spans = mod_loader._row_spans(entry.data)
        data = entry.data
        if spans:
            size = spans[0][1] - spans[0][0]
            data = mod_loader._write_table(entry.data, size, mod_loader._table_rows(entry.data, size), b"")
        entries.append(texts.Entry(entry.member_id, entry.name, entry.flags, data))
    return deflate(archive, texts.build_bnd3(plain, entries))


GAME_LAYOUT = game_layout(VANILLA)


def with_table(archive, table, change):
    """The archive with one table's payload passed through change(payload)."""
    plain = inflate(archive)
    entries = [texts.Entry(e.member_id, e.name, e.flags,
                           change(e.data) if e.name.replace("\\", "/").rsplit("/", 1)[-1] == f"{table}.param" else e.data)
               for e in texts.bnd3_entries(plain)]
    return deflate(archive, texts.build_bnd3(plain, entries))


def added(archive, table, *copies):
    """Rows appended the way a mod tool adds them: (source id, new id, name)."""
    from plugins.ds3.formats import ParamView
    def change(payload):
        for source, new, name in copies:
            view = ParamView(payload)
            payload = view.copy_row(source, new, name, mod_loader._row_spans(payload)[0][1] - mod_loader._row_spans(payload)[0][0])
        return payload
    return with_table(archive, table, change)


def test_rows_two_mods_add_to_one_table_are_all_kept():
    game = {RELATIVE: GAME_LAYOUT}
    a = mod("A", added(GAME_LAYOUT, "EquipParamGoods", (100, 150, "A one"), (101, 900, "A two")))
    b = mod("B", added(GAME_LAYOUT, "EquipParamGoods", (102, 101500, "B one")))
    c_doc = ItemDocument(GAME_LAYOUT)
    c_doc.edit("EquipParamGoods", 100, "sellValue", 77)
    c = mod("C", c_doc.export())
    for order in ([a, b, c], [c, b, a]):
        result = mod_loader.compose(game, order)
        assert result.conflicts == []
        document = ItemDocument(result.files[RELATIVE])
        ids = [row.row_id for row in document.params["EquipParamGoods"].rows]
        assert ids == [100, 101, 102, 150, 900, 101500]
        assert document.value("EquipParamGoods", 100, "sellValue") == 77
        assert document.value("EquipParamGoods", 900, "sellValue") == ItemDocument(GAME_LAYOUT).value("EquipParamGoods", 101, "sellValue")


def test_rows_the_same_new_id_added_differently_conflicts_and_the_later_mod_is_used():
    game = {RELATIVE: GAME_LAYOUT}
    a = mod("A", added(GAME_LAYOUT, "EquipParamGoods", (100, 150, "A")))
    b = mod("B", added(GAME_LAYOUT, "EquipParamGoods", (101, 150, "B")))
    result = mod_loader.compose(game, [a, b])
    assert [(c.part, c.mods) for c in result.conflicts] == [("Items 150 (added by both)", ["A", "B"])]
    document = ItemDocument(result.files[RELATIVE])
    assert document.value("EquipParamGoods", 150, "sellValue") == ItemDocument(GAME_LAYOUT).value("EquipParamGoods", 101, "sellValue")


def test_rows_a_removed_row_another_mod_changes_conflicts():
    game = {RELATIVE: GAME_LAYOUT}
    def without_102(payload):
        size = mod_loader._row_spans(payload)[0][1] - mod_loader._row_spans(payload)[0][0]
        rows = [row for row in mod_loader._table_rows(payload, size) if row[0] != 102]
        return mod_loader._write_table(payload, size, rows, b"")
    a = mod("A", with_table(GAME_LAYOUT, "EquipParamGoods", without_102))
    b_doc = ItemDocument(GAME_LAYOUT)
    b_doc.edit("EquipParamGoods", 102, "sellValue", 5)
    b = mod("B", b_doc.export())
    result = mod_loader.compose(game, [b, a])
    assert [(c.part, c.mods) for c in result.conflicts] == [("Items 102 (removed by one, changed by another)", ["B", "A"])]
    assert 102 not in [row.row_id for row in ItemDocument(result.files[RELATIVE]).params["EquipParamGoods"].rows]

def test_player_attacks_merge_by_field_and_conflict_by_name():
    a = mod("A", edited(("AtkParam_Pc", 100, "atkPhys", 111)))
    b = mod("B", edited(("AtkParam_Pc", 100, "atkMag", 222)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    merged = ItemDocument(result.files[RELATIVE])
    assert merged.value("AtkParam_Pc", 100, "atkPhys") == 111
    assert merged.value("AtkParam_Pc", 100, "atkMag") == 222
    c = mod("C", edited(("AtkParam_Pc", 100, "atkPhys", 333)))
    result = mod_loader.compose(GAME, [a, c])
    assert [(c.part, c.mods) for c in result.conflicts] == [("Player attacks 100, Physical (%)", ["A", "C"])]
    assert ItemDocument(result.files[RELATIVE]).value("AtkParam_Pc", 100, "atkPhys") == 333

def test_reinforce_rows_merge_by_field_and_conflict_by_name():
    a = mod("A", edited(("ReinforceParamWeapon", 100, "physicsAtkRate", 2.5)))
    b = mod("B", edited(("ReinforceParamWeapon", 100, "magicAtkRate", 3.5)))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    merged = ItemDocument(result.files[RELATIVE])
    assert merged.value("ReinforceParamWeapon", 100, "physicsAtkRate") == 2.5
    assert merged.value("ReinforceParamWeapon", 100, "magicAtkRate") == 3.5
    c = mod("C", edited(("ReinforceParamWeapon", 100, "physicsAtkRate", 4.5)))
    result = mod_loader.compose(GAME, [a, c])
    assert [(c.part, c.mods) for c in result.conflicts] == [("Weapon upgrades 100, Physical Damage (x)", ["A", "C"])]
    assert ItemDocument(result.files[RELATIVE]).value("ReinforceParamWeapon", 100, "physicsAtkRate") == 4.5


MENU = make_menu_archive()
MENUGAME = {RELATIVE: VANILLA, texts.MENU_RELATIVE: MENU}


def relabeled(*edits):
    document = texts.MenuDocument(MENU)
    for key, value in edits:
        document.set_label(key, value)
    return document.export()


def menulabels(archive):
    """Every copy of Menu_general_text_ in the archive; they must agree."""
    document = texts.MenuDocument(archive)
    copies = [document.tables[position][1] for position in document.tables
              if document._file(position) == texts.MENU_LABEL_FILE]
    assert copies, "the archive carries no Menu_general_text_ table"
    assert all(copy == copies[0] for copy in copies), "Menu_general_text_ copies disagree"
    return copies[0]


def test_menu_labels_merge_by_entry_and_conflict_on_the_same_one():
    a = mod("A", menu=relabeled(("magicDefense", "MagABS"), ("fireDefense", "FireABS")))
    b = mod("B", menu=relabeled(("lightningDefense", "LitngABS"), ("fireDefense", "FireWard")))
    result = mod_loader.compose(MENUGAME, [a, b])
    merged = menulabels(result.files[texts.MENU_RELATIVE])
    assert merged[102204] == "MagABS" and merged[102206] == "LitngABS"
    assert merged[102205] == "FireWard"
    assert [(c.file, c.part, c.mods) for c in result.conflicts] == [
        (texts.MENU_RELATIVE, "Menu label 102205 (Menu general text)", ["A", "B"])]


def test_the_same_menu_label_from_two_mods_is_no_conflict():
    a = mod("A", menu=relabeled(("magicDefense", "MagABS")))
    b = mod("B", menu=relabeled(("magicDefense", "MagABS")))
    assert mod_loader.compose(MENUGAME, [a, b]).conflicts == []


def test_menu_label_edits_write_both_copies_and_nothing_else():
    document = texts.MenuDocument(MENU)
    assert document.export() == MENU
    assert document.set_label("magicDefense", "  MagABS  ") == "MagABS"
    assert document.label("magicDefense") == "MagABS"
    assert document.original_label("magicDefense") == "MagDEF"
    assert document.dirty == {"magicDefense"}
    merged = menulabels(document.export())
    assert merged[102204] == "MagABS" and merged[102205] == "FireDEF"


def test_menu_labels_reject_blank_unknown_and_missing_tables():
    document = texts.MenuDocument(MENU)
    for bad in ("", "   ", "two\nlines", "x" * 201):
        with pytest.raises(FormatError):
            document.set_label("magicDefense", bad)
    with pytest.raises(FormatError):
        document.set_label("noSuchLabel", "X")
    with pytest.raises(FormatError):
        document.label("noSuchLabel")
    with pytest.raises(FormatError):
        texts.MenuDocument(make_menu_archive(labels=None, extra={'Other_.fmg': {1: 'x'}}, omit_labels=True))


def test_menu_labels_list_read_and_edit_as_records():
    document = ItemDocument(VANILLA)
    assert document.list_rows("menu-labels") == []
    document.menu_texts = texts.MenuDocument(MENU)
    rows = document.list_rows("menu-labels")
    assert [(row["id"], row["table"], row["name"]) for row in rows] == [
        (102204, "MenuText", "Magic defense label"),
        (102205, "MenuText", "Fire defense label"),
        (102206, "MenuText", "Lightning defense label")]
    assert rows[0]["values"] == {"label": "MagDEF"}
    row = document.read_row("MenuText", 102204)
    assert (row["name"], row["renamable"]) == ("Magic defense label", False)
    (field,) = row["fields"]
    assert (field["key"], field["type"], field["value"], field["vanilla"]) == ("label", "text", "MagDEF", "MagDEF")
    assert field["editable"] and field["maxLength"] == 200
    assert document.edit("MenuText", 102204, "label", "MagABS")["fields"][0]["value"] == "MagABS"
    assert document.dirty_count == 1
    assert document.pending_changes() == [{
        "label": "Menu label · Magic defense label", "before": "MagDEF", "after": "MagABS"}]
    document.edit("MenuText", 102204, "label", "MagDEF")
    assert document.dirty_count == 0 and document.pending_changes() == []
    with pytest.raises(FormatError):
        document.edit("MenuText", 102204, "other", "x")
    with pytest.raises(FormatError):
        document.edit("MenuText", 999999, "label", "x")
    with pytest.raises(FormatError):
        document.read_row("MenuText", 999999)
    document.menu_texts = None
    with pytest.raises(FormatError):
        document.edit("MenuText", 102204, "label", "x")

def test_records_compare_preserved_vanilla_not_deployed_live(tmp_path):
    # The Records tab compares a mod against vanilla as shipped, not the
    # live files: once another mod is applied, the live archive holds
    # its rows, and comparing against those would report its edits as
    # this mod's (the 1000-phantom-entries failure).
    from plugins.ds1 import deployment
    game, decoy, subject = tmp_path / "game", tmp_path / "decoy", tmp_path / "subject"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(VANILLA)
    for folder in (decoy, subject):
        (folder / RELATIVE).parent.mkdir(parents=True)
        (folder / MARKER).touch()
    (decoy / RELATIVE).write_bytes(edited(("EquipParamGoods", 100, "sellValue", 42)))
    deployment.apply(game, decoy)
    assert value((game / RELATIVE).read_bytes(), "EquipParamGoods", 100, "sellValue") == 42
    (subject / RELATIVE).write_bytes(edited(("EquipParamGoods", 101, "maxNum", 7)))
    reported = mod_loader.describe_changes(subject, game)
    assert [(entry["table"], entry["id"]) for entry in reported["changes"]] == [
        ("EquipParamGoods", 101)]
    assert reported["total"] == 1 and not reported["truncated"]
    assert reported["note"] == ""
