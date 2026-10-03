"""The generic audit reaches nested tabs and restores their parents."""
import json
from pathlib import Path
from test_shared_ui_feedback import page, framework
from ui_tab_sweep import sweep_nested_tabs


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
