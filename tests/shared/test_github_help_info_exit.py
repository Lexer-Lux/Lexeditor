"""Shell Data Map / Info buttons leave the GitHub workspace, like tabs do."""
from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401  (pytest fixture)


def test_help_and_info_close_github_workspace(page):
    page.evaluate('''()=>{
      window.calls = [];
      window.pywebview = {api: {
        lexeditor_settings: async () => ({developerMode: true}),
        github_repository: async () => ({repository: 'Lexer-Lux/Lexeditor'}),
        github_issues: async () => ({issues: []}),
        default_views: async () => ({}),
      }};
      document.body.prepend(Object.assign(document.createElement('div'), {id: 'shell'}));
    }''')
    framework(page)
    page.evaluate('''()=>{
      window.shell = LexeditorUI.mountShell({host: '#shell', brand: 'LEXEDITOR',
        plugin: {id: 'ff7', name: 'FF7'},
        tabs: [{id: 'items', label: 'Items'}], activeTab: () => 'items',
        navigate: id => calls.push('tab:' + id),
        help: () => calls.push('datamap'), helpTitle: 'Open Data Map',
        info: () => calls.push('info'), infoTitle: 'Open Info'});
      LexeditorUI.finishPluginLoading();
    }''')
    page.wait_for_function('shell.githubWorkspace()')
    page.evaluate('shell.githubWorkspace().show()')
    assert page.locator('.lex-github-workspace:visible').count() == 1
    page.locator('#plugin-data-map').click()
    page.wait_for_function('!shell.githubWorkspace().state.open')
    assert page.locator('.lex-github-workspace:visible').count() == 0
    assert page.evaluate('calls') == ['datamap']
    page.evaluate('shell.githubWorkspace().show()')
    page.locator('#plugin-info').click()
    page.wait_for_function('!shell.githubWorkspace().state.open')
    assert page.locator('.lex-github-workspace:visible').count() == 0
    assert page.evaluate('calls') == ['datamap', 'info']
