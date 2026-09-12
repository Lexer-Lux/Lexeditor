from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


xml_patch = Path("games/bannerlord/xml_patch.py")
replace_once(
    xml_patch,
    '''import math\nimport re\nfrom xml.sax.saxutils import escape, unescape\n''',
    '''import math\nfrom pathlib import Path\nimport re\nfrom xml.sax.saxutils import escape, unescape\n''',
    "xml patch Path import",
)
replace_once(
    xml_patch,
    '''_NUMBER = re.compile(r"[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)")\n\n\ndef _decode(value: str) -> str:\n''',
    '''_NUMBER = re.compile(r"[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)")\n_UTF8_BOM = b"\\xef\\xbb\\xbf"\n\n\ndef read_utf8_text_preserving(path: Path) -> tuple[str, str]:\n    """Decode UTF-8 XML without universal-newline translation and remember BOM state."""\n    raw = Path(path).read_bytes()\n    if raw.startswith(_UTF8_BOM):\n        return raw.decode("utf-8-sig"), "utf-8-sig"\n    return raw.decode("utf-8"), "utf-8"\n\n\ndef encode_utf8_text_preserving(text: str, encoding: str) -> bytes:\n    if encoding not in {"utf-8", "utf-8-sig"}:\n        raise ValueError(f"Unsupported Bannerlord XML encoding: {encoding}")\n    return str(text).encode(encoding)\n\n\ndef _decode(value: str) -> str:\n''',
    "xml byte fidelity helpers",
)


gauntlet = Path("games/bannerlord/gauntlet_data.py")
replace_once(
    gauntlet,
    '''from .paths import clear_write_helper, contained_project_path, is_contained_file\nfrom .xml_patch import scan_xml_start_tags, serialize_attribute\n''',
    '''from .paths import clear_write_helper, contained_project_path, is_contained_file\nfrom .source_revision import require_source_revision, source_revision\nfrom .xml_patch import (\n    encode_utf8_text_preserving,\n    read_utf8_text_preserving,\n    scan_xml_start_tags,\n    serialize_attribute,\n)\n''',
    "gauntlet imports",
)
replace_once(
    gauntlet,
    '''def read_prefab(project: Path, requested: str) -> dict:\n    path = _prefab_path(project, requested)\n    text = path.read_text(encoding="utf-8-sig")\n    try:\n        ET.fromstring(text)\n''',
    '''def read_prefab(project: Path, requested: str) -> dict:\n    path = _prefab_path(project, requested)\n    text, _encoding = read_utf8_text_preserving(path)\n    try:\n        ET.fromstring(text)\n''',
    "gauntlet read bytes",
)
replace_once(
    gauntlet,
    '''        "relativePath": path.relative_to(project.resolve()).as_posix(),\n        "elements": [_public(element) for element in elements],\n''',
    '''        "relativePath": path.relative_to(project.resolve()).as_posix(),\n        "sourceHash": source_revision(path),\n        "elements": [_public(element) for element in elements],\n''',
    "gauntlet source hash",
)
replace_once(
    gauntlet,
    '''def save_prefab(project: Path, requested: str, edits: list[dict]) -> dict:\n    path = _prefab_path(project, requested)\n    text = path.read_text(encoding="utf-8-sig")\n''',
    '''def save_prefab(\n    project: Path,\n    requested: str,\n    edits: list[dict],\n    source_hash: str | None = None,\n) -> dict:\n    path = _prefab_path(project, requested)\n    text, encoding = read_utf8_text_preserving(path)\n''',
    "gauntlet save revision signature",
)
replace_once(
    gauntlet,
    '''        clear_write_helper(backup)\n        shutil.copy2(path, backup)\n        temporary = path.with_name(path.name + ".lexeditor.tmp")\n        clear_write_helper(temporary)\n        temporary.write_text(candidate, encoding="utf-8")\n        temporary.replace(path)\n''',
    '''        if source_hash is not None:\n            require_source_revision(path, source_hash)\n        temporary = path.with_name(path.name + ".lexeditor.tmp")\n        clear_write_helper(temporary)\n        temporary.write_bytes(encode_utf8_text_preserving(candidate, encoding))\n        try:\n            if source_hash is not None:\n                require_source_revision(path, source_hash)\n            clear_write_helper(backup)\n            shutil.copy2(path, backup)\n            temporary.replace(path)\n        except Exception:\n            temporary.unlink(missing_ok=True)\n            raise\n''',
    "gauntlet byte-safe revision write",
)


