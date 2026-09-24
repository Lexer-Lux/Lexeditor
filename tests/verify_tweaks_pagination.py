"""Headless reachability checks for the shared Tweaks pager."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
# Realistic RDR2-shaped groups: settings sections of short subs, paged with
# RDR2's own options. Tall groups split between subs, and one Map-Icons-long
# sub splits between its own fields, so every group and control stays
# reachable through the pager at every size.
FIXTURE="""() => {
  const u = LexeditorUI;
  const host = document.createElement('div');
  let cards = '';
  for (let i = 0; i < 19; i++) {
    let subs = '';
    for (let s = 0; s < 6; s++) {
      const rows = (i === 7 && s === 2) ? 12 : 3;
      let fields = '';
      for (let f = 0; f < rows; f++) {
        fields += `<div class="settings-field">`
          + `<div class="settings-field-label">Setting ${i}-${s}-${f}</div>`
          + `<div class="settings-field-control"><input aria-label="Setting ${i}-${s}-${f}" value="${i}-${s}-${f}"></div>`
          + `</div>`;
      }
      subs += `<div class="settings-sub"><h3>Sub ${i}-${s}</h3><div class="settings-fields">${fields}</div></div>`;
    }
    cards += `<section class="settings-section" data-card="${i}"><h2>Group ${i}</h2><div class="settings-subs">${subs}</div></section>`;
  }
  host.innerHTML = cards;
  document.querySelector('main').append(u.settingsColumns([...host.children], {columnMajor: true, strictColumns: true}));
}"""
EXPECTED={f'Setting {i}-{s}-{f}' for i in range(19) for s in range(6) for f in range(12 if (i==7 and s==2) else 3)}
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page()
 page.route("http://fixture/**",lambda route:route.fulfill(body="<html></html>",content_type="text/html"))
 page.goto("http://fixture/")
 css=(root/"ui/framework.css").read_text(encoding="utf-8")
 rdr_css=(root/"plugins/rdr2/editor.css").read_text(encoding="utf-8")
 page.set_content('<style>'+rdr_css+css+'</style><header class="lex-shell-header" style="height:130px;flex-shrink:0">Tweaks</header><main></main>')
 page.add_script_tag(path=str(root/"ui/framework.js"))
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.evaluate(FIXTURE)
 for width,height,zoom in [(1280,720,1),(800,600,1),(800,600,1.5),(1920,1080,.75)]:
  page.set_viewport_size({'width':width,'height':height});page.evaluate('(z)=>{document.body.style.zoom=z;document.body.style.height=`${100/z}dvh`}',zoom)
  page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
  assert not errors,errors
  first=page.get_by_role('button',name='First page',exact=True)
  if first.is_enabled():first.click()
  page.get_by_label('Setting 0-0-0',exact=True).fill('changed')
  seen=set();labels=set()
  while True:
   seen.update(page.locator('[data-card]:visible').evaluate_all('(nodes)=>nodes.map(n=>+n.dataset.card)'))
   for label in page.locator('[data-card]:visible input').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("aria-label"))'):
    field=page.locator('[data-card]:visible').locator(f'input[aria-label="{label}"]')
    field.scroll_into_view_if_needed()
    box=field.bounding_box();assert box['y']>=0 and box['y']+box['height']<=height,(width,height,zoom,label,box)
    labels.add(label)
   pager=page.locator('.lex-tweaks-pages').bounding_box();assert pager['y']+pager['height']<=height+1,(zoom,pager)
   if not page.get_by_role('button',name='Next page',exact=True).is_enabled():break
   page.get_by_role('button',name='Next page',exact=True).click()
  assert seen==set(range(19)),seen
  assert labels==EXPECTED,len(labels)
  assert page.get_by_label('Setting 0-0-0',exact=True).input_value()=='changed'
  assert not errors,errors
 print('PASS: every group, tall final controls, and pager reachable at four viewport/scale combinations')
 browser.close()
