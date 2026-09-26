"""Map selection stays on the image when its container or UI scale changes."""
from pathlib import Path
import os

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
from test_shared_ui_feedback import page, framework


def test_magnifier_properties_and_placement_share_state(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;window.position={x:.25,y:.5};
      U.mapMagnifier({label:'Position',magnify:()=>({ratio:4/3,
        note:'Click to place the point. Edit its coordinates on the right.',
        points:[{...position,label:'Point'}],place:point=>Object.assign(position,point)}),
        details:({refresh})=>U.detailPanel({title:'Coordinates',body:['x','y'].map(key=>
          U.detailField({label:key.toUpperCase(),control:U.el('input',{type:'number',min:0,max:1,step:.01,
            value:position[key],'aria-label':key,onchange:event=>{position[key]=Number(event.target.value);refresh()}})}))})});}''')
    stage=page.locator('.lex-map-magnifier-body .lex-image-map-stage')
    box=stage.bounding_box()
    page.mouse.click(box['x']+box['width']*.75,box['y']+box['height']*.25)
    assert abs(float(page.get_by_role('spinbutton',name='x',exact=True).input_value())-.75)<.01
    x=page.get_by_role('spinbutton',name='x',exact=True)
    x.fill('0.1')
    x.press('Tab')
    page.wait_for_function("Math.abs(parseFloat(document.querySelector('.lex-image-map-point').style.left)-10)<.01")
    map_box=page.locator('.lex-map-magnifier-map').bounding_box()
    details=page.locator('.lex-map-magnifier-details').bounding_box()
    assert details['x']>=map_box['x']+map_box['width']-1
    assert map_box['width']>details['width']
    if destination:=os.environ.get('LEXEDITOR_UI_SCREENSHOT_DIR'):
        Path(destination).mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(Path(destination)/'map-properties-wide.png'))
    page.set_viewport_size({'width':650,'height':800})
    page.wait_for_function("document.querySelector('.lex-panel-layout').classList.contains('lex-panel-layout-below-minimum')")
    assert page.locator('.lex-map-magnifier-dialog').evaluate('n=>n.scrollWidth<=n.clientWidth+1')
    page.get_by_role('button',name='Close large map',exact=True).click()
    assert page.locator('.lex-map-magnifier-dialog').count()==0


@pytest.mark.parametrize('zoom', [1, 1.25])
def test_image_map_bounds_and_fractional_selection(zoom):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1200, 'height': 900})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<div id="host" style="width:700px;height:300px"></div>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''zoom=>{
                document.body.style.zoom=zoom;window.points=[];
                const map=LexeditorUI.imageMap({ratio:4/3,columns:8,rows:8,
                    points:[{x:.5,y:.5,label:'Center',activate:()=>points.push('center')}],
                    place:point=>points.push(point)});
                document.querySelector('#host').append(map);
            }''', zoom)
            stage = page.locator('.lex-image-map-stage')
            box = stage.bounding_box()
            assert abs(box['width'] / box['height'] - 4 / 3) < .01
            assert box['height'] <= 300 * zoom + 1
            page.mouse.click(box['x'] + box['width'] * .25, box['y'] + box['height'] * .75)
            value = page.evaluate('points[0]')
            assert abs(value['x'] - .25) < .01
            assert abs(value['y'] - .75) < .01
            page.get_by_role('button', name='Center', exact=True).click()
            assert page.evaluate('points[1]') == 'center'
            page.evaluate("document.querySelector('#host').style.width='250px'")
            box = stage.bounding_box()
            assert abs(box['width'] / box['height'] - 4 / 3) < .01
            assert box['width'] <= 250 * zoom + 1
            # The same map also works in an ordinary section whose height
            # comes from its contents, without a fixed viewport-sized host.
            page.evaluate('''() => {
              const host=document.querySelector('#host');host.style.height='auto';
              host.replaceChildren(LexeditorUI.detailSection({title:'Position',body:[
                LexeditorUI.imageMap({fill:false,ratio:4/3,points:[{x:.5,y:.5,label:'Natural center'}]})]}));
            }''')
            box=stage.bounding_box()
            assert box['width']>100 and box['height']>70
            assert abs(box['width']/box['height']-4/3)<.01
            assert page.get_by_role('button',name='Natural center').is_visible()
        finally:
            browser.close()


def test_magnifier_opens_the_same_map_at_the_size_of_the_window():
    """A small panel map is hard to place a point on exactly.

    The magnifier draws the caller's own map bigger, with a crosshair and a live
    readout, and a click inside it runs the same placement handler.
    """
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<div id="host" style="width:420px;height:280px"></div>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''() => {
                window.placed = [];
                window.spec = () => ({
                    ratio: 4 / 3, columns: 8, rows: 8, label: 'Fixture map',
                    points: [{x: .25, y: .25, label: 'Fixture point'}],
                    place: point => placed.push(point),
                    readout: point => `cell ${point.column}, ${point.row}`,
                });
                const map = LexeditorUI.imageMap({...spec(), magnify: () => spec()});
                document.querySelector('#host').append(map);
            }''')
            small = page.locator('.lex-image-map-stage').bounding_box()
            page.get_by_role('button', name='Open the large map: Fixture map').click()
            dialog = page.locator('.lex-map-magnifier-dialog')
            assert dialog.is_visible()
            large = page.locator('.lex-map-magnifier-body .lex-image-map-stage').bounding_box()
            assert large['width'] > small['width'] * 1.5, (small, large)
            assert abs(large['width'] / large['height'] - 4 / 3) < .02
            page.mouse.move(large['x'] + large['width'] * .5, large['y'] + large['height'] * .5)
            assert page.evaluate(
                "document.querySelector('.lex-map-magnifier-body .lex-image-map-readout').textContent") == 'cell 4, 4'
            crosshair = page.evaluate("""()=>{const node=document.querySelector('.lex-map-magnifier-body .lex-map-crosshair');
              return {hidden:node.hidden,left:node.style.left,top:node.style.top}}""")
            assert crosshair == {'hidden': False, 'left': '50%', 'top': '50%'}, crosshair
            page.mouse.click(large['x'] + large['width'] * .25, large['y'] + large['height'] * .75)
            placed = page.evaluate('placed[0]')
            assert abs(placed['x'] - .25) < .01 and abs(placed['y'] - .75) < .01, placed
            assert dialog.is_visible(), 'the large map stays open, so a point can be nudged'
            page.keyboard.press('Escape')
            assert page.locator('.lex-map-magnifier-dialog').count() == 0
        finally:
            browser.close()
