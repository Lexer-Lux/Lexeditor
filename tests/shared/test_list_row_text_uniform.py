"""Every row name in a list renders at one font size.

DS1 Items -> Consumables showed most row names at one small size with a few
("Soul of a Nameless Soldier", "Large Soul of a Brave Warrior", ...) visibly
larger. Row names must share a single size per list; a name that does not fit
is ellipsized (or the column gives it room), never sized apart from its
neighbours. The shared fixture below runs everywhere; the DS1 render needs the
installed game and skips without LEXEDITOR_DS1_ACCEPTANCE_ROOT.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))

from test_shared_ui_feedback import framework, page  # noqa: E402,F401

OUTPUT = Path(os.environ.get('LEXEDITOR_TEST_OUTPUT',
                             str(Path(tempfile.gettempdir()) / 'lexeditor-dev')))

NAMES = ['Bow', 'Joy', 'None', 'Humanity', 'Prayer',
         'Soul of a Nameless Soldier', 'Large Soul of a Brave Warrior',
         'Large Soul of a Lost Undead', 'Orange Guidance Soapstone',
         'Soul of Gwyn, Lord of Cinder', 'Soul of the Moonlight Butterfly']


def _uniformity(page):
    return page.evaluate("""() => {
      const nodes=[...document.querySelectorAll(
        '.lex-barrelled-master .lex-column-cell-text, .lex-column-list .lex-column-cell-text')];
      const sizes=nodes.map(n=>getComputedStyle(n).fontSize);
      const overflowing=nodes.filter(n=>n.scrollWidth>n.clientWidth+1);
      return {count:nodes.length, sizes:[...new Set(sizes)],
        ellipsis:overflowing.every(n=>getComputedStyle(n).textOverflow==='ellipsis'
          && getComputedStyle(n).whiteSpace==='nowrap'),
        titled:nodes.every(n=>n.title===n.textContent)};
    }""")


def test_barrelled_master_keeps_one_row_text_size(page):
    framework(page)
    page.evaluate("""(names)=>{
      const U=LexeditorUI, main=document.querySelector('main');
      main.style.cssText='position:absolute;inset:0;';
      const rows=Array.from({length:90},(_,id)=>({id, name:names[id%names.length]}));
      const barrels=[0,1,2].map(barrel=>U.columnList({rows:rows.slice(barrel*30,barrel*30+30),
        key:r=>r.id, columns:[{key:'name', label:'Name', grow:1}]}));
      barrels.forEach(list=>{list.style.fontSize='15px';});
      window.grid=U.el('div',{class:'lex-barrel-grid',style:'--lex-barrels:3;width:900px;'},...barrels);
      main.replaceChildren(U.el('div',{class:'lex-barrelled-master'},grid));
    }""", NAMES)
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(700)
    # Narrow, then wide again: the list refits after every geometry change and
    # every row name keeps the same size as its neighbours throughout. At the
    # narrow width the long names cannot fit at the base size, so per-row
    # fitting would leave them smaller than the short names beside them.
    for width in (900, 420, 900):
        page.evaluate('(width)=>{grid.style.width=width+"px";}', width)
        page.wait_for_timeout(700)
        result = _uniformity(page)
        assert result['count'] == 90, result
        assert result['sizes'] == [result['sizes'][0]], result
        assert result['ellipsis'] and result['titled'], result
    OUTPUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUTPUT / 'lex-row-text-uniform-fixture.png'))


def _ds1_root():
    root = os.environ.get('LEXEDITOR_DS1_ACCEPTANCE_ROOT')
    if not root:
        pytest.skip('needs the installed game (LEXEDITOR_DS1_ACCEPTANCE_ROOT)')
    return Path(root)


def test_ds1_item_lists_keep_one_row_text_size():
    from playwright.sync_api import sync_playwright
    from plugins.ds1.store import RELATIVE, MARKER
    from plugins.ds1 import texts
    from plugins.ds1.plugin import DS1Session
    real_root = _ds1_root()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-row-text-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        for rel in (RELATIVE, texts.RELATIVE, texts.MENU_RELATIVE):
            dst = game / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real_root / rel, dst)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0',
                              'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    tab = browser.new_page(viewport={'width': 1920, 'height': 1080})
                    tab.on('pageerror', lambda error: errors.append(str(error)))
                    tab.goto(session.url)
                    tab.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    tab.wait_for_function(
                        "state.tab==='items' && state.sub==='consumables' && state.row",
                        timeout=60000)
                    for sub in ('consumables', 'weapons'):
                        tab.evaluate("""([key, barrels, rows]) => {
                          localStorage.setItem(`lexeditor:barrels:${key}`, String(barrels));
                          localStorage.setItem(`lexeditor:rows:${key}`, String(rows));
                        }""", [f'ds1-items-{sub}', 3, 45])
                        tab.reload()
                        tab.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                        tab.wait_for_function(
                            "state.tab==='items' && state.sub==='consumables' && state.row",
                            timeout=60000)
                        # Weapons is not the landing subtab; navigate to it.
                        if sub != 'consumables':
                            tab.locator('.lex-subtab-bar [data-subtab="weapons"]').click()
                            tab.wait_for_function(
                                "state.tab==='items' && state.sub==='weapons' && state.row",
                                timeout=60000)
                        tab.wait_for_function(
                            "()=>document.fonts ? document.fonts.status==='loaded' : true",
                            timeout=30000)
                        tab.wait_for_timeout(1500)
                        result = tab.evaluate("""() => {
                          const nodes=[...document.querySelectorAll(
                            '.lex-barrelled-master .lex-column-list-cell[data-column-key="name"] .lex-column-cell-text')];
                          const sizes=nodes.map(n=>getComputedStyle(n).fontSize);
                          return {count:nodes.length, sizes:[...new Set(sizes)],
                            detail:nodes.map(n=>({text:n.textContent,
                              size:getComputedStyle(n).fontSize, inline:n.style.fontSize}))};
                        }""")
                        assert result['count'] > 40, (sub, result['count'])
                        assert len(result['sizes']) == 1, (sub, result['sizes'],
                            [row for row in result['detail']
                             if row['size'] != result['sizes'][0]][:10])
                        OUTPUT.mkdir(parents=True, exist_ok=True)
                        tab.screenshot(path=str(OUTPUT / f'lex-row-text-uniform-{sub}.png'))
                finally:
                    browser.close()
        finally:
            session.stop()
    assert not errors, errors
