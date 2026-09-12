from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld.package import (
    InfoDocument,
    PackageValidationError,
    StaleInfoError,
    default_info,
    validate_info,
)


class PalworldInfoTests(unittest.TestCase):
    def fixture(self) -> dict:
        return {
            "ModName": "Fixture Mod",
            "PackageName": "FixtureMod",
            "Thumbnail": "thumbnail.png",
            "Version": "1.0-test",
            "DebugMode": False,
            "MinRevision": 82182,
            "Author": "Lexer",
            "Dependencies": ["PalSchema"],
            "Tags": ["Gameplay"],
            "InstallRule": [
                {
                    "Type": "Paks",
                    "Targets": ["./Paks/"],
                    "FutureRuleKey": {"preserve": True},
                },
                {
                    "Type": "Lua",
                    "IsServer": True,
                    "Targets": ["./Scripts"],
                },
            ],
            "FutureTopLevel": {"nested": [1, 2, 3]},
        }

    def test_valid_official_shape_and_future_fields(self):
        issues = validate_info(self.fixture())
        self.assertEqual([], [issue for issue in issues if issue.severity == "error"])

    def test_package_name_matches_uploader_constraint(self):
        data = self.fixture()
        data["PackageName"] = "bad package-name"
        errors = [issue.code for issue in validate_info(data) if issue.severity == "error"]
        self.assertIn("package.characters", errors)

    def test_rule_type_and_targets_are_validated(self):
        data = self.fixture()
        data["InstallRule"] = [
            {"Type": "MadeUp", "Targets": ["./Payload"]},
            {"Type": "Paks", "Targets": []},
            {"Type": "Lua", "Targets": ["../../escape"]},
        ]
        errors = {issue.code for issue in validate_info(data) if issue.severity == "error"}
        self.assertEqual(
            {"rule.type.unknown", "rule.targets.required", "rule.target.unsafe"},
            errors,
        )

    def test_unknown_tags_warn_but_survive_forward_compatibility(self):
        data = self.fixture()
        data["Tags"].append("Future Pocketpair Tag")
        issues = validate_info(data)
        self.assertEqual([], [issue for issue in issues if issue.severity == "error"])
        self.assertIn("tag.unknown", [issue.code for issue in issues])

    def test_noop_save_is_byte_exact(self):
        raw = b'{"PackageName":"FixtureMod","InstallRule":[{"Type":"Paks","Targets":["./Paks/"]}],"Unknown":7}\n'
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "Info.json"
            path.write_bytes(raw)
            document = InfoDocument.load(path)
            document.save(path)
            self.assertEqual(raw, path.read_bytes())
            self.assertFalse((path.parent / "Info.json.lexeditor.bak").exists())

    def test_changed_save_preserves_unknown_data_and_creates_backup(self):
        raw = (json.dumps(self.fixture(), separators=(",", ":")) + "\n").encode()
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "Info.json"
            path.write_bytes(raw)
            document = InfoDocument.load(path)
            document.update({"Version": "1.1", "DebugMode": True})
            new_sha = document.save(path)
            reread = json.loads(path.read_text("utf-8"))
            self.assertEqual("1.1", reread["Version"])
            self.assertIs(True, reread["DebugMode"])
            self.assertEqual({"nested": [1, 2, 3]}, reread["FutureTopLevel"])
            self.assertTrue(reread["InstallRule"][0]["FutureRuleKey"]["preserve"])
            self.assertEqual(raw, (path.parent / "Info.json.lexeditor.bak").read_bytes())
            self.assertEqual(new_sha, InfoDocument.load(path).source_sha256)

    def test_stale_source_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "Info.json"
            path.write_text(json.dumps(default_info()), encoding="utf-8")
            document = InfoDocument.load(path)
            document.update({"Version": "2"})
            path.write_text(json.dumps({**default_info(), "Version": "external"}), encoding="utf-8")
            external = path.read_bytes()
            with self.assertRaises(StaleInfoError):
                document.save(path)
            self.assertEqual(external, path.read_bytes())

    def test_invalid_document_never_writes(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "Info.json"
            path.write_text(json.dumps(default_info()), encoding="utf-8")
            document = InfoDocument.load(path)
            document.update({"PackageName": "bad name"})
            original = path.read_bytes()
            with self.assertRaises(PackageValidationError):
                document.save(path)
            self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
