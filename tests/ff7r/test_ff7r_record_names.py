"""Curated rows are named from the table that joins them, or not at all."""
from types import SimpleNamespace

from plugins.ff7r.semantics import (
    names_by_key_prefix,
    player_prefix_names,
    record_name_map,
)


def entry(tag, **values):
    return SimpleNamespace(tag=tag, values=values)


# PlayerTable's own fields, exactly as the installed Resident table stores them.
PLAYER_TABLE = [
    entry("pt_Cloud", PlayerParameterStringFormat="Cloud%02d", TextID="$party_cloud"),
    entry("pt_RedXIII", PlayerParameterStringFormat="RedXIII%02d", TextID="$party_red13"),
]
TEXT = {"$party_cloud": "Cloud", "$party_red13": "Red XIII"}


def test_player_prefix_names_uses_the_key_format_and_the_name_text_id():
    assert player_prefix_names(PLAYER_TABLE, TEXT) == {"Cloud": "Cloud", "RedXIII": "Red XIII"}


def test_a_row_with_no_name_text_is_left_unnamed():
    rows = [entry("pt_Ghost", PlayerParameterStringFormat="Ghost%02d", TextID="$party_ghost")]
    assert player_prefix_names(rows, TEXT) == {}


def test_a_row_with_no_key_format_is_left_unnamed():
    rows = [entry("pt_Cloud", PlayerParameterStringFormat="", TextID="$party_cloud")]
    assert player_prefix_names(rows, TEXT) == {}


def test_every_level_of_a_character_gets_that_character_s_name():
    prefixes = player_prefix_names(PLAYER_TABLE, TEXT)
    named = names_by_key_prefix(["Cloud01", "Cloud99", "RedXIII07"], prefixes)
    assert named == {"Cloud01": "Cloud", "Cloud99": "Cloud", "RedXIII07": "Red XIII"}


def test_an_unmatched_key_is_absent_rather_than_invented():
    named = names_by_key_prefix(["Sonon07"], player_prefix_names(PLAYER_TABLE, TEXT))
    assert named == {}


def test_the_longest_matching_prefix_wins():
    prefixes = {"Red": "Wrong", "RedXIII": "Red XIII"}
    assert names_by_key_prefix(["RedXIII07"], prefixes) == {"RedXIII07": "Red XIII"}


def test_tables_that_join_no_name_return_an_empty_map(tmp_path):
    # EnemyParameter rows carry six stats and nothing else, and no installed
    # DataObject holds their keys, so there is nothing to join. Item/Equipment
    # names come from economy_payload, not from here.
    index = {"assets": [{"asset": "Game/Resident/PlayerTable", "name": "PlayerTable"}]}
    for asset in ("Game/Resident/EnemyParameter", "Game/Resident/BattleAbility",
                  "Game/Resident/Materia"):
        assert record_name_map(tmp_path, tmp_path, tmp_path, index, asset) == {}


def test_player_rows_are_unnamed_when_the_joining_table_is_missing(tmp_path):
    assert record_name_map(tmp_path, tmp_path, tmp_path, {"assets": []},
                           "Game/Resident/PlayerParameter") == {}


def test_an_unreadable_package_is_unnamed_rather_than_an_error(tmp_path):
    # The game is not installed here, so load_package cannot read either table.
    index = {"assets": [{"asset": "Game/Resident/PlayerTable", "name": "PlayerTable"}]}
    assert record_name_map(tmp_path, tmp_path, tmp_path, index,
                           "Game/Resident/PlayerParameter") == {}
