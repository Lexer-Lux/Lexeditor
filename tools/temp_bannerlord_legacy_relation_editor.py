from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


community = Path("games/bannerlord/community_metadata.py")
replace_once(
    community,
    '''This module normalizes the community metadata used by BLSE/BUTR plus the\nlegacy/optional dependency tags that Bannerlord.ModuleManager folds into the\nsame dependency model.  It is deliberately read-only: unknown XML attributes\nand structures remain untouched by Lexeditor until a structured writer has an\nexplicit schema for them.\n''',
    '''This module normalizes the community metadata used by BLSE/BUTR plus the\nlegacy/optional dependency tags that Bannerlord.ModuleManager folds into the\nsame dependency model. Parsing itself is read-only. Structured writes for the\nknown modern and legacy shapes live in ``module_data`` so this parser remains\nthe single normalization source for Play, diagnostics, and editor readback.\n''',
    "community metadata docstring",
)

module_data = Path("games/bannerlord/module_data.py")
replace_once(
    module_data,
    '''    community_dependencies = [\n        row for row in read_community_dependencies(path)\n        if row.get("origin") == "DependedModuleMetadatas"\n    ]\n''',
    '''    extended_dependencies = read_community_dependencies(path)\n    community_dependencies = [\n        row for row in extended_dependencies\n        if row.get("origin") == "DependedModuleMetadatas"\n    ]\n    legacy_dependencies = [\n        row for row in extended_dependencies\n        if row.get("origin") != "DependedModuleMetadatas"\n    ]\n''',
    "split legacy dependency readback",
)
replace_once(
    module_data,
    '''        "communityDependencies": community_dependencies,\n        "modulesToLoadAfterThis": modules_to_load_after_this,\n''',
    '''        "communityDependencies": community_dependencies,\n        "legacyDependencies": legacy_dependencies,\n        "modulesToLoadAfterThis": modules_to_load_after_this,\n''',
    "legacy dependency response",
)
replace_once(
    module_data,
    '''def _edit_module_id_rows(\n''',
    '''_LEGACY_DEPENDENCY_ORIGINS = {\n    "LoadAfterModules",\n    "DependedModules/OptionalDependModule",\n    "OptionalDependModules/OptionalDependModule",\n    "OptionalDependModules/DependModule",\n}\n\n\ndef _legacy_dependency_elements(root: ET.Element) -> dict[tuple[str, int], tuple[ET.Element, ET.Element]]:\n    """Map normalized legacy origins/indexes back to their original XML elements."""\n    result: dict[tuple[str, int], tuple[ET.Element, ET.Element]] = {}\n    load_after = root.find("LoadAfterModules")\n    if load_after is not None:\n        for index, element in enumerate(_element_children(load_after, "LoadAfterModule")):\n            result[("LoadAfterModules", index)] = (load_after, element)\n\n    optional_index = 0\n    depended_modules = root.find("DependedModules")\n    if depended_modules is not None:\n        for element in _element_children(depended_modules, "OptionalDependModule"):\n            result[("DependedModules/OptionalDependModule", optional_index)] = (depended_modules, element)\n            optional_index += 1\n\n    optional_root = root.find("OptionalDependModules")\n    if optional_root is not None:\n        for element in list(optional_root):\n            if element.tag not in {"OptionalDependModule", "DependModule"}:\n                continue\n            origin = f"OptionalDependModules/{element.tag}"\n            result[(origin, optional_index)] = (optional_root, element)\n            optional_index += 1\n    return result\n\n\ndef _edit_legacy_dependencies(root: ET.Element, rows: list[dict]) -> int:\n    """Edit/remove existing legacy launcher relations without inventing a legacy shape."""\n    existing = _legacy_dependency_elements(root)\n    requested: dict[tuple[str, int], str] = {}\n    for position, row in enumerate(rows):\n        module_id = str(row.get("id") or "").strip()\n        if not module_id:\n            raise ValueError(f"Legacy dependency {position + 1} needs an ID")\n        origin = str(row.get("origin") or "")\n        index = row.get("index")\n        if origin not in _LEGACY_DEPENDENCY_ORIGINS or not isinstance(index, int):\n            raise ValueError(\n                "Legacy dependency edits must reference an existing compatibility row; "\n                "create new legacy rows in source XML instead"\n            )\n        key = (origin, index)\n        if key not in existing:\n            raise ValueError("Legacy dependency changed or no longer exists; reload before saving")\n        if key in requested:\n            raise ValueError("Duplicate legacy dependency edit")\n        requested[key] = module_id\n\n    changes = 0\n    for key, (parent, element) in existing.items():\n        if key not in requested:\n            parent.remove(element)\n            changes += 1\n            continue\n        before = dict(element.attrib)\n        element.set("Id", requested[key])\n        changes += int(before != element.attrib)\n    return changes\n\n\ndef _edit_module_id_rows(\n''',
    "legacy dependency writer",
)
replace_once(
    module_data,
    '''        "communityDependencies",\n        "modulesToLoadAfterThis",\n''',
    '''        "communityDependencies",\n        "legacyDependencies",\n        "modulesToLoadAfterThis",\n''',
    "legacy relation preflight key",
)
replace_once(
    module_data,
    '''    if "communityDependencies" in payload:\n        structured = [dict(row) for row in list(payload.get("communityDependencies") or [])]\n        for row in structured:\n            row.setdefault("origin", "DependedModuleMetadatas")\n        legacy = [\n            row\n            for row in current_extended\n            if row.get("origin") != "DependedModuleMetadatas"\n        ]\n        extended = structured + legacy\n    else:\n        extended = current_extended\n''',
    '''    current_community = [\n        row for row in current_extended\n        if row.get("origin") == "DependedModuleMetadatas"\n    ]\n    current_legacy = [\n        row for row in current_extended\n        if row.get("origin") != "DependedModuleMetadatas"\n    ]\n    if "communityDependencies" in payload:\n        structured = [dict(row) for row in list(payload.get("communityDependencies") or [])]\n        for row in structured:\n            row.setdefault("origin", "DependedModuleMetadatas")\n    else:\n        structured = current_community\n    legacy = (\n        [dict(row) for row in list(payload.get("legacyDependencies") or [])]\n        if "legacyDependencies" in payload\n        else current_legacy\n    )\n    extended = structured + legacy\n''',
    "legacy relation preflight composition",
)
replace_once(
    module_data,
    '''    allowed = {"metadata", "dependencies", "communityDependencies", "modulesToLoadAfterThis", "incompatibleModules", "submodules", "xmls"}\n''',
    '''    allowed = {"metadata", "dependencies", "communityDependencies", "legacyDependencies", "modulesToLoadAfterThis", "incompatibleModules", "submodules", "xmls"}\n''',
    "legacy relation save allowance",
)
replace_once(
    module_data,
    '''    if "communityDependencies" in payload:\n        changes += _edit_community_dependencies(root, list(payload.get("communityDependencies") or []))\n    if "modulesToLoadAfterThis" in payload:\n''',
    '''    if "communityDependencies" in payload:\n        changes += _edit_community_dependencies(root, list(payload.get("communityDependencies") or []))\n    if "legacyDependencies" in payload:\n        changes += _edit_legacy_dependencies(root, list(payload.get("legacyDependencies") or []))\n    if "modulesToLoadAfterThis" in payload:\n''',
    "legacy relation save dispatch",
)
replace_once(
    module_data,
    '''            "controls": "Module identity/category, native and BLSE dependency/load-order relations, incompatibilities, submodule DLL/class/assemblies/tags, and XML registrations",\n''',
    '''            "controls": "Module identity/category, native, BLSE, and existing legacy launcher dependency/load-order relations, incompatibilities, submodule DLL/class/assemblies/tags, and XML registrations",\n''',
    "Data Map legacy controls",
)
replace_once(
    module_data,
    '''                "Structured editor for identity/category, dependency/load-order relations, incompatibilities, "\n                "submodule DLL/class/assemblies/tags, and XML registrations; unsupported or unknown nodes are "\n''',
    '''                "Structured editor for identity/category, dependency/load-order relations (including existing legacy launcher tags), incompatibilities, "\n                "submodule DLL/class/assemblies/tags, and XML registrations; unsupported or unknown nodes are "\n''',
    "Data Map legacy notes",
)

