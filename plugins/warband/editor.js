  "use strict";
  const {el,columnList,list,masterDetail,pagedListDetail,pager,clone,showAlert,hoverable,detailPanel,detailField,detailGroup}=LexeditorUI;
  const $=selector=>document.querySelector(selector);
  const state={
    booting:true,modOnly:false,tab:"items",dashboard:null,settings:null,troops:null,items:null,upgrades:null,modules:null,datamap:null,activeSource:"mine",
    manual:null,font:null,selectedModule:"",selectedSetting:"",selectedItem:"",selectedTroop:"",selectedUpgrade:"",selectedFile:"",catalogFile:null,catalogDraft:"",
    settingEdits:{},itemEdits:{},troopEdits:{},filters:{items:"",troops:"",cut:false,upgrades:"",settings:"",datamap:"",mapStatus:""},
    pages:{items:0,troops:0,upgrades:0,datamap:0,settings:0},pageSizes:{items:20,troops:20,upgrades:20,settings:20},sorts:{items:["name",1],troops:["name",1],upgrades:["from",1],datamap:["filename",1],settings:["section",1]},
    build:{cursor:0,lines:[],running:false,returnCode:null},status:"Ready"
  };

  let moduleRecords=null;
  async function api(path,options){const response=await fetch(path,options);const value=await response.json();if(value.error)throw new Error(value.error);return value;}
  // "Mod contents only" keeps the records this project has actually changed.
  // Warband records edits against the record itself, so the filter is the set
  // of records that carry one. A view whose records this editor cannot change
  // says so rather than offering a switch that would hide everything.
  function modOnlySpec(view,changed){
    return {available:state.activeSource==="mine"&&typeof changed==="function",
      value:state.modOnly===true,changed:changed||(()=>true),
      unavailableTitle:"This view has no editable records to filter by.",
      change:value=>{state.modOnly=value;state.pages[view]=0;render()}};
  }
  function itemDirtyCount(){return Object.values(state.itemEdits).reduce((total,row)=>total+Object.keys(row.fields||{}).length,0);}
  function dirtyCount(){return state.activeSource==="mine"?Object.keys(state.settingEdits).length+itemDirtyCount()+Object.values(state.troopEdits).reduce((n,r)=>n+Object.keys(r.fields).length,0)+(moduleRecords?.dirtyCount()||0)+(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text?1:0):0;}
  function historyCapture(){return {troopEdits:clone(state.troopEdits),settingEdits:clone(state.settingEdits),itemEdits:clone(state.itemEdits),moduleRecords:moduleRecords?.snapshot(),catalogDraft:state.catalogDraft,selectedFile:state.selectedFile,catalogFile:clone(state.catalogFile)};}
  async function historyRestore(snapshot){state.troopEdits=clone(snapshot.troopEdits||{});state.settingEdits=clone(snapshot.settingEdits);state.itemEdits=clone(snapshot.itemEdits||{});moduleRecords?.restore(snapshot.moduleRecords);state.catalogDraft=snapshot.catalogDraft;state.selectedFile=snapshot.selectedFile;state.catalogFile=clone(snapshot.catalogFile);}
  function effectiveSetting(row){return state.settingEdits[row.line]??row.value;}
  function setStatus(text){state.status=text;const target=$("#plugin-status");if(target)target.textContent=text;}
  function bitmapText(text,pixels){
    const font=state.font;if(!font?.available)return document.createTextNode(text);
    const scale=pixels/font.fontSize;
    return LexeditorUI.bitmapText({label:text,lineHeight:font.lineSpacing*scale,glyphs:[...text].map(character=>{
      const metrics=font.characters[String(character.codePointAt(0))];
      if(!metrics)return {width:pixels*.52,text:character};
      return {width:Math.max(1,metrics.postshift*scale),quad:metrics.w>metrics.u&&metrics.h>metrics.v?{
        left:metrics.preshift*scale,top:(font.fontSize-metrics.yadjust)*scale,width:(metrics.w-metrics.u)*scale,height:(metrics.h-metrics.v)*scale,
        atlasWidth:font.width*scale,atlasHeight:font.height*scale,u:metrics.u*scale,v:metrics.v*scale}:null};
    })});
  }
  function applyInstalledWarbandFont(){
    const brand=(window.LexeditorUI?.shellTextNodes?.()||[])[0]?.closest("button");if(brand&&!brand.dataset.bitmapFont){brand.dataset.bitmapFont="1";brand.replaceChildren(bitmapText("LEXEDITOR",24));}
    document.querySelectorAll("nav button").forEach(button=>{if(button.dataset.bitmapFont)return;const target=(window.LexeditorUI?.shellTextNodes?.(button)||[])[0]||button;if(!target)return;const label=target.textContent;button.dataset.bitmapFont="1";button.setAttribute("aria-label",label);target.replaceChildren(bitmapText(label,26));});
  }
  function search(rows,query,fields){const needle=query.trim().toLowerCase();return needle?rows.filter(row=>fields.some(field=>String(row[field]??"").toLowerCase().includes(needle))):rows;}
  function sorted(rows,view){const [key,direction]=state.sorts[view];return [...rows].sort((a,b)=>direction*String(a[key]??"").localeCompare(String(b[key]??""),undefined,{numeric:true}));}
  function sort(view,key){const [active,direction]=state.sorts[view];state.sorts[view]=[key,active===key?-direction:1];render();}
  function renderTableView(view,rows,columns,options={}){
    const query=state.filters[view]||"",filtered=sorted(search(rows,query,options.searchFields||columns.map(column=>column.key)),view);
    const keyOf=options.key||((row)=>columns.map(column=>String(row[column.key]??"")).join("|"));
    const selected=options.selected?.()||"",setSelected=options.setSelected||(()=>{});
    const detail=row=>row?detailPanel({title:row.name||String(keyOf(row)),body:[LexeditorUI.detailSection({body:columns.map(column=>
      detailField({label:typeof column.label==="string"?column.label:column.key,control:LexeditorUI.readonlyField(row[column.key]??"—",{format:false})}))})]})
      :detailPanel({title:"No matching records"});
    $("#toolbar").replaceChildren();
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(view,options.changed),rows:filtered,key:keyOf,slots:false,fit:{minRowHeight:36},page:state.pages[view],pageSize:state.pageSizes[view],selected,noun:view,splitKey:`warband-${view}`,className:"warband-paged-table",defaultSplit:58,
      search:{key:`warband-${view}`,value:query,placeholder:`Search ${view}…`,change:value=>{state.filters[view]=value;state.pages[view]=0;render();}},filters:options.filters||[],
      master:({rows,selected,select})=>columnList({rows,key:keyOf,columns:columns.map(column=>({...column,sortable:true})),sortState:{key:state.sorts[view][0],dir:state.sorts[view][1]},sort:key=>sort(view,key),selected,selectedClass:"selected",select,class:"warband-record-list", "aria-label":`${view} records`}),
      detail:options.detail||detail,sync:next=>{state.pages[view]=next.page;state.pageSizes[view]=next.pageSize;setSelected(next.selected||"");},change:next=>{state.pages[view]=next.page;state.pageSizes[view]=next.pageSize;setSelected(next.selected||"");render();}}));
  }

  function troopRowKey(troop){return String(troop.recordIndex??troop.line??troop.id);}
  function openTroop(troopId){
    const matches=state.troops.rows.filter(row=>row.id===troopId),troop=matches.find(row=>row.status!=="CUT")||matches[0];if(!troop)return;
    state.filters.troops="";state.filters.cut=false;state.selectedTroop=troopRowKey(troop);
    state.pages.troops=0;navigate("troops");
  }
  function troopLink(troopId,label){
    if(!state.troops.rows.some(row=>row.id===troopId))return label;
    return hoverable({targetType:"warband-troop",targetId:troopId,targetLabel:label,label,activate:()=>openTroop(troopId)});
  }

  // Undeclared columns size to their longest value, and Warband's ids and mesh
  // names are long enough to push the table past its panel and cut the last
  // column in half. Bounded widths let the long ones ellipsise instead.
  // The cells read the edited values, so a change in the detail pane shows in
  // the row it belongs to instead of waiting for a save.
  function itemColumns(){return [
    {key:"name",label:"Name",width:"minmax(9em,1.4fr)",render:row=>el("span",{title:effectiveItemField(row,"name")},effectiveItemField(row,"name")),
      sortValue:row=>effectiveItemField(row,"name")},
    {key:"id",label:"ID",width:"minmax(6em,.8fr)"},
    {key:"type",label:"Type",width:"minmax(6em,.7fr)",render:row=>el("span",{title:itemTypeFromFlags(effectiveItemField(row,"flags"))},itemTypeFromFlags(effectiveItemField(row,"flags"))),
      sortValue:row=>itemTypeFromFlags(effectiveItemField(row,"flags"))},
    {key:"inventoryMesh",label:"Inventory mesh",width:"minmax(7em,1fr)",render:row=>el("span",{title:itemInventoryMesh(row)},itemInventoryMesh(row)),
      sortValue:itemInventoryMesh}];}
  function itemRowKey(item){return String(item.recordIndex??item.line??item.id);}
  function renderItems(){
    const view="items",columns=itemColumns(),query=state.filters.items||"";
    const filtered=sorted(search(state.items.rows,query,["name","id","type","inventoryMesh"]),view);
    $("#toolbar").replaceChildren();
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec("items",item=>Object.keys(state.itemEdits[itemEditKey(item)]?.fields||{}).length>0),rows:filtered,key:itemRowKey,slots:false,fit:{minRowHeight:36},page:state.pages.items,pageSize:state.pageSizes.items,selected:state.selectedItem,noun:"items",splitKey:"warband-items",className:"warband-paged-table warband-items",defaultSplit:43,
      search:{key:"warband-items",value:query,placeholder:"Search items…",change:value=>{state.filters.items=value;state.pages.items=0;renderItems();}},
      master:({rows,selected,select})=>columnList({rows,key:itemRowKey,columns:columns.map(column=>({...column,sortable:true})),sortState:{key:state.sorts.items[0],dir:state.sorts.items[1]},sort:key=>sort("items",key),selected,selectedClass:"selected",select,class:"warband-record-list","aria-label":"Warband items"}),
      detail:()=>warbandItemDetail(state.items.rows.find(row=>itemRowKey(row)===state.selectedItem)),sync:next=>{state.pages.items=next.page;state.pageSizes.items=next.pageSize;state.selectedItem=next.selected||"";},change:next=>{state.pages.items=next.page;state.pageSizes.items=next.pageSize;state.selectedItem=next.selected||"";renderItems();}}));
  }

  function warbandEyeIcon(){
    const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("width","22");svg.setAttribute("height","22");
    const path=document.createElementNS(ns,"path");path.setAttribute("fill","none");path.setAttribute("stroke","currentColor");path.setAttribute("stroke-width","1.8");path.setAttribute("d","M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z");svg.append(path);return svg;
  }

  function disposeWarbandPreview(){
    if(window.__warbandPreview){window.__warbandPreview.forEach(controller=>controller.dispose());delete window.__warbandPreview;}
  }
  function itemEditKey(item){return itemRowKey(item);}
  function effectiveItemField(item,key){return state.itemEdits[itemEditKey(item)]?.fields?.[key]??item.fields?.[key]??"";}
  function setItemField(item,key,value){
    const recordKey=itemEditKey(item),base=String(item.fields?.[key]??""),next=String(value);
    if(next===base){const existing=state.itemEdits[recordKey];if(existing?.fields)delete existing.fields[key];if(existing&&!Object.keys(existing.fields).length)delete state.itemEdits[recordKey];}
    else{const existing=state.itemEdits[recordKey]||(state.itemEdits[recordKey]={recordIndex:item.recordIndex,originalId:item.id,fields:{}});existing.fields[key]=next;}
    shell.refresh();
  }
  function itemTypeFromFlags(flags){return (String(flags).match(/\bitp_type_([a-z0-9_]+)/i)||[])[1]||"";}
  function setItemType(item,value){
    const clean=String(value).trim().replace(/^itp_type_/i,""),flags=String(effectiveItemField(item,"flags"));if(!clean)return;
    const token=`itp_type_${clean}`,next=/\bitp_type_[a-z0-9_]+/i.test(flags)?flags.replace(/\bitp_type_[a-z0-9_]+/i,token):(flags.trim()?`${token}|${flags}`:token);
    setItemField(item,"flags",next);render();
  }
  // The meshes field is a list of (mesh, flags) pairs. Lexeditor reads and
  // writes the pair list itself, so a mesh can be chosen from the project's own
  // names instead of typed, and the item's first mesh - the icon's own mesh -
  // has a property exactly where the table column shows it.
  const meshField=()=>WarbandFieldControls;
  function itemMeshEntries(item){return meshField().parseMeshes(effectiveItemField(item,"meshes"))||[];}
  function setItemMeshes(item,entries){
    const expression=meshField().meshExpression(entries);
    if(!expression)return;
    setItemField(item,"meshes",expression);render();
  }
  function itemInventoryMesh(item){const entries=itemMeshEntries(item);return entries.length?entries[0].name:(item.inventoryMesh||"");}
  function itemMeshChoices(){return state.items?.choices?.meshes||[];}
  function itemMeshNames(){return itemMeshChoices().map(choice=>choice.name);}
  function openItemMesh(name){
    const choice=itemMeshChoices().find(value=>value.name===name);
    if(!choice||choice.recordIndex===undefined||choice.recordIndex===null)return;
    moduleRecords.openRecord("meshes",choice.recordIndex);
  }
  // One sizing rule for the panel. The shared fitter grows a number box until
  // its digits fill it, which in a panel of text boxes, a dropdown and
  // checkboxes read as one property ("Weight") shouting and the next
  // ("Value") whispering. Every control here keeps the panel's own text size,
  // which is also the size a native dropdown and a checkbox row can hold.
  function sized(control){control.dataset.lexAutofit="false";return control;}
  function itemMeshControl(item,index,entries,readOnly){
    const entry=entries[index];
    const select=el("select",{disabled:readOnly,"aria-label":`Mesh ${index+1}`,
      onchange:event=>{const next=entries.map(value=>({...value}));next[index].name=event.target.value;setItemMeshes(item,next);}});
    const names=itemMeshNames();
    if(!names.includes(entry.name))select.append(el("option",{value:entry.name,selected:true},entry.name));
    for(const name of names)select.append(el("option",{value:name,selected:name===entry.name},name));
    sized(select);
    const show=el("button",{type:"button",title:`Show ${entry.name} in the Meshes area`,
      "aria-label":`Show ${entry.name} in the Meshes area`,onclick:()=>openItemMesh(entry.name)},"Show mesh");
    return el("div",{class:"lex-action-row"},select,show);
  }
  function itemWeightFromStats(stats){return (String(stats).match(/\bweight\(([^)]+)\)/)||[])[1]?.trim()||"";}
  function setItemWeight(item,value){
    const clean=String(value).trim();if(!clean)return;const stats=String(effectiveItemField(item,"stats"));
    const next=/\bweight\([^)]+\)/.test(stats)?stats.replace(/\bweight\([^)]+\)/,`weight(${clean})`):(stats.trim()?`weight(${clean})|${stats}`:`weight(${clean})`);
    setItemField(item,"stats",next);const control=document.querySelector('[data-lex-property="stats"] textarea');if(control)control.value=next;
  }
  const ITEM_HELP={
    id:"Stable Module System identifier referenced by troops, shops, scripts, and other records. It is read-only because Lexeditor does not rewrite every reference when an item ID changes.",
    name:"Player-facing item name compiled into the module's item data.",
    type:"The itp_type_* flag defines the item's fundamental equipment/use class and changes how Warband interprets its other stats.",
    value:"Base item price before merchant, trade-skill, abundance, and other economy adjustments.",
    weight:"Inventory/equipment weight from the weight(...) stat macro; Warband uses it for encumbrance and other weight-sensitive behavior.",
    meshes:"Meshes used to render the item. The first mesh is also the source for Lexeditor's generated inventory icon.",
    inventoryMesh:"The mesh the item table and the item icon read: the first mesh in this item's meshes field. Change it here or open it in the Meshes area, which is where the mesh's own record lives.",
    flags:"Item behavior flags control equipment class, merchandise/civilian availability, handedness, and other engine behavior.",
    capabilities:"Weapon capability expression controlling supported attacks and animations; non-weapons commonly leave this at zero.",
    stats:"Gameplay stat macros for weight, abundance, armor, speed, reach, damage, ammunition, and related item values.",
    modifierBits:"Controls which generated item modifiers such as rusty, balanced, masterwork, or lordly may apply.",
    factions:"Optional faction list restricting where merchandise for this item may appear."
  };
  function itemExpressionControl(item,key){return LexeditorUI.codeField({value:effectiveItemField(item,key),oninput:event=>setItemField(item,key,event.target.value)});}
  function itemFieldLabel(key){return ({meshes:"Meshes",flags:"Flags",capabilities:"Capabilities",value:"Value",stats:"Stats",modifierBits:"Modifier bits",factions:"Factions"})[key]||key.replace(/^extra/,"Extra field ");}
  function warbandItemDetail(item){
    disposeWarbandPreview();
    if(!item)return detailPanel({className:"warband-item-detail",title:"Select an item"});
    const thumbnail=LexeditorUI.iconSlot({className:"warband-item-thumbnail",message:item.inventoryMesh?"Preparing icon…":"No mesh"}),thumbnailMessage=thumbnail.lexMessage;
    const readOnly=state.activeSource!=="mine";
    const flagsExpression=String(effectiveItemField(item,"flags")),bits=state.items?.choices?.flags||[];
    const types=state.items?.choices?.types||[];
    const entries=itemMeshEntries(item),meshNames=itemMeshNames();
    const valueControl=el("input",{value:effectiveItemField(item,"value"),disabled:readOnly,oninput:event=>setItemField(item,"value",event.target.value)});
    const nameControl=el("input",{value:effectiveItemField(item,"name"),disabled:readOnly,oninput:event=>setItemField(item,"name",event.target.value)});
    const weightControl=()=>el("input",{type:"number",step:"any",value:itemWeightFromStats(effectiveItemField(item,"stats")),disabled:readOnly,onchange:event=>setItemWeight(item,event.target.value)});
    const core=detailGroup({title:"Item",body:[
      detailField({label:"ID",property:"id",dataType:"STRING",description:ITEM_HELP.id,control:el("input",{value:item.id,disabled:true})}),
      detailField({label:"Name",property:"name",dataType:"STRING",description:ITEM_HELP.name,control:sized(nameControl)}),
      // The type is one of the itp_type_* values the project's header_items.py
      // defines, so it is a list of those names, not a box a typo can brick an
      // armour piece in.
      detailField({label:"Type",property:"type",dataType:"ENUM",description:ITEM_HELP.type,
        control:sized(WarbandFieldControls.enumSelect({options:types,value:itemTypeFromFlags(flagsExpression),readOnly,
          apply:value=>setItemType(item,value)}))}),
      detailField({label:"Value",property:"value",dataType:"EXPR",description:ITEM_HELP.value,control:sized(valueControl)}),
      detailField({label:"Weight",property:"weight",dataType:"FLOAT",description:ITEM_HELP.weight,control:sized(weightControl())}),
      // The table shows an inventory mesh for every item, so the panel says
      // which mesh that is and lets the reader change it here.
      detailField({label:"Inventory mesh",property:"inventoryMesh",dataType:"MESH",showType:false,description:ITEM_HELP.inventoryMesh,
        control:entries.length?itemMeshControl(item,0,entries,readOnly):LexeditorUI.readonlyField("No mesh in this record",{format:false})})
    ]});
    const body=[core];
    // A field only leaves the "Module System fields" list when a control was
    // actually built for it, so nothing becomes unreachable when a project's
    // headers do not name a set (a compiled module, or a header without
    // imodbits_*).
    const handled=["id","name","value"];
    // Stats read as one row per stat with a number box per value. A stats
    // expression this editor cannot take apart keeps its source control.
    const statsExpression=String(effectiveItemField(item,"stats")).trim();
    const calls=statsExpression===""||statsExpression==="0"?[]:WarbandFieldControls.parseCalls(statsExpression);
    if(calls){
      const named=calls.filter(call=>call.name!=="weight");
      handled.push("stats");
      body.push(detailGroup({title:"Stats",help:LexeditorUI.infoHelp("One row per stat macro in this item's stats field. Weight has its own row above, so it is not repeated here."),
        body:WarbandFieldControls.statRows({calls:named,macros:(state.items?.choices?.stats||[]).filter(name=>name!=="weight"),readOnly,
          arguments:state.items?.choices?.statArguments||{},
          apply:value=>{setItemField(item,"stats",value||"0");render();}})}));
    }else{
      handled.push("stats");
      body.push(detailGroup({title:"Stats",body:[detailField({label:"Stat macros",property:"stats",dataType:"EXPR",description:ITEM_HELP.stats,
        control:(()=>{const control=itemExpressionControl(item,"stats");control.disabled=readOnly;return control;})()}),
        detailField({label:"Weight",property:"weight-from-stats",dataType:"FLOAT",description:ITEM_HELP.weight,control:sized(weightControl())})]}));
    }
    if(bits.length){
      handled.push("flags");
      body.push(WarbandFieldControls.bitFields({label:"Flags",help:ITEM_HELP.flags,flags:bits,expression:flagsExpression,readOnly,
        // The item's Type property owns the itp_type_* part of this same field,
        // so it is not repeated as an "also set" part of the flag list.
        ownOther:/^itp_type_[a-z0-9_]+$/i,
        apply:value=>{setItemField(item,"flags",value);render();}}));
    }
    const modifierChoices=state.items?.choices?.modifierBits||[];
    if(modifierChoices.length){
      handled.push("modifierBits");
      body.push(WarbandFieldControls.bitFields({label:"Modifier bits",help:ITEM_HELP.modifierBits,flags:modifierChoices,
        expression:String(effectiveItemField(item,"modifierBits")),readOnly,
        apply:value=>{setItemField(item,"modifierBits",value);render();}}));
    }
    if(meshNames.length){
      handled.push("meshes");
      body.push(detailGroup({title:"Meshes",help:LexeditorUI.infoHelp(ITEM_HELP.meshes),
        body:WarbandFieldControls.meshRows({label:"Mesh",property:"mesh",entries,choices:itemMeshChoices(),readOnly,
          apply:next=>setItemMeshes(item,next),open:entry=>openItemMesh(entry.name)})}));
    }
    const sourceFields=(item.fieldOrder||[]).filter(key=>!handled.includes(key));
    if(sourceFields.length){
      body.push(detailGroup({title:"Module System fields",body:sourceFields.map(key=>detailField({label:itemFieldLabel(key),property:key,dataType:"EXPR",description:ITEM_HELP[key]||"",control:(()=>{const control=itemExpressionControl(item,key);control.disabled=readOnly;return control;})()}))}));
    }
    // The heading icon is the shared 3D viewer control: pressing it slides the
    // model out of the panel, and the same slot carries the close mark. The
    // panel had the icon and the renderer but never the control, so the viewer
    // was there and unreachable.
    const detail=detailPanel({className:"warband-item-detail",icon:thumbnail,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(item.name,24)),identity:item.id,body,
      modelPreview:item.inventoryMesh?{
        label:`${item.name} model`,
        openLabel:`Open the ${item.name} model`,
        closeLabel:`Close the ${item.name} model`,
        content:()=>warbandPreviewStage(item),
      }:null});
    if(item.inventoryMesh)requestAnimationFrame(()=>loadWarbandIcon(item,detail,thumbnail,thumbnailMessage));
    return detail;
  }
  // The drawer's own stage. The icon in the heading stays a still thumbnail;
  // this is the turnable model behind it.
  function warbandPreviewStage(item){
    const stage=LexeditorUI.modelStage({className:"warband-preview-stage",busy:Boolean(item.inventoryMesh),message:"This item has no inventory mesh."}),message=stage.lexMessage;
    if(item.inventoryMesh)requestAnimationFrame(()=>loadWarbandModel(item,stage,message));
    return stage;
  }
  async function loadWarbandModel(item,stage,message){
    try{
      const response=await fetch(`/api/item-preview?mesh=${encodeURIComponent(item.inventoryMesh)}`);
      const data=await response.json();
      if(!response.ok||data.error)throw new Error(data.error||"Model unavailable");
      if(!stage.isConnected)return;
      const canvas=el("canvas",{"aria-label":`${item.name} model`});
      stage.replaceChildren(canvas);
      const controller=await createWarbandRenderer(canvas,data,true);
      if(!stage.isConnected){controller.dispose();return;}
      (window.__warbandPreview ||= []).push(controller);
    }catch(error){
      if(stage.isConnected){message.textContent="Model unavailable";message.title=error.message||String(error);stage.replaceChildren(message);}
    }
  }

  async function loadWarbandIcon(item,detail,thumbnail,message){
    const url=`/api/item-icon?mesh=${encodeURIComponent(item.inventoryMesh)}`;
    try{
      while(detail.isConnected){
        const response=await fetch(url);
        if(!detail.isConnected)return;
        if(response.status===202){await new Promise(resolve=>setTimeout(resolve,750));continue;}
        if(!response.ok){const error=await response.json();throw new Error(error.error||"Icon unavailable");}
        const blob=await response.blob();if(!detail.isConnected)return;
        const objectUrl=URL.createObjectURL(blob),image=el("img",{alt:`${item.name} inventory icon`});
        image.onload=image.onerror=()=>URL.revokeObjectURL(objectUrl);image.src=objectUrl;thumbnail.replaceChildren(image);return;
      }
    }catch(error){if(detail.isConnected){message.textContent="Icon unavailable";message.title=error.message;}}
  }

  async function createWarbandRenderer(canvas,data,interactive=true){
    const image=new Image();if(!data.texture)throw new Error("The material has no resolved texture.");
    await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error("The Warband DDS texture could not be loaded."));image.src=data.texture;});
    const gl=canvas.getContext("webgl2",{antialias:true,alpha:false});if(!gl)throw new Error("This window cannot start the WebGL 2 model renderer.");
    const compile=(type,source)=>{const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(shader));return shader;};
    const vertex=compile(gl.VERTEX_SHADER,`#version 300 es\nin vec3 aPosition;in vec3 aNormal;in vec2 aUv;uniform float uYaw,uPitch,uZoom,uAspect;out vec3 vNormal;out vec2 vUv;vec3 ry(vec3 v,float a){float c=cos(a),s=sin(a);return vec3(c*v.x+s*v.z,v.y,-s*v.x+c*v.z);}vec3 rx(vec3 v,float a){float c=cos(a),s=sin(a);return vec3(v.x,c*v.y-s*v.z,s*v.y+c*v.z);}void main(){vec3 p=rx(ry(aPosition,uYaw),uPitch),n=rx(ry(aNormal,uYaw),uPitch);vNormal=n;vUv=aUv;gl_Position=vec4(p.x*uZoom/uAspect,p.y*uZoom,p.z*.25,1.0);}`);
    const fragment=compile(gl.FRAGMENT_SHADER,`#version 300 es\nprecision highp float;in vec3 vNormal;in vec2 vUv;uniform sampler2D uDiffuse;uniform float uHasTexture;out vec4 outColor;vec3 linearize(vec3 c){return pow(max(c,vec3(0.0)),vec3(2.2));}void main(){vec3 n=normalize(vNormal);if(!gl_FrontFacing)n=-n;vec3 base=mix(vec3(.55,.48,.36),linearize(texture(uDiffuse,vUv).rgb),uHasTexture);float key=max(dot(n,normalize(vec3(-.3,.7,.65))),0.0),fill=max(dot(n,normalize(vec3(.7,.2,.5))),0.0);vec3 color=base*(.28+.82*key+.20*fill);color=color/(color+vec3(.62));outColor=vec4(pow(color,vec3(1.0/2.2)),1.0);}`);
    const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
    const g=data.geometry,b=g.bounds,center=b.min.map((value,index)=>(value+b.max[index])/2),largest=Math.max(...b.max.map((value,index)=>value-b.min[index]),.0001),scale=1.8/largest;
    const positions=new Float32Array(g.positions.length*3),normals=new Float32Array(g.normals.length*3),uvs=new Float32Array(g.texCoords.length*2);g.positions.forEach((row,index)=>{positions[index*3]=(row[0]-center[0])*scale;positions[index*3+1]=(row[2]-center[2])*scale;positions[index*3+2]=-(row[1]-center[1])*scale;});g.normals.forEach((row,index)=>{normals[index*3]=row[0];normals[index*3+1]=row[2];normals[index*3+2]=-row[1];});g.texCoords.forEach((row,index)=>{uvs[index*2]=row[0];uvs[index*2+1]=row[1];});
    const vao=gl.createVertexArray();gl.bindVertexArray(vao);const buffers=[];const attribute=(name,size,data)=>{const location=gl.getAttribLocation(program,name),buffer=gl.createBuffer();buffers.push(buffer);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,size,gl.FLOAT,false,0,0);};attribute("aPosition",3,positions);attribute("aNormal",3,normals);attribute("aUv",2,uvs);const indices=new Uint32Array(g.triangles.flat()),indexBuffer=gl.createBuffer();buffers.push(indexBuffer);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,indexBuffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);
    const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([170,148,112,255]));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.generateMipmap(gl.TEXTURE_2D);let hasTexture=0;if(data.texture){gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);gl.generateMipmap(gl.TEXTURE_2D);hasTexture=1;}
    const uniform=name=>gl.getUniformLocation(program,name),yawU=uniform("uYaw"),pitchU=uniform("uPitch"),zoomU=uniform("uZoom"),aspectU=uniform("uAspect"),hasTextureU=uniform("uHasTexture");let yaw=0,pitch=-.18,zoom=1,dragging=false,lastX=0,lastY=0,disposed=false;
    const draw=()=>{if(disposed)return;const rect=canvas.getBoundingClientRect(),ratio=Math.min(devicePixelRatio||1,2),width=Math.max(1,Math.floor(rect.width*ratio)),height=Math.max(1,Math.floor(rect.height*ratio));if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}gl.viewport(0,0,width,height);gl.clearColor(.07,.055,.035,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.useProgram(program);gl.uniform1f(yawU,yaw);gl.uniform1f(pitchU,pitch);gl.uniform1f(zoomU,zoom);gl.uniform1f(aspectU,width/height);gl.uniform1f(hasTextureU,hasTexture);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindVertexArray(vao);gl.drawElements(gl.TRIANGLES,indices.length,gl.UNSIGNED_INT,0);};
    const down=event=>{dragging=true;lastX=event.clientX;lastY=event.clientY;canvas.classList.add("dragging");canvas.setPointerCapture(event.pointerId);},move=event=>{if(!dragging)return;yaw+=(event.clientX-lastX)*.012;pitch=Math.max(-1.45,Math.min(1.45,pitch+(event.clientY-lastY)*.012));lastX=event.clientX;lastY=event.clientY;draw();},up=event=>{dragging=false;canvas.classList.remove("dragging");if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);},wheel=event=>{event.preventDefault();zoom=Math.max(.35,Math.min(2.8,zoom*Math.exp(-event.deltaY*.001)));draw();};const reset=()=>{yaw=0;pitch=-.18;zoom=1;draw();};if(interactive){canvas.addEventListener("pointerdown",down);canvas.addEventListener("pointermove",move);canvas.addEventListener("pointerup",up);canvas.addEventListener("pointercancel",up);canvas.addEventListener("wheel",wheel,{passive:false});canvas.addEventListener("dblclick",reset);}let observerFrame=0;const observer=new ResizeObserver(()=>{if(observerFrame)cancelAnimationFrame(observerFrame);observerFrame=requestAnimationFrame(()=>{observerFrame=0;draw();});});observer.observe(canvas);requestAnimationFrame(draw);
    return{dispose(){disposed=true;observer.disconnect();if(observerFrame)cancelAnimationFrame(observerFrame);for(const [event,handler] of [["pointerdown",down],["pointermove",move],["pointerup",up],["pointercancel",up],["wheel",wheel],["dblclick",reset]])canvas.removeEventListener(event,handler);gl.deleteShader(vertex);gl.deleteShader(fragment);buffers.forEach(buffer=>gl.deleteBuffer(buffer));gl.deleteTexture(texture);gl.deleteVertexArray(vao);gl.deleteProgram(program);}};
  }
  function renderTroops(){
    const base=state.filters.cut?state.troops.rows.filter(row=>row.status==="CUT"):state.troops.rows;
    const cutFilter=el("label",{class:"lex-bottom-filter"},el("input",{type:"checkbox",checked:state.filters.cut,onchange:event=>{state.filters.cut=event.target.checked;state.pages.troops=0;render();}})," Cut only");
    renderTableView("troops",base,[{key:"status",label:"State",render:row=>row.status==="CUT"?"Cut":"Active"},{key:"id",label:"ID"},{key:"name",label:"Name"},{key:"level",label:"Level"},{key:"faction",label:"Faction"},{key:"line",label:"Line"}],{key:troopRowKey,selected:()=>state.selectedTroop,setSelected:value=>{state.selectedTroop=value;},filters:[cutFilter],detail:troopEditorPanel});
  }
  function troopTreeDetail(node){
    disposeWarbandPreview();
    if(!node)return detailPanel({title:"Select a troop"});
    // A troop has no mesh of its own: it is a body, a face built from morph
    // keys and a list of equipment. The equipment is the part that resolves to
    // meshes, so the viewer opens the troop's gear - which is what there is to
    // look at - rather than staying shut because a troop is not one model.
    // The tree node carries only the upgrade graph, so the troop's own record
    // is what holds its equipment.
    const matching=state.troops?.rows?.filter(row=>row.id===node.id)||[],record=matching.find(row=>row.status!=="CUT")||matching[0]||node;
    // module_troops.py names an item "itm_leather_cap"; the item table's own id
    // is "leather_cap". Matching the two without stripping the prefix found
    // nothing, so the viewer stayed shut on every troop in the game.
    const gear=(record.items||[])
      .map(id=>{const bare=String(id).replace(/^itm_/,"");
        return state.items?.rows?.find(row=>row.id===bare||row.id===id);})
      .filter(item=>item&&item.inventoryMesh)
      .slice(0,12);
    // The shared viewer control lives in the heading's icon slot, so a panel
    // without an icon has nowhere to put it. A troop's icon is the first piece
    // of equipment it carries, which is also the first thing the drawer shows.
    let icon=null;
    if(gear.length){
      icon=LexeditorUI.iconSlot({className:"warband-item-thumbnail",message:"Preparing icon…"});
      const iconMessage=icon.lexMessage;
      requestAnimationFrame(()=>loadWarbandIcon(gear[0],icon,icon,iconMessage));
    }
    return detailPanel({className:"warband-tree-detail",icon,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(node.name||node.id,24)),identity:node.id,
      modelPreview:gear.length?{
        label:`${node.name||node.id} equipment`,
        openLabel:`Open ${node.name||node.id}'s equipment`,
        closeLabel:`Close ${node.name||node.id}'s equipment`,
        content:()=>LexeditorUI.figureGrid(gear.map(item=>({media:warbandPreviewStage(item),caption:item.name||item.id}))),
      }:null,
      body:node.missing?[LexeditorUI.notice({tone:"warning",message:"This upgrade refers to a troop missing from the parsed active source."})]:[
        ...troopFields(record)
      ]});
  }
  function renderUpgrades(keep){
    const all=WarbandTroopTrees.build(state.troops.rows,state.upgrades.rows);
    const factions=[...new Set(all.flatMap(t=>t.factions))].sort();
    if(!factions.includes(state.treeFaction))state.treeFaction=factions[0]||"";
    const trees=all.filter(t=>t.factions.includes(state.treeFaction));
    const tree=trees.find(t=>t.id===state.treeId)||trees[0];state.treeId=tree?.id||"";
    const factionSelect=el("select",{"aria-label":"Troop tree faction",onchange:e=>{state.treeFaction=e.target.value;state.treeId="";renderUpgrades();}},
      ...factions.map(f=>el("option",{value:f,selected:f===state.treeFaction},f)));
    // Each tree is its own subtab. A dropdown hid how many trees a faction has
    // and made moving between two of them a two-step gesture; a bar shows the
    // whole set and switches in one press. A faction with a single tree shows
    // no bar at all, which the shared control handles.
    const treeTabs=LexeditorUI.subtabBar({
      tabs:trees.map(t=>({id:t.id,label:t.label})),
      active:tree?.id,label:"Troop trees",
      change:value=>{state.treeId=value;renderUpgrades();},
    });
    $("#toolbar").replaceChildren(el("label",{},"Faction ",factionSelect));
    if(!tree){$("#main").replaceChildren(detailPanel({className:"lex-information-panel",title:"Troop trees",body:[LexeditorUI.detailNote("No upgrade trees are available in the selected project's Module System source.")]}));return;}
    const graph=WarbandTroopTrees.layout(tree), byId=new Map(graph.nodes.map(n=>[n.id,n]));
    let selected=byId.get(state.selectedUpgrade)||byId.get(tree.roots[0])||graph.nodes[0];state.selectedUpgrade=selected.id;
    const master=LexeditorUI.treeGraph({width:graph.width,height:graph.height,edges:graph.edges,selected:selected.id,label:"Bottom-up troop upgrade tree",
      nodes:graph.nodes.map(node=>({id:node.id,x:node.x,y:node.y,label:node.name||node.id,sub:node.id,missing:node.missing})),
      note:graph.cyclic?LexeditorUI.notice({tone:"warning",message:"Cyclic upgrade links detected. Cycle members share a row; arrows preserve the source links."}):null,
      // A new selection redraws the page with its detail; the tree stays
      // scrolled where the reader left it, with the pressed node focused.
      select:node=>{state.selectedUpgrade=node.id;renderUpgrades({left:master.scrollLeft,top:master.scrollTop});}});
    $("#main").replaceChildren(LexeditorUI.stack(treeTabs,
      masterDetail(master,troopTreeDetail(selected),"warband-trees",{splitKey:"warband-troop-trees",defaultSplit:65})));
    if(keep){master.scrollLeft=keep.left;master.scrollTop=keep.top;master.querySelector(`[data-node="${CSS.escape(selected.id)}"]`)?.focus();}
    else requestAnimationFrame(()=>{if(master.isConnected)master.scrollTop=master.scrollHeight;});
  }

  async function selectModule(name){state.selectedModule=name;state.manual=await api(`/api/manual?module=${encodeURIComponent(name)}`);renderManuals();}
  function renderManuals(){
    $("#toolbar").replaceChildren(el("span",{},`${state.modules.modules.length} installed modules`));
    const master=list({rows:state.modules.modules,key:name=>name,selected:state.selectedModule,select:selectModule,render:name=>el("div",{},el("b",{},name))});
    const detail=state.manual
      ?detailPanel({title:state.manual.module,meta:`${state.manual.pages.length} pages`,body:state.manual.pages.map(page=>
        LexeditorUI.detailSection({title:page.title,body:[LexeditorUI.detailText(page.body.trim())]}))})
      :detailPanel({title:"Mod manuals",body:[LexeditorUI.detailNote("Select an installed mod to read its manual.")]});
    $("#main").replaceChildren(masterDetail(master,detail,"",{splitKey:"warband-manuals",defaultSplit:38}));
  }

  function settingDetail(row){
    return detailPanel({title:el("h2",{class:"lex-detail-panel-title"},bitmapText(row.key,24)),meta:row.section,body:[LexeditorUI.detailSection({body:[
      detailField({label:"Value",property:"value",control:el("input",{value:effectiveSetting(row),oninput:event=>{if(event.target.value===row.value)delete state.settingEdits[row.line];else state.settingEdits[row.line]=event.target.value;shell.refresh();}})}),
      LexeditorUI.detailNote(row.description||"No description.")]})]});
  }
  async function saveSettings(){
    const edits=Object.entries(state.settingEdits).map(([line,value])=>({line:+line,value}));if(!edits.length)return;
    const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};await buildSavedModule();shell.history.clear();setStatus(`Saved ${result.saved} settings and build verified`);renderSettings();shell.refresh();
  }
  function discardSettings(){state.settingEdits={};setStatus("Restored the last saved settings");renderSettings();shell.refresh()}
  function renderSettings(){
    // No plugin Save button in the bar: the shell's own Save owns every
    // unsaved change in the editor, and a second one beside it asks the reader
    // which of the two they meant.
    renderTableView("settings",state.settings.rows,[{key:"key",label:"Key"},{key:"section",label:"Section"},{key:"value",label:"Value",render:row=>el("span",{title:effectiveSetting(row)},effectiveSetting(row))}],
      {key:row=>String(row.line),selected:()=>state.selectedSetting,setSelected:value=>{state.selectedSetting=value;},
       searchFields:["section","key","value","description"],changed:row=>state.settingEdits[row.line]!==undefined,detail:settingDetail});
  }

  async function selectCatalog(row){
    if(moduleRecords?.fileHasEdits(row.filename)){showAlert({title:"Structured edits are open",items:[{item:row.filename,issue:"Discard or save the Misc. changes before opening this file as raw source."}],closeLabel:"Close"});return;}
    if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text&&!confirm("Discard the unsaved source-file edit?"))return;
    state.selectedFile=row.filename;state.catalogFile=await api(`/api/catalog/file?name=${encodeURIComponent(row.filename)}`);state.catalogDraft=state.catalogFile.text||"";shell.history.clear();renderDataMap();
  }
  function closeCatalog(){
    if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text&&!confirm("Discard the unsaved source-file edit?"))return;
    state.selectedFile="";state.catalogFile=null;state.catalogDraft="";shell.history.clear();renderDataMap();
  }
  function sourceDialog(){
    if(!state.catalogFile)return null;
    const backdrop=el("div",{class:"lex-dialog-backdrop"});
    const panel=el("div",{class:"lex-dialog lex-source-dialog"},
      el("div",{class:"lex-source-dialog-head"},el("h2",{},state.catalogFile.filename),el("button",{onclick:closeCatalog,"aria-label":"Close source editor"},"×")),
      el("p",{},state.catalogFile.editable?`${state.catalogFile.path} [${state.catalogFile.encoding}]`:state.catalogFile.reason),
      state.catalogFile.editable?el("textarea",{value:state.catalogDraft,oninput:event=>{state.catalogDraft=event.target.value;shell.refresh();}},state.catalogDraft):"");
    backdrop.append(panel);backdrop.addEventListener("click",event=>{if(event.target===backdrop)closeCatalog();});return backdrop;
  }
  function renderDataMap(){
    window.LexeditorUI?.dismissDialogs?.();
    const view=LexeditorUI.dataMap({rows:state.datamap.rows,query:state.filters.datamap,
      status:state.filters.mapStatus,page:state.pages.datamap,sort:state.sorts.datamap,
      tableClass:"warband-record-list",open:row=>row.dataset?moduleRecords.open(row.dataset):navigate(row.view),openSource:selectCatalog,
      changeQuery:value=>{state.filters.datamap=value;state.pages.datamap=0;renderDataMap()},
      changeStatus:value=>{state.filters.mapStatus=value;state.pages.datamap=0;renderDataMap()},
      changePage:value=>{state.pages.datamap=value;renderDataMap()},
      changeSort:key=>sort("datamap",key)});
    state.pages.datamap=view.page;$("#toolbar").replaceChildren(...view.controls);
    $("#main").replaceChildren(view.content);
    const dialog=sourceDialog();if(dialog)document.body.append(dialog);
  }

  function renderDashboard(){
    $("#toolbar").replaceChildren();
    const problems=state.dashboard.problems;
    $("#main").replaceChildren(detailPanel({className:"lex-information-panel",icon:LexeditorUI.infoIcon(),title:"Information",meta:"Plugin and path health, mod manuals, and the build log",body:[
      LexeditorUI.detailSection({title:"STATUS",body:problems.length
        ?problems.map(problem=>LexeditorUI.notice({tone:"warning",message:problem}))
        :[LexeditorUI.detailNote("All configured paths found.")]}),
      LexeditorUI.detailSection({title:"MOD MANUALS",body:[LexeditorUI.actionRow(el("button",{type:"button",onclick:()=>navigate("manuals")},"Read installed mod manuals"))]}),
      LexeditorUI.detailSection({title:"LOG",body:[LexeditorUI.logView(state.build.lines.join("")||"No save or build has run in this session.")]}),
      LexeditorUI.modLoaderSection({
        loader:"Warband loads a module folder chosen in its own launcher. There is no separate mod loader.",
        output:"Lexeditor builds a saved module folder under the game's Modules directory; the launcher lists it as its own entry.",
        order:"Only one module runs at a time, so modules do not stack or conflict. Combining changes means building them into one module.",
        safety:"The Native module and the installed game files are never written. A build only ever creates or updates its own module folder.",
        removal:"Pick a different module in the launcher, and delete the generated module folder to remove it entirely.",
      }),
    ]}));
  }

  async function buildSavedModule(){
    const started=await api("/api/build/start",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    if(!started.started)throw new Error(started.reason||"The Warband build could not start.");
    state.build={cursor:0,lines:[],running:true,returnCode:null};setStatus("Saving and building…");
    while(state.build.running){
      await new Promise(resolve=>setTimeout(resolve,200));
      const result=await api(`/api/build/status?cursor=${state.build.cursor}`);
      state.build.cursor=result.cursor;state.build.lines.push(...result.lines);state.build.running=result.running;state.build.returnCode=result.returnCode;
    }
    if(state.build.returnCode!==0||!state.build.lines.join("").includes("Build verified:")){
      throw new Error("The source was saved, but the module build failed. Open Info to read the log.");
    }
    setStatus("Saved and build verified");
  }

  async function saveAll(){
    try{
      const itemSourceDirty=state.catalogFile?.filename==="module_items.py"&&state.catalogFile.editable&&state.catalogDraft!==state.catalogFile.text;
      if(itemDirtyCount()&&itemSourceDirty)throw new Error("Items has structured edits while module_items.py also has unsaved source edits. Save or discard one editing path before using the other.");
      if(Object.keys(state.settingEdits).length){const edits=Object.entries(state.settingEdits).map(([line,value])=>({line:+line,value}));const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};setStatus(`Saved ${result.saved} settings`);}
      const troopEdits=Object.values(state.troopEdits).filter(row=>Object.keys(row.fields).length);
      if(troopEdits.length){
        if(state.catalogFile?.filename==="module_troops.py"&&state.catalogDraft!==state.catalogFile.text)throw new Error("Save or discard the troop source draft first.");
        await api("/api/troops/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sha256:state.troops.sha256,edits:troopEdits})});
        state.troops=await api("/api/troops");state.troopEdits={};
        if(state.catalogFile?.filename==="module_troops.py"){state.catalogFile=await api("/api/catalog/file?name=module_troops.py");state.catalogDraft=state.catalogFile.text;}
      }
      if(itemDirtyCount()){
        const selectedRecord=state.items.rows.find(row=>itemRowKey(row)===state.selectedItem)?.recordIndex,edits=Object.values(state.itemEdits);
        const result=await api("/api/items/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sha256:state.items.sha256,edits})});state.items=await api("/api/items");state.itemEdits={};
        if(selectedRecord!==undefined){const selected=state.items.rows.find(row=>row.recordIndex===selectedRecord);state.selectedItem=selected?itemRowKey(selected):"";}
        if(state.catalogFile?.filename==="module_items.py"){state.catalogFile=await api("/api/catalog/file?name=module_items.py");state.catalogDraft=state.catalogFile.text;}
        setStatus(`Saved ${result.saved} item records`);
      }
      const moduleResult=await moduleRecords.saveAll();
      if(moduleResult.saved){if(moduleResult.files.includes(state.catalogFile?.filename)){state.catalogFile=await api("/api/catalog/file?name="+encodeURIComponent(state.catalogFile.filename));state.catalogDraft=state.catalogFile.text;}setStatus("Saved "+moduleResult.saved+" Module System records");}
      if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text){const result=await api("/api/catalog/file/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:state.catalogFile.filename,text:state.catalogDraft,encoding:state.catalogFile.encoding,sha256:state.catalogFile.sha256})});state.catalogFile.text=state.catalogDraft;state.catalogFile.sha256=result.sha256;setStatus(`Saved ${state.catalogFile.filename}; backup created`);}
      await buildSavedModule();
      shell.history.clear();shell.refresh();render();
    }catch(error){setStatus("Save failed");showAlert({title:"Save failed",items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }

  // Music, factions, skills and sounds are areas of their own; Misc. keeps the
  // rest behind a subtab bar.
  const views={items:renderItems,misc:()=>moduleRecords.render("misc"),music:()=>moduleRecords.render("music"),factions:()=>moduleRecords.render("factions"),skills:()=>moduleRecords.render("skills"),sounds:()=>moduleRecords.render("sounds"),manuals:renderManuals,upgrades:renderUpgrades,troops:renderTroops,tweaks:renderSettings,datamap:renderDataMap,dashboard:renderDashboard};
  function navigate(tab){disposeWarbandPreview();state.tab=tab;render();}
  function renderVanilla(){$("#toolbar").replaceChildren();$("#main").replaceChildren(detailPanel({className:"lex-information-panel",title:"Vanilla",body:[LexeditorUI.detailSection({body:[
    LexeditorUI.detailText("The installed Native module is read-only. Its generated text files do not contain the Module System source used by this editor."),
    LexeditorUI.detailText("Select a mod to edit Items, Misc., Troops, Troop Trees, or Tweaks.")]})]}))}
  function render(){document.querySelectorAll("nav button").forEach(button=>button.classList.toggle("active",button.dataset.tab===state.tab));if(state.booting)return;if(state.activeSource!=="mine"&&!['manuals','datamap','dashboard'].includes(state.tab))renderVanilla();else views[state.tab]();shell.refresh();}
  async function switchProjectSource(value){state.activeSource=String(value||"mine")==="vanilla"?"vanilla":"mine";shell.history?.clear();render()}
  
