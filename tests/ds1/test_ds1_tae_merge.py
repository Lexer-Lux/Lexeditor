"""Character binders merge existing and added members independently.

Two mods changing different animation files in one binder both apply.
Two mods changing the same member conflict and the later one is used.
Synthetic binders only.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tae_fixture import build_anibnd, build_tae
from plugins.ds1 import mod_loader
from plugins.ds1.formats import inflate, members
from plugins.ds1.tae import TaeDocument
from plugins.ds1.tae_store import CHR_DIR

TAE_A = build_tae()
TAE_B = build_tae()
VANILLA = build_anibnd({"a87.tae": TAE_A, "a88.tae": TAE_B})
BINDER = CHR_DIR / "c1200.anibnd.dcx"
GAME = {BINDER: VANILLA}


def edited(member, *edits):
    document = TaeDocument(TAE_A if member == "a87.tae" else TAE_B)
    for anim, event, field, value in edits:
        document.edit(anim, event, field, value)
    members_out = {"a87.tae": TAE_A, "a88.tae": TAE_B}
    members_out[member] = document.export()
    return build_anibnd(members_out)


def mod(name, *binders):
    return mod_loader.Mod(name, Path(name), dict(binders))


def value(payload, member, anim, event, field):
    plain = inflate(payload)
    entry = members(plain)[member]
    row = TaeDocument(bytes(plain[entry.offset:entry.offset + entry.size])).read_event(anim, event)
    return next(item["value"] for item in row["fields"] if item["key"] == field)


def test_no_changes_and_single_mod_is_its_own_bytes():
    assert mod_loader.compose(GAME, []).files == {}
    alone = mod("A", (BINDER, edited("a87.tae", (0, 0, "start", 0.25))))
    result = mod_loader.compose(GAME, [alone])
    assert result.files == alone.files and result.conflicts == []


def test_different_members_both_apply():
    a = mod("A", (BINDER, edited("a87.tae", (0, 0, "start", 0.25))))
    b = mod("B", (BINDER, edited("a88.tae", (0, 0, "judge", 300))))
    result = mod_loader.compose(GAME, [a, b])
    assert result.conflicts == []
    assert value(result.files[BINDER], "a87.tae", 0, 0, "start") == 0.25
    assert value(result.files[BINDER], "a88.tae", 0, 0, "judge") == 300


def test_the_same_member_conflicts_and_the_later_mod_is_used():
    a = mod("A", (BINDER, edited("a87.tae", (0, 0, "start", 0.25))))
    b = mod("B", (BINDER, edited("a87.tae", (0, 0, "start", 0.75))))
    result = mod_loader.compose(GAME, [a, b])
    assert value(result.files[BINDER], "a87.tae", 0, 0, "start") == 0.75
    assert [(c.part, c.mods) for c in result.conflicts] == [("a87.tae", ["A", "B"])]
    lines = result.by_mod([a, b])
    assert "B changes this too and loads later" in lines["A"][0] and "overrides A" in lines["B"][0]


def test_the_same_bytes_from_two_mods_is_no_conflict():
    a = mod("A", (BINDER, edited("a87.tae", (0, 0, "judge", 200))))
    b = mod("B", (BINDER, edited("a87.tae", (0, 0, "judge", 200))))
    assert mod_loader.compose(GAME, [a, b]).conflicts == []


def test_added_members_preserve_other_mods_existing_member_edits():
    grown = build_anibnd({"a87.tae": TAE_A, "a88.tae": TAE_B, "a89.tae": TAE_A})
    b = mod("B", (BINDER, edited("a87.tae", (0, 0, "start", 0.25))))
    a = mod("A", (BINDER, grown))
    result = mod_loader.compose(GAME, [b, a])
    assert result.conflicts == []
    assert value(result.files[BINDER], "a87.tae", 0, 0, "start") == 0.25
    assert set(members(inflate(result.files[BINDER]))) == {"a87.tae", "a88.tae", "a89.tae"}
    plain = inflate(result.files[BINDER])
    added = members(plain)["a89.tae"]
    assert plain[added.offset:added.offset + added.size] == TAE_A
    foreign = mod("C", (BINDER, b"not a binder"))
    result = mod_loader.compose(GAME, [foreign])
    assert result.files[BINDER] == b"not a binder" and result.conflicts == []


def test_a_binder_missing_from_vanilla_is_taken_whole():
    extra = CHR_DIR / "c9999.anibnd.dcx"
    a = mod("A", (extra, edited("a87.tae", (0, 0, "start", 0.25))))
    result = mod_loader.compose(GAME, [a])
    assert result.files[extra] == a.files[extra] and result.conflicts == []


def test_read_mod_and_vanilla_files_find_binders(tmp_path):
    from plugins.ds1.store import MARKER
    game, folder = tmp_path / "game", tmp_path / "mod"
    (game / CHR_DIR).mkdir(parents=True)
    (game / CHR_DIR / "c1200.anibnd.dcx").write_bytes(VANILLA)
    folder.mkdir()
    (folder / MARKER).touch()
    assert mod_loader.read_mod(folder, "empty").files == {}
    (folder / CHR_DIR).mkdir(parents=True)
    (folder / CHR_DIR / "C1200.ANIBND.DCX").write_bytes(edited("a87.tae", (0, 0, "start", 0.25)))
    found = mod_loader.read_mod(folder, "chars")
    assert list(found.files) == [BINDER]
    assert mod_loader.vanilla_files(game, frozenset({BINDER})) == {BINDER: VANILLA}
    for index in range(64):
        (folder / CHR_DIR / f"c99{index:02d}.anibnd.dcx").write_bytes(VANILLA)
    try:
        mod_loader.read_mod(folder, "many")
    except ValueError as error:
        assert "too many character files" in str(error)
    else:
        raise AssertionError("Expected too many character files to fail")