editor = Path("games/bannerlord/editor_core.js")
replace_once(
    editor,
    '''  const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],communityDependencies:m.communityDependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;\n''',
    '''  const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],communityDependencies:m.communityDependencies||[],legacyDependencies:m.legacyDependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;\n''',
    "legacy dependencies dirty/save model",
)
replace_once(
    editor,
    '''        ...fieldRow("BLSE dependency metadata",String((m.communityDependencies||[]).length)),\n        ...fieldRow("Modules forced after this",String((m.modulesToLoadAfterThis||[]).length)),\n''',
    '''        ...fieldRow("BLSE dependency metadata",String((m.communityDependencies||[]).length)),\n        ...fieldRow("Legacy launcher dependencies",String((m.legacyDependencies||[]).length)),\n        ...fieldRow("Modules forced after this",String((m.modulesToLoadAfterThis||[]).length)),\n''',
    "legacy dependency module summary",
)
replace_once(
    editor,
    '''  function relationList(kind){\n    if(kind==="community")return state.module.communityDependencies||[];\n    if(kind==="incompatible")return state.module.incompatibleModules||[];\n''',
    '''  function relationList(kind){\n    if(kind==="community")return state.module.communityDependencies||[];\n    if(kind==="legacy")return state.module.legacyDependencies||[];\n    if(kind==="incompatible")return state.module.incompatibleModules||[];\n''',
    "legacy relation selection",
)
replace_once(
    editor,
    '''      ...(state.module.communityDependencies||[]).map((row,index)=>({kind:"community",index,row})),\n      ...(state.module.modulesToLoadAfterThis||[]).map((row,index)=>({kind:"loadAfter",index,row})),\n''',
    '''      ...(state.module.communityDependencies||[]).map((row,index)=>({kind:"community",index,row})),\n      ...(state.module.legacyDependencies||[]).map((row,index)=>({kind:"legacy",index,row})),\n      ...(state.module.modulesToLoadAfterThis||[]).map((row,index)=>({kind:"loadAfter",index,row})),\n''',
    "legacy dependency rows",
)
replace_once(
    editor,
    '''  function addDependency(kind){\n''',
    '''  function legacyRelationLabel(row){\n    if(row.origin==="LoadAfterModules")return "Legacy load-after";\n    if(row.origin==="DependedModules/OptionalDependModule")return "Legacy nested optional";\n    return "Legacy optional dependency";\n  }\n  function addDependency(kind){\n''',
    "legacy relation label helper",
)
replace_once(
    editor,
    '''        const label=item.kind==="dependency"?"Native dependency":item.kind==="community"?`BLSE ${item.row.order||"metadata"}`:item.kind==="loadAfter"?"Loads after this":"Incompatible";\n''',
    '''        const label=item.kind==="dependency"?"Native dependency":item.kind==="community"?`BLSE ${item.row.order||"metadata"}`:item.kind==="legacy"?legacyRelationLabel(item.row):item.kind==="loadAfter"?"Loads after this":"Incompatible";\n''',
    "legacy relation list label",
)
replace_once(
    editor,
    '''    else if(selection.kind==="incompatible")detail=el("div",{class:"bl-detail"},\n''',
    '''    else if(selection.kind==="legacy")detail=el("div",{class:"bl-detail"},\n      el("section",{class:"bl-panel"},el("h2",{},record.id||legacyRelationLabel(record)),\n        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),\n        el("div",{class:"bl-grid"},\n          ...fieldRow("Module ID",textInput(record.id,value=>record.id=value)),\n          ...fieldRow("Legacy shape",el("code",{},record.origin||"legacy dependency"))\n        ),\n        el("div",{class:"bl-note"},record.order==="LoadAfterThis"?"This historical LoadAfterModules relation is required and orders the target after the current module.":"This historical optional-dependency relation never auto-enables its target; it only affects precedence when the module is otherwise enabled."),\n        el("div",{class:"bl-note"},"Lexeditor edits or removes existing legacy rows while preserving their original element shape and unknown attributes. Creating a new legacy relation remains source-only because several incompatible historical XML shapes exist.")));\n    else if(selection.kind==="incompatible")detail=el("div",{class:"bl-detail"},\n''',
    "legacy dependency detail editor",
)

