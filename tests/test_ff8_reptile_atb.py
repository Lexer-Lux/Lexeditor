from pathlib import Path
import tempfile
import unittest

from games.ff8 import reptile_atb


class ReptileAtbTests(unittest.TestCase):
    def test_missing_defaults_off_and_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            data = reptile_atb.load(Path(temp))
        self.assertEqual(data, {"schemaVersion": 1, "enabled": False, "enemyIds": []})

    def test_build_parse_sorts_and_deduplicates_enemy_ids(self):
        text = reptile_atb.build(enabled=True, reptile_enemy_ids=[44, 16, 44, 200])
        self.assertEqual(
            text,
            'schemaVersion = 1\nenabled = true\nenemyIds = "16,44,200"\n',
        )
        self.assertEqual(
            reptile_atb.parse(text),
            {"schemaVersion": 1, "enabled": True, "enemyIds": [16, 44, 200]},
        )

    def test_write_round_trip_is_project_metadata_not_enemy_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            enemy = root / "direct" / "battle" / "c0m016.dat"
            enemy.parent.mkdir(parents=True)
            enemy.write_bytes(b"enemy-bytes")
            target = reptile_atb.write(root, enabled=True, reptile_enemy_ids=[16])
            self.assertEqual(target, root.resolve() / "direct" / "lexeditor" / "reptile-atb.toml")
            self.assertEqual(enemy.read_bytes(), b"enemy-bytes")
            self.assertEqual(reptile_atb.load(root)["enemyIds"], [16])

    def test_invalid_or_unknown_configuration_fails_closed(self):
        invalid = [
            'schemaVersion = 1\nenabled = true\nenemyIds = "255"\n',
            'schemaVersion = 1\nenabled = yes\nenemyIds = "16"\n',
            'schemaVersion = 1\nenabled = true\nenemyIds = "16"\nextra = 1\n',
            'schemaVersion = 2\nenabled = true\nenemyIds = "16"\n',
            'schemaVersion = 1\nenabled = true\nenemyIds = "16,16x"\n',
        ]
        for text in invalid:
            with self.subTest(text=text):
                with self.assertRaises(reptile_atb.ReptileAtbError):
                    reptile_atb.parse(text)

    def test_fire_and_ice_multiply_cumulatively_per_move(self):
        self.assertAlmostEqual(reptile_atb.after_element(1.0, reptile_atb.ICE_ELEMENT), 0.92)
        self.assertAlmostEqual(reptile_atb.after_element(0.92, reptile_atb.ICE_ELEMENT), 0.92 ** 2)
        self.assertAlmostEqual(reptile_atb.after_element(1.0, reptile_atb.FIRE_ELEMENT), 1.08)
        self.assertAlmostEqual(reptile_atb.after_element(1.08, reptile_atb.FIRE_ELEMENT), 1.08 ** 2)
        self.assertAlmostEqual(
            reptile_atb.after_element(1.0, reptile_atb.FIRE_ELEMENT | reptile_atb.ICE_ELEMENT),
            1.08 * 0.92,
        )
        self.assertEqual(reptile_atb.after_element(0.77, 0x04), 0.77)


if __name__ == "__main__":
    unittest.main()
