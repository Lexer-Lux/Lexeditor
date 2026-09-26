"""The active mod name gets space before its secondary folder path."""
from test_shared_ui_feedback import ROOT, page, framework


def test_project_name_uses_available_space_before_path(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
        activeTab:()=>'',navigate(){},projectSnapshot:async()=>({canCreate:false,projects:[]}),
        projectSources:()=>[{key:'a',label:'FF8 Testing Gameplay Changes',path:'C:/Mods/Test',managed:true}],
        projectActiveSource:()=>'a',sourcesReplaceProjects:true,addProjectSource(){},
        changeProjectSource:async()=>{}});
      U.finishPluginLoading();
    }''')
    page.wait_for_function("document.querySelector('.lex-project-name')?.textContent==='FF8 Testing Gameplay Changes'")
    selector = page.locator('.lex-project-select')
    name = selector.locator('.lex-project-name')
    # Pick a width that fits the full name and padding, but where the old
    # percentage cap cut it while leaving unused room in the path column.
    selector.evaluate('''n=>{
      const name=n.querySelector('.lex-project-name');
      const width=name.scrollWidth+110;
      n.closest('.lex-project-control').style.width=width+'px';
      n.closest('.lex-project-control').style.flex='none';
    }''')
    assert name.evaluate('n=>n.scrollWidth<=n.clientWidth+1')
    for width in [200, 350, 600]:
        selector.evaluate('(n,w)=>n.closest(".lex-project-control").style.width=w+"px"', width)
        assert selector.evaluate('''n=>{
          const outer=n.getBoundingClientRect();
          return [...n.children].filter(c=>c.getBoundingClientRect().width).every(c=>{
            const r=c.getBoundingClientRect();
            return r.left>=outer.left && r.right<=outer.right;
          });
        }''')
