from __future__ import annotations

import unittest

from games.terraria.build_metadata import parse_build_text, update_build_text


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

    def test_noop_is_byte_exact(self):
        text = "displayName   =   Example Mod  \r\nfuture = untouched\r\n"
        self.assertEqual(update_build_text(text, {"displayName": "Example Mod"}), text)

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

    def test_missing_key_appends_without_rewriting_existing_content(self):
        text = "author = Lexer\r\nunknown = preserve"
        changed = update_build_text(text, {"version": "1.2.3"})
        self.assertEqual(changed, "author = Lexer\r\nunknown = preserve\r\nversion = 1.2.3\r\n")

    def test_duplicate_target_refuses_structured_write(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            update_build_text("side = Both\nside = Client\n", {"side": "Server"})

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

    def test_multiline_and_unknown_structured_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            update_build_text("", {"author": "one\ntwo"})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            update_build_text("", {"modReferences": "ExampleMod"})


if __name__ == "__main__":
    unittest.main()
