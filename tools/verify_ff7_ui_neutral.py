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
const originalDetailField=window.LexeditorUI.detailField;
const detailField=o=>o.control instanceof HTMLButtonElement
  ? el("div",{},el("span",{},o.label),o.control)
  : originalDetailField(o);
const subtabBar=o=>el("div",{role:"tablist","aria-label":o.label||"Subsections"},
  ...(o.tabs||[]).map(tab=>el("button",{type:"button",role:"tab","aria-selected":String(tab.id===o.active),onclick:()=>o.change?.(tab.id)},tab.label)));
const tabbedPanel=o=>{
  const active=(o.tabs||[]).find(tab=>tab.id===o.active);
  return el("section",{},
    subtabBar({tabs:o.tabs,active:o.active,label:o.label,change:o.change}),
    el("section",{role:"tabpanel","aria-label":active?.label||"Panel"},o.content));
};
const toggleRow=o=>el("div",{role:"group","aria-label":o.label||"Toggles"},...(o.toggles||[]).map(t=>
  el("label",{},el("input",{type:"checkbox",checked:!!t.checked,disabled:!!t.disabled,"aria-label":t.label,onchange:e=>t.change?.(e.target.checked,e)}),el("span",{},t.label))));
Object.assign(window.LexeditorUI,{
  detailField,
  readonlyField:value=>el("span",{},String(value??"")),
  infoIcon:()=>el("span",{"aria-hidden":"true"},"i"),
  integrationStatus:value=>el("span",{},String(value??"")),
  subtabBar,
  tabbedPanel,
  toggleRow,
});
})();
'''

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2)
