"""FF8's enemy AI view opens without building every dropdown's options.

Every instruction used to carry a full opcode catalogue and every branch a list
of every instruction: twenty-five thousand <option>s and six seconds of frozen
window for one enemy. Selects now hold their current choice until used.
"""
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

OPEN_AI = """(()=>{const button=document.querySelector('[aria-label="Enemy AI scripts"] [role="tab"]');
const started=performance.now();button.click();
return new Promise(done=>requestAnimationFrame(()=>setTimeout(()=>done({
  ms:performance.now()-started,
  instructions:document.querySelectorAll('.lex-instruction-row').length,
  options:document.querySelectorAll('.lex-instruction-pane option').length}))))})()"""


def main():
    server = create_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/api/**", lambda route: route.abort() if route.request.method != "GET" else route.continue_())
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.wait_for_function("typeof state==='object' && !state.booting", timeout=60000)
            page.locator('nav [data-tab="enemies"]').click()
            page.wait_for_selector('[aria-label="Enemy AI scripts"] [role="tab"]')
            result = page.evaluate(OPEN_AI)
            if not result["instructions"]:
                print("No AI instructions in this game data; nothing to check.")
                return
            # A long list holds only its current choice until it is used.
            longest = page.evaluate("Math.max(...[...document.querySelectorAll('.lex-instruction-pane select')].map(s=>s.options.length))")
            assert longest <= 24, longest
            assert result["options"] < 2000, result
            assert result["ms"] < 3000, result
            opcode = page.locator(".enemy-ai-opcode").first
            value = opcode.input_value()
            opcode.dispatch_event("pointerdown")
            filled = page.evaluate("document.querySelector('.enemy-ai-opcode').options.length")
            assert filled > 1, filled
            assert opcode.input_value() == value
            colours = page.evaluate("(o=>[o.backgroundColor,o.color,o.textShadow])(getComputedStyle(document.querySelector('.enemy-ai-opcode option')))")
            assert colours[0] != "rgb(255, 255, 255)" and colours[2] == "none", colours
            assert not errors, errors
            print(f"AI view: {result['instructions']} instructions in {result['ms']:.0f} ms; "
                  f"{result['options']} options until a select is used ({filled} after).")
            browser.close()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
