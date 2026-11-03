"""The tab audit catches misplaced boolean help beyond the default view."""
import json
from pathlib import Path
import pytest

from test_shared_ui_feedback import framework, page
from ui_tab_sweep import sweep_nested_tabs


def test_boolean_help_probe_detects_nondefault_tab_and_skips_hidden_controls(page):
    framework(page)
    probe = Path(__file__).with_name("boolean_help_probe.js").read_text(encoding="utf-8")
    for style in ("box", "arrow"):
        page.evaluate("""style=>{
          document.documentElement.dataset.lexBooleanStyle=style;
          const U=LexeditorUI;window.active='good';
          window.render=()=>{
            const field=U.detailField({label:'Melee weapon',help:U.infoHelp('Synthetic test help'),
              control:U.el('input',{type:'checkbox'})});
            if(active==='bad')field.querySelector('.lex-info-help').style.marginLeft='60px';
            const hidden=U.detailField({label:'Hidden',help:U.infoHelp('Hidden synthetic help'),
              control:U.el('input',{type:'checkbox'})});
            hidden.style.display='none';
            hidden.querySelector('.lex-info-help').style.marginLeft='60px';
            document.querySelector('main').replaceChildren(
              U.subtabBar({tabs:[{id:'good',label:'Good'},{id:'bad',label:'Bad'}],active,
                change:id=>{active=id;render();}}),field,hidden);
          };render();
        }""", style)
        page.wait_for_timeout(150)
        assert json.loads(page.evaluate(probe)) == []
        hits = []
        sweep_nested_tabs(page.evaluate, lambda: page.wait_for_timeout(150),
                          lambda path: hits.extend(json.loads(page.evaluate(probe))))
        assert len(hits) == 1 and hits[0]["label"] == "Melee weapon", (style, hits)
        assert hits[0]["gap"] > 14
        assert page.evaluate("active") == "good"


@pytest.mark.parametrize('style',['box','arrow'])
@pytest.mark.parametrize('zoom',[1,1.5])
def test_wrapped_boolean_help_follows_last_word_after_resize(page,tmp_path,style,zoom):
    framework(page)
    page.evaluate('''([style,zoom])=>{
      document.documentElement.dataset.lexBooleanStyle=style;
      document.body.style.zoom=zoom;
      const U=LexeditorUI;
      document.querySelector('main').append(U.detailField({label:'Melee weapon',
        help:U.infoHelp('Synthetic test help'),control:U.el('input',{type:'checkbox'})}));
    }''',[style,zoom])
    for width in (650,1000,650):
        page.evaluate('(width)=>document.querySelector("main").style.width=width+"px"',width)
        page.wait_for_timeout(250)
        geometry=page.locator('.lex-detail-field-label').evaluate('''label=>{
          const range=document.createRange();range.selectNodeContents(label.firstElementChild);
          const last=[...range.getClientRects()].filter(box=>box.width&&box.height).at(-1);
          const help=label.querySelector('.lex-info-help').getBoundingClientRect();
          return {gap:help.left-last.right,center:help.top+help.height/2,
            last:last.toJSON()};
        }''')
        assert abs(geometry['gap']-4*zoom)<1,geometry
        assert abs(geometry['center']-(geometry['last']['top']+geometry['last']['height']/2))<1,geometry
    page.screenshot(path=str(tmp_path/f'boolean-help-{style}-{zoom}.png'))
