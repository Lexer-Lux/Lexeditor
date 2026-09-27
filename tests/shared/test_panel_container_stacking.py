"""Container-aware stacking preserves readable first-render panel widths."""
import os
import pytest
from pathlib import Path
from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('resizable',[True,False])
def test_panel_stacks_at_its_own_minimum_and_recovers_on_resize(page,resizable):
    page.set_viewport_size({'width':1920,'height':950})
    framework(page)
    page.evaluate('''resizable=>{
      const U=LexeditorUI,main=document.querySelector('main');
      main.style.cssText='width:1000px;height:800px';
      localStorage.setItem('lexeditor:panel-layout:container-test','10');
      main.append(U.panelLayout([
        U.detailPanel({title:'Picture and filters',body:U.detailText('Preview')}),
        U.detailPanel({title:'Field properties',body:U.detailText('Editor')})],
        {layoutKey:'container-test',minSizes:[620,720],stackBelowMinimum:true,resizable}));
    }''',resizable)
    layout=page.locator('.lex-panel-layout').first
    for width,stacked in [(1000,True),(1600,False),(900,True),(1600,False)]:
        page.locator('main').evaluate('(e,w)=>e.style.width=w+"px"',width)
        page.wait_for_function('(stacked)=>document.querySelector(".lex-panel-layout").classList.contains("lex-panel-layout-below-minimum")===stacked',arg=stacked)
        page.wait_for_timeout(70)
        bounds=layout.locator(':scope > .lex-panel-layout-pane').evaluate_all('es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})')
        if stacked:
            assert bounds[0]['x']==bounds[1]['x']
            assert bounds[0]['y']+bounds[0]['h']<=bounds[1]['y']
            if resizable:
                assert not layout.get_by_role('separator').is_visible()
        else:
            assert abs(bounds[0]['y']-bounds[1]['y'])<1
            assert bounds[0]['w']>=619 and bounds[1]['w']>=719,bounds
        assert layout.evaluate('e=>e.scrollWidth<=e.clientWidth+1')
        if os.environ.get('LEXEDITOR_TEST_SHOTS'):
            page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/f'panel-container-{width}.png'))
    assert page.evaluate('localStorage.getItem("lexeditor:panel-layout:container-test")')=='10'
