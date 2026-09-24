from __future__ import annotations

import struct
import unittest

from plugins.rdr import rbf


def record(index: int, kind: int, name: str | None = None, payload: bytes = b"") -> bytes:
    out = bytearray([index, kind])
    if name is not None:
        raw = name.encode("ascii")
        out += struct.pack("<h", len(raw)) + raw
    out += payload
    return bytes(out)


def fixture() -> bytes:
    data = bytearray(rbf.MAGIC)
    data += record(0, rbf.TYPE_STRUCTURE, "Root", struct.pack("<hhh", 0, 0, 1))
    data += record(1, rbf.TYPE_UINT32, "Count", struct.pack("<I", 7))
    data += record(2, rbf.TYPE_FLOAT, "Speed", struct.pack("<f", 1.25))
    data += record(3, rbf.TYPE_BOOL_FALSE, "Enabled")
    data += record(4, rbf.TYPE_STRING, "Label", struct.pack("<h", 4) + b"Test")
    data += record(5, rbf.TYPE_FLOAT3, "Position", struct.pack("<fff", 1, 2, 3))
    data += record(6, rbf.TYPE_STRUCTURE, "Child", struct.pack("<hhh", 0, 0, 0))
    data += record(7, rbf.TYPE_FLOAT, "Ratio", struct.pack("<f", 0.5))
    data += record(2, rbf.TYPE_FLOAT, payload=struct.pack("<f", 2.5))
    data += b"\xff\xff"
    data += b"\xfd\xff" + struct.pack("<i", 3) + b"XYZ"
    data += b"\xff\xff"
    return bytes(data)


class RbfTests(unittest.TestCase):
    def test_parse_safe_scalars_and_skip_variable_content(self):
        payload = rbf.parse(fixture())
        rows = payload["scalars"]
        self.assertEqual([row["path"] for row in rows], [
            "Root/@Count", "Root/Speed", "Root/Enabled",
            "Root/Child/Ratio", "Root/Child/Speed",
        ])
        self.assertEqual([row["kind"] for row in rows], [
            "uint32", "float", "bool", "float", "float",
        ])
        self.assertEqual(payload["skipped"], {"strings": 1, "float3": 1, "byteBlocks": 1})
        self.assertEqual(payload["trailingBytes"], 0)

    def test_noop_is_byte_identical(self):
        source = fixture()
        row = rbf.parse(source)["scalars"][1]
        candidate, changed = rbf.apply_scalar_edits(source, [{
            "recordOffset": row["recordOffset"], "path": row["path"],
            "kind": row["kind"], "rawHex": row["rawHex"], "value": row["value"],
        }])
        self.assertEqual(changed, 0)
        self.assertEqual(candidate, source)

    def test_fixed_width_edits_preserve_every_other_byte(self):
        source = fixture()
        rows = rbf.parse(source)["scalars"]
        wanted = {row["path"]: row for row in rows}
        edits = []
        for path, value in (("Root/@Count", 42), ("Root/Speed", 3.5), ("Root/Enabled", True)):
            row = wanted[path]
            edits.append({
                "recordOffset": row["recordOffset"], "path": row["path"],
                "kind": row["kind"], "rawHex": row["rawHex"], "value": value,
            })
        candidate, changed = rbf.apply_scalar_edits(source, edits)
        self.assertEqual(changed, 3)
        reparsed = {row["path"]: row["value"] for row in rbf.parse(candidate)["scalars"]}
        self.assertEqual(reparsed["Root/@Count"], 42)
        self.assertAlmostEqual(reparsed["Root/Speed"], 3.5)
        self.assertIs(reparsed["Root/Enabled"], True)
        self.assertIn(b"Test", candidate)
        self.assertIn(b"XYZ", candidate)
        self.assertEqual(len(candidate), len(source))

    def test_stale_identity_refuses_write(self):
        source = fixture()
        row = rbf.parse(source)["scalars"][0]
        with self.assertRaisesRegex(ValueError, "changed since"):
            rbf.apply_scalar_edits(source, [{
                "recordOffset": row["recordOffset"], "path": row["path"],
                "kind": row["kind"], "rawHex": "00000000", "value": 9,
            }])

    def test_structure_must_consume_advertised_attributes(self):
        malformed = (
            rbf.MAGIC
            + record(0, rbf.TYPE_STRUCTURE, "Root", struct.pack("<hhh", 0, 0, 1))
            + b"\xff\xff"
        )
        with self.assertRaisesRegex(ValueError, "advertised attributes"):
            rbf.parse(malformed)

    def test_strings_vectors_and_unknown_types_are_not_promoted(self):
        source = fixture()
        paths = {row["path"] for row in rbf.parse(source)["scalars"]}
        self.assertNotIn("Root/Label", paths)
        self.assertNotIn("Root/Position", paths)
        bad = bytearray(source)
        first = rbf.parse(source)["scalars"][0]
        bad[first["typeOffset"]] = 0x70
        with self.assertRaisesRegex(ValueError, "Unsupported RBF0 data type"):
            rbf.parse(bad)


if __name__ == "__main__":
    unittest.main()
