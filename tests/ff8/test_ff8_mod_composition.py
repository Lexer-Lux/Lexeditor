"""Overlapping FF8 mods compose per record instead of replacing wholesale.

Two mods editing different lines of one field's dialogue, different
entrances, different starting fields, or different script methods keep both
sides' changes. Formats without a proved merger fail closed: the winner is
named and the dropped changes are spelled out in the conflict warning.
"""
import struct
import tempfile
import unittest
from pathlib import Path

from plugins.ff8 import (field_data, field_dialogue, field_scripts, init_data,
                         kernel_text, runtime_layout)


def _msd(*lines: str) -> bytes:
    payloads = [kernel_text.encode(line) + b"\0" for line in lines]
    cursor = len(lines) * 4
    offsets = []
    for payload in payloads:
        offsets.append(cursor)
        cursor += len(payload)
    return struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(payloads)


def _jsm(*methods: list[int]) -> bytes:
    flat = [word for method in methods for word in method]
    positions = [0]
    for method in methods:
        positions.append(positions[-1] + len(method))
    positions_offset = 10
    data_offset = positions_offset + len(positions) * 2
    data_offset += (-data_offset) % 4
    header = struct.pack("<BBBBHH", 0, 1, 0, 0, positions_offset, data_offset)
    groups = struct.pack("<H", len(methods) - 1)
    table = struct.pack(f"<{len(positions)}H", *positions)
    pad = b"\0" * (data_offset - positions_offset - len(table))
    return header + groups + table + pad + struct.pack(f"<{len(flat)}I", *flat)


def _word(name: str, argument: int) -> int:
    return (field_scripts.OPCODE_IDS[name] << 24) | (argument & 0xFFFFFF)


METHOD_A = [_word("LBL", 0), _word("RET", 8)]
METHOD_B = [_word("LBL", 1), _word("RET", 8)]


class DialogueMergeTests(unittest.TestCase):
    def test_different_lines_compose(self):
        vanilla = _msd("AAA", "BBB", "CCC")
        mod_a, _ = field_dialogue.apply_edits(vanilla, [{"id": 0, "text": "A0"}])
        mod_b, _ = field_dialogue.apply_edits(vanilla, [{"id": 1, "text": "B1"}])
        merged, conflicts, reason = field_dialogue.merge(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.msd")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [])
        texts = [line["text"] for line in field_dialogue.read(merged)["lines"]]
        self.assertEqual(texts, ["A0", "B1", "CCC"])

    def test_same_line_conflict_names_the_winner(self):
        vanilla = _msd("AAA", "BBB")
        mod_a, _ = field_dialogue.apply_edits(vanilla, [{"id": 0, "text": "A0"}])
        mod_b, _ = field_dialogue.apply_edits(vanilla, [{"id": 0, "text": "B0"}])
        merged, conflicts, reason = field_dialogue.merge(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.msd")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [{
            "unit": "direct/x/y/y.msd:line:0",
            "winner": "mod-b", "claimants": ["mod-a", "mod-b"]}])
        texts = [line["text"] for line in field_dialogue.read(merged)["lines"]]
        self.assertEqual(texts, ["B0", "BBB"])

    def test_line_count_change_falls_back_with_a_reason(self):
        vanilla = _msd("AAA", "BBB")
        merged, _, reason = field_dialogue.merge(
            vanilla, [("mod-a", _msd("AAA"))], "direct/x/y/y.msd")
        self.assertIsNone(merged)
        self.assertIn("line count", reason)


