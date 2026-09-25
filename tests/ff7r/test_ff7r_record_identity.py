from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui


def test_ff7r_shows_game_keys_not_parser_row_indices_as_identity():
    source = plugin_ui("ff7r")

    # The curated tabs build their columns from the loaded property list, and
    # the identity column is the game's own row key, labelled for what it is.
    assert 'return [{key:"tag",label:"Record ID"' in source
    assert "function curatedColumns(spec)" in source
    assert "numberedId:true" not in source
    assert "identity:recordId(row.id)" not in source
    # A tab with no display name of its own still falls back to the key.
    assert 'row.tag||"Unnamed record"' in source
    assert 'title:row.key||"Unnamed text entry"' in source
