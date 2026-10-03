"""The tab audit catches misplaced boolean help beyond the default view."""
import json
from pathlib import Path

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
