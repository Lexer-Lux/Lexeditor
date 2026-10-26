"""Help bubbles have one store: the text the caller passes.

A bubble shows exactly the shipped text it was given. There is no
second source: no `.help.` override is read from storage, double-clicking
opens no editor, and none ships through the view defaults.
"""
import json
from pathlib import Path

from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = "Chance that this item drops, in percent."


def test_packaged_view_defaults_carry_no_help_overrides():
    views = json.loads((ROOT / "ui/default_views.json").read_text(encoding="utf-8"))
    help_keys = [key
                 for tabs in views.values()
                 for prefs in (tabs or {}).values()
                 for key in (prefs or {})
                 if ".help." in key]
    assert help_keys == []


def mount_help(page):
    page.evaluate("""shipped => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailPanel({title:'Record', body:[
          LexeditorUI.detailField({label:'Drop rate', help:LexeditorUI.infoHelp(shipped),
            control:LexeditorUI.el('input',{type:'number',value:25})})]}));
    }""", SHIPPED)
    page.wait_for_timeout(200)


def open_help(page):
    page.locator(".lex-field-help .lex-info-help").first.hover()
    page.wait_for_selector(".lex-help-popover", timeout=3000)
    page.wait_for_timeout(150)
    return page.locator(".lex-help-popover").last


def seed_stale_override(page, value):
    # The exact key the deleted rewording path would have read: a digest
    # of the shipped text. A store that reads it shows the stale value.
    page.evaluate("""([shipped, value]) => {
      let hash = 2166136261;
      for (let index = 0; index < shipped.length; index += 1) {
        hash ^= shipped.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
      }
      const key = `fixture-items.help.${(hash >>> 0).toString(16)}.text`;
      localStorage.setItem(key, value);
    }""", [SHIPPED, value])


def test_a_stale_help_override_in_storage_is_ignored(page):
    framework(page)
    mount_shell(page)
    seed_stale_override(page, "A stale rewording.")
    mount_help(page)
    assert open_help(page).evaluate("n=>n.textContent.trim()") == SHIPPED


def test_a_stale_empty_override_hides_no_marker(page):
    framework(page)
    mount_shell(page)
    seed_stale_override(page, "")
    mount_help(page)
    assert page.locator(".lex-field-help .lex-info-help").count() == 1
    assert open_help(page).evaluate("n=>n.textContent.trim()") == SHIPPED


def test_double_clicking_a_bubble_opens_no_editor(page):
    framework(page)
    mount_shell(page)
    mount_help(page)
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    page.wait_for_timeout(200)
    assert page.locator(".lex-help-edit").count() == 0
    assert page.evaluate("window.savedCalls") == []
