"""The world map's magnifier: place a draw point and a field return on the large map.

The panels that own a world position show the map beside the numbers, but a
panel-sized map is a coarse pointer. The magnifier draws the same map at the
size of the window with a crosshair and a live readout, and a click inside it
places the record. A draw point's own map opens that view when it is clicked -
a click on a panel must not move game data - while the panel that still places
points keeps its magnifier button. Either way one placement handler runs.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui  # noqa: E402

STUBS = r"""
const el=LexeditorUI.el;
const infoHelp=LexeditorUI.infoHelp;
const shell={refresh:()=>{}};
const state={activeSource:'mine',vanilla:null,references:[],referenceData:{},
  data:{world:{sha256:'fixture',rows:[],drawPoints:[]}}};
function worldTextureDataset(){return 'vanilla'}
function worldRow(){return null}
function formatNumber(value){return new Intl.NumberFormat('en-US').format(value)}
function readonlyField(value){return el('span',{class:'lex-readonly'},String(value))}
function step(name){window.steps=(window.steps||[]);window.steps.push(name)}
function worldNumber(row,key,min,max,label){
  const input=el('input',{type:'number','aria-label':label,value:String(row[key])});
  input.addEventListener('change',()=>{row[key]=Number(input.value);render();step('typed '+key)});
  return input}
function sharedDetail(row,prefs,body,className){
  return el('section',{class:`lex-detail ${className||''}`.trim()},...body)}
function detailSection(options){
  return el('section',{class:`lex-detail-section ${options.className||''}`.trim()},
    options.title?el('h3',{},options.title):null,...(options.body||[]))}
function detailField(options){return el('label',{class:'lex-detail-field'},options.label,options.control)}
const drawRow={kind:'drawPoint',id:0,drawId:129,x:192,y:24,subId:3};
const returnRow={kind:'fieldReturn',id:1,x:65536,y:0,z:-32768,unknown:7};
let panel='draw';
function render(){
  document.querySelector('#fixture').replaceChildren(
    panel==='draw'?worldDrawPointDetail(drawRow,{}):worldFieldReturnDetail(returnRow,{}));}
function rerenderWorldMap(){render()}
"""


def readout(page, scoped=True):
    selector = ('.lex-map-magnifier-body ' if scoped else '') + '.lex-image-map-readout'
    return page.evaluate(f"document.querySelector({selector!r}).textContent")


def main():
    source = plugin_ui('ff8')
    projection = source[source.index('  function worldMapFraction'):source.index('  function worldColorHex')]
    helpers = source[source.index('  function worldDrawPosition'):source.index('  function worldDrawPointDetail')]
    draw = source[source.index('  function worldDrawPointDetail'):source.index('  function worldFieldReturnDetail')]
    field_return = source[source.index('  function worldFieldReturnDetail'):source.index('  function worldSkyDetail')]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        page.route('http://fixture/', lambda route: route.fulfill(
            body='<div id="fixture" style="width:1100px"></div>', content_type='text/html'))
        page.goto('http://fixture/')
        page.add_style_tag(content=(ROOT / 'ui/framework.css').read_text(encoding='utf-8'))
        page.add_style_tag(content=(ROOT / 'plugins/ff8/editor.css').read_text(encoding='utf-8'))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.add_script_tag(content=(ROOT / 'ui/framework.js').read_text(encoding='utf-8'))
        page.add_script_tag(content=STUBS + projection + helpers + draw + field_return + "\nrender();\n")
        assert not errors, errors

        # A draw point: the small map names the block under the pointer, and
        # clicking it opens the large map, which is where the point is placed.
        small = page.locator('.lex-image-map-stage').bounding_box()
        page.mouse.move(small['x'] + small['width'] * .5, small['y'] + small['height'] * .5)
        assert readout(page, False) == 'block 64, 48', readout(page, False)
        assert page.locator('.world-draw-point .lex-image-map-magnify').count() == 0, \
            'the panel map is the way into the large map, so it carries no magnifier button'
        before = page.evaluate('[drawRow.x,drawRow.y]')
        page.mouse.click(small['x'] + small['width'] * .5, small['y'] + small['height'] * .5)
        page.wait_for_selector('.lex-map-magnifier-dialog', timeout=5000)
        assert page.evaluate('[drawRow.x,drawRow.y]') == before, 'a click on the panel moved the point'
        assert page.locator('.lex-map-magnifier-dialog').is_visible()
        large = page.locator('.lex-map-magnifier-body .lex-image-map-stage').bounding_box()
        assert large['width'] > small['width'] * 2, (small, large)
        target = (round(large['x'] + large['width'] * .75), round(large['y'] + large['height'] * .5))
        page.mouse.move(*target)
        assert readout(page) == 'block 96, 48', readout(page)
        crosshair = page.evaluate("""()=>{const node=document.querySelector('.lex-map-magnifier-body .lex-map-crosshair');
          return {hidden:node.hidden,left:node.style.left,top:node.style.top}}""")
        assert crosshair['hidden'] is False, crosshair
        assert abs(float(crosshair['left'][:-1]) - 75) < .2 and abs(float(crosshair['top'][:-1]) - 50) < .2, crosshair
        page.mouse.click(*target)
        assert page.evaluate('drawRow.x') == 96 and page.evaluate('drawRow.y') == 24, page.evaluate('[drawRow.x,drawRow.y]')
        markers = page.evaluate("""()=>[...document.querySelectorAll('.lex-image-map-point')]
          .map(node=>({left:node.style.left,top:node.style.top}))""")
        assert all(marker == {'left': '75%', 'top': '50%'} for marker in markers), markers
        assert page.locator('.lex-map-magnifier-dialog').is_visible(), 'the large map stays open for a nudge'
        page.keyboard.press('Escape')
        assert page.locator('.lex-map-magnifier-dialog').count() == 0

        # A field return: the magnifier names the world coordinate under the
        # crosshair, and clicking stores exactly that coordinate.
        page.evaluate("panel='return';render()")
        marker = page.locator('.lex-image-map-point')
        assert marker.count() == 1
        assert abs(float(marker.evaluate('node=>parseFloat(node.style.left)')) - 75) < .1
        page.get_by_role('button', name='Open the large map: World position of field return 1').click()
        large = page.locator('.lex-map-magnifier-body .lex-image-map-stage').bounding_box()
        target = (round(large['x'] + large['width'] * .25), round(large['y'] + large['height'] * .75))
        page.mouse.move(*target)
        named = readout(page)
        match = re.fullmatch(r'x (-?[\d,]+), z (-?[\d,]+)', named)
        assert match, named
        page.mouse.click(*target)
        stored = page.evaluate('[returnRow.x,returnRow.z]')
        return_row_y = page.evaluate('returnRow.y')
        assert stored == [int(value.replace(',', '')) for value in match.groups()], (named, stored)
        panel_marker = float(page.evaluate(
            "document.querySelector('.world-field-return .lex-image-map-point').style.left")[:-1])
        expected_marker = page.evaluate('(returnRow.x/2048+64)/128*100')
        assert abs(panel_marker - expected_marker) < .05, (panel_marker, expected_marker)
        inputs = page.evaluate(
            "()=>[...document.querySelectorAll('.world-field-return input[aria-label]')].map(node=>Number(node.value))")
        assert inputs == [stored[0], return_row_y, stored[1]], inputs
        assert not errors, errors
        browser.close()
    print('magnifier: panel readout, 4x map, crosshair, draw-point placement, '
          'field-return placement and Escape all passed.')


if __name__ == '__main__':
    main()
