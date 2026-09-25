"""Rendered browser acceptance for approved FF8 graph formula design A (#299)."""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
from pathlib import Path
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "ff8-graph-design-a"
OUT.mkdir(parents=True, exist_ok=True)

FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")

# Deliberately recreate the old FF8 thick-outline rule. Design A has to beat
# the actual rejected treatment, not merely the framework default.
FIXTURE_CSS = r"""
:root {
  --lex-bg:#000; --lex-panel:#626262; --lex-panel-2:#4f4f4f;
  --lex-border:#929292; --lex-text:#fff; --lex-muted:#d0d0d0;
  --lex-accent:#aa2432; --lex-highlight:#fff;
  --lex-font:"FF8 Menu","Arial Narrow",sans-serif;
  --lex-math-font:var(--lex-font);
  --lex-heading-font:"FF8 Menu","Arial Narrow",sans-serif;
}
html,body{margin:0;min-height:100%;background:#000;color:#fff}
body{padding:12px;font-family:var(--lex-font)}
#mount{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.ff8-character-curve{min-width:0;background:transparent}
.ff8-character-curve .lex-curve-formula{display:none!important}
.ff8-character-curve .lex-curve-path-formula{
  display:block;fill:#f5f5f5;stroke:#222;stroke-width:4.5px;paint-order:stroke fill
}
.ff8-character-curve .lex-curve-svg{background:#303030}
@media(max-width:700px){#mount{grid-template-columns:1fr}}
"""

MOUNT_SCRIPT = r"""() => {
  const {curveEditor, el} = LexeditorUI;
  const number = (name, value, min, max) => el("input", {
    type:"number", value, min, max, step:1, "aria-label":name
  });

  const hpA=number("HP A",2,0,100), hpB=number("HP B",50,1,255), hpC=number("HP C",100,0,9999);
  const hp=curveEditor({
    title:"HP",className:"ff8-character-curve",
    variables:[{label:"A",control:hpA},{label:"B",control:hpB},{label:"C",control:hpC}],
    domain:{min:1,max:100},range:{min:0,max:2600},graphLabel:"Fixture HP curve",
    evaluate:L=>Number(hpC.value)+L*Number(hpA.value)+Math.floor(10*L*L/Number(hpB.value)),
    formula:LexeditorUI.mathFormula("HP(L) = C + L * A + floor(10 * L^2 / B)")
  });

  const strA=number("STR A",40,0,255), strB=number("STR B",2,1,255);
  const strC=number("STR C",100,0,255), strD=number("STR D",100,1,255);
  const strength=curveEditor({
    title:"STR",className:"ff8-character-curve ff8-enemy-curve",
    variables:[{label:"A",control:strA},{label:"B",control:strB},{label:"C",control:strC},{label:"D",control:strD}],
    domain:{min:1,max:100},range:{min:0,max:180},graphLabel:"Fixture enemy strength curve",
    evaluate:L=>Math.floor(L*Number(strA.value)/40)+Math.floor(L/(4*Number(strB.value)))
      +Math.floor(Number(strC.value)/4)+Math.floor(L*L/(8*Number(strD.value))),
    formula:LexeditorUI.mathFormula("STR(L)=⌊L·A/40⌋+⌊L/(4·B)⌋+⌊C/4⌋+⌊L²/(8·D)⌋")
  });
  document.querySelector("#mount").replaceChildren(hp,strength);
}"""