memory = Path("codex/bannerlord/project-memory.md")
replace_once(
    memory,
    '''- Normalize BLSE `DependedModuleMetadatas`, legacy `LoadAfterModules`, and optional dependency blocks before native dependency rows. For duplicate load relations, the first row for a module ID wins; incompatibility relations use a separate first-ID-wins set.\n''',
    '''- Normalize BLSE `DependedModuleMetadatas`, legacy `LoadAfterModules`, and optional dependency blocks before native dependency rows. For duplicate load relations, the first row for a module ID wins; incompatibility relations use a separate first-ID-wins set. Existing compatibility-only legacy rows are structured-editable by ID/removal while retaining their original element shape and unknown attributes; creating new legacy rows stays source-only so Lexeditor does not invent a historical schema.\n''',
    "legacy relation project-memory invariant",
)

Path("tests/test_bannerlord_legacy_relation_editor.py").write_text(r'''from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule, save_module


LEGACY = '''<Module>
  <Name value="Legacy Shapes" />
  <Id value="LegacyShapes" />
  <SingleplayerModule value="true" />
  <DependedModules>
    <!-- nested optional comment stays -->
    <OptionalDependModule Id="NestedOptional" Mystery="keep-nested" />
    <DependedModule Id="NativeRequired" />
  </DependedModules>
  <DependedModuleMetadatas>
    <DependedModuleMetadata id="Modern" order="LoadBeforeThis" Future="keep-modern" />
  </DependedModuleMetadatas>
  <LoadAfterModules>
    <!-- load-after comment stays -->
    <LoadAfterModule Id="LegacyAfter" Future="keep-after" />
    <UnknownLegacyNode value="keep" />
  </LoadAfterModules>
  <OptionalDependModules>
    <OptionalDependModule Id="OptionalOne" Future="keep-one" />
    <DependModule Id="OptionalTwo" Future="keep-two" />
  </OptionalDependModules>
  <IncompatibleModules>
    <Module Id="Blocked" />
  </IncompatibleModules>
</Module>
'''


class BannerlordLegacyRelationEditorTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        project = Path(temporary.name)
        source = project / "SubModule.xml"
        source.write_text(LEGACY, encoding="utf-8")
        return temporary, source

    def test_readback_exposes_legacy_shapes_separately_from_blse(self):
        temporary, source = self.fixture()
        try:
            module = read_submodule(source)
            self.assertEqual([row["id"] for row in module["communityDependencies"]], ["Modern"])
            self.assertEqual(
                [(row["id"], row["origin"], row["order"], row["optional"]) for row in module["legacyDependencies"]],
                [
                    ("LegacyAfter", "LoadAfterModules", "LoadAfterThis", False),
                    ("NestedOptional", "DependedModules/OptionalDependModule", "", True),
                    ("OptionalOne", "OptionalDependModules/OptionalDependModule", "", True),
                    ("OptionalTwo", "OptionalDependModules/DependModule", "", True),
                ],
            )
        finally:
            temporary.cleanup()

    def test_existing_legacy_rows_can_be_edited_or_removed_without_shape_conversion(self):
        temporary, source = self.fixture()
        try:
            module = read_submodule(source)
            rows = module["legacyDependencies"]
            result = save_module(
                source,
                {"legacyDependencies": [
                    {**rows[0], "id": "LegacyAfterRenamed"},
                    {**rows[2], "id": "OptionalOneRenamed"},
                    rows[3],
                ]},
            )
            self.assertGreater(result["saved"], 0)
            self.assertTrue(Path(result["backup"]).is_file())
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('<LoadAfterModule Id="LegacyAfterRenamed" Future="keep-after"', rewritten)
            self.assertIn('<OptionalDependModule Id="OptionalOneRenamed" Future="keep-one"', rewritten)
            self.assertIn('<DependModule Id="OptionalTwo" Future="keep-two"', rewritten)
            self.assertNotIn('Id="NestedOptional"', rewritten)
            self.assertIn("nested optional comment stays", rewritten)
            self.assertIn("load-after comment stays", rewritten)
            self.assertIn('<UnknownLegacyNode value="keep"', rewritten)
            self.assertIn('Future="keep-modern"', rewritten)
            self.assertIn('<DependedModule Id="NativeRequired"', rewritten)
            self.assertEqual(
                [row["id"] for row in result["module"]["legacyDependencies"]],
                ["LegacyAfterRenamed", "OptionalOneRenamed", "OptionalTwo"],
            )
        finally:
            temporary.cleanup()

    def test_legacy_relation_save_participates_in_atomic_conflict_preflight(self):
        temporary, source = self.fixture()
        try:
            before = source.read_bytes()
            row = next(row for row in read_submodule(source)["legacyDependencies"] if row["id"] == "OptionalOne")
            with self.assertRaisesRegex(ValueError, "loadable and incompatible"):
                save_module(source, {"legacyDependencies": [{**row, "id": "Blocked"}]})
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(source.with_name(source.name + ".lexeditor.bak").exists())
            self.assertFalse(source.with_name(source.name + ".lexeditor.tmp").exists())
        finally:
            temporary.cleanup()

    def test_new_legacy_shape_is_not_invented_by_structured_writer(self):
        temporary, source = self.fixture()
        try:
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, "existing compatibility row"):
                save_module(source, {"legacyDependencies": [{
                    "index": None,
                    "id": "NewLegacy",
                    "origin": "OptionalDependModules/DependModule",
                    "optional": True,
                    "order": "",
                }]})
            self.assertEqual(source.read_bytes(), before)
        finally:
            temporary.cleanup()

    def test_dependency_ui_includes_legacy_read_write_surface(self):
        editor = Path(__file__).resolve().parents[1] / "games" / "bannerlord" / "editor_core.js"
        text = editor.read_text(encoding="utf-8")
        self.assertIn("legacyDependencies:m.legacyDependencies||[]", text)
        self.assertIn('selection.kind==="legacy"', text)
        self.assertIn("Creating a new legacy relation remains source-only", text)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")
