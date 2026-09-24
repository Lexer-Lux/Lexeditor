"""Headless interaction check for the #136 presentation proposal, not game acceptance."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  try:
   page=browser.new_page(viewport={'width':1200,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',lambda r:r.abort());page.set_content((ROOT/'tools/prototypes/rdr2_trinkets/index.html').read_text(encoding='utf-8-sig'))
   expect(page.get_by_role('option')).to_have_count(3)
   assert page.evaluate("ownedTrinkets(sample,{PROVISION_TRINKET_BUCK_ANTLER:-1,PROVISION_TRINKET_FOX_CLAW:0,PROVISION_TALISMAN_BEAR_CLAW:1}).length")==0
   first=page.get_by_role('option').first;first.focus();page.keyboard.press('ArrowDown');assert page.get_by_role('option').nth(1).get_attribute('aria-selected')=='true'
   page.get_by_role('searchbox').fill('fox');expect(page.get_by_role('option')).to_have_count(1)
   page.get_by_role('searchbox').fill('');page.get_by_role('button',name='Show empty example').click();expect(page.get_by_role('heading',name='No trinkets yet')).to_be_visible()
   page.get_by_role('button',name='Show owned example').click();page.keyboard.press('Escape');assert page.evaluate('closed')
   output=ROOT/'out/rdr2-trinket-proposal';output.mkdir(parents=True,exist_ok=True)
   for width in (1200,600):
    page.set_viewport_size({'width':width,'height':800});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output/f'trinkets-{width}.png'),full_page=True)
   assert not errors,errors
  finally:browser.close()
 print('PASS: owned-only filter, unknown counts, talisman exclusion, keyboard selection, search, empty state, back request and responsive proposal')
if __name__=='__main__':main()
