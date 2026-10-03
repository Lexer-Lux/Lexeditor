"""Bounty response/cooldown batches reject invalid drafts before either write."""
import json
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
        [None, True, [], {}, '', 'NaN', 'Inf', '-Inf', float('nan'), float('inf'), -1]]
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
    response.write_text('<Root><!--keep--><BountyResponses><BountyDispatch><MinBounty value="10"/><Opaque value="keep"/></BountyDispatch></BountyResponses></Root>')
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
