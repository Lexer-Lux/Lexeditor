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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.rdr import server, mission_rewards
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