METRICS_SCRIPT = r"""() => [...document.querySelectorAll('.ff8-character-curve')].map(card => {
  const label=card.querySelector('.lex-curve-plot > .lex-math-formula');
  const old=card.querySelector('.lex-curve-path-formula');
  const endpoint=card.querySelector('.lex-curve-range-value');
  const fraction=label?.querySelector('mfrac');
  const numerator=fraction?.children[0];
  const denominator=fraction?.children[1];
  const power=label?.querySelector('msup');
  const style=label && getComputedStyle(label);
  const endpointStyle=endpoint && getComputedStyle(endpoint);
  const box=label?.getBoundingClientRect();
  const transform=label.style.transform;
  label.style.transform='none';
  const numeratorBox=numerator?.getBoundingClientRect(),denominatorBox=denominator?.getBoundingClientRect();
  const powerBase=power?.children[0].getBoundingClientRect(), powerExponent=power?.children[1].getBoundingClientRect();
  label.style.transform=transform;
  return {
    title:card.dataset.curveTitle,
    text:label?.textContent||'',
    visible:!!box&&box.width>0&&box.height>0,
    transparent:style?.backgroundColor==='rgba(0, 0, 0, 0)',
    weight:style?.fontWeight||'',
    shadow:style?.textShadow||'',
    font:style?.fontFamily||'',
    fontSize:Number.parseFloat(style?.fontSize||'0'),
    // Each term of the equation carries its own tilt now, so the tilt is read
    // from the terms. The element that holds them has no angle of its own.
    angles:[...card.querySelectorAll('.lex-curve-plot > .lex-math-formula .lex-curve-math-atom')]
      .map(node=>node.style.getPropertyValue('--lex-formula-angle')),
    oldDisplay:old?getComputedStyle(old).display:'',
    // Use local box geometry. getBoundingClientRect() is screen-space and the
    // whole equation is intentionally rotated with the curve, so screen Y is
    // not a valid test for numerator/denominator stacking.
    fractionStacked:!!numerator&&!!denominator
      && denominatorBox.top>=numeratorBox.bottom-1,
    fractionRule:fraction ? 1 : 0,
    hasPower:!!power,
    powerTop:powerExponent&&powerBase ? powerExponent.top-powerBase.top : 0,
    endpointWeight:endpointStyle?.fontWeight||'',
    endpointFilter:endpointStyle?.filter||'',
    endpointStroke:endpointStyle?.stroke||'',
    insideViewport:!!box&&box.left>=-2&&box.right<=innerWidth+2,
  };
})"""

results=[]
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(
        executable_path=shutil.which("chromium") or None,
        headless=True,args=["--no-sandbox"],
    )
    try:
        for width,height in ((900,620),(620,760)):
            errors=[]
            page=browser.new_page(viewport={"width":width,"height":height})
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.route('http://fixture/**',lambda route:route.fulfill(body='<html></html>',content_type='text/html'))
            page.goto('http://fixture/')
            page.set_content(
                "<!doctype html><html><head>"
                '<meta charset="utf-8"><base href="http://127.0.0.1:9/">'
                '<link id="lex-ff8-graph-design-a-style">'
                f"<style>{FRAMEWORK_CSS}</style><style>{FIXTURE_CSS}</style>"
                '</head><body><main id="mount"></main></body></html>',
                wait_until="domcontentloaded",
            )
            page.add_script_tag(content=FRAMEWORK_JS)
            page.evaluate(MOUNT_SCRIPT)
            page.wait_for_selector(".lex-curve-plot > .lex-math-formula")
            page.wait_for_timeout(350)

            metrics=page.evaluate(METRICS_SCRIPT)
            screenshot=OUT/f"graph-design-a-{width}.png"
            page.screenshot(path=str(screenshot),full_page=True)
            assert len(metrics)==2,(width,metrics)
            for item in metrics:
                assert item["visible"],(width,item)
                assert item["transparent"],(width,item)
                assert item["weight"] in ("700","bold"),(width,item)
                assert item["shadow"]!="none",(width,item)
                assert "FF8 Menu" in item["font"],(width,item)
                assert item["fontSize"]>=7.49,(width,item)
                assert item["angles"],(width,item)
                assert all(angle.endswith("deg") for angle in item["angles"]),(width,item)
                assert item["oldDisplay"]=="none",(width,item)
                assert item["fractionStacked"],(width,item)
                assert item["fractionRule"]>=1,(width,item)
                assert item["hasPower"],(width,item)
                assert item["powerTop"]<0,(width,item)
                assert item["endpointWeight"] in ("700","bold"),(width,item)
                assert "drop-shadow" in item["endpointFilter"],(width,item)
                assert item["endpointStroke"]=="none",(width,item)
                assert item["insideViewport"],(width,item)

            before=page.locator('.ff8-character-curve[data-curve-title="HP"] .lex-curve-line').get_attribute("d")
            page.locator('.ff8-character-curve[data-curve-title="HP"]').hover()
            page.get_by_label("HP A",exact=True).fill("8")
            page.wait_for_timeout(300)
            after=page.locator('.ff8-character-curve[data-curve-title="HP"] .lex-curve-line').get_attribute("d")
            assert before!=after,(width,"curve did not redraw")
            assert page.locator(".lex-curve-plot > .lex-math-formula").count()==2,(width,"formula overlay duplicated")
            assert not errors,(width,errors)

            results.append({"viewport":[width,height],"curves":metrics,"redraw":"passed","screenshot":screenshot.name})
            page.close()
    finally:
        browser.close()

(OUT/"results.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
print(json.dumps(results,indent=2))
