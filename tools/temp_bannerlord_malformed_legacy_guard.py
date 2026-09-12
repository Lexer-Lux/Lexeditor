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
replace_once(
    module_data,
    '''        key = (origin, index)\n        if key not in existing:\n            raise ValueError("Legacy dependency changed or no longer exists; reload before saving")\n        if key in requested:\n            raise ValueError("Duplicate legacy dependency edit")\n        requested[key] = module_id\n''',
    '''        key = (origin, index)\n        if key not in existing:\n            raise ValueError("Legacy dependency changed or no longer exists; reload before saving")\n        _parent, existing_element = existing[key]\n        current_id = str(existing_element.attrib.get("Id") or "").strip()\n        original_id = str((row.get("attributes") or {}).get("Id") or "").strip()\n        if original_id and current_id != original_id:\n            raise ValueError("Legacy dependency changed on disk; reload before saving")\n        if key in requested:\n            raise ValueError("Duplicate legacy dependency edit")\n        requested[key] = module_id\n''',
    "reject stale legacy row identity",
)

test = Path("tests/test_bannerlord_legacy_relation_editor.py")
replace_once(
    test,
    '''    def test_dependency_ui_includes_legacy_read_write_surface(self):\n''',
    """    def test_malformed_legacy_rows_are_preserved_without_shifting_valid_indexes(self):
        malformed = '''<Module>
  <Id value="MalformedLegacy" />
  <LoadAfterModules>
    <LoadAfterModule Future="blank-after" />
    <LoadAfterModule Id="ValidAfter" Future="keep-after" />
  </LoadAfterModules>
  <DependedModules>
    <OptionalDependModule Future="blank-nested" />
    <OptionalDependModule Id="NestedValid" Future="keep-nested" />
  </DependedModules>
  <OptionalDependModules>
    <OptionalDependModule Future="blank-optional" />
    <DependModule Id="OptionalValid" Future="keep-optional" />
  </OptionalDependModules>
</Module>
'''
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "SubModule.xml"
            source.write_text(malformed, encoding="utf-8")
            rows = read_submodule(source)["legacyDependencies"]
            self.assertEqual(
                [(row["id"], row["origin"], row["index"]) for row in rows],
                [
                    ("ValidAfter", "LoadAfterModules", 1),
                    ("NestedValid", "DependedModules/OptionalDependModule", 1),
                    ("OptionalValid", "OptionalDependModules/DependModule", 3),
                ],
            )
            save_module(
                source,
                {"legacyDependencies": [
                    {**rows[0], "id": "ValidAfterRenamed"},
                    rows[1],
                    rows[2],
                ]},
            )
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('Future="blank-after"', rewritten)
            self.assertIn('Future="blank-nested"', rewritten)
            self.assertIn('Future="blank-optional"', rewritten)
            self.assertIn('Id="ValidAfterRenamed" Future="keep-after"', rewritten)
            self.assertIn('Id="NestedValid" Future="keep-nested"', rewritten)
            self.assertIn('Id="OptionalValid" Future="keep-optional"', rewritten)

    def test_stale_legacy_row_identity_is_rejected_before_write(self):
        temporary, source = self.fixture()
        try:
            rows = read_submodule(source)["legacyDependencies"]
            source.write_text(
                source.read_text(encoding="utf-8").replace('Id="LegacyAfter"', 'Id="ChangedAfter"'),
                encoding="utf-8",
            )
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                save_module(source, {"legacyDependencies": rows})
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(source.with_name(source.name + ".lexeditor.bak").exists())
            self.assertFalse(source.with_name(source.name + ".lexeditor.tmp").exists())
        finally:
            temporary.cleanup()

    def test_dependency_ui_includes_legacy_read_write_surface(self):
""",
    "malformed and stale legacy preservation regressions",
)
