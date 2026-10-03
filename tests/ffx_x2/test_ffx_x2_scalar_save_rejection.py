"""Real battle-table save routes reject malformed batches without output changes."""
from pathlib import Path
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from core.service_session import request_json
from plugins.ffx_x2 import ctb_base, ffx_commands, ffx_auto_abilities, ffx2_abilities
from plugins.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from test_ffx_x2_scalar_write_validation import authored_codec


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind', ['ctb', 'auto', 'x2', *ffx_commands.TABLES])
def test_battle_table_http_rejection_preserves_project_and_archives(tmp_path, kind):
    raw, _, good, patches = authored_codec(kind)
    if kind == 'ctb':
        path, route = ctb_base.ARCHIVE_PATH, 'ctb-base'
    elif kind == 'auto':
        path, route = ffx_auto_abilities.ARCHIVE_PATH, 'ffx-auto-abilities'
    elif kind == 'x2':
        path, route = ffx2_abilities.ARCHIVE_PATH, 'ffx2-abilities'
    else:
        path, route = ffx_commands.TABLES[kind].archive_path, 'ffx-commands'
    game = 'x2' if kind == 'x2' else 'x'
    archive_name = 'FFX2_Data' if game == 'x2' else 'FFX_Data'
    game_root, project_root = tmp_path / 'game', tmp_path / 'project'
    _write_fixture_vbf(game_root / 'data' / f'{archive_name}.vbf',
                       [(path.removeprefix(archive_name + '/'), raw)])
    vanilla = snapshot(game_root)
    target = project_root / 'efl' / game / Path(*path.split('/'))
    with FFXX2Session({
        'LEXEDITOR_FFX_X2_ROOT': str(game_root),
        'LEXEDITOR_FFX_X2_PROJECT': str(project_root),
        'LEXEDITOR_FFX_X2_THEME_CACHE': str(tmp_path / 'theme'),
    }) as session:
        query = f'?table={kind}' if route == 'ffx-commands' else ''
        state = request_json(session.url + f'api/{route}' + query)
        def request(edits):
            body = dict(headerMd5=state['headerMd5'], baselineSha256=state['baselineSha256'], edits=edits)
            if route == 'ffx-commands':
                body['table'] = kind
            return Request(session.url + f'api/{route}/save', data=json.dumps(body).encode(),
                           headers={'Content-Type': 'application/json'})
        def reject_all():
            for field in good:
                for value in (False, .5, float('inf'), float('nan')):
                    before = snapshot(project_root)
                    with pytest.raises(HTTPError) as failure:
                        urlopen(request([good | dict(id=1), good | {field: value}]), timeout=5)
                    assert failure.value.code == 400
                    failure.value.close()
                    assert snapshot(project_root) == before
                    assert snapshot(game_root) == vanilla
        reject_all()
        assert not target.exists()
        with urlopen(request([good]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        expected = bytearray(raw)
        for offset, payload in patches.items():
            expected[offset:offset + len(payload)] = payload
        assert target.read_bytes() == expected
        state = request_json(session.url + f'api/{route}' + query)
        assert state['source'] == 'project'
        reject_all()
        assert target.read_bytes() == expected
        assert snapshot(game_root) == vanilla
    assert session.wait_closed()
