"""Repeated author builds reuse compression; cache damage cannot stop a save."""
import struct
import zlib
import json
import hashlib

import pytest
from plugins.ds1 import formats, composition_cache
from flver_fixture import DCX_HEADER


def dcx(plain):
    compressed=zlib.compress(plain,9)
    header=bytearray(DCX_HEADER)
    struct.pack_into('>II',header,28,len(plain),len(compressed))
    return bytes(header)+compressed


def test_repeated_content_reuses_exact_compressed_bytes_with_each_original_header(monkeypatch):
    original=dcx(b'original'*100)
    plain=b'bonfire commands'*1000
    first=formats.deflate(original,plain)
    header=bytearray(original);header[52]^=1
    def no_compression(*_):raise AssertionError('unchanged content was compressed again')
    monkeypatch.setattr(formats.zlib,'compress',no_compression)
    second=formats.deflate(bytes(header),plain)
    assert second[76:]==first[76:]
    assert second[52]==header[52]
    assert formats.inflate(second)==plain


@pytest.mark.parametrize('bad',[b'broken',zlib.compress(b'other archive'*100,9)])
def test_valid_checksum_with_broken_or_wrong_cached_stream_rebuilds(monkeypatch,bad):
    original=dcx(b'original'*100);plain=b'bonfire commands'*1000
    monkeypatch.setattr(composition_cache,'load',lambda *_:bad)
    result=formats.deflate(original,plain)
    assert result[76:]==zlib.compress(plain,9)
    assert formats.inflate(result)==plain


def test_unavailable_cache_does_not_fail_build_and_bounds_still_apply(monkeypatch):
    original=dcx(b'original'*100);plain=b'bonfire commands'*1000
    def unavailable(*_):raise OSError('cache unavailable')
    monkeypatch.setattr(composition_cache,'load',unavailable)
    monkeypatch.setattr(composition_cache,'store',unavailable)
    assert formats.inflate(formats.deflate(original,plain))==plain
    with pytest.raises(formats.FormatError,match='size limit'):
        formats.deflate(original,b'x'*2000,max_size=1000)
    with pytest.raises(formats.FormatError):
        formats.deflate(b'broken',plain)


def test_generated_outputs_restore_evicted_compression_without_rebuilding_it(tmp_path,monkeypatch):
    from plugins.ds1 import script_worker
    plain=b'unchanged generated bonfire commands'*1000
    produced=dcx(plain)
    path=tmp_path/'script/talk/generated.talkesdbnd.dcx'
    path.parent.mkdir(parents=True);path.write_bytes(produced)
    (tmp_path/'.lexeditor-generated.json').write_text(json.dumps({'version':1,'files':{
        'script/talk/generated.talkesdbnd.dcx':hashlib.sha256(produced).hexdigest()}}))
    def no_compression(*_):raise AssertionError('owned output was recompressed after cache eviction')
    original=dcx(b'vanilla bonfire commands'*1000)
    monkeypatch.setattr(formats.zlib,'compress',no_compression)
    with formats.compression_sources(script_worker._seed_compression(tmp_path)):
        assert formats.deflate(original,plain)==produced


def test_unchanged_original_needs_neither_cache_nor_compression(monkeypatch):
    plain=b'unchanged original'*100
    original=dcx(plain)
    def unnecessary(*_):raise AssertionError('unchanged original requested compression or cache')
    monkeypatch.setattr(composition_cache,'load',unnecessary)
    monkeypatch.setattr(formats.zlib,'compress',unnecessary)
    assert formats.deflate(original,plain)==original


def test_bad_seed_is_optional_and_cannot_poison_requested_content(tmp_path):
    from plugins.ds1 import script_worker
    path=tmp_path/'script/talk/broken.talkesdbnd.dcx'
    path.parent.mkdir(parents=True);path.write_bytes(b'DCX\0broken')
    (tmp_path/'.lexeditor-generated.json').write_text(json.dumps({'version':1,'files':{
        'script/talk/broken.talkesdbnd.dcx':hashlib.sha256(path.read_bytes()).hexdigest()}}))
    plain=b'valid output'*100
    with formats.compression_sources(script_worker._seed_compression(tmp_path)):
        assert formats.inflate(formats.deflate(dcx(b'original'*100),plain))==plain


def test_warm_compression_never_reads_prior_generated_archives(monkeypatch):
    plain=b'reused output'*1000
    original=dcx(b'original'*100)
    expected=formats.deflate(original,plain)
    def unnecessary():
        raise AssertionError('a cache hit scanned prior output archives')
        yield
    def no_compression(*_):raise AssertionError('a cache hit recompressed output')
    monkeypatch.setattr(formats.zlib,'compress',no_compression)
    with formats.compression_sources(unnecessary()):
        assert formats.deflate(original,plain)==expected
    assert formats._compression_sources.get() is None


def test_broken_optional_sources_do_not_fail_compression(monkeypatch):
    plain=b'new output'*1000
    original=dcx(b'original'*100)
    monkeypatch.setattr(composition_cache,'load',lambda *_:None)
    def unavailable():
        raise OSError('owned outputs temporarily unavailable')
        yield
    with formats.compression_sources(unavailable()):
        assert formats.inflate(formats.deflate(original,plain))==plain


@pytest.mark.parametrize('kind', ['item', 'menu'])
def test_text_exports_reuse_shared_compression(kind, tmp_path, monkeypatch):
    from ds1_fixture import make_text_archive, make_menu_archive
    from plugins.ds1 import texts, mod_loader
    monkeypatch.setattr(composition_cache, 'user_root', lambda: tmp_path/'cache')
    original = make_text_archive() if kind == 'item' else make_menu_archive()
    def edited():
        document = texts.TextDocument(original) if kind == 'item' else texts.MenuDocument(original)
        if kind == 'item': document.rename('EquipParamGoods', 100, 'New name')
        else: document.set_label('magicDefense', 'Magic defense')
        return document
    expected = edited().export()
    def no_compression(*_): raise AssertionError('an identical text archive was compressed again')
    monkeypatch.setattr(formats.zlib, 'compress', no_compression)
    assert edited().export() == expected
    assert formats.inflate(expected) != formats.inflate(original)
    document = texts.TextDocument if kind == 'item' else texts.MenuDocument
    merged, conflicts = mod_loader._compose_texts(original, [('Mod', expected)], document=document)
    assert merged == expected and not conflicts
