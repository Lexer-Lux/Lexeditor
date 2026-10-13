"""Main-table writes reject malformed scalars and preserve unrelated bytes."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import kernel_text, namedic, paths, wm2field
from plugins.ff8.server import create_server


def names(text='One'):
    chunks = [kernel_text.encode(text, compress=False) + b'\0\0\0',
              kernel_text.encode('Two', compress=False) + b'\0\0',
              kernel_text.encode('Other', compress=False) + b'\0\0\0\0']
    offsets = [8, 8 + len(chunks[0]), 8 + len(chunks[0]) + len(chunks[1])]
    return struct.pack('<4H', 3, *offsets) + b''.join(chunks)


def world():
    raw = bytearray([0xA5] * (wm2field.ENTRY_COUNT * wm2field.ENTRY_SIZE))
    for i in range(wm2field.ENTRY_COUNT):
        struct.pack_into('<hhHH', raw, i * wm2field.ENTRY_SIZE, i, -i, i + 1, i + 2)
    return bytes(raw)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['namedic', 'wm2field'])
def files(tmp_path, monkeypatch, request):
    module = namedic if request.param == 'namedic' else wm2field
    original = names() if module is namedic else world()
    source = tmp_path / 'vanilla.bin'
    source.write_bytes(original)
    output = tmp_path / 'mod'
    destination = output / module.DIRECT_RELATIVE
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(module, 'source_path', lambda dataset: destination if dataset == 'current' and destination.exists() else source)
    good = dict(index=0, text='Changed longer') if module is namedic else dict(id=0, x=-32768, y=32767, z=65535, fieldId=0)
    return tmp_path, module, source, destination, original, good


@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('-inf'), float('nan'), '1.5', None])
def test_main_tables_invalid_later_scalars_preserve_outputs(files, value):
    root, module, source, destination, original, good = files
    fields = ['index'] if module is namedic else ['id', 'x', 'y', 'z', 'fieldId']
    later = good | ({'index': 1} if module is namedic else {'id': 1})
    for field in fields:
        before = snapshot(root)
        with pytest.raises(ValueError):
            module.save([good, later | {field: value}])
        assert snapshot(root) == before
    assert not destination.exists()
    module.save([good])
    for field in fields:
        before = snapshot(root)
        with pytest.raises(ValueError):
            module.save([good, later | {field: value}])
        assert snapshot(root) == before
    assert source.read_bytes() == original


def expected(files):
    _, module, _, _, original, _ = files
    if module is namedic:
        return names('Changed longer')
    raw = bytearray(original)
    struct.pack_into('<hhHH', raw, 0, -32768, 32767, 65535, 0)
    return bytes(raw)


def test_main_tables_valid_reload_keeps_padding_reserved_bytes_and_vanilla(files):
    _, module, source, destination, original, good = files
    assert module.apply_edits(original, []) == original
    result = module.save([good])
    assert destination.read_bytes() == expected(files)
    assert source.read_bytes() == original
    if module is namedic:
        assert [e['text'] for e in result['entries']] == ['Changed longer', 'Two', 'Other']
        assert [e['padding'] for e in result['entries']] == [2, 1, 3]
    else:
        assert tuple(result['rows'][0][field] for field in ('x', 'y', 'z', 'fieldId')) == (-32768, 32767, 65535, 0)
        assert result['rows'][0]['pointer'] == 0xA5


def test_main_table_bounds_duplicate_and_text_rejections(files):
    root, module, _, _, _, good = files
    if module is namedic:
        invalid = [good | dict(index=-1), good | dict(index=3), good,
                   good | dict(index=1, text=None), good | dict(index=1, text='a\0b'),
                   good | dict(index=1, text='\U0010FFFF'), good | dict(index=2, text='A' * 65535)]
    else:
        invalid = [good | dict(id=-1), good | dict(id=72), good, good | dict(id=1, x=-32769),
                   good | dict(id=1, y=32768), good | dict(id=1, z=65536), good | dict(id=1, fieldId=-1)]
    module.save([good])
    for bad in invalid:
        before = snapshot(root)
        with pytest.raises(ValueError):
            module.save([good, bad])
        assert snapshot(root) == before


def test_main_table_http_invalid_later_identity_then_valid_reload(files):
    root, module, source, destination, original, good = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/{module.__name__.rsplit(".", 1)[1]}/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        field = 'index' if module is namedic else 'id'
        for value in (.5, False, float('inf')):
            before = snapshot(root)
            with pytest.raises(HTTPError) as failure:
                urlopen(request([good, good | {field: value}]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
        with urlopen(request([good]), timeout=5) as response:
            assert json.load(response)['count'] == (3 if module is namedic else 72)
        assert destination.read_bytes() == expected(files)
        assert source.read_bytes() == original
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
