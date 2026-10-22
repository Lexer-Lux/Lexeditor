"""Memory overlaps between mods, marked in the Mods tab without enabling anything.

File conflicts come from composing archives; memory conflicts used to surface
only at enable time. core/memory_conflicts.py parses each mod's patch address
ranges statically - Hext `ADDRESS = ...` lines, or DS1's already-built native
descriptions - and the DS1 adapter reports overlaps through the same row
marks. Synthetic mods only; the game is never touched.
"""
import json

import pytest

from core import memory_conflicts, mods_service
from core.memory_conflicts import carries_native_code, exclusive_lines_by_mod, hext_ranges, overlaps
from core.mod_conflicts import MAX_LISTED
from plugins.ds1 import exe_patches, tweak_mods
from plugins.ds1.mod_support import Ds1ModAdapter, _merge_marks
from plugins.ds1.store import MARKER


def test_hext_counts_address_lines_and_skips_comments_and_unknown_lines():
    text = ("# Lexeditor: per-group initial world encounter chances\n"
            "\n"
            "541E2D = 8A 1D 61 0A\n"
            "0x541E31 = FF ; trailing comment\n"
            "   # indented comment\n"
            "; semicolon comment\n"
            "not an address line\n"
            "ZZZZ = 00\n"
            "1234 = \n"
            "1234 = 0\n")
    assert hext_ranges(text) == [(0x541E2D, 0x541E31), (0x541E31, 0x541E32)]


def test_hext_byte_runs_need_no_spaces():
    assert hext_ranges("100 = 8A1D61\n") == [(0x100, 0x103)]


def test_overlaps_name_shared_bytes_in_load_order():
    pairs = overlaps([("A", [(0x100, 0x110)]), ("B", [(0x108, 0x120)]), ("C", [(0x200, 0x210)])])
    assert pairs == [("memory 108-10F", ["A", "B"])]


def test_overlaps_touching_but_not_shared_is_no_conflict():
    assert overlaps([("A", [(0x100, 0x110)]), ("B", [(0x110, 0x120)])]) == []
    assert overlaps([("A", [(0x100, 0x101)]), ("B", [(0x100, 0x101)])]) == [("memory 100", ["A", "B"])]


def test_overlaps_never_conflicts_a_mod_with_itself_and_lists_shared_bytes_once():
    pairs = overlaps([("A", [(0x100, 0x110), (0x100, 0x110)]), ("A", [(0x105, 0x108)])])
    assert pairs == []
    pairs = overlaps([("A", [(0x100, 0x110), (0x100, 0x110)]), ("B", [(0x105, 0x108)])])
    assert pairs == [("memory 105-107", ["A", "B"])]


def test_exclusive_lines_name_the_others_from_every_side_with_no_winner():
    lines = exclusive_lines_by_mod([("memory 100", ["A", "B"])], {"A": "a", "B": "b"})
    assert lines == {"a": ["memory 100: B patches this too; only one of these mods can be on"],
                     "b": ["memory 100: A patches this too; only one of these mods can be on"]}
    lines = exclusive_lines_by_mod([("memory 100", ["A", "B", "C"])], {"A": "a", "B": "b", "C": "c"})
    assert lines["a"] == ["memory 100: B and C patch this too; only one of these mods can be on"]


def test_exclusive_lines_skip_lone_mods_count_outsiders_and_cap_long_lists():
    assert exclusive_lines_by_mod([("memory 100", ["A"])], {"A": "a"}) == {}
    lines = exclusive_lines_by_mod([("memory 100", ["A", "Project"])], {"A": "a"})
    assert lines == {"a": ["memory 100: Project patches this too; only one of these mods can be on"]}
    many = [(f"memory {index:X}", ["A", "B"]) for index in range(MAX_LISTED + 5)]
    lines = exclusive_lines_by_mod(many, {"A": "a", "B": "b"})
    assert len(lines["a"]) == MAX_LISTED + 1 and lines["a"][-1] == "…and 5 more"


def test_carries_native_code_finds_a_dll_or_asi_at_any_depth_or_case(tmp_path):
    assert carries_native_code(tmp_path) is False
    assert carries_native_code(tmp_path / "missing") is False
    (tmp_path / "hext").mkdir()
    (tmp_path / "hext" / "patch.txt").write_text("100 = 00\n", encoding="utf-8")
    assert carries_native_code(tmp_path) is False
    (tmp_path / "native").mkdir()
    (tmp_path / "native" / "driver.ASI").write_bytes(b"MZ")
    assert carries_native_code(tmp_path) is True


