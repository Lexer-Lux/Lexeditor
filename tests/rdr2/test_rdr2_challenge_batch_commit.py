"""Challenge families publish together; rejected candidates never leak into cache."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

GOAL = {'name': 'Goal', 'index': 0, 'value': '12', 'sources': []}
LABEL = {'file': s.CHALLENGES_FILE, 'owner': 'Challenge', 'rank': 0,
         'field': 'description', 'value': 'New label'}


@pytest.fixture
def challenges(fixture, monkeypatch):
    root, _ = fixture
    documents = {
        s.GOALS_FILE: '<Root><!--goals--><goals><Item><name>Goal</name><scoreParams><Item><desiredGoal value="10"/></Item></scoreParams><Opaque>keep</Opaque></Item></goals></Root>',
        s.CHALLENGES_FILE: '<Root><!--challenges--><challenges><Item><name>Challenge</name><uiInfo><description>Old label</description></uiInfo><Opaque>keep</Opaque></Item></challenges></Root>',
    }
    for name, text in documents.items():
        path = s.data_file_path(name, 'mine')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        s.load_file(name)
    monkeypatch.setattr(s, 'get_challenges', lambda ds: {
        'allowedSourcePairs': [], 'allowedRewards': [], 'allowedConditionValues': []})
    return root


@pytest.mark.parametrize('backups', [False, True])
@pytest.mark.parametrize('later', [
    {'mode_edits': [{'challenge': 'Challenge', 'mode': 'parallel'}]},
    {'mode_edits': [{'challenge': 'Challenge', 'mode': []}]},
    {'ui_edits': [dict(LABEL, rank='invalid')]},
    {'condition_edits': [{'type': 'Unknown', 'field': 'value', 'value': 'bad'}]},
    {'reward_edits': [None]},
])
def test_late_rejection_preserves_files_and_cached_roots(challenges, backups, later):
    if backups:
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original')
    before = snapshot(challenges)
    roots = {name: s.load_file(name)['root'] for name in (s.GOALS_FILE, s.CHALLENGES_FILE)}
    with pytest.raises(ValueError):
        s.apply_challenge_edits([GOAL], **later)
    assert snapshot(challenges) == before
    assert all(s.load_file(name)['root'] is root for name, root in roots.items())
    assert roots[s.GOALS_FILE].find('.//desiredGoal').get('value') == '10'


@pytest.mark.parametrize('backups,fail_at', [(False, 1), (False, 2), (False, 3), (False, 4), (True, 1), (True, 2)])
def test_disk_failure_restores_both_files_backups_and_roots(challenges, monkeypatch, backups, fail_at):
    if backups:
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original')
    before = snapshot(challenges)
    roots = {name: s.load_file(name)['root'] for name in (s.GOALS_FILE, s.CHALLENGES_FILE)}
    replace = s.os.replace
    count = 0

    def fail(source, destination):
        nonlocal count
        count += 1
        if count == fail_at:
            raise OSError('injected challenge disk failure')
        return replace(source, destination)

    monkeypatch.setattr(s.os, 'replace', fail)
    with pytest.raises(OSError):
        s.apply_challenge_edits([GOAL], ui_edits=[LABEL])
    assert snapshot(challenges) == before
    assert all(s.load_file(name)['root'] is root for name, root in roots.items())


def test_http_rejection_then_real_save_reload(challenges):
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()

    def post(modes):
        return Request(f'http://127.0.0.1:{http.server_port}/api/challenges/save',
                       data=json.dumps({'edits': [GOAL], 'uiEdits': [LABEL], 'modes': modes}).encode(),
                       headers={'Content-Type': 'application/json'})

    try:
        before = snapshot(challenges)
        with pytest.raises(HTTPError) as error:
            urlopen(post([{'challenge': 'Challenge', 'mode': 'parallel'}]))
        assert error.value.code == 400
        assert snapshot(challenges) == before
        with urlopen(post([])) as response:
            assert json.load(response)['saved'] == 2
        s._files.clear()
        assert s.load_file(s.GOALS_FILE)['root'].find('.//desiredGoal').get('value') == '12'
        assert s.load_file(s.CHALLENGES_FILE)['root'].find('.//description').text == 'New label'
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            assert s.load_file(name)['root'].find('.//Opaque').text == 'keep'
            assert b'<!--' in s.data_file_path(name, 'mine').read_bytes()
            path = s.data_file_path(name, 'mine')
            assert path.with_suffix(path.suffix + '.bak').read_bytes() == before[str(path.relative_to(challenges))]
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_readonly_and_empty_batch(challenges):
    before = snapshot(challenges)
    s.DATASETS['mine']['readonly'] = True
    assert s.apply_challenge_edits([]) == 0
    with pytest.raises(ValueError, match='read-only'):
        s.apply_challenge_edits([GOAL], ui_edits=[LABEL])
    assert snapshot(challenges) == before
