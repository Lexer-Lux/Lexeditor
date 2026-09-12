from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


module_data = Path("games/bannerlord/module_data.py")
replace_once(
    module_data,
    '''def _edit_legacy_dependencies(root: ET.Element, rows: list[dict]) -> int:\n    """Edit/remove existing legacy launcher relations without inventing a legacy shape."""\n    existing = _legacy_dependency_elements(root)\n    requested: dict[tuple[str, int], str] = {}\n''',
    '''def _edit_legacy_dependencies(\n    root: ET.Element,\n    rows: list[dict],\n    baseline_rows: list[dict],\n) -> int:\n    """Edit/remove legacy rows only when their loaded identity set is still current."""\n    existing = _legacy_dependency_elements(root)\n    baseline: dict[tuple[str, int], str] = {}\n    for position, row in enumerate(baseline_rows):\n        origin = str(row.get("origin") or "")\n        index = row.get("index")\n        module_id = str(row.get("id") or "").strip()\n        if origin not in _LEGACY_DEPENDENCY_ORIGINS or not isinstance(index, int) or not module_id:\n            raise ValueError(f"Legacy dependency baseline row {position + 1} is invalid; reload before saving")\n        key = (origin, index)\n        if key in baseline:\n            raise ValueError("Duplicate legacy dependency baseline row; reload before saving")\n        baseline[key] = module_id\n\n    if set(existing) != set(baseline):\n        raise ValueError("Legacy dependency set changed on disk; reload before saving")\n    for key, (_parent, element) in existing.items():\n        current_id = str(element.attrib.get("Id") or "").strip()\n        if current_id != baseline[key]:\n            raise ValueError("Legacy dependency changed on disk; reload before saving")\n\n    requested: dict[tuple[str, int], str] = {}\n''',
    "legacy baseline writer",
)
replace_once(
    module_data,
    '''        _parent, existing_element = existing[key]\n        current_id = str(existing_element.attrib.get("Id") or "").strip()\n        original_id = str((row.get("attributes") or {}).get("Id") or "").strip()\n        if original_id and current_id != original_id:\n            raise ValueError("Legacy dependency changed on disk; reload before saving")\n        if key in requested:\n''',
    '''        if key not in baseline:\n            raise ValueError(\n                "Legacy dependency edits must reference a row from the loaded baseline; "\n                "create new legacy rows in source XML instead"\n            )\n        if key in requested:\n''',
    "legacy requested row baseline identity",
)
replace_once(
    module_data,
    '''    allowed = {"metadata", "dependencies", "communityDependencies", "legacyDependencies", "modulesToLoadAfterThis", "incompatibleModules", "submodules", "xmls"}\n    unknown = set(payload) - allowed\n''',
    '''    allowed = {"metadata", "dependencies", "communityDependencies", "legacyDependencies", "legacyDependenciesBaseline", "modulesToLoadAfterThis", "incompatibleModules", "submodules", "xmls"}\n    unknown = set(payload) - allowed\n''',
    "legacy baseline save allowance",
)
replace_once(
    module_data,
    '''    if unknown:\n        raise ValueError(f"Unsupported SubModule.xml sections: {', '.join(sorted(unknown))}")\n    _validate_relation_payload(path, payload)\n''',
    '''    if unknown:\n        raise ValueError(f"Unsupported SubModule.xml sections: {', '.join(sorted(unknown))}")\n    if "legacyDependencies" in payload and "legacyDependenciesBaseline" not in payload:\n        raise ValueError("Legacy dependency save requires the originally loaded row baseline; reload before saving")\n    _validate_relation_payload(path, payload)\n''',
    "require legacy baseline",
)
replace_once(
    module_data,
    '''    if "legacyDependencies" in payload:\n        changes += _edit_legacy_dependencies(root, list(payload.get("legacyDependencies") or []))\n''',
    '''    if "legacyDependencies" in payload:\n        changes += _edit_legacy_dependencies(\n            root,\n            list(payload.get("legacyDependencies") or []),\n            list(payload.get("legacyDependenciesBaseline") or []),\n        )\n''',
    "legacy baseline save dispatch",
)

core = Path("games/bannerlord/editor_core.js")
replace_once(
    core,
    '''  const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],communityDependencies:m.communityDependencies||[],legacyDependencies:m.legacyDependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;\n  const moduleDirty=()=>state.module&&state.savedModule&&!same(moduleEditable(state.module),moduleEditable(state.savedModule));\n''',
    '''  const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],communityDependencies:m.communityDependencies||[],legacyDependencies:m.legacyDependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;\n  const moduleSavePayload=(m,baseline)=>({...moduleEditable(m),legacyDependenciesBaseline:clone(baseline?.legacyDependencies||[])});\n  const moduleDirty=()=>state.module&&state.savedModule&&!same(moduleEditable(state.module),moduleEditable(state.savedModule));\n''',
    "legacy baseline UI payload helper",
)

