"""Regression coverage for FF8 kernel text overrides (encode/decode/rows/edits)."""
import unittest

from plugins.ff8 import kernel_text as kt


def fixture():
    """25 one-string text sections (32..56) with linked one-record data sections."""
    sections = {}
    payloads = {}
    for text_id in range(kt.TEXT_SECTION_FIRST, kt.TEXT_SECTION_LAST + 1):
        data_id = text_id - 31
        sections[data_id] = {"id": data_id, "number_sub_section": 1,
                             "sub_section_size": 2,
                             "sub_section_nb_text_offset": 1}
        payloads[data_id] = b"\x00\x00"
        sections[text_id] = {"id": text_id,
                             "section_name": f"Test {text_id} section",
                             "type": "text",
                             "section_id_data_linked": data_id}
        payloads[text_id] = kt.encode("Hi") + b"\x00\x00"
    for section_id in range(26, 32):
        sections[section_id] = {"id": section_id}
        payloads[section_id] = b""
    ordered = [payloads[i] for i in range(1, 57)]
    header_size = 57 * 4
    cursor = header_size
    starts = []
    for payload in ordered:
        starts.append(cursor)
        cursor += len(payload)
    data = (len(ordered).to_bytes(4, "little")
            + b"".join(start.to_bytes(4, "little") for start in starts)
            + b"".join(ordered))
    return data, sections


class KernelTextTests(unittest.TestCase):
    def test_round_trip(self):
        for text in ("Fire", "Cure\nCura", "Lionheart 777"):
            self.assertEqual(kt.decode(kt.encode(text)), text)

    def test_newline_and_raw_tokens(self):
        self.assertEqual(kt.decode(bytes((0x02,))), "\n")
        self.assertEqual(kt.encode("{x41}"), b"\x41")

    def test_apostrophe_normalizes_to_font_quote(self):
        # Both quote marks share one glyph byte; decode prefers U+2018.
        self.assertEqual(kt.decode(kt.encode("Squall's")), "Squall\u2018s")

    def test_rejections(self):
        for bad in ("a{b", "a{Nope}", "a`b", "{x00}"):
            with self.assertRaises(ValueError):
                kt.encode(bad)

    def test_rows_cover_every_text_section(self):
        data, sections = fixture()
        result = kt.rows(data, sections)
        self.assertEqual(len(result["rows"]), 25)
        self.assertEqual({row["sectionId"] for row in result["rows"]},
                         set(range(kt.TEXT_SECTION_FIRST, kt.TEXT_SECTION_LAST + 1)))
        self.assertTrue(all(row["value"] == "Hi" for row in result["rows"]))

    def test_edit_changes_one_string_only(self):
        data, sections = fixture()
        updated, changed = kt.apply_edits(data, sections, [
            {"sectionId": 32, "recordId": 0, "slot": 0, "value": "Yo"}])
        self.assertEqual(changed, 1)
        values = [row["value"] for row in kt.rows(updated, sections)["rows"]]
        self.assertEqual(values[0], "Yo")
        self.assertTrue(all(value == "Hi" for value in values[1:]))

    def test_edit_validation(self):
        data, sections = fixture()
        edit = {"sectionId": 32, "recordId": 0, "slot": 0, "value": "Yo"}
        with self.assertRaises(ValueError):
            kt.apply_edits(data, sections, [edit, dict(edit)])
        with self.assertRaises(ValueError):
            kt.apply_edits(data, sections, [dict(edit, sectionId=7)])
        with self.assertRaises(ValueError):
            kt.apply_edits(data, sections, [dict(edit, recordId=9)])
