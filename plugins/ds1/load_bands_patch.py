"""Exact-build variable-band native projection with a bounded read-only table.

The original final executable section is extended by 8 KiB. The certificate
overlay is moved intact and its file pointer updated; modification invalidates
the signature as it already does for the other native tweaks. The two added
routines are x64 leaf functions. Existing nonleaf stack frames remain intact.
"""
from __future__ import annotations

import json
import struct

from . import load_bands

EXTENSION_SIZE = 0x2000
BLOCK_OFFSET = 0x2FF2800
BLOCK_RVA = 0x319B000
CLASS_RVA, CLASS_OFFSET = 0x2E1A10, 0x2E0E10
FACTOR_RVA, FACTOR_OFFSET = 0x356FEA, 0x3563EA
FRACTION_RVA, FRACTION_OFFSET = 0x2E1A7B, 0x2E0E7B
BASELINE_OFFSET = 0x1A2A240
CLASSIFIER_OFFSET, RECOVERY_OFFSET = 0x40, 0xC0
TABLE_OFFSET, JSON_OFFSET = 0x400, 0x1000
MAGIC = b"LEXDS1BANDS\x02".ljust(16, b"\0")
# Original replacement instructions from load_bands.S/.ld. No game code copied.
CLASSIFIER = bytes.fromhex("4584c9753df30f5ec14c8d15b00300008b0dc2ffffff410f2f02760c4983c220ffc975f24983ea20418b420483f80175104584c0740b833d9fffffff00740231c0c3b804000000c3")
RECOVERY = bytes.fromhex("4584c97547f30f5ec14c8d15300300008b0d42ffffff410f2f02760c4983c220ffc975f24983ea20f3410f10420841837a040175164584c07411833d1bffffff007408f30f100515ffffffc3f30f100510ffffffc3")
FACTOR = bytes.fromhex("4889f1e84eb300000f28c80f28c7440fb6c7440fb6cbe8bb40e4020f28f09090909090909090909090")
FRACTION = bytes.fromhex("f30f1035a595eb020f57edf30f5ed9488d0d6f99eb028b058195eb020f2f19760c4883c120ffc875f34883e9200f28d5f30f1061100f2fe574140f28d3f30f5c510cf30f5ed4f30f5fd5f30f5dd6f30f11542420488d4424209090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090909090")


def block(rules) -> bytes:
    rules = load_bands.validate_native(rules)
    encoded = json.dumps(rules, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(encoded) > EXTENSION_SIZE - JSON_OFFSET:
        raise ValueError("Native band settings exceed the bounded storage area")
    result = bytearray(EXTENSION_SIZE)
    result[:16] = MAGIC
    # 16: schema; 20: JSON length; 24: count; 28: special enabled;
    # 32: special recovery; 36: forced recovery; 40: one.
    struct.pack_into("<4I3f", result, 16, 2, len(encoded), len(rules["bands"]),
                     int(rules["specialLight"]["enabled"]),
                     rules["specialLight"]["recovery"] / 100, rules["forcedRecovery"] / 100, 1.0)
    result[CLASSIFIER_OFFSET:CLASSIFIER_OFFSET + len(CLASSIFIER)] = CLASSIFIER
    result[RECOVERY_OFFSET:RECOVERY_OFFSET + len(RECOVERY)] = RECOVERY
    for index, row in enumerate(load_bands.runtime_rows(rules["bands"])):
        struct.pack_into("<fI3f", result, TABLE_OFFSET + 32 * index, *row)
    result[JSON_OFFSET:JSON_OFFSET + len(encoded)] = encoded
    return bytes(result)


def read_rules(source: bytes) -> dict:
    if source[BLOCK_OFFSET:BLOCK_OFFSET + 16] != MAGIC:
        raise ValueError("Unknown native band projection")
    version, length = struct.unpack_from("<II", source, BLOCK_OFFSET + 16)
    if version != 2 or not 1 <= length <= EXTENSION_SIZE - JSON_OFFSET:
        raise ValueError("Invalid native band settings length or version")
    try:
        value = json.loads(source[BLOCK_OFFSET + JSON_OFFSET:BLOCK_OFFSET + JSON_OFFSET + length])
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid native band settings") from error
    return load_bands.validate_native(value)


def transform_verified(original: bytes, rules: dict) -> bytes:
    """Caller must first verify the complete original with stamina_patch._pristine."""
    payload = block(rules)
    # Guard the precise PE mapping even under synthetic tests with a substituted hash.
    pe = struct.unpack_from("<I", original, 0x3C)[0]
    optional = pe + 24
    sections = struct.unpack_from("<H", original, pe + 6)[0]
    optional_size = struct.unpack_from("<H", original, pe + 20)[0]
    last = optional + optional_size + (sections - 1) * 40
    virtual_size, rva, raw_size, raw_start = struct.unpack_from("<4I", original, last + 8)
    cert_pointer, cert_size = struct.unpack_from("<II", original, optional + 144)
    if (original[:2] != b"MZ" or original[pe:pe + 4] != b"PE\0\0"
            or struct.unpack_from("<H", original, optional)[0] != 0x20B
            or sections != 9 or raw_start + raw_size != BLOCK_OFFSET
            or rva + virtual_size != BLOCK_RVA or virtual_size != raw_size
            or struct.unpack_from("<I", original, last + 36)[0] != 0x60000020
            or cert_pointer != BLOCK_OFFSET or cert_pointer + cert_size != len(original)
            or struct.unpack_from("<I", original, optional + 56)[0] != BLOCK_RVA):
        raise ValueError("Unsupported native band PE mapping")
    result = bytearray(original[:BLOCK_OFFSET] + payload + original[BLOCK_OFFSET:])
    struct.pack_into("<I", result, last + 8, virtual_size + EXTENSION_SIZE)
    struct.pack_into("<I", result, last + 16, raw_size + EXTENSION_SIZE)
    struct.pack_into("<I", result, optional + 56, BLOCK_RVA + EXTENSION_SIZE)
    size_of_code = struct.unpack_from("<I", original, optional + 4)[0]
    struct.pack_into("<I", result, optional + 4, size_of_code + EXTENSION_SIZE)
    struct.pack_into("<I", result, optional + 144, cert_pointer + EXTENSION_SIZE)
    result[CLASS_OFFSET:CLASS_OFFSET + 5] = b"\xE9" + struct.pack(
        "<i", BLOCK_RVA + CLASSIFIER_OFFSET - (CLASS_RVA + 5))
    result[FACTOR_OFFSET:FACTOR_OFFSET + len(FACTOR)] = FACTOR
    result[FRACTION_OFFSET:FRACTION_OFFSET + len(FRACTION)] = FRACTION
    struct.pack_into("<f", result, BASELINE_OFFSET, rules["baseRecovery"])
    return bytes(result)
