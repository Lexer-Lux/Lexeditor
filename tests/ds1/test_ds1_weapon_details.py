"""Synthetic PARAM tests; no retail bytes, guessed movesets or menu claims."""
import math
import struct
from types import SimpleNamespace
import unittest

from plugins.ds1.weapon_details import DetailsError, WeaponDetails, weapon_poise_damage


# Independent literal fixture layouts: do not generate offsets from production.
_TYPES = {
    "EquipParamWeapon": ("EQUIP_PARAM_WEAPON_ST", 272, 1),
    "BehaviorParam_PC": ("BEHAVIOR_PARAM_ST", 32, 2),
    "AtkParam_Pc": ("ATK_PARAM_ST", 128, 1),
    "ReinforceParamWeapon": ("REINFORCE_PARAM_WEAPON_ST", 96, 1),
}


def _param(table, rows):
    name, size, version = _TYPES[table]
    start = 48 + 12 * len(rows)
    strings = start + size * len(rows)
    out = bytearray(strings + 1)
    struct.pack_into("<I", out, 0, strings)
    struct.pack_into("<hH", out, 8, version, len(rows))
    out[12:12 + len(name)] = name.encode("ascii")
    out[44:48] = b"\0\x02\0\0"
    for index, (row_id, values) in enumerate(rows):
        at = start + size * index
        struct.pack_into("<iII", out, 48 + 12 * index, row_id, at, 0)
        out[at:at + size] = bytes([0xA5]) * size
        for offset, code, value in values:
            struct.pack_into("<" + code, out, at + offset, value)
    return bytes(out)


def _weapon(row_id=100000, base=35, variation=2000, reinforcement=700):
    return row_id, [(0, "i", variation), (0xCE, "H", base),
                    (0xD6, "h", reinforcement),
                    (0xCC, "H", 999), (0xD0, "H", 888)]


def _behavior(row_id=42, variation=2000, judge=777, kind=0, ref=123, stamina=20):
    return row_id, [(0, "i", variation), (4, "i", judge), (9, "B", kind),
                    (12, "i", ref), (20, "i", stamina)]


def _attack(row_id=123, correction=150, fixed=900):
    return row_id, [(0x4E, "H", correction), (0x5E, "H", fixed),
                    (0x58, "H", 777)]


def _fixtures(weapons=None, behaviors=None, attacks=None, reinforces=None):
    return {
        "EquipParamWeapon": _param("EquipParamWeapon",
            [_weapon(), _weapon(200000, base=20, variation=3000)] if weapons is None else weapons),
        "BehaviorParam_PC": _param("BehaviorParam_PC",
            [_behavior(), _behavior(99, judge=123, stamina=37)] if behaviors is None else behaviors),
        "AtkParam_Pc": _param("AtkParam_Pc", [_attack()] if attacks is None else attacks),
        "ReinforceParamWeapon": _param("ReinforceParamWeapon",
            [(700, [(0x14, "f", 1.0)]), (705, [(0x14, "f", 2.0)])]
            if reinforces is None else reinforces),
    }


