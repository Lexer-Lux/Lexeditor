"""A rename toast claims "shipped" only when the save shipped.

The name is always kept on this device; the shared default is a second
write that can fail (no host, no rights). The toast says which happened.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import label_of, rename


def mount(page, saved=True):
    page.evaluate("""saved => {
      window.savedCalls = [];
      window.pywebview = {api: {
        lexeditor_settings: async () => ({developerMode: true}),
        save_default_view: async (...args) => {
          window.savedCalls.push(args);
          if (!saved) throw new Error('denied');
          return {saved: true};
        },
      }};
      document.body.insertAdjacentHTML('afterbegin','<div id="shell"></div>');
      window.shell = LexeditorUI.mountShell({host:'#shell',brand:'LEXEDITOR',
        plugin:{id:'fixture',name:'Fixture'},
        tabs:[{id:'items',label:'Items'},{id:'magic',label:'Magic'}],
        activeTab:()=> 'items', navigate(){}});
    }""", saved)
    page.wait_for_timeout(300)


def toast(page):
    return page.locator(".lex-toast-stack > .lex-toast").last.inner_text()


def test_a_saved_rename_says_shipped(page):
    framework(page)
    mount(page, saved=True)
    rename(page, "items", "Gear")
    assert label_of(page, "items") == "Gear"
    assert toast(page) == "Gear is now the shipped name."


def test_a_failed_save_says_this_device_but_keeps_the_name(page):
    framework(page)
    mount(page, saved=False)
    rename(page, "items", "Gear")
    assert label_of(page, "items") == "Gear"
    assert toast(page) == "Gear is saved on this device."
    assert page.evaluate('localStorage.getItem("fixture-items.label")') == "Gear"
    assert page.evaluate("window.savedCalls").__len__() == 1
