import pytest
from test_shared_ui_feedback import ROOT,page,framework


def test_repeated_open_and_ready_messages_only_slide_once(page):
    page.route('http://fixture/editor',lambda r:r.fulfill(content_type='text/html',body='''<body style="background:#626262">Editor<script>
      for(let id=1;id<=8;id++) parent.postMessage({type:'lexeditor-host-call',id,method:'editor_ready'},'*');
      </script>'''))
    page.evaluate('''()=>{document.body.innerHTML='<div id="chooser-surface">Menu</div>';
      window.slides=0;const animate=Element.prototype.animate;
      Element.prototype.animate=function(...args){if(this.id==='lexeditor-editor')slides++;return animate.apply(this,args)};}''')
    page.add_script_tag(path=str(ROOT/'ui/editor-host.js'))
    page.evaluate("Promise.all(Array.from({length:20},()=>LexeditorHost.open('http://fixture/editor')))")
    assert page.locator('#lexeditor-editor').count()==1
    assert page.evaluate('slides')==1
    assert page.locator('#lexeditor-editor').evaluate('n=>!n.inert&&n.getBoundingClientRect().left===0')
    assert page.evaluate("document.getAnimations().length")==0


def test_resident_handle_blocks_repeat_clicks_and_clears_cover(page):
    source=(ROOT/'ui/chooser.html').read_text(encoding='utf-8')
    resume=source[source.index('async function resumeResident(plugin)'):source.index('async function restartLexeditor()')]
    page.evaluate('''()=>{window.chooser={opening:false};window.calls=0;
      window.residentHandle=document.createElement('button');window.loadingScreen={hidden:false};
      window.closeDialog=()=>window.dialogClosed=true;
      window.LexeditorHost={open:()=>new Promise(resolve=>window.finishOpen=resolve)};
      window.pywebview={api:{resume_plugin:async()=>{calls++;return {url:'http://fixture/editor'}}}};}''')
    page.add_script_tag(content=resume)
    page.evaluate("window.requests=Array.from({length:20},()=>resumeResident({id:'ff8'}))")
    assert page.evaluate('calls')==1
    assert page.evaluate('residentHandle.disabled && dialogClosed && chooser.opening')
    page.evaluate('finishOpen();Promise.all(requests)')
    assert page.evaluate('!residentHandle.disabled && loadingScreen.hidden && !chooser.opening')


@pytest.mark.parametrize('zoom',[.75,1,1.25])
def test_pointer_tip_tracks_icon_and_text_at_each_ui_scale(page,zoom):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''zoom=>{const U=LexeditorUI;document.body.style.zoom=zoom;
      document.querySelector('main').append(U.columnList({rows:[{id:1,name:'Fuel'}],key:r=>r.id,selected:1,
        columns:[{key:'name',label:'Item',render:r=>U.inlineLabel(U.el('img',{style:'width:20px;height:20px'}),U.el('span',{},r.name))}]}));}''',zoom)
    page.wait_for_timeout(200)
    assert page.locator('.selected .lex-column-cell-content').evaluate('''n=>{
      const icon=n.querySelector('.lex-inline-label > img');
      const rect=n.getBoundingClientRect(),scale=rect.width/n.offsetWidth,p=getComputedStyle(n,'::before');
      const tip=rect.left+(parseFloat(p.left)+parseFloat(p.width))*scale;
      return Math.abs(icon.getBoundingClientRect().left-tip-6*scale)<2;}''')


def test_control_text_grows_into_available_height_without_overflow(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;const input=U.el('input',{type:'number',value:3000,style:'height:40px;width:200px;font-size:14px;padding:2px 6px'});
      document.querySelector('main').append(input);U.autoFitControlText(input);}''')
    page.wait_for_timeout(200)
    control=page.locator('input')
    assert control.evaluate('n=>parseFloat(getComputedStyle(n).fontSize)')>=24
    assert control.evaluate('n=>n.scrollWidth<=n.clientWidth')
