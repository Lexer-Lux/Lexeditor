"""Saved native edits and added bands retain distinct game-data provenance."""
import os

from plugins.ds1 import native_rules
from test_ds1_band_composition import original
from test_ds1_native_property_release import project


def test_saved_native_edits_keep_original_values_and_clean_save_state(project):
    game,_library,mod,rules,_original = project
    assert rules.dirty_count == 0
    for rules in (rules,native_rules.NativeRules(game,mod,False)):
        row = rules.list_rows('misc')[0]
        assert row['modified'] and not row.get('created')
        field = rules.read_row(0)['fields'][0]
        assert field['value'] == 67 and field['vanilla'] == 45
        assert rules.dirty_count == 0
    rules.edit_row(0,'baseRecovery',45)
    assert not rules.list_rows('misc')[0]['modified']
    assert rules.dirty_count == 1
    rules.save()
    assert not native_rules.NativeRules(game,mod,False).list_rows('misc')[0]['modified']


def test_new_band_stays_added_after_save_reload_and_later_edits(project):
    game,_library,mod,rules,_original = project
    added = rules.band_action('add',1001,revision=rules.band_revision(),at=12.5)['id']
    assert added == 1005
    rules.save()
    for rules in (rules,native_rules.NativeRules(game,mod,False)):
        rows = {row['id']:row for row in rules.list_rows('encumbrance')}
        assert rows[added]['created'] and not rows[added]['modified']
        assert rows[1001]['modified'] and not rows[1001]['created']
        assert all(field['vanilla'] is None for field in rules.read_row(added)['fields'])
        assert rules.dirty_count == 0
    rules.edit_row(added,'recovery',125)
    assert rules.read_row(added)['created'] and not rules.read_row(added)['modified']
    assert rules.dirty_count == 1


def test_saved_native_provenance_uses_shared_icons_and_reference_controls(project):
    from playwright.sync_api import sync_playwright
    from plugins.ds1.plugin import DS1Session
    game,library,mod,rules,_original = project
    rules.band_action('add',1001,revision=rules.band_revision(),at=12.5)
    rules.save()
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(mod),
                     'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0',
                     'LEXEDITOR_DS1_MODS':str(library)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':900})
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("misc","misc","NativeRules:0")')
                page.locator('[data-field-key="baseRecovery"]').wait_for()
                row = page.locator('.lex-list-row[data-key="NativeRules:0"]')
                assert row.locator('[aria-label="Changed from vanilla"]').inner_text() == '📝'
                assert page.locator('.lex-source-control').count() > 0
                page.evaluate('navigate("misc","encumbrance","NativeRules:1005")')
                added = page.locator('.lex-list-row[data-key="NativeRules:1005"]')
                added.wait_for()
                assert added.locator('[aria-label="Created in this mod"]').inner_text() == '✒️'
                screenshot = os.environ.get('LEXEDITOR_NATIVE_PROVENANCE_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot)
            finally:
                browser.close()
