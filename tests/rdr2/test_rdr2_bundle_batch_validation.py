"""A rejected later bundle must not leak an earlier edit through cached loot XML."""
import xml.etree.ElementTree as ET
import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s


@pytest.mark.parametrize('existing_backup', [False, True])
def test_bad_later_bundle_preserves_both_file_caches_and_backups(fixture, existing_backup):
    root, _ = fixture
    name = s.LOOT_FILES[0]
    path = s.data_file_path(name, 'mine')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<Root><LootTables><Item key="BUNDLE"><Entries><Item><Name>OUTPUT</Name>'
                    '<Min value="1"/><Max value="1"/><Opaque value="17"/></Item></Entries></Item>'
                    '</LootTables></Root>')
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    cached = {file: ET.tostring(s.load_file(file)['root']) for file in [s.CATALOG_FILE, name]}
    before = snapshot(root)
    with pytest.raises(ValueError, match='bundle entry not found'):
        s.apply_catalog_edits({'carry': [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 9}],
                              'bundles': [{'key': f'{name}|BUNDLE|OUTPUT', 'qty': 8},
                                          {'key': f'{name}|BUNDLE|MISSING', 'qty': 9}]})
    assert snapshot(root) == before
    assert {file: ET.tostring(s.load_file(file)['root']) for file in cached} == cached
    # An ordinary subsequent save cannot publish the rejected cached edit.
    s.save_file(name)
    s._files.clear()
    doc = s.load_file(name)['root']
    assert doc.find('.//Entries/Item/Min').get('value') == '1'
    assert doc.find('.//Entries/Item/Max').get('value') == '1'
    assert doc.find('.//Entries/Item/Opaque').get('value') == '17'
