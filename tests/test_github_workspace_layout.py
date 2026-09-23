from pathlib import Path
from test_shared_ui_feedback import ROOT, page, framework

def test_github_owns_search_pager_detail_and_workflow(page):
    page.set_viewport_size({'width':1600,'height':900})
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      window.issue={number:484,title:'Fix shared editor layout',state:'OPEN',body:'Example issue body',labels:[{name:'actionable'},{name:'ff8'}],comments:[]};
      window.writes=[];
      window.pywebview={api:{lexeditor_settings:async()=>({developerMode:true}),github_repository:async()=>({repository:'Lexer-Lux/Lexeditor'}),
        github_issues:async()=>({issues:Array.from({length:22},(_,i)=>({...issue,number:484+i}))}),
        github_issue:async(_,number)=>({...issue,number}),github_labels:async()=>({labels:[]}),
        github_set_issue_labels:async(_,number,labels)=>{writes.push(labels);issue={...issue,number,labels:labels.map(name=>({name}))};return issue;}}};
      document.body.prepend(Object.assign(document.createElement('div'),{id:'shell'}));
    }''')
    framework(page)
    page.evaluate('''()=>{
      window.shell=LexeditorUI.mountShell({host:'#shell',brand:'LEXEDITOR',plugin:{id:'ff8',name:'FF8'},tabs:[{id:'items',label:'Items'}],activeTab:()=> 'items',navigate(){}});
      document.querySelector('main').append(LexeditorUI.pager({page:0,pages:149,pageSize:15,total:2225,change(){}}));
      LexeditorUI.finishPluginLoading();
    }''')
    page.wait_for_function('shell.githubWorkspace()')
    page.evaluate('shell.githubWorkspace().show()')
    page.wait_for_selector('.lex-github-editor .lex-detail-panel')
    root=page.locator('.lex-github-workspace')
    assert abs(root.bounding_box()['y']+root.bounding_box()['height']-900)<1
    assert page.locator('.lex-pager:visible').count()==1
    assert root.locator('input[type=search]').count()==1
    assert root.locator('.lex-page-summary').inner_text()=='1-15/22'
    assert root.locator('.lex-subtab-bar').count()==1
    assert root.locator('.lex-detail-panel-id').text_content()=='#484'
    assert root.get_by_role('img',name='Open issue').count()>=1
    priority=root.get_by_role('button',name='Mark high priority')
    page.mouse.move(0,0)
    assert priority.evaluate('n=>getComputedStyle(n).opacity')=='0'
    root.locator('.lex-github-editor').hover()
    assert priority.evaluate('n=>getComputedStyle(n).opacity')=='0.25'
    priority.click()
    page.wait_for_function('writes.length===1')
    assert page.evaluate('writes[0]')==['actionable','ff8','high priority']
    assert root.get_by_role('button',name='Remove high priority').get_attribute('aria-pressed')=='true'
    buttons=root.locator('.lex-github-workflow-actions button')
    assert buttons.all_text_contents()==['Actionable','Needs Testing','Waiting','Unfeasible']
    root.get_by_role('button',name='Next page',exact=True).click()
    assert root.locator('.lex-page-summary').inner_text()=='16-22/22'
    search=root.get_by_role('searchbox')
    search.fill('505')
    page.wait_for_timeout(150)
    assert root.locator('.lex-github-issue-row').count()==1
    assert root.locator('.lex-page-summary').inner_text()=='1-1/1'
    output=Path('C:/Users/Lexer/AppData/Local/Temp/lex-github-layout.png')
    page.screenshot(path=str(output))
    root.locator('.lex-github-workflow-actions').get_by_role('button',name='Needs Testing').click()
    page.wait_for_function('writes.length===2')
    assert page.evaluate('writes[1]')==['ff8','high priority','untested']
    page.evaluate('shell.githubWorkspace().hide()')
    assert page.locator('.lex-pager:visible').count()==1