class EntranceMergeTests(unittest.TestCase):
    def test_gateway_and_trigger_compose(self):
        vanilla = bytes(504)
        mod_a = field_data._edit_inf_bytes(vanilla, [
            {"kind": "gateway", "slot": 0, "field": "fieldId", "value": 5}])
        mod_b = field_data._edit_inf_bytes(vanilla, [
            {"kind": "trigger", "slot": 0, "field": "doorId", "value": 7}])
        merged, conflicts, reason = field_data.merge_inf(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.inf")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [])
        parsed = field_data._parse_inf(merged)
        self.assertEqual(parsed["gateways"][0]["fieldId"], 5)
        self.assertEqual(parsed["triggers"][0]["doorId"], 7)

    def test_same_scalar_conflict_names_the_winner(self):
        vanilla = bytes(504)
        mod_a = field_data._edit_inf_bytes(vanilla, [
            {"kind": "gateway", "slot": 0, "field": "fieldId", "value": 5}])
        mod_b = field_data._edit_inf_bytes(vanilla, [
            {"kind": "gateway", "slot": 0, "field": "fieldId", "value": 6}])
        merged, conflicts, reason = field_data.merge_inf(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.inf")
        self.assertEqual(reason, "")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["winner"], "mod-b")
        self.assertEqual(field_data._parse_inf(merged)["gateways"][0]["fieldId"], 6)

    def test_unmapped_byte_change_falls_back_with_a_reason(self):
        vanilla = bytes(504)
        # Variant 3 gateways are 24 bytes; bytes 20-23 of each hold no unit.
        mod_a = bytearray(vanilla)
        mod_a[24 + 20] = 1
        merged, _, reason = field_data.merge_inf(
            vanilla, [("mod-a", bytes(mod_a))], "direct/x/y/y.inf")
        self.assertIsNone(merged)
        self.assertIn("outside proved entrance units", reason)


class StartingDataMergeTests(unittest.TestCase):
    def test_units_cover_disjoint_slices_of_the_layout(self):
        spans = []
        for identity, (offset, size) in init_data._merge_units().items():
            self.assertGreaterEqual(offset, 0)
            self.assertLessEqual(offset + size, init_data.FULL_SIZE)
            spans.append((offset, offset + size, identity))
        spans.sort()
        for (_, end, _), (start, _, identity) in zip(spans, spans[1:]):
            self.assertLessEqual(end, start, f"overlapping unit at {identity}")

    def test_different_fields_compose(self):
        vanilla = bytes(init_data.FULL_SIZE)
        mod_a = bytearray(vanilla)
        mod_a[init_data.MISC_OFFSET + 24:init_data.MISC_OFFSET + 28] = (12345).to_bytes(4, "little")
        mod_b = bytearray(vanilla)
        mod_b[init_data.MISC_OFFSET] = 3
        merged, conflicts, reason = init_data.merge(
            vanilla, [("mod-a", bytes(mod_a)), ("mod-b", bytes(mod_b))],
            "direct/init.out")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [])
        self.assertEqual(int.from_bytes(
            merged[init_data.MISC_OFFSET + 24:init_data.MISC_OFFSET + 28], "little"), 12345)
        self.assertEqual(merged[init_data.MISC_OFFSET], 3)

    def test_short_vanilla_pads_like_the_editor_save(self):
        vanilla = bytes(2812)
        mod_a = bytearray(init_data.FULL_SIZE)
        mod_a[init_data.MISC_OFFSET + 24:init_data.MISC_OFFSET + 28] = (999).to_bytes(4, "little")
        merged, _, reason = init_data.merge(
            vanilla, [("mod-a", bytes(mod_a))], "direct/init.out")
        self.assertEqual(reason, "")
        self.assertEqual(len(merged), init_data.FULL_SIZE)

    def test_unmapped_byte_change_falls_back_with_a_reason(self):
        vanilla = bytes(init_data.FULL_SIZE)
        mod_a = bytearray(vanilla)
        mod_a[5] = 1  # GF 0 bytes 0-11 hold no proved unit.
        merged, _, reason = init_data.merge(
            vanilla, [("mod-a", bytes(mod_a))], "direct/init.out")
        self.assertIsNone(merged)
        self.assertIn("outside proved starting-data units", reason)


