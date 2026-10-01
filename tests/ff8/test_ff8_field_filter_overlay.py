"""Field filters overlay the preview without reserving side columns."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import ROOT, framework, page


def test_field_filters_overlay_full_width_picture(page, tmp_path):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    source=(ROOT/'plugins/ff8/places.js').read_text(encoding='utf-8')
    render=source[source.index('  function fieldBackgroundPanels('):source.index('  const fieldTileDefinitions')]
    page.add_script_tag(content='''
      const U=LexeditorUI,el=U.el,toggleRow=U.toggleRow;
      const row={background:{tiles:[{}],layers:[0,1],parameterStates:[{parameter:1,state:0}]}};
      const preview={layers:[0,1],states:['1:0'],hide:false};
      const fieldBackgroundPreviewState=()=>preview,fieldPreviewRedraw=()=>{};
      const fieldPreviewToggle=(label,help,checked,change)=>({label,checked,change});
    '''+render)
    page.evaluate('''()=>{
      const picture=U.imageMap({media:el('div',{style:'width:100%;height:400px;background:linear-gradient(135deg,#123,#789)'})});
      document.querySelector('main').append(fieldBackgroundPanels(row,picture));
    }''')
    for width in [850, 480]:
        page.locator('main').evaluate('(n,w)=>n.style.width=w+"px"', width)
        page.wait_for_timeout(100)
        assert page.evaluate('''()=>{
          const root=document.querySelector('.field-preview-sides').getBoundingClientRect();
          const picture=document.querySelector('.lex-image-map').getBoundingClientRect();
          const left=document.querySelector('.field-preview-layers').getBoundingClientRect();
          const right=document.querySelector('.field-preview-states').getBoundingClientRect();
          return Math.abs(root.width-picture.width)<2 && left.left>=picture.left-1 &&
            right.right<=picture.right+1 && left.right>picture.left && right.left<picture.right;
        }''')
    page.get_by_role('checkbox',name='Layer 0',exact=True).uncheck()
    assert page.evaluate('preview.layers') == [1]
    page.screenshot(path=str(tmp_path/'field-filters.png'))
