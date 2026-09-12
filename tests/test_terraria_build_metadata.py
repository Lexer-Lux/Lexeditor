from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest

from games.terraria.build_metadata import parse_build_text, update_build_text
from games.terraria import server


class TerrariaBuildMetadataTests(unittest.TestCase):
    def test_reads_known_values_and_reports_duplicate_keys(self):
        text = (
            "author = First\n"
            "futureThing = keep me\n"
            "side = Client\n"
            "author = Second\n"
        )
        metadata = parse_build_text(text)
        self.assertEqual(metadata.values["author"], "Second")
        self.assertEqual(metadata.values["side"], "Client")
        self.assertEqual(metadata.duplicates, ("author",))
        self.assertNotIn("futureThing", metadata.values)

    def test_reads_tmodloader_list_properties(self):
        metadata = parse_build_text(
            "modReferences = MagicStorage@0.6.0, RecipeBrowser, , BossChecklist\n"
            "weakReferences = Census\n"
            "dllReferences = NativeLibrary\n"
            "sortAfter = MagicStorage, RecipeBrowser\n"
            "sortBefore = BossChecklist\n"
            "buildIgnore = obj/*, bin/*\n"
        )
        self.assertEqual(
            metadata.values["modReferences"],
            ["MagicStorage@0.6.0", "RecipeBrowser", "BossChecklist"],
        )
        self.assertEqual(metadata.values["weakReferences"], ["Census"])
        self.assertEqual(metadata.values["dllReferences"], ["NativeLibrary"])
        self.assertEqual(metadata.values["sortAfter"], ["MagicStorage", "RecipeBrowser"])
        self.assertEqual(metadata.values["sortBefore"], ["BossChecklist"])
        self.assertEqual(metadata.values["buildIgnore"], ["obj/*", "bin/*"])

    def test_noop_is_byte_exact(self):
        text = "displayName   =   Example Mod  \r\nfuture = untouched\r\n"
        self.assertEqual(update_build_text(text, {"displayName": "Example Mod"}), text)

    def test_list_semantic_noop_is_byte_exact(self):
        text = "modReferences=One,Two\r\nfuture = untouched\r\n"
        self.assertEqual(
            update_build_text(text, {"modReferences": ["One", "Two"]}),
            text,
        )

    def test_changed_write_preserves_unknown_lines_and_spacing(self):
        text = (
            "# retained future/comment-ish line\n"
            "displayName   =   Example Mod  \n"
            "futureKey = opaque=value\n"
            "side = Both\n"
        )
        changed = update_build_text(text, {"displayName": "Renamed", "side": "nosync"})
        self.assertEqual(
            changed,
            "# retained future/comment-ish line\n"
            "displayName   =   Renamed  \n"
            "futureKey = opaque=value\n"
            "side = NoSync\n",
        )

    def test_list_write_and_clear_preserve_unrelated_content(self):
        text = (
            "modReferences = One, Two\n"
            "futureKey = keep\n"
            "sortAfter = Old\n"
        )
        changed = update_build_text(
            text,
            {
                "modReferences": ["One@1.2", "Three"],
                "sortAfter": [],
                "buildIgnore": ["obj/*", "bin/*"],
            },
        )
        self.assertEqual(
            changed,
            "modReferences = One@1.2, Three\n"
            "futureKey = keep\n"
            "buildIgnore = obj/*, bin/*\n",
        )

    def test_missing_key_appends_without_rewriting_existing_content(self):
        text = "author = Lexer\r\nunknown = preserve"
        changed = update_build_text(text, {"version": "1.2.3"})
        self.assertEqual(changed, "author = Lexer\r\nunknown = preserve\r\nversion = 1.2.3\r\n")

    def test_duplicate_key_refuses_all_structured_writes(self):
        text = "author = One\nauthor = Two\nside = Both\n"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            update_build_text(text, {"side": "Server"})

    def test_boolean_and_side_validation(self):
        self.assertEqual(update_build_text("", {"hideCode": True}), "hideCode = true\n")
        with self.assertRaisesRegex(ValueError, "true or false"):
            update_build_text("", {"hideCode": "yes"})
        with self.assertRaisesRegex(ValueError, "Both, Client, Server, NoSync"):
            update_build_text("", {"side": "Maybe"})

    def test_system_version_shape_is_bounded(self):
        self.assertEqual(update_build_text("", {"version": "1.2.3.4"}), "version = 1.2.3.4\n")
        for invalid in ("1", "1.2.3.4.5", "1.-2", "1.beta", "2147483648.0"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    update_build_text("", {"version": invalid})

    def test_reference_list_validation_matches_tmodloader_constraints(self):
        with self.assertRaisesRegex(ValueError, "2 to 4"):
            update_build_text("", {"modReferences": ["ExampleMod@1"]})
        with self.assertRaisesRegex(ValueError, "Duplicate mod/weak reference"):
            update_build_text(
                "",
                {"modReferences": ["ExampleMod"], "weakReferences": ["ExampleMod@1.2"]},
            )
        with self.assertRaisesRegex(ValueError, "dllReferences"):
            update_build_text(
                "",
                {"modReferences": ["ExampleMod"], "dllReferences": ["ExampleMod"]},
            )
        with self.assertRaisesRegex(ValueError, "must be a list"):
            update_build_text("", {"modReferences": "ExampleMod"})

    def test_multiline_and_unknown_structured_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            update_build_text("", {"author": "one\ntwo"})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            update_build_text("", {"futureStructured": "ExampleMod"})

    def test_service_preserves_bom_and_refuses_stale_writes(self):
        previous = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = directory
                target = Path(directory) / "build.txt"
                original = server.UTF8_BOM + b"author = Lexer\r\nunknown = preserve\r\n"
                target.write_bytes(original)
                original_sha = sha256(original).hexdigest()

                state = server.save_build({"author": "Changed"}, original_sha)
                saved = target.read_bytes()
                self.assertTrue(saved.startswith(server.UTF8_BOM))
                self.assertIn(b"author = Changed\r\n", saved)
                self.assertIn(b"unknown = preserve\r\n", saved)
                self.assertEqual(state["sha256"], sha256(saved).hexdigest())

                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.save_build({"author": "Again"}, original_sha)
        finally:
            if previous is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous


if __name__ == "__main__":
    unittest.main()
