"""Browser regression tests for the compact Enemies editor using real UI code.

Uses synthetic DAT records, real parsers and the production JS/CSS. No game
assets or running game required. --exe optionally checks private card art.
Requires Pillow and playwright, plus Chromium (--browser can override).
"""
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import enemy_tables
from games.ff8.formats import ENEMY_FIELDS


def fixture() -> dict:
    properties = []
    for field in ENEMY_FIELDS:
        props = {**field, 'field': field['name'], 'control': field.get('control', 'number')}
        props['value'] = False if props['control'] == 'boolean' else 20 if field['name'] == 'medium_level' else 30 if field['name'] == 'high_level' else 8
        properties.append(props)
    enemies = [{'id': i, 'name': name, 'available': i != 2, 'filename': f'c0m{i:03}.dat',
                'scanDescription': 'A test enemy with a long Scan description.', 'fields': json.loads(json.dumps(properties))}
               for i, name in enumerate(['Geezard', 'T-Rexaur', 'Unavailable'])]
    tables = []
    for row in enemies[:2]:
        raw = bytearray(0x180)
        raw[0x160:0x168] = bytes([80] * 8)
        raw[0x168:0x17c] = bytes([100] * 20)
        raw[0xf8:0xfb] = bytes([0, 1, 2])
        table = enemy_tables.read_tables(raw, 0)
        for kind in ['draw', 'mug', 'drops']:
            for tier in table[kind].values():
                for entry in tier:
                    entry.update(valueId=entry['slot'] + 1, quantity=entry['slot'] + 2)
        tables.append({'id': row['id'], 'name': row['name'], 'tables': table})
    cards = json.loads((ROOT/'games/ff8/schema/card.json').read_text())['card_info']
    statuses = json.loads((ROOT/'games/ff8/schema/status.json').read_text())['status']
    return {'enemies': {'rows': enemies}, 'enemyTables': {'rows': tables, 'choices': {'cards': cards,
        'statuses': statuses, 'enemyAbilities': [{'id': 0, 'name': 'None'}], 'abilityTypes': [{'id': 0, 'name': 'None'}]}},
        'enemyBattleText': {'rows': [{'id': 0, 'available': True, 'lines': [{'id': 0, 'text': 'Local dialogue.'}]},
                                   {'id': 1, 'available': False, 'lines': []}]},
        'enemyAi': {'rows': [], 'opcodes': []},
        'items': {'rows': [{'id': i, 'name': name, 'iconId': None} for i, name in enumerate(['None', 'Potion', 'Hi-Potion', 'Mega-Potion', 'Elixir', 'Tent'])]},
        'magic': {'rows': [{'id': i, 'name': name, 'fields': []} for i, name in enumerate(['None', 'Fire', 'Blizzard', 'Thunder', 'Cure', 'Ultima'])]},
        'cards': {'rows': [{**card, 'top': 1, 'bottom': 2, 'left': 3, 'right': 4, 'element': 0, 'power': 1}
                           for card in cards if card['id'] < 110], 'elements': [{'id': 0, 'name': 'None'}]},
        'text': {'rows': []}}


