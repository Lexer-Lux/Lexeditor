"""The Mob lists sit under a pager that pages and searches.

The no-clipped-text sweep flags a record list with no pager above it as
table-without-pager. Both Mobs views render through the shared paged
list-detail with the filter on the pager bar, so the bar is there even
when one page holds every row, and page turns reach the plugin.
"""
from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document

MOBS = {
    "combat": {"available": True, "records": [
        {"section": "Profiles", "name": "GANG_A", "group": "humans", "fields": [
            {"field": "WeaponAccuracy", "kind": "float", "path": [0, 0], "value": "0.5"},
            {"field": "CombatAbility", "kind": "string", "path": [0, 1], "value": "AVERAGE"},
        ]},
        {"section": "Profiles", "name": "GANG_B", "group": "humans", "fields": [
            {"field": "WeaponAccuracy", "kind": "float", "path": [1, 0], "value": "0.7"},
            {"field": "CombatAbility", "kind": "string", "path": [1, 1], "value": "AVERAGE"},
        ]},
    ]},
    "health": {"available": True, "records": []},
}

MODELS = {"probeAvailable": True, "probedCount": 1, "models": [
    {"model": "U_M_M_GANG_01", "observedHealth": 200, "group": "gang", "candidates": []},
]}

PAGER_ABOVE = """(label) => {
  const list = document.querySelector(`.lex-column-list[aria-label="${label}"]`);
  for (let node = list.parentElement; node && node !== document.body; node = node.parentElement) {
    if (node.querySelector(':scope .lex-pager')) return true;
  }
  return false;
}"""


def open_mobs(page):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", lambda route: route.abort())
    page.set_content(document().replace(
        "<head>", '<head><base href="https://lexeditor.test/">', 1))
    page.evaluate("LexeditorUI.finishPluginLoading()")
    page.evaluate("mobs => { window.__responses['/api/mobs'] = mobs; }", MOBS)
    page.evaluate("models => { window.__responses['/api/mob-models'] = models; }", MODELS)
    page.evaluate("navigate('mobs')")
    return errors


def test_mob_archetypes_have_a_pager_that_searches():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = open_mobs(page)
        expect(page.locator('.lex-column-list[aria-label="Mob archetypes"]')).to_have_count(1)
        assert page.evaluate(PAGER_ABOVE, "Mob archetypes")
        rows = page.locator('.lex-column-list[aria-label="Mob archetypes"] .lex-column-list-row')
        expect(rows).to_have_count(2)
        page.locator(".lex-pager-search input").fill("GANG_B")
        expect(rows).to_have_count(1)
        assert not errors, errors
        browser.close()


def test_observed_models_have_a_pager():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = open_mobs(page)
        page.get_by_role("tab", name="Observed Models").click()
        expect(page.locator('.lex-column-list[aria-label="Mob models"]')).to_have_count(1)
        assert page.evaluate(PAGER_ABOVE, "Mob models")
        assert not errors, errors
        browser.close()