class ScriptMergeTests(unittest.TestCase):
    def test_different_methods_compose(self):
        vanilla = _jsm(METHOD_A, METHOD_B)
        self.assertTrue(all(method["editable"]
                            for method in field_scripts.read(vanilla)["methods"]))
        mod_a, _ = field_scripts.rebuild(vanilla, b"", [
            {"id": 0, "source": "LBL 0\nRET 9"}])
        mod_b, _ = field_scripts.rebuild(vanilla, b"", [
            {"id": 1, "source": "LBL 1\nRET 9"}])
        merged, conflicts, reason = field_scripts.merge(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.jsm")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [])
        methods = field_scripts.read(merged)["methods"]
        self.assertEqual(methods[0]["source"], "LBL 0\nRET 9")
        self.assertEqual(methods[1]["source"], "LBL 1\nRET 9")

    def test_same_method_conflict_names_the_winner(self):
        vanilla = _jsm(METHOD_A, METHOD_B)
        mod_a, _ = field_scripts.rebuild(vanilla, b"", [
            {"id": 0, "source": "LBL 0\nRET 9"}])
        mod_b, _ = field_scripts.rebuild(vanilla, b"", [
            {"id": 0, "source": "LBL 0\nRET 10"}])
        merged, conflicts, reason = field_scripts.merge(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.jsm")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [{
            "unit": "direct/x/y/y.jsm:method:0",
            "winner": "mod-b", "claimants": ["mod-a", "mod-b"]}])
        self.assertEqual(field_scripts.read(merged)["methods"][0]["source"],
                         "LBL 0\nRET 10")

    def test_method_table_change_falls_back_with_a_reason(self):
        vanilla = _jsm(METHOD_A, METHOD_B)
        merged, _, reason = field_scripts.merge(
            vanilla, [("mod-a", _jsm(METHOD_A))], "direct/x/y/y.jsm")
        self.assertIsNone(merged)
        self.assertIn("method table", reason)


