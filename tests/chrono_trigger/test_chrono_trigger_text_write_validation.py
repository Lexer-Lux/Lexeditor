"""Localization rejection cannot write an earlier record or unrelated resource."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.text_data import load_messages, save_messages
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from test_chrono_trigger_replacement import build_archive

PATH = 'Localize/en/msg/authored.txt'
OTHER = 'Game/authored.txt'
ORIGINAL = b'\xef\xbb\xbfA,First, comma\r\n# untouched\nB,Second\rC,Last'


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(**changes):
    return dict(line=0, key='A', text='Changed, longer') | changes


@pytest.fixture
def files(tmp_path):
    game = tmp_path / 'game'
    game.mkdir()
    archive = game / 'resources.bin'
    build_archive(archive, [(PATH, ORIGINAL), (OTHER, ORIGINAL)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(archive), project)
    return tmp_path, game, project, store


@pytest.mark.parametrize('changes', [dict(line=v) for v in (False, True, .5, float('inf'), float('nan'), '2.5', None)] +
                         [dict(text=v) for v in (None, True, 2, {}, [])] +
                         [dict(key=v) for v in (None, True, 2, {}, [])])
def test_text_invalid_later_scalar_preserves_new_and_existing_outputs(files, changes):
    root, _, project, store = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_messages(store, PATH, digest(ORIGINAL), [edit(), edit(line=2, key='B') | changes])
    assert snapshot(root) == before
    assert not (project / PATH).exists()
    save_messages(store, PATH, digest(ORIGINAL), [edit()])
    raw, _ = store.read(PATH)
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_messages(store, PATH, digest(raw), [edit(text='Another'), edit(line=2, key='B') | changes])
    assert snapshot(root) == before


@pytest.mark.parametrize('path', [OTHER, 'Localize/en/other/authored.txt', '../authored.txt', None])
def test_text_path_rejection_precedes_writes(files, path):
    root, _, _, store = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_messages(store, path, digest(ORIGINAL), [edit()])
    assert snapshot(root) == before


@pytest.mark.parametrize('bad', [edit(line=2, key='wrong'), edit(line=4), edit(line=-1), edit(),
                                edit(line=2, key='B', text='line\nbreak'), None])
def test_text_rejected_batch_preserves_existing_files(files, bad):
    root, _, _, store = files
    save_messages(store, PATH, digest(ORIGINAL), [edit()])
    raw, _ = store.read(PATH)
    before = snapshot(root)
    with pytest.raises((ValueError, RuntimeError)):
        save_messages(store, PATH, digest(raw), [edit(text='Another'), bad])
    assert snapshot(root) == before


def test_text_valid_reload_keeps_bom_line_endings_comments_and_other_lines(files):
    _, game, project, store = files
    before = snapshot(game)
    saved = save_messages(store, PATH, digest(ORIGINAL), [edit()])
    assert saved['rows'][0]['text'] == 'Changed, longer'
    assert (project / PATH).read_bytes() == ORIGINAL.replace(b'First, comma', b'Changed, longer')
    assert snapshot(game) == before


def test_text_http_rejects_later_id_nontext_and_nonlocalization_path(files):
    _, game, project, _ = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(path, edits, checksum=digest(ORIGINAL)):
            return Request(session.url + 'api/messages/save',
                           data=json.dumps(dict(path=path, sha256=checksum, edits=edits)).encode(),
                           headers={'Content-Type': 'application/json'})
        for path, batch in [(PATH, [edit(), edit(line=2.5, key='B')]),
                            (PATH, [edit(), edit(line=2, key='B', text=None)]),
                            (OTHER, [edit()])]:
            before = snapshot(project)
            with pytest.raises(HTTPError) as failure:
                urlopen(request(path, batch), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(project) == before
            assert snapshot(game) == vanilla
        with urlopen(request(PATH, [edit()]), timeout=5) as response:
            assert json.load(response)['rows'][0]['text'] == 'Changed, longer'
        assert (project / PATH).read_bytes() == ORIGINAL.replace(b'First, comma', b'Changed, longer')
        assert snapshot(game) == vanilla
    assert session.wait_closed()
