"""Repeated author builds reuse compression; cache damage cannot stop a save."""
import struct
import zlib

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
