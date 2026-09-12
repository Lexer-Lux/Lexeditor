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
    '''    optional_root = root.find("OptionalDependModules")\n    if optional_root is not None:\n        for element in list(optional_root):\n            if element.tag not in {"OptionalDependModule", "DependModule"}:\n                continue\n            origin = f"OptionalDependModules/{element.tag}"\n            if str(element.attrib.get("Id") or "").strip():\n                result[(origin, optional_index)] = (optional_root, element)\n            optional_index += 1\n''',
    '''    optional_root = root.find("OptionalDependModules")\n    if optional_root is not None:\n        for tag in ("OptionalDependModule", "DependModule"):\n            for element in _element_children(optional_root, tag):\n                origin = f"OptionalDependModules/{tag}"\n                if str(element.attrib.get("Id") or "").strip():\n                    result[(origin, optional_index)] = (optional_root, element)\n                optional_index += 1\n''',
    "mirror ModuleManager optional tag-group index order",
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
    """    def test_optional_root_indexes_follow_modulemanager_tag_grouping(self):
        mixed = '''<Module>
  <Id value="MixedLegacy" />
  <DependedModules>
    <OptionalDependModule Id="Nested" Future="keep-nested" />
  </DependedModules>
  <OptionalDependModules>
    <DependModule Id="DependFirstInXml" Future="keep-depend" />
    <OptionalDependModule Id="OptionalSecondInXml" Future="keep-optional" />
  </OptionalDependModules>
</Module>
'''
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "SubModule.xml"
            source.write_text(mixed, encoding="utf-8")
            rows = read_submodule(source)["legacyDependencies"]
            self.assertEqual(
                [(row["id"], row["origin"], row["index"]) for row in rows],
                [
                    ("Nested", "DependedModules/OptionalDependModule", 0),
                    ("OptionalSecondInXml", "OptionalDependModules/OptionalDependModule", 1),
                    ("DependFirstInXml", "OptionalDependModules/DependModule", 2),
                ],
            )
            save_module(
                source,
                {"legacyDependencies": [
                    rows[0],
                    {**rows[1], "id": "OptionalRenamed"},
                    {**rows[2], "id": "DependRenamed"},
                ]},
            )
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('DependModule Id="DependRenamed" Future="keep-depend"', rewritten)
            self.assertIn('OptionalDependModule Id="OptionalRenamed" Future="keep-optional"', rewritten)
            self.assertLess(rewritten.index('DependModule Id="DependRenamed"'), rewritten.index('OptionalDependModule Id="OptionalRenamed"'))

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
    "tag-group and stale legacy regressions",
)
