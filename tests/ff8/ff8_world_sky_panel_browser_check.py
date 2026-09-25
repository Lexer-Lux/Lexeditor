"""The Sky Colours page: the gradient column, and one panel for one record.

Two defects the reader reported are checked here. The Sky gradient column drew
nothing, because a cell renderer gave the swatch no box of its own. And a sky
record picked on the Map page showed a shorter panel than the same record on
the Sky Colours page, so the two screens disagreed about what the record holds.
"""
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
const state={activeSource:'mine',worldTab:'map',worldMapSky:null,selected:{world:null},
  pages:{},filters:{},modOnly:false,vanilla:null,references:[],referenceData:{},
  data:{world:{rows:[]}}};
function worldTextureDataset(){return 'vanilla'}
function worldRow(){return null}
function formatNumber(value){return new Intl.NumberFormat('en-US').format(value)}
function rerenderWorldMap(){window.rerenders=(window.rerenders||0)+1}
function hoverable(options){
  window.hoverables=window.hoverables||[];
  window.hoverables.push(options);
  return el('span',{class:'lex-hoverable',"data-lex-target":options.targetType},options.content);
}
function worldNumber(row,key,min,max,label){
  return el('input',{type:'number','aria-label':label,value:String(row[key])});
}
function worldColor(row,key,label){
  return el('input',{type:'color','aria-label':label,value:'#000000'});
}
function sharedDetail(row,prefs,body,className,note){
  return el('section',{class:`lex-detail ${className||''}`.trim(),"data-lex-note":note||''},
    el('h2',{class:'lex-detail-panel-title'},row.titleContent||row.name),...(body||[]));
}
function detailSection(options){
  return el('section',{class:`lex-detail-section ${options.className||''}`.trim()},
    options.title?el('h3',{},options.title):null,...(options.body||[]));
}
function detailField(options){
  return el('label',{class:'lex-detail-field','data-lex-property':options.label||''},options.control);
}
const skyRow={kind:'skyColor',id:3,x:1024,y:16384,z:-2048,
  shadows:[7,8,9],vehicles:[10,11,12],skyTop:[13,14,15],
  skyCenter:[16,17,18],skyBottom:[19,20,21]};
function render(){
  document.querySelector('#list').replaceChildren(worldSkyDetail(skyRow,null,null,''));
  document.querySelector('#map').replaceChildren(
    worldSkyDetail(skyRow,null,worldSkyMapTitle(skyRow),
      `World ${formatNumber(skyRow.x)}, ${formatNumber(skyRow.z)}`));
  document.querySelector('#swatch').replaceChildren(worldSkySwatch(skyRow));
}
"""


def fields(page, selector):
    return page.evaluate(
        f"[...document.querySelectorAll({selector!r} + ' [data-lex-property]')]"
        ".map(node=>node.getAttribute('data-lex-property'))")


def main():
    source = plugin_ui('ff8')
    # The Map page has to draw that same panel, not a shorter copy of it.
    assert 'worldMapSkyPreview' not in source, \
        "the Map page still draws its own, shorter sky panel"
    assert 'pickedSky?worldSkyDetail(pickedSky,null,worldSkyMapTitle(pickedSky),' in source, \
        "the Map page does not draw the Sky Colours panel for a picked sky record"
    color_hex = source[source.index('  function worldColorHex'):
                       source.index('  function worldColor(')]
    swatch = source[source.index('  function worldSkySwatch'):
                    source.index('  function railTrackDetail')]
    sky_detail = source[source.index('  function worldSkyDetail'):
                        source.index('  function worldSegmentDetail')]
    sky_title = source[source.index('  function worldSkyMapTitle'):
                       source.index('  function worldMapPointPreview')]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        page.route('http://fixture/', lambda route: route.fulfill(
            body='<div id="list"></div><div id="map"></div><div id="swatch" '
                 'style="width:200px"></div>', content_type='text/html'))
        page.goto('http://fixture/')
        page.add_style_tag(content=(ROOT / 'ui/framework.css').read_text(encoding='utf-8'))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text)
                if message.type == 'error' else None)
        page.add_script_tag(content=(ROOT / 'ui/framework.js').read_text(encoding='utf-8'))
        page.add_script_tag(content=STUBS + color_hex + swatch + sky_detail + sky_title
                            + "\nrender();\n")
        assert not errors, errors

        # One panel for the record, whichever page shows it.
        listed = fields(page, '#list')
        mapped = fields(page, '#map')
        assert listed == ['X', 'RANGE', 'Z', 'SHADOWS', 'VEHICLES', 'SKY TOP',
                          'SKY CENTRE', 'SKY BOTTOM'], listed
        assert mapped == listed, (mapped, listed)
        assert 'SKY AND AMBIENT COLOURS' in page.locator('#map').inner_text()

        # The map panel keeps the way to the page that owns the record.
        hoverables = page.evaluate(
            "()=>window.hoverables.map(entry=>({target:entry.targetType,"
            "label:entry.targetLabel,content:entry.content}))")
        assert hoverables == [{'target': 'skyColors', 'label': 'sky record 3',
                               'content': 'SKY RECORD 3'}], hoverables
        page.evaluate("window.hoverables[0].activate()")
        assert page.evaluate("state.worldTab") == 'skyColors'
        assert page.evaluate("state.selected.world") == 3
        assert page.evaluate("state.worldMapSky") is None
        assert page.evaluate("window.rerenders") == 1
        assert page.evaluate("document.querySelector('#map').dataset.lexNote"
                             "||document.querySelector('#map [data-lex-note]').dataset.lexNote"
                             ) == 'World 1,024, -2,048'

        # The gradient column draws a box, a three-stop gradient and its colours.
        cell = page.locator('#swatch .world-sky-swatch')
        assert cell.count() == 1
        box = cell.bounding_box()
        assert box['height'] >= 18 and box['width'] >= 70, box
        assert cell.evaluate("node=>getComputedStyle(node).backgroundImage"
                             ).startswith('linear-gradient')
        assert cell.evaluate("node=>getComputedStyle(node).backgroundImage"
                             ).count('rgb(') == 3
        assert cell.get_attribute('aria-label') == (
            'Sky gradient for record 3: top #0d0e0f, centre #101112, bottom #131415')
        assert not errors, errors
        browser.close()
    print('world sky: the gradient column draws its three-stop swatch, and the map '
          'and the Sky Colours page show one identical panel with a title that '
          'opens the page that owns the record.')


if __name__ == '__main__':
    main()
