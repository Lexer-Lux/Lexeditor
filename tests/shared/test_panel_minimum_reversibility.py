"""Panel minima must not depend on the text exposed by previous resizing."""
import pytest
from test_shared_ui_feedback import framework, page


@pytest.mark.parametrize('count',[2,3])
def test_panel_returns_to_initial_minimum_after_expansion(page, tmp_path, count):
    framework(page)
    page.evaluate('''count=>{
      const U=LexeditorUI;
      document.querySelector('main').style.cssText='width:1150px;height:700px';
      localStorage.setItem('lexeditor:panel-layout:reversible',count===2?'10':'[10,45,45]');
      document.querySelector('main').append(U.panelLayout(Array.from({length:count},(_,i)=>
        U.detailPanel({title:'Panel '+i,body:U.el('div',{
          class:'lex-readonly-field',style:'white-space:nowrap;overflow:hidden;font-size:22px'},
          'An exceptionally long record name whose text stays the same throughout resizing')})),
        {layoutKey:'reversible',minSizes:Array(count).fill(240)}));
    }''',count)
    panes=page.locator('.lex-panel-layout-pane')
    widths=lambda:panes.evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().width)')
    page.wait_for_timeout(150)
    assert widths()[0]==pytest.approx(240,abs=1)
    divider=page.get_by_role('separator').first
    divider.press('End')
    assert widths()[0]>400
    divider.press('Home')
    assert widths()[0]==pytest.approx(240,abs=1)
    assert all(w>=239 for w in widths())
    # Mouse movement must be reversible too, not only the keyboard endpoints.
    before=widths()
    box=divider.bounding_box()
    x,y=box['x']+box['width']/2,box['y']+box['height']/2
    page.mouse.move(x,y)
    page.mouse.down()
    page.mouse.move(x+170,y,steps=8)
    page.wait_for_timeout(60)
    assert widths()[0]>before[0]+100
    page.mouse.move(x,y,steps=8)
    page.mouse.up()
    assert widths()==pytest.approx(before,abs=1)
    page.screenshot(path=str(tmp_path/f'panel-minimum-{count}.png'))


@pytest.mark.parametrize('vertical',[False,True])
@pytest.mark.parametrize('resizable',[False,True])
def test_initial_and_reset_sizes_share_the_configured_floor(page,vertical,resizable):
    framework(page)
    page.evaluate('''({vertical,resizable})=>{
      const U=LexeditorUI;
      document.querySelector('main').style.cssText='width:1100px;height:700px';
      document.querySelector('main').append(U.panelLayout([
        U.detailPanel({title:'First',body:'First panel'}),U.detailPanel({title:'Second',body:'Second panel'})],
        {orientation:vertical?'vertical':'horizontal',resizable,defaultSizes:[5,95],minSizes:[260,280]}));
    }''',{'vertical':vertical,'resizable':resizable})
    page.wait_for_timeout(100)
    sizes=lambda:page.locator('.lex-panel-layout-pane').evaluate_all(
        '(ns,vertical)=>ns.map(n=>n.getBoundingClientRect()[vertical?"height":"width"])',vertical)
    assert sizes()[0]==pytest.approx(260,abs=1)
    assert sizes()[1]>=279
    if resizable:
        divider=page.get_by_role('separator')
        divider.press('End')
        divider.click(button='right')
        assert sizes()[0]==pytest.approx(260,abs=1)
        assert sizes()[1]>=279
