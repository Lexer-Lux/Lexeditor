"""Panel loading uses one accessible, themeable indicator across editors."""
import os
from test_shared_ui_feedback import page, framework, ROOT


def test_loading_panel_in_caller_themes(page):
    framework(page)
    page.evaluate('''()=>document.querySelector('main').append(
      LexeditorUI.loadingPanel({label:'Loading records'}))''')
    for plugin in ['ff7','ff8','ff9','rdr2','ds3','factorio','terraria','ffx_x2',
                   'chrono_trigger','warband','bannerlord','stardew_valley']:
        css=ROOT/'plugins'/plugin/'editor.css'
        style=page.add_style_tag(path=str(css)) if css.exists() else None
        indicator=page.get_by_role('status',name='Loading records',exact=True)
        assert indicator.is_visible(),plugin
        assert indicator.get_attribute('aria-busy')=='true'
        assert indicator.inner_text()=='',plugin
        pulse=indicator.locator('.lex-plugin-loading-pulse')
        assert pulse.is_visible(),plugin
        assert pulse.evaluate('e=>{const r=e.getBoundingClientRect();return r.width>=16&&r.height>=16}'),plugin
        if plugin=='ff8' and os.environ.get('LEX_LOADING_SCREENSHOT'):
            page.screenshot(path=os.environ['LEX_LOADING_SCREENSHOT'])
        if style:
            style.evaluate('e=>e.remove()')
    page.evaluate('''()=>{const p=document.querySelector('.lex-panel-loading');
      p.style.setProperty('--lex-loading-color','rgb(10, 100, 200)');
      p.style.setProperty('--lex-loading-size','48px');}''')
    pulse=page.locator('.lex-plugin-loading-pulse')
    assert pulse.evaluate('e=>getComputedStyle(e).width')=='48px'
