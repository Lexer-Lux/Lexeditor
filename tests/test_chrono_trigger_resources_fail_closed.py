from __future__ import annotations

import gzip
import random
import unittest

from games.chrono_trigger.resources import ResourceArchive, ResourceArchiveError


class ResourceArchiveFailClosedTests(unittest.TestCase):
    def test_decode_is_symmetric_across_offsets_and_lengths(self):
        rng = random.Random(0xA2C1)
        for offset in (0, 1, 15, 16, 31, 0x1234, 0x100000):
            for length in (0, 1, 2, 7, 16, 31, 64, 257):
                raw = bytes(rng.getrandbits(8) for _ in range(length))
                encoded = ResourceArchive.decode(raw, offset)
                self.assertEqual(ResourceArchive.decode(encoded, offset), raw)

    def test_inflate_accepts_valid_blocks_and_rejects_size_mismatch(self):
        for payload in (b"a", b"hello", bytes(range(256)), b"chrono" * 1024):
            block = len(payload).to_bytes(4, "big") + gzip.compress(payload)
            self.assertEqual(ResourceArchive._inflate_block(block, "fixture"), payload)

            wrong = (len(payload) + 1).to_bytes(4, "big") + gzip.compress(payload)
            with self.assertRaisesRegex(ResourceArchiveError, "size mismatch"):
                ResourceArchive._inflate_block(wrong, "fixture")

    def test_corrupt_deflate_is_normalized_to_resource_archive_error(self):
        # This has a gzip signature but an invalid DEFLATE payload. CPython's
        # gzip module can raise zlib.error here rather than OSError/EOFError;
        # callers must still see the archive parser's single fail-closed type.
        block = b"\x00\x00\x00\x01" + b"\x1f\x8b\x08\x00" + (b"\x00" * 20)
        with self.assertRaisesRegex(ResourceArchiveError, "gzip payload is invalid"):
            ResourceArchive._inflate_block(block, "corrupt")

    def test_short_and_random_malformed_blocks_never_leak_decoder_errors(self):
        for size in range(4):
            with self.assertRaises(ResourceArchiveError):
                ResourceArchive._inflate_block(b"\x00" * size, "short")

        rng = random.Random(0xB10C)
        for _ in range(512):
            length = rng.randrange(4, 80)
            block = bytes(rng.getrandbits(8) for _ in range(length))
            try:
                payload = ResourceArchive._inflate_block(block, "random")
            except ResourceArchiveError:
                continue
            expected = int.from_bytes(block[:4], "big")
            self.assertEqual(len(payload), expected)


if __name__ == "__main__":
    unittest.main()
