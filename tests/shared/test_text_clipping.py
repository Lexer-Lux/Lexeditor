"""Rendered checks for the clipping detector and dense shared tables."""
import json
import os
import tempfile
from pathlib import Path

import pytest
from test_shared_ui_feedback import ROOT, page, framework

PROBE = (ROOT / 'tests/shared/text_clipping_probe.js').read_text(encoding='utf-8')


def test_probe_detects_parent_clip_and_vertical_ellipsis(page):
    page.set_content('''<style>body{margin:0;font:20px/30px Arial}
      .cut{height:15px;overflow:hidden;width:300px}
      .ellipsis{white-space:nowrap;text-overflow:ellipsis}
      </style><div class="cut"><span>Parent clip</span></div>
      <div class="cut ellipsis">Vertical ellipsis clip</div>
      <div style="width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">Allowed ellipsis</div>
      <div style="height:15px;overflow:auto">Scrollable</div>
      <span style="overflow:hidden">Inline overflow has no clipping box</span>''')
    hits = json.loads(page.evaluate(PROBE))
    assert {hit['text'] for hit in hits} == {'Parent clip', 'Vertical ellipsis clip'}, hits
    assert all(hit['overH'] > 1 for hit in hits)


def test_probe_tracks_positioned_containing_blocks(page):
    page.set_content('''<style>body{margin:0;font:20px/30px Arial}
      .cut{width:90px;height:35px;overflow:hidden;margin-bottom:10px}
      .line{white-space:nowrap}
      </style>
      <div class="cut"><div class="line" style="position:relative">Relative child clipped</div></div>
      <div class="cut"><div style="position:relative;width:300px;height:30px">
        <span class="line" style="position:absolute">Absolute child clipped</span></div></div>
      <div style="position:relative;height:45px"><div class="cut">
        <span class="line" style="position:absolute">Absolute child escapes</span></div></div>
      <div class="cut"><span class="line" style="position:fixed;top:160px">Fixed child escapes</span></div>
      <div class="cut" style="transform:translateX(0)">
        <span class="line" style="position:fixed">Fixed transformed child clipped</span></div>''')
    hits=json.loads(page.evaluate(PROBE))
    assert {hit['text'] for hit in hits}=={
        'Relative child clipped','Absolute child clipped','Fixed transformed child clipped'}, hits


@pytest.mark.parametrize('height', [720, 950, 1080])
@pytest.mark.parametrize('theme', ['blank', 'rdr2'])
@pytest.mark.parametrize('zoom', [1, 1.5])
def test_dense_table_text_fits_real_rows(page, height, theme, zoom):
    page.set_viewport_size({'width':1280, 'height':height})
    page.evaluate('zoom=>document.body.style.zoom=zoom', zoom)
    if theme == 'rdr2':
        page.route('**/assets/fonts/*', lambda route: route.fulfill(
            path=str(ROOT/'plugins/rdr2/assets/fonts'/route.request.url.rsplit('/',1)[-1]))
            if (ROOT/'plugins/rdr2/assets/fonts'/route.request.url.rsplit('/',1)[-1]).exists()
            else route.fulfill(status=404,body=''))
        page.add_style_tag(path=str(ROOT/'plugins/rdr2/editor.css'))
        page.add_style_tag(content=':root{--lex-font: "Lex RDR Lino", Arial; --lex-text:#e8e1d4;--lex-panel:#191714;--lex-panel-2:#24211c;--lex-border:#4a4439}')
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const rows=Array.from({length:200},(_,id)=>({id,name:id%2?'0x05468962':'ADVERT_WHR_QUARTER_SHOES',kind:'ADVERT'}));
      const main=document.querySelector('main');main.style.cssText='position:absolute;inset:150px 0 0;height:auto';
      const render=()=>{
        const table=U.pagedListDetail({rows,key:r=>r.id,slots:false,pageSize:40,order:'given',
          splitKey:'clip-fixture',maxBarrels:1,change:render,
          master:v=>U.columnList({rows:v.rows,key:r=>r.id,select:v.select,
            columns:[{key:'name',label:'Name'},{key:'kind',label:'Kind'}]}),
          detail:()=>U.el('div')});
        main.replaceChildren(table);
      };render();
    }''')
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(700)
    hits = json.loads(page.evaluate(PROBE))
    table_hits = [hit for hit in hits if 'lex-column' in hit['clippedBy'] or 'lex-column' in hit['cls']]
    output = Path(os.environ.get('LEXEDITOR_TEST_OUTPUT', tempfile.gettempdir()))
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output/f'lex-dense-{theme}-{height}-{zoom}.png'))
    assert not table_hits, table_hits
    # The reader's requested density is authoritative. A former 32px row
    # minimum silently capped the row count, contradicting the pager's choice.
    assert page.locator('.lex-column-list-row').count() == 40
    samples = page.evaluate('''async()=>{
      const values=[];
      for(let frame=0;frame<12;frame++) {
        await new Promise(requestAnimationFrame);
        values.push([...document.querySelectorAll('.lex-column-cell-text')]
          .map(n=>getComputedStyle(n).fontSize).join('|'));
      }return values;
    }''')
    assert len(set(samples)) == 1, samples
    assert len(set(samples[-1].split('|'))) == 1, samples[-1]
    if theme == 'rdr2' and (ROOT/'plugins/rdr2/assets/fonts/RDRLino-Regular.woff2').exists():
        assert page.evaluate('document.fonts.check(\'14px "Lex RDR Lino"\')')


def test_dense_text_grows_back_when_rows_gain_height(page):
    test_dense_table_text_fits_real_rows(page, 720, 'blank', 1)
    label = page.locator('.lex-column-cell-text').first
    before = label.evaluate('n=>parseFloat(getComputedStyle(n).fontSize)')
    page.set_viewport_size({'width':1280, 'height':1080})
    page.wait_for_function('''before=>parseFloat(getComputedStyle(
      document.querySelector('.lex-column-cell-text')).fontSize)>before''', arg=before)
    page.wait_for_timeout(200)
    assert page.locator('.lex-column-list-row').count() == 40
    assert not json.loads(page.evaluate(PROBE))
