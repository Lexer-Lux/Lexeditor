"""Build freshness reads stay small without weakening size or content checks."""
import hashlib
import io
import json

import pytest

from core import build_dependencies, mod_metadata, script_mods
from core.plugin_files import read_bounded


class ShortReads(io.BytesIO):
    def read(self, size=-1):
        assert 0 < size <= 64 * 1024
        return super().read(min(size, 17))


def test_short_reads_continue_to_eof_or_the_exact_limit():
    payload = b'abc' * 50000
    stream = ShortReads(payload)
    assert read_bounded(stream, 100003) == payload[:100003]
    assert stream.tell() == 100003
    assert read_bounded(stream, len(payload)) == payload[100003:]
    assert read_bounded(stream, 0) == b''


def test_metadata_preserves_text_and_rejects_oversized_input(tmp_path, monkeypatch):
    payload = json.dumps({'name': 'Example', 'description': 'writing ' * 20000}).encode()
    (tmp_path/'mod.json').write_bytes(payload)
    assert mod_metadata._stored(tmp_path)['description'] == 'writing ' * 20000
    assert script_mods._read_json(tmp_path/'mod.json')['name'] == 'Example'
    monkeypatch.setattr(mod_metadata, 'MAX_BYTES', len(payload)-1)
    monkeypatch.setattr(script_mods, 'MAX_METADATA_BYTES', len(payload)-1)
    with pytest.raises(mod_metadata.MetadataError, match='metadata limit'):
        mod_metadata._stored(tmp_path)
    with pytest.raises(script_mods.ScriptModError, match='metadata limit'):
        script_mods._read_json(tmp_path/'mod.json')


def test_source_and_repository_hashes_observe_edits_and_limits(tmp_path, monkeypatch):
    (tmp_path/'script').mkdir()
    (tmp_path/'mod.json').write_text('{"name":"Example","script":{"version":1}}')
    source = tmp_path/'script/tweak.py'
    source.write_bytes(b'# source\n' * 9000)
    first = script_mods.source_fingerprint(tmp_path)
    assert build_dependencies.fingerprint('script/tweak.py', tmp_path) == hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_bytes(source.read_bytes()+b'# changed\n')
    assert script_mods.source_fingerprint(tmp_path) != first
    monkeypatch.setattr(script_mods, 'MAX_SOURCE_BYTES', source.stat().st_size-1)
    monkeypatch.setattr(build_dependencies, 'MAX_INPUT_BYTES', source.stat().st_size-1)
    with pytest.raises(script_mods.ScriptModError, match='size limit'):
        script_mods.source_fingerprint(tmp_path)
    with pytest.raises(ValueError, match='size limit'):
        build_dependencies.fingerprint('script/tweak.py', tmp_path)
