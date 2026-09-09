from __future__ import annotations

import unittest

from games.chrono_trigger.field_semantics import command_semantics, decorate_event


LABELS = {
    "sceneNames": ["", "Millennial Fair", "Guardia Forest"],
    "itemNames": ["Wood Sword", "Bronze Bow", "Tonic"],
    "playerNames": ["Crono", "Marle", "Lucca"],
    "languages": {"scenes": "en", "items": "en", "players": "en"},
}


def cmd(opcode: int, args: bytes):
    return {"opcode": opcode, "argumentsHex": args.hex(" ").upper()}


class FieldSemanticTests(unittest.TestCase):
    def test_change_location_gets_scene_name_and_coordinates(self):
        semantic = command_semantics(cmd(0xDC, b"\x02\x00\x03\x10\x20"), LABELS)
        self.assertEqual(semantic["sceneId"], 2)
        self.assertEqual(semantic["sceneName"], "Guardia Forest")
        self.assertIn("(16, 32)", semantic["summary"])

    def test_item_check_uses_localized_name(self):
        semantic = command_semantics(cmd(0xC9, b"\x02\x00\x08"), LABELS)
        self.assertEqual(semantic["itemId"], 2)
        self.assertEqual(semantic["itemName"], "Tonic")
        self.assertIn("Tonic", semantic["summary"])
        self.assertEqual(semantic["jumpOffset"], 8)

    def test_pc_and_text_commands_are_annotated(self):
        self.assertEqual(command_semantics(cmd(0x81, b"\x01"), LABELS)["summary"], "Marle (1)")
        self.assertEqual(command_semantics(cmd(0xBB, b"\x34\x12"), LABELS)["stringIndex"], 0x1234)
        self.assertEqual(command_semantics(cmd(0xB8, b"\x07"), LABELS)["messageTable"], 7)

    def test_enemy_music_and_sound_have_safe_ids(self):
        enemy = command_semantics(cmd(0x83, b"\x34\x12\x85"), LABELS)
        self.assertEqual(enemy["enemyId"], 0x1234)
        self.assertEqual(enemy["slot"], 5)
        self.assertTrue(enemy["static"])
        self.assertEqual(command_semantics(cmd(0xEA, b"\x09"), LABELS)["musicId"], 9)
        self.assertEqual(command_semantics(cmd(0xE8, b"\x0A"), LABELS)["soundId"], 10)

    def test_gold_commands_decode_little_endian_amounts(self):
        check = command_semantics(cmd(0xCC, b"\x88\x13\x09"), LABELS)
        self.assertEqual(check["gold"], 5000)
        self.assertEqual(check["jumpOffset"], 9)
        self.assertIn("5000 G", check["summary"])
        add = command_semantics(cmd(0xCD, b"\xF4\x01"), LABELS)
        remove = command_semantics(cmd(0xCE, b"\x2C\x01"), LABELS)
        self.assertEqual(add, {"summary": "Add 500 G", "gold": 500, "operation": "add"})
        self.assertEqual(remove, {"summary": "Remove 300 G", "gold": 300, "operation": "remove"})

    def test_battle_flags_are_named_without_hiding_unknown_bits(self):
        semantic = command_semantics(cmd(0xD8, b"\xD0\xE1"), LABELS)
        self.assertEqual(semantic["flags1"], 0xD0)
        self.assertEqual(semantic["flags2"], 0xE1)
        self.assertIn("static enemies", semantic["enabledFlags"])
        self.assertIn("no run", semantic["enabledFlags"])
        self.assertIn("unknown 2:01", semantic["enabledFlags"])
        self.assertIn("no game over", semantic["enabledFlags"])
        self.assertIn("map music", semantic["enabledFlags"])
        self.assertIn("regroup", semantic["enabledFlags"])

    def test_unknown_semantics_do_not_invent_meaning(self):
        self.assertIsNone(command_semantics(cmd(0x4E, b"\x00\x20\x02\x00"), LABELS))

    def test_decorates_commands_in_place(self):
        payload = {"objects": [{"functions": [{"commands": [cmd(0x81, b"\x00")]}]}]}
        result = decorate_event(payload, LABELS)
        command = result["objects"][0]["functions"][0]["commands"][0]
        self.assertEqual(command["semantic"]["playerId"], 0)
        self.assertEqual(result["labelLanguages"]["players"], "en")


if __name__ == "__main__":
    unittest.main()
