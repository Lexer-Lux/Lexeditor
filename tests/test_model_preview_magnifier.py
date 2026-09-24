"""R2-2: the preview magnifier reads on any thumbnail in any theme.

The ring used to inherit the theme accent, so on RDR2's dark art it was a
dark-red ring on a dark thumbnail: effectively no magnifier. It is now a
white ring with a dark halo, which reads on light and dark art alike.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_magnifier_ring_is_light_with_halo_despite_dark_accent():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 800})
            page.route("http://fixture/**", lambda r: r.fulfill(
                body="<main></main>", content_type="text/html"))
            page.goto("http://fixture/")
            page.add_style_tag(path=str(ROOT / "ui/framework.css"))
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            page.evaluate("""() => {
              const panel = LexeditorUI.detailPanel({title: "Example", body: "Fields"});
              panel.querySelector(".lex-detail-panel-icon")?.remove();
              const icon = document.createElement("div");
              icon.className = "lex-detail-panel-icon";
              icon.style.color = "#a92b20";
              icon.append(LexeditorUI.iconSlot({message: "Icon"}));
              panel.querySelector(".lex-detail-panel-heading").prepend(icon);
              LexeditorUI.attachModelPreview(panel, {
                content: () => LexeditorUI.modelStage({message: "Model fixture"}),
              });
              document.querySelector("main").append(panel);
            }""")
            trigger = page.get_by_role("button", name="Open model preview", exact=True)
            assert page.locator(".lex-model-preview-close").evaluate(
                "n=>getComputedStyle(n).opacity") == "0"
            assert page.locator(".lex-model-preview-close svg circle").evaluate(
                "n=>getComputedStyle(n).stroke") == "rgb(255, 255, 255)"
            assert "drop-shadow" in page.locator(".lex-model-preview-close").evaluate(
                "n=>getComputedStyle(n).filter")
            trigger.hover()
            page.wait_for_timeout(250)
            assert page.locator(".lex-model-preview-close").evaluate(
                "n=>getComputedStyle(n).opacity") == "1"
            trigger.click()
            assert page.locator(".lex-model-preview-drawer").is_visible()
        finally:
            browser.close()
