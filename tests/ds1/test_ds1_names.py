"""DS1 items are renamed in the game's own text, which a mod carries and
deploys beside its parameters.

Lexer: "I can't rename items ... is there some technical reason you can't
rename things in DS1". The in-game name is not in the parameter row; it is in
msg/ENGLISH/item.msgbnd.dcx, which Lexeditor now reads, writes and deploys.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_text_archive  # noqa: E402
from plugins.ds1 import deployment, texts  # noqa: E402
from plugins.ds1.formats import FormatError  # noqa: E402
from plugins.ds1.store import ItemStore, MARKER, RELATIVE  # noqa: E402


@pytest.fixture()
def game(tmp_path):
    root = tmp_path / "game"
    (root / RELATIVE).parent.mkdir(parents=True)
    (root / RELATIVE).write_bytes(make_archive())
    (root / texts.RELATIVE).parent.mkdir(parents=True)
    (root / texts.RELATIVE).write_bytes(make_text_archive())
    return root


@pytest.fixture()
def mod(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    (root / MARKER).touch()
    return root


def test_an_unchanged_text_archive_writes_back_its_exact_bytes():
    source = make_text_archive()
    assert texts.TextDocument(source).export() == source


def test_a_rename_changes_every_copy_and_nothing_else():
    document = texts.TextDocument(make_text_archive())
    document.rename("EquipParamGoods", 100, "Soul Safety Stone")
    assert document.dirty == {("EquipParamGoods", 100)}
    reread = texts.TextDocument(document.export())
    assert reread.name("EquipParamGoods", 100) == "Soul Safety Stone"
    assert reread.name("EquipParamGoods", 101) == "Fixture Key"
    assert reread.name("EquipParamWeapon", 100) == "Fixture Sword"
    copies = [position for position in reread.tables if reread._file(position) == "Item_name_.fmg"]
    assert len(copies) == 2
    assert all(reread.tables[position][1][100] == "Soul Safety Stone" for position in copies)


def test_an_item_with_no_name_yet_can_be_given_one():
    document = texts.TextDocument(make_text_archive())
    document.rename("Magic", 100, "New Spell")
    assert texts.TextDocument(document.export()).name("Magic", 100) == "New Spell"


@pytest.mark.parametrize("name", ["", "   ", "two\nlines", "x" * (texts.MAX_NAME + 1)])
def test_a_bad_name_is_refused(name):
    with pytest.raises(FormatError):
        texts.TextDocument(make_text_archive()).rename("EquipParamGoods", 100, name)


def test_the_store_shows_game_names_and_saves_a_rename_into_the_mod(game, mod):
    store = ItemStore(game, mod, read_only=False)
    rows = {row["id"]: row for row in store.get().list_rows("consumables")}
    assert rows[100]["name"] == "Fixture Stone"
    assert store.get().read_row("EquipParamGoods", 100)["renamable"] is True
    assert store.get().read_row("NpcParam", 120000)["renamable"] is False
    with pytest.raises(FormatError):
        store.rename("NpcParam", 120000, "Big Rat")
    store.rename("EquipParamGoods", 100, "Soul Safety Stone")
    assert store.get().dirty_count == 1
    assert not (mod / texts.RELATIVE).exists(), "nothing is written before Save"
    store.save()
    assert (mod / texts.RELATIVE).is_file()
    reopened = ItemStore(game, mod, read_only=False)
    assert reopened.get().read_row("EquipParamGoods", 100)["name"] == "Soul Safety Stone"
    assert reopened.get().dirty_count == 0
    assert (game / texts.RELATIVE).read_bytes() == make_text_archive(), "the game is untouched until Apply"


def test_a_mod_without_renames_carries_no_text(game, mod):
    store = ItemStore(game, mod, read_only=False)
    store.edit("EquipParamGoods", 100, "sortId", 5)
    store.save()
    assert not (mod / texts.RELATIVE).exists()


def test_apply_installs_both_files_and_restore_puts_both_back(game, mod):
    store = ItemStore(game, mod, read_only=False)
    store.rename("EquipParamGoods", 100, "Soul Safety Stone")
    store.save()
    applied = deployment.apply(game, mod)
    assert applied["enabled"] and applied["texts"]["enabled"] and not applied["stale"]
    assert texts.TextDocument((game / texts.RELATIVE).read_bytes()).name("EquipParamGoods", 100) == "Soul Safety Stone"
    # Renaming again makes the installed copy out of date until reapplied.
    store.rename("EquipParamGoods", 100, "Soul Safer Stone")
    store.save()
    assert deployment.status(game, mod)["stale"]
    deployment.disable(game)
    assert (game / texts.RELATIVE).read_bytes() == make_text_archive()
    assert (game / RELATIVE).read_bytes() == make_archive()


def test_vanilla_names_come_from_the_preserved_original_once_applied(game, mod):
    store = ItemStore(game, mod, read_only=False)
    store.rename("EquipParamGoods", 100, "Soul Safety Stone")
    store.save()
    deployment.apply(game, mod)
    vanilla = ItemStore(game, None, read_only=True)
    assert vanilla.get().read_row("EquipParamGoods", 100)["name"] == "Fixture Stone"
