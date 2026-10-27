"""Help bubbles have one store: the property definition.

A bubble shows exactly the shipped text it was given. There is no
second source: no `.help.` override is read from storage, and none
ships through the view defaults. Double-clicking a bubble whose marker
carries its definition key edits that definition through the plugin
service; a bubble with no key is interface text, so it says so.
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


def mount_help(page, key=None):
    page.evaluate("""([shipped, key]) => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailPanel({title:'Record', body:[
          LexeditorUI.detailField({label:'Drop rate',
            help:LexeditorUI.infoHelp(shipped, key ? {helpKey: key} : {}),
            control:LexeditorUI.el('input',{type:'number',value:25})})]}));
    }""", [SHIPPED, key])
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


def test_double_clicking_a_keyless_bubble_explains_and_opens_nothing(page):
    framework(page)
    mount_shell(page)
    mount_help(page)
    calls = []
    page.route("**/api/annotation-help", lambda route: (calls.append(1), route.fulfill(status=200, body="{}")))
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    page.wait_for_timeout(300)
    assert page.locator(".lex-prompt-dialog").count() == 0
    assert calls == []
    assert "not an annotation file" in page.locator(".lex-toast").last.inner_text()


def test_double_clicking_a_keyed_bubble_edits_through_the_plugin_service(page):
    framework(page)
    mount_shell(page)
    mount_help(page, key="EquipParamGoods/dropRate")
    bodies = []
    def serve(route):
        bodies.append(route.request.post_data_json)
        route.fulfill(status=200, content_type="application/json",
                      body='{"saved": true, "file": "EQUIP_PARAM_GOODS_ST"}')
    page.route("**/api/annotation-help", serve)
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.get_by_role("textbox", name="Help text")
    editor.wait_for()
    assert editor.input_value() == SHIPPED
    editor.fill("Chance that the enemy drops this item, in percent.")
    page.locator(".lex-prompt-dialog").get_by_role("button", name="Save").click()
    page.wait_for_timeout(300)
    assert bodies == [{"key": "EquipParamGoods/dropRate",
                        "text": "Chance that the enemy drops this item, in percent."}], bodies
    assert "EQUIP_PARAM_GOODS_ST" in page.locator(".lex-toast").last.inner_text()
    assert open_help(page).evaluate("n=>n.textContent.trim()") == \
        "Chance that the enemy drops this item, in percent."


def test_a_failed_help_save_keeps_the_old_text(page):
    framework(page)
    mount_shell(page)
    mount_help(page, key="EquipParamGoods/dropRate")
    page.route("**/api/annotation-help", lambda route: route.fulfill(
        status=400, content_type="application/json", body='{"error": "Help is one paragraph."}'))
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.get_by_role("textbox", name="Help text")
    editor.wait_for()
    editor.fill("Two\nparagraphs.")
    page.locator(".lex-prompt-dialog").get_by_role("button", name="Save").click()
    page.wait_for_timeout(300)
    assert "one paragraph" in page.locator(".lex-toast").last.inner_text()
    assert open_help(page).evaluate("n=>n.textContent.trim()") == SHIPPED
