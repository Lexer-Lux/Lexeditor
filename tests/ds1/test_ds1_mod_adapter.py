"""Switching DS1 mods in the Mods tab installs exactly the switched-on set.

The adapter combines every enabled data mod over the game's own archives,
puts the originals back when none is left, and reports each mod's
conflicts by folder for the red mark on its row. Synthetic files only.
"""
import hashlib
import json

import pytest

from ds1_fixture import make_archive
from plugins.ds1 import deployment, exe_patches, tweak_mods
from plugins.ds1.formats import ItemDocument
from plugins.ds1.mod_support import Ds1ModAdapter
from plugins.ds1.store import MARKER, RELATIVE
from test_ds1_exe_patches import VANILLA as EXE

VANILLA = make_archive()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(exe_patches, "VANILLA_SIZE", len(EXE))
    monkeypatch.setattr(exe_patches, "VANILLA_SHA256", hashlib.sha256(EXE).hexdigest())
    monkeypatch.setattr(tweak_mods, "ensure_game_closed", lambda: None)
    game, library = tmp_path / "game", tmp_path / "library"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(VANILLA)
    (game / exe_patches.EXECUTABLE).write_bytes(EXE)
    library.mkdir()
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=library, game_root=game)
    return game, library, adapter


def data_mod(library, name, order, *edits):
    folder = library / name
    (folder / RELATIVE).parent.mkdir(parents=True)
    (folder / MARKER).write_text("project", encoding="utf-8")
    document = ItemDocument(VANILLA)
    for table, row, key, value in edits:
        document.edit(table, row, key, value)
    (folder / RELATIVE).write_bytes(document.export())
    (folder / "mod.json").write_text(json.dumps({"name": name, "order": order, "enabled": True}), encoding="utf-8")
    return folder


def installed(game, key):
    return ItemDocument((game / RELATIVE).read_bytes()).value("EquipParamGoods", 100, key)


def test_two_mods_install_together_and_switching_both_off_restores_the_game(setup):
    game, library, adapter = setup
    a = data_mod(library, "A", 1, ("EquipParamGoods", 100, "sellValue", 42))
    b = data_mod(library, "B", 2, ("EquipParamGoods", 100, "maxNum", 7))
    result = adapter.activate([a, b], game)
    assert result["dataMods"] == ["A", "B"] and result["conflicts"] == 0
    assert (installed(game, "sellValue"), installed(game, "maxNum")) == (42, 7)
    adapter.activate([b], game)
    assert (installed(game, "sellValue"), installed(game, "maxNum")) == (0, 7)
    adapter.activate([], game)
    assert (game / RELATIVE).read_bytes() == VANILLA
    assert deployment.status(game, None)["enabled"] is False


def test_conflicts_are_reported_by_mod_folder(setup):
    game, library, adapter = setup
    a = data_mod(library, "A", 1, ("EquipParamGoods", 100, "sellValue", 1))
    b = data_mod(library, "B", 2, ("EquipParamGoods", 100, "sellValue", 2))
    found = adapter.conflicts([a, b], game)
    assert set(found) == {str(a.resolve()), str(b.resolve())}
    assert "B changes this too" in found[str(a.resolve())][0]
    assert adapter.conflicts([a], game) == {}


def test_conflicts_reuse_the_composition_across_a_reorder(setup, monkeypatch):
    from core import mods_service
    from plugins.ds1 import mod_loader
    game, library, adapter = setup
    a = data_mod(library, "A", 1, ("EquipParamGoods", 100, "sellValue", 1))
    b = data_mod(library, "B", 2, ("EquipParamGoods", 100, "sellValue", 2))
    reads = []
    real_read = mod_loader.read_mod

    def counting(folder, name):
        reads.append(name)
        return real_read(folder, name)

    monkeypatch.setattr(mod_loader, "read_mod", counting)
    first = adapter.conflicts([a, b], game)
    assert "B changes this too" in first[str(a.resolve())][0]
    assert len(reads) == 2
    # Reordering only rewrites mod.json order keys: no file is re-read,
    # and the winner flips to the mod that now loads later.
    mods_service.move(library, str(b), -1)
    second = adapter.conflicts([b, a], game)
    assert len(reads) == 2
    assert "A changes this too" in second[str(b.resolve())][0]
    # The cached lines match a fresh composition exactly.
    fresh = Ds1ModAdapter()
    fresh.attach_context(library_root=library, game_root=game)
    assert fresh.conflicts([b, a], game) == second


def test_conflicts_recompute_when_mod_content_changes(setup, monkeypatch):
    from plugins.ds1 import mod_loader
    game, library, adapter = setup
    a = data_mod(library, "A", 1, ("EquipParamGoods", 100, "sellValue", 1))
    b = data_mod(library, "B", 2, ("EquipParamGoods", 100, "sellValue", 2))
    reads = []
    real_read = mod_loader.read_mod

    def counting(folder, name):
        reads.append(name)
        return real_read(folder, name)

    monkeypatch.setattr(mod_loader, "read_mod", counting)
    adapter.conflicts([a, b], game)
    assert len(reads) == 2
    assert adapter.conflicts([a, b], game) == adapter.conflicts([a, b], game)
    assert len(reads) == 2
    # A new file in a mod is a content change, whatever the clock says.
    (a / "map").mkdir(exist_ok=True)
    (a / "map" / "m10_00_00_00.msb").write_bytes(b"map-bytes")
    adapter.conflicts([a, b], game)
    assert len(reads) == 4


def test_a_folder_without_mod_files_is_refused_on_import(setup):
    _game, library, adapter = setup
    assert not adapter.inspect(library, [])["valid"]
    assert adapter.inspect(library, [RELATIVE])["valid"]


def test_library_message_says_what_switching_does():
    """The Mod Library status line names the action, not the machinery.

    Lexer quoted the old "combines ... field by field" line back with
    "WHAT?????". The line must say what switching does and that the game
    must be closed, without loader internals.
    """
    message = Ds1ModAdapter.message
    assert "Switch mods on or off" in message
    assert "Close the game before switching" in message
    for jargon in ("field by field", "placement by placement",
                   "member by member", "executable", "binder"):
        assert jargon not in message
