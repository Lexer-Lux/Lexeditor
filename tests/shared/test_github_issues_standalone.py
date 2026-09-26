"""The GitHub issues workspace opens from Home without a game's editor.

Lexer: "make it so i can right click on a game's cover on the main menu to just
go straight to its github page/tab thing in the app. for when i dont have
something installed but need to manage my issues." Home has no editor
header, so the shared workspace gets a slim bar of its own.
"""
from test_shared_ui_feedback import page, framework


def test_open_and_close_issues_without_an_editor(page):
    page.evaluate('''() => { window.pywebview = {api: new Proxy({
      github_repository: async () => ({repository: 'Lexer-Lux/Lexeditor'}),
    }, {get: (target, key) => target[key] || (async () => ({issues: [], labels: [], items: []}))})}; }''')
    framework(page)
    page.evaluate("window.__ws = LexeditorUI.openGitHubIssues('ff8', 'Final Fantasy VIII')")
    page.wait_for_selector('.lex-github-workspace:not([hidden])')
    assert page.locator('.lex-github-standalone-title').inner_text() == 'Final Fantasy VIII issues'
    assert page.evaluate("document.body.dataset.lexGithubOpen") == 'true'
    page.locator('.lex-shell-header.lex-github-standalone button').last.click()
    page.wait_for_timeout(200)
    assert page.locator('.lex-github-workspace').count() == 0
    assert page.locator('.lex-github-standalone').count() == 0
    assert page.evaluate("document.body.dataset.lexGithubOpen") != 'true'
