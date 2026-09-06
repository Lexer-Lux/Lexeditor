"""Exercise the complete FF8 editor with synthetic data, not an installed game.

Runs the real shell, Enemies page, Searcher, reference controls and saveAll.
Only startup/network and images are supplied by the fixture. Serialized table
edits are applied by the production binary writer and reloaded by its reader.
Requires Pillow, fonttools, playwright and Chromium (or --browser PATH).
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import enemy_tables, formats
from PIL import Image

DATASETS = ('cards items menuItems shops weapons magic gfs characters abilityJunction '
            'abilityCommand abilityStat abilityCharacter abilityParty abilityGf '
            'abilityMenu text enemies enemyTables enemyAi enemyBattleText refine '
            'encounters world fields').split()


def fixture() -> tuple[dict, bytearray]:
    raw = bytearray(0x200)
    for offsets in enemy_tables.PAIR_OFFSETS.values():
        for offset in offsets.values():
            for slot in range(4):
                raw[offset + slot*2:offset + slot*2 + 2] = bytes((slot+1, slot+2))
    raw[0x160:0x168] = bytes([80, 100, 90, 80, 80, 80, 80, 80])
    raw[0x168:0x17C] = bytes([100, 255] + [100]*18)
    raw[0xF8:0xFB] = bytes((0, 1, 2))
    choices = enemy_tables.choices(ROOT/'games/ff8/schema', formats.MAGIC, formats.ITEMS)
    fields = [dict(field=f['name'], label=f['label'], control=f.get('control', 'integer'),
                   value=False if f.get('control') == 'boolean' else 20,
                   minimum=f.get('minimum', 0), maximum=f.get('maximum', 255),
                   group=f['group'], help=f.get('help', '')) for f in formats.ENEMY_FIELDS]
    data = {key: {'rows': []} for key in DATASETS}
    data.update(
        enemyTables={'rows': [dict(id=1, name='Funguar', tables=enemy_tables.read_tables(raw, 0))],
                     'choices': choices},
        enemies={'rows': [dict(id=1, name='Funguar', filename='c0m001.dat', available=True,
                              scanDescription='A forest mushroom.', fields=fields)]},
        enemyBattleText={'rows': [dict(id=1, available=True, lines=[dict(id=0, text='Dialogue.')])]},
        enemyAi={'rows': [dict(id=1, available=True, scripts=[])], 'opcodes': []},
        cards={'rows': [dict(id=c['id'], name=c['name'], top=1, left=2, right=3,
                             bottom=4, element=0, power=1)
                        for c in choices['cards'] if c['id'] < 110],
               'elements': [{'id': 0, 'name': 'None'}]}, init={}, settings={})
    data['magic']['rows'] = [dict(id=i, name=f'Magic {i}', fields=[], description='Test spell')
                             for i in range(8)]
    data['items']['rows'] = [dict(id=i, name=f'Item {i}', fields=[], description='Test item')
                             for i in range(8)]
    return data, raw


class Backend:
    def __init__(self):
        self.data, self.raw = fixture()
        self.vanilla = deepcopy(self.data)
        self.requests: list[tuple[str, dict]] = []

    def fetch(self, url: str, options: dict) -> dict:
        import json
        path = urlparse(url).path
        query = parse_qs(urlparse(url).query)
        if options.get('method') == 'POST':
            body = json.loads(options.get('body') or '{}')
            self.requests.append((path, body))
            if path == '/api/enemy-tables/save':
                enemy_tables.apply_edits(self.raw, 0, body['edits'], ROOT/'games/ff8/schema',
                                         set(range(8)), set(range(8)))
                self.data['enemyTables']['rows'][0]['tables'] = enemy_tables.read_tables(self.raw, 0)
            elif path == '/api/enemies/save':
                row = self.data['enemies']['rows'][0]
                for edit in body['edits']:
                    if edit['field'] == 'scan_description':
                        row['scanDescription'] = edit['value']
                    else:
                        next(f for f in row['fields'] if f['field'] == edit['field'])['value'] = edit['value']
            return {'saved': len(body.get('edits', []))}
        dataset = self.vanilla if query.get('dataset') == ['vanilla'] else self.data
        key = {'/api/menu-items': 'menuItems', '/api/enemy-tables': 'enemyTables',
               '/api/enemy-ai': 'enemyAi', '/api/enemy-battle-text': 'enemyBattleText',
               '/api/world-map': 'world'}.get(path, path.removeprefix('/api/'))
        if path == '/api/kernel':
            key = dict(zip([2,3,7,12,13,14,15,16,17,18],
                           ['magic','gfs','characters','abilityJunction','abilityCommand',
                            'abilityStat','abilityCharacter','abilityParty','abilityGf','abilityMenu']))[int(query['section'][0])]
        if key in dataset:
            return deepcopy(dataset[key])
        if path in ('/api/references', '/api/mods'):
            return {'rows': []}
        return {}


def load_page(page, backend: Backend):
    editor = (ROOT/'games/ff8/editor.html').read_text(encoding='utf-8')
    # Omit only the invocation that discovers a local installation.
    assert editor.count('\n  boot();') == 1
    editor = editor.replace('\n  boot();', '\n  // Fixture supplies installation data.')
    page.set_content(re.sub(r'<script\b[^>]*>.*?</script>|<link\b[^>]*>', '', editor, flags=re.S))
    page.add_style_tag(path=str(ROOT/'ui/framework.css'))
    page.add_style_tag(content=re.search(r'<style>(.*?)</style>', editor, re.S)[1])
    page.add_style_tag(path=str(ROOT/'games/ff8/enemies_ui.css'))
    page.expose_function('fixtureFetch', backend.fetch)
    # Use synthetic pixels at the resource boundary, retaining the requested
    # path so card-ID routing can be asserted. No UI functions are replaced.
    image = BytesIO()
    Image.new('RGBA', (62,88), (123,153,174,255)).save(image, format='PNG')
    uri = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode()
    page.add_script_tag(content='''
      window.fetch=async(url, options={})=>({ok:true,json:()=>fixtureFetch(String(url),options)});
      const realSetAttribute=Element.prototype.setAttribute;
      Element.prototype.setAttribute=function(key,value){
        if(this.tagName==='IMG' && key==='src' && String(value).startsWith('/assets/')){
          realSetAttribute.call(this,'data-requested-src',value);
          value=FIXTURE_IMAGE;
        }
        return realSetAttribute.call(this,key,value);
      };
    '''.replace('FIXTURE_IMAGE', repr(uri)))
    for src in re.findall(r'<script src="([^"]+)"', editor):
        path = ROOT/'ui'/src.removeprefix('/shared/') if src.startswith('/shared/') else ROOT/'games/ff8'/src.lstrip('/')
        page.add_script_tag(path=str(path))
    for script in re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', editor, re.S):
        if script.strip():
            page.add_script_tag(content=script)
    page.evaluate('''data=>{
      Object.assign(state.data,data);state.vanilla=structuredClone(data);
      for(const key of editableDatasets)state.base[key]=structuredClone(state.data[key].rows);
      state.base.init={};state.base.settings={};state.booting=false;state.selected.enemies=1;
      navigate('enemies');
    }''', backend.data)


def rows_y(locator) -> set[int]:
    return set(locator.evaluate_all('(nodes)=>nodes.map(n=>Math.round(n.getBoundingClientRect().y))'))


def select_record(page, opener, kind: str, record: int):
    opener.click()
    assert page.evaluate('state.tab') == kind
    page.locator('.lex-searcher-bar').wait_for()
    # Exercise the same long-press candidate gesture as the real editor.
    candidate = page.locator(f'[aria-label="FF8 {kind}"] .lex-search-candidate[data-key="{record}"]')
    if not candidate.count():
        page.locator(f'[data-lex-bottom-search="ff8-{kind}"]').fill('Bite Bug' if kind == 'cards' else f'{kind[:-1].title()} {record}')
        candidate.wait_for()
    candidate.scroll_into_view_if_needed()
    box = candidate.bounding_box()
    page.mouse.move(box['x']+10, box['y']+box['height']/2)
    page.mouse.down()
    page.wait_for_timeout(750)
    page.mouse.up()
    assert page.evaluate('state.tab') == 'enemies'
    assert page.locator('.lex-searcher-bar').count() == 0


def run(browser_path: str | None, screenshots: Path | None):
    from playwright.sync_api import sync_playwright
    backend = Backend()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**({'executable_path':browser_path} if browser_path else {}))
        try:
            page = browser.new_page(viewport={'width':1920,'height':1200})
            page.set_default_timeout(6000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            load_page(page, backend)
            page.wait_for_timeout(150)
            assert not page.locator('.enemy-scan-section').count()
            page.get_by_role('tab', name='Battle Text', exact=True).click()
            assert page.locator('.enemy-battle-text-content .enemy-scan-section').count() == 1
            assert not page.locator('.enemy-detail .enemy-scan-section').count()
            page.get_by_label('Scan description for Funguar', exact=True).fill('Edited Scan description.')
            numbers = page.locator('.enemy-properties-numbers input')
            bools = page.locator('.enemy-properties-bools input[type=checkbox]')
            assert numbers.count() == 7 and len(rows_y(numbers)) == 1
            assert bools.count() == 9 and len(rows_y(bools)) == 2
            for kind in ('draw','mug','drops'):
                section = page.locator(f'.enemy-pair-{kind}')
                assert section.locator('.lex-column-list-row').count() == 3
                assert section.locator('[data-enemy-slot]').count() == 12
                if kind == 'draw':
                    assert not section.locator('.lex-column-list-header').is_visible()
                else:
                    assert 'Slot 4' in section.locator('.lex-column-list-header').inner_text()
            print('PASS full page: Scan tab, numeric row, two boolean rows, three lossless tier rows')
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots/'enemies-top.png'))

            # The real Searcher must write into canonical entries, not copies.
            select_record(page, page.locator('.enemy-pair-draw [data-key=low] .ff8-entity-search-button').first, 'magic', 7)
            select_record(page, page.locator('.enemy-pair-mug [data-key=medium] .ff8-item-finder').nth(2), 'items', 6)
            select_record(page, page.locator('.enemy-pair-drops [data-key=high] .ff8-item-finder').nth(3), 'items', 5)
            for title, tier, slot, quantity in [('DRAW','Low',1,17),('MUG','Med',3,99),('DROPS','High',4,255)]:
                page.get_by_label(f'{title} {tier} entry {slot} quantity',exact=True).fill(str(quantity))
            assert page.evaluate('state.data.enemyTables.rows[0].tables.draw.low[0].valueId') == 7
            page.get_by_role('button',name='Choose card entry 1',exact=True).click()
            page.get_by_role('button',name='Cancel selection',exact=True).click()
            assert page.evaluate('state.data.enemyTables.rows[0].tables.cards[0].cardId') == 0
            select_record(page, page.get_by_role('button',name='Choose card entry 1',exact=True), 'cards', 2)
            card = page.locator('[data-card-slot="0"]')
            assert card.locator('.enemy-card-name').inner_text() == 'Bite Bug'
            assert card.locator('img').get_attribute('data-requested-src') == '/assets/cards/2.png'
            assert page.locator('.enemy-card-choice').count() == 3
            assert len(rows_y(page.locator('.enemy-card-art'))) == 1
            for node in page.locator('.enemy-card-choice').all():
                assert node.locator('.enemy-card-caption').bounding_box()['y'] >= node.locator('.enemy-card-art').bounding_box()['y'] + node.locator('.enemy-card-art').bounding_box()['height']
            print('PASS real magic/item/card Searchers, cancel, changed art/name and canonical slot edits')

            fire = page.get_by_role('button',name='Fire immunity',exact=True)
            fire.click()
            assert fire.get_attribute('aria-pressed') == 'true'
            assert page.get_by_label('Fire damage taken percent',exact=True).is_disabled()
            assert page.locator('.enemy-element-defence .is-immune .enemy-defence-immune').first.is_visible()
            page.evaluate('renderEnemies()')
            fire.click()
            assert page.get_by_label('Fire damage taken percent',exact=True).input_value() == '100'
            assert page.get_by_role('button',name='Ice immunity',exact=True).get_attribute('aria-pressed') == 'false'
            page.get_by_role('button',name='Ice immunity',exact=True).click()
            page.get_by_role('button',name='Ice immunity',exact=True).click()
            assert page.get_by_label('Ice damage taken percent',exact=True).input_value() == '-100'
            field = page.get_by_label('Fire damage taken percent',exact=True)
            field.fill('')
            field.press_sequentially('120',delay=0)
            field.press('Tab')
            assert field.input_value() == '120' and not field.is_disabled()
            page.get_by_role('button',name='Death immunity',exact=True).click()
            assert page.get_by_label('Death status defence percent',exact=True).is_disabled()
            assert page.evaluate('state.data.enemyTables.rows[0].tables.statusDefence[0].stored') == 255
            # Reference restoration uses the shared rails and must update both
            # percent and storage while re-enabling the input.
            fire_tile = page.locator('.enemy-element-defence > .lex-source-control').first
            fire_tile.get_by_title('Use Vanilla: 100%',exact=True).click()
            assert page.get_by_label('Fire damage taken percent',exact=True).input_value() == '100'
            page.get_by_role('button',name='Fire immunity',exact=True).click()
            for width in (1920,1280):
                page.set_viewport_size({'width':width,'height':1200})
                page.locator('.enemy-element-defence').scroll_into_view_if_needed()
                page.wait_for_timeout(100)
                assert len(rows_y(page.locator('.enemy-element-defence .enemy-defence-toggle'))) == 1
                assert len(rows_y(page.locator('.enemy-status-defence .enemy-defence-toggle'))) > 1
                for tile in page.locator('.enemy-defence-tile').all():
                    assert abs(tile.locator('button').bounding_box()['width'] - tile.locator('input').bounding_box()['width']) < 2
                    if tile.locator('img').count():
                        icon_box=tile.locator('img').bounding_box();button_box=tile.locator('button').bounding_box()
                        assert icon_box['y']+icon_box['height'] <= button_box['y']+button_box['height']+1
                if screenshots:
                    page.screenshot(path=str(screenshots/f'enemies-defences-{width}.png'))
            for root in page.locator('.enemy-defence-grid > .lex-source-control:not(.no-reference)').all():
                tile_box=root.locator('.enemy-defence-tile').bounding_box()
                assert root.locator('.lex-source-strip').bounding_box()['y'] >= tile_box['y']+tile_box['height']
            print('PASS immunity/absorption, numeric typing, remembered values, references and icon/input geometry')

            # Action definitions had the same copied-entry bug as the tiers.
            page.set_viewport_size({'width':1920,'height':1200})
            page.get_by_role('tab',name='AI',exact=True).click()
            ability = page.locator('.enemy-ability-table').first.locator('.lex-column-list-row').first
            ability.locator('input').fill('42')
            assert page.evaluate('state.data.enemyTables.rows[0].tables.abilities.low[0].animation') == 42
            page.get_by_role('tab',name='Battle Text',exact=True).click()
            expected = page.evaluate('state.data.enemyTables.rows[0].tables')
            page.evaluate('saveAll()')
            assert backend.data['enemyTables']['rows'][0]['tables'] == expected
            assert page.evaluate('state.data.enemyTables.rows[0].tables') == expected
            assert backend.data['enemies']['rows'][0]['scanDescription'] == 'Edited Scan description.'
            assert page.evaluate('dirtyCount()') == 0
            assert len([x for x in backend.requests if x[0]=='/api/enemy-tables/save']) == 1
            assert backend.raw[0x104:0x106] == bytes([7,17])
            assert backend.raw[0x124+4:0x124+6] == bytes([6,99])
            assert backend.raw[0x144+6:0x144+8] == bytes([5,255])
            assert backend.raw[0xF8] == 2 and backend.raw[0x160] == 90 and backend.raw[0x168] == 255
            print('PASS saveAll -> production binary writer -> reader -> complete editor reload; all untouched entries retained')
            # Scan remains available when there are no script/dialogue records.
            page.evaluate('state.data.enemyBattleText.rows=[];renderEnemies()')
            assert page.get_by_label('Scan description for Funguar',exact=True).is_visible()
            page.evaluate('state.activeSource="vanilla";render()')
            assert page.get_by_label('Scan description for Funguar',exact=True).evaluate('node=>node.readOnly')
            assert page.get_by_role('button',name='Choose card entry 1',exact=True).is_disabled()
            assert page.get_by_role('button',name='Fire immunity',exact=True).is_disabled()
            assert not errors, errors
            print('PASS missing dialogue and read-only sources; zero JavaScript errors')
        finally:
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',default=shutil.which('chromium') or shutil.which('chromium-browser'))
    parser.add_argument('--screenshots',type=Path)
    args = parser.parse_args()
    run(args.browser,args.screenshots)
