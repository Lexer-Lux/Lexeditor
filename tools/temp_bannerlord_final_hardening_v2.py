import subprocess

PAYLOAD_COMMIT = "ab1d2398235aba282bab231d60e9b8eb1a87e962"
subprocess.run(
    ["git", "fetch", "--depth=16", "origin", "feature/bannerlord-plugin"],
    check=True,
)
payload = subprocess.check_output(
    ["git", "show", f"{PAYLOAD_COMMIT}:tools/temp_bannerlord_final_hardening.py"],
    text=True,
)
old = '''    if count != 1:\n        raise SystemExit(f"{label}: expected one match, found {count}")\n    path.write_text(text.replace(old, new, 1), encoding="utf-8")\n'''
new = '''    if count < 1:\n        raise SystemExit(f"{label}: expected a match, found {count}")\n    if count != 1 and not label.endswith(" read"):\n        raise SystemExit(f"{label}: expected one match, found {count}")\n    path.write_text(text.replace(old, new, 1), encoding="utf-8")\n'''
if payload.count(old) != 1:
    raise SystemExit("could not patch final hardening matcher")
payload = payload.replace(old, new, 1)
exec(compile(payload, "temp_bannerlord_final_hardening_payload.py", "exec"))

# Raw Source also uses an exact-byte revision, not only decoded baseline text.
project = Path("games/bannerlord/project_data.py")
replace_once(
    project,
    '''def read_source(project: Path, requested: str) -> dict:\n    target = _safe_project_path(project, requested)\n    text, encoding = _decode_source(target.read_bytes())\n    return {\n        "path": target.relative_to(project.resolve()).as_posix(),\n''',
    '''def read_source(project: Path, requested: str) -> dict:\n    target = _safe_project_path(project, requested)\n    raw = target.read_bytes()\n    text, encoding = _decode_source(raw)\n    return {\n        "path": target.relative_to(project.resolve()).as_posix(),\n        "sourceHash": revision_bytes(raw),\n''',
    "raw source hash",
)
replace_once(
    project,
    '''def save_source(\n    project: Path,\n    requested: str,\n    text: str,\n    original_text: str | None = None,\n) -> dict:\n''',
    '''def save_source(\n    project: Path,\n    requested: str,\n    text: str,\n    original_text: str | None = None,\n    source_hash: str | None = None,\n) -> dict:\n''',
    "raw source hash signature",
)
replace_once(
    project,
    '''    loaded_revision = revision_bytes(raw_bytes)\n    if original_text is None:\n''',
    '''    loaded_revision = revision_bytes(raw_bytes)\n    if source_hash is not None:\n        require_source_revision(target, source_hash)\n    if original_text is None:\n''',
    "raw source initial revision",
)
replace_once(
    project,
    '''    backup = replace_source_bytes(target, encoded, loaded_revision)\n''',
    '''    backup = replace_source_bytes(target, encoded, source_hash or loaded_revision)\n''',
    "raw source expected revision",
)

server = Path("games/bannerlord/server.py")
replace_once(
    server,
    '''                        str(payload.get("text") or ""),\n                        payload.get("originalText") if "originalText" in payload else None,\n                    )\n''',
    '''                        str(payload.get("text") or ""),\n                        payload.get("originalText") if "originalText" in payload else None,\n                        payload.get("sourceHash"),\n                    )\n''',
    "raw source server revision",
)

boot = Path("games/bannerlord/editor_boot.js")
replace_once(
    boot,
    '''          path:state.source.path,text:state.source.text,originalText:state.savedSourceText\n''',
    '''          path:state.source.path,text:state.source.text,originalText:state.savedSourceText,\n          sourceHash:state.source.sourceHash||""\n''',
    "raw source UI revision",
)

source_tests = Path("tests/test_bannerlord_source_safety.py")
text = source_tests.read_text(encoding="utf-8")
marker = '''    def test_matching_source_baseline_writes_and_backs_up(self):\n'''
addition = '''    def test_external_bom_only_change_is_rejected_by_exact_byte_revision(self):\n        with tempfile.TemporaryDirectory() as name:\n            project=Path(name);source=project/"notes.cs";source.write_bytes(b"\\xef\\xbb\\xbfloaded\\r\\n")\n            loaded=read_source(project,"notes.cs")\n            source.write_bytes(b"loaded\\r\\n")\n            before=source.read_bytes()\n            with self.assertRaisesRegex(ValueError,"changed on disk"):\n                save_source(project,"notes.cs","edited\\r\\n",loaded["text"],loaded["sourceHash"])\n            self.assertEqual(source.read_bytes(),before)\n            self.assertFalse(source.with_name(source.name+".lexeditor.bak").exists())\n\n'''
if text.count(marker) != 1:
    raise SystemExit("raw source revision test insertion point changed")
source_tests.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")
