"""Attack corrections carry the percent unit, never a bare label.

The four elemental corrections (atkPhysCorrection etc.) are u16
percent-scale values where 100 is neutral. Their labels use the
trailing-(%) form so the client's unit control engages, matching the
PC motion values ('Physical (%)'); the descriptions read as percent
of base, not as a bare multiplier.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1.attacks import ATTACK_FIELDS, PC_ATTACK_FIELDS  # noqa: E402
from plugins.ds1.formats import schema  # noqa: E402


def labels(table):
    return {item['spec'].key: item['spec'].label
            for item in schema(table)['fields']}


def descriptions(table):
    return {item['spec'].key: item['spec'].description
            for item in schema(table)['fields']}


def test_correction_labels_carry_the_percent_unit():
    npc, pc = labels('AtkParam_Npc'), labels('AtkParam_Pc')
    npc_desc, pc_desc = descriptions('AtkParam_Npc'), descriptions('AtkParam_Pc')
    for key in [k for k in ATTACK_FIELDS if k.endswith('Correction')]:
        assert key in pc or key in PC_ATTACK_FIELDS
    assert [k for k in ATTACK_FIELDS if k.endswith('Correction')] == [
        'atkPhysCorrection', 'atkMagCorrection',
        'atkFireCorrection', 'atkThunCorrection']
    assert [k for k in PC_ATTACK_FIELDS if k.endswith('Correction')] == [
        'atkPhysCorrection', 'atkMagCorrection',
        'atkFireCorrection', 'atkThunCorrection']
    for key in ('atkPhysCorrection', 'atkMagCorrection',
                'atkFireCorrection', 'atkThunCorrection'):
        assert npc[key].endswith(' (%)'), (key, npc[key])
        assert pc[key].endswith(' (%)'), (key, pc[key])
        assert '100' in npc_desc[key] and 'ercent' in npc_desc[key], (key, npc_desc[key])
        assert '100' in pc_desc[key] and 'ercent' in pc_desc[key], (key, pc_desc[key])
    assert npc['atkPhysCorrection'] == 'Physical correction (%)'
