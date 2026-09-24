"""Portable RDR editor regression checks. No installed game or native plugin required."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.rdr import magic_rdr_manager, mission_rewards, server, string_tables
from tools.rdr_test_support import workspace, loot_document, fake_resource_tool


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdr-editor-test-")
        self.addCleanup(self.temp.cleanup)
        self.fixture = workspace(Path(self.temp.name))
        self.paths = self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)
        self.shop = server.shops_payload()["rows"][0]
        self.item = server.items_payload()["rows"][0]

    def shop_save(self, value, field="PriceModifier"):
        return server.save_shop(self.shop["source"], self.shop["rootHash"], self.shop["itemIndex"],
                                self.shop["name"], [{"field": field, "value": value}])

    def item_save(self, value, field="MaxItemCount"):
        return server.save_item("base", 0, "TEST_0", [{"field": field, "value": value}])

    def ini_save(self, value, key="TimeScale", section="WeaponRadial"):
        return server.save_settings([{"section": section, "key": key, "value": value}])

    def test_magic_rdr_helper_is_pinned_read_only_and_reports_upstream(self):
        tool = Path(self.temp.name) / "Rpf6ReadCli.exe"
        names = Path(self.temp.name) / "ImportedFileNames.txt"
        missing = magic_rdr_manager.status(tool, names)
        self.assertFalse(missing["installed"])
        self.assertFalse(missing["installable"])
        tool.write_bytes(b"local bridge")
        names.write_text("example")
        ready = magic_rdr_manager.status(tool, names)
        self.assertTrue(ready["installed"])
        self.assertEqual(ready["version"], magic_rdr_manager.PINNED_RELEASE)
        self.assertFalse(ready["autoUpdate"])
        latest = magic_rdr_manager.upstream_release(lambda _url: {
            "tag_name": "v1.3.11",
            "draft": False,
            "prerelease": False,
            "published_at": "2026-01-01T00:00:00Z",
        })
        self.assertEqual(latest["pinned"], "v1.3.10")
        self.assertEqual(latest["latest"], "v1.3.11")
        self.assertTrue(latest["behind"])
        self.assertFalse(latest["installable"])

    def test_decimal_shop_price_roundtrip_and_noop(self):
        original = Path(self.shop["sourcePath"]).read_bytes()
        self.assertEqual(self.shop_save("1.1")["saved"], 1)
        expected = struct.unpack("<f", struct.pack("<f", 1.1))[0]
        self.assertEqual(server.shops_payload()["rows"][0]["priceModifier"], expected)
        self.assertEqual(self.shop_save("1.1")["saved"], 0)
        self.assertEqual(Path(self.shop["sourcePath"]).read_bytes(), original)

    def test_repack_corruption_preserves_override_and_backup(self):
        self.shop_save(2)
        self.shop_save(3)
        target = Path(self.shop["projectPath"])
        backup = target.with_name(target.name + ".lexeditor.bak")
        before = target.read_bytes(), backup.read_bytes()
        def corrupt(args, **kwargs):
            fake_resource_tool(args, **kwargs)
            if args[0] == "resource-pack":
                output = Path(args[-1])
                damaged = bytearray(output.read_bytes())
                damaged[-1] ^= 1
                output.write_bytes(damaged)
        with patch.object(server, "_run_resource_tool", corrupt):
            with self.assertRaisesRegex(RuntimeError, "not changed"):
                self.shop_save(4)
        self.assertEqual((target.read_bytes(), backup.read_bytes()), before)

    def test_failed_first_repack_does_not_create_override(self):
        with patch.object(server, "_run_resource_tool", side_effect=RuntimeError("pack failed")):
            with self.assertRaisesRegex(RuntimeError, "pack failed"):
                self.shop_save(4)
        self.assertFalse(Path(self.shop["projectPath"]).exists())

    def test_invalid_shop_numbers_do_not_write(self):
        for value in (True, None, "", "nan", "inf", -0.1, 1000.1, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.shop_save(value)
        for field in ("QuantityPerPurchase", "TotalAvailableQuantity"):
            for value in (True, "", "1.2", -2, 2147483648):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.shop_save(value, field)
        self.assertFalse(Path(self.shop["projectPath"]).exists())

    def test_shop_stock_bounds_and_unlimited(self):
        self.assertEqual(self.shop_save(-1, "TotalAvailableQuantity")["saved"], 1)
        self.assertEqual(self.shop_save(0, "QuantityPerPurchase")["saved"], 1)
        self.assertEqual(server.shops_payload()["rows"][0]["totalAvailableQuantity"], -1)

    def test_shop_handoff_is_deterministic_reversible_and_does_not_clobber_custom_price(self):
        plan = server.shop_test_plan()
        self.assertTrue(plan["available"])
        self.assertEqual(plan["status"], "baseline")
        identity = plan["id"]
        source_bytes = Path(next(row for row in server.shops_payload(True)["rows"] if row["id"] == identity)["sourcePath"]).read_bytes()
        staged = server.stage_shop_test()
        self.assertEqual(staged["test"]["id"], identity)
        self.assertEqual(staged["test"]["status"], "staged")
        self.assertEqual(staged["test"]["currentPriceModifier"], plan["testPriceModifier"])
        self.assertEqual(server.shop_test_plan()["id"], identity)
        restored = server.restore_shop_test()
        self.assertEqual(restored["test"]["status"], "baseline")
        self.assertEqual(restored["test"]["currentPriceModifier"], plan["baselinePriceModifier"])
        active = next(row for row in server.shops_payload()["rows"] if row["id"] == identity)
        server.save_shop(active["source"], active["rootHash"], active["itemIndex"], active["name"],
                         [{"field": "PriceModifier", "value": 3.0}])
        self.assertEqual(server.shop_test_plan()["status"], "custom")
        with self.assertRaisesRegex(ValueError, "will not overwrite"):
            server.stage_shop_test()
        self.assertEqual(Path(active["sourcePath"]).read_bytes(), source_bytes)

    def test_item_numeric_bounds_and_enums(self):
        for field, values in {
            "MaxItemCount": (-2, 100001, "1.5", "nan", True),
            "HUDReticleIndex": (-2, 256, "0.2"),
            "SpawnTimeOut": (-1, 86401, "inf"),
            "Enabled": ("1", "maybe"),
            "mp_EquipStringId": ("UNPROVEN_ENUM",),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.item_save(value, field)
        self.assertFalse(Path(self.item["projectPath"]).exists())

    def test_item_fractional_timeout_and_unknown_xml_preserved(self):
        original = Path(self.item["sourcePath"]).read_bytes()
        self.assertEqual(self.item_save("0.5", "SpawnTimeOut")["saved"], 1)
        saved = Path(self.item["projectPath"]).read_text()
        for text in ('SpawnTimeOut value="0.5"', '<!--keep-comment-->', 'Nested value="untouched"'):
            self.assertIn(text, saved)
        self.assertEqual(Path(self.item["sourcePath"]).read_bytes(), original)

    def test_bool_and_fractional_indices_are_not_records(self):
        for index in (True, 0.5, "0"):
            with self.subTest(index=index), self.assertRaises(ValueError):
                server.save_item("base", index, "TEST_0", [])
            with self.subTest(index=index), self.assertRaises(ValueError):
                server.save_shop(self.shop["source"], self.shop["rootHash"], index, self.shop["name"], [])

    def test_malformed_edit_lists(self):
        for value in ({}, "bad", [None], [1]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.save_item("base", 0, "TEST_0", value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.save_settings(value)

    def test_settings_validation_leaves_bytes_unchanged(self):
        target = self.paths["SETTINGS_FILE"]
        before = target.read_bytes()
        for key, values in {"TimeScale": ("", "nan", "inf", "0", "1.01", "0.5 ; injected", True),
                            "Enabled": ("1", "maybe", "true\nOther=false")}.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.ini_save(value, key)
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(target.with_name(target.name + ".lexeditor.bak").exists())

    def test_settings_comment_newline_backup_and_noop(self):
        target = self.paths["SETTINGS_FILE"]
        original = target.read_bytes()
        self.assertEqual(self.ini_save(" 0.5 ")["saved"], 1)
        self.assertIn(b"TimeScale = 0.5 ; keep inline\r\nUnknownKey=keep\r\n", target.read_bytes())
        self.assertIn(b"Enabled=false\r\n", target.read_bytes())
        self.assertEqual(target.with_name(target.name + ".lexeditor.bak").read_bytes(), original)
        self.assertEqual(self.ini_save("0.5")["saved"], 0)

    def test_settings_batch_validation_before_write(self):
        before = self.paths["SETTINGS_FILE"].read_bytes()
        with self.assertRaises(ValueError):
            server.save_settings([{"section": "WeaponRadial", "key": "Enabled", "value": "true"},
                                  {"section": "WeaponRadial", "key": "TimeScale", "value": "-1"}])
        self.assertEqual(self.paths["SETTINGS_FILE"].read_bytes(), before)

    def test_settings_unknown_comment_injection_not_written(self):
        before = self.paths["SETTINGS_FILE"].read_bytes()
        with self.assertRaises(ValueError):
            self.ini_save("value ; unexpected comment", "UnknownKey")
        self.assertEqual(self.paths["SETTINGS_FILE"].read_bytes(), before)

    def test_loot_contract_validation(self):
        for mutate in (
            lambda d: d.update(schemaVersion=True),
            lambda d: d["money"]["decoratorPaths"].append(d["money"]["decoratorPaths"][0]),
            lambda d: d["money"]["decoratorPaths"].append(None),
            lambda d: d["money"]["baseRoll"]["range"].update(minimum=True),
            lambda d: d["money"]["baseRoll"]["range"].update(maximum=float("nan")),
            lambda d: d["corpseBonusItem"]["entries"][0].update(quantity=1.2),
            lambda d: d["corpseBonusItem"].update(chancePercent=101),
        ):
            document = loot_document()
            mutate(document)
            with self.subTest(document=document), self.assertRaises(ValueError):
                server.save_loot(document)

    def test_loot_roundtrip_and_optional_evidence(self):
        document = loot_document()
        document.pop("source")
        document["corpseBonusItem"]["entries"][0]["quantity"] = 7
        self.assertEqual(server.save_loot(document)["saved"], 1)
        self.assertEqual(server.loot_payload()["document"], document)

    def test_string_table_index_edit_reopen_and_vanilla_source(self):
        index = server.string_tables_index()
        self.assertEqual(index["counts"]["tables"], 2)
        self.assertEqual(index["counts"]["available"], 2)
        self.assertEqual(index["counts"]["records"], 8)
        self.assertFalse(any(
            row["path"].casefold().endswith("_ps3.strtbl")
            for row in index["tables"]
        ))

        path = "tune/stringtable/global.strtbl"
        payload = server.string_table_payload("tuning", path)
        row = next(
            entry for entry in payload["rows"]
            if entry["languageIndex"] == 0 and entry["identifier"] == "HELLO"
        )
        source = Path(payload["table"]["sourcePath"])
        source_bytes = source.read_bytes()
        result = server.save_string_table("tuning", path, [{
            "languageIndex": row["languageIndex"],
            "entryIndex": row["entryIndex"],
            "expectedHash": row["hash"],
            "expectedText": row["text"],
            "value": "Hello from New Austin",
        }])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(source.read_bytes(), source_bytes)
        project = Path(payload["table"]["projectPath"])
        self.assertTrue(project.is_file())

        reopened = server.string_table_payload("tuning", path)
        current = next(
            entry for entry in reopened["rows"]
            if entry["languageIndex"] == 0 and entry["identifier"] == "HELLO"
        )
        self.assertEqual(current["text"], "Hello from New Austin")
        vanilla = server.string_table_payload("tuning", path, True)
        original = next(
            entry for entry in vanilla["rows"]
            if entry["languageIndex"] == 0 and entry["identifier"] == "HELLO"
        )
        self.assertEqual(original["text"], "Hello")

        no_change = server.save_string_table("tuning", path, [{
            "languageIndex": current["languageIndex"],
            "entryIndex": current["entryIndex"],
            "expectedHash": current["hash"],
            "expectedText": current["text"],
            "value": current["text"],
        }])
        self.assertEqual(no_change["saved"], 0)

    def test_string_language_view_combines_resources_without_fake_record_ids(self):
        index = server.string_tables_index()
        english = next(row for row in index["languages"] if row["label"] == "English")
        self.assertIn("Spanish (Spain)", {row["label"] for row in index["languages"]})
        self.assertIn("Spanish (Mexico)", {row["label"] for row in index["languages"]})
        payload = server.strings_payload(english["index"])
        self.assertEqual(payload["language"]["label"], "English")
        self.assertGreaterEqual(payload["counts"]["tables"], 2)
        paths = {row["path"] for row in payload["rows"]}
        self.assertIn("tune/stringtable/global.strtbl", paths)
        self.assertIn("content/dlc/zombiepack/zombiepack_standalone.strtbl", paths)
        self.assertTrue(all(row["language"] == "English" for row in payload["rows"]))

    def test_shared_string_block_has_separate_logical_language_tabs(self):
        index = server.string_tables_index()
        mexican = next(row for row in index["languages"] if row["label"] == "Spanish (Mexico)")
        payload = server.strings_payload(mexican["index"])
        self.assertTrue(payload["rows"])
        self.assertTrue(all(row["language"] == "Spanish (Mexico)" for row in payload["rows"]))
        self.assertTrue(all(mexican["index"] in row["languageIndexes"] for row in payload["rows"]))
        row = payload["rows"][0]
        self.assertNotEqual(row["languageIndex"], row["languageIndexes"][0])
        candidate, changed = string_tables.apply_text_edits(
            Path(row["sourcePath"]).read_bytes(),
            [{
                "languageIndex": row["languageIndex"],
                "entryIndex": row["entryIndex"],
                "expectedHash": row["hash"],
                "expectedText": row["text"],
                "value": row["text"] + " FR",
            }],
        )
        self.assertEqual(changed, 1)
        reparsed = string_tables.rows(string_tables.parse(candidate))
        shared = next(item for item in reparsed if row["entryIndex"] == item["entryIndex"]
                      and mexican["index"] in item["languageIndexes"])
        self.assertEqual(shared["text"], row["text"] + " FR")

    def test_string_table_stale_identity_does_not_write(self):
        path = "content/dlc/zombiepack/zombiepack_standalone.strtbl"
        payload = server.string_table_payload("content", path)
        row = payload["rows"][0]
        project = Path(payload["table"]["projectPath"])
        with self.assertRaisesRegex(ValueError, "text changed"):
            server.save_string_table("content", path, [{
                "languageIndex": row["languageIndex"],
                "entryIndex": row["entryIndex"],
                "expectedHash": row["hash"],
                "expectedText": "stale text",
                "value": "changed",
            }])
        self.assertFalse(project.exists())

    def test_data_map_routes_supported_strings_and_keeps_ps3_duplicate_visible(self):
        payload = server.data_map_payload()
        rows = {row["filename"]: row for row in payload["rows"]}
        pc = rows[
            "game/content.rpf:/content/dlc/zombiepack/zombiepack_standalone.strtbl"
        ]
        ps3 = rows[
            "game/content.rpf:/content/dlc/zombiepack/zombiepack_standalone_ps3.strtbl"
        ]
        tuning = rows["game/tune_d11generic.rpf:/tune/stringtable/global.strtbl"]
        loot = rows[f"game/content.rpf:/{server.loot_script.ARCHIVE_PATH}"]
        self.assertEqual((pc["status"], pc["target"], pc["openable"]),
                         ("partial", "strings", True))
        self.assertEqual((tuning["status"], tuning["target"], tuning["openable"]),
                         ("partial", "strings", True))
        self.assertEqual((ps3["status"], ps3["target"], ps3["openable"]),
                         ("not-integrated", "", False))
        self.assertEqual((loot["status"], loot["target"], loot["openable"]),
                         ("partial", "loot", True))

    def test_rbf0_scalar_editor_is_in_place_and_data_map_gated(self):
        payload = server.rbf_scalars_payload()
        self.assertEqual(payload["counts"]["resources"], 1)
        self.assertEqual(payload["counts"]["scalars"], 3)
        row = next(item for item in payload["rows"] if item["path"].endswith("/Scale"))
        source = Path(row["sourcePath"])
        before = source.read_bytes()
        result = server.save_rbf_scalars(row["resourcePath"], [{
            "recordOffset": row["recordOffset"], "path": row["path"],
            "kind": row["kind"], "rawHex": row["rawHex"], "value": 2.5,
        }])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(source.read_bytes(), before)
        current = server.rbf_scalars_payload()
        saved = next(item for item in current["rows"] if item["id"] == row["id"])
        self.assertAlmostEqual(saved["value"], 2.5)
        vanilla = next(item for item in server.rbf_scalars_payload(True)["rows"] if item["id"] == row["id"])
        self.assertAlmostEqual(vanilla["value"], 1.0)

        pretend = server.PREPARED_ROOT / "tune/ai/not_really_rbf.tune"
        pretend.write_bytes(b"plain tuning text\n")
        rows = {item["filename"]: item for item in server.data_map_payload()["rows"]}
        supported = rows["game/tune_d11generic.rpf:/tune/ai/protected.tune"]
        unsupported = rows["game/tune_d11generic.rpf:/tune/ai/not_really_rbf.tune"]
        self.assertEqual((supported["status"], supported["target"], supported["openable"]),
                         ("partial", "rbf", True))
        self.assertEqual((unsupported["status"], unsupported["target"], unsupported["openable"]),
                         ("not-integrated", "", False))

    def test_data_map_never_promotes_unverified_research_rows(self):
        rows = server._normalize_data_map_rows([{
            "filename": "game/content.rpf:/content/unknown.bin",
            "status": "integrated",
            "target": "items",
            "notes": "Research inventory claimed this was editable.",
        }], interfaces={})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["filename"], "game/content.rpf:/content/unknown.bin")
        self.assertEqual(rows[0]["status"], "not-integrated")
        self.assertEqual(rows[0]["target"], "")
        self.assertFalse(rows[0]["openable"])

    def test_mission_identity_schema_and_reward_limits(self):
        for document in (None, [], {"schemaVersion": True},
                         {"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": {}},
                         *({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards",
                            "overrides": [{"id": i, "rewards": {"cash": 2}}]} for i in (True, "1", 1.2, 58))):
            with self.subTest(document=document), self.assertRaises(ValueError):
                mission_rewards.validate_override(document)
        for kind, amount in (("cash", -1), ("fame", True), ("honor", -1000000), ("cash", 1.2)):
            with self.subTest(kind=kind, amount=amount), self.assertRaises(ValueError):
                mission_rewards.validate_override({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards",
                    "overrides": [{"id": 2, "rewards": {kind: amount}}]})

    def test_mission_handoff_preserves_and_restores_exact_pretest_override(self):
        base = server.mission_test_plan()
        self.assertEqual(base["missionId"], 2)
        self.assertEqual(base["status"], "baseline")
        server.save_missions({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards",
            "overrides": [{"id": 5, "rewards": {"cash": 777}}, {"id": 2, "rewards": {"honor": 7}}]})
        custom = server.mission_test_plan()
        self.assertEqual(custom["status"], "custom")
        staged = server.stage_mission_test()["test"]
        self.assertEqual(staged["status"], "staged")
        self.assertEqual(staged["currentOverride"], {"id": 2, "rewards": {"cash": 123, "fame": 321, "honor": 222}})
        document = server._mission_override_document()
        self.assertIn({"id": 5, "rewards": {"cash": 777}}, document["overrides"])
        restored = server.restore_mission_test()["test"]
        self.assertEqual(restored["status"], "custom")
        document = server._mission_override_document()
        self.assertIn({"id": 5, "rewards": {"cash": 777}}, document["overrides"])
        self.assertIn({"id": 2, "rewards": {"honor": 7}}, document["overrides"])
        self.assertFalse(server.MISSION_TEST_STATE.exists())

    def test_mission_handoff_refuses_restore_after_mission2_changes(self):
        server.stage_mission_test()
        document = server._mission_override_document()
        rows = [row for row in document["overrides"] if row["id"] != 2]
        rows.append({"id": 2, "rewards": {"honor": 999}})
        server.save_missions({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": rows})
        plan = server.mission_test_plan()
        self.assertEqual(plan["status"], "conflict")
        with self.assertRaisesRegex(RuntimeError, "changed after"):
            server.restore_mission_test()
        self.assertEqual(server._mission_row(server._mission_override_document(), 2), {"id": 2, "rewards": {"honor": 999}})

    def test_mission_save_and_reset_leave_generated_table_unchanged(self):
        original = mission_rewards.GENERATED_FILE.read_bytes()
        doc = {"schemaVersion": 1, "contract": "LexerRDR.mission-rewards",
               "overrides": [{"id": 2, "rewards": {"cash": 321, "honor": -25}}]}
        self.assertEqual(server.save_missions(doc)["saved"], 2)
        row = next(r for r in server.missions_payload()["missions"] if r["id"] == 2)
        self.assertEqual(row["rewards"]["cash"], 321)
        doc["overrides"] = []
        server.save_missions(doc)
        row = next(r for r in server.missions_payload()["missions"] if r["id"] == 2)
        self.assertEqual(row["rewards"], row["baseRewards"])
        self.assertEqual(mission_rewards.GENERATED_FILE.read_bytes(), original)

    def test_http_rejects_malformed_json_and_indices(self):
        service = server.create_server(0)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{service.server_port}"
            for body in ('[]', '{"index":NaN}', '{"index":Infinity}',
                         '{"index":true,"source":"base","expectedName":"TEST_0","edits":[]}',
                         '{"index":0.5,"source":"base","expectedName":"TEST_0","edits":[]}'):
                request = urllib.request.Request(url + '/api/item/save', data=body.encode(),
                                                 headers={'Content-Type': 'application/json'})
                with self.subTest(body=body), self.assertRaises(urllib.error.HTTPError) as result:
                    urllib.request.urlopen(request, timeout=5)
                self.assertEqual(result.exception.code, 400)
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
