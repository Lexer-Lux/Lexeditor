"""Fast LZS decoder output and archive-index caching (synthetic only)."""

from __future__ import annotations

import os
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import fs_archive  # noqa: E402
from plugins.ff8.fs_archive import FsArchive, clear_archive_cache, open_archive  # noqa: E402
from plugins.ff8.lzs_decode import decode_lzs  # noqa: E402
from plugins.ff8.vendor.ff8ue.lzs import Lzs  # noqa: E402


def _vendored(payload: bytes) -> bytes:
    return bytes(Lzs().decode(payload))


def test_literals():
    assert decode_lzs(b"\xffABCDEFGH") == b"ABCDEFGH"


def test_match_copies_history():
    # Literal A, literal B, then a 3-byte match at ring position 4078,
    # where A was just written: output AB + ABA.
    assert decode_lzs(b"\x03AB\xee\xf0") == b"ABABA"


def test_match_may_overlap_its_source():
    # Literal A, then a 5-byte match one byte back: each A copies
    # itself as it lands.
    assert decode_lzs(b"\x01A\xee\xf2") == b"AAAAAA"


def test_match_at_write_position_reads_zeros():
    # A match pointing at the current write position reads unwritten ring
    # history, which starts zeroed.
    assert decode_lzs(b"\x00\xee\xf0") == b"\x00\x00\x00"


def test_truncated_stream_stops():
    assert decode_lzs(b"\xffABC") == b"ABC"
    assert decode_lzs(b"") == b""


def test_matches_vendored_decoder_on_vectors():
    vectors = [b"\xffABCDEFGH", b"\x03AB\xee\xf0", b"\x01A\xee\xf2",
               b"\x00\xee\xf0", b"\xffABC", b"", b"\x00\x00\x00",
               bytes(range(256))]
    for payload in vectors:
        assert decode_lzs(payload) == _vendored(payload), payload[:8]


def test_matches_vendored_decoder_on_fuzz():
    random.seed(20261011)
    for _ in range(200):
        payload = bytes(random.randrange(256)
                        for _ in range(random.randrange(64)))
        assert decode_lzs(payload) == _vendored(payload)


def _write_triplet(folder: Path, body: bytes) -> Path:
    prefix = folder / "arc"
    prefix.with_suffix(".fl").write_text("data\\FILE.DAT\n", encoding="utf-8")
    prefix.with_suffix(".fi").write_bytes(
        struct.pack("<III", len(body), 0, 0))
    prefix.with_suffix(".fs").write_bytes(body)
    return prefix


def test_open_archive_caches_index(tmp_path):
    clear_archive_cache()
    try:
        prefix = _write_triplet(tmp_path, b"first-bytes-here")
        first = open_archive(prefix)
        assert open_archive(prefix) is first
        assert first.find("file.dat").unpacked_length == 16
        assert first.extract(first.find("file.dat")) == b"first-bytes-here"
        try:
            first.find("missing.dat")
        except KeyError:
            pass
        else:
            raise AssertionError("find accepted a missing entry")
    finally:
        clear_archive_cache()


def test_open_archive_notices_rebuild(tmp_path):
    clear_archive_cache()
    try:
        prefix = _write_triplet(tmp_path, b"v1")
        before = open_archive(prefix)
        prefix.with_suffix(".fs").write_bytes(b"v2-longer")
        prefix.with_suffix(".fi").write_bytes(struct.pack("<III", 9, 0, 0))
        stamp = prefix.with_suffix(".fi").stat().st_mtime_ns + 10_000_000
        os.utime(prefix.with_suffix(".fi"), ns=(stamp, stamp))
        after = open_archive(prefix)
        assert after is not before
        assert after.extract(after.find("file.dat")) == b"v2-longer"
        assert isinstance(after, FsArchive)
    finally:
        clear_archive_cache()
