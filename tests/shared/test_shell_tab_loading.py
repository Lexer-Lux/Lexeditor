"""Tab switches announce a loading panel before the plugin renders."""
from test_shared_ui_feedback import page, framework


def mount_tabs(page):
    page.evaluate('''() => {
      document.querySelector('main').textContent = 'Items content';
      document.body.insertAdjacentHTML('afterbegin', '<div id="shell"></div>');
      window.pywebview = {api: {lexeditor_settings: async () => ({developerMode: false})}};
      window.sawPanel = 'unset';
      LexeditorUI.mountShell({host: '#shell', plugin: {id: 'fixture', name: 'Fixture'},
        tabs: [{id: 'items', label: 'Items'}, {id: 'magic', label: 'Magic'}],
        activeTab: () => 'items',
        navigate: tab => {
          window.sawPanel = document.querySelector('#main .lex-panel-loading') !== null;
          document.querySelector('#main').textContent = tab + ' content';
        }});
    }''')
    page.wait_for_timeout(300)


def test_shell_replaces_old_content_with_panel_before_navigate(page):
    framework(page)
    mount_tabs(page)
    page.locator('nav button[data-tab="magic"]').click()
    page.wait_for_function("window.sawPanel !== 'unset'")
    assert page.evaluate('sawPanel') is True
    assert page.locator('#main').inner_text() == 'magic content'


def test_synchronous_render_leaves_no_panel_behind(page):
    framework(page)
    mount_tabs(page)
    page.locator('nav button[data-tab="magic"]').click()
    page.wait_for_function("document.querySelector('#main').textContent === 'magic content'")
    assert page.locator('#main .lex-panel-loading').count() == 0
    assert 'Items content' not in page.locator('#main').inner_text()