boot = Path("games/bannerlord/editor_boot.js")
replace_once(
    boot,
    '''        const result=await post("/api/module/save",moduleEditable(state.module));\n''',
    '''        const result=await post("/api/module/save",moduleSavePayload(state.module,state.savedModule));\n''',
    "legacy baseline module save payload",
)

test = Path("tests/test_bannerlord_legacy_relation_editor.py")
text = test.read_text(encoding="utf-8")
text = text.replace(
    '''{"legacyDependencies": [\n                    {**rows[0], "id": "LegacyAfterRenamed"},\n                    {**rows[2], "id": "OptionalOneRenamed"},\n                    rows[3],\n                ]},''',
    '''{"legacyDependencies": [\n                    {**rows[0], "id": "LegacyAfterRenamed"},\n                    {**rows[2], "id": "OptionalOneRenamed"},\n                    rows[3],\n                ], "legacyDependenciesBaseline": rows},''',
    1,
)
text = text.replace(
    '''save_module(source, {"legacyDependencies": [{**row, "id": "Blocked"}]})''',
    '''save_module(source, {"legacyDependencies": [{**row, "id": "Blocked"}], "legacyDependenciesBaseline": read_submodule(source)["legacyDependencies"]})''',
    1,
)
old = '''            with self.assertRaisesRegex(ValueError, "existing compatibility row"):\n                save_module(source, {"legacyDependencies": [{\n                    "index": None,\n                    "id": "NewLegacy",\n                    "origin": "OptionalDependModules/DependModule",\n                    "optional": True,\n                    "order": "",\n                }]})\n'''
new = '''            baseline = read_submodule(source)["legacyDependencies"]\n            with self.assertRaisesRegex(ValueError, "loaded baseline"):\n                save_module(source, {"legacyDependencies": [{\n                    "index": None,\n                    "id": "NewLegacy",\n                    "origin": "OptionalDependModules/DependModule",\n                    "optional": True,\n                    "order": "",\n                }], "legacyDependenciesBaseline": baseline})\n'''
if text.count(old) != 1:
    raise SystemExit("new legacy shape regression block changed")
text = text.replace(old, new, 1)
text = text.replace(
    '''                {"legacyDependencies": [\n                    {**rows[0], "id": "ValidAfterRenamed"},\n                    rows[1],\n                    rows[2],\n                ]},''',
    '''                {"legacyDependencies": [\n                    {**rows[0], "id": "ValidAfterRenamed"},\n                    rows[1],\n                    rows[2],\n                ], "legacyDependenciesBaseline": rows},''',
    1,
)
text = text.replace(
    '''                save_module(source, {"legacyDependencies": rows})''',
    '''                save_module(source, {"legacyDependencies": rows, "legacyDependenciesBaseline": rows})''',
    1,
)
marker = '''    def test_dependency_ui_includes_legacy_read_write_surface(self):\n'''
addition = """    def test_external_legacy_addition_is_not_misread_as_user_deletion(self):
        temporary, source = self.fixture()
        try:
            baseline = read_submodule(source)["legacyDependencies"]
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    '<LoadAfterModule Id="LegacyAfter" Future="keep-after" />',
                    '<LoadAfterModule Id="LegacyAfter" Future="keep-after" />\\n    <LoadAfterModule Id="ExternallyAdded" Future="keep-external" />',
                ),
                encoding="utf-8",
            )
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, "set changed on disk"):
                save_module(source, {"legacyDependencies": baseline, "legacyDependenciesBaseline": baseline})
            self.assertEqual(source.read_bytes(), before)
            self.assertIn(b'ExternallyAdded', before)
            self.assertFalse(source.with_name(source.name + ".lexeditor.bak").exists())
            self.assertFalse(source.with_name(source.name + ".lexeditor.tmp").exists())
        finally:
            temporary.cleanup()

    def test_legacy_save_without_loaded_baseline_is_rejected(self):
        temporary, source = self.fixture()
        try:
            rows = read_submodule(source)["legacyDependencies"]
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, "originally loaded row baseline"):
                save_module(source, {"legacyDependencies": rows})
            self.assertEqual(source.read_bytes(), before)
        finally:
            temporary.cleanup()

""" + marker
if text.count(marker) != 1:
    raise SystemExit("legacy UI regression insertion point changed")
text = text.replace(marker, addition, 1)
text = text.replace(
    '''        self.assertIn("legacyDependencies:m.legacyDependencies||[]", text)\n''',
    '''        self.assertIn("legacyDependencies:m.legacyDependencies||[]", text)\n        self.assertIn("legacyDependenciesBaseline", text)\n''',
    1,
)
test.write_text(text, encoding="utf-8")
