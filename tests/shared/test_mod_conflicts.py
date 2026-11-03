"""Each mod's conflict lines, said from its own side (core/mod_conflicts.py)."""
from core.mod_conflicts import MAX_LISTED, lines_by_mod


def test_the_last_mod_overrides_and_the_others_are_told():
    lines = lines_by_mod([("Sword, Damage", ["A", "B", "C"])], {"A": "a", "B": "b", "C": "c"})
    assert lines["c"] == ["Sword, Damage: overrides A and B"]
    assert lines["a"] == lines["b"] == ["Sword, Damage: C changes this too and loads later, so this mod's change is not used"]


def test_a_part_one_mod_changes_is_no_conflict_and_long_lists_are_counted():
    assert lines_by_mod([("Alone", ["A"])], {"A": "a"}) == {}
    many = [(f"Row {index}", ["A", "B"]) for index in range(MAX_LISTED + 5)]
    lines = lines_by_mod(many, {"A": "a", "B": "b"})
    assert len(lines["a"]) == MAX_LISTED + 1 and lines["a"][-1] == "…and 5 more"


def test_a_mod_outside_the_library_counts_but_gets_no_row():
    lines = lines_by_mod([("Name 100", ["A", "Project"])], {"A": "a"})
    assert lines == {"a": ["Name 100: Project changes this too and loads later, so this mod's change is not used"]}