class WeaponDetailTests(unittest.TestCase):
    def test_correct_fields_not_wielder_poise_or_shield_stamina_damage(self):
        view = WeaponDetails(_fixtures())
        self.assertEqual(view.weapon(100000)["basePoiseDamage"], 35)
        action = view.action(100000, 42)
        self.assertEqual(action["staminaCost"], 20)
        self.assertEqual(action["poiseDamage"], 52.5)
        self.assertNotEqual(action["staminaCost"], 999)

    def test_action_costs_are_distinct_not_one_weapon_constant(self):
        view = WeaponDetails(_fixtures())
        self.assertEqual([view.action(100000, row)["staminaCost"] for row in (42, 99)], [20, 37])
        self.assertNotIn("staminaCost", view.weapon(100000))

    def test_no_r1_guess_from_id_order_or_judge(self):
        view = WeaponDetails(_fixtures())
        self.assertEqual(view.weapon(100000)["behaviorIds"], [42, 99])
        action = view.action(100000, 42)
        self.assertEqual(action["behaviorJudgeId"], 777)
        self.assertNotIn("name", action)

    def test_variation_association_is_required(self):
        with self.assertRaisesRegex(DetailsError, "associated"):
            WeaponDetails(_fixtures()).action(200000, 42)

    def test_upgrade_id_normalization_and_reinforcement(self):
        view = WeaponDetails(_fixtures())
        self.assertEqual(view.weapon(100005)["weaponRowId"], 100000)
        self.assertEqual(view.weapon(100005)["reinforcementId"], 705)
        self.assertEqual(view.action(100005, 42)["poiseDamage"], 105)

    def test_low_two_digit_row_is_not_a_weapon_override(self):
        params = _fixtures(weapons=[_weapon(), _weapon(100005, base=999)])
        self.assertEqual(WeaponDetails(params).action(100005, 42)["poiseDamage"], 105)

    def test_missing_reinforcement_uses_native_identity_fallback(self):
        view = WeaponDetails(_fixtures(reinforces=[]))
        self.assertTrue(view.weapon(100005)["reinforcementFallback"])
        self.assertEqual(view.action(100005, 42)["poiseDamage"], 52.5)

    def test_negative_reinforcement_row_is_not_used(self):
        view = WeaponDetails(_fixtures(weapons=[_weapon(reinforcement=-1)],
            reinforces=[(-1, [(0x14, "f", 9.0)])]))
        self.assertTrue(view.weapon(100000)["reinforcementFallback"])
        self.assertEqual(view.action(100000, 42)["poiseDamage"], 52.5)

    def test_event_multiplier_is_explicit_and_precedes_correction(self):
        view = WeaponDetails(_fixtures())
        self.assertEqual(view.action(100000, 42, event_multiplier=0.5)["poiseDamage"], 26.25)

    def test_fixed_mode_is_not_added_to_weapon_mode(self):
        view = WeaponDetails(_fixtures())
        self.assertEqual(view.action(100000, 42)["poiseDamage"], 52.5)
        self.assertEqual(view.action(100000, 42, poise_mode="fixed",
                                     event_multiplier=9)["poiseDamage"], 900)

    def test_zero_values_are_real_values(self):
        view = WeaponDetails(_fixtures(behaviors=[_behavior(stamina=0)],
            attacks=[_attack(correction=0, fixed=0)]))
        self.assertEqual(view.action(100000, 42)["staminaCost"], 0)
        self.assertEqual(view.action(100000, 42)["poiseDamage"], 0)

    def test_negative_stamina_is_unavailable_not_clamped(self):
        result = WeaponDetails(_fixtures(behaviors=[_behavior(stamina=-3)])).action(100000, 42)
        self.assertIsNone(result["staminaCost"])
        self.assertEqual(result["poiseDamage"], 52.5)
        self.assertTrue(result["issues"])

    def test_missing_player_attack_is_unavailable_not_zero(self):
        view = WeaponDetails(_fixtures(attacks=[]))
        result = view.action(100000, 42)
        self.assertIsNone(result["poiseDamage"])
        self.assertEqual(result["staminaCost"], 20)
        self.assertTrue(result["issues"])

    def test_npc_attack_with_same_id_is_never_used(self):
        params = _fixtures(attacks=[])
        params["AtkParam_Npc"] = _param("AtkParam_Pc", [_attack()])
        self.assertIsNone(WeaponDetails(params).action(100000, 42)["poiseDamage"])

    def test_negative_attack_id_is_never_resolved(self):
        view = WeaponDetails(_fixtures(behaviors=[_behavior(ref=-1)], attacks=[_attack(-1)]))
        self.assertIsNone(view.action(100000, 42)["poiseDamage"])

    def test_projectile_effect_and_unknown_references_are_not_direct_hits(self):
        for kind in (1, 2, 255):
            with self.subTest(kind=kind):
                view = WeaponDetails(_fixtures(behaviors=[_behavior(kind=kind)]))
                result = view.action(100000, 42)
                self.assertIsNone(result["poiseDamage"])
                self.assertEqual(result["staminaCost"], 20)

    def test_unknown_weapon_and_behavior_raise(self):
        view = WeaponDetails(_fixtures())
        for call in (lambda: view.weapon(900000), lambda: view.action(100000, 333)):
            with self.assertRaises(DetailsError):
                call()

    def test_invalid_user_identifiers_and_modes(self):
        view = WeaponDetails(_fixtures())
        for invalid in (-1, True, 1.5, "100000", 2**31):
            with self.subTest(invalid=invalid), self.assertRaises(DetailsError):
                view.weapon(invalid)
            with self.subTest(behavior=invalid), self.assertRaises(DetailsError):
                view.action(100000, invalid)
        with self.assertRaises(DetailsError):
            view.action(100000, 42, poise_mode="auto")

    def test_missing_tables_are_explicit_and_do_not_fall_back_to_npc(self):
        params = _fixtures()
        params["BehaviorParam"] = params.pop("BehaviorParam_PC")
        with self.assertRaisesRegex(DetailsError, "BehaviorParam_PC"):
            WeaponDetails(params)

    def test_empty_behavior_table_has_no_synthetic_action(self):
        self.assertEqual(WeaponDetails(_fixtures(behaviors=[])).weapon(100000)["behaviorIds"], [])

    def test_input_bytes_and_returned_lists_cannot_mutate_snapshot(self):
        params = {key: bytearray(value) for key, value in _fixtures().items()}
        originals = {key: bytes(value) for key, value in params.items()}
        view = WeaponDetails(params)
        self.assertEqual(params, originals)
        for value in params.values():
            value[:] = bytes(len(value))
        result = view.weapon(100000)
        result["behaviorIds"].clear()
        action = view.action(100000, 42)
        action["issues"].append("changed by caller")
        self.assertEqual(view.weapon(100000)["behaviorIds"], [42, 99])
        self.assertEqual(view.action(100000, 42)["issues"], [])

    def test_document_snapshot_reads_pending_bytes(self):
        params = _fixtures(weapons=[_weapon(base=17)])
        plain = bytearray()
        members = {}
        for table, payload in params.items():
            members[table + ".param"] = SimpleNamespace(offset=len(plain), size=len(payload))
            plain.extend(payload)
        document = SimpleNamespace(plain=plain, members=members)
        view = WeaponDetails.from_document(document)
        self.assertEqual(view.weapon(100000)["basePoiseDamage"], 17)
        document.plain[:] = bytes(len(plain))
        self.assertEqual(view.weapon(100000)["basePoiseDamage"], 17)

    def test_wrong_type_version_endian_and_flags_are_rejected(self):
        for offset, code, value in ((8, "h", 9), (12, "B", ord("Z")),
                                    (44, "B", 255), (45, "B", 4), (46, "B", 1)):
            with self.subTest(offset=offset):
                params = _fixtures()
                blob = bytearray(params["BehaviorParam_PC"])
                struct.pack_into("<" + code, blob, offset, value)
                params["BehaviorParam_PC"] = bytes(blob)
                with self.assertRaises(ValueError):
                    WeaponDetails(params)

    def test_duplicate_ids_and_overlapping_rows_are_rejected(self):
        for at, value in ((60, 42), (64, 72)):
            params = _fixtures()
            blob = bytearray(params["BehaviorParam_PC"])
            struct.pack_into("<I", blob, at, value)
            params["BehaviorParam_PC"] = bytes(blob)
            with self.subTest(at=at), self.assertRaises(DetailsError):
                WeaponDetails(params)

    def test_row_in_directory_or_outside_strings_is_rejected(self):
        for at, value in ((52, 48), (0, 80)):
            params = _fixtures()
            blob = bytearray(params["BehaviorParam_PC"])
            struct.pack_into("<I", blob, at, value)
            params["BehaviorParam_PC"] = bytes(blob)
            with self.subTest(at=at), self.assertRaises(DetailsError):
                WeaponDetails(params)

    def test_nonfinite_or_negative_reinforcement_is_rejected(self):
        for rate in (math.nan, math.inf, -1.0):
            view = WeaponDetails(_fixtures(reinforces=[(700, [(0x14, "f", rate)])]))
            with self.subTest(rate=rate), self.assertRaises(DetailsError):
                view.action(100000, 42)

    def test_poisoned_multiplier_and_overflow_are_rejected(self):
        for rate in (math.nan, math.inf, -1, True, "1", 10**500, 3.5e38):
            with self.subTest(rate=rate), self.assertRaises(DetailsError):
                weapon_poise_damage(35, rate, 150)
        with self.assertRaises(DetailsError):
            weapon_poise_damage(65535, 3e38, 65535)

    def test_float32_percent_operation_order(self):
        f32 = lambda v: struct.unpack("<f", struct.pack("<f", v))[0]
        for base, rate, correction, event in ((35, 1, 150, 1), (27, 1.23, 125, 0.7),
                                               (65535, 1, 65535, 0.999)):
            expected = f32(f32(f32(float(base) * f32(rate)) * f32(event))
                           * f32(float(correction) * f32(0.01)))
            self.assertEqual(weapon_poise_damage(base, rate, correction, event), expected)


if __name__ == "__main__":
    unittest.main()