class ComposeOverlapTests(unittest.TestCase):
    def test_two_mod_overlap_composes_and_warns_where_it_cannot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline"
            field_dir = baseline / "field" / "mapdata" / "g" / "n"
            field_dir.mkdir(parents=True)
            (field_dir / "n.msd").write_bytes(_msd("AAA", "BBB"))
            (field_dir / "n.inf").write_bytes(bytes(504))
            (field_dir / "n.jsm").write_bytes(_jsm(METHOD_A, METHOD_B))
            (baseline / "main").mkdir()
            (baseline / "main" / "init.out").write_bytes(bytes(init_data.FULL_SIZE))
            mod_a, mod_b = root / "mod-a", root / "mod-b"
            field_rel = Path("direct/field/mapdata/g/n")
            for mod in (mod_a, mod_b):
                (mod / field_rel).mkdir(parents=True)
            msd_base = (field_dir / "n.msd").read_bytes()
            msd_a, _ = field_dialogue.apply_edits(msd_base, [{"id": 0, "text": "A0"}])
            msd_b, _ = field_dialogue.apply_edits(msd_base, [{"id": 1, "text": "B1"}])
            (mod_a / field_rel / "n.msd").write_bytes(msd_a)
            (mod_b / field_rel / "n.msd").write_bytes(msd_b)
            inf_base = bytes(504)
            (mod_a / field_rel / "n.inf").write_bytes(field_data._edit_inf_bytes(
                inf_base, [{"kind": "gateway", "slot": 0, "field": "fieldId",
                            "value": 5}]))
            (mod_b / field_rel / "n.inf").write_bytes(field_data._edit_inf_bytes(
                inf_base, [{"kind": "trigger", "slot": 0, "field": "doorId",
                            "value": 7}]))
            jsm_base = (field_dir / "n.jsm").read_bytes()
            jsm_a, _ = field_scripts.rebuild(jsm_base, b"", [
                {"id": 0, "source": "LBL 0\nRET 9"}])
            jsm_b, _ = field_scripts.rebuild(jsm_base, b"", [
                {"id": 1, "source": "LBL 1\nRET 9"}])
            (mod_a / field_rel / "n.jsm").write_bytes(jsm_a)
            (mod_b / field_rel / "n.jsm").write_bytes(jsm_b)
            init_base = bytes(init_data.FULL_SIZE)
            init_first = bytearray(init_base)
            init_first[init_data.MISC_OFFSET + 24:init_data.MISC_OFFSET + 28] = (
                12345).to_bytes(4, "little")
            init_second = bytearray(init_base)
            init_second[init_data.MISC_OFFSET] = 3
            (mod_a / "direct").mkdir(exist_ok=True)
            (mod_b / "direct").mkdir(exist_ok=True)
            (mod_a / "direct" / "init.out").write_bytes(bytes(init_first))
            (mod_b / "direct" / "init.out").write_bytes(bytes(init_second))
            # No merger understands enemy DAT or textures. DAT warns; media stays quiet.
            (mod_a / "direct" / "battle").mkdir()
            (mod_b / "direct" / "battle").mkdir()
            (mod_a / "direct" / "battle" / "c0m000.dat").write_bytes(b"A" * 64)
            (mod_b / "direct" / "battle" / "c0m000.dat").write_bytes(b"B" * 64)
            (mod_a / "textures").mkdir()
            (mod_b / "textures").mkdir()
            (mod_a / "textures" / "x.png").write_bytes(b"A" * 16)
            (mod_b / "textures" / "x.png").write_bytes(b"B" * 16)
            rows = [
                {"id": "mod-a", "path": str(mod_a), "enabled": True, "order": 0,
                 "name": "mod-a", "folderOptions": {}},
                {"id": "mod-b", "path": str(mod_b), "enabled": True, "order": 1,
                 "name": "mod-b", "folderOptions": {}},
            ]
            result = runtime_layout.compose(
                root / "project", root / "runtime", rows, baseline, None,
                runtime_layout.prelaunch_condition_state())
            runtime = root / "runtime"
            texts = [line["text"] for line in field_dialogue.read(
                (runtime / field_rel / "n.msd").read_bytes())["lines"]]
            self.assertEqual(texts, ["A0", "B1"])
            entrances = field_data._parse_inf(
                (runtime / field_rel / "n.inf").read_bytes())
            self.assertEqual(entrances["gateways"][0]["fieldId"], 5)
            self.assertEqual(entrances["triggers"][0]["doorId"], 7)
            methods = field_scripts.read(
                (runtime / field_rel / "n.jsm").read_bytes())["methods"]
            self.assertEqual(methods[0]["source"], "LBL 0\nRET 9")
            self.assertEqual(methods[1]["source"], "LBL 1\nRET 9")
            starting = (runtime / "direct" / "init.out").read_bytes()
            self.assertEqual(int.from_bytes(
                starting[init_data.MISC_OFFSET + 24:init_data.MISC_OFFSET + 28],
                "little"), 12345)
            self.assertEqual(starting[init_data.MISC_OFFSET], 3)
            by_path = {conflict["path"]: conflict for conflict in result["conflicts"]}
            for key in ("direct/field/mapdata/g/n/n.msd",
                        "direct/field/mapdata/g/n/n.inf",
                        "direct/field/mapdata/g/n/n.jsm",
                        "direct/init.out"):
                self.assertEqual(by_path[key]["mode"], "semantic merge", key)
            dat = by_path["direct/battle/c0m000.dat"]
            self.assertEqual(dat["mode"], "opaque winner")
            self.assertEqual(dat["winner"], "mod-b")
            self.assertIn("mod-a's changes to this file are dropped", dat["warning"])
            self.assertEqual(
                (runtime / "direct" / "battle" / "c0m000.dat").read_bytes(), b"B" * 64)
            texture = by_path["textures/x.png"]
            self.assertEqual(texture["mode"], "opaque winner")
            self.assertNotIn("warning", texture)


if __name__ == "__main__":
    unittest.main()
