"""Packed Draw Point coordinates, marker selection and map navigation."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
 source=plugin_ui('ff8')
 helpers=source[source.index('  function worldDrawPosition'):source.index('  function worldDrawPointDetail')]
 visual=source[source.index('  function renderWorldVisual'):source.index('  function worldDetail')]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1400,'height':900})
  p.route('http://fixture/',lambda r:r.fulfill(body='<div id="fixture" style="height:800px"></div>',content_type='text/html'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.add_script_tag(content='''const {el,infoHelp,detailPanel}=LexeditorUI;const state={data:{world:{rows:[{kind:'worldSegment',id:0,groupId:0}],drawPoints:[{id:0,drawId:129,x:192,y:24},{id:127,drawId:256,x:0,y:0}],sha256:'fixture'}},selected:{},pages:{},filters:{world:'old'},modOnly:true};function worldTextureDataset(){return 'vanilla'}function worldRow(){return {regionId:0}}function worldSegmentDetail(){return el('div',{},'Details')}function rerenderWorldMap(){window.opened=state.selected.world;document.querySelector('#fixture').replaceChildren(renderWorldVisual())}'''+helpers+visual+"function worldMapPointPreview(){return el('div',{},'Point')};document.querySelector('#fixture').append(renderWorldVisual());")
  assert p.evaluate('''()=>{for(let y=0;y<96;y++)for(let x=0;x<128;x++){const v=worldDrawPosition(worldDrawBytes(x,y));if(v.x!==x||v.y!==y)return false}return true}''')
  marker=p.get_by_role('button',name='Select draw point 129');assert p.locator('.lex-image-map-point').count()==1
  assert marker.evaluate("e=>parseFloat(e.style.top)>50 && parseFloat(e.style.left)===50")
  # Picking a marker selects it for the panel beside the map. The panel's own
  # title is what carries a reader to the page that owns the record, so a click
  # here no longer leaves the map.
  marker.click();assert p.evaluate('state.worldMapPoint')==0
  assert p.evaluate("document.querySelector('.lex-image-map-point.selected')!==null")
  panel=p.get_by_role('region',name='FF8 world map');box=panel.bounding_box();p.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);p.mouse.wheel(0,-500);p.wait_for_timeout(100)
  assert p.evaluate('worldVisualView.scale')>1
  p.mouse.down(button='middle');p.mouse.move(box['x']+box['width']/2+40,box['y']+box['height']/2+20);p.mouse.up(button='middle')
  assert p.evaluate('worldVisualView.x')>20
  p.mouse.wheel(0,10000);p.wait_for_timeout(100);assert p.evaluate('worldVisualView.scale')==1
  b.close()
 print('12,288 coordinate round trips; marker position/selection; wheel zoom and middle-button pan passed.')
if __name__=='__main__':main()
