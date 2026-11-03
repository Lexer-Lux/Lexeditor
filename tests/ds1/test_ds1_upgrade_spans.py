"""Upgrade rates carry no slider span: the slider spans the accepted range."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument


def fields():
    raw = make_archive(field_values={'ReinforceParamProtector': {
        100: {'physicsDefRate': 1.5, 'resistPoisonRate': 3.0},
        101: {'slashDefRate': 2.0}}})
    return {field['key']: field
            for field in ItemDocument(raw).read_row('ReinforceParamProtector', 100)['fields']}


def test_no_slider_keys():
    for key, field in fields().items():
        assert 'sliderMin' not in field, key
        assert 'sliderMax' not in field, key


def test_accepted_bounds_survive():
    by_key = fields()
    assert by_key['physicsDefRate']['minimum'] == 0
    assert by_key['physicsDefRate']['maximum'] == 99.99