moduledata = Path("games/bannerlord/module_xml_data.py")
replace_once(
    moduledata,
    '''from .module_data import read_submodule\nfrom .xml_patch import scan_xml_start_tags, serialize_attribute, serialize_new_attribute\n''',
    '''from .module_data import read_submodule\nfrom .source_revision import require_source_revision, source_revision\nfrom .xml_patch import (\n    encode_utf8_text_preserving,\n    read_utf8_text_preserving,\n    scan_xml_start_tags,\n    serialize_attribute,\n    serialize_new_attribute,\n)\n''',
    "moduledata imports",
)
replace_once(
    moduledata,
    '''def read_document(project: Path, requested: str, game_root: Path | None = None) -> dict:\n    path = _document_path(project, requested)\n    text = path.read_text(encoding="utf-8-sig")\n    try:\n        root = ET.fromstring(text)\n''',
    '''def read_document(project: Path, requested: str, game_root: Path | None = None) -> dict:\n    path = _document_path(project, requested)\n    text, _encoding = read_utf8_text_preserving(path)\n    try:\n        root = ET.fromstring(text)\n''',
    "moduledata read bytes",
)
replace_once(
    moduledata,
    '''        "relativePath": path.relative_to(project.resolve()).as_posix(),\n        "rootTag": root.tag,\n''',
    '''        "relativePath": path.relative_to(project.resolve()).as_posix(),\n        "sourceHash": source_revision(path),\n        "rootTag": root.tag,\n''',
    "moduledata source hash",
)
replace_once(
    moduledata,
    '''def save_document(\n    project: Path,\n    requested: str,\n    edits: list[dict],\n    game_root: Path | None = None,\n    additions: list[dict] | None = None,\n) -> dict:\n    path = _document_path(project, requested)\n    text = path.read_text(encoding="utf-8-sig")\n''',
    '''def save_document(\n    project: Path,\n    requested: str,\n    edits: list[dict],\n    game_root: Path | None = None,\n    additions: list[dict] | None = None,\n    source_hash: str | None = None,\n) -> dict:\n    path = _document_path(project, requested)\n    text, encoding = read_utf8_text_preserving(path)\n''',
    "moduledata save revision signature",
)
replace_once(
    moduledata,
    '''        paths.clear_write_helper(backup)\n        shutil.copy2(path, backup)\n        temporary = path.with_name(path.name + ".lexeditor.tmp")\n        paths.clear_write_helper(temporary)\n        temporary.write_text(candidate, encoding="utf-8")\n        temporary.replace(path)\n''',
    '''        if source_hash is not None:\n            require_source_revision(path, source_hash)\n        temporary = path.with_name(path.name + ".lexeditor.tmp")\n        paths.clear_write_helper(temporary)\n        temporary.write_bytes(encode_utf8_text_preserving(candidate, encoding))\n        try:\n            if source_hash is not None:\n                require_source_revision(path, source_hash)\n            paths.clear_write_helper(backup)\n            shutil.copy2(path, backup)\n            temporary.replace(path)\n        except Exception:\n            temporary.unlink(missing_ok=True)\n            raise\n''',
    "moduledata byte-safe revision write",
)


server = Path("games/bannerlord/server.py")
replace_once(
    server,
    '''        if path == "/api/module-data/save":\n            try:\n                payload = self.read_json()\n                self.send_json(\n                    save_document(\n                        PROJECT,\n                        str(payload.get("path") or ""),\n                        list(payload.get("edits") or []),\n                    )\n                )\n''',
    '''        if path == "/api/module-data/save":\n            try:\n                payload = self.read_json()\n                requested = str(payload.get("path") or "")\n                snapshot = read_document(PROJECT, requested)\n                source = Path(str(snapshot.get("path") or ""))\n                source_hash = payload.get("sourceHash")\n                require_source_revision(source, source_hash)\n                self.send_json(\n                    save_document(\n                        PROJECT,\n                        requested,\n                        list(payload.get("edits") or []),\n                        source_hash=source_hash,\n                    )\n                )\n''',
    "moduledata server revision",
)
replace_once(
    server,
    '''        if path == "/api/gauntlet/save":\n            try:\n                payload = self.read_json()\n                self.send_json(\n                    save_prefab(\n                        PROJECT,\n                        str(payload.get("path") or ""),\n                        list(payload.get("edits") or []),\n                    )\n                )\n''',
    '''        if path == "/api/gauntlet/save":\n            try:\n                payload = self.read_json()\n                requested = str(payload.get("path") or "")\n                snapshot = read_prefab(PROJECT, requested)\n                source = Path(str(snapshot.get("path") or ""))\n                source_hash = payload.get("sourceHash")\n                require_source_revision(source, source_hash)\n                self.send_json(\n                    save_prefab(\n                        PROJECT,\n                        requested,\n                        list(payload.get("edits") or []),\n                        source_hash=source_hash,\n                    )\n                )\n''',
    "gauntlet server revision",
)


