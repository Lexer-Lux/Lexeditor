from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import page, framework


def test_information_sections_survive_refits_and_remain_reachable(page):
    page.route('**/mod-loading.json', lambda route: route.fulfill(json={
        'plugins': {'fixture': {'loader': 'Fixture loader', 'structure': 'One folder', 'overriding': 'Ordered'}}
    }))
    page.route('**/credits.json', lambda route: route.fulfill(json={
        'plugins': {'fixture': {'contributions': [{'name': 'Fixture author', 'role': 'Integration'}]}},
        'shared': {},
    }))
    page.route('**/distribution-notices.json', lambda route: route.fulfill(json=[
        {'name': 'Fixture license', 'text': 'License text\n' * 30}
    ]))
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.body.insertAdjacentHTML('afterbegin','<div id="lexeditor-shell"></div>');
      window.pywebview={api:{lexeditor_settings:async()=>({}),default_views:async()=>({views:{}})}};
      document.querySelector('main').style.cssText='width:600px;height:350px';
      document.querySelector('main').append(U.panelLayout([U.detailPanel({className:'lex-information-panel',title:'Information',body:[
        U.detailSection({title:'GAME',body:[U.detailField({label:'FOLDER',control:U.readonlyField('Fixture game')})]})
      ]})],{layoutKey:'fixture-information',defaultSizes:[100]}));
      window.fixtureShell=U.mountShell({host:'#lexeditor-shell',plugin:{id:'fixture',name:'Fixture'},
        tabs:[],activeTab:()=>'',navigate:()=>{},info:()=>{},infoActive:()=>true});
    }''')
    page.wait_for_function("document.querySelector('.lex-plugin-mod-loading')?.textContent.includes('Fixture loader')")
    page.wait_for_function("document.querySelector('.lex-plugin-credits')?.textContent.includes('Fixture author')")
    page.evaluate("document.querySelector('#main .lex-tweaks-paged').lexFitPage();fixtureShell.refresh()")
    assert page.locator('.lex-plugin-mod-loading').count() == 1
    assert page.locator('.lex-plugin-credits').count() == 1
    assert page.locator('#main .lex-tweaks-scroll').evaluate('node=>node.clientHeight') > 100
    reachable = set()
    for _ in range(12):
        for selector in ('.lex-plugin-mod-loading', '.lex-plugin-credits'):
            if page.locator(selector).is_visible():
                reachable.add(selector)
        next_page = page.locator('#main .lex-tweaks-pages').get_by_role('button', name='Next page', exact=True)
        if next_page.is_disabled():
            break
        next_page.click()
    assert reachable == {'.lex-plugin-mod-loading', '.lex-plugin-credits'}
    license = page.locator('.lex-plugin-credits').get_by_text('Fixture license', exact=True)
    license.click()
    page.wait_for_timeout(100)
    assert page.locator('.lex-plugin-credits').count() == 1
    assert page.locator('.lex-plugin-credits details').get_attribute('open') is not None
    assert page.locator('.lex-plugin-credits pre').inner_text().count('License text') == 30