def page_html() -> str:
    editor = (ROOT/'games/ff8/editor.html').read_text()
    # Only omit the desktop boot / external game discovery; every view,
    # picker, provenance control, serializer and layout is production code.
    editor = editor[:editor.index('  const shell=LexeditorUI.mountShell(')]
    editor = editor.replace('<header id="lexeditor-shell"></header>',
        '<header id="lexeditor-shell" class="lex-shell-header"><div class="lex-shell-command-row">LEXEDITOR · UI regression fixture</div></header>')
    return editor + r'''
const shell={refresh(){LexeditorUI.refreshReferences(document);}, history:{clear(){}}};
window.setup = data => {
  for(const key of editableDatasets)state.data[key]={rows:[]};
  Object.assign(state.data,structuredClone(data));state.vanilla=structuredClone(state.data);
  for(const key of editableDatasets)state.base[key]=structuredClone(state.data[key]?.rows||[]);
  state.data.settings={};state.base.settings={};state.data.init={};state.base.init={};
  state.booting=false;state.tab='enemies';state.enemyPanelTab='battleText';state.selected.enemies=0;
  document.body.dataset.lexPlugin='ff8';render();
};
window.fixtureState=state;
window.rerender=render;
window.mountRight = width => {
  document.getElementById('main').replaceChildren(enemyDetail(state.data.enemies.rows[0],state.columnPrefs.enemies));
  const panel=document.querySelector('.enemy-detail');panel.style.width=width+'px';panel.style.margin='0 auto';
};
window.savedPayloads=[];
window.captureSave = async () => {
  // Retain production saveAll's payload generation, but don't perform disk I/O.
  const originalApi=api;
  api=async(path,options)=>{
    if(path.endsWith('/save'))window.savedPayloads.push({path,body:JSON.parse(options.body)});
    throw new Error('fixture save intercepted');
  };
  try{await saveAll()}catch{}finally{api=originalApi;document.querySelector('.lex-alert-backdrop')?.remove()}
};
</script></body></html>'''


