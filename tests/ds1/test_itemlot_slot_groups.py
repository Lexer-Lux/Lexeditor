"""ItemLotParam fields group by drop slot, not by field kind.

A lot is eight drop slots plus four lot-level settings. Grouping every
slot's item, category, rate, amount and flags under its own Drop header
is what makes the tab readable; the flat per-kind wall is unusable.
"""
from plugins.ds1.formats import schema


def groups():
    return {entry['spec'].key: entry['spec'].group
            for entry in schema('ItemLotParam')['fields']}


def test_slots_group_by_number():
    found = groups()
    for slot in range(1, 9):
        name = f'Drop {slot}'
        suffix = f'{slot:02d}'
        assert found[f'lotItemId{suffix}'] == name
        assert found[f'lotItemCategory{suffix}'] == name
        assert found[f'lotItemBasePoint{suffix}'] == name
        assert found[f'cumulateLotPoint{suffix}'] == name
        assert found[f'getItemFlagId{suffix}'] == name
        assert found[f'lotItemNum{suffix}'] == name
        assert found[f'enableLuck{suffix}'] == name
        assert found[f'cumulateReset{suffix}'] == name


def test_lot_level_fields_group_together():
    found = groups()
    assert found['getItemFlagId'] == 'Lot'
    assert found['cumulateNumFlagId'] == 'Lot'
    assert found['cumulateNumMax'] == 'Lot'
    assert found['lotItem_Rarity'] == 'Lot'
