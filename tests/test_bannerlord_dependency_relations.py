import unittest

from games.bannerlord.dependency_relations import (
    effective_incompatible_relations,
    effective_load_relations,
    incompatible_relation_rows,
    load_relation_rows,
)


class BannerlordDependencyRelationTests(unittest.TestCase):
    def test_extended_rows_precede_native_rows_and_shadow_duplicates(self):
        module = {
            "dependencies": [
                {"id": "Library", "dependentVersion": "v1.0.0", "optional": False, "attributes": {}},
                {"id": "NativeOnly", "dependentVersion": "", "optional": False, "attributes": {}},
            ],
            "modulesToLoadAfterThis": [
                {"id": "Library", "attributes": {}},
                {"id": "NativeAfter", "attributes": {}},
            ],
            "incompatibleModules": [],
        }
        extended = [
            {
                "id": "Library",
                "order": "LoadAfterThis",
                "optional": True,
                "incompatible": False,
                "version": "v2.0.*",
                "origin": "DependedModuleMetadatas",
                "attributes": {},
            }
        ]
        rows = load_relation_rows(module, extended)
        self.assertEqual([row["id"] for row in rows], ["Library", "Library", "NativeOnly", "Library", "NativeAfter"])
        self.assertTrue(rows[0]["effective"])
        self.assertEqual(rows[0]["source"], "community")
        self.assertEqual(rows[0]["order"], "LoadAfterThis")
        self.assertFalse(rows[1]["effective"])
        self.assertEqual(rows[1]["shadowedByOrigin"], "DependedModuleMetadatas")
        self.assertFalse(rows[3]["effective"])
        self.assertEqual(
            [(row["id"], row["order"], row["optional"]) for row in effective_load_relations(module, extended)],
            [
                ("Library", "LoadAfterThis", True),
                ("NativeOnly", "LoadBeforeThis", False),
                ("NativeAfter", "LoadAfterThis", True),
            ],
        )

    def test_first_extended_duplicate_wins_even_when_later_row_is_required(self):
        module = {"dependencies": [], "modulesToLoadAfterThis": [], "incompatibleModules": []}
        extended = [
            {"id": "Library", "order": "LoadBeforeThis", "optional": True, "incompatible": False, "origin": "DependedModuleMetadatas"},
            {"id": "Library", "order": "LoadAfterThis", "optional": False, "incompatible": False, "origin": "DependedModuleMetadatas"},
        ]
        rows = effective_load_relations(module, extended)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["optional"])
        self.assertEqual(rows[0]["order"], "LoadBeforeThis")

    def test_native_load_after_is_optional_and_loses_to_native_dependency(self):
        module = {
            "dependencies": [{"id": "Library", "optional": False}],
            "modulesToLoadAfterThis": [{"id": "Library"}],
            "incompatibleModules": [],
        }
        rows = load_relation_rows(module, [])
        self.assertEqual(rows[0]["origin"], "DependedModules")
        self.assertTrue(rows[0]["effective"])
        self.assertEqual(rows[0]["order"], "LoadBeforeThis")
        self.assertFalse(rows[0]["optional"])
        self.assertEqual(rows[1]["origin"], "ModulesToLoadAfterThis")
        self.assertFalse(rows[1]["effective"])
        self.assertTrue(rows[1]["optional"])

    def test_incompatibility_precedence_is_separate_from_load_precedence(self):
        module = {
            "dependencies": [{"id": "Library", "optional": False}],
            "modulesToLoadAfterThis": [],
            "incompatibleModules": [{"id": "Library", "attributes": {}}],
        }
        extended = [
            {"id": "Library", "order": "LoadBeforeThis", "optional": False, "incompatible": True, "origin": "DependedModuleMetadatas"},
            {"id": "Library", "order": "LoadAfterThis", "optional": False, "incompatible": False, "origin": "DependedModuleMetadatas"},
        ]
        load_rows = effective_load_relations(module, extended)
        self.assertEqual([(row["id"], row["order"]) for row in load_rows], [("Library", "LoadAfterThis")])
        incompatibles = incompatible_relation_rows(module, extended)
        self.assertTrue(incompatibles[0]["effective"])
        self.assertFalse(incompatibles[1]["effective"])
        self.assertEqual(
            [(row["id"], row["origin"]) for row in effective_incompatible_relations(module, extended)],
            [("Library", "DependedModuleMetadatas")],
        )

    def test_precedence_is_case_sensitive_like_distinct_by_string_id(self):
        module = {
            "dependencies": [{"id": "library", "optional": False}],
            "modulesToLoadAfterThis": [],
            "incompatibleModules": [],
        }
        extended = [
            {"id": "Library", "order": "LoadBeforeThis", "optional": True, "incompatible": False, "origin": "DependedModuleMetadatas"},
        ]
        self.assertEqual([row["id"] for row in effective_load_relations(module, extended)], ["Library", "library"])


if __name__ == "__main__":
    unittest.main()
