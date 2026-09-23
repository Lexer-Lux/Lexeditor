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
from plugins.ff8 import enemy_tables
from plugins.ff8.formats import ENEMY_FIELDS


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
    cards = json.loads((ROOT/'plugins/ff8/schema/card.json').read_text())['card_info']
    statuses = json.loads((ROOT/'plugins/ff8/schema/status.json').read_text())['status']
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
    editor = '<html><head><style>'+(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8')+'</style></head><body><header id="lexeditor-shell"></header><div id="toolbar"></div><main id="main"></main><script>'
    editor += '\n'.join((ROOT/'plugins/ff8'/name).read_text(encoding='utf-8') for name in ['core.js','records.js','party.js','battle.js','places.js','boot.js'])
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
  state.booting=false;state.tab='enemies';state.enemyDetailTab='text';state.selected.enemies=0;
  document.body.dataset.lexPlugin='ff8';render();LexeditorUI.finishPluginLoading();
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
        from plugins.ff8.card_art import _read_atlas, _render_card
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
            page.route('http://localhost/',lambda route:route.fulfill(content_type='text/html',body=markup))
            page.goto('http://localhost/')
            page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
            # Plugin overrides come after the shared stylesheet, as in production.
            page.add_style_tag(content=re.search(r'<style>(.*?)</style>',html,re.S)[1])
            page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
            page.add_script_tag(content=(ROOT/'plugins/ff8/cards_ui.js').read_text(encoding='utf-8'))
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
            assert page.locator('.enemy-detail .enemy-scan-section textarea').count() == 1
            page.locator('.enemy-scan-section textarea').fill('Changed Scan text')
            assert page.evaluate('fixtureState.data.enemies.rows[0].scanDescription') == 'Changed Scan text'
            # Scan remains accessible without local scripted dialogue or a DAT file.
            for enemy in [1,2]:
                page.evaluate('(id)=>{fixtureState.selected.enemies=id;rerender()}',enemy)
                assert page.locator('.enemy-scan-section textarea').count()==1
            page.evaluate('fixtureState.selected.enemies=0;rerender()')
            print('PASS Scan is editable in Battle Text, including empty/unavailable script cases')
            page.evaluate("fixtureState.enemyDetailTab='loot';rerender()")
            for kind in ['draw','mug','drops']:
                table=page.locator(f'.enemy-{kind}-table')
                assert table.locator('.enemy-tier-row').count()==3
                assert table.locator('[role="columnheader"]').count()==(0 if kind=='draw' else 5)
                for tier in ['low','medium','high']:
                    for slot in range(4):
                        control=page.get_by_label(f'{kind.upper()} {tier} choice {slot+1} quantity',exact=True)
                        control.fill(str(30+slot))
                        assert page.evaluate('([k,t,s])=>fixtureState.data.enemyTables.rows[0].tables[k][t][s].quantity',[kind,tier,slot])==30+slot
            page.evaluate('rerender()')
            assert page.get_by_label('DRAW low choice 1 quantity',exact=True).input_value()=='30'
            print('PASS all 36 quantities edit their stored slots and survive rendering')
            page.get_by_label('Clear card slot 1',exact=True).click()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.cards[0].cardId')==255
            assert page.get_by_label('Clear card slot 1',exact=True).is_disabled()
            for width in [720,1000,1600]:
                page.set_viewport_size({'width':width,'height':1000})
                page.wait_for_timeout(150)
                # Each quantity choice stays on one row: the multiplier cannot
                # overlap its input or acquire a different baseline on resize.
                for choice in page.locator('.enemy-tier-table .lex-quantity-choice').all():
                    assert choice.evaluate('n=>n.scrollWidth<=n.clientWidth+1')
            page.evaluate("fixtureState.enemyDetailTab='defense';rerender()")
            number=page.get_by_label('Fire defence percent',exact=True)
            toggle=page.locator('[data-defence="Fire"] input[type=checkbox]')
            number.fill('40');number.blur()
            toggle.check()
            assert number.is_disabled()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.elementDefence[0].stored')==90
            toggle.uncheck();assert number.input_value()=='40' and number.is_enabled()
            number.fill('-100');number.blur()
            assert not toggle.is_checked()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.elementDefence[0].stored')==100
            death=page.get_by_label('Death defence percent',exact=True)
            death.fill('75');death.blur();page.locator('[data-defence="Death"] input[type=checkbox]').check()
            assert death.is_disabled()
            assert page.evaluate('fixtureState.data.enemyTables.rows[0].tables.statusDefence[0].stored')==255
            page.locator('[data-defence="Death"] input[type=checkbox]').uncheck();assert death.input_value()=='75'
            print('PASS card sentinel, immunity, negative defence and restored previous values')
            page.evaluate("fixtureState.activeSource='vanilla';rerender()")
            assert number.is_disabled() and toggle.is_disabled()
            page.evaluate("fixtureState.activeSource='mine'")
            page.evaluate('setup',dataset)
            page.evaluate("fixtureState.enemyDetailTab='loot';rerender()")
            page.get_by_label('MUG high choice 3 quantity',exact=True).fill('77')
            page.get_by_label('DRAW medium choice 2 quantity',exact=True).fill('8')
            page.get_by_label('DROPS low choice 4 quantity',exact=True).fill('99')
            page.get_by_label('Clear card slot 1',exact=True).click()
            page.evaluate("fixtureState.enemyDetailTab='defense';rerender()")
            page.locator('[data-defence="Fire"] input[type=checkbox]').check()
            page.locator('[data-defence="Death"] input[type=checkbox]').check()
            page.evaluate('captureSave()')
            payload=page.evaluate('savedPayloads.find(value=>value.path==="/api/enemy-tables/save")')
            assert payload,page.evaluate('savedPayloads')
            raw=bytearray(0x180)
            enemy_tables.apply_edits(raw,0,payload['body']['edits'],ROOT/'plugins/ff8/schema',set(range(6)),set(range(6)))
            saved=enemy_tables.read_tables(raw,0)
            assert saved['mug']['high'][2]['quantity']==77
            assert saved['draw']['medium'][1]['quantity']==8
            assert saved['drops']['low'][3]['quantity']==99
            assert saved['cards'][0]['cardId']==255
            assert saved['elementDefence'][0]['stored']==90
            assert saved['statusDefence'][0]['stored']==255
            print('PASS production save payload -> DAT writer -> read-back')
            assert not errors,errors
        finally:
            browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',default=shutil.which('chromium') or shutil.which('chromium-browser'))
    parser.add_argument('--exe',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();run(args.browser,args.exe,args.output)
