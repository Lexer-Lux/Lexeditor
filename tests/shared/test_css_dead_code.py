"""The cleanup audit must cover logical and grid shorthand declarations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import css_dead_code


def test_shorthand_removes_superseded_geometry_inside_layers():
    source = '@layer controls { .field {padding-block:3px;padding:0 0 0 12px;grid-row:1;grid-column:1;grid-area:1/2;font-size:9px;font:10px/1 sans-serif;} }'
    clean, count, _ = css_dead_code.remove(source)
    assert count == 4
    assert 'padding-block' not in clean and 'grid-row' not in clean and 'font-size' not in clean
    assert 'grid-area:1/2' in clean and 'font:10px/1 sans-serif' in clean


def test_partial_override_keeps_the_rest_of_the_shorthand():
    source = '.field {padding:2px;padding-left:8px;grid-area:1/2;grid-row:3;}'
    clean, count, _ = css_dead_code.remove(source)
    assert count == 0 and clean == source
