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
    '''    temporary = target.with_name(target.name + ".lexeditor.tmp")\n    clear_write_helper(temporary)\n    temporary.write_text(candidate, encoding=encoding)\n    temporary.replace(target)\n''',
    '''    temporary = target.with_name(target.name + ".lexeditor.tmp")\n    clear_write_helper(temporary)\n    # Write encoded bytes so Python's platform newline translation cannot\n    # rewrite raw-source line endings on Windows. The selected codec still\n    # preserves an existing UTF-8 BOM when one was present on load.\n    temporary.write_bytes(candidate.encode(encoding))\n    temporary.replace(target)\n''',
    "raw source exact-byte newline write",
)

test = Path("tests/test_bannerlord_plugin.py")
replace_once(
    test,
    '''opened=read_source(project,"src/Example.cs");self.assertEqual(opened["text"],"class Example {}");saved=save_source(project,"src/Example.cs","class Example { int Value; }");self.assertTrue(Path(saved["backup"]).is_file())''',
    '''opened=read_source(project,"src/Example.cs");self.assertEqual(opened["text"],"class Example {}");saved=save_source(project,"src/Example.cs","class Example { int Value; }",opened["text"]);self.assertTrue(Path(saved["backup"]).is_file())''',
    "existing source helper baseline regression",
)
