from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile

from plugins.factorio.data_map import build_data_map
from plugins.factorio import server as factorio_server
from plugins.factorio.model import (
    FactorioDataError, PrototypeStore, build_mod_bytes, detect_install,
    export_dependencies, export_mod, project_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "factorio"


class FactorioModelTests(unittest.TestCase):
    def project(self, temp: Path) -> Path:
        target = temp / "project"
        shutil.copytree(FIXTURE, target)
        return target

    def test_fixture_exposes_requested_structured_families(self):
        with tempfile.TemporaryDirectory() as name:
            store = PrototypeStore.from_project(self.project(Path(name)))
            self.assertEqual([row["name"] for row in store.rows("recipes")],
                             ["fixture-water", "iron-gear-wheel"])
            item_types = {row["prototypeType"] for row in store.rows("items")}
            self.assertEqual(len(store.rows("items")), 10)
            self.assertTrue({
                "gun", "item-with-label", "item-with-tags",
                "space-platform-starter-pack",
            } <= item_types)
            self.assertEqual({row["prototypeType"] for row in store.rows("machines")},
                             {"assembling-machine", "furnace", "rocket-silo"})
            self.assertEqual([row["name"] for row in store.rows("technologies")],
                             ["automation", "automation-2"])
            self.assertEqual(store.diagnostics(), [])

    def test_noop_save_does_not_touch_source_snapshot(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            source = project / "source" / "data-raw-dump.json"
            before = source.read_bytes()
            PrototypeStore.from_project(project).save(project)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(json.loads((project / "overrides.json").read_text(encoding="utf-8")),
                             {"format": 1, "edits": {}})

    def test_edit_save_reopen_roundtrip_keeps_source_dump_immutable(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            source = project / "source" / "data-raw-dump.json"
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            store = PrototypeStore.from_project(project)
            store.set_edit("recipes", "iron-gear-wheel", {
                "enabled": False,
                "energy_required": 0.75,
                "maximum_productivity": 2.5,
            })
            store.set_edit("items", "iron-plate", {"stack_size": 250})
            store.set_edit("machines", "assembling-machine-1", {"crafting_speed": 1.25})
            store.set_edit("technologies", "automation", {
                "enabled": True,
                "prerequisites": [],
                "unit_count": 25,
                "unit_time": 10,
            })
            store.save(project)
            reopened = PrototypeStore.from_project(project)
            recipe = next(row for row in reopened.rows("recipes")
                          if row["name"] == "iron-gear-wheel")
            item = next(row for row in reopened.rows("items")
                        if row["name"] == "iron-plate")
            machine = next(row for row in reopened.rows("machines")
                           if row["name"] == "assembling-machine-1")
            technology = next(row for row in reopened.rows("technologies")
                              if row["name"] == "automation")
            self.assertFalse(recipe["enabled"])
            self.assertEqual(recipe["energyRequired"], 0.75)
            self.assertEqual(item["stackSize"], 250)
            self.assertEqual(machine["craftingSpeed"], 1.25)
            self.assertEqual(technology["unitCount"], 25)
            self.assertEqual(technology["unitTime"], 10)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_edit_delta_omits_unchanged_modeled_fields_and_can_reset(self):
        with tempfile.TemporaryDirectory() as name:
            store = PrototypeStore.from_project(self.project(Path(name)))
            delta = store.set_edit("recipes", "iron-gear-wheel", {
                "enabled": True,
                "energy_required": 0.75,
                "maximum_productivity": 3.0,
            })
            self.assertEqual(delta, {"energy_required": 0.75})
            self.assertEqual(
                store.overrides["edits"]["recipes"]["iron-gear-wheel"],
                {"energy_required": 0.75},
            )
            reset = store.set_edit("recipes", "iron-gear-wheel", {
                "enabled": True,
                "energy_required": 0.5,
                "maximum_productivity": 3.0,
            })
            self.assertEqual(reset, {})
            self.assertNotIn("recipes", store.overrides["edits"])

    def test_post_mod_snapshot_overlap_preserves_unedited_fields_and_load_order(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            source = project / "source" / "data-raw-dump.json"
            raw = json.loads(source.read_text(encoding="utf-8"))
            recipe = raw["recipe"]["iron-gear-wheel"]

            # Model a real source-mod overlap: the imported dump is already the
            # result of Factorio's data stages, so these are the values Lexeditor
            # must compose against rather than vanilla defaults.
            recipe["energy_required"] = 3.5
            recipe["maximum_productivity"] = 8.0
            recipe["source_mod_marker"] = "Krastorio2"
            source.write_text(
                json.dumps(raw, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            mod_list_path = project / "source" / "mod-list.json"
            mod_list = json.loads(mod_list_path.read_text(encoding="utf-8"))
            mod_list["mods"].extend([
                {"name": "Krastorio2", "enabled": True},
                {"name": "aai-industry", "enabled": True},
            ])
            mod_list_path.write_text(json.dumps(mod_list), encoding="utf-8")

            store = PrototypeStore.from_project(project)
            delta = store.set_edit("recipes", "iron-gear-wheel", {
                "enabled": True,
                "energy_required": 4.0,
                "maximum_productivity": 8.0,
            })
            self.assertEqual(delta, {"energy_required": 4.0})

            _name, package = build_mod_bytes(project, store)
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                info = json.loads(archive.read(
                    "lexeditor-factorio-fixture_0.1.0/info.json"))
                script = archive.read(
                    "lexeditor-factorio-fixture_0.1.0/data-final-fixes.lua"
                ).decode("utf-8")

            self.assertIn("? Krastorio2", info["dependencies"])
            self.assertIn("? aai-industry", info["dependencies"])
            self.assertIn("p.energy_required = 4", script)
            self.assertNotIn("maximum_productivity", script)
            self.assertNotIn("source_mod_marker", script)
            self.assertNotIn("p.enabled", script)
            preserved = json.loads(source.read_text(encoding="utf-8"))
            self.assertEqual(
                preserved["recipe"]["iron-gear-wheel"]["source_mod_marker"],
                "Krastorio2",
            )
            self.assertEqual(
                preserved["recipe"]["iron-gear-wheel"]["maximum_productivity"],
                8.0,
            )

    def test_dirty_count_tracks_changes_since_saved_overrides(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            store = PrototypeStore.from_project(project)
            store.set_edit("recipes", "iron-gear-wheel", {
                "enabled": True,
                "energy_required": 0.75,
                "maximum_productivity": 3.0,
            })
            store.save(project)

            reopened = PrototypeStore.from_project(project)
            with mock.patch.object(
                    factorio_server, "_saved_edits",
                    factorio_server._snapshot_edits(reopened)):
                self.assertEqual(factorio_server._dirty_records(reopened), 0)
                reopened.set_edit("items", "iron-plate", {"stack_size": 250})
                self.assertEqual(factorio_server._dirty_records(reopened), 1)
                reopened.set_edit(
                    "machines", "assembling-machine-1",
                    {"crafting_speed": 1.25},
                )
                self.assertEqual(factorio_server._dirty_records(reopened), 2)
                reopened.set_edit("items", "iron-plate", {"stack_size": 100})
                self.assertEqual(factorio_server._dirty_records(reopened), 1)

    def test_ranges_and_references_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            store = PrototypeStore.from_project(self.project(Path(name)))
            bad = (
                ("recipes", "iron-gear-wheel", {"energy_required": 0.001}),
                ("recipes", "iron-gear-wheel", {"maximum_productivity": -0.01}),
                ("items", "single-token", {"stack_size": 2}),
                ("items", "fixture-blueprint", {"stack_size": 2}),
                ("items", "iron-plate", {"stack_size": 0}),
                ("machines", "assembling-machine-1", {"crafting_speed": 0}),
                ("technologies", "automation", {"prerequisites": ["missing-tech"]}),
                ("technologies", "automation", {"prerequisites": ["automation"]}),
                ("technologies", "automation", {"prerequisites": ["automation-2"]}),
                ("technologies", "automation", {"unit_count": 0}),
                ("technologies", "automation-2", {"unit_count": 200}),
                ("technologies", "automation", {"unit_time": float("inf")}),
            )
            for kind, prototype, changes in bad:
                with self.subTest(kind=kind, prototype=prototype, changes=changes):
                    with self.assertRaises(FactorioDataError):
                        store.set_edit(kind, prototype, changes)

    def test_non_json_and_truncated_dump_are_rejected(self):
        for invalid in (
            'data:extend({{type="recipe",name="not-json"}})',
            '{"recipe":{"broken":',
        ):
            with self.subTest(invalid=invalid):
                with tempfile.TemporaryDirectory() as name:
                    project = self.project(Path(name))
                    (project / "source" / "data-raw-dump.json").write_text(
                        invalid, encoding="utf-8")
                    with self.assertRaisesRegex(
                            FactorioDataError, "Invalid Factorio prototype dump"):
                        PrototypeStore.from_project(project)

    def test_atomic_override_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            target = project / "overrides.json"
            original = b'{\n  "edits": {},\n  "format": 1\n}\n'
            target.write_bytes(original)
            store = PrototypeStore.from_project(project)
            store.set_edit("items", "iron-plate", {"stack_size": 250})
            with mock.patch("plugins.factorio.model.os.replace",
                            side_effect=OSError("synthetic replace failure")):
                with self.assertRaisesRegex(OSError, "synthetic replace failure"):
                    store.save(project)
            self.assertEqual(target.read_bytes(), original)
            leftovers = [path for path in project.iterdir()
                         if path.is_file() and path.name != "overrides.json"
                         and path.name.startswith("tmp")]
            self.assertEqual(leftovers, [])

    def test_export_is_byte_deterministic_and_native_factorio_shape(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            store = PrototypeStore.from_project(project)
            store.set_edit("recipes", "iron-gear-wheel", {
                "enabled": False,
                "energy_required": 0.75,
                "maximum_productivity": 2.0,
            })
            store.set_edit("technologies", "automation", {
                "enabled": True,
                "prerequisites": [],
                "unit_count": 20,
                "unit_time": 12,
            })
            first_name, first = build_mod_bytes(project, store)
            second_name, second = build_mod_bytes(project, store)
            self.assertEqual(first_name, second_name)
            self.assertEqual(first, second)
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(sorted(archive.namelist()), [
                    "lexeditor-factorio-fixture_0.1.0/data-final-fixes.lua",
                    "lexeditor-factorio-fixture_0.1.0/info.json",
                ])
                info = json.loads(archive.read(
                    "lexeditor-factorio-fixture_0.1.0/info.json"))
                script = archive.read(
                    "lexeditor-factorio-fixture_0.1.0/data-final-fixes.lua").decode("utf-8")
            self.assertEqual(info["factorio_version"], "2.1")
            self.assertEqual(info["dependencies"], [
                "base >= 2.1.0", "? fixture-source", "? space-age"])
            self.assertIn('data.raw["recipe"]["iron-gear-wheel"]', script)
            self.assertIn("p.energy_required = 0.75", script)
            self.assertIn("p.unit.count = 20", script)
            self.assertNotIn("data:extend", script)
            self.assertNotIn("loadfile", script)
            self.assertNotIn("require(", script)

            # Exercise the same live-store export contract used by /api/export.
            exported = export_mod(
                project, output_dir=project / "candidate", store=store)
            self.assertEqual(exported.read_bytes(), first)

            mod_list_path = project / "source" / "mod-list.json"
            mod_list = json.loads(mod_list_path.read_text(encoding="utf-8"))
            mod_list["mods"].append({
                "name": "lexeditor-factorio-fixture", "enabled": True,
            })
            mod_list_path.write_text(json.dumps(mod_list), encoding="utf-8")
            _name, self_filtered = build_mod_bytes(project, store)
            with zipfile.ZipFile(io.BytesIO(self_filtered)) as archive:
                info_self = json.loads(archive.read(
                    "lexeditor-factorio-fixture_0.1.0/info.json"))
            self.assertNotIn("? lexeditor-factorio-fixture",
                             info_self["dependencies"])

    def test_dependency_validation_rejects_injection(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            manifest = project_manifest(project)
            self.assertEqual(export_dependencies(project, manifest["mod"]["dependencies"]),
                             ["base >= 2.1.0", "? fixture-source", "? space-age"])
            manifest["mod"]["dependencies"].append('? bad"; os.execute("oops") --')
            (project / "factorio-project.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(FactorioDataError):
                project_manifest(project)

    def test_manifest_and_dependency_versions_follow_factorio_bounds(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            original = project_manifest(project)
            for bad_version in ("1.2", "1.2.3.4", "65536.0.0"):
                with self.subTest(mod_version=bad_version):
                    manifest = json.loads(json.dumps(original))
                    manifest["mod"]["version"] = bad_version
                    (project / "factorio-project.json").write_text(
                        json.dumps(manifest), encoding="utf-8")
                    with self.assertRaises(FactorioDataError):
                        project_manifest(project)
            for dependency in (
                "? optional >= 1.2",
                "? optional >= 65536.0.0",
            ):
                with self.subTest(dependency=dependency):
                    manifest = json.loads(json.dumps(original))
                    manifest["mod"]["dependencies"] = [dependency]
                    (project / "factorio-project.json").write_text(
                        json.dumps(manifest), encoding="utf-8")
                    with self.assertRaises(FactorioDataError):
                        project_manifest(project)

    def test_manifest_rejects_invalid_generated_info_metadata(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            original = project_manifest(project)
            bad = [
                ("title", 42),
                ("title", "x" * 101),
                ("author", ["not", "text"]),
                ("description", {"not": "text"}),
                ("dependencies", {}),
            ]
            for key, value in bad:
                with self.subTest(key=key):
                    manifest = json.loads(json.dumps(original))
                    manifest["mod"][key] = value
                    (project / "factorio-project.json").write_text(
                        json.dumps(manifest), encoding="utf-8")
                    with self.assertRaises(FactorioDataError):
                        project_manifest(project)

    def test_dependency_grammar_accepts_factorio_markers_and_comparisons(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            manifest = project_manifest(project)
            manifest["mod"]["dependencies"] = [
                "base >= 2.1.0",
                "? optional_mod",
                "(?) hidden_optional = 1.2.3",
                "+ load_after > 4.2.0",
                "~ no_order <= 3.0.0",
                "! incompatible < 9.9.9",
            ]
            (project / "factorio-project.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            parsed = project_manifest(project)
            self.assertEqual(parsed["mod"]["dependencies"],
                             manifest["mod"]["dependencies"])

    def test_current_mod_portal_names_fit_optional_load_order_contract(self):
        # Public Factorio 2.1 mods checked during the PR audit. The plugin
        # only needs their internal names here: source mods stay untouched and
        # become optional dependencies so the generated final-fixes mod loads
        # after them when they are enabled in the imported profile.
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            mod_list = {
                "mods": [
                    {"name": "base", "enabled": True},
                    {"name": "aai-industry", "enabled": True},
                    {"name": "factoryplanner", "enabled": True},
                    {"name": "RateCalculator", "enabled": True},
                    {"name": "flib", "enabled": True},
                    {"name": "even-distribution", "enabled": True},
                    {"name": "Krastorio2", "enabled": True},
                ],
            }
            (project / "source" / "mod-list.json").write_text(
                json.dumps(mod_list), encoding="utf-8")
            self.assertEqual(
                export_dependencies(project, ["base >= 2.1.0"]),
                [
                    "base >= 2.1.0",
                    "? aai-industry",
                    "? even-distribution",
                    "? factoryplanner",
                    "? flib",
                    "? Krastorio2",
                    "? RateCalculator",
                ],
            )

    def test_server_edit_context_rejects_unsupported_configured_install(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = self.project(root)
            game = root / "game"
            base = game / "data" / "base"
            base.mkdir(parents=True)
            (base / "info.json").write_text(
                json.dumps({"name": "base", "version": "2.0.72"}),
                encoding="utf-8")
            with (
                mock.patch.object(factorio_server, "PROJECT_ROOT", project),
                mock.patch.object(factorio_server, "GAME_ROOT", game),
            ):
                with self.assertRaisesRegex(
                        FactorioDataError, "not supported"):
                    factorio_server._require_edit_context()

    def test_server_edit_context_rejects_invalid_project_manifest(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = self.project(root)
            manifest = json.loads(
                (project / "factorio-project.json").read_text(encoding="utf-8"))
            manifest["mod"]["version"] = "2.1"
            (project / "factorio-project.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            with (
                mock.patch.object(factorio_server, "PROJECT_ROOT", project),
                mock.patch.object(factorio_server, "GAME_ROOT", None),
            ):
                with self.assertRaisesRegex(
                        FactorioDataError, "number.number.number"):
                    factorio_server._require_edit_context()

    def test_install_version_and_dlc_detection_are_data_only(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for mod in ("base", "space-age", "quality", "elevated-rails"):
                folder = root / "data" / mod
                folder.mkdir(parents=True)
                (folder / "info.json").write_text(json.dumps({
                    "name": mod, "version": "2.1.19"
                }), encoding="utf-8")
            info = detect_install(root)
            self.assertEqual(info.version, "2.1.19")
            self.assertTrue(info.supported)
            self.assertTrue(info.space_age_installed)
            self.assertTrue(info.quality_installed)
            self.assertTrue(info.elevated_rails_installed)
            (root / "data" / "base" / "info.json").write_text(
                json.dumps({"name": "base", "version": "2.0.72"}), encoding="utf-8")
            self.assertFalse(detect_install(root).supported)

    def test_data_map_is_explicit_about_partial_and_unsupported_scope(self):
        with tempfile.TemporaryDirectory() as name:
            project = self.project(Path(name))
            store = PrototypeStore.from_project(project)
            counts = {kind: len(store.rows(kind))
                      for kind in ("recipes", "items", "machines", "technologies")}
            payload = build_data_map(
                project, counts=counts, diagnostics=[],
                unsupported_prototypes={"tile": 2, "character": 1},
            )
            rows = {row["filename"]: row for row in payload["rows"]}
            self.assertEqual(rows["data.raw.recipe"]["status"], "partial")
            self.assertEqual(rows["data.raw.technology"]["status"], "partial")
            self.assertEqual(rows["overrides.json"]["status"], "integrated")
            self.assertEqual(rows["other data.raw prototype types"]["status"],
                             "not-integrated")
            self.assertEqual(rows["data.raw.tile"]["status"], "not-integrated")
            self.assertEqual(rows["data.raw.tile"]["records"], 2)
            self.assertEqual(rows["data.raw.character"]["records"], 1)
            self.assertFalse(rows["control.lua / runtime scripts"]["openable"])
            self.assertTrue(rows["data.raw.recipe"]["openable"])


if __name__ == "__main__":
    unittest.main()
