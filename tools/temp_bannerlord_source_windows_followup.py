from pathlib import Path

project_data = Path("games/bannerlord/project_data.py")
text = project_data.read_text(encoding="utf-8")
if "import os\n" not in text:
    needle = "from pathlib import Path\n"
    if text.count(needle) != 1:
        raise SystemExit("project_data import insertion point changed")
    text = text.replace(needle, needle + "import os\n", 1)
old = '''    temporary.write_text(candidate, encoding=encoding)\n'''
new = '''    # Write encoded bytes so Python's platform newline translation cannot\n    # rewrite raw-source line endings on Windows. The selected codec still\n    # preserves an existing UTF-8 BOM when one was present on load.\n    temporary.write_bytes(candidate.encode(encoding))\n'''
if old in text:
    if text.count(old) != 1:
        raise SystemExit("raw source write site is ambiguous")
    text = text.replace(old, new, 1)
if "temporary.write_bytes(candidate.encode(encoding))" not in text:
    raise SystemExit("raw source exact-byte write is missing")
project_data.write_text(text, encoding="utf-8")

test = Path("tests/test_bannerlord_plugin.py")
text = test.read_text(encoding="utf-8")
old = '''opened=read_source(project,"src/Example.cs");self.assertEqual(opened["text"],"class Example {}");saved=save_source(project,"src/Example.cs","class Example { int Value; }");self.assertTrue(Path(saved["backup"]).is_file())'''
new = '''opened=read_source(project,"src/Example.cs");self.assertEqual(opened["text"],"class Example {}");saved=save_source(project,"src/Example.cs","class Example { int Value; }",opened["text"]);self.assertTrue(Path(saved["backup"]).is_file())'''
if old in text:
    if text.count(old) != 1:
        raise SystemExit("existing source helper regression is ambiguous")
    text = text.replace(old, new, 1)
if new not in text:
    raise SystemExit("existing source helper baseline regression was not updated")
test.write_text(text, encoding="utf-8")
