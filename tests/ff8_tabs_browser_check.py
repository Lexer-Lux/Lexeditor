"""Check every FF8 tab with the installed game font, including bold ink overhang."""
import base64
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui
LABELS = 'ABILITIES CARDS CHARACTERS ENCOUNTERS ENEMIES GFS ITEMS MAGIC MAPS REFINE SHOPS START TEXT WEAPONS TWEAKS'.split()

def main():
    font = Path(os.environ['LOCALAPPDATA']) / 'Lexeditor/game-data/ff8/generated/ff8-menu.ttf'
    assert font.is_file(), 'Install/extract the FF8 menu font before this check.'
    css = (ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8')
    css = re.sub(r'url\("/assets/ff8-menu.ttf\?v=4"\)', 'url(data:font/ttf;base64,' + base64.b64encode(font.read_bytes()).decode() + ')', css)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.route('http://fixture/', lambda r: r.fulfill(content_type='text/html', body='<body data-lex-plugin="ff8"><header class="lex-shell-header"><nav></nav></header><div id="subtabs"></div></body>'))
        page.goto('http://fixture/')
        page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
        page.add_style_tag(content=css)
        page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
        page.evaluate('''labels => {
          document.querySelector('nav').innerHTML=labels.map((label,i)=>`<button data-tab="${i}"><span class="lex-tab-label"><span class="lex-tab-label-text">${label}</span></span><span class="lex-tab-shortcut">${i}</span></button>`).join('');
          document.querySelector('#subtabs').append(LexeditorUI.subtabBar({tabs:['STATS','AI','BATTLE TEXT','ABILITIES','SPELLBOOK'].map(label=>({id:label,label})),active:'STATS',change:()=>{}}));
        }''', LABELS)
        page.evaluate('document.fonts.ready')
        for width in (1024, 1536, 2048, 2560):
            page.set_viewport_size({'width':width,'height':900})
            for scale in (.96, 1, 1.5):
                page.evaluate('(scale)=>document.body.style.zoom=scale', scale)
                for i in range(len(LABELS)):
                    page.evaluate('''i=>document.querySelectorAll('nav button').forEach((b,n)=>b.classList.toggle('active',n===i))''', i)
                    errors = page.evaluate('''() => {
                      const errors=[],c=document.createElement('canvas').getContext('2d');
                      for(const bar of document.querySelectorAll('nav,.lex-subtab-bar')) {
                        if(new Set([...bar.children].map(b=>b.offsetTop)).size!==1) errors.push('tabs wrapped');
                        const edge=bar.getBoundingClientRect().right;
                        if([...bar.children].some(b=>b.getBoundingClientRect().right>edge+1)) errors.push('tab outside bar');
                      }
                      for(const e of document.querySelectorAll('.lex-tab-label-text')) {
                        const s=getComputedStyle(e);c.font=`${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
                        const m=c.measureText(e.textContent);
                        if(parseFloat(s.paddingLeft)+.01<m.actualBoundingBoxLeft) errors.push(e.textContent+': left ink clipped');
                        if(parseFloat(s.paddingRight)+.01<Math.max(0,m.actualBoundingBoxRight-m.width)) errors.push(e.textContent+': right ink clipped');
                        if(e.scrollWidth>e.clientWidth+1 && s.textOverflow!=='ellipsis') errors.push(e.textContent+': no ellipsis');
                      }
                      if(getComputedStyle(document.querySelector('nav .active'),'::after').content!=='none') errors.push('active underline');
                      return errors;
                    }''')
                    assert not errors, (width,scale,i,errors)
        browser.close()
    print('All main/subtab labels: real FF8 font ink clearance, ellipsis and no active underline passed at four widths and three scales.')

if __name__ == '__main__':
    main()