def hook(rva, size=5):
    return {"rva": rva, "original": "90" * size, "bytes": "90" * size}


def island(name, code="01000000" + "C3" * 12, **extra):
    return {"name": name, "code": code, "functions": [[4, 12, 0]], **extra}


def validated(spec):
    return exe_patches.validate(spec, "test")


def test_spans_claim_hooks_state_and_fixed_islands_but_not_floating_code():
    spec = validated({"version": 2, "islands": [island("fixed", rva=0x6000), island("placed")],
                      "hooks": [hook(0x1200)],
                      "sectionVirtualSize": {".data": 0x200}, "state": [{"rva": 0x2100, "size": 0x10}]})
    assert exe_patches.spans(spec) == {"hooks": [(0x1200, 0x1205)],
                                       "state": [(0x2100, 0x2110)],
                                       "islands": [(0x6000, 0x6010)]}


def tweak_mod(library, name, order, *native_specs, dll=False, damaged=False, script=True):
    folder = library / name
    folder.mkdir(parents=True)
    metadata = {"name": name, "order": order, "enabled": True}
    if script:
        metadata["script"] = {"version": 1}
    (folder / "mod.json").write_text(json.dumps(metadata), encoding="utf-8")
    if native_specs:
        native = folder / "native"
        native.mkdir()
        for index, spec in enumerate(native_specs):
            (native / f"{name}-{index}.json").write_text(json.dumps(spec), encoding="utf-8")
    if damaged:
        native = folder / "native"
        native.mkdir(exist_ok=True)
        (native / "damaged.json").write_text("{ not json", encoding="utf-8")
    if dll:
        (folder / "loader.dll").write_bytes(b"MZ")
    return folder


def adapter(library):
    owned = Ds1ModAdapter()
    owned.attach_context(library_root=library)
    return owned


def test_ds1_memory_overlap_is_marked_on_both_rows_without_enabling(tmp_path):
    library = tmp_path / "library"
    a = tweak_mod(library, "A", 1, {"version": 2, "hooks": [hook(0x1200)]})
    b = tweak_mod(library, "B", 2, {"version": 2, "hooks": [hook(0x1202, 4)]})
    found = adapter(library).conflicts([a, b], tmp_path / "game-missing")
    assert set(found) == {str(a.resolve()), str(b.resolve())}
    assert found[str(a.resolve())] == ["memory 1202-1204: B patches this too; only one of these mods can be on"]
    assert found[str(b.resolve())] == ["memory 1202-1204: A patches this too; only one of these mods can be on"]


def test_ds1_disjoint_hooks_and_other_kinds_are_no_conflict(tmp_path):
    library = tmp_path / "library"
    a = tweak_mod(library, "A", 1, {"version": 2, "hooks": [hook(0x1200)]})
    b = tweak_mod(library, "B", 2, {"version": 2, "hooks": [hook(0x1300)]})
    assert adapter(library).conflicts([a, b], tmp_path / "game") == {}
    # A hook and kept state at one address are different claims; the combiner
    # refuses each kind only against its own, and so does the mark.
    c = tweak_mod(library, "C", 3, {"version": 2, "hooks": [hook(0x2100)]})
    d = tweak_mod(library, "D", 4, {"version": 2, "sectionVirtualSize": {".data": 0x200},
                                   "state": [{"rva": 0x2100, "size": 4}]})
    assert adapter(library).conflicts([c, d], tmp_path / "game") == {}
    e = tweak_mod(library, "E", 5, {"version": 2, "sectionVirtualSize": {".data": 0x200},
                                   "state": [{"rva": 0x2100, "size": 4}]})
    found = adapter(library).conflicts([d, e], tmp_path / "game")
    assert set(found) == {str(d.resolve()), str(e.resolve())}


def test_ds1_fixed_islands_overlap_but_floating_code_is_left_for_the_composer(tmp_path):
    library = tmp_path / "library"
    a = tweak_mod(library, "A", 1, {"version": 2, "islands": [island("a", rva=0x6000)]})
    b = tweak_mod(library, "B", 2, {"version": 2, "islands": [island("b", rva=0x6008)]})
    assert set(adapter(library).conflicts([a, b], tmp_path / "game")) == {str(a.resolve()), str(b.resolve())}
    c = tweak_mod(library, "C", 3, {"version": 2, "islands": [island("c")]})
    assert adapter(library).conflicts([a, c], tmp_path / "game") == {}


