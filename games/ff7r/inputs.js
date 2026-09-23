"use strict";
  function setScalar(row,prop,value){row.values[prop.name]=value;refreshShell()}
  function setArrayValue(row,prop,index,value){if(!Array.isArray(row.values[prop.name]))return;row.values[prop.name][index]=value;refreshShell()}
  function numericInput(row,prop,index=null){const current=index===null?row.values[prop.name]:row.values[prop.name][index];const attrs={type:"number",value:current,disabled:state.activeSource!=="mine"||!prop.editable,oninput:event=>{if(event.target.value==="")return;const value=prop.type==="FLOAT"?Number(event.target.value):Number.parseInt(event.target.value,10);if(index===null)setScalar(row,prop,value);else setArrayValue(row,prop,index,value)}};const low=semanticMin(prop),high=semanticMax(prop);if(low!==null&&low!==undefined)attrs.min=low;if(high!==null&&high!==undefined)attrs.max=high;attrs.step=prop.type==="FLOAT"?"any":1;return el("input",attrs)}
  function percentInput(row,prop,index){const current=row.values[prop.name]?.[index]??0;return el("input",{type:"number",min:0,max:100,step:1,value:current,disabled:state.activeSource!=="mine"||!prop.editable,oninput:event=>{if(event.target.value==="")return;const value=Number.parseInt(event.target.value,10);if(Number.isFinite(value)&&value>=0&&value<=100)setArrayValue(row,prop,index,value)},onchange:event=>{let value=Number.parseInt(event.target.value,10);if(!Number.isFinite(value))value=current;value=Math.max(0,Math.min(100,value));event.target.value=String(value);setArrayValue(row,prop,index,value)}})}
  function boolInput(row,prop,index=null){const current=index===null?row.values[prop.name]:row.values[prop.name][index];return el("input",{type:"checkbox",checked:!!current,disabled:state.activeSource!=="mine"||!prop.editable,onchange:event=>{if(index===null)setScalar(row,prop,event.target.checked);else setArrayValue(row,prop,index,event.target.checked)}})}
  function nameInput(row,prop,index=null,source=null){const current=index===null?row.values[prop.name]:row.values[prop.name][index];const select=el("select",{disabled:state.activeSource!=="mine"||!prop.editable,onchange:event=>{if(index===null)setScalar(row,prop,event.target.value);else setArrayValue(row,prop,index,event.target.value)}});for(const name of (source||state.data).names){const option=el("option",{value:name},name);option.selected=name===current;select.append(option)}return select}
  function semanticItemInput(row,prop,index){const current=row.values[prop.name]?.[index]??"";const choices=[...(state.loot?.itemChoices||[])];if(current&&!choices.some(choice=>choice.id===current))choices.unshift({id:current,name:current});const select=el("select",{disabled:state.activeSource!=="mine"||!prop.editable,onchange:event=>setArrayValue(row,prop,index,event.target.value)});for(const choice of choices){const option=el("option",{value:choice.id},choice.name&&choice.name!==choice.id?`${choice.name} (${choice.id})`:choice.id);option.selected=choice.id===current;select.append(option)}return select}
  function readonlyResolved(value){const resolved=resolvedText(value);return resolved?el("div",{},readonlyField(resolved),detailNote(value)):readonlyField(String(value??""))}
  // A value's storage type is not always the type a person should edit. CanSale
  // is stored as a byte but only ever means yes or no, so it is presented as a
  // switch and written back as 0 or 1. Add a field here when the schema type is
  // wider than the meaning.
  // The generic Misc tab can open any DataObject, but "open the table called
  // PlayerParameter" is not an answer to "where do I edit character stats".
  // These are the tables worth their own tab, with the columns that make the
  // list readable at a glance; everything else stays one click away in Misc.
  // Property names are the installed game's own, including Square's spelling
  // of Spilit for Spirit.
  const CURATED_TABLES=[
    {id:"characters",label:"Characters",basename:"playerparameter",
     noun:"stat rows",columns:["HPMax","MPMax","Strength","Magic","Vitality","Spilit"]},
    {id:"enemies",label:"Enemies",basename:"enemyparameter",
     noun:"enemies",columns:["HPMax","BPMax","Strength","Magic","Vitality","Spilit"]},
    {id:"abilities",label:"Abilities",basename:"battleability",
     noun:"abilities",columns:["ATB"]},
  ];
  const curatedSpec=tab=>CURATED_TABLES.find(entry=>entry.id===tab)||null;
  // Every archive holding a table of this name. FF7R ships one EnemyParameter
  // per field map - eight of them - so taking the first match showed one
  // enemy and silently hid the rest.
  const curatedAssets=spec=>assets().filter(item=>
    String(item.asset||"").split("/").pop().toLowerCase().replace(/\.uasset$/,"")===spec.basename)
    .sort((a,b)=>Number(/\/Resident\//i.test(b.asset))-Number(/\/Resident\//i.test(a.asset)));
  const curatedAsset=spec=>curatedAssets(spec)[0]||null;
  const SEMANTIC_TYPES={CanSale:"BOOL"};
  // The storage type is a signed 32-bit integer, so the schema's honest range is
  // plus or minus two billion. A price is not, and a slider handed that range
  // put -24832854 into a Buy Price on a drag to the middle. These are the
  // meanings, not the storage limits, and they only ever narrow.
  const SEMANTIC_BOUNDS={BuyValue:{min:0,max:99999999},SaleValue:{min:0,max:99999999},
    MaxCount:{min:0,max:99}};
  function semanticMin(prop){
    const bound=SEMANTIC_BOUNDS[prop.name];
    if(!bound)return prop.min;
    return prop.min===null||prop.min===undefined?bound.min:Math.max(Number(prop.min),bound.min);
  }
  function semanticMax(prop){
    const bound=SEMANTIC_BOUNDS[prop.name];
    if(!bound)return prop.max;
    return prop.max===null||prop.max===undefined?bound.max:Math.min(Number(prop.max),bound.max);
  }
  function semanticType(prop){
    const wanted=SEMANTIC_TYPES[prop.name];
    if(!wanted)return prop.type;
    if(wanted==="BOOL"&&["BYTE","INT16","UINT16","INT32"].includes(prop.type))return "BOOL";
    return prop.type;
  }
  function byteBoolInput(row,prop,index=null){
    const current=index===null?row.values[prop.name]:row.values[prop.name][index];
    return el("input",{type:"checkbox",checked:Number(current)!==0,
      disabled:state.activeSource!=="mine"||!prop.editable,
      "aria-label":prop.label||prop.name,
      onchange:event=>{const value=event.target.checked?1:0;
        if(index===null)setScalar(row,prop,value);else setArrayValue(row,prop,index,value)}});
  }
  function scalarControl(row,prop,index=null,source=null){if(semanticType(prop)==="BOOL"&&prop.type!=="BOOL")return byteBoolInput(row,prop,index);if(prop.type==="BOOL")return boolInput(row,prop,index);if(prop.type==="ENUM")return nameInput(row,prop,index,source);if(["BYTE","INT16","UINT16","INT32","FLOAT"].includes(prop.type))return numericInput(row,prop,index);const value=index===null?row.values[prop.name]:row.values[prop.name][index];return readonlyResolved(value)}
  // An array property with nothing in it used to render an empty box: a
  // fifteen-pixel sliver with a name beside it and no control, which reads as
  // a broken property rather than an empty one. It says it is empty instead.
  function propertyControl(row,prop,source=null){
    if(!prop.array)return scalarControl(row,prop,null,source);
    const values=row.values[prop.name]||[];
    if(!values.length)return readonlyField("None");
    return LexeditorUI.controlGroup(values.map((_value,index)=>
      ({label:`#${index+1}`,control:scalarControl(row,prop,index,source)})));
  }
  function propertyHelp(prop){if(!prop.editable)return infoHelp("This DataObject stores this value in a form Lexeditor cannot safely rewrite in place.");if(prop.type==="ENUM")return infoHelp("This value is an Unreal FName. A same-size edit can choose only a name already present in this .uasset's name table.");if(prop.array)return infoHelp("Existing array elements are editable. Resizing the array would move later row data and is not yet supported.");return null}