gauntlet_editor = Path("games/bannerlord/editor_gauntlet.js")
replace_once(
    gauntlet_editor,
    '''async function loadGauntlet(path,ask=true){\n''',
    '''async function reloadGauntlet(){\n  if(!state.gauntlet)return;\n  await loadGauntlet(state.gauntlet.relativePath,true);\n}\n\nasync function loadGauntlet(path,ask=true){\n''',
    "gauntlet reload helper",
)
replace_once(
    gauntlet_editor,
    '''  const master=el("div",{class:"bl-master"},\n    el("div",{class:"bl-master-head"},el("strong",{},`Widgets (${state.gauntlet.elementCount||0})`)),\n''',
    '''  const master=el("div",{class:"bl-master"},\n    el("div",{class:"bl-master-head"},el("strong",{},`Widgets (${state.gauntlet.elementCount||0})`),\n      el("button",{type:"button",onclick:()=>reloadGauntlet()},"Reload")),\n''',
    "gauntlet reload button",
)
replace_once(
    gauntlet_editor,
    '''  const result=await post("/api/gauntlet/save",{path:state.gauntlet.relativePath,edits});\n''',
    '''  const result=await post("/api/gauntlet/save",{\n    path:state.gauntlet.relativePath,edits,sourceHash:state.savedGauntlet.sourceHash||""\n  });\n''',
    "gauntlet send revision",
)


moduledata_editor = Path("games/bannerlord/editor_moduledata.js")
replace_once(
    moduledata_editor,
    '''async function loadModuleData(path,ask=true){\n''',
    '''async function reloadModuleData(){\n  if(!state.moduleData)return;\n  await loadModuleData(state.moduleData.relativePath,true);\n}\n\nasync function loadModuleData(path,ask=true){\n''',
    "moduledata reload helper",
)
replace_once(
    moduledata_editor,
    '''    const result=prepareModuleData(await post("/api/module-data/save",{path:state.moduleData.relativePath,edits:[payload]}));\n''',
    '''    const result=prepareModuleData(await post("/api/module-data/save",{\n      path:state.moduleData.relativePath,edits:[payload],sourceHash:state.savedModuleData.sourceHash||""\n    }));\n''',
    "moduledata record revision",
)
replace_once(
    moduledata_editor,
    '''  const master=el("div",{class:"bl-master"},\n    el("div",{class:"bl-master-head"},el("strong",{},`${state.moduleData.rootTag} (${state.moduleData.recordCount||0})`)),\n''',
    '''  const master=el("div",{class:"bl-master"},\n    el("div",{class:"bl-master-head"},el("strong",{},`${state.moduleData.rootTag} (${state.moduleData.recordCount||0})`),\n      el("button",{type:"button",onclick:()=>reloadModuleData()},"Reload")),\n''',
    "moduledata reload button",
)
replace_once(
    moduledata_editor,
    '''async function saveModuleData(){const edits=moduleDataEdits();if(!edits.length)return;const result=prepareModuleData(await post("/api/module-data/save",{path:state.moduleData.relativePath,edits}));state.moduleData=result;state.savedModuleData=clone(result);if(!(result.records||[]).some(record=>record.path===state.moduleDataRecordPath))applyModuleDataRecordSelection(result.records?.[0])}\n''',
    '''async function saveModuleData(){const edits=moduleDataEdits();if(!edits.length)return;const result=prepareModuleData(await post("/api/module-data/save",{path:state.moduleData.relativePath,edits,sourceHash:state.savedModuleData.sourceHash||""}));state.moduleData=result;state.savedModuleData=clone(result);if(!(result.records||[]).some(record=>record.path===state.moduleDataRecordPath))applyModuleDataRecordSelection(result.records?.[0])}\n''',
    "moduledata save revision",
)


