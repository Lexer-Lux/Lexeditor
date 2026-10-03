"""Bounty response/cooldown batches reject invalid drafts before either write."""
import json
import copy
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import bounty_hunters as bounty, server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

FIRST = {'id': 'response/MinBounty', 'value': '123.456789f'}
COOLDOWN = 'cooldown/DelayInGameHoursAfterBountyAcquired/0/Min'
BAD = [None, {}, False, '', [None], [{}], [dict(FIRST, extra=1)],
       [dict(FIRST, id=[])], [FIRST]]
BAD += [[{'id': COOLDOWN, 'value': value}] for value in
        [None, True, [], {}, '', 'NaN', 'Inf', '-Inf', float('nan'), float('inf'), -1, '1_0', '-1e-999', '1e999', '2.000000000000000001']]
BAD += [[{'id': COOLDOWN.replace('/0/', f'/{index}/'), 'value': '2'}]
        for index in ['-1', '+0', '00', '1.5', 'unknown', '99']]
BAD += [[{'id': COOLDOWN.replace('DelayInGameHoursAfterBountyAcquired', 'Opaque'), 'value': '2'}]]


@pytest.fixture
def files(fixture):
    root, _ = fixture
    response = s.ds_dir('mine') / s.BOUNTY_HUNTERS_FILE
    dispatch = s.ds_dir('mine') / s.DISPATCH_FILE
    response.parent.mkdir(parents=True, exist_ok=True)
    dispatch.parent.mkdir(parents=True, exist_ok=True)
    response.write_text('<Root><!--keep--><BountyResponses><BountyDispatch><Name>LAW_BOUNTY_HUNTERS_CSI</Name><MinBounty value="10"/><Opaque value="keep"/></BountyDispatch></BountyResponses></Root>')
    dispatch.write_text('<Root><!--keep--><BountyResponseCooldowns><Item><Name>BountyHuntersGlobalCooldown</Name><DelayInGameHoursAfterBountyAcquired><Item><Min value="1"/><Max value="2"/></Item><Item><Min value="3"/><Max value="4"/></Item></DelayInGameHoursAfterBountyAcquired><Opaque><Item><Min value="7"/></Item></Opaque></Item></BountyResponseCooldowns></Root>')
    return root, response, dispatch


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('backups', [False, True])
def test_rejected_batch_preserves_both_files_and_backups(files, bad, backups):
    root, response, dispatch = files
    if backups:
        for path in [response, dispatch]:
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    with pytest.raises(ValueError):
        s.apply_bounty_hunter_edits([FIRST, *bad] if isinstance(bad, list) else bad)
    assert snapshot(root) == before


