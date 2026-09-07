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
            print("NEUTRAL-HARNESS page errors:", self.errors)
        except Exception as diagnostic_error:
            print("NEUTRAL-HARNESS diagnostic failed:", diagnostic_error)
        raise

target.PageTests.test_kernel_api_failure_keeps_auxiliary_tabs_and_runtime_detection = _diagnostic_kernel_failure

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2)
