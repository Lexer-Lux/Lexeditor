"""Undo and redo run newest-first across label and record history.

Renames and layout changes live on the label stack, value edits on the
plugin's stack. The shell used to drain every label entry before touching
a value edit, so a pile of rearranges swallowed the button and a value
edit never came back. Every entry carries a tick from one shared clock,
and the newest top wins.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import label_of, mount_shell, rename

STUB = """() => {
  window.stub = {undoStack: [], redoStack: [],
    get canUndo(){ return this.undoStack.length > 0; },
    get canRedo(){ return this.redoStack.length > 0; },
    undone: [], redone: [],
    async undo(){ const entry = this.undoStack.pop(); if (!entry) return false;
      this.redoStack.push(entry); this.undone.push(entry.id); return true; },
    async redo(){ const entry = this.redoStack.pop(); if (!entry) return false;
      this.undoStack.push(entry); this.redone.push(entry.id); return true; },
    push(id){ this.undoStack.push({id, at: LexeditorUI.nextHistoryTick()}); }};
}"""


def setup(page, history=False):
    framework(page)
    mount_shell(page, history=history)
    page.evaluate(STUB)


def test_newer_value_undoes_before_older_rename(page):
    setup(page)
    rename(page, "items", "Gear")
    page.evaluate("window.stub.push('v1')")
    assert page.evaluate("LexeditorUI.undoNewest(window.stub)") is True
    assert page.evaluate("window.stub.undone") == ["v1"]
    assert label_of(page, "items") == "Gear"


def test_newer_rename_undoes_before_older_value(page):
    setup(page)
    page.evaluate("window.stub.push('v1')")
    rename(page, "items", "Gear")
    assert page.evaluate("LexeditorUI.undoNewest(window.stub)") is True
    assert page.evaluate("window.stub.undone") == []
    assert label_of(page, "items") == "Items"


def test_redo_runs_newest_first_too(page):
    setup(page)
    rename(page, "items", "Gear")
    page.evaluate("window.stub.push('v1')")
    assert page.evaluate("LexeditorUI.undoNewest(window.stub)") is True
    assert page.evaluate("LexeditorUI.undoNewest(window.stub)") is True
    assert page.evaluate("window.stub.undone") == ["v1"]
    assert label_of(page, "items") == "Items"
    assert page.evaluate("LexeditorUI.redoNewest(window.stub)") is True
    assert page.evaluate("window.stub.redone") == ["v1"]
    assert label_of(page, "items") == "Items"
    assert page.evaluate("LexeditorUI.redoNewest(window.stub)") is True
    assert label_of(page, "items") == "Gear"


def test_empty_histories_undo_to_false(page):
    setup(page)
    assert page.evaluate("LexeditorUI.undoNewest(window.stub)") is False
    assert page.evaluate("LexeditorUI.redoNewest(window.stub)") is False


def test_ctrl_z_fires_exactly_one_undo(page):
    # With an observed history the shell used to bind Ctrl+Z twice: the
    # observer's capture handler plus the shortcut dispatcher. One press
    # undid two entries.
    setup(page, history=True)
    rename(page, "items", "Gear")
    rename(page, "items", "Tools")
    page.evaluate("document.activeElement?.blur()")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(500)
    assert label_of(page, "items") == "Gear"


def test_ctrl_z_in_free_text_leaves_app_history_alone(page):
    # The observer's binding never skipped free text: typing in a box and
    # pressing Ctrl+Z undid the app instead of the typing.
    setup(page, history=True)
    rename(page, "items", "Gear")
    page.evaluate("""() => {
      document.body.insertAdjacentHTML('beforeend', '<textarea id="note">hello</textarea>');
      document.querySelector('#note').focus();
    }""")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(500)
    assert label_of(page, "items") == "Gear"


def test_ctrl_z_in_a_number_field_undoes_the_app(page):
    setup(page)
    rename(page, "items", "Gear")
    page.evaluate("""() => {
      document.body.insertAdjacentHTML('beforeend',
        '<input type="number" id="amount" data-field-key="amount" value="3">');
      document.querySelector('#amount').focus();
    }""")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(500)
    assert label_of(page, "items") == "Items"
