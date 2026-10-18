"""Tweak panels: a mod with nothing to change has no panel.

The Mods tab renders a SETTINGS section whenever a tweak mod (or bundle)
yields panels, so an empty schema must yield none - otherwise the section
header sits over blank space.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401


def test_fields_only_skips_a_mod_with_an_empty_schema(page):
    framework(page)
    count = page.evaluate("""() => LexeditorUI.tweakModPanels({fieldsOnly: true,
      rows: [{id: 'plain', name: 'Plain', enabled: true,
        schema: {fields: []}, values: {}}]}).panels.length""")
    assert count == 0


def test_fields_only_keeps_errors_blockers_and_visible_fields(page):
    framework(page)
    count = page.evaluate("""() => LexeditorUI.tweakModPanels({fieldsOnly: true, rows: [
      {id: 'broken', name: 'Broken', enabled: true, error: 'Schema failed to load',
        schema: {fields: []}, values: {}},
      {id: 'blocked', name: 'Blocked', enabled: true, schema: {blocker: 'Needs the game'}, values: {}},
      {id: 'knobs', name: 'Knobs', enabled: false,
        schema: {fields: [{key: 'size', label: 'Size', type: 'number', min: 1, max: 9}]},
        values: {size: 3}}]}).panels.length""")
    assert count == 3


def test_tweaks_page_still_hides_switched_off_mods(page):
    framework(page)
    count = page.evaluate("""() => LexeditorUI.tweakModPanels({rows: [
      {id: 'off', name: 'Off', enabled: false,
        schema: {fields: [{key: 'size', label: 'Size', type: 'number', min: 1, max: 9}]},
        values: {size: 3}}]}).panels.length""")
    assert count == 0
