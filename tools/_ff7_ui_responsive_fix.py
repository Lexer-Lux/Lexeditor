"""One-shot responsive FF7 UI repair; removed after verified landing."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
editor_path=root/'games/ff7/editor.html'
text=editor_path.read_text(encoding='utf-8')

replacements=[]
replacements.append((
'''  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",limitBreaks:"Limit breaks",magicOrder:"Magic menu",items:"Items",itemSortOrder:"Name sort",materia:"Materia",materiaEquipEffects:"Equip effects",materiaPriority:"Menu priority",apMultiplier:"Master sale price",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",exeText:"Executable text",audioMixing:"Audio mixing",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};
''',
'''  const labels={accessories:"Accessories",armor:"Armor",characters:"Characters",initialState:"New game",initialInventory:"Starting inventory",initialMateria:"Starting Materia",stolenMateria:"Yuffie stolen Materia",commands:"Commands",playerAttacks:"Player attacks",limitBreaks:"Limit breaks",magicOrder:"Magic menu",items:"Items",itemSortOrder:"Name sort",materia:"Materia",materiaEquipEffects:"Equip effects",materiaPriority:"Menu priority",apMultiplier:"Master sale price",weapons:"Weapons",enemies:"Enemies",encounters:"Encounters",shops:"Shops",prices:"Prices",texts:"Text",exeText:"Executable text",audioMixing:"Audio mixing",enemyAttacks:"Enemy attacks",tweaks:"Tweaks",characterNames:"Initial names",growthCurves:"Growth curves",growthBonuses:"Growth bonuses",characterAI:"Character AI",enemyAI:"Enemy AI",formationAI:"Formation AI",recruits:"Recruits",defaultNames:"Default names",fieldEncounters:"Field encounters",worldEncounters:"World encounters",yuffieEncounters:"Yuffie encounters",chocoboRatings:"Chocobo ratings"};
  const subtabLabels={characters:"Stats",characterNames:"Names",growthCurves:"Curves",growthBonuses:"Bonuses",characterAI:"AI",recruits:"Recruits",defaultNames:"Defaults",initialState:"Setup",initialInventory:"Inventory",initialMateria:"Materia",stolenMateria:"Stolen",encounters:"Battles",formationAI:"Formation AI",fieldEncounters:"Field",worldEncounters:"World",yuffieEncounters:"Yuffie",chocoboRatings:"Chocobo"};
'''))

replacements.append((
'''    const group=toggleRow({label:`${field.label} for ${row.name}`,columns:3,toggles:(field.flags||[]).map(flag=>({
      label:flag.label,checked:(logical()&Number(flag.value))!==0,disabled:readonly(),help:flag.help,change:checked=>{
        if(readonly())return;
        const bit=Number(flag.value),value=raw();
        row.values[field.key]=field.invertBits?(checked?(value&~bit):(value|bit)):(checked?(value|bit):(value&~bit));
        shellRefresh();
      }
    }))});
''',
'''    const group=toggleRow({label:`${field.label} for ${row.name}`,toggles:(field.flags||[]).map(flag=>({
      label:flag.label,checked:(logical()&Number(flag.value))!==0,disabled:readonly(),help:flag.help,change:checked=>{
        if(readonly())return;
        const bit=Number(flag.value),value=raw();
        row.values[field.key]=field.invertBits?(checked?(value&~bit):(value|bit)):(checked?(value|bit):(value&~bit));
        shellRefresh();
      }
    }))});
    group.style.setProperty("--lex-toggle-minimum","85px");group.style.minWidth="0";group.style.maxWidth="100%";group.style.width="100%";
'''))

replacements.append((
'''    const select=el("select",{disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,onchange:event=>{
      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();
    }});
''',
'''    const select=el("select",{disabled:readonly(),style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} for ${row.name}`,onchange:event=>{
      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();
    }});
'''))

replacements.append((
'''    const openButton=el("button",{type:"button",class:"lex-semantic-reference-open",title:`Open selected ${field.label.toLowerCase()}`,"aria-label":`Open ${field.label} for ${row.name}`,disabled:true,onclick:event=>{
''',
'''    const openButton=el("button",{type:"button",class:"lex-semantic-reference-open",style:"box-sizing:border-box;min-width:30px;width:30px;max-width:30px;align-self:stretch",title:`Open selected ${field.label.toLowerCase()}`,"aria-label":`Open ${field.label} for ${row.name}`,disabled:true,onclick:event=>{
'''))

replacements.append((
'''    const search=searchable?el("input",{type:"search",class:"lex-semantic-reference-search",placeholder:`Search ${field.label.toLowerCase()}…`,disabled:readonly(),"aria-label":`Search ${field.label} for ${row.name}`,oninput:event=>rebuild(event.target.value)}):null;
    rebuild();
    const root=el("div",{class:`lex-semantic-reference-control${searchable?" searchable":""}`},...(search?[openButton,search,select]:[openButton,select]));
''',
'''    const search=searchable?el("input",{type:"search",class:"lex-semantic-reference-search",style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%",placeholder:`Search ${field.label.toLowerCase()}…`,disabled:readonly(),"aria-label":`Search ${field.label} for ${row.name}`,oninput:event=>rebuild(event.target.value)}):null;
    rebuild();
    if(searchable)openButton.style.gridRow="1 / span 2";
    const root=el("div",{class:`lex-semantic-reference-control${searchable?" searchable":""}`,style:searchable?"display:grid;grid-template-columns:30px minmax(0,1fr);grid-template-rows:auto auto;align-items:stretch;gap:4px 6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box":"display:grid;grid-template-columns:30px minmax(0,1fr);align-items:stretch;gap:6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box"},...(search?[openButton,search,select]:[openButton,select]));
'''))

for old in (
'''    const mode=el("select",{"aria-label":`${field.label} mode for ${row.name}`,disabled:readonly()},...modes.map(value=>el("option",{value:value.value},value.label)));
    const amount=el("input",{type:"number",min:0,max:63,step:1,"aria-label":`${field.label} chance or amount for ${row.name}`,disabled:readonly()});
    mode.value=initial.mode;amount.value=String(initial.mode==="unknown"?0:initial.amount);amount.disabled=readonly()||["none","unknown"].includes(initial.mode);
    const root=el("div",{class:"lex-semantic-compound"},mode,amount);
''',
'''    const mode=el("select",{"aria-label":`${field.label} method for ${row.name}`,disabled:readonly()},el("option",{value:"drop"},"Drop"),el("option",{value:"steal"},"Steal"));
    const amount=el("input",{type:"number",min:0,max:127,step:1,"aria-label":`${field.label} chance for ${row.name}`,disabled:readonly(),value:initial.amount});mode.value=initial.mode;
    const root=el("div",{class:"lex-semantic-compound"},mode,amount);
'''):
    if "chance or amount" in old:
        new='''    const mode=el("select",{style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} mode for ${row.name}`,disabled:readonly()},...modes.map(value=>el("option",{value:value.value},value.label)));
    const amount=el("input",{type:"number",min:0,max:63,step:1,style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} chance or amount for ${row.name}`,disabled:readonly()});
    mode.value=initial.mode;amount.value=String(initial.mode==="unknown"?0:initial.amount);amount.disabled=readonly()||["none","unknown"].includes(initial.mode);
    const root=el("div",{class:"lex-semantic-compound",style:"display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.8fr);gap:6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box"},mode,amount);
'''
    else:
        new='''    const mode=el("select",{style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} method for ${row.name}`,disabled:readonly()},el("option",{value:"drop"},"Drop"),el("option",{value:"steal"},"Steal"));
    const amount=el("input",{type:"number",min:0,max:127,step:1,style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} chance for ${row.name}`,disabled:readonly(),value:initial.amount});mode.value=initial.mode;
    const root=el("div",{class:"lex-semantic-compound",style:"display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.8fr);gap:6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box"},mode,amount);
'''
    replacements.append((old,new))

old_formation='''  function formationDetail(row){
    const omit=new Set();for(let i=0;i<6;i++)for(const suffix of ["enemy","x","y","z","row","cover","flags"])omit.add(`slot${i}_${suffix}`);for(let i=0;i<3;i++)for(const axis of ["x","y","z","directionX","directionY","directionZ"])omit.add(`camera${i}_${axis}`);for(let i=0;i<4;i++)omit.add(`arena${i}`);const body=ordinarySections(row,omit);
    const slots=Array.from({length:6},(_,i)=>({key:i+1,enemy:fieldByKey(`slot${i}_enemy`),x:fieldByKey(`slot${i}_x`),y:fieldByKey(`slot${i}_y`),z:fieldByKey(`slot${i}_z`),row:fieldByKey(`slot${i}_row`),cover:fieldByKey(`slot${i}_cover`),flags:fieldByKey(`slot${i}_flags`)}));body.push(detailSection({title:"ENEMY SLOTS",attrs:{"data-concept":"formation-slots"},body:conceptTable(slots,"40px minmax(130px,1.4fr) repeat(3,minmax(62px,.55fr)) minmax(90px,.8fr) minmax(82px,.7fr) minmax(82px,.7fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"enemy",label:"Enemy",render:e=>semanticControl(row,e.enemy)},{key:"x",label:"X",render:e=>semanticControl(row,e.x)},{key:"y",label:"Y",render:e=>semanticControl(row,e.y)},{key:"z",label:"Z",render:e=>semanticControl(row,e.z)},{key:"row",label:"Row",render:e=>semanticControl(row,e.row)},{key:"cover",label:"Cover",render:e=>semanticControl(row,e.cover)},{key:"flags",label:"Flags",render:e=>semanticControl(row,e.flags)}],"Formation enemy slots")}));
    const cameras=Array.from({length:3},(_,i)=>({key:i+1,...Object.fromEntries(["x","y","z","directionX","directionY","directionZ"].map(axis=>[axis,fieldByKey(`camera${i}_${axis}`)]))}));body.push(detailSection({title:"CAMERAS",attrs:{"data-concept":"formation-cameras"},body:conceptTable(cameras,"40px repeat(6,minmax(68px,1fr))",[{key:"camera",label:"#",numberedId:true,render:e=>e.key},...['x','y','z','directionX','directionY','directionZ'].map(axis=>({key:axis,label:axis.startsWith('direction')?`Dir ${axis.slice(9)}`:axis.toUpperCase(),render:e=>semanticControl(row,e[axis])}))],"Formation cameras")}));
    const arenas=Array.from({length:4},(_,i)=>({key:i+1,field:fieldByKey(`arena${i}`)}));body.push(detailSection({title:"ARENA CANDIDATES",attrs:{"data-concept":"formation-arenas"},body:conceptTable(arenas,"44px minmax(120px,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"arena",label:"Arena ID",render:e=>semanticControl(row,e.field)}],"Formation arena candidates")}));return conceptPanel(row,body)
  }
'''
new_formation='''  function formationDetail(row){
    const omit=new Set();for(let i=0;i<6;i++)for(const suffix of ["enemy","x","y","z","row","cover","flags"])omit.add(`slot${i}_${suffix}`);for(let i=0;i<3;i++)for(const axis of ["x","y","z","directionX","directionY","directionZ"])omit.add(`camera${i}_${axis}`);for(let i=0;i<4;i++)omit.add(`arena${i}`);const body=[];
    const slots=Array.from({length:6},(_,i)=>({key:i+1,enemy:fieldByKey(`slot${i}_enemy`),x:fieldByKey(`slot${i}_x`),y:fieldByKey(`slot${i}_y`),z:fieldByKey(`slot${i}_z`),row:fieldByKey(`slot${i}_row`),cover:fieldByKey(`slot${i}_cover`),flags:fieldByKey(`slot${i}_flags`)}));
    body.push(detailSection({title:"ENEMY SLOTS",attrs:{"data-concept":"formation-slots"},body:conceptTable(slots,"36px minmax(0,1fr) 68px",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"enemy",label:"Enemy",render:e=>semanticControl(row,e.enemy)},{key:"row",label:"Row",render:e=>semanticControl(row,e.row)}],"Formation enemy slots")}));
    body.push(detailSection({title:"ENEMY POSITIONS",attrs:{"data-concept":"formation-positions"},body:conceptTable(slots,"36px repeat(3,minmax(0,1fr))",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"x",label:"X",render:e=>semanticControl(row,e.x)},{key:"y",label:"Y",render:e=>semanticControl(row,e.y)},{key:"z",label:"Z",render:e=>semanticControl(row,e.z)}],"Formation enemy positions")}));
    body.push(detailSection({title:"SLOT FLAGS",attrs:{"data-concept":"formation-flags"},body:conceptTable(slots,"36px repeat(2,minmax(0,1fr))",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"cover",label:"Cover",render:e=>semanticControl(row,e.cover)},{key:"flags",label:"Initial flags",render:e=>semanticControl(row,e.flags)}],"Formation enemy slot flags")}));
    const cameras=Array.from({length:3},(_,i)=>({key:i+1,...Object.fromEntries(["x","y","z","directionX","directionY","directionZ"].map(axis=>[axis,fieldByKey(`camera${i}_${axis}`)]))}));
    body.push(detailSection({title:"CAMERA POSITIONS",attrs:{"data-concept":"formation-cameras"},body:conceptTable(cameras,"36px repeat(3,minmax(0,1fr))",[{key:"camera",label:"#",numberedId:true,render:e=>e.key},...['x','y','z'].map(axis=>({key:axis,label:axis.toUpperCase(),render:e=>semanticControl(row,e[axis])}))],"Formation camera positions")}));
    body.push(detailSection({title:"CAMERA DIRECTIONS",attrs:{"data-concept":"formation-camera-directions"},body:conceptTable(cameras,"36px repeat(3,minmax(0,1fr))",[{key:"camera",label:"#",numberedId:true,render:e=>e.key},...['directionX','directionY','directionZ'].map(axis=>({key:axis,label:`Dir ${axis.slice(9)}`,render:e=>semanticControl(row,e[axis])}))],"Formation camera directions")}));
    const arenas=Array.from({length:4},(_,i)=>({key:i+1,field:fieldByKey(`arena${i}`)}));body.push(detailSection({title:"ARENA CANDIDATES",attrs:{"data-concept":"formation-arenas"},body:conceptTable(arenas,"36px minmax(0,1fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"arena",label:"Arena ID",render:e=>semanticControl(row,e.field)}],"Formation arena candidates")}));
    body.push(...ordinarySections(row,omit));return conceptPanel(row,body)
  }
'''
replacements.append((old_formation,new_formation))

old_shop='''  function shopDetail(row){const omit=new Set();for(let i=0;i<10;i++){omit.add(`type${i}`);omit.add(`item${i}`)}const body=ordinarySections(row,omit),entries=Array.from({length:10},(_,i)=>({key:i+1,index:i,kind:fieldByKey(`type${i}`),product:fieldByKey(`item${i}`)}));body.push(detailSection({title:"INVENTORY",attrs:{"data-concept":"shop-inventory"},body:conceptTable(entries,"44px 62px minmax(130px,.8fr) minmax(180px,1.3fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"active",label:"Active",render:e=>e.index<Number(row.values.count)?"Yes":"No"},{key:"kind",label:"Kind",render:e=>semanticControl(row,{...e.kind,rerenderOnChange:true})},{key:"product",label:"Product",render:e=>semanticControl(row,e.product)}],"Shop inventory slots")}));return conceptPanel(row,body)}
'''
new_shop='''  function shopDetail(row){const omit=new Set();for(let i=0;i<10;i++){omit.add(`type${i}`);omit.add(`item${i}`)}const body=[],entries=Array.from({length:10},(_,i)=>({key:i+1,index:i,kind:fieldByKey(`type${i}`),product:fieldByKey(`item${i}`)}));body.push(detailSection({title:"INVENTORY",attrs:{"data-concept":"shop-inventory"},body:conceptTable(entries,"36px 48px minmax(68px,.65fr) minmax(0,1.35fr)",[{key:"slot",label:"#",numberedId:true,render:e=>e.key},{key:"active",label:"Active",render:e=>e.index<Number(row.values.count)?"Yes":"No"},{key:"kind",label:"Kind",render:e=>semanticControl(row,{...e.kind,rerenderOnChange:true})},{key:"product",label:"Product",render:e=>semanticControl(row,e.product)}],"Shop inventory slots")}));body.push(...ordinarySections(row,omit));return conceptPanel(row,body)}
'''
replacements.append((old_shop,new_shop))

replacements.append((
'''    const nav=subtabBar({tabs:sub.map(id=>({id,label:labels[id]})),active:state.tab,label:labels[parentTab(state.tab)]+" datasets",change:id=>{if(id!==state.tab)LexeditorUI.playThemeSound?.("confirm");navigate(id)}});
''',
'''    const nav=subtabBar({tabs:sub.map(id=>({id,label:subtabLabels[id]||labels[id]})),active:state.tab,label:labels[parentTab(state.tab)]+" datasets",change:id=>{if(id!==state.tab)LexeditorUI.playThemeSound?.("confirm");navigate(id)}});
'''))

for old,new in replacements:
    count=text.count(old)
    if count!=1: raise SystemExit(f'editor marker count {count}: {old[:90]!r}')
    text=text.replace(old,new)
editor_path.write_text(text,encoding='utf-8')

# Keep a small permanent narrow-view regression instead of retaining the
# expensive 30-screenshot audit scaffold.
test_path=root/'tools/verify_ff7_rendered_neutral.py'
tests=test_path.read_text(encoding='utf-8')
marker='target.RenderedTests.open = open_with_neutral\n'
if tests.count(marker)!=1: raise SystemExit('rendered test insertion marker missing')
addition='''def test_dense_custom_views_fit_narrow_detail_pane(self):
    self.install(); self.open()
    self.page.set_viewport_size({"width":900,"height":620})
    for group in ("characters","playerAttacks","encounters","shops"):
        with self.subTest(group=group):
            self.navigate(group); self.page.wait_for_timeout(50)
            metrics=self.page.evaluate("""()=>{
              const detail=document.querySelector('.ff7-detail'),dr=detail.getBoundingClientRect();
              const visible=node=>{const r=node.getBoundingClientRect();return r.width>0&&r.height>0};
              const clipped=[...detail.querySelectorAll('input,select,textarea,button')].filter(visible).filter(node=>{const r=node.getBoundingClientRect();return r.left<dr.left-2||r.right>dr.right+2}).length;
              const tableOverflow=[...detail.querySelectorAll('.ff7-concept-table')].filter(table=>table.scrollWidth>table.clientWidth+1).length;
              const subtabOverflow=[...document.querySelectorAll('.lex-subtab-button .lex-tab-label-text')].filter(label=>label.scrollWidth>label.clientWidth+1).length;
              return {clipped,tableOverflow,subtabOverflow,documentWidth:document.documentElement.scrollWidth};
            }""")
            self.assertEqual(metrics["clipped"],0,(group,metrics))
            self.assertEqual(metrics["tableOverflow"],0,(group,metrics))
            self.assertEqual(metrics["subtabOverflow"],0,(group,metrics))
            self.assertLessEqual(metrics["documentWidth"],902,(group,metrics))
    self.originals_unchanged()


'''
tests=tests.replace(marker,addition+marker)
assignment='target.RenderedTests.test_finished_high_value_detail_views = test_finished_high_value_detail_views\n'
if tests.count(assignment)!=1: raise SystemExit('rendered assignment marker missing')
tests=tests.replace(assignment,assignment+'target.RenderedTests.test_dense_custom_views_fit_narrow_detail_pane = test_dense_custom_views_fit_narrow_detail_pane\n')
test_path.write_text(tests,encoding='utf-8')
