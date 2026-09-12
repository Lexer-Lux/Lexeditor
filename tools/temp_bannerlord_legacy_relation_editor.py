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
    '''    if load_after is not None:\n        for index, element in enumerate(_element_children(load_after, "LoadAfterModule")):\n            result[("LoadAfterModules", index)] = (load_after, element)\n\n    optional_index = 0\n    depended_modules = root.find("DependedModules")\n    if depended_modules is not None:\n        for element in _element_children(depended_modules, "OptionalDependModule"):\n            result[("DependedModules/OptionalDependModule", optional_index)] = (depended_modules, element)\n            optional_index += 1\n\n    optional_root = root.find("OptionalDependModules")\n    if optional_root is not None:\n        for element in list(optional_root):\n            if element.tag not in {"OptionalDependModule", "DependModule"}:\n                continue\n            origin = f"OptionalDependModules/{element.tag}"\n            result[(origin, optional_index)] = (optional_root, element)\n            optional_index += 1\n''',
    '''    if load_after is not None:\n        for index, element in enumerate(_element_children(load_after, "LoadAfterModule")):\n            if not str(element.attrib.get("Id") or "").strip():\n                continue\n            result[("LoadAfterModules", index)] = (load_after, element)\n\n    optional_index = 0\n    depended_modules = root.find("DependedModules")\n    if depended_modules is not None:\n        for element in _element_children(depended_modules, "OptionalDependModule"):\n            if str(element.attrib.get("Id") or "").strip():\n                result[("DependedModules/OptionalDependModule", optional_index)] = (depended_modules, element)\n            optional_index += 1\n\n    optional_root = root.find("OptionalDependModules")\n    if optional_root is not None:\n        for element in list(optional_root):\n            if element.tag not in {"OptionalDependModule", "DependModule"}:\n                continue\n            origin = f"OptionalDependModules/{element.tag}"\n            if str(element.attrib.get("Id") or "").strip():\n                result[(origin, optional_index)] = (optional_root, element)\n            optional_index += 1\n''',
    "ignore malformed legacy rows without shifting indexes",
)

test = Path("tests/test_bannerlord_legacy_relation_editor.py")
replace_once(
    test,
    '''    def test_dependency_ui_includes_legacy_read_write_surface(self):\n''',
    '''    def test_malformed_legacy_rows_are_preserved_without_shifting_valid_indexes(self):\n        malformed = '''<Module>\n  <Id value="MalformedLegacy" />\n  <LoadAfterModules>\n    <LoadAfterModule Future="blank-after" />\n    <LoadAfterModule Id="ValidAfter" Future="keep-after" />\n  </LoadAfterModules>\n  <DependedModules>\n    <OptionalDependModule Future="blank-nested" />\n    <OptionalDependModule Id="NestedValid" Future="keep-nested" />\n  </DependedModules>\n  <OptionalDependModules>\n    <OptionalDependModule Future="blank-optional" />\n    <DependModule Id="OptionalValid" Future="keep-optional" />\n  </OptionalDependModules>\n</Module>\n'''\n        with tempfile.TemporaryDirectory() as name:\n            source = Path(name) / "SubModule.xml"\n            source.write_text(malformed, encoding="utf-8")\n            rows = read_submodule(source)["legacyDependencies"]\n            self.assertEqual(\n                [(row["id"], row["origin"], row["index"]) for row in rows],\n                [\n                    ("ValidAfter", "LoadAfterModules", 1),\n                    ("NestedValid", "DependedModules/OptionalDependModule", 1),\n                    ("OptionalValid", "OptionalDependModules/DependModule", 3),\n                ],\n            )\n            save_module(\n                source,\n                {"legacyDependencies": [\n                    {**rows[0], "id": "ValidAfterRenamed"},\n                    rows[1],\n                    rows[2],\n                ]},\n            )\n            rewritten = source.read_text(encoding="utf-8")\n            self.assertIn('Future="blank-after"', rewritten)\n            self.assertIn('Future="blank-nested"', rewritten)\n            self.assertIn('Future="blank-optional"', rewritten)\n            self.assertIn('Id="ValidAfterRenamed" Future="keep-after"', rewritten)\n            self.assertIn('Id="NestedValid" Future="keep-nested"', rewritten)\n            self.assertIn('Id="OptionalValid" Future="keep-optional"', rewritten)\n\n    def test_dependency_ui_includes_legacy_read_write_surface(self):\n''',
    "malformed legacy preservation regression",
)
