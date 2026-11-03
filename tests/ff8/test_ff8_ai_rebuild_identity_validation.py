"""Structured AI identities cannot silently select a different script/opcode."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import enemy_ai, enemy_battle_text, formats
from plugins.ff8.server import create_server
from test_ff8_ai_dialogue_batch_validation import script_files, operand
from test_ff8_enemy_batch_validation import files, snapshot


@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('-inf'), float('nan'), '1.5', None])
@pytest.mark.parametrize('field', ['script', 'opcode', 'source'])
def test_ai_rebuild_invalid_scalar_preserves_batch_and_existing_outputs(script_files, value, field):
    root, _, output, raw = script_files
    scripts = deepcopy(enemy_ai.read(raw)['scripts'])
    if field == 'source':
        sources = [dict(id=row['id'], source=row['source']) for row in scripts]
        sources[0]['id'] = value
        document = dict(id=1, sources=sources)
    else:
        if field == 'script':
            scripts[0]['id'] = value
        else:
            scripts[0]['instructions'][0]['opcode'] = value
        document = dict(id=1, scripts=scripts)
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        formats.save_enemy_ai([operand()], documents=[document])
    assert snapshot(root) == before and not output.exists()
    formats.save_enemy_ai([operand(), operand(1)])
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        formats.save_enemy_ai([operand() | dict(value=3)], documents=[document])
    assert snapshot(root) == before


@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5', None])
def test_ai_template_and_source_parser_require_exact_ids(value):
    with pytest.raises(ValueError, match='integer'):
        enemy_ai.instruction_template(value)
    with pytest.raises(ValueError, match='integer'):
        enemy_ai.parse_script('L0: Stop[0]', value)


@pytest.mark.parametrize('scripts', [None, {}, 'invalid', [None] * 5, []])
def test_ai_rebuild_shape_rejection_writes_nothing(script_files, scripts):
    root, _, _, _ = script_files
    before = snapshot(root)
    with pytest.raises(ValueError):
        formats.save_enemy_ai([operand()], documents=[dict(id=1, scripts=scripts)])
    assert snapshot(root) == before


def test_ai_rebuild_valid_integer_ids_and_opcodes_preserve_dialogue_and_vanilla(script_files):
    _, source, output, raw = script_files
    scripts = deepcopy(enemy_ai.read(raw)['scripts'])
    for script in scripts:
        script['id'] = float(script['id'])
    scripts[0]['instructions'][0]['opcode'] = 13.0
    scripts[0]['instructions'][0]['operands'][0]['value'] = 4
    assert formats.save_enemy_ai([], documents=[dict(id=0, scripts=scripts)])['saved'] == 1
    saved = (output / 'battle' / 'c0m000.dat').read_bytes()
    assert enemy_ai.read(saved)['scripts'][0]['instructions'][0]['operands'][0]['value'] == 4
    assert enemy_battle_text.read(saved)['lines'] == enemy_battle_text.read(raw)['lines']
    assert saved[16:20] == raw[16:20] == b'KEEP'
    assert all(p.read_bytes() == raw for p in source.iterdir())


def test_ai_rebuild_http_rejects_script_and_opcode_scalars(script_files):
    root, _, _, raw = script_files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/enemy-ai/save'
        for field in ('id', 'opcode'):
            scripts = deepcopy(enemy_ai.read(raw)['scripts'])
            if field == 'id':
                scripts[0]['id'] = .5
            else:
                scripts[0]['instructions'][0]['opcode'] = 13.5
            before = snapshot(root)
            body = dict(edits=[operand()], documents=[dict(id=1, scripts=scripts)])
            request = Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            with pytest.raises(HTTPError) as failure:
                urlopen(request, timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
