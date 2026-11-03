"""Real World HTTP saves from the shared Rules/Groups chance controls."""
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from plugins.ff8 import encounter_chances as chances
from test_ff8_encounter_chance_save import service
from ff8_encounter_tabs_browser_check import serve, formation
from tests.shared.paged_detail import reveal


def test_chance_drafts_header_save_reopen_and_default_restore(service):
    project, baseline, request = service
    posts = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def route_api(route, incoming):
            path = urlparse(incoming.url).path
            if incoming.method == 'POST':
                posts.append(path)
            if path in ('/api/world-map', '/api/world-map/save'):
                route.continue_()
            elif path == '/api/encounters':
                route.fulfill(json={'rows': [formation(identifier, {0: (0, 7)}) for identifier in range(10,38)]})
            else:
                serve(route, incoming)

        page.route('**/*', route_api)
        page.goto(request.base_url+'/editor.html')
        page.wait_for_function("() => typeof state !== 'undefined' && !state.booting")
        page.locator("nav button[data-tab='encounters']").click()
        assert not errors, errors
        assert page.locator('.ff8-encounter-tabs').count(), page.locator('#main').inner_text()
        groups = page.locator('.ff8-encounter-tabs [role=tab]').nth(1)
        rules = page.locator('.ff8-encounter-tabs [role=tab]').nth(2)
        formations = page.locator('.ff8-encounter-tabs [role=tab]').nth(0)
        groups.click()

        def chance(index):
            control = page.get_by_label(f'Group 0 slot {index+1} initial chance', exact=True)
            reveal(page, control)
            return control

        # Nested formation rows use the same percentage lane as record panes.
        for width in (1600, 1000, 1600):
            page.set_viewport_size({'width': width, 'height': 1000})
            control = chance(0)
            page.wait_for_timeout(250)
            geometry = control.evaluate('''input => {
              const field=input.closest('.lex-detail-field');
              const label=field.querySelector('.lex-detail-field-label');
              const range=document.createRange();range.selectNodeContents(label.firstElementChild);
              return {field:field.getBoundingClientRect().toJSON(),
                label:label.getBoundingClientRect().toJSON(),ink:range.getBoundingClientRect().toJSON()};
            }''')
            assert .07 <= geometry['label']['width']/geometry['field']['width'] <= .08, geometry
            assert geometry['ink']['right'] <= geometry['label']['right']+1, geometry
            assert geometry['ink']['bottom'] <= geometry['label']['bottom']+1, geometry

        save = page.locator('#global-save')
        initial = [value*100/256 for value in chances.DEFAULT_OUTCOMES]
        for index, expected in enumerate(initial):
            assert float(chance(index).input_value()) == expected
            assert chance(index).get_attribute('min') == '0'
            assert chance(index).get_attribute('max') == '100'
            assert chance(index).get_attribute('step') == '0.390625'
        chance(0).fill('1')
        page.wait_for_function('() => shell.history.canUndo')
        page.locator('#global-undo').click()
        assert float(chance(0).input_value()) == initial[0]
        assert page.evaluate('dirtyCount()') == 0
        page.locator('#global-redo').click()
        assert chance(0).input_value() == '1'
        assert page.evaluate('encounterChanceDraftCount()') == 1
        # Undo of a different slot must retain the first slot's invalid draft
        # even though history restoration replaces all world row objects.
        chance(1).fill('50')
        page.wait_for_function('() => shell.history.canUndo')
        page.locator('#global-undo').click()
        assert chance(0).input_value() == '1'
        assert float(chance(1).input_value()) == initial[1]
        page.locator('#global-redo').click()
        assert chance(0).input_value() == '1'
        assert float(chance(1).input_value()) == 50
        page.evaluate('discardAll()')
        assert float(chance(0).input_value()) == initial[0]
        assert page.evaluate('encounterChanceDraftCount()') == 0
        for value in ('', '-0.390625', '100.390625', '1'):
            chance(0).fill(value)
            assert not chance(0).evaluate('(input) => input.checkValidity()')
            assert page.evaluate('dirtyCount()') > 0
            assert page.evaluate('encounterChanceError(encounterGroupById(0))')
        # Invalid precision persists across navigation and blocks all writers.
        chance(0).fill('1')
        page.evaluate('state.data.encounters.rows[0].stageId+=1;shell.refresh()')
        formations.click()
        save.click()
        page.get_by_role('button', name=re.compile('confirm and close', re.I)).click()
        assert not posts and not (project/chances.HEXT_RELATIVE).exists()
        page.evaluate('state.data.encounters.rows[0].stageId=state.base.encounters[0].stageId;shell.refresh()')
        groups.click()
        assert chance(0).input_value() == '1'
        chance(0).fill('50')
        formations.click()
        save.click()
        page.get_by_role('button', name=re.compile('confirm and close', re.I)).click()
        assert not posts  # A hidden group's incomplete total still blocks Save.
        groups.click()
        for index, value in enumerate([50, 50]+[0]*6):
            chance(index).fill(str(value))
        assert page.evaluate("encounterChanceError(encounterGroupById(0))") == ''
        assert page.locator('.ff8-encounter-initial-chances .lex-column-list-row [data-column-key="chance"]').all_text_contents() == ['50%', '50%']+['0%']*6
        with page.expect_response('**/api/world-map/save') as result:
            save.click()
        assert result.value.status == 200
        page.wait_for_function('() => dirtyCount() === 0')
        assert posts == ['/api/world-map/save']
        assert request()[1]['groups'][0]['initialOutcomes'] == [128,128]+[0]*6
        assert (project/chances.HEXT_RELATIVE).read_bytes()
        page.reload()
        page.wait_for_function("() => typeof state !== 'undefined' && !state.booting")
        page.locator("nav button[data-tab='encounters']").click()
        groups.click()
        for index, expected in enumerate([50,50]+[0]*6):
            assert float(chance(index).input_value()) == expected
        for index, value in enumerate([100]+[0]*7):
            chance(index).fill(str(value))
        with page.expect_response('**/api/world-map/save') as result:
            save.click()
        assert result.value.status == 200
        page.wait_for_function('() => dirtyCount() === 0')
        assert request()[1]['groups'][0]['initialOutcomes'] == [256]+[0]*7
        # The very same controls appear in the Rules group's preview.
        rules.click()
        assert float(chance(0).input_value()) == 100
        for index, value in enumerate(initial):
            chance(index).fill(str(value))
        with page.expect_response('**/api/world-map/save') as result:
            save.click()
        assert result.value.status == 200
        page.wait_for_function('() => dirtyCount() === 0')
        assert (project/'direct/world/dat/wmsetus.obj').read_bytes() == baseline.read_bytes()
        assert (project/chances.HEXT_RELATIVE).read_bytes() == b''
        # Inspect the rendered control using the standard detail field sizing.
        reveal(page, chance(0))
        screenshot = Path(tempfile.gettempdir())/'lexeditor-dev/ff8-encounters/ff8-chance-controls.png'
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot))
        page.evaluate("state.activeSource='vanilla';render()")
        controls=page.locator('input[aria-label^="Group 0 slot "][aria-label$="initial chance"]')
        assert controls.count() == 8
        assert controls.evaluate_all('(inputs) => inputs.every(input => input.disabled)')
        assert not errors, errors
        browser.close()