def test_ds1_a_dll_mod_a_damaged_build_and_a_data_mod_claim_nothing(tmp_path):
    library = tmp_path / "library"
    spec = {"version": 2, "hooks": [hook(0x1200)]}
    a = tweak_mod(library, "A", 1, spec)
    # Its addresses are unknowable without running it: the schema's declared
    # conflicts still guard it at enable time, not this mark.
    b = tweak_mod(library, "B", 2, spec, dll=True)
    assert adapter(library).conflicts([a, b], tmp_path / "game") == {}
    c = tweak_mod(library, "C", 3, spec, damaged=True)
    assert set(adapter(library).conflicts([a, c], tmp_path / "game")) == {str(a.resolve()), str(c.resolve())}
    d = tweak_mod(library, "D", 4)
    assert adapter(library).conflicts([a, d], tmp_path / "game") == {}
    # A stray native/ folder in a data mod is dead weight, never applied.
    e = tweak_mod(library, "E", 5, spec, script=False)
    assert adapter(library).conflicts([a, e], tmp_path / "game") == {}


def test_ds1_native_spans_reads_the_last_build_and_skips_what_it_cannot(tmp_path):
    folder = tweak_mod(tmp_path, "A", 1, {"version": 2, "hooks": [hook(0x1200)]}, damaged=True)
    assert tweak_mods.native_spans(folder, "A") == {"hooks": [(0x1200, 0x1205)], "state": [], "islands": []}
    assert tweak_mods.native_spans(tmp_path / "missing", "A") == {"hooks": [], "state": [], "islands": []}
    link = folder / "native" / "link.json"
    try:
        link.symlink_to(folder / "native" / "A-0.json")
    except OSError:
        pytest.skip("this machine cannot create symlinks")
    assert tweak_mods.native_spans(folder, "A")["hooks"] == [(0x1200, 0x1205)]


def data_mod(library, name, order):
    folder = library / name
    folder.mkdir(parents=True)
    (folder / MARKER).write_text("project", encoding="utf-8")
    (folder / "mod.json").write_text(json.dumps({"name": name, "order": order, "enabled": True}),
                                     encoding="utf-8")
    return folder


def test_ds1_data_mods_without_archives_compose_clean_beside_memory_marks(tmp_path):
    library, game = tmp_path / "library", tmp_path / "game"
    game.mkdir()
    a, b = data_mod(library, "A", 1), data_mod(library, "B", 2)
    owned = adapter(library)
    assert owned.conflicts([a, b], game) == {}
    assert owned.conflicts([a, b], game) == {}  # second call reuses the data report
    c = tweak_mod(library, "C", 3, {"version": 2, "hooks": [hook(0x1200)]})
    d = tweak_mod(library, "D", 4, {"version": 2, "hooks": [hook(0x1200)]})
    found = owned.conflicts([a, b, c, d], game)
    assert set(found) == {str(c.resolve()), str(d.resolve())}


def test_ds1_unreadable_metadata_is_skipped_not_failed(tmp_path):
    library = tmp_path / "library"
    a = tweak_mod(library, "A", 1, {"version": 2, "hooks": [hook(0x1200)]})
    broken = library / "Broken"
    broken.mkdir()
    (broken / "mod.json").write_text("{ not json", encoding="utf-8")
    rows = mods_service.library_rows(library)
    assert {row["folder"] for row in rows} == {"A", "Broken"}
    assert next(row for row in rows if row["folder"] == "Broken")["error"] != ""
    assert adapter(library).conflicts([a, broken], tmp_path / "game") == {}


def test_merge_marks_combines_reports_caps_and_changes_neither_input():
    first = {"a": ["data 1"]}
    second = {"a": ["memory 1"], "b": ["memory 2"]}
    assert _merge_marks(first, second) == {"a": ["data 1", "memory 1"], "b": ["memory 2"]}
    assert (first, second) == ({"a": ["data 1"]}, {"a": ["memory 1"], "b": ["memory 2"]})
    many = _merge_marks({folder: [f"line {index}" for index in range(MAX_LISTED)] for folder in ("a",)},
                        {"a": ["one more", "another"]})
    assert len(many["a"]) == MAX_LISTED + 1 and many["a"][-1] == "…and 2 more"


def test_memory_conflicts_module_is_documented_where_it_matters():
    assert memory_conflicts.__doc__ and "without enabling" in memory_conflicts.__doc__.casefold()
