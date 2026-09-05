"""Card record preservation, validation and supported executable integration."""
import argparse
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8 import cards


class CardTests(unittest.TestCase):
    def setUp(self):
        self.table = bytes([1, 2, 3, 4, 0, 21, 0xA5, 0x5A]) * cards.COUNT

    def test_preserves_every_other_byte(self):
        result, count = cards.apply_edits(self.table, [{"id": 109, "field": "top", "value": 10}])
        expected = bytearray(self.table)
        expected[109 * 8] = 10
        self.assertEqual(result, expected)
        self.assertEqual(count, 1)

    def test_invalid_values_and_ids(self):
        for field, value in [("top", 11), ("bottom", -1), ("power", 256),
                             ("element", 3), ("left", 1.5), ("right", True),
                             ("padding", 0), ("name", "Custom")]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                cards.apply_edits(self.table, [{"id": 0, "field": field, "value": value}])
        for i in (-1, 110, True):
            with self.assertRaises(ValueError):
                cards.apply_edits(self.table, [{"id": i, "field": "top", "value": 2}])

    def test_zero_ten_and_byte_bounds(self):
        for value in (0, 10):
            cards.apply_edits(self.table, [{"id": 0, "field": "top", "value": value}])
        for value in cards.ELEMENTS:
            cards.apply_edits(self.table, [{"id": 0, "field": "element", "value": value}])

    def test_duplicate_and_incomplete_rejected(self):
        edit = {"id": 0, "field": "top", "value": 2}
        with self.assertRaises(ValueError):
            cards.apply_edits(self.table, [edit, edit])
        with self.assertRaises(ValueError):
            cards.apply_edits(self.table[:-1], [])

    def test_unknown_executable_rejected(self):
        with self.assertRaises(ValueError):
            cards.build_hext(b"not the supported executable", [])


def integration(path):
    exe = path.read_bytes()
    original = cards.read_tables(exe)[0]
    rows = cards.load(path)
    assert len(rows) == 110 and rows[0]["name"] == "Geezard"
    assert cards.build_hext(exe, []) == ""
    edit = {"id": 109, "field": "top", "value": (rows[109]["top"] + 1) % 11}
    hext = cards.build_hext(exe, [edit])
    writes = [line.split(" = ") for line in hext.splitlines() if " = " in line]
    assert len(writes) == 2
    for table_offset, (address, value) in zip(cards.TABLE_OFFSETS, writes):
        va = cards._virtual_address(exe, table_offset, len(original))
        assert int(address, 16) == va + 109 * 8
        record = bytes.fromhex(value)
        assert record == bytes([edit["value"]])
    assert path.read_bytes() == exe
    with tempfile.TemporaryDirectory(prefix="lexeditor-cards-91-") as temporary:
        from games.ff8 import runtime_layout, gameplay_settings
        root = Path(temporary)
        project = root / "project"
        cards.save_project(project, exe, [edit])
        assert cards.project_edits(project, exe) == [edit]
        second = {"id": 0, "field": "power", "value": (rows[0]["power"] + 1) % 256}
        cards.save_project(project, exe, [second])
        merged = cards.project_edits(project, exe)
        assert merged == [second, edit]
        expected = cards.build_hext(exe, merged)
        runtime_layout.compose(project, root / "runtime")
        emitted = list((root / "runtime" / "hext").rglob("*lexeditor-cards.txt"))
        assert len(emitted) == 1 and emitted[0].read_text() == expected
        loader_directory = root / "runtime" / "hext" / gameplay_settings.FFNX_HEXT_SUFFIX
        assert emitted[0].parent == loader_directory, "FFNx does not scan this card patch directory"
        assert cards.HEXT.parent == Path("hext") / "ff8" / "en_nv"
        (project / cards.HEXT).write_text("# external edit\n")
        try:
            cards.save_project(project, exe, [])
        except ValueError:
            pass
        else:
            raise AssertionError("External patch conflict was overwritten")
        (project / cards.HEXT).write_text(expected)
        cards.save_project(project, exe, [{**edit, "value": rows[109]["top"]},
                                          {**second, "value": rows[0]["power"]}])
        assert cards.project_edits(project, exe) == []
        assert (project / cards.HEXT).read_text() == ""
    print("PASS: 110 names, two PE-resolved table writes, untouched executable and record bytes")
    print("PASS: temporary project save/reload, merged edits, ordered runtime output, external conflict rejection, baseline reset")


def http_integration():
    from games.ff8.plugin import FF8Session
    from service_session import request_json
    with tempfile.TemporaryDirectory(prefix="lexeditor-cards-http-91-") as temporary:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": temporary}) as session:
            original = request_json(session.url + "api/cards")
            rank = (original["rows"][0]["top"] + 1) % 11
            response = request_json(session.url + "api/cards/save", {"edits": [{"id": 0, "field": "top", "value": rank}]})
            assert response["saved"] == 1
            request_json(session.url + "api/text/save", {"edits": [{"source": "exe_card_names", "sectionId": 60, "recordId": 0, "slot": 0, "value": "Test Card"}]})
            current = request_json(session.url + "api/cards")
            vanilla = request_json(session.url + "api/cards?dataset=vanilla")
            assert current["rows"][0]["top"] == rank
            assert current["rows"][0]["name"] == "Test Card"
            assert vanilla == original
        with FF8Session({"LEXEDITOR_FF8_PROJECT": temporary}) as session:
            assert request_json(session.url + "api/cards")["rows"] == current["rows"]
    print("PASS: isolated HTTP stat/name save, vanilla source and service restart persistence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CardTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.exe:
        integration(args.exe)
    if args.http:
        http_integration()
