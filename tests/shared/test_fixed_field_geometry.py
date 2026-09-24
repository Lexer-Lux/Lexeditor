"""Fixed name lanes and selection must not change value or text geometry."""
import base64
import struct
from io import BytesIO

import pytest
from PIL import Image, ImageChops
from test_shared_ui_feedback import ROOT, page, framework


@pytest.mark.parametrize('theme', ['ff8', 'ff7r2', 'rdr2'])
@pytest.mark.parametrize('platform',[False,True])
def test_name_lane_keeps_names_readable_when_panel_resizes(page, theme, platform):
    # The lane is a tenth-ish of the field (7.5%) and grows only when a name
    # cannot be read in it. Names used to shrink to fit a fixed lane, which in
    # a narrow panel meant text a few pixels high.
    framework(page)
    page.add_style_tag(path=str(ROOT / f'plugins/{theme}/editor.css'))
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(
      U.detailField({label:'A very long property name',control:U.el('input',{value:4})}),
      U.detailField({label:'HP',control:U.el('input',{value:4})}));}''')
    if platform:
        page.locator('.lex-detail-field').first.evaluate("n=>n.classList.add('lex-platform-config-field')")
    for width in [1000, 500, 800]:
        page.locator('main').evaluate('(n,w)=>n.style.width=w+"px"', width)
        page.wait_for_timeout(250)
        result=page.locator('.lex-detail-field').first.evaluate('''n=>{
          const css=getComputedStyle(n),label=n.querySelector('.lex-detail-field-label');
          const available=n.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight);
          return {ratio:parseFloat(css.gridTemplateColumns)/available,size:parseFloat(getComputedStyle(label).fontSize),
            fits:label.scrollWidth<=label.clientWidth+1&&label.scrollHeight<=label.clientHeight+1};}''')
        assert result['ratio'] >= .075 - .001, result
        assert result['ratio'] <= .5 + .001, result
        assert result['size'] >= 9, result
        assert result['fits'], result
        # Every name in the panel shares the one lane.
        lanes = page.locator('.lex-detail-field').evaluate_all(
            "ns=>ns.map(n=>Math.round(n.querySelector('.lex-detail-field-label').getBoundingClientRect().width))")
        assert len(set(lanes)) == 1, lanes


def test_selected_row_does_not_move_text_and_keeps_pointer_gap(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.columnList({
      rows:[{id:1,name:'Flame Saber'},{id:2,name:'Gauntlet'}],key:r=>r.id,selected:1,
      columns:[{key:'name',label:'Name'}]}));}''')
    page.wait_for_timeout(100)
    coords='''()=>[...document.querySelectorAll('.lex-column-cell-content')].map(n=>{
      const r=document.createRange();r.selectNodeContents(n);return r.getBoundingClientRect().toJSON();})'''
    before=page.evaluate(coords)
    page.evaluate('''()=>document.querySelectorAll('.lex-column-list-row').forEach((n,i)=>n.classList.toggle('selected',i===1))''')
    page.wait_for_timeout(100)
    assert page.evaluate(coords)==before
    assert page.locator('.selected .lex-column-pointer-cell > .lex-column-cell-content').evaluate('''n=>{
      const p=getComputedStyle(n,'::before'),range=document.createRange();range.selectNodeContents(n);
      const tip=n.getBoundingClientRect().left+parseFloat(p.left)+parseFloat(p.width);
      return p.position==='absolute'&&Math.abs(range.getBoundingClientRect().left-tip-6)<2;}''')


def test_native_font_first_glyph_is_not_clipped(page):
    from plugins.ff8.game_font import ensure_font
    try:
        font=ensure_font()
    except (FileNotFoundError, RuntimeError):
        pytest.skip('Native FF8 font is not installed')
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    encoded=base64.b64encode(font.read_bytes()).decode()
    page.add_style_tag(content=f'@font-face{{font-family:PixelCheck;src:url(data:font/ttf;base64,{encoded})}} :root{{--lex-font:PixelCheck;--lex-number-font:PixelCheck}}')
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.columnList({
      rows:['#Flame Saber','Gauntlet#','Harpoon'].map((name,id)=>({name,id})),
      columns:[{key:'id',label:'ID',render:r=>U.recordId(r.id)},
      {key:'name',label:'Name',render:r=>U.el('span',{class:'lex-hoverable-label'},r.name)}]}));}''')
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(100)
    before=Image.open(BytesIO(page.locator('main').screenshot())).convert('RGB')
    page.add_style_tag(content='.lex-hoverable-label,.lex-column-cell-content,.lex-column-list-cell{overflow:visible!important}')
    after=Image.open(BytesIO(page.locator('main').screenshot())).convert('RGB')
    assert ImageChops.difference(before,after).getbbox() is None


def test_icon_export_trims_transparent_cell_padding(monkeypatch):
    from plugins.ff8 import game_icons
    atlas=Image.new('RGBA',(16,16))
    atlas.paste((255,0,0,255),(2,1,12,13))
    monkeypatch.setattr(game_icons,'_tex',lambda _: (16,16,[[0]],b''))
    monkeypatch.setattr(game_icons,'_atlas_image',lambda *args:atlas)
    sp1=struct.pack('<IHHIBbBb',1,8,1,0,16,0,16,0)
    icon=game_icons._render_icon(0,sp1,b'')
    assert icon.size==(10,12)
    assert icon.getchannel('A').getbbox()==(0,0,10,12)
