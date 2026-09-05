"""Check the restored curve-following text; redesign is deferred in #299."""
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from games.ff8.plugin import FF8Session
from games.blank.plugin import BlankSession
from tools.verify_panel_layout_visual_46 import browser_session,close_browser,screenshot,wait_eval

def check_math(cdp):
    rows=cdp.eval("""(()=>[...document.querySelectorAll('.lex-curve-editor')].map(card=>{const text=card.querySelector('.lex-curve-path-formula'),path=text.querySelector('textPath'),guide=card.querySelector(path.getAttribute('href')),style=getComputedStyle(text),r=text.getBoundingClientRect();return {title:card.dataset.curveTitle,text:path.textContent,visible:style.display!=='none'&&r.width>0&&r.height>0,guide:!!guide?.getAttribute('d'),font:style.fontFamily,shadow:style.filter!=='none'||parseFloat(style.strokeWidth)>0,overlay:!!card.querySelector('.lex-curve-math,math')}}))()""")
    assert rows
    for row in rows:
        assert row['text'] and row['visible'] and row['guide'] and row['shadow'] and not row['overlay'],row
        assert 'Cambria Math' not in row['font'],row
    return rows

def main():
    p=b=c=None
    try:
        p,b,c=browser_session()
        with tempfile.TemporaryDirectory(prefix='graph-rollback-') as project:
            with FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
                c.call('Page.navigate',{'url':session.url})
                wait_eval(c,"typeof state!=='undefined'&&!state.booting",90)
                for view in ('characters','gfs','enemies'):
                    c.eval('navigate('+json.dumps(view)+')')
                    wait_eval(c,"document.querySelector('.lex-curve-path-formula textPath')?.getComputedTextLength()>0",20)
                    c.eval('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))',await_promise=True)
                    check_math(c)
                    screenshot(c,'graph-rollback-'+view+'.png')
        with BlankSession() as session:
            c.call('Page.navigate',{'url':session.url})
            wait_eval(c,"typeof navigate==='function'",20)
            c.eval("navigate('graphs')")
            wait_eval(c,"document.querySelector('.lex-curve-path-formula textPath')?.getComputedTextLength()>0",10)
            check_math(c)
            c.eval("window.__line=document.querySelector('.lex-curve-line').getAttribute('d');const i=document.querySelector('.blank-graphs input');i.value=2;i.dispatchEvent(new Event('input',{bubbles:true}))")
            wait_eval(c,"document.querySelector('.lex-curve-line').getAttribute('d')!==__line",5)
            screenshot(c,'blank-shared-graphs.png')
            assert not c.eval('window.__testErrors'),c.eval('window.__testErrors')
        print('PASS: FF8 curve text restored; Blank graphs render and respond to edits')
    finally:
        if p:close_browser(p,b,c)

if __name__=='__main__':main()
