"""RDR2's model preview must be the shared control, not one of its own.

Every plugin opens a model the same way: the Detail panel's heading icon is the
trigger, it becomes the close mark while open, and the model appears in the
drawer that slides over the editing surface. RDR2 used to own the whole thing -
a separate eye button in the item's name line opening a page-wide modal - so a
reader moving between games met a different control in the same situation.

What stays private is the part that has to be: which archive holds the mesh,
whether this machine can read it, and how the geometry is fetched and drawn.
"""
from pathlib import Path


EDITOR = Path(__file__).resolve().parents[1] / "games" / "rdr2" / "editor.html"
FRAMEWORK = Path(__file__).resolve().parents[1] / "ui" / "framework.js"


def test_the_item_panel_has_the_shared_heading_the_control_needs():
    html = EDITOR.read_text(encoding="utf-8")
    # attachModelPreview takes the panel's heading icon; without a real heading
    # there is nothing for it to take, which is why this plugin grew its own.
    assert 'el("div",{class:"lex-detail-panel-heading no-actions"}' in html
    assert 'el("div",{class:"lex-detail-panel-icon"}' in html
    assert 'el("div",{class:"lex-detail-panel-body"})' in html


def test_the_preview_opens_through_the_shared_control():
    html = EDITOR.read_text(encoding="utf-8")
    assert "LexeditorUI.attachModelPreview(pane,{" in html
    assert "attachItemModelPreview(pane,it)" in html
    # The page-wide modal is gone: the preview is drawer content now.
    assert "model-preview-drawer-body" in html
    assert "openPreparedModelPreview" not in html


def test_one_click_on_the_heading_icon_means_one_thing():
    html = EDITOR.read_text(encoding="utf-8")
    # The inventory icon is a button of its own. Left in the trigger slot it
    # opened the icon picker AND the drawer from a single click, so in the
    # detail panel it is shown rather than clicked and its action moves to the
    # actions column beside the acquisition-sources control.
    assert "item-icon-shown" in html
    assert "item-icon-view" in html
    assert 'const iconOptions=asDetail?{showAt:' in html


def test_the_shared_drawer_accepts_a_content_factory():
    # Reading a mesh out of a game archive should not be paid for until someone
    # opens the drawer. A factory is how a plugin says so; before this the
    # framework only understood a ready-made node and silently showed nothing.
    framework = FRAMEWORK.read_text(encoding="utf-8")
    assert "typeof spec.content === 'function' ? spec.content" in framework
