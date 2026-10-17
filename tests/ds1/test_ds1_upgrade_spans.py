"""Armor upgrade rates with one meaning share one slider span."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument


def spans():
    raw = make_archive(field_values={'ReinforceParamProtector': {
        100: {'physicsDefRate': 1.5, 'resistPoisonRate': 3.0},
        101: {'slashDefRate': 2.0}}})
    fields = {field['key']: field
              for field in ItemDocument(raw).read_row('ReinforceParamProtector', 100)['fields']}
    return fields


def test_defense_rates_share_one_span():
    fields = spans()
    shared = {(fields[key]['sliderMin'], fields[key]['sliderMax'])
              for key in ('physicsDefRate', 'magicDefRate', 'fireDefRate', 'thunderDefRate',
                          'slashDefRate', 'blowDefRate', 'thrustDefRate')}
    assert shared == {(0, 2.5)}, shared


def test_resist_rates_share_their_own_span():
    fields = spans()
    shared = {(fields[key]['sliderMin'], fields[key]['sliderMax'])
              for key in ('resistPoisonRate', 'resistDiseaseRate', 'resistBloodRate', 'resistCurseRate')}
    assert shared == {(0, 3.75)}, shared


def test_unrelated_fields_keep_their_spans():
    fields = spans()
    assert (fields['materialSetId']['sliderMin'], fields['materialSetId']['sliderMax']) == (0, 1)
