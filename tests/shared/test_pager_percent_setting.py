"""G11: pagination bar height is a percentage of screen height, wired end to end."""
import json
from pathlib import Path

from test_shared_ui_feedback import page, framework
from core.settings_manager import SettingsStore

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))


def test_pager_percent_round_trip_and_clamp(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json', tmp_path / 'defaults.json')
    assert store.snapshot()['pagerBarHeightPercent'] == 6.0
    store.save('daily', pager_bar_height_percent=8.5)
    assert SettingsStore(store.path, store.defaults_path).snapshot()['pagerBarHeightPercent'] == 8.5
    store.save('daily', pager_bar_height_percent=99)
    assert store.snapshot()['pagerBarHeightPercent'] == 12.0
    store.save('daily', pager_bar_height_percent=-4)
    assert store.snapshot()['pagerBarHeightPercent'] == 3.0
    store.save_packaged_defaults({'pagerBarHeightPercent': 30})
    assert store.snapshot()['defaultValues']['pagerBarHeightPercent'] == 12.0


def test_pager_percent_control_and_var(page):
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={},
                    defaultValues=dict(BASE),
                    updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])
    settings['pagerBarHeightPercent'] = 8
    page.evaluate(f'window.pywebview={{api:{{lexeditor_settings:async()=>({json.dumps(settings)})}}}}')
    framework(page)
    page.evaluate('LexeditorUI.openSettings()')
    page.wait_for_selector('#lex-pagerBarHeightPercent')
    control = page.locator('#lex-pagerBarHeightPercent')
    assert control.is_enabled()
    assert control.get_attribute('min') == '3'
    assert control.get_attribute('max') == '12'
    assert 'screen height' in page.locator('.lex-global-setting', has=control).inner_text()
    assert page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--lex-pager-bar-height').trim()") == '8vh'
    page.evaluate("document.body.append(LexeditorUI.element('div',{class:'lex-pager'}))")
    assert page.locator('.lex-pager').evaluate('n=>n.getBoundingClientRect().height') == 64


def test_populated_pager_obeys_small_height_settings(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>document.querySelector('main').append(LexeditorUI.pager({
        page:0,pages:5,total:100,pageSize:20,change:()=>{},
        search:{key:'height-check',change:()=>{}}}))''')
    for percent in [3,6,9]:
        page.evaluate("p=>document.documentElement.style.setProperty('--lex-pager-bar-height',p+'vh')",percent)
        page.wait_for_timeout(100)
        box=page.locator('.lex-pager').bounding_box()
        assert abs(box['height']-800*percent/100)<1
        assert page.locator('.lex-pager').evaluate('''bar=>{
            const box=bar.getBoundingClientRect();
            return [...bar.querySelectorAll('input,button,select')].filter(n=>n.offsetWidth).every(n=>{
                const r=n.getBoundingClientRect();return r.top>=box.top-1&&r.bottom<=box.bottom+1;
            });}''')


def pager_gap(page):
    return page.evaluate('''()=>{
      const pager=document.querySelector('.lex-pager');
      const list=document.querySelector('.lex-column-list');
      return {bar:Math.round(pager.getBoundingClientRect().height),
        reserved:getComputedStyle(document.documentElement)
          .getPropertyValue('--lex-pager-height').trim(),
        listBottom:list?Math.round(list.getBoundingClientRect().bottom):null,
        pagerTop:Math.round(pager.getBoundingClientRect().top),
        gap:list?Math.round(pager.getBoundingClientRect().top-
          list.getBoundingClientRect().bottom):null};
    }''')


def test_lower_bar_height_resizes_the_page_above_it(page):
    """A saved pagination-bar height must resize the page under it at once.

    The space held open under a page is the measured bar height, so before this
    a reader who lowered the bar height in Settings was left with a band of
    empty space between the page and the bar until the page was rebuilt.
    """
    framework(page)
    page.add_style_tag(content='#main{display:flex;flex-direction:column}'
                               '.lex-paged-list-detail{flex:1 1 auto;min-height:0}')
    page.evaluate("()=>document.documentElement.style.setProperty('--lex-pager-bar-height','9vh')")
    page.evaluate('''()=>{
      const U=LexeditorUI,rows=Array.from({length:80},(_,i)=>({id:i+1,name:'Row '+(i+1)}));
      const view=U.pagedListDetail({rows,key:r=>r.id,selected:0,pageSize:15,fit:{minRowHeight:34},
        master:v=>U.columnList({rows:v.rows,key:r=>r.id,selected:v.selected,
          columns:[{key:'name',label:'Name'}]}),
        detail:r=>U.detailPanel({title:r.name})});
      document.querySelector('main').append(view);
    }''')
    page.wait_for_timeout(600)
    before=pager_gap(page)
    assert before['reserved']==f"{before['bar']}px",before
    # A reader reaches Settings long after the page was built; the bar used to
    # be watched for its first ten seconds only, so the wait is the defect.
    page.wait_for_timeout(11000)
    # Saving the pagination-bar height in Settings applies the new value and
    # announces the change, exactly as openSettings() does.
    page.evaluate("()=>{document.documentElement.style.setProperty('--lex-pager-bar-height','3.5vh');"
                  "dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{}}))}")
    page.wait_for_timeout(400)
    after=pager_gap(page)
    assert after['bar']<before['bar'],(before,after)
    assert after['reserved']==f"{after['bar']}px",after
    assert after['listBottom']>before['listBottom'],(before,after)
    assert abs(after['gap']-before['gap'])<2,(before,after)
