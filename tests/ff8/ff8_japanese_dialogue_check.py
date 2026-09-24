"""Check Japanese field text and lossless MSD editing without game writes."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8 import field_dialogue, japanese_text, kernel_text

# Original bccent12 strings: jump to coast; do squats.
payloads = [bytes.fromhex("6b8d2bb96736beb84d"),
            bytes.fromhex("786eb6bc86779d795e")]
raw = struct.pack("<II", 8, 8 + len(payloads[0]) + 1)
raw += b"\0".join(payloads) + b"\0"
lines = field_dialogue.read(raw, map_name="bccent12")["lines"]
assert [line["text"] for line in lines] == ["かいがんへジャンプ", "スクワットします。"]
assert field_dialogue.apply_edits(raw, [
    {"id": line["id"], "text": line["text"]} for line in lines
], map_name="bccent12") == (raw, 0)
changed, count = field_dialogue.apply_edits(raw, [
    {"id": 0, "text": "スクワットします。"}
], map_name="bccent12")
assert count == 1
assert field_dialogue.read(changed, map_name="bccent12")["lines"][0]["text"] == lines[1]["text"]
assert field_dialogue.read(changed, map_name="bccent12")["lines"][1]["rawText"] == payloads[1].hex()
assert field_dialogue.read(raw, map_name="other")["lines"][0]["text"] == kernel_text.decode(payloads[0])
for page in (0x19, 0x1A, 0x1B):
    value = japanese_text.decode(bytes((page, 0x20)))
    assert japanese_text.decode(japanese_text.encode(value)) == value
for value in (b"\x19", b"\x19\x01", b"\x06\x20", b"\x03\x30"):
    assert japanese_text.encode(japanese_text.decode(value)) == value
try:
    japanese_text.encode("🙂")
except ValueError:
    pass
else:
    raise AssertionError("Unsupported glyph accepted")
print("PASS: Japanese field decoding, pages, tokens, edits, and unchanged bytes")
