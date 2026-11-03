"""The generic audit reaches nested tabs and restores their parents."""
import json
from pathlib import Path
from test_shared_ui_feedback import page, framework
from ui_tab_sweep import sweep_nested_tabs, wait_for_loading_clear


def test_nested_tabs_are_discovered_and_restored(page):
    framework(page)
    page.evaluate("""()=>{
      const U=LexeditorUI;window.outer='a';window.inner='x';
      window.render=()=>document.querySelector('main').replaceChildren(
        U.subtabBar({tabs:[{id:'a',label:'A'},{id:'b',label:'B'},{id:'locked',label:'Locked',disabled:true}],
          active:outer,change:id=>{outer=id;render();}}),
        outer==='a'?U.subtabBar({label:'Details',tabs:[{id:'x',label:'X'},{id:'y',label:'Y'}],
          active:inner,change:id=>{inner=id;render();}}):U.el('div',
            {style:'width:300px;height:10px;min-height:10px;max-height:10px;overflow:hidden;font:20px/30px Arial'},
            U.el('span',{},'Nested clipped text')));
      render();
    }""")
    measured = []
    findings = []
    probe = (Path(__file__).with_name('text_clipping_probe.js')).read_text(encoding='utf-8')
    def measure(path):
        measured.append(page.evaluate('[outer,outer==="a"?inner:null]'))
        findings.extend(json.loads(page.evaluate(probe)))
    count = sweep_nested_tabs(page.evaluate, lambda: None,
        measure)
    assert count == 3
    assert sorted(measured, key=str) == [['a', 'x'], ['a', 'y'], ['b', None]]
    assert page.evaluate('[outer,inner]') == ['a', 'x']
    assert any(hit['text'] == 'Nested clipped text' for hit in findings)


def test_budget_exhaustion_is_a_coverage_failure(page):
    framework(page)
    page.evaluate("""()=>{
      const U=LexeditorUI;window.active='a';window.render=()=>document.querySelector('main').replaceChildren(
        U.subtabBar({tabs:[{id:'a',label:'A'},{id:'b',label:'B'}],active,change:id=>{active=id;render();}}));render();
    }""")
    import pytest
    with pytest.raises(AssertionError, match='coverage is incomplete'):
        sweep_nested_tabs(page.evaluate, lambda: None, lambda path: None, limit=1)
    assert page.evaluate('active') == 'a'


def test_sweep_waits_for_an_async_tab_bar(page):
    """A subtab switch that loads behind a loading panel (FF7R text/abilities)."""
    framework(page)
    page.evaluate("""()=>{
      const U=LexeditorUI;window.active='en';
      window.render=()=>document.querySelector('main').replaceChildren(
        window.loading?U.loadingPanel({label:'Loading text'})
        :U.subtabBar({label:'Languages',tabs:[{id:'en',label:'EN'},{id:'fr',label:'FR'}],
          active,change:id=>{window.loading=true;render();
            setTimeout(()=>{active=id;window.loading=false;render();},400);}}));
      render();
    }""")
    measured = []
    def settle():
        page.wait_for_timeout(50)
        assert wait_for_loading_clear(page.evaluate, timeout=10)
    count = sweep_nested_tabs(page.evaluate, settle, measured.append)
    assert count == 2
    assert measured == [[], ['fr']]
    assert page.evaluate('[active,window.loading]') == ['en', False]


def test_loading_wait_times_out_without_raising(page):
    framework(page)
    page.evaluate("()=>document.querySelector('main').replaceChildren("
                  "LexeditorUI.loadingPanel({label:'Stuck'}))")
    assert wait_for_loading_clear(page.evaluate, timeout=0.3) is False
    assert page.locator('.lex-panel-loading').count() == 1

