from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


project_data = Path("games/bannerlord/project_data.py")
replace_once(
    project_data,
    '''def _decode_source(raw: bytes) -> tuple[str, str]:\n    for encoding in ("utf-8-sig", "utf-8", "cp1252"):\n        try:\n            return raw.decode(encoding), encoding\n        except UnicodeDecodeError:\n            continue\n    raise ValueError("Source file is not supported text")\n''',
    '''def _decode_source(raw: bytes) -> tuple[str, str]:\n    # utf-8-sig also decodes ordinary UTF-8, so trying it first would classify\n    # every UTF-8 file as BOM-bearing and add a BOM on the next write.\n    if raw.startswith(b"\\xef\\xbb\\xbf"):\n        return raw.decode("utf-8-sig"), "utf-8-sig"\n    for encoding in ("utf-8", "cp1252"):\n        try:\n            return raw.decode(encoding), encoding\n        except UnicodeDecodeError:\n            continue\n    raise ValueError("Source file is not supported text")\n''',
    "source encoding detection",
)

test = Path("tests/test_bannerlord_source_safety.py")
text = test.read_text(encoding="utf-8")
marker = '''\n\nif __name__ == "__main__":\n    unittest.main()\n'''
addition = '''\n    def test_existing_utf8_bom_is_preserved_without_duplication(self):\n        with tempfile.TemporaryDirectory() as name:\n            project=Path(name); source=project/"notes.cs"\n            source.write_bytes(b"\\xef\\xbb\\xbfloaded\\n")\n            baseline=read_source(project,"notes.cs")["text"]\n            self.assertEqual(baseline,"loaded\\n")\n            result=save_source(project,"notes.cs","edited\\n",baseline)\n            raw=source.read_bytes()\n            self.assertTrue(raw.startswith(b"\\xef\\xbb\\xbf"))\n            self.assertFalse(raw.startswith(b"\\xef\\xbb\\xbf\\xef\\xbb\\xbf"))\n            self.assertEqual(result["text"],"edited\\n")\n'''
if text.count(marker) != 1:
    raise SystemExit("source safety test insertion point changed")
test.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")
