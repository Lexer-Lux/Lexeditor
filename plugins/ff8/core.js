  "use strict";
  const {lazyOptions,enabledMark,el,columnList,columnPreferences,panelLayout,pagedListDetail,pager,detailPanel,tabbedPanel,detailSection,detailField,multiNumberRow,subtabBar,curveEditor,newButton,infoHelp,unitField,readonlyField,formatNumber,numberValue,recordId,closeButton,hoverable,infoIcon,folderIcon,searchIcon,beginSearcher,decorateSearchCandidate,openGameFolder,platformConfigView,clone,showAlert,bindSettingDependencies,toggleRow,autoFitControlText}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  const state={booting:true,modOnly:false,tab:"items",status:"Loading…",dashboard:null,datamap:null,editorSettings:null,mods:{rows:[],composition:{}},activeSource:"mine",
    data:{cards:null,items:null,menuItems:null,shops:null,weapons:null,magic:null,gfs:null,characters:null,text:null,enemies:null,enemyTables:null,enemyAi:null,enemyBattleText:null,refine:null,encounters:null,world:null,fields:null,init:null,settings:null},base:{},vanilla:{},references:[],referenceData:{},platformConfig:null,savedPlatformConfig:null,platformQuery:"",settingsTab:"gameplay",enemyPanelTab:"stats",enemyAiView:"structure",mapsTab:"field",worldTab:"map",refineTab:"m000",fieldScriptSelection:{},fieldWalkmeshSelection:{},fieldBackgroundSelection:{},fieldBackgroundPreview:{},
    selected:{cards:null,abilityJunction:null,abilityCommand:null,abilityStat:null,abilityCharacter:null,abilityParty:null,abilityGf:null,abilityMenu:null,items:null,shops:null,weapons:null,magic:null,gfs:null,characters:null,text:null,enemies:null,refine:null,encounters:null,world:null,fields:null,startingCharacter:0,startingGf:0},startingTab:"general",
    pages:{cards:0,abilityJunction:0,abilityCommand:0,abilityStat:0,abilityCharacter:0,abilityParty:0,abilityGf:0,abilityMenu:0,items:0,shops:0,weapons:0,magic:0,gfs:0,characters:0,text:0,enemies:0,refine:0,encounters:0,world:0,fields:0,startingMagic:0,startingInventory:0,datamap:0},
    pageSizes:{cards:15,abilityJunction:15,abilityCommand:15,abilityStat:15,abilityCharacter:15,abilityParty:15,abilityGf:15,abilityMenu:15,items:15,shops:15,weapons:15,magic:15,gfs:15,characters:15,text:15,enemies:15,refine:15,encounters:15,world:15,fields:15,startingMagic:12,startingInventory:15},
    filters:{cards:"",abilityJunction:"",abilityCommand:"",abilityStat:"",abilityCharacter:"",abilityParty:"",abilityGf:"",abilityMenu:"",items:"",shops:"",weapons:"",magic:"",gfs:"",characters:"",text:"",enemies:"",refine:"",encounters:"",world:"",fields:"",datamap:"",mapStatus:""},
    sorts:{cards:["name",1],items:["name",1],shops:["name",1],weapons:["name",1],magic:["name",1],gfs:["name",1],characters:["name",1],text:["sectionId",1],enemies:["name",1],refine:["id",1],encounters:["id",1],world:["id",1],fields:["mapId",1],datamap:["filename",1],abilityJunction:["name",1],abilityCommand:["name",1],abilityStat:["name",1],abilityCharacter:["name",1],abilityParty:["name",1],abilityGf:["name",1],abilityMenu:["name",1]},gfSorts:{compatibility:["label",1],abilities:["ability",1]},enemyTableSorts:{},encounterSlotSort:["slot",1],columnPrefs:{},formula:{weaponId:0,strength:80,vitality:40,luck:20,eva:15,targetLuck:10,flying:true,float:false}};

  async function api(path,options){const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);return data;}
  function signature(value){return JSON.stringify(value)}
  const editableDatasets=["battleItems","ammoEffects","cards","items","menuItems","shops","weapons","magic","gfs","characters","abilityJunction","abilityCommand","abilityStat","abilityCharacter","abilityParty","abilityGf","abilityMenu","text","enemies","enemyTables","enemyAi","enemyBattleText","refine","encounters","world","fields"];
  const platformFields=config=>Object.fromEntries((config?.sections||[]).flatMap(section=>section.fields).map(field=>[field.id,field.value]));
  function platformChanges(){const current=platformFields(state.platformConfig),saved=platformFields(state.savedPlatformConfig),changes={};for(const [id,value] of Object.entries(current))if(signature(value)!==signature(saved[id]))changes[id]=value;return changes}
  // "Mod contents only" keeps the rows this project has actually changed.
  // FF8 mounts every view through one shared paged panel, so rather than name a
  // dataset at each of its call sites, the baseline for every editable row is
  // indexed by the row object itself. A row with no baseline is new, which
  // counts as changed.
  function baselineByRow(){
    const map=new WeakMap();
    for(const name of editableDatasets){
      const rows=state.data[name]?.rows;if(!rows)continue;
      const base=state.base[name]||[];
      rows.forEach((row,index)=>map.set(row,
        name==="fields"?base.find(entry=>entry.key===row.key):base[index]));
    }
    return map;
  }
  function modOnlySpec(view){
    const changed=(name,row)=>{const before=(state.vanilla[name]?.rows||[]).find(entry=>name==="fields"?entry.key===row.key:entry.id===row.id);return before===undefined||signature(row)!==signature(before)};
    const itemEffectsChanged=row=>view==='items'&&[
      ['battleItems',(state.data.battleItems?.rows||[]).filter(entry=>Number(row.id)!==0&&entry.id===row.id)],
      ['ammoEffects',(state.data.ammoEffects?.rows||[]).filter(entry=>Number(entry.fields.find(field=>field.field==='used_item_index')?.value)===Number(row.id))],
    ].some(([name,rows])=>rows.some(entry=>changed(name,entry)));
    return {available:state.activeSource==="mine",value:state.modOnly===true,
      changed:row=>changed(editableDatasets.find(name=>state.data[name]?.rows?.includes(row))||view,row)||itemEffectsChanged(row)||(view==="enemies"&&["enemyTables","enemyAi","enemyBattleText"].some(name=>{const linked=state.data[name]?.rows?.find(entry=>entry.id===row.id);return linked&&changed(name,linked)})),
      change:value=>{state.modOnly=value;state.pages[view]=0;render()}};
  }
  function dirtyCount(){if(state.activeSource!=="mine")return 0;let count=Object.keys(platformChanges()).length+(window.ff8SpellbookDrafts?.size||0);for(const name of editableDatasets){if(!state.data[name])continue;const current=state.data[name].rows,base=state.base[name]||[];for(let i=0;i<current.length;i++){const before=name==="fields"?base.find(row=>row.key===current[i].key):base[i];if(signature(current[i])!==signature(before))count++;}}if(state.data.init&&signature(state.data.init)!==signature(state.base.init))count++;if(state.data.settings&&signature(state.data.settings)!==signature(state.base.settings))count++;return count}
  function historyCapture(){return {...Object.fromEntries(editableDatasets.map(name=>[name,clone(state.data[name]?.rows||[])])),init:clone(state.data.init||{}),settings:clone(state.data.settings||{})}}
  function historyRestore(snapshot){for(const [name,value] of Object.entries(snapshot)){if(!state.data[name])continue;if(name==="settings"||name==="init")state.data[name]=clone(value);else state.data[name].rows=clone(value)}}
  function setStatus(text){state.status=text}
  function rowSortValue(row,key){if(String(key).startsWith("field:"))return row.fields?.find(field=>field.field===String(key).slice(6))?.value??"";return row?.[key]??""}
  function filtered(view,fields){const query=state.filters[view].trim().toLocaleLowerCase();let rows=state.data[view].rows.filter(row=>!query||fields.some(field=>String(row[field]??"").toLocaleLowerCase().includes(query)));const [key,direction]=state.sorts[view];return [...rows].sort((a,b)=>direction*String(rowSortValue(a,key)).localeCompare(String(rowSortValue(b,key)),undefined,{numeric:true,sensitivity:"base"}))}
  function sort(view,key){const [active,direction]=state.sorts[view];state.sorts[view]=[key,active===key?-direction:1];render()}
  function listColumns(view,columns,template,prefs,forceTemplate=false){return ({rows,selected,select})=>columnList({rows,key:row=>row.id,columns:columns.map(column=>({...column,sortable:true,numberedId:column.numberedId??column.key==="id"})),columnPreferences:prefs,template:forceTemplate?template:(prefs?null:template),sortState:{key:state.sorts[view][0],dir:state.sorts[view][1]},sort:key=>sort(view,key),selected,selectedClass:"selected",select,decorateRow:(node,row)=>decorateSearchCandidate(node,{type:view,value:row.id,label:row.name}),class:"ff8-record-list","aria-label":`FF8 ${view}`})}
  function showPaged(view,rows,columns,detail,template="minmax(220px,2fr) minmax(72px,.7fr) minmax(100px,1fr)",layout={},mount=true){
    const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;
    const noun=view==="gfs"?"GFs":view;
    const normalized=columns.map(column=>({...column,sortable:true,numberedId:column.numberedId??column.key==="id"}));
    const prefs=state.columnPrefs[view]||=columnPreferences(`ff8-${view}`,normalized,()=>render());
    const root=pagedListDetail({bulkChanged:()=>shell.refresh(),modOnly:modOnlySpec(view),rows,key:row=>row.id,slots:true,page:state.pages[view],pageSize:state.pageSizes[view],selected:state.selected[view],noun:view==="gfs"?"GFs":view,splitKey:`ff8-${view}`,defaultSplit:layout.defaultSplit??42,minLeft:layout.minLeft??340,minRight:layout.minRight??420,maxBarrels:layout.maxBarrels,leadingPanel:layout.leadingPanel,minLeading:layout.minLeading,defaultLeadingWidth:layout.defaultLeadingWidth,trailingPanel:layout.trailingPanel,minTrailing:layout.minTrailing,panelSizes:layout.panelSizes,
      search:{key:`ff8-${view}`,value:state.filters[view],delay:110,placeholder:`Search ${noun.toLocaleLowerCase()}…`,label:`Search ${noun}`,change:value=>{state.filters[view]=value;state.pages[view]=0;render()}},
      sync:value=>{state.pages[view]=value.page;state.pageSizes[view]=value.pageSize;state.selected[view]=value.selected},
      change:async value=>{if(view==="enemies"&&!(await enemyAiBeforeLeave()))return;state.pages[view]=value.page;state.pageSizes[view]=value.pageSize;state.selected[view]=value.selected;render()},
      master:listColumns(view,normalized,template,prefs,layout.fixedTemplate===true),detail:row=>detail(row,prefs)});
    if(mount)$("#main").replaceChildren(root);
    return root;
  }
  // The heading's icon box is for a record that has a 3D view, and FF8 has none.
  // A record's icon goes before its name instead, the same way it is shown in
  // every list and property (itemDisplay).
  function sharedDetail(row,prefs,body,className="",note="",icon=null,actions=null){const named=row.titleContent??(icon?LexeditorUI.inlineLabel(icon,el("span",{},row.name)):row.name);icon=null;return detailPanel({className:`lex-detail detail ${className}`.trim(),title:named,identity:el("span",{class:"lex-pinnable-property"},prefs?.pinButton("id","ID"),recordId(row.id)),meta:note||null,icon,actions,body})}
  function numberControl(value,min,max,step,onchange,attrs={}){const digits=String(step).includes(".")?String(step).split(".")[1].length:0,display=number=>formatNumber(number,{minimumFractionDigits:0,maximumFractionDigits:digits}),control=el("input",{type:"number",min,max,step,value:Number(value),"data-min":min,"data-max":max,"data-step":step,/* The bounds were enforced on input but never stated, so a field like Status Defence looked like it capped at an arbitrary 155. It is a ubyte shown as stored-100, so -100 to 155 is the whole byte - obvious once the range is visible, baffling when it is not. */title:`Range ${display(min)} to ${display(max)}`,...attrs,oninput:event=>{const next=Number(String(event.target.value).replaceAll(",",""));if(Number.isFinite(next))onchange(Math.max(min,Math.min(max,next)));if(!event.target.lexValueSliderDragging)shell.refresh();},onchange:event=>{if(!event.target.lexValueSliderDragging)shell.refresh()},onblur:event=>{const next=Number(String(event.target.value).replaceAll(",",""));event.target.value=String(Number.isFinite(next)?Math.max(min,Math.min(max,next)):value)},onkeydown:event=>{if(event.key!=="ArrowUp"&&event.key!=="ArrowDown")return;event.preventDefault();const current=Number(String(event.target.value).replaceAll(",",""))||0,next=Math.max(min,Math.min(max,current+(event.key==="ArrowUp"?step:-step)));event.target.value=String(next);event.target.dispatchEvent(new Event("input",{bubbles:true}))}});return control}
  function ratio255Control(value,onchange,label="Hit rate"){
    let raw=Math.max(0,Math.min(255,Math.round(Number(value)||0)));
    const percentage=()=>formatNumber(raw/255*100,{maximumFractionDigits:2});
    const percent=el("input",{type:"number",min:0,max:100,step:.01,value:percentage(),"aria-label":`${label} percentage`});
    const exact=el("input",{type:"number",min:0,max:255,step:1,value:String(raw),"aria-label":`${label} out of 255`});
    const setRaw=next=>{raw=Math.max(0,Math.min(255,Math.round(next)));exact.value=String(raw);percent.value=percentage();onchange(raw);shell.refresh()};
    percent.addEventListener("input",event=>{const next=Number(String(event.target.value).replaceAll(",",""));if(Number.isFinite(next))setRaw(next/100*255)});
    exact.addEventListener("input",event=>{const next=Number(String(event.target.value).replaceAll(",",""));if(Number.isFinite(next))setRaw(next)});
    percent.addEventListener("blur",()=>{percent.value=percentage()});
    exact.addEventListener("blur",()=>{exact.value=String(raw)});
    return LexeditorUI.controlGroup([unitField(percent,"%"),unitField(exact,"/255")]);
  }
  // A long list holds only its current choice until the select is used.
  function selectControl(value,entries,onchange){
    const key=entry=>entry.value??entry.id;
    const selected=entry=>String(key(entry))===String(value);
    const control=el("select",{onchange:event=>{
      const entry=entries.find(entry=>String(key(entry))===event.target.value);
      onchange(entry?key(entry):event.target.value);shell.refresh();
    }});
    const lazy=entries.length>24;
    if(lazy)lazyOptions(control,()=>entries.map(entry=>({value:key(entry),label:entry.name})));
    const shown=lazy?[entries.find(selected)??entries[0]].filter(Boolean):entries;
    for(const entry of shown)control.append(el("option",{value:key(entry),selected:selected(entry)},entry.name));
    if(entries.some(entry=>entry.abilityType)){
      let icon=abilityIcon(entries.find(selected));
      control.addEventListener("change",()=>{
        const next=abilityIcon(entries.find(entry=>String(key(entry))===control.value));
        icon.replaceWith(next);icon=next;
      });
      return LexeditorUI.inlineLabel(icon,autoFitControlText(control));
    }
    return autoFitControlText(control);
  }
  function openItem(itemId){const item=itemById(itemId);if(!item)return;state.selected.items=item.id;navigate("items")}
  function gfNameKey(name){return String(name||"").toLocaleLowerCase().replace(/\bking\b/g,"").replace(/[^a-z0-9]/g,"").replace("quetzalcoatl","quezacotl")}
  function gfByName(name){const key=gfNameKey(name);return state.data.gfs?.rows?.find(row=>gfNameKey(row.name)===key)}
  function openGFByName(name){const gf=gfByName(name);if(!gf)return;state.selected.gfs=gf.id;navigate("gfs")}
  function itemById(itemId){return state.data.items?.rows?.find(item=>Number(item.id)===Number(itemId))||state.data.shops?.items?.find(item=>Number(item.id)===Number(itemId))||state.data.weapons?.items?.find(item=>Number(item.id)===Number(itemId))||null}
  function itemIcon(item){if(item?.iconId===null||item?.iconId===undefined)return null;const image=el("img",{src:`/assets/icons/${item.iconId}.png`,alt:"",onerror:()=>image.remove()});return LexeditorUI.inlineLabel(image)}
  function itemDisplay(item,text=item?.name||`Item ${item?.id??"?"}`){return LexeditorUI.inlineLabel(itemIcon(item),el("span",{},text))}
  function itemLabel(item,text=item?.name||`Item ${item?.id??"?"}`){return hoverable({content:itemDisplay(item,text),targetType:"item",targetId:item?.id,targetLabel:text,activate:()=>openItem(item?.id)})}
  function itemIconLink(item){return hoverable({content:itemIcon(item),targetType:"item",targetId:item?.id,targetLabel:item?.name||`Item ${item?.id??"?"}`,activate:()=>openItem(item?.id)})}
  function itemSelectControl(value,entries,onchange){let current=itemIconLink(entries.find(entry=>Number(entry.id??entry.value)===Number(value))||itemById(value));const select=selectControl(value,entries,next=>{onchange(next);const replacement=itemIconLink(entries.find(entry=>Number(entry.id??entry.value)===Number(next))||itemById(next));current.replaceWith(replacement);current=replacement});return LexeditorUI.inlineLabel(current,select)}
  function itemSearchControl(value,prompt,accept,origin){const item=itemById(value)||{id:value,name:`Item ${value}`},link=hoverable({content:itemDisplay(item,item.name),targetType:"items",targetId:item.id,targetLabel:item.name,activate:()=>{state.selected.items=Number(item.id);navigate("items")}}),finder=el("button",{type:"button",title:"Choose an item","aria-label":`Choose an item for ${item.name}`,onclick:event=>{event.preventDefault();event.stopPropagation();beginSearcher({type:"items",prompt,target:()=>navigate("items"),origin,accept})}},LexeditorUI.selectionIcon());return LexeditorUI.choiceField(link,finder)}
  function enemyById(enemyId){return state.data.enemies?.rows?.find(enemy=>Number(enemy.id)===Number(enemyId))||{id:enemyId,name:`Enemy ${enemyId}`}}
  function enemySearchControl(value,prompt,accept,origin){const enemy=enemyById(value),name=hoverable({content:enemyDisplayName(enemy.name),targetType:"enemies",targetId:enemy.id,targetLabel:enemy.name,activate:()=>{state.selected.enemies=enemy.id;navigate("enemies")}}),finder=el("button",{type:"button",title:"Choose an enemy","aria-label":"Choose an enemy",onclick:event=>{event.stopPropagation();beginSearcher({type:"enemies",prompt,target:()=>navigate("enemies"),origin,accept})}},LexeditorUI.selectionIcon());return LexeditorUI.choiceField(name,finder)}
  function rowOf(dataset,view,id){return dataset?.[view]?.rows?.find(row=>row.id===id)}
  function sameValue(left,right){return signature(left)===signature(right)}
  function sourceControl(control,current,vanilla,references,apply,format,options={}){return LexeditorUI.provenanceControl({control,current,vanilla,references,format,same:sameValue,internal:options.internal,apply:value=>{apply(value);render();shell.refresh()}})}
  function pinLabel(prefs,key,label){return el("span",{class:"lex-pinnable-property"},label,prefs?.pinButton(key,label))}
  function referenceValues(view,id,read){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(rowOf(state.referenceData[reference.id],view,id))})).filter(entry=>entry.value!==undefined)}
  function auxiliaryReferences(view,id,read){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(rowOf(state.referenceData[reference.id],view,id))})).filter(entry=>entry.value!==undefined)}

  function bitFlagsControl(value,definitions,onchange,label){return toggleRow({label,toggles:definitions.map(entry=>{const bit=1<<Number(entry.bit);return{key:String(entry.bit),label:entry.name,help:entry.description||null,checked:(Number(value)&bit)===bit,change:next=>{value=next?(Number(value)|bit):(Number(value)&~bit);onchange(value);shell.refresh()}}})})}
  function menuParameterControl(menuRow,key){const typeName=menuRow[key==="param1"?"param1Type":"param2Type"],meta=state.data.menuItems.parameterTypes.find(entry=>entry.name===typeName),value=menuRow[key],apply=next=>menuRow[key]=Number(next);if(meta?.widget==="flags")return bitFlagsControl(value,meta.values,apply,meta.description);if(meta?.widget==="list")return selectControl(value,state.data.menuItems.parameterChoices[typeName]||[],apply);return autoFitControlText(numberControl(value,0,255,1,apply,{"aria-label":meta?.widget==="none"?`${key}; stored but unused by this item type`:meta?.description||key}))}
  function menuItemSection(itemId){const row=rowOf(state.data,"menuItems",itemId),vanilla=rowOf(state.vanilla,"menuItems",itemId);if(!row||!vanilla)return null;const typeEntries=state.data.menuItems.types.map(entry=>({value:entry.id,name:entry.name})),setType=value=>{const type=state.data.menuItems.types.find(entry=>Number(entry.id)===Number(value));row.typeId=Number(value);row.typeName=type.name;row.description=type.description;row.param1Type=type.param1;row.param2Type=type.param2;renderItems();shell.refresh()};const refs=read=>auxiliaryReferences("menuItems",itemId,read);return detailSection({className:"item-menu-section",title:"MENU BEHAVIOR",body:[
    detailField({label:"TYPE",help:row.description?infoHelp(row.description):null,control:sourceControl(selectControl(row.typeId,typeEntries,setType),()=>row.typeId,vanilla.typeId,refs(value=>value?.typeId),setType,value=>typeEntries.find(entry=>entry.value===Number(value))?.name||value)}),
    detailField({label:"USE FLAGS",control:sourceControl(bitFlagsControl(row.flags,state.data.menuItems.flagDefinitions,value=>row.flags=value,"Item use flags"),()=>row.flags,vanilla.flags,refs(value=>value?.flags),value=>row.flags=Number(value),value=>`0x${Number(value).toString(16).padStart(2,"0").toLocaleUpperCase()}`)}),
    detailField({className:"item-parameter-field",label:"Param 1",help:(help=>help?infoHelp(help):null)(state.data.menuItems.parameterTypes.find(entry=>entry.name===row.param1Type)?.description||""),control:sourceControl(menuParameterControl(row,"param1"),()=>row.param1,vanilla.param1,refs(value=>value?.param1),value=>row.param1=Number(value))}),
    detailField({className:"item-parameter-field",label:"Param 2",help:(help=>help?infoHelp(help):null)(state.data.menuItems.parameterTypes.find(entry=>entry.name===row.param2Type)?.description||""),control:sourceControl(menuParameterControl(row,"param2"),()=>row.param2,vanilla.param2,refs(value=>value?.param2),value=>row.param2=Number(value))})]})}

  function gilValue(value){return unitField(numberValue(value),"G",{unitClass:"ff8-gil-unit"})}
