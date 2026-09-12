from pathlib import Path
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

    def test_malformed_legacy_rows_are_preserved_without_shifting_valid_indexes(self):
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
        editor = Path(__file__).resolve().parents[1] / "games" / "bannerlord" / "editor_core.js"
        text = editor.read_text(encoding="utf-8")
        self.assertIn("legacyDependencies:m.legacyDependencies||[]", text)
        self.assertIn('selection.kind==="legacy"', text)
        self.assertIn("Creating a new legacy relation remains source-only", text)


if __name__ == "__main__":
    unittest.main()
