from pathlib import Path


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui


def test_history_is_source_bounded_and_covers_curated_and_tweak_edits():
    source = plugin_ui("ff7r")
    assert 'state.activeSource==="mine"&&(' in source
    assert '"tweaks"].includes(state.tab)' in source
    assert "!!curatedSpec(state.tab)" in source
    assert "snapshot?.tweaks" in source
