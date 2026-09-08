"""Rendered shared-UI coverage for the FF7 executable-backed editor surface."""
from __future__ import annotations

import unittest

import verify_ff7_rendered_neutral  # applies the real shared/neutral page harness
import verify_ff7_rendered as target


def test_executable_surface_navigation_save_and_reopen(self):
    self.install(); self.open()

    # New executable datasets are reachable through the normal related-tab UI.
    for parent, tab_name, expected in (
        ("commands", "Limit breaks", "limitBreaks"),
        ("items", "Name sort", "itemSortOrder"),
        ("materia", "Equip effects", "materiaEquipEffects"),
        ("materia", "Menu priority", "materiaPriority"),
        ("materia", "Master sale price", "apMultiplier"),
        ("texts", "Executable text", "exeText"),
    ):
        self.navigate(parent)
        tab = self.page.get_by_role("tab", name=tab_name, exact=True)
        self.assertEqual(tab.count(), 1, (parent, tab_name))
        tab.click()
        self.assertEqual(self.page.evaluate("state.tab"), expected)

    # Exercise actual shared controls and the real save path for every newly
    # exposed executable family. Installed source bytes must remain untouched.
    edits = (
        ("limitBreaks", "attackPower", "77", 77),
        ("materiaEquipEffects", "strength", "7", 7),
        ("itemSortOrder", "position", "7", 7),
        ("materiaPriority", "priority", "1", 1),
        ("audioMixing", "volume", "123", 123),
        ("apMultiplier", "multiplier", "3", 3),
        ("exeText", "text", "Rendered executable text", "Rendered executable text"),
    )
    for group, key, value, expected in edits:
        with self.subTest(group=group):
            control = self.control(group, key)
            self.assertTrue(control.is_editable())
            control.fill(value)
            self.save()
            selected = self.page.evaluate("g=>state.selected[g]", group)
            status, data = self.backend.request("/api/data")
            self.assertEqual(status, 200)
            row = next(row for row in data["records"][group] if row["id"] == selected)
            self.assertEqual(row["values"][key], expected)

    self.originals_unchanged()
    self.open()
    for group, key, _value, expected in edits:
        with self.subTest(reopen=group):
            control = self.control(group, key)
            self.assertEqual(control.input_value(), str(expected))
    self.originals_unchanged()


target.RenderedTests.test_executable_surface_navigation_save_and_reopen = test_executable_surface_navigation_save_and_reopen

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2,
                  defaultTest="RenderedTests.test_executable_surface_navigation_save_and_reopen")
