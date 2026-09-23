"use strict";
  function matchingItems(){
    const needle=state.itemQuery.trim().toLowerCase();
    return (state.items?.rows||[]).filter(item=>(!needle||[item.name,item.friendlyName,item.type,item.icon].some(value=>String(value||"").toLowerCase().includes(needle)))&&(!state.itemSource||item.source===state.itemSource));
  }
  function itemValue(item,field){const key=`${item.id}|${field.field}`;return Object.prototype.hasOwnProperty.call(state.itemEdits,key)?state.itemEdits[key]:field.value;}
  function editItem(item,field,value){const key=`${item.id}|${field.field}`;if(value===field.value)delete state.itemEdits[key];else state.itemEdits[key]=value;shell.refresh();}
  function selectItem(item){state.itemSelected=item.id;renderItems();}
  const ITEM_COLUMNS=[
    {key:"name",label:"Name",width:"minmax(0,1.35fr)",render:item=>cell(item.friendlyName||item.name||`Item ${item.index}`)},
    {key:"id",label:"ID",width:"minmax(0,1.05fr)",render:item=>cell(item.name||`#${item.index}`)},
    {key:"type",label:"Type",width:"minmax(0,.7fr)",render:item=>cell(item.type)},
    {key:"source",label:"Source",width:"minmax(0,.8fr)",render:item=>cell(item.sourceLabel)}];
  function scalarControl(item,field){
    const value=itemValue(item,field);
    const vanillaItem=state.vanilla.items?.rows?.find(row=>row.id===item.id),vanilla=vanillaItem?.fields?.find(value=>value.field===field.field)?.value;
    let control;if(field.control==="checkbox")control=el("input",{type:"checkbox",checked:String(value).toLowerCase()==="true",disabled:state.activeSource!=="mine",onchange:event=>editItem(item,field,event.target.checked?"true":"false"),"aria-label":field.field});
    else if(field.control==="select")control=el("select",{disabled:state.activeSource!=="mine",onchange:event=>editItem(item,field,event.target.value)},...(field.options||[]).map(option=>el("option",{value:option,selected:String(option)===String(value)},option||"(none)")));
    else if(field.control==="number")control=el("input",{type:"number",value,step:String(field.step??"any"),min:field.minimum,max:field.maximum,disabled:state.activeSource!=="mine",oninput:event=>editItem(item,field,event.target.value)});
    else control=el("input",{type:"text",value,spellcheck:false,disabled:state.activeSource!=="mine",oninput:event=>editItem(item,field,event.target.value)});
    return sourceControl(control,()=>itemValue(item,field),vanilla,next=>editItem(item,field,String(next)));
  }
  function itemDetail(){
    const item=(state.items?.rows||[]).find(row=>row.id===state.itemSelected);
    if(!item)return LexeditorUI.detailPanel({className:"record-detail item-detail",title:"Select an inventory item",body:[LexeditorUI.detailNote("Edits become full XML overrides in C:\\RDRMod. The installed content.rpf stays unchanged.")]});
    // An item's name is the heading, so the heading is where it is typed. It
    // used to be two ordinary rows further down - NAME and FRIENDLYNAME - so
    // the name a reader sees at the top was the one copy they could not
    // change. NAME is the record's key and the override's filename, so it
    // stays read-only, under the heading where the other identities go.
    const fieldNamed=wanted=>item.fields.find(field=>String(field.field).toLowerCase()===wanted);
    const friendly=fieldNamed("friendlyname");
    const rest=item.fields.filter(field=>!["name","friendlyname"].includes(String(field.field).toLowerCase()));
    return LexeditorUI.detailPanel({className:"record-detail item-detail",
      title:(friendly?itemValue(item,friendly):"")||item.friendlyName||item.name||`Item ${item.index}`,
      renameLabel:"Item name",
      renameRecord:state.activeSource==="mine"&&friendly?value=>editItem(item,friendly,value):undefined,
      identity:LexeditorUI.recordId(item.index),
      meta:item.name||"",
      actions:projectBadge(item),
      body:[
        detailField("Record type",shown(item.type),"","The XML element this record comes from. It decides which fields the game reads."),
        detailField("Dataset",shown(item.sourceLabel),"","Which shipped data file this item was defined in: the base game or one of its DLC."),
        detailField("Vanilla source",shown(item.sourcePath),"","The untouched file inside the installed content.rpf. Lexeditor never writes here."),
        detailField("Project override",shown(item.projectPath),"","Where your edit is written, as a full XML override. The game loads this instead of the vanilla file."),
        // No bubble on the data fields themselves. A generic note repeated on
        // every scalar is noise, and the four rows above already say where the
        // value comes from and where an edit is written.
        ...rest.map(field=>detailField(field.field,scalarControl(item,field)))]});
  }
  function renderItems(){
    const rows=matchingItems();
    $("#toolbar").replaceChildren();
    const sourceFilter=el("select",{"aria-label":"Filter items by source",onchange:event=>{state.itemSource=event.target.value;state.itemPage=0;renderItems();}},el("option",{value:"",selected:!state.itemSource},"Base game and DLC"),...(state.items?.sources||[]).map(source=>el("option",{value:source.id,selected:source.id===state.itemSource},source.label)));
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(state.itemEdits,()=>{state.itemPage=0}),rows,key:item=>item.id,slots:false,page:state.itemPage,pageSize:state.itemPageSize,selected:state.itemSelected,noun:"items",splitKey:"rdr-items",className:"rdr-split",defaultSplit:44,fit:{minRowHeight:32},
      search:{key:"rdr-items",value:state.itemQuery,placeholder:"Search RDR inventory items…",change:value=>{state.itemQuery=value;state.itemPage=0;renderItems();}},filters:[sourceFilter],
      master:({rows,selected,select})=>columnList({rows,key:item=>item.id,columns:ITEM_COLUMNS,selected,selectedClass:"sel",select,class:"rdr-record-list","aria-label":"RDR inventory items"}),
      detail:()=>itemDetail(),sync:next=>{state.itemPage=next.page;state.itemPageSize=next.pageSize;state.itemSelected=next.selected||"";},change:next=>{state.itemPage=next.page;state.itemPageSize=next.pageSize;state.itemSelected=next.selected||"";renderItems();}}));shell.refresh();
  }
