"""Rendered checks for the shared Blank field metadata rail."""

import json
import sys
import time

ROOT = r"C:\Lexeditor"
sys.path.insert(0, ROOT)

from games.blank.plugin import BlankSession  # noqa: E402
from tools.verify_panel_layout_visual_46 import browser_session, close_browser, wait_eval  # noqa: E402


def main() -> int:
    profile, browser, cdp = browser_session()
    try:
        with BlankSession() as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "document.body.dataset.lexPlugin==='blank'&&!!document.querySelector('.blank-layout')", 30)
            results = []
            for width, height in ((1600, 900), (800, 600)):
                cdp.call("Emulation.setDeviceMetricsOverride", {
                    "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
                })
                time.sleep(.25)
                result = cdp.eval("""(()=>{
                  const field=[...document.querySelectorAll('.blank-detail .lex-detail-field')]
                    .find(node=>node.dataset.lexType==='INT'&&node.querySelector('input[type=number]'));
                  const rail=field.querySelector('.lex-field-type-rail');
                  const name=rail.querySelector('.lex-field-type-name');
                  const range=rail.querySelector('.lex-field-type-range');
                  const help=rail.querySelector('.lex-info-help');
                  const stacks=[...document.querySelectorAll('.blank-detail .lex-detail-field')]
                    .filter(node=>node.querySelectorAll('.lex-reference-tag').length>1)
                    .map(node=>[...node.querySelectorAll('.lex-reference-tag')].map(tag=>tag.getBoundingClientRect().width));
                  field.querySelector('input').focus();
                  return {width:innerWidth,writing:getComputedStyle(name).writingMode,
                    rotation:getComputedStyle(name).transform,background:getComputedStyle(name).backgroundColor,
                    nameOpacity:getComputedStyle(name).opacity,rangeOpacity:getComputedStyle(range).opacity,
                    visible:[name,range].filter(node=>parseFloat(getComputedStyle(node).opacity)>.9).length,
                    helpSize:[help.getBoundingClientRect().width,help.getBoundingClientRect().height],
                    helpCursor:getComputedStyle(help).cursor,stacks};
                })()""")
                time.sleep(.25)
                focused = cdp.eval("""(()=>{const field=[...document.querySelectorAll('.blank-detail .lex-detail-field')].find(node=>node.dataset.lexType==='INT'&&node.querySelector('input[type=number]')),rail=field.querySelector('.lex-field-type-rail'),name=rail.querySelector('.lex-field-type-name'),range=rail.querySelector('.lex-field-type-range');return {nameOpacity:getComputedStyle(name).opacity,rangeOpacity:getComputedStyle(range).opacity,visible:[name,range].filter(node=>parseFloat(getComputedStyle(node).opacity)>.9).length}})()""")
                result.update(focused)
                assert result["writing"] == "horizontal-tb", result
                assert result["rotation"].startswith("matrix(0, -1, 1, 0"), result
                assert result["background"] == "rgba(0, 0, 0, 0)", result
                assert result["nameOpacity"] == "0" and result["rangeOpacity"] == "1" and result["visible"] == 1, result
                assert result["helpSize"][0] >= 18 and result["helpSize"][1] >= 18 and result["helpCursor"] == "pointer", result
                assert all(len(set(widths)) == 1 and widths[0] >= 22 for widths in result["stacks"]), result
                results.append(result)
            cdp.eval("document.querySelector('[data-tab=two]').click()")
            wait_eval(cdp, "!!document.querySelector('.blank-detail')", 10)
            cdp.eval("document.querySelector('.blank-table [data-column-key=\\\"value\\\"] .lex-column-sort').click()")
            time.sleep(.25)
            sort = cdp.eval("""(()=>{const field=[...document.querySelectorAll('.blank-detail .lex-detail-field')].find(x=>x.querySelector('.lex-detail-field-label')?.textContent.trim()==='VALUE'),rail=field.querySelector('.lex-field-type-rail'),box=rail.getBoundingClientRect(),style=getComputedStyle(rail,'::after');return{sort:field.dataset.lexSort,railCenter:box.left+box.width/2,triangleContent:style.content,triangleLeft:style.left,triangleTransform:style.transform}})()""")
            assert sort["sort"] == "asc" and sort["triangleContent"] == '"▲"', sort
            assert sort["triangleLeft"] == "11px" and "-4.5, -4.5" in sort["triangleTransform"], sort
            results.append({"detailSort": sort})
            print(json.dumps(results, indent=2))
    finally:
        close_browser(profile, browser, cdp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
