"""GF Acquisition Rework logic tests. No game install required."""
import unittest

from . import gf_acquisition_rework as m


class AcquisitionMapTests(unittest.TestCase):
    def test_six_drawable_gfs_with_distinct_primary_and_recovery(self):
        self.assertEqual(len(m.DRAWN_GFS), 6)
        for gf in m.DRAWN_GFS:
            self.assertTrue(m.PRIMARY_VICTORY[gf])
            self.assertTrue(m.RECOVERY_VICTORY[gf])
            self.assertNotEqual(m.PRIMARY_VICTORY[gf], m.RECOVERY_VICTORY[gf])

    def test_approved_primary_and_recovery_pairs(self):
        self.assertEqual(m.PRIMARY_VICTORY["Siren"], "Elvoret")
        self.assertEqual(m.RECOVERY_VICTORY["Siren"], "Tri-Point")
        self.assertEqual(m.PRIMARY_VICTORY["Carbuncle"], "Iguion")
        self.assertEqual(m.RECOVERY_VICTORY["Carbuncle"], "Krysta")
        self.assertEqual(m.PRIMARY_VICTORY["Leviathan"], "NORG")
        self.assertEqual(m.RECOVERY_VICTORY["Leviathan"], "Trauma")
        self.assertEqual(m.PRIMARY_VICTORY["Pandemona"], "Fujin")
        self.assertEqual(m.RECOVERY_VICTORY["Pandemona"], "Red Giant")
        self.assertEqual(m.PRIMARY_VICTORY["Alexander"], "Edea")
        self.assertEqual(m.RECOVERY_VICTORY["Alexander"], "Catoblepas")
        self.assertEqual(m.PRIMARY_VICTORY["Eden"], "Ultima Weapon")
        self.assertEqual(m.RECOVERY_VICTORY["Eden"], "Tiamat")

    def test_unchanged_gfs_are_never_awarded(self):
        for gf in m.UNCHANGED_GFS:
            self.assertNotIn(gf, m.DRAWN_GFS)
        self.assertEqual(m.awards_for_victory("Elvoret", list(m.UNCHANGED_GFS)), ["Siren"])


class AwardTests(unittest.TestCase):
    def test_primary_victory_awards_when_missing(self):
        self.assertEqual(m.awards_for_victory("Elvoret", []), ["Siren"])
        self.assertEqual(m.awards_for_victory("NORG", []), ["Leviathan"])

    def test_recovery_victory_awards_when_still_missing(self):
        self.assertEqual(m.awards_for_victory("Tri-Point", []), ["Siren"])
        self.assertEqual(m.awards_for_victory("Tiamat", ["Siren"]), ["Eden"])

    def test_owned_gf_is_never_reawarded(self):
        self.assertEqual(m.awards_for_victory("Elvoret", ["Siren"]), [])
        self.assertEqual(
            m.apply_victory(["Siren"], "Elvoret").count("Siren"), 1)

    def test_unknown_boss_awards_nothing(self):
        self.assertEqual(m.awards_for_victory("Somewhere Else", []), [])

    def test_bad_inputs_raise(self):
        with self.assertRaises(ValueError):
            m.awards_for_victory("", [])
        with self.assertRaises(ValueError):
            m.awards_for_victory("Elvoret", ["Not A GF"])
        with self.assertRaises(ValueError):
            m.awards_for_victory("Elvoret", "Siren")

    def test_apply_victory_appends_and_never_removes(self):
        owned = ["Quezacotl", "Shiva"]
        updated = m.apply_victory(owned, "Elvoret")
        self.assertEqual(updated, ["Quezacotl", "Shiva", "Siren"])
        # Disabling later keeps legitimately acquired GFs: awards only add.
        self.assertEqual(
            m.apply_victory(["Siren"], "Elvoret"), ["Siren"])


class DrawFilterTests(unittest.TestCase):
    def test_gf_entries_suppressed_spells_kept_in_order(self):
        entries = [
            {"kind": "spell", "id": "Fire"},
            {"kind": "gf", "id": "Siren"},
            {"kind": "spell", "id": "Cure"},
        ]
        kept = m.filter_draw_entries(entries)
        self.assertEqual([entry["id"] for entry in kept], ["Fire", "Cure"])

    def test_unknown_kind_and_malformed_entries_raise(self):
        with self.assertRaises(ValueError):
            m.filter_draw_entries([{"kind": "item", "id": "Potion"}])
        with self.assertRaises(ValueError):
            m.filter_draw_entries([{"kind": "spell"}])
        with self.assertRaises(ValueError):
            m.filter_draw_entries("Fire")


class GateTests(unittest.TestCase):
    def test_activation_fails_closed(self):
        self.assertFalse(m.GF_ACQUISITION_AVAILABLE)
        self.assertEqual(m.requirement_errors(enabled=False), [])
        self.assertEqual(
            m.requirement_errors(enabled=True), [m.GF_ACQUISITION_BLOCKER])
        with self.assertRaises(ValueError):
            m.build_hext(True)
        self.assertEqual(m.build_hext(False), "")
        with self.assertRaises(ValueError):
            m.requirement_errors(enabled="yes")


if __name__ == "__main__":
    unittest.main()
