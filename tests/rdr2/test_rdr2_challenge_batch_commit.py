"""Challenge families publish together; rejected candidates never leak into cache."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot
REAL_GET_CHALLENGES = s.get_challenges

GOAL = {'name': 'Goal', 'index': 0, 'value': '12', 'sources': []}
LABEL = {'file': s.CHALLENGES_FILE, 'owner': 'Challenge', 'rank': 0,
         'field': 'challengeDescLabel', 'value': 'New label'}
SOURCE = {'index': 0, 'base': 'SECOND', 'permutation': ''}
CONDITION = {'goal': 'Goal', 'index': 0, 'type': 'CAIConditionGoalContext',
             'field': 'ContextHash', 'value': 'CHAL_CTX_SCOPED_KIT'}
REWARD = {'challenge': 'Challenge', 'rank': 1, 'owner': 'Challenge', 'ownerRank': 1,
          'rewards': [{'type': 'CUnlockReward', 'value': 'FIXTURE_UNLOCK_2'}]}


@pytest.fixture
def challenges(fixture, monkeypatch):
    root, _ = fixture
    documents = {
        s.GOALS_FILE: '<Root><!--goals--><goals><Item><name>Goal</name><scoreParams><Item><desiredGoal value="10"/><statId><BaseId>BASE</BaseId><PermutationId>PERM</PermutationId></statId></Item></scoreParams><Item type="CAIConditionGoalContext"><ContextHash>CHAL_CTX_ON_MOVING_TRAIN</ContextHash></Item><Opaque>keep</Opaque></Item></goals></Root>',
        s.CHALLENGES_FILE: '<Root><!--challenges--><challenges><Item><name>Challenge</name><uiInfo><challengeDescLabel>Old label</challengeDescLabel></uiInfo><Opaque>keep</Opaque></Item></challenges></Root>',
    }
    for name, text in documents.items():
        path = s.data_file_path(name, 'mine')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        s.load_file(name)
    monkeypatch.setattr(s, 'get_challenges', lambda ds: {
        'allowedSourcePairs': [{'base': 'BASE', 'permutation': 'PERM'}, {'base': 'SECOND', 'permutation': ''}],
        'allowedRewards': [], 'allowedConditionValues': [{'type': 'CAIConditionGoalContext',
            'field': 'ContextHash', 'values': ['CHAL_CTX_ON_MOVING_TRAIN', 'CHAL_CTX_SCOPED_KIT']}]})
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
        assert s.load_file(s.CHALLENGES_FILE)['root'].find('.//challengeDescLabel').text == 'New label'
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


BAD_GOALS = [{}, dict(GOAL, name='Unknown'), dict(GOAL, name=[]), dict(GOAL, extra=1),
             dict(GOAL, index=1), dict(GOAL, index=True), dict(GOAL, index=0.5),
             dict(GOAL, sources=None), dict(GOAL, sources=[None]),
             dict(GOAL, sources=[dict(SOURCE, index=1)]),
             dict(GOAL, sources=[dict(SOURCE, index=0.5)]),
             dict(GOAL, sources=[dict(SOURCE, index=True)]),
             dict(GOAL, sources=[dict(SOURCE, base=[])]),
             dict(GOAL, sources=[dict(SOURCE, base='Unknown')]),
             dict(GOAL, sources=[dict(SOURCE, extra=1)]),
             dict(GOAL, sources=[SOURCE, SOURCE]),
             dict(GOAL, sources=[{'index': 0, 'remove': True}]),
             dict(GOAL, sources=[{'index': 0, 'remove': 'true'}])]
BAD_GOALS += [dict(GOAL, value=value) for value in [None, True, [], {}, '', float('nan'), float('inf'), 10**400]]
BAD_CONDITIONS = [dict(CONDITION, **change) for change in [
    {'index': True}, {'index': 0.5}, {'index': 1}, {'goal': 'Unknown'},
    {'goal': []}, {'type': 'Unknown'}, {'field': '../Opaque'}, {'value': []}, {'extra': 1}]]


@pytest.mark.parametrize('family,bad', [('goal', row) for row in BAD_GOALS] +
                         [('condition', row) for row in BAD_CONDITIONS])
@pytest.mark.parametrize('backups', [False, True])
def test_invalid_targets_preserve_prior_valid_family(challenges, family, bad, backups):
    if backups:
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original')
    before = snapshot(challenges)
    root = s.load_file(s.GOALS_FILE)['root']
    cached = ET.tostring(root)
    with pytest.raises(ValueError):
        s.apply_challenge_edits([bad] if family == 'goal' else [GOAL], ui_edits=[LABEL],
                               condition_edits=[bad] if family == 'condition' else None)
    assert snapshot(challenges) == before
    assert s.load_file(s.GOALS_FILE)['root'] is root
    assert ET.tostring(root) == cached


@pytest.mark.parametrize('family', ['goal', 'condition'])
def test_duplicate_targets_reject(challenges, family):
    before = snapshot(challenges)
    with pytest.raises(ValueError, match='Duplicate'):
        s.apply_challenge_edits([GOAL, GOAL] if family == 'goal' else [GOAL],
                               condition_edits=[CONDITION, CONDITION] if family == 'condition' else [])
    assert snapshot(challenges) == before


@pytest.mark.parametrize('change', ['duplicate_goal', 'nonfinite_target', 'unknown_source', 'duplicate_source_field', 'unknown_condition', 'duplicate_condition_field'])
def test_unsupported_source_cannot_be_normalized(challenges, change):
    root = s.load_file(s.GOALS_FILE)['root']
    if change == 'duplicate_goal':
        root.find('goals').append(ET.fromstring(ET.tostring(root.find('goals/Item'))))
    elif change == 'nonfinite_target':
        root.find('.//desiredGoal').set('value', 'NaN')
    elif change == 'unknown_source':
        root.find('.//BaseId').text = 'Unknown'
    elif change == 'duplicate_source_field':
        ET.SubElement(root.find('.//statId'), 'BaseId').text = 'BASE'
    elif change == 'unknown_condition':
        root.find('.//ContextHash').text = 'Unknown'
    else:
        node = next(node for node in root.iter() if node.get('type') == CONDITION['type'])
        ET.SubElement(node, 'ContextHash').text = 'CHAL_CTX_ON_MOVING_TRAIN'
    s.save_file(s.GOALS_FILE)
    before = snapshot(challenges)
    cached = ET.tostring(root)
    with pytest.raises(ValueError):
        s.apply_challenge_edits([dict(GOAL, sources=[SOURCE])], condition_edits=[CONDITION])
    assert snapshot(challenges) == before
    assert s.load_file(s.GOALS_FILE)['root'] is root
    assert ET.tostring(root) == cached


def test_exact_goal_source_and_condition_save_reload(challenges):
    value = '9007199254740993.125'
    assert s.apply_challenge_edits([dict(GOAL, index=0.0, value=value,
                                         sources=[dict(SOURCE, index='0')])],
                                  condition_edits=[dict(CONDITION, index='0')]) == 3
    s._files.clear()
    root = s.load_file(s.GOALS_FILE)['root']
    assert root.find('.//desiredGoal').get('value') == value
    assert root.find('.//BaseId').text == 'SECOND'
    assert root.find('.//PermutationId').text is None
    assert root.find('.//ContextHash').text == 'CHAL_CTX_SCOPED_KIT'
    assert root.find('.//Opaque').text == 'keep'
    assert b'<!--goals-->' in s.data_file_path(s.GOALS_FILE, 'mine').read_bytes()


BAD_LABELS = [{}, dict(LABEL, file='unknown.meta'), dict(LABEL, file=[]),
              dict(LABEL, owner='Unknown'), dict(LABEL, owner=[]), dict(LABEL, extra=1),
              dict(LABEL, field='../Opaque'), dict(LABEL, field='Unknown'),
              dict(LABEL, rank=True), dict(LABEL, rank=0.5), dict(LABEL, rank=-1),
              dict(LABEL, rank=1), dict(LABEL, rank='1.5')]
BAD_LABELS += [dict(LABEL, value=value) for value in [None, True, [], {}, 12]]
BAD_MODES = [{}, {'challenge': [], 'mode': 'series'}, {'challenge': 'Unknown', 'mode': 'series'},
             {'challenge': 'Challenge', 'mode': 'series', 'extra': 1}]


@pytest.mark.parametrize('family,bad', [('label', row) for row in BAD_LABELS] +
                         [('mode', row) for row in BAD_MODES])
@pytest.mark.parametrize('backups', [False, True])
def test_bad_labels_or_modes_do_not_publish_valid_goal(challenges, family, bad, backups):
    if backups:
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original')
    before = snapshot(challenges)
    roots = {name: s.load_file(name)['root'] for name in (s.GOALS_FILE, s.CHALLENGES_FILE)}
    with pytest.raises(ValueError):
        s.apply_challenge_edits([GOAL], ui_edits=[bad] if family == 'label' else [LABEL],
                               mode_edits=[bad] if family == 'mode' else [])
    assert snapshot(challenges) == before
    assert all(s.load_file(name)['root'] is root for name, root in roots.items())


@pytest.mark.parametrize('family', ['label', 'mode'])
def test_duplicate_labels_and_modes_reject(challenges, family):
    if family == 'mode':
        record = s.load_file(s.CHALLENGES_FILE)['root'].find('challenges/Item')
        ET.SubElement(ET.SubElement(record, 'ranks'), 'Item')
        s.save_file(s.CHALLENGES_FILE)
    before = snapshot(challenges)
    mode = {'challenge': 'Challenge', 'mode': 'series'}
    with pytest.raises(ValueError, match='Duplicate'):
        s.apply_challenge_edits([GOAL], ui_edits=[LABEL, LABEL] if family == 'label' else [LABEL],
                               mode_edits=[mode, mode] if family == 'mode' else [])
    assert snapshot(challenges) == before


@pytest.mark.parametrize('change', ['owner', 'ui', 'field', 'nested'])
def test_ambiguous_or_nested_label_source_is_protected(challenges, change):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    record = root.find('challenges/Item')
    if change == 'owner':
        root.find('challenges').append(ET.fromstring(ET.tostring(record)))
    elif change == 'ui':
        record.append(ET.fromstring(ET.tostring(record.find('uiInfo'))))
    elif change == 'field':
        ET.SubElement(record.find('uiInfo'), LABEL['field']).text = 'Other'
    else:
        ET.SubElement(record.find('uiInfo/' + LABEL['field']), 'Opaque').text = 'keep'
    s.save_file(s.CHALLENGES_FILE)
    before = snapshot(challenges)
    cached = ET.tostring(root)
    with pytest.raises(ValueError):
        s.apply_challenge_edits([GOAL], ui_edits=[LABEL])
    assert snapshot(challenges) == before
    assert s.load_file(s.CHALLENGES_FILE)['root'] is root
    assert ET.tostring(root) == cached


def test_goal_and_rank_labels_save_reload_without_touching_other_fields(challenges):
    goal = s.load_file(s.GOALS_FILE)['root'].find('goals/Item')
    ui = ET.SubElement(goal, 'uiInfo')
    ET.SubElement(ui, 'pauseMenuDescriptionLabel').text = 'Old goal'
    record = s.load_file(s.CHALLENGES_FILE)['root'].find('challenges/Item')
    ranks = ET.SubElement(record, 'ranks')
    rank = ET.SubElement(ranks, 'Item')
    rank_ui = ET.SubElement(rank, 'uiInfo')
    ET.SubElement(rank_ui, 'rankDescLabel').text = 'Old rank'
    for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
        s.save_file(name)
    assert s.apply_challenge_edits([], ui_edits=[
        {'file': s.GOALS_FILE, 'owner': 'Goal', 'field': 'pauseMenuDescriptionLabel', 'value': 'New goal'},
        dict(LABEL, rank='1', field='rankDescLabel', value='New rank'), LABEL]) == 3
    s._files.clear()
    assert s.load_file(s.GOALS_FILE)['root'].find('.//pauseMenuDescriptionLabel').text == 'New goal'
    root = s.load_file(s.CHALLENGES_FILE)['root']
    assert root.find('.//rankDescLabel').text == 'New rank'
    assert root.find('.//challengeDescLabel').text == 'New label'
    assert root.find('.//Opaque').text == 'keep'


@pytest.fixture
def rewards(challenges, monkeypatch):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    record = root.find('challenges/Item')
    record.append(ET.fromstring('<ranks><Item><reward><rewards><!--reward note--><Opaque mode="keep">opaque text</Opaque><Item type="CUnlockReward"><unlock>FIXTURE_UNLOCK_1</unlock></Item></rewards></reward><Other>keep rank</Other></Item></ranks>',
                               parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))))
    s.save_file(s.CHALLENGES_FILE)
    assert b'<!--reward note-->' in s.data_file_path(s.CHALLENGES_FILE, 'mine').read_bytes()
    original = s.get_challenges
    def definitions(ds):
        result = original(ds)
        result['allowedRewards'] = [{'type': 'CUnlockReward', 'value': value}
                                    for value in ['FIXTURE_UNLOCK_1', 'FIXTURE_UNLOCK_2']]
        return result
    monkeypatch.setattr(s, 'get_challenges', definitions)
    return challenges


BAD_REWARDS = [{}, dict(REWARD, challenge='Unknown'), dict(REWARD, challenge=[]),
               dict(REWARD, rank=0), dict(REWARD, rank=True), dict(REWARD, rank=1.5),
               dict(REWARD, rank=2), dict(REWARD, owner='Other'), dict(REWARD, owner=[]),
               dict(REWARD, ownerRank=True), dict(REWARD, ownerRank=1.5), dict(REWARD, ownerRank=2),
               dict(REWARD, extra=1), dict(REWARD, rewards=None), dict(REWARD, rewards={}),
               dict(REWARD, rewards=[None]), dict(REWARD, rewards=[{}]),
               dict(REWARD, rewards=[{'type': [], 'value': 'FIXTURE_UNLOCK_2'}]),
               dict(REWARD, rewards=[{'type': 'CUnlockReward', 'value': []}]),
               dict(REWARD, rewards=[{'type': 'CUnlockReward', 'value': 'Unknown'}]),
               dict(REWARD, rewards=[{'type': 'CUnlockReward', 'value': 'FIXTURE_UNLOCK_2', 'extra': 1}]),
               dict(REWARD, rewards=[{'type': 'CUnlockReward', 'value': 'CHALLENGE_REWARD_TYPE_MONEY_UNKNOWN'}])]


@pytest.mark.parametrize('bad', BAD_REWARDS)
@pytest.mark.parametrize('backups', [False, True])
def test_bad_reward_batch_preserves_files_backups_and_roots(rewards, bad, backups):
    if backups:
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original')
    before = snapshot(rewards)
    roots = {name: s.load_file(name)['root'] for name in (s.GOALS_FILE, s.CHALLENGES_FILE)}
    cached = {name: ET.tostring(root) for name, root in roots.items()}
    with pytest.raises(ValueError):
        s.apply_challenge_edits([GOAL], reward_edits=[bad], ui_edits=[LABEL])
    assert snapshot(rewards) == before
    for name, root in roots.items():
        assert s.load_file(name)['root'] is root
        assert ET.tostring(root) == cached[name]


@pytest.mark.parametrize('change', ['unknown_value', 'extra_field', 'extra_attribute', 'nested_value',
                                  'duplicate_value', 'duplicate_owner', 'duplicate_container', 'text'])
def test_unsupported_reward_source_is_protected(rewards, change):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    container = root.find('.//rewards')
    item = container.find('Item')
    if change == 'unknown_value':
        item.find('unlock').text = 'Unknown'
    elif change == 'extra_field':
        ET.SubElement(item, 'Future').text = 'keep'
    elif change == 'extra_attribute':
        item.set('future', 'keep')
    elif change == 'nested_value':
        ET.SubElement(item.find('unlock'), 'Future').text = 'keep'
    elif change == 'duplicate_value':
        ET.SubElement(item, 'unlock').text = 'FIXTURE_UNLOCK_1'
    elif change == 'duplicate_owner':
        root.find('challenges').append(ET.fromstring(ET.tostring(root.find('challenges/Item'))))
    elif change == 'duplicate_container':
        root.find('.//reward').append(ET.fromstring(ET.tostring(container)))
    else:
        container.text = 'future text'
    s.save_file(s.CHALLENGES_FILE)
    reader_rank = REAL_GET_CHALLENGES()['strands'][0]['ranks'][0]
    assert reader_rank['rewardsReadonly'] is (change != 'unknown_value')
    before = snapshot(rewards)
    cached = ET.tostring(root)
    with pytest.raises(ValueError):
        s.apply_challenge_edits([GOAL], reward_edits=[REWARD])
    assert snapshot(rewards) == before
    assert s.load_file(s.CHALLENGES_FILE)['root'] is root
    assert ET.tostring(root) == cached


def test_reward_reader_keeps_empty_unsupported_reward(rewards):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    rank = REAL_GET_CHALLENGES()['strands'][0]['ranks'][0]
    assert rank['rewardsReadonly'] is False
    ET.SubElement(root.find('.//rewards'), 'Item', type='FutureReward')
    s.save_file(s.CHALLENGES_FILE)
    rank = REAL_GET_CHALLENGES()['strands'][0]['ranks'][0]
    assert rank['rewardsReadonly'] is True
    assert rank['rewards'][-1] == {'type': 'FutureReward', 'value': ''}


def test_duplicate_reward_target_rejects(rewards):
    before = snapshot(rewards)
    with pytest.raises(ValueError, match='Duplicate'):
        s.apply_challenge_edits([GOAL], reward_edits=[REWARD, REWARD])
    assert snapshot(rewards) == before


def test_http_reward_save_remove_reload_preserves_opaque_siblings(rewards):
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def post(reward):
        return Request(f'http://127.0.0.1:{http.server_port}/api/challenges/save',
                       data=json.dumps({'edits': [GOAL], 'rewards': [reward]}).encode(),
                       headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(rewards)
        with pytest.raises(HTTPError) as error:
            urlopen(post(dict(REWARD, rank=1.5)))
        assert error.value.code == 400
        assert snapshot(rewards) == before
        for values in [REWARD['rewards'], []]:
            with urlopen(post(dict(REWARD, rewards=values))) as response:
                assert json.load(response)['saved'] == 2
            s._files.clear()
            root = s.load_file(s.CHALLENGES_FILE)['root']
            assert [node.text for node in root.findall('.//rewards/Item/unlock')] == [row['value'] for row in values]
            assert root.find('.//rewards/Opaque').text == 'opaque text'
            assert root.find('.//rewards/Opaque').get('mode') == 'keep'
            assert root.find('.//Other').text == 'keep rank'
            assert b'<!--reward note-->' in s.data_file_path(s.CHALLENGES_FILE, 'mine').read_bytes()
        assert s.load_file(s.GOALS_FILE)['root'].find('.//desiredGoal').get('value') == '12'
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_split_strand_reward_uses_logical_rank_and_exact_owner(rewards):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    record = root.find('challenges/Item')
    record.find('name').text = 'SP_CHAL_FIXTURE_ROOT_2'
    s.save_file(s.CHALLENGES_FILE)
    edit = dict(REWARD, challenge='SP_CHAL_FIXTURE_ROOT', rank='2',
                owner='SP_CHAL_FIXTURE_ROOT_2', ownerRank='1')
    assert s.apply_challenge_edits([], reward_edits=[edit]) == 1
    s._files.clear()
    assert s.load_file(s.CHALLENGES_FILE)['root'].find('.//unlock').text == 'FIXTURE_UNLOCK_2'


@pytest.fixture
def strands(challenges):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    collection = root.find('challenges')
    template = collection.find('Item')
    collection.remove(template)
    for number in [1, 2]:
        record = ET.fromstring(ET.tostring(template))
        record.find('name').text = f'SP_CHAL_FIXTURE_ROOT_{number}'
        ranks = ET.SubElement(record, 'ranks')
        ranks.append(ET.Comment(f'rank note {number}'))
        item = ET.SubElement(ranks, 'Item')
        ET.SubElement(item, 'RankMarker').text = str(number)
        ET.SubElement(item, 'OpaqueRank').text = f'keep {number}'
        collection.append(record)
    s.save_file(s.CHALLENGES_FILE)
    return challenges


MODE = {'challenge': 'SP_CHAL_FIXTURE_ROOT', 'mode': 'series'}


def test_series_merge_preserves_rank_order_comments_and_metadata(strands):
    assert s.apply_challenge_edits([GOAL], mode_edits=[MODE]) == 2
    s._files.clear()
    root = s.load_file(s.CHALLENGES_FILE)['root']
    records = root.findall('challenges/Item')
    assert len(records) == 1
    assert records[0].findtext('name') == MODE['challenge']
    assert [item.findtext('RankMarker') for item in records[0].findall('ranks/Item')] == ['1', '2']
    assert [item.findtext('OpaqueRank') for item in records[0].findall('ranks/Item')] == ['keep 1', 'keep 2']
    assert records[0].findtext('Opaque') == 'keep'
    assert records[0].findtext('uiInfo/challengeDescLabel') == 'Old label'
    payload = s.data_file_path(s.CHALLENGES_FILE, 'mine').read_bytes()
    assert b'<!--rank note 1-->' in payload and b'<!--rank note 2-->' in payload
    assert s.load_file(s.GOALS_FILE)['root'].find('.//desiredGoal').get('value') == '12'


@pytest.mark.parametrize('change', ['duplicate_identity', 'mixed_identity', 'different_root_data',
                                  'different_rank_attributes', 'unknown_rank_metadata',
                                  'missing_ranks', 'duplicate_name', 'root_tail'])
@pytest.mark.parametrize('backups', [False, True])
def test_unsafe_series_merge_preserves_original_strands(strands, change, backups):
    root = s.load_file(s.CHALLENGES_FILE)['root']
    record = root.findall('challenges/Item')[1]
    if change == 'duplicate_identity':
        record.find('name').text = 'SP_CHAL_FIXTURE_ROOT_1'
    elif change == 'mixed_identity':
        record.find('name').text = MODE['challenge']
    elif change == 'different_root_data':
        record.find('Opaque').text = 'different data'
    elif change == 'different_rank_attributes':
        record.find('ranks').set('future', 'keep')
    elif change == 'unknown_rank_metadata':
        ET.SubElement(record.find('ranks'), 'Future').text = 'keep'
    elif change == 'missing_ranks':
        record.remove(record.find('ranks'))
    elif change == 'duplicate_name':
        ET.SubElement(record, 'name').text = 'SP_CHAL_FIXTURE_ROOT_2'
    else:
        record.tail = 'future text'
    s.save_file(s.CHALLENGES_FILE)
    if backups:
        for name in (s.GOALS_FILE, s.CHALLENGES_FILE):
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original')
    before = snapshot(strands)
    cached = ET.tostring(root)
    with pytest.raises(ValueError):
        s.apply_challenge_edits([GOAL], mode_edits=[MODE])
    assert snapshot(strands) == before
    assert s.load_file(s.CHALLENGES_FILE)['root'] is root
    assert ET.tostring(root) == cached


def test_series_merge_disk_failure_retains_original_strands(strands, monkeypatch):
    before = snapshot(strands)
    roots = {name: s.load_file(name)['root'] for name in (s.GOALS_FILE, s.CHALLENGES_FILE)}
    replace = s.os.replace
    failed = False
    target = s.data_file_path(s.CHALLENGES_FILE, 'mine')
    def fail(source, destination):
        nonlocal failed
        if destination == target and not failed:
            failed = True
            raise OSError('injected final strand publication failure')
        return replace(source, destination)
    monkeypatch.setattr(s.os, 'replace', fail)
    with pytest.raises(OSError):
        s.apply_challenge_edits([GOAL], mode_edits=[MODE])
    assert snapshot(strands) == before
    assert all(s.load_file(name)['root'] is root for name, root in roots.items())


def test_reader_keeps_empty_source_slot_and_writer_uses_displayed_index(challenges):
    root = s.load_file(s.GOALS_FILE)['root']
    parent = root.find('.//scoreParams/Item')
    parent.insert(0, ET.Element('statId'))
    condition = next(node for node in root.iter() if node.get('type') == CONDITION['type'])
    condition.append(ET.Comment('condition note'))
    s.save_file(s.GOALS_FILE)
    data = REAL_GET_CHALLENGES('mine')
    sources = data['goals'][0]['requirements'][0]['sources']
    assert [source['index'] for source in sources] == [0, 1]
    assert sources[0]['readonly'] and sources[0]['base'] == ''
    assert sources[1]['base'] == 'BASE' and not sources[1]['readonly']
    assert list(data['goals'][0]['conditions'][0]['fields']) == ['ContextHash']
    assert s.apply_challenge_edits([dict(GOAL, sources=[dict(SOURCE, index=1)])]) == 2
    s._files.clear()
    root = s.load_file(s.GOALS_FILE)['root']
    stats = list(root.find('.//scoreParams/Item').iter('statId'))
    assert len(stats) == 2 and len(stats[0]) == 0
    assert stats[1].findtext('BaseId') == 'SECOND'
    assert b'<!--condition note-->' in s.data_file_path(s.GOALS_FILE, 'mine').read_bytes()


@pytest.mark.parametrize('change', ['nonfinite', 'duplicate_name', 'duplicate_goal'])
def test_reader_marks_uneditable_targets_readonly(challenges, change):
    root = s.load_file(s.GOALS_FILE)['root']
    goal = root.find('goals/Item')
    if change == 'nonfinite':
        goal.find('.//desiredGoal').set('value', 'NaN')
    elif change == 'duplicate_name':
        ET.SubElement(goal, 'name').text = 'Goal'
    else:
        root.find('goals').append(ET.fromstring(ET.tostring(goal)))
    s.save_file(s.GOALS_FILE)
    assert all(row['requirements'][0]['readonly'] for row in REAL_GET_CHALLENGES('mine')['goals'])
