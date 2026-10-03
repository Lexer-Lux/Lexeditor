"""Glyph ink stays inside the box that clips it.

The layout sweep measures each text run's advance box. A game face is often
bolder than its own metrics claim, so its glyphs paint outside that advance box
- and that ink is lost when an ancestor clips. Canvas TextMetrics reports the
real ink box, so it can catch the shaved first letter of a label that the layout
sweep calls perfect.
"""
import json

import pytest
from test_shared_ui_feedback import ROOT, page, framework  # noqa: F401

INK = (ROOT / 'tests/shared/text_ink_probe.js').read_text(encoding='utf-8')


def test_probe_reports_text_pushed_past_the_clip(page):
    page.set_content('''<style>body{margin:0;font:20px/30px Arial}
      .cut{width:300px;overflow:hidden;text-indent:-8px}
      .room{width:300px;overflow:hidden}
      .reach{width:40px;overflow:auto;text-indent:-8px}
      </style><div class="cut"><span>Pushed left</span></div>
      <div class="room"><span>Roomy</span></div>
      <div class="reach"><span>Scrollable</span></div>''')
    hits = json.loads(page.evaluate(INK))
    assert [hit['text'] for hit in hits] == ['Pushed left'], hits
    assert hits[0]['overLeft'] > 1


def test_probe_ignores_an_ellipsis_it_can_see(page):
    page.set_content('''<style>body{margin:0;font:20px/30px Arial}
      .short{width:40px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      </style><div class="short">A longer label</div>''')
    assert json.loads(page.evaluate(INK)) == []


def test_probe_checks_outer_clip_after_a_roomy_inner_clip(page):
    page.set_content('''<style>body{margin:0;font:20px/30px Arial}
      .outer{width:90px;overflow:hidden}
      .inner{width:300px;overflow:hidden;white-space:nowrap}
      </style><div class="outer"><div class="inner">Outer clip cuts this text</div></div>''')
    hits=json.loads(page.evaluate(INK))
    assert [hit['text'] for hit in hits]==['Outer clip cuts this text'],hits
    assert hits[0]['clippedBy']=='outer',hits


def test_ink_probe_tracks_positioned_containing_blocks_and_scrolling(page):
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
        <span class="line" style="position:fixed">Fixed transformed child clipped</span></div>
      <div class="cut"><div class="line" style="overflow:auto">Scrollable child reachable</div></div>
      <div style="width:90px;overflow:auto"><div class="cut line">Inner hard clip remains</div></div>''')
    hits=json.loads(page.evaluate(INK))
    assert {hit['text'] for hit in hits}=={
        'Relative child clipped','Absolute child clipped',
        'Fixed transformed child clipped','Inner hard clip remains'},hits


@pytest.mark.parametrize('zoom', [1, 1.5])
@pytest.mark.parametrize('width', [1280, 1000])
def test_shared_tab_labels_hold_their_ink(page, width, zoom):
    page.set_viewport_size({'width': width, 'height': 900})
    framework(page)
    page.evaluate('''zoom=>{
      document.body.style.zoom=zoom;
      const host=document.createElement('div');host.id='shell';document.body.append(host);
      LexeditorUI.mountShell({host:'#shell',brand:'LEXEDITOR',
        plugin:{id:'fixture',name:'Fixture'},
        tabs:[['characters','Characters'],['items','Items'],['sfx','SFX'],
              ['textures','Textures'],['settings','Tweaks']].map(([id,label])=>({id,label})),
        activeTab:()=>'sfx',navigate(){}});
    }''', zoom)
    page.wait_for_timeout(400)
    hits = json.loads(page.evaluate(INK))
    assert not hits, hits


def test_a_real_game_face_stays_inside_its_tab(page):
    """The face these screens use paints wider than its advance boxes."""
    font = ROOT / 'plugins/rdr2/assets/fonts/RDRLino-Regular.rockstar.woff2'
    if not font.exists():
        pytest.skip('the game face is not redistributed in this checkout')
    page.set_viewport_size({'width': 1280, 'height': 900})
    framework(page)
    page.route('**/ink-face.woff2', lambda route: route.fulfill(path=str(font)))
    page.add_style_tag(content='''
      @font-face{font-family:"Ink Face";src:url("/ink-face.woff2") format("woff2")}
      :root{--lex-font:"Ink Face",Arial;--lex-heading-font:"Ink Face",Arial}''')
    page.evaluate('''()=>{
      const host=document.createElement('div');host.id='shell';document.body.append(host);
      LexeditorUI.mountShell({host:'#shell',brand:'LEXEDITOR',
        plugin:{id:'fixture',name:'Fixture'},
        tabs:[['sfx','SFX'],['settings','Tweaks'],['items','Items']].map(([id,label])=>({id,label})),
        activeTab:()=>'sfx',navigate(){}});
      const bar=LexeditorUI.subtabBar({label:'Loop',active:'yes',
        tabs:[{id:'yes',label:'Loop'},{id:'no',label:'No'},{id:'tweaks',label:'Tweaks'}],
        change(){}});
      (document.querySelector('main,#main')||document.body).prepend(bar);
    }''')
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(600)
    assert page.evaluate("document.fonts.check('16px \"Ink Face\"')")
    hits = json.loads(page.evaluate(INK))
    assert not hits, hits
