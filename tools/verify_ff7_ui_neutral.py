"""Run FF7 page-logic tests with the current shared-helper contract facade."""
from __future__ import annotations

import unittest
import verify_ff7_ui as target

# verify_ff7_ui deliberately uses a tiny component facade so its tests isolate
# page/business logic from framework implementation. FF7 now calls these shared
# helpers instead of rebuilding them locally, so the facade must expose their
# public contracts too.
target.FRAMEWORK += r'''
(()=>{
const el=window.LexeditorUI.el;
const subtabBar=o=>el("div",{role:"tablist","aria-label":o.label||"Subsections"},
  ...(o.tabs||[]).map(tab=>el("button",{type:"button",role:"tab","aria-selected":String(tab.id===o.active),onclick:()=>o.change?.(tab.id)},tab.label)));
const tabbedPanel=o=>{
  const active=(o.tabs||[]).find(tab=>tab.id===o.active);
  return el("section",{},
    subtabBar({tabs:o.tabs,active:o.active,label:o.label,change:o.change}),
    el("section",{role:"tabpanel","aria-label":active?.label||"Panel"},o.content));
};
Object.assign(window.LexeditorUI,{
  readonlyField:value=>el("span",{},String(value??"")),
  infoIcon:()=>el("span",{"aria-hidden":"true"},"i"),
  integrationStatus:value=>el("span",{},String(value??"")),
  subtabBar,
  tabbedPanel,
});
})();
'''

_original_kernel_failure = target.PageTests.test_kernel_api_failure_keeps_auxiliary_tabs_and_runtime_detection

def _diagnostic_kernel_failure(self):
    try:
        _original_kernel_failure(self)
    except Exception:
        try:
            print("NEUTRAL-HARNESS state.tab:", self.page.evaluate("state.tab"))
            print("NEUTRAL-HARNESS state.saving:", self.page.evaluate("state.saving"))
            print("NEUTRAL-HARNESS platformLoading:", self.page.evaluate("state.platformLoading"))
            print("NEUTRAL-HARNESS main text:", self.page.locator("main").inner_text())
            print("NEUTRAL-HARNESS buttons:", self.page.locator("main button").all_inner_texts())
            print("NEUTRAL-HARNESS reload DOM:", self.page.evaluate("""()=>{
              const b=[...document.querySelectorAll('main button')].find(e=>e.textContent.trim()==='Reload settings');
              if(!b)return null;
              const r=b.getBoundingClientRect(),s=getComputedStyle(b),chain=[];
              for(let n=b;n;n=n.parentElement){chain.push({tag:n.tagName,role:n.getAttribute('role'),hidden:n.hidden,ariaHidden:n.getAttribute('aria-hidden'),inert:n.inert,display:getComputedStyle(n).display,visibility:getComputedStyle(n).visibility,opacity:getComputedStyle(n).opacity});if(n.tagName==='MAIN')break}
              return {disabled:b.disabled,hidden:b.hidden,ariaHidden:b.getAttribute('aria-hidden'),rect:{x:r.x,y:r.y,width:r.width,height:r.height},display:s.display,visibility:s.visibility,opacity:s.opacity,offsetParent:!!b.offsetParent,chain};
            }"""))
            print("NEUTRAL-HARNESS role count:", self.page.get_by_role("button", name="Reload settings", exact=True).count())
            print("NEUTRAL-HARNESS page errors:", self.errors)
        except Exception as diagnostic_error:
            print("NEUTRAL-HARNESS diagnostic failed:", diagnostic_error)
        raise

target.PageTests.test_kernel_api_failure_keeps_auxiliary_tabs_and_runtime_detection = _diagnostic_kernel_failure

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2)
