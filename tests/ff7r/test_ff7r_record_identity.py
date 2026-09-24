from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui


def test_ff7r_shows_game_keys_not_parser_row_indices_as_identity():
    source = plugin_ui("ff7r")

    assert 'const dataColumns=[{key:"tag",label:"Record"' in source
    assert 'const textColumns=[{key:"resource",label:"Resource"' in source
    assert 'return [{key:"tag",label:"Record"' in source
    assert "numberedId:true" not in source
    assert "identity:recordId(row.id)" not in source
    assert 'title:row.tag||"Unnamed record"' in source
    assert 'title:row.key||"Unnamed text entry"' in source