def test_http_rejection_and_valid_two_file_reload(files):
    root, response, dispatch = files
    originals = [path.read_bytes() for path in [response, dispatch]]
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def post(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/bounty-hunters/save',
                       data=json.dumps({'edits': edits}).encode(),
                       headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as error:
            urlopen(post([FIRST, {'id': COOLDOWN, 'value': 'NaN'}]))
        assert error.value.code == 400
        assert snapshot(root) == before
        assert json.load(urlopen(post([FIRST, {'id': COOLDOWN, 'value': '0.125'}])))['saved'] == 2
        assert bounty._parse(response).find('.//MinBounty').get('value') == FIRST['value']
        cooldown = bounty._parse(dispatch).find('.//DelayInGameHoursAfterBountyAcquired')
        assert cooldown.findall('Item')[0].find('Min').get('value') == '0.125'
        assert cooldown.findall('Item')[1].find('Min').get('value') == '3'
        for path, original in zip([response, dispatch], originals):
            assert b'<!--keep-->' in path.read_bytes()
            assert path.with_suffix(path.suffix + '.bak').read_bytes() == original
    finally:
        http.shutdown(); http.server_close(); worker.join()


def test_empty_and_readonly_batches(files):
    root, _, _ = files
    before = snapshot(root)
    s.DATASETS['mine']['readonly'] = True
    assert s.apply_bounty_hunter_edits([]) == 0
    with pytest.raises(ValueError, match='read-only'):
        s.apply_bounty_hunter_edits([FIRST])
    assert snapshot(root) == before


@pytest.mark.parametrize('kind', ['owner', 'name', 'field', 'attributes', 'child', 'text', 'nonfinite', 'cooldown-owner', 'cooldown-name', 'cooldown-section', 'cooldown-field', 'cooldown-attributes', 'cooldown-child', 'cooldown-nonfinite'])
@pytest.mark.parametrize('backups', [False, True])
def test_unsupported_sources_are_locked_and_preserved(files, monkeypatch, kind, backups):
    root, response, dispatch = files
    doc = bounty._parse(dispatch if kind.startswith('cooldown') else response)
    if kind.startswith('cooldown'):
        owner = doc.find('./BountyResponseCooldowns/Item')
        section = owner.find('DelayInGameHoursAfterBountyAcquired')
        parent = section.findall('Item')[0]
        node = parent.find('Min')
        identity = COOLDOWN
        if kind == 'cooldown-owner':doc.find('BountyResponseCooldowns').append(copy.deepcopy(owner))
        elif kind == 'cooldown-name':owner.append(copy.deepcopy(owner.find('Name')))
        elif kind == 'cooldown-section':owner.append(copy.deepcopy(section))
        elif kind == 'cooldown-field':parent.append(copy.deepcopy(node))
        elif kind == 'cooldown-attributes':node.set('opaque', 'keep')
        elif kind == 'cooldown-child':node.append(bounty.ET.Element('Opaque'))
        else:node.set('value', 'NaN')
        dispatch.write_bytes(bounty.ET.tostring(doc))
    else:
        parent = doc.find('./BountyResponses/BountyDispatch')
        node = parent.find('MinBounty')
        identity = FIRST['id']
        if kind == 'owner':doc.find('BountyResponses').append(copy.deepcopy(parent))
        elif kind == 'name':parent.append(copy.deepcopy(parent.find('Name')))
        elif kind == 'field':parent.append(copy.deepcopy(node))
        elif kind == 'attributes':node.set('opaque', 'keep')
        elif kind == 'child':node.append(bounty.ET.Element('Opaque'))
        elif kind == 'text':node.text = 'opaque'
        else:node.set('value', 'NaN')
        response.write_bytes(bounty.ET.tostring(doc))
    if backups:
        for path in [response, dispatch]:path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    monkeypatch.setattr(bounty, 'EXTRACT_ROOT', root / 'missing-extract')
    view = bounty.read_bounty_hunters(response, dispatch)
    if kind not in ['cooldown-owner', 'cooldown-name']:
        assert identity in view['readonlyIds']
    else:
        assert not view['cooldowns']
    before = snapshot(root)
    with pytest.raises(ValueError):
        s.apply_bounty_hunter_edits([{'id': identity, 'value': '1'}])
    assert snapshot(root) == before


@pytest.mark.parametrize('kind', ['phase', 'phase-name', 'groups', 'group', 'preset', 'conditions', 'condition', 'chance', 'unknown-chance', 'range', 'overchance', 'valid'])
@pytest.mark.parametrize('backups', [False, True])
def test_phase_source_lookup_requires_unique_owners(files, monkeypatch, kind, backups):
    root, response, dispatch = files
    doc = bounty._parse(response)
    owner = doc.find('./BountyResponses/BountyDispatch')
    phases = bounty.ET.SubElement(owner, 'DispatchPhases')
    phase = bounty.ET.fromstring('<Phase><Name>InitialRiders</Name><GroupMultiplier value="1"/><DispatchPeds><RandomDispatchPedGroups><DispatchGroup><Preset>PoliceDog</Preset><MinNumPeds value="1"/><MaxNumPeds value="2"/><RandomWeight value="1"/><SelectionConditions><Condition type="CAIConditionRandom"><Chances value="0.2"/></Condition></SelectionConditions><Opaque value="keep"/></DispatchGroup></RandomDispatchPedGroups></DispatchPeds></Phase>')
    phases.append(phase)
    groups = phase.find('./DispatchPeds/RandomDispatchPedGroups')
    group = groups.find('DispatchGroup')
    conditions = group.find('SelectionConditions')
    condition = conditions.find('Condition')
    chance = condition.find('Chances')
    if kind == 'phase':phases.append(copy.deepcopy(phase))
    elif kind == 'phase-name':phase.append(copy.deepcopy(phase.find('Name')))
    elif kind == 'groups':phase.find('DispatchPeds').append(copy.deepcopy(groups))
    elif kind == 'group':groups.append(copy.deepcopy(group))
    elif kind == 'preset':group.append(copy.deepcopy(group.find('Preset')))
    elif kind == 'conditions':group.append(copy.deepcopy(conditions))
    elif kind == 'condition':conditions.append(copy.deepcopy(condition))
    elif kind == 'chance':condition.append(copy.deepcopy(chance))
    elif kind == 'unknown-chance':chance.set('value', 'NaN')
    response.write_bytes(bounty.ET.tostring(doc))
    if backups:
        for path in [response, dispatch]:path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    monkeypatch.setattr(bounty, 'EXTRACT_ROOT', root / 'missing-extract')
    identity = 'phase/InitialRiders/random/PoliceDog/Chances'
    view = bounty.read_bounty_hunters(response, dispatch)
    before = snapshot(root)
    edits = [FIRST, {'id': identity, 'value': '0.75'}]
    if kind == 'range':edits.append({'id': identity.replace('/Chances', '/MinNumPeds'), 'value': '2.000000000000000001'})
    if kind == 'overchance':edits[-1]['value'] = '1.000000000000000001'
    if kind != 'valid':
        if kind not in ['range', 'overchance']:assert identity in view['readonlyIds']
        with pytest.raises(ValueError):s.apply_bounty_hunter_edits(edits)
        assert snapshot(root) == before
    else:
        assert identity not in view['readonlyIds']
        assert s.apply_bounty_hunter_edits(edits) == 2
        after = bounty.read_bounty_hunters(response, dispatch)
        assert after['phases'][0]['groups'][0]['chance'] == '0.75'
        assert bounty._parse(response).find('.//Opaque').get('value') == 'keep'


@pytest.mark.parametrize('values', [('2.000000000000000001', '2'), ('1e-999', '0'), ('1', '0.999999999999999999')])
@pytest.mark.parametrize('backups', [False, True])
def test_final_cooldown_range_uses_exact_decimals(files, values, backups):
    root, response, dispatch = files
    if backups:
        for path in [response, dispatch]:path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    with pytest.raises(ValueError, match='minimum exceeds maximum'):
        s.apply_bounty_hunter_edits([FIRST, {'id': COOLDOWN, 'value': values[0]}, {'id': COOLDOWN[:-3] + 'Max', 'value': values[1]}])
    assert snapshot(root) == before
    assert s.apply_bounty_hunter_edits([{'id': COOLDOWN, 'value': '5.000000000000000001'}, {'id': COOLDOWN[:-3] + 'Max', 'value': '5.000000000000000002'}]) == 2
    node = bounty._parse(dispatch).find('.//DelayInGameHoursAfterBountyAcquired/Item')
    assert node.find('Min').get('value') == '5.000000000000000001'
    assert node.find('Max').get('value') == '5.000000000000000002'
