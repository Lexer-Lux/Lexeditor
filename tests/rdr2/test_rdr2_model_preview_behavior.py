"""A cached model result must arm the icon before the rebuilt pane is mounted."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


def test_cached_preview_opens_once_and_closes_from_the_same_icon():
    source = (ROOT / 'plugins/rdr2/items.js').read_text(encoding='utf-8')
    attach = source[source.index('function attachItemModelPreview('):source.index('// The drawer\'s contents.')]
    detail = source[source.index('function itemDetailPane('):source.index('const inventoryIconLoads=')]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.route('http://fixture/**', lambda r: r.fulfill(body='<main></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_script_tag(content='''
              const state={modelPreviewAvailability:{item:{available:true}}};
              const modelPreviewKey=()=> 'item';
              const fieldHelp=LexeditorUI.infoHelp,refField=control=>control;
              const localizationInput=()=>LexeditorUI.el('input',{class:'localized-name',value:'Item'});
              const fillItemSources=async (item,root)=>root.append(LexeditorUI.detailNote('Source fixture'));
              let built=0;
              function armItemModelPreview(pane){LexeditorUI.attachModelPreview(pane,{
                content:()=>{built++;return LexeditorUI.modelStage({message:'Model fixture'})}
              })}
            ''' + attach + detail)
            page.evaluate('''() => {
              const U=LexeditorUI;
              const icon=U.iconSlot({message:'Icon'});icon.dataset.inventoryIcon='';
              const cells={identity:U.el('div',{},U.el('div',{class:'item-identity'},icon)),
                description:U.textArea({value:'Example description'})};
              for(const key of ['buy','purchase','sell','carry','quickSelect','recipe','usedIn','effects','tags'])
                cells[key]=U.readonlyField('Example');
              const pane=itemDetailPane({key:'item',model:'test',nameKey:'name',category:'CI_CATEGORY_TEST'},cells);
              document.querySelector('main').append(pane);
            }''')
            assert page.evaluate('built') == 0
            assert page.locator('.lex-detail-panel-heading .lex-detail-field').count() == 0
            assert page.get_by_role('textbox', name='Item name', exact=True).input_value() == 'Item'
            page.get_by_role('button', name='Open model preview', exact=True).click()
            assert page.locator('.lex-model-preview-drawer').is_visible()
            assert page.evaluate('built') == 1
            page.get_by_role('button', name='Close model preview', exact=True).click()
            expect(page.locator('.lex-model-preview-drawer')).to_be_hidden()
            assert page.locator('textarea').input_value() == 'Example description'
            page.get_by_role('button', name='Open model preview', exact=True).click()
            assert page.evaluate('built') == 1
            assert page.locator('[role=dialog]').count() == 0
        finally:
            browser.close()


def test_missing_thumbnail_and_disposed_rdr_renderer_reopen():
    source = (ROOT / 'plugins/rdr2/items.js').read_text(encoding='utf-8')
    arm = source[source.index('function armItemModelPreview('):source.index('function prepareModelPreview(')]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1100, 'height': 800})
            page.route('http://fixture/**', lambda r: r.fulfill(body='<main></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_script_tag(content='''
              const el=LexeditorUI.el,localizedValue=()=> 'Example';
              let created=0,disposed=0;
              const prepareModelPreview=()=>({promise:Promise.resolve({geometry:{lod:0},preview:{
                format:'fixture',summary:{vertices:3,triangles:1},
                source:{outerArchive:'fixture',archiveChain:[],entry:'mesh'},limitations:[]}})});
              const createModelRenderer=async()=>{created++;return {draw(){},dispose(){disposed++}}};
            ''' + arm)
            page.evaluate('''() => {
              const panel=LexeditorUI.detailPanel({title:'Example',body:LexeditorUI.textArea({value:'Keep this edit'})});
              document.querySelector('main').append(panel);
              armItemModelPreview(panel,{key:'example',model:'mesh'});
            }''')
            trigger = page.get_by_role('button', name='View the real mesh model')
            assert trigger.is_visible()
            assert page.locator('.lex-model-preview-close').evaluate('n=>getComputedStyle(n).opacity') == '0'
            assert page.locator('.lex-detail-panel-icon').bounding_box()['x'] > page.locator('.lex-detail-panel-title').bounding_box()['x']
            trigger.hover()
            page.wait_for_timeout(200)
            assert page.locator('.lex-model-preview-close svg').is_visible()
            assert page.locator('.lex-model-preview-close').evaluate('n=>getComputedStyle(n).opacity') == '1'
            for count in [1, 2]:
                trigger.click()
                page.wait_for_function('count=>created===count', arg=count)
                expect(page.locator('.lex-model-preview-drawer canvas')).to_be_visible()
                page.mouse.move(0, 0)
                page.wait_for_timeout(180)
                assert page.locator('.lex-model-preview-close').evaluate('n=>getComputedStyle(n).opacity') == '1'
                page.get_by_role('button', name='Close the mesh model').click()
                expect(page.locator('.lex-model-preview-drawer')).to_be_hidden()
                assert page.evaluate('disposed') == count
            assert page.locator('textarea').input_value() == 'Keep this edit'
        finally:
            browser.close()