gauntlet_tests = Path("tests/test_bannerlord_gauntlet.py")
text = gauntlet_tests.read_text(encoding="utf-8")
marker = '''    def test_prefab_root_redirection_outside_project_is_rejected(self):\n'''
addition = '''    def test_unrelated_external_prefab_change_rejects_stale_save(self):\n        temporary, project, source = self.fixture()\n        try:\n            value = read_prefab(project, "GUI/Prefabs/Mission/LexerMoraleBars.xml")\n            widget = next(row for row in value["elements"] if row["tag"] == "Widget")\n            source.write_text(PREFAB.replace("preserve this comment", "externally changed comment"), encoding="utf-8")\n            before = source.read_bytes()\n            with self.assertRaisesRegex(ValueError, "changed on disk"):\n                save_prefab(\n                    project, value["relativePath"],\n                    [{"elementPath": widget["path"], "tag": widget["tag"], "attribute": "SuggestedHeight", "originalValue": "24", "value": 30}],\n                    source_hash=value["sourceHash"],\n                )\n            self.assertEqual(source.read_bytes(), before)\n            self.assertFalse(source.with_name(source.name + ".lexeditor.bak").exists())\n        finally:\n            temporary.cleanup()\n\n    def test_prefab_save_preserves_utf8_bom_and_crlf(self):\n        temporary, project, source = self.fixture()\n        try:\n            crlf = PREFAB.replace("\\n", "\\r\\n")\n            source.write_bytes(b"\\xef\\xbb\\xbf" + crlf.encode("utf-8"))\n            value = read_prefab(project, "GUI/Prefabs/Mission/LexerMoraleBars.xml")\n            widget = next(row for row in value["elements"] if row["tag"] == "Widget")\n            save_prefab(\n                project, value["relativePath"],\n                [{"elementPath": widget["path"], "tag": widget["tag"], "attribute": "SuggestedHeight", "originalValue": "24", "value": 30}],\n                source_hash=value["sourceHash"],\n            )\n            raw = source.read_bytes()\n            self.assertTrue(raw.startswith(b"\\xef\\xbb\\xbf"))\n            body = raw[3:]\n            self.assertIn(b' SuggestedHeight="30"', body)\n            self.assertNotIn(b"\\n", body.replace(b"\\r\\n", b""))\n        finally:\n            temporary.cleanup()\n\n    def test_gauntlet_editor_sends_revision_and_exposes_reload(self):\n        editor = Path(__file__).resolve().parents[1] / "games" / "bannerlord" / "editor_gauntlet.js"\n        text = editor.read_text(encoding="utf-8")\n        self.assertIn('sourceHash:state.savedGauntlet.sourceHash||""', text)\n        self.assertIn("async function reloadGauntlet", text)\n        self.assertIn('onclick:()=>reloadGauntlet()', text)\n\n'''
if text.count(marker) != 1:
    raise SystemExit("gauntlet test insertion point changed")
text = text.replace(marker, addition + marker, 1)
gauntlet_tests.write_text(text, encoding="utf-8")


moduledata_tests = Path("tests/test_bannerlord_moduledata.py")
text = moduledata_tests.read_text(encoding="utf-8")
marker = '''    def test_moduledata_root_redirection_outside_project_is_rejected(self):\n'''
addition = '''    def test_unrelated_external_moduledata_change_rejects_stale_save(self):\n        temporary, project, source = self.fixture()\n        try:\n            value = read_document(project, "ModuleData/items.xml")\n            item = next(row for row in value["elements"] if row["tag"] == "Item")\n            source.write_text(ITEMS.replace("preserve module-specific data", "externally changed comment"), encoding="utf-8")\n            before = source.read_bytes()\n            with self.assertRaisesRegex(ValueError, "changed on disk"):\n                save_document(\n                    project, value["relativePath"],\n                    [{"elementPath": item["path"], "tag": "Item", "attribute": "weight", "originalValue": "0.2", "value": 0.4}],\n                    source_hash=value["sourceHash"],\n                )\n            self.assertEqual(source.read_bytes(), before)\n            self.assertFalse(source.with_name(source.name + ".lexeditor.bak").exists())\n        finally:\n            temporary.cleanup()\n\n    def test_moduledata_save_preserves_utf8_bom_and_crlf(self):\n        temporary, project, source = self.fixture()\n        try:\n            crlf = ITEMS.replace("\\n", "\\r\\n")\n            source.write_bytes(b"\\xef\\xbb\\xbf" + crlf.encode("utf-8"))\n            value = read_document(project, "ModuleData/items.xml")\n            item = next(row for row in value["elements"] if row["tag"] == "Item")\n            save_document(\n                project, value["relativePath"],\n                [{"elementPath": item["path"], "tag": "Item", "attribute": "weight", "originalValue": "0.2", "value": 0.4}],\n                source_hash=value["sourceHash"],\n            )\n            raw = source.read_bytes()\n            self.assertTrue(raw.startswith(b"\\xef\\xbb\\xbf"))\n            body = raw[3:]\n            self.assertIn(b' weight="0.4"', body)\n            self.assertNotIn(b"\\n", body.replace(b"\\r\\n", b""))\n        finally:\n            temporary.cleanup()\n\n    def test_moduledata_editor_sends_revision_and_exposes_reload(self):\n        editor = Path(__file__).resolve().parents[1] / "games" / "bannerlord" / "editor_moduledata.js"\n        text = editor.read_text(encoding="utf-8")\n        self.assertIn('sourceHash:state.savedModuleData.sourceHash||""', text)\n        self.assertIn("async function reloadModuleData", text)\n        self.assertIn('onclick:()=>reloadModuleData()', text)\n\n'''
if text.count(marker) != 1:
    raise SystemExit("moduledata test insertion point changed")
text = text.replace(marker, addition + marker, 1)
moduledata_tests.write_text(text, encoding="utf-8")
