"""Created records, backups and all metadata share one staged transaction."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from test_rdr2_item_creation_validation import isolated, fixture, BASE
from test_rdr2_catalog_numeric_validation import snapshot
from plugins.rdr2 import server as s


@pytest.fixture
def creation(isolated, monkeypatch):
    root, path = isolated
    monkeypatch.setattr(s, 'LABELS_FILE', root / 'labels.json')
    monkeypatch.setattr(s, 'ORIGIN_PROVENANCE_FILE', root / 'new_metadata' / 'provenance.json')
    (s.ds_dir('mine') / 'install.xml').write_text('<Install><Resources><Resource><Opaque>keep</Opaque></Resource></Resources></Install>')
    return root, path


def create(kind):
    return s.create_catalog_item(BASE) if kind == 'item' else s.create_catalog_effect({
        'key': 'LEX_FIXTURE_EFFECT', 'behavior': 'BEHAVIOR', 'durationcategory': '', 'label': 'Fixture'})


CASES = [(kind, target, existing) for kind, targets in [
    ('item', ['catalog', 'backup', 'provenance', 'strings', 'install']),
    ('effect', ['catalog', 'backup', 'provenance', 'labels'])]
    for target in targets for existing in [False, True] if target != 'backup' or not existing]


@pytest.mark.parametrize('kind,target,existing', CASES)
def test_failure_at_every_output_restores_originals_cache_and_origin_markers(creation, monkeypatch, kind, target, existing):
    root, catalog = creation
    paths = {'catalog': catalog, 'backup': catalog.with_suffix(catalog.suffix + '.bak'),
             'provenance': s.ORIGIN_PROVENANCE_FILE, 'labels': s.LABELS_FILE,
             'strings': s.ds_dir('mine') / s.LOCALIZATION_FILE, 'install': s.ds_dir('mine') / 'install.xml'}
    paths['backup'].unlink()
    if existing:
        paths['backup'].write_bytes(b'original backup')
        paths['provenance'].parent.mkdir()
        paths['provenance'].write_text('{"schema":2,"customCatalogItems":["OLD"],"customCatalogEffects":["OLD"],"opaque":{"keep":true}}')
        paths['labels'].write_text('{"effects":{"OLD":"Keep"},"effectSymbols":{"OLD":"OLD_SYMBOL"},"opaque":{"key":"keep"}}')
        paths['strings'].write_text('[LEXEDITOR OVERRIDES]\nOLD = Keep\n')
    s._ORIGIN_MARKER_CACHE['sentinel'] = {'keep': True}
    before = snapshot(root)
    entry = s.load_file(s.CATALOG_FILE)
    old_root = entry['root']
    cached = ET.tostring(old_root)
    real_replace = Path.replace
    failed = False
    def replace(path, destination):
        nonlocal failed
        if Path(destination) == paths[target] and not failed:
            failed = True
            raise OSError('Injected creation write failure')
        return real_replace(path, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(OSError, match='Injected creation write failure'):
        create(kind)
    assert failed
    assert snapshot(root) == before
    assert s.load_file(s.CATALOG_FILE) is entry
    assert entry['root'] is old_root
    assert ET.tostring(old_root) == cached
    assert s._ORIGIN_MARKER_CACHE == {'sentinel': {'keep': True}}
    assert not list(root.rglob('*.tmp'))
    if not existing:
        assert not paths['provenance'].parent.exists()
    result = create(kind)
    assert s._ORIGIN_MARKER_CACHE == {}
    s._files.clear()
    doc = s.load_file(s.CATALOG_FILE)['root']
    if kind == 'item':
        assert s.find_catalog_item(doc, result['key']) is not None
        assert s.parse_gxt2(paths['strings'])['LEX_FIXTURE'] == 'Fixture'
    else:
        assert any(row.findtext('key') == result['key'] for row in doc.findall('./effectsids/item'))
        assert json.loads(paths['labels'].read_text())['effects'][result['key']] == 'Fixture'
    field = 'customCatalogItems' if kind == 'item' else 'customCatalogEffects'
    assert result['key'] in json.loads(paths['provenance'].read_text())[field]
    if existing:
        assert paths['backup'].read_bytes() == b'original backup'
        assert 'OLD' in json.loads(paths['provenance'].read_text())[field]
        assert json.loads(paths['provenance'].read_text())['opaque'] == {'keep': True}
        if kind == 'effect':
            labels = json.loads(paths['labels'].read_text())
            assert labels['effects']['OLD'] == 'Keep'
            assert labels['opaque'] == {'key': 'keep'}
    else:
        assert paths['backup'].read_bytes() == before[str(catalog.relative_to(root))]
    assert not list(root.rglob('*.tmp'))


@pytest.mark.parametrize('bad', [[], {'schema': 9}, {'schema': 2, 'customCatalogItems': {}},
                               {'schema': 2, 'weapons': [3]}, {'schema': 2, 'ammo': [None]}])
@pytest.mark.parametrize('kind', ['item', 'effect'])
def test_invalid_existing_provenance_rejects_before_creation(creation, bad, kind):
    root, _ = creation
    s.ORIGIN_PROVENANCE_FILE.parent.mkdir()
    s.ORIGIN_PROVENANCE_FILE.write_text(json.dumps(bad))
    before = snapshot(root)
    old_root = s.load_file(s.CATALOG_FILE)['root']
    with pytest.raises(ValueError):
        create(kind)
    assert snapshot(root) == before
    assert s.load_file(s.CATALOG_FILE)['root'] is old_root


@pytest.mark.parametrize('bad', [[], {'effects': []}, {'effectSymbols': None}, {'effects': {'OLD': 3}}])
def test_invalid_existing_labels_reject_before_effect_creation(creation, bad):
    root, _ = creation
    s.LABELS_FILE.write_text(json.dumps(bad))
    before = snapshot(root)
    old_root = s.load_file(s.CATALOG_FILE)['root']
    with pytest.raises(ValueError):
        create('effect')
    assert snapshot(root) == before
    assert s.load_file(s.CATALOG_FILE)['root'] is old_root


@pytest.mark.parametrize('kind', ['item', 'effect'])
def test_read_only_creation_preserves_all_outputs(creation, monkeypatch, kind):
    root, _ = creation
    monkeypatch.setitem(s.DATASETS['mine'], 'readonly', True)
    before = snapshot(root)
    old_root = s.load_file(s.CATALOG_FILE)['root']
    with pytest.raises(PermissionError, match='read-only'):
        create(kind)
    assert snapshot(root) == before
    assert s.load_file(s.CATALOG_FILE)['root'] is old_root
