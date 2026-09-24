"""Tweak categories stay in one column and reject oversized content."""
import pytest
from test_shared_ui_feedback import page, framework
from core.settings_manager import SettingsStore


def test_developer_column_default_round_trip(tmp_path):
    store=SettingsStore(tmp_path/'settings.json',tmp_path/'defaults.json')
    store.save_packaged_defaults({'tweakColumnsPerPage':4})
    assert store.snapshot()['tweakColumnsPerPage']==4
    store.save_packaged_defaults({'tweakColumnsPerPage':30})
    assert store.snapshot()['tweakColumnsPerPage']==12


def test_categories_do_not_have_nested_columns_or_gaps(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.cards=Array.from({length:12},(_,i)=>{
        const subs=['Access','Dev tools'].map(label=>{
          const field=U.el('div',{class:'settings-field'},'Value',U.el('input',{type:'number',value:1}));
          return U.el('div',{class:'settings-sub'},U.el('h3',{},label),U.el('div',{class:'settings-fields'},field));
        });
        return U.el('section',{class:'settings-section'},U.el('h2',{},'Tweak '+i),U.el('div',{class:'settings-subs'},...subs));
      });
      window.view=U.settingsColumns(cards,{columns:3,strictColumns:true,splitOversized:false});
      document.querySelector('main').append(view);
    }''')
    page.wait_for_timeout(150)
    assert page.locator('.lex-tweaks-scroll').evaluate('n=>getComputedStyle(n).overflowY')=='hidden'
    for subs in page.locator('.lex-tweak-column .settings-subs').all():
        boxes=subs.locator('.settings-sub').evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().toJSON())')
        assert abs(boxes[0]['left']-boxes[1]['left'])<1
        assert abs(boxes[0]['bottom']-boxes[1]['top'])<1
    with pytest.raises(Exception,match='Tweak cannot fit one column'):
        page.evaluate("()=>{cards[0].style.minHeight='2000px';view.lexFitPage()}")
