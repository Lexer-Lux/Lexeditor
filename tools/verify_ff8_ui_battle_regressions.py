"""Browser regression checks for search focus and the FF8 FFNx settings header.

Uses the real shared component code in Chromium, with only its surrounding
chrome stubbed. No game files, installed game, or network are needed.
Install test dependency: python -m pip install playwright
Install browser when needed: python -m playwright install chromium
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def component_source(framework: str) -> str:
    # Keep the component and pager implementations exactly as shipped. Only
    # unrelated shell/desktop setup is excluded from this isolated fixture.
    start = framework.index("  const bottomSearchChangeTimers = new Map();")
    end = framework.index("  // Editing chrome that stays live", start)
    platform = framework.index("  const platformConfigView = options =>")
    platform_end = framework.index("\n  window.LexeditorUI =", platform)
    return framework[start:end] + "\n" + framework[platform:platform_end]


FIXTURE = r'''
const element = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === undefined || value === null) continue;
    if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else if (name === "text") node.textContent = value;
    else if (["checked", "disabled", "hidden", "open"].includes(name)) node[name] = !!value;
    else node.setAttribute(name, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child !== undefined && child !== null && child !== false) node.append(child);
  }
  return node;
};
const searchIcon = () => element("span", {}, "Search");
const formatNumber = value => String(value);
const detailField = options => element("label", {class: options.className}, options.label, options.control);
const infoHelp = value => element("span", {}, value);
'''

PAGE = r'''
window.query = "";
window.changes = [];
window.delay = 0;
window.render = () => {
  const search = bottomSearch({key: "test-records", value: window.query,
    delay: window.delay, change: value => {
      window.query = value;
      window.changes.push(value);
      window.render();
    }});
  document.getElementById("fixture").replaceChildren(search);
};
window.renderPlatform = (showHeader = false) => {
  const config = {available: true, runtime: "FFNx", message: "Setup summary", path: "FFNx.toml",
    sections: [{label: "Display", fields: [
      {id: "fullscreen", key: "fullscreen", label: "Fullscreen", kind: "boolean", value: true, description: "Window mode"},
      {id: "width", key: "width", label: "Width", kind: "integer", value: 640, minimum: 1, maximum: 4096, description: "Screen width"}
    ]}]};
  document.getElementById("fixture").replaceChildren(platformConfigView({config, showHeader,
    query: "", search: value => { window.platformQuery = value; }, change: () => {}}));
};
window.render();
'''


def run(framework_path: Path, *, executable: str | None = None) -> None:
    from playwright.sync_api import sync_playwright

    framework = framework_path.read_text(encoding="utf-8")
    editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert "platformConfigView({config:state.platformConfig,showHeader:false," in editor
    with sync_playwright() as playwright:
        kwargs = {"headless": True}
        if executable:
            kwargs["executable_path"] = executable
        browser = playwright.chromium.launch(**kwargs)
        try:
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content('<main id="fixture"></main><button id="elsewhere">Other control</button>')
            page.add_script_tag(content=FIXTURE + component_source(framework) + PAGE)
            selector = '[data-lex-bottom-search="test-records"]'
            page.locator(selector).focus()
            text = "Fastitocalon HP level 255"
            page.keyboard.type(text, delay=0)
            assert page.locator(selector).input_value() == text
            assert page.evaluate("window.query") == text
            assert page.evaluate("window.changes.length") == len(text)
            assert page.locator(selector).evaluate("node => document.activeElement === node")
            print("PASS rapid zero-delay typing retains every character and immediate filtering")

            page.locator(selector).evaluate("(node, start) => node.setSelectionRange(start, start + 2)", text.index("HP"))
            page.keyboard.type("GF", delay=0)
            assert page.locator(selector).input_value() == "Fastitocalon GF level 255"
            assert page.locator(selector).evaluate("node => node.selectionStart") == text.index("HP") + 2
            page.keyboard.press("Backspace")
            assert page.locator(selector).input_value() == "Fastitocalon G level 255"
            print("PASS replacement and backspace preserve the caret across pager rebuilds")

            page.evaluate('''() => {
              window.query = ""; window.render();
              const input = document.querySelector('[data-lex-bottom-search]');
              input.focus(); window.composingInput = input;
              input.dispatchEvent(new CompositionEvent("compositionstart", {bubbles: true}));
              input.value = "召";
              input.dispatchEvent(new InputEvent("input", {bubbles: true, isComposing: true}));
            }''')
            assert page.evaluate("window.composingInput.isConnected")
            assert page.evaluate("window.query") == ""
            page.evaluate('''() => {
              const input = window.composingInput;
              input.value = "召喚";
              input.dispatchEvent(new CompositionEvent("compositionend", {bubbles: true, data: "召喚"}));
            }''')
            assert page.evaluate("window.query") == "召喚"
            print("PASS IME composition is retained and applied at composition end")

            page.evaluate("window.query = ''; window.delay = 50; window.render();")
            page.locator(selector).focus()
            page.keyboard.type("pending", delay=0)
            page.evaluate("document.getElementById('fixture').replaceChildren();")
            page.locator("#elsewhere").focus()
            page.wait_for_timeout(120)
            assert page.evaluate("window.query") == ""
            assert page.locator("#elsewhere").evaluate("node => document.activeElement === node")
            assert page.locator(selector).count() == 0
            print("PASS delayed searches cannot resurrect a page or steal focus after navigation")

            page.evaluate("window.renderPlatform(false)")
            assert page.locator(".lex-platform-config-head").count() == 0
            assert page.locator(".lex-platform-config-field").count() == 2
            search = page.locator('[data-lex-bottom-search="platform-FFNx"]')
            search.focus()
            page.keyboard.type("fullscreen", delay=0)
            assert page.locator(".lex-platform-config-field:visible").count() == 1
            assert page.locator(".lex-platform-config-field:visible").inner_text() == "FULLSCREEN"
            assert page.evaluate("window.platformQuery") == "fullscreen"
            page.evaluate("window.renderPlatform(true)")
            assert page.locator(".lex-platform-config-head").count() == 1
            assert not errors, errors
            print("PASS FFNx header is optional; settings and live filtering remain; other callers retain header")
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", type=Path, default=ROOT / "ui/framework.js")
    parser.add_argument("--browser", default=shutil.which("chromium") or shutil.which("chromium-browser"))
    args = parser.parse_args()
    run(args.framework, executable=args.browser)


if __name__ == "__main__":
    main()