def run(browser_path: str | None, exe: Path | None, output: Path | None) -> None:
    from playwright.sync_api import sync_playwright
    dataset = fixture()
    pngs = {}
    if exe:
        from games.ff8.card_art import _read_atlas, _render_card
        palette, pixels = _read_atlas(exe.read_bytes())
        for i in range(110):
            pngs[f'/assets/cards/{i}.png'] = _render_card(i, palette, pixels)
    html = page_html()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, **({'executable_path': browser_path} if browser_path else {}))
        try:
            page = browser.new_page(viewport={'width': 1600, 'height': 1000})
            errors = []
            page.set_default_timeout(5000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            # Inline the same files: no network/browser navigation is needed.
            scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S)
            markup=re.sub(r'<script(?:\s[^>]*)?>.*?</script>','',html,flags=re.S)
            markup=re.sub(r'<link[^>]+>','',markup)
            # framework.js resolves shared assets relative to document.baseURI;
            # about:blank is not a valid URL base in current Chromium.
            markup=markup.replace('<head>','<head><base href="http://localhost/">',1)
            page.set_content(markup)
            page.add_style_tag(content=(ROOT/'ui/framework.css').read_text())
            # Plugin overrides come after the shared stylesheet, as in production.
            page.add_style_tag(content=re.search(r'<style>(.*?)</style>',html,re.S)[1])
            page.add_script_tag(content=(ROOT/'ui/framework.js').read_text())
            page.add_script_tag(content=(ROOT/'games/ff8/cards_ui.js').read_text())
            if pngs:
                # Mock asset transport only; preserve the production image,
                # load/error handlers and card controls. No HTTP is required.
                page.evaluate('''images => {
                  const original=LexeditorUI.el;
                  LexeditorUI.el=(tag,attrs={},...children)=>original(tag,
                    tag==='img' && images[attrs.src] ? {...attrs,src:images[attrs.src]} : attrs,...children);
                }''', {path:'data:image/png;base64,'+base64.b64encode(data).decode() for path,data in pngs.items()})
            page.add_script_tag(content=scripts[-1])
            page.evaluate('setup', dataset)
            page.wait_for_timeout(200)
            assert not errors, errors
            assert page.locator('.enemy-detail .enemy-scan-section').count() == 0
            assert page.locator('.enemy-tabbed-column .enemy-scan-section textarea').count() == 1
            page.locator('.enemy-scan-section textarea').fill('Changed Scan text')
            assert page.evaluate('fixtureState.data.enemies.rows[0].scanDescription') == 'Changed Scan text'
            # Scan remains accessible without local scripted dialogue or a DAT file.
            for enemy in [1,2]:
                page.evaluate('(id)=>{fixtureState.selected.enemies=id;rerender()}',enemy)
                assert page.locator('.enemy-scan-section textarea').count()==1
            page.evaluate('fixtureState.selected.enemies=0;rerender()')
            print('PASS Scan is editable in Battle Text, including empty/unavailable script cases')
            for kind in ['draw','mug','drops']:
                table=page.locator(f'.enemy-{kind}-table')
                assert table.locator('tbody>tr').count()==3
                assert table.locator('tbody>tr>td').count()==12
                assert table.locator('thead th').count()==(0 if kind=='draw' else 5)
                assert table.locator('tbody>tr>th').all_text_contents()==['LOW','MED','HIGH']
                for tier in ['low','medium','high']:
                    for slot in range(4):
                        value=30+slot
                        table.locator(f'[data-tier="{tier}"] [data-slot="{slot}"] input').fill(str(value))
                        assert page.evaluate('([kind,tier,slot])=>fixtureState.data.enemyTables.rows[0].tables[kind][tier][slot].quantity',[kind,tier,slot])==value
            page.evaluate('rerender()')
            assert page.locator('.enemy-draw-table [data-tier="low"] [data-slot="0"] input').input_value()=='30'
            print('PASS all 36 live pair entries persist across rerenders; slot labels and order preserved')
            # Use the actual shared thing finder (press-and-hold a candidate).
            page.locator('.enemy-draw-table [data-tier="low"] [data-slot="0"] .ff8-entity-search-button').click()
            assert page.evaluate('fixtureState.tab')=='magic'
            candidate=page.locator('.lex-search-candidate').filter(has_text='Ultima').first
            candidate.hover();page.mouse.down();page.wait_for_timeout(800);page.mouse.up()
            assert page.evaluate('fixtureState.tab')=='enemies'
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.draw.low[0].valueId')==5
            page.locator('.enemy-card-finder').first.click()
            assert page.evaluate('fixtureState.tab')=='cards'
            candidate=page.locator('.lex-search-candidate').filter(has_text='Abadon').first
            candidate.hover();page.mouse.down();page.wait_for_timeout(800);page.mouse.up()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.cards[0].cardId')==61
            assert page.locator('.enemy-card-name').first.inner_text().strip()=='Abadon'
            page.locator('.enemy-card-clear').first.click()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.cards[0].cardId')==255
            assert page.locator('.enemy-card-name').first.inner_text().strip()=='Immune'
            print('PASS production magic/card thing finders, return navigation, and card sentinel')
            fire=page.locator('[data-defence="Fire"]');number=fire.locator('input[type=number]');toggle=fire.locator('input[type=checkbox]')
            number.fill('40');number.press('Tab');toggle.check()
            assert number.is_disabled() and fire.locator('.enemy-immunity-label').is_visible()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.elementDefence[0].stored')==90
            toggle.uncheck();assert number.input_value()=='40' and number.is_enabled()
            number.fill('-100');number.press('Tab')
            assert not toggle.is_checked() and number.is_enabled()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.elementDefence[0].stored')==100
            death=page.locator('[data-defence="Death"]');death.locator('input[type=number]').fill('75');death.locator('input[type=number]').press('Tab')
            death.locator('input[type=checkbox]').check()
            assert death.locator('input[type=number]').is_disabled()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.statusDefence[0].stored')==255
            death.locator('input[type=checkbox]').uncheck()
            assert death.locator('input[type=number]').input_value()=='75'
            fire.locator('.lex-reference-value').first.click()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.elementDefence[0].percent')==100
            assert page.locator('[data-defence="Fire"] input[type=number]').is_enabled()
            page.locator('.enemy-mug-table [data-tier="low"] [data-slot="0"] .lex-source-control').last.locator('.lex-reference-value').first.click()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.mug.low[0].quantity')==2
            print('PASS immune overlays, disabled inputs, exact byte conversion, negative values and reference restoration')
            # Layout at minimum and wide right-pane sizes, with real provenance.
            for width in [430,720,1000]:
                page.evaluate('mountRight',width);page.wait_for_timeout(100)
                geometry=page.evaluate('''() => {
                  const tops=s=>[...document.querySelectorAll(s)].map(x=>Math.round(x.getBoundingClientRect().top));
                  const panel=document.querySelector('.enemy-detail');
                  return {numbers:tops('.enemy-properties-numeric>.enemy-property'),flags:tops('.enemy-properties-booleans>.enemy-property'),
                    elements:tops('.enemy-elements>.enemy-defence-tile'),cards:tops('.enemy-card-choices>.lex-source-control'),
                    horizontalOverflow:panel.scrollWidth>panel.clientWidth+1};
                }''')
                assert len(set(geometry['numbers']))==1,geometry
                assert len(set(geometry['flags']))==2,geometry
                assert len(set(geometry['elements']))==1,geometry
                assert len(set(geometry['cards']))==1,geometry
                assert not geometry['horizontalOverflow'],geometry
                if output and width==720:
                    output.mkdir(parents=True,exist_ok=True)
                    page.locator('.enemy-detail').screenshot(path=str(output/'enemy-compact-panel.png'))
                    page.locator('.enemy-card-choices').scroll_into_view_if_needed()
                    page.wait_for_timeout(100)
                    if pngs:
                        assert page.locator('.enemy-card-art img').count()==2
                        assert page.locator('.enemy-card-art img').evaluate_all('(images)=>images.every(img=>img.complete&&img.naturalWidth===64)')
                    page.locator('.enemy-detail').screenshot(path=str(output/'enemy-cards.png'))
                    page.locator('.enemy-defence-section').last.scroll_into_view_if_needed()
                    page.locator('[data-defence="Fire"] input[type=checkbox]').check()
                    page.locator('[data-defence="Death"] input[type=checkbox]').check()
                    page.locator('.enemy-detail').screenshot(path=str(output/'enemy-defences.png'))
            # Read-only project sources must not expose any of the new writes.
            page.evaluate("fixtureState.activeSource='vanilla';mountRight(720)")
            for selector in ['.enemy-tier-table input','.enemy-card-finder','.enemy-defence-tile input','.enemy-properties-compact input']:
                for control in page.locator(selector).all(): assert control.is_disabled(),selector
            page.evaluate("fixtureState.activeSource='mine'")
            print('PASS 7-number row, two boolean rows, 8-element row and 3-card row at 430/720/1000px')
            # Record the real save payload before it reaches the backend.
            page.evaluate('setup',dataset)
            page.locator('.enemy-mug-table [data-tier="high"] [data-slot="2"] input').fill('77')
            page.locator('.enemy-draw-table [data-tier="medium"] [data-slot="1"] input').fill('8')
            page.locator('.enemy-drops-table [data-tier="low"] [data-slot="3"] input').fill('99')
            page.locator('.enemy-card-clear').first.click()
            page.locator('[data-defence="Fire"] input[type=checkbox]').check()
            page.locator('[data-defence="Death"] input[type=checkbox]').check()
            page.evaluate('captureSave()')
            payload=page.evaluate('savedPayloads.find(value=>value.path==="/api/enemy-tables/save")')
            assert payload, page.evaluate('savedPayloads')
            edits=payload['body']['edits']
            assert next(e for e in edits if e['kind']=='mug' and e['tier']=='high' and e['slot']==2)['quantity']==77
            raw=bytearray(0x180)
            enemy_tables.apply_edits(raw,0,edits,ROOT/'games/ff8/schema',set(range(6)),set(range(6)))
            saved=enemy_tables.read_tables(raw,0)
            assert saved['mug']['high'][2]['quantity']==77
            assert saved['draw']['medium'][1]['quantity']==8
            assert saved['drops']['low'][3]['quantity']==99
            assert saved['cards'][0]['cardId']==255
            assert saved['elementDefence'][0]['stored']==90
            assert saved['statusDefence'][0]['stored']==255
            print('PASS actual saveAll payload -> backend DAT writer -> read-back')
            assert not errors, errors
        finally:
            browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',default=shutil.which('chromium') or shutil.which('chromium-browser'))
    parser.add_argument('--exe',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();run(args.browser,args.exe,args.output)
