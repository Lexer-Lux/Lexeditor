"""Synthetic read-only 7th Heaven profile/folder compatibility acceptance."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.ff7 import mod_stack


class SeventhHeavenCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workshop = self.root / "7thWorkshop"
        (self.workshop / "profiles").mkdir(parents=True)
        self.library = self.root / "library"
        self.library.mkdir()
        (self.workshop / "settings.xml").write_text(
            f"<Settings><LibraryLocation>{self.library}</LibraryLocation><CurrentProfile>Default</CurrentProfile></Settings>",
            encoding="utf-8",
        )

    def profile(self, rows):
        body = []
        for row in rows:
            mod_id, name, active = row[:3]
            settings = row[3] if len(row) > 3 else {}
            values = "".join(
                f"<ProfileSetting><ID>{key}</ID><Value>{value}</Value></ProfileSetting>"
                for key, value in settings.items()
            )
            body.append(
                f"<ProfileItem><ModID>{mod_id}</ModID><Name>{name}</Name>"
                f"<IsModActive>{str(active).lower()}</IsModActive><Settings>{values}</Settings></ProfileItem>"
            )
        (self.workshop / "profiles" / "Default.xml").write_text(
            f"<Profile><Items>{''.join(body)}</Items></Profile>", encoding="utf-8")

    def library_xml(self, rows):
        body = "".join(
            f"<InstalledItem><ModID>{mod_id}</ModID><Versions><InstalledVersion><VersionDetails><Version>{version}</Version></VersionDetails><InstalledLocation>{location}</InstalledLocation></InstalledVersion></Versions></InstalledItem>"
            for mod_id, version, location in rows
        )
        (self.workshop / "library.xml").write_text(
            f"<Library><Items>{body}</Items></Library>", encoding="utf-8")

    def test_ordered_active_folder_mods_report_definite_direct_overlaps(self):
        first = self.library / "first"
        (first / "direct/kernel").mkdir(parents=True)
        (first / "direct/kernel/kernel.bin.chunk.1").write_bytes(b"one")
        second = self.library / "second"
        (second / "Option/direct/battle").mkdir(parents=True)
        (second / "Option/direct/battle/scene.bin.chunk.0").write_bytes(b"two")
        (second / "mod.xml").write_text('<ModInfo><ModFolder Folder="Option"/></ModInfo>', encoding="utf-8")
        inactive = self.library / "inactive"
        (inactive / "direct/world_us.lgp").mkdir(parents=True)
        (inactive / "direct/world_us.lgp/enc_w.bin").write_bytes(b"ignored")
        self.profile([("a", "First", True), ("b", "Second", True), ("c", "Inactive", False)])
        self.library_xml([("a", "1.0", "first"), ("b", "2.0", "second"), ("c", "9.0", "inactive")])

        report = mod_stack.scan_7h_stack(self.workshop, [
            "kernel/kernel.bin.chunk.1", "battle/scene.bin.chunk.0", "world_us.lgp/enc_w.bin"])
        self.assertEqual([row["modId"] for row in report["active"]], ["a", "b"])
        self.assertEqual([row["path"] for row in report["overlaps"]], [
            "direct/kernel/kernel.bin.chunk.1", "direct/battle/scene.bin.chunk.0"])
        self.assertTrue(report["complete"])
        self.assertFalse(report["clear"])

    def test_public_60fps_modfolder_activewhen_shape_uses_profile_settings(self):
        """Covers the public tangtang95/ff7-60fps-mod v1.15 ModFolder pattern."""
        fps = self.library / "fps"
        for folder, relative in (
            ("FieldAnimation", "kernel/kernel.bin.chunk.1"),
            ("BattleAnimation", "battle/scene.bin.chunk.0"),
            ("KOTRAnimation30FPS", "kernel/kernel.bin.chunk.2"),
        ):
            target = fps / folder / "direct" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(folder.encode("ascii"))
        (fps / "mod.xml").write_text("""<ModInfo>
          <ModFolder Folder="FieldAnimation"><ActiveWhen><Option>FPSMode = 3</Option></ActiveWhen></ModFolder>
          <ModFolder Folder="BattleAnimation"><ActiveWhen><Or><Option>FPSMode = 2</Option><Option>FPSMode = 3</Option></Or></ActiveWhen></ModFolder>
          <ModFolder Folder="KOTRAnimation30FPS"><ActiveWhen><Option>FPSMode = 2</Option></ActiveWhen></ModFolder>
        </ModInfo>""", encoding="utf-8")
        self.profile([("fps", "60/30 FPS Gameplay", True, {"FPSMode": 3})])
        self.library_xml([("fps", "1.15", "fps")])

        report = mod_stack.scan_7h_stack(self.workshop, [
            "kernel/kernel.bin.chunk.1", "battle/scene.bin.chunk.0", "kernel/kernel.bin.chunk.2"])
        self.assertEqual([row["path"] for row in report["overlaps"]], [
            "direct/battle/scene.bin.chunk.0", "direct/kernel/kernel.bin.chunk.1"])
        self.assertEqual(report["conditionalOverlaps"], [])
        self.assertTrue(report["complete"])

    def test_ffnx_prefixed_activewhen_uses_current_runtime_value(self):
        folder = self.library / "ffnx-condition"
        target = folder / "Active/direct/kernel/kernel.bin.chunk.4"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"ffnx")
        (folder / "mod.xml").write_text(
            '<ModInfo><ModFolder Folder="Active" ActiveWhen="ffnx_ff7_fps_limiter = 3"/></ModInfo>',
            encoding="utf-8")
        self.profile([("a", "FFNx conditional", True)])
        self.library_xml([("a", "1.0", "ffnx-condition")])

        off = mod_stack.scan_7h_stack(
            self.workshop, ["kernel/kernel.bin.chunk.4"], ffnx_values={"ff7_fps_limiter": 2})
        on = mod_stack.scan_7h_stack(
            self.workshop, ["kernel/kernel.bin.chunk.4"], ffnx_values={"ff7_fps_limiter": 3})
        self.assertEqual(off["overlaps"], [])
        self.assertTrue(off["complete"])
        self.assertEqual(len(on["overlaps"]), 1)

    def test_iro_and_conditional_content_are_explicitly_incomplete_not_guessed(self):
        conditional = self.library / "conditional"
        (conditional / "Maybe/direct/kernel").mkdir(parents=True)
        (conditional / "Maybe/direct/kernel/kernel.bin.chunk.2").write_bytes(b"conditional")
        (conditional / "mod.xml").write_text(
            '<ModInfo><Conditional Folder="Maybe"><ActiveWhen><Option>Flag = 1</Option></ActiveWhen>'
            '<RuntimeVar ApplyTo="">0</RuntimeVar></Conditional></ModInfo>',
            encoding="utf-8")
        (self.library / "opaque.iro").write_bytes(b"not parsed")
        self.profile([("a", "Conditional", True, {"Flag": 1}), ("b", "IRO", True)])
        self.library_xml([("a", "1.0", "conditional"), ("b", "1.0", "opaque.iro")])

        report = mod_stack.scan_7h_stack(self.workshop, ["kernel/kernel.bin.chunk.2"])
        self.assertEqual(report["overlaps"], [])
        self.assertEqual(len(report["conditionalOverlaps"]), 1)
        self.assertEqual(len(report["opaque"]), 1)
        self.assertFalse(report["complete"])
        self.assertIn("partially inspectable", report["message"])

    def test_latest_installed_version_and_missing_library_items_are_preserved_as_evidence(self):
        old = self.library / "old"; old.mkdir()
        new = self.library / "new"; (new / "direct/kernel").mkdir(parents=True)
        (new / "direct/kernel/kernel.bin.chunk.3").write_bytes(b"new")
        self.profile([("a", "Versioned", True), ("missing", "Missing", True)])
        (self.workshop / "library.xml").write_text("""<Library><Items>
          <InstalledItem><ModID>a</ModID><Versions>
            <InstalledVersion><VersionDetails><Version>1.10</Version></VersionDetails><InstalledLocation>old</InstalledLocation></InstalledVersion>
            <InstalledVersion><VersionDetails><Version>1.9</Version></VersionDetails><InstalledLocation>new</InstalledLocation></InstalledVersion>
          </Versions></InstalledItem>
        </Items></Library>""", encoding="utf-8")
        report = mod_stack.scan_7h_stack(self.workshop, ["kernel/kernel.bin.chunk.3"])
        self.assertEqual(report["active"][0]["location"], str(new.resolve()))
        self.assertEqual(len(report["overlaps"]), 1)
        self.assertEqual(len(report["missing"]), 1)
        self.assertFalse(report["complete"])

    def test_configured_scan_is_opt_in_and_invalid_state_is_reported_not_mutated(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            report = mod_stack.configured_stack(["kernel/kernel.bin.chunk.1"])
            self.assertFalse(report["checked"])
        with mock.patch.dict("os.environ", {mod_stack.WORKSHOP_ENV: str(self.workshop)}, clear=True):
            report = mod_stack.configured_stack(["kernel/kernel.bin.chunk.1"])
            self.assertTrue(report["checked"])
            self.assertFalse(report["complete"])
            self.assertIn("could not be completely inspected", report["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
