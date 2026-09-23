"use strict";
  function numberControl(row,field){
    const key=`${state.tab}/${row.id}/${field.key}`;
    const input=el("input",{type:"number",min:field.minimum,max:field.maximum,step:field.step,
      value:state.invalid[key]??row.values[field.key],disabled:readonly(),
      "aria-label":`${field.label} for ${row.name}`,oninput:event=>{
        if(readonly())return;
        const raw=event.target.value,value=Number(raw);
        if(raw===""||!Number.isInteger(value)||!event.target.checkValidity())state.invalid[key]=raw;
        else{delete state.invalid[key];row.values[field.key]=value}
        field.rerenderOnChange?render():shellRefresh();
      }});
    const vanilla=rowById(state.tab,row.id,state.data.vanilla).values[field.key];
    return provenanceControl({control:input,current:()=>row.values[field.key],vanilla,internal:true,
      apply:value=>{if(readonly())return;delete state.invalid[key];row.values[field.key]=Number(value);input.value=String(value);shellRefresh()}});
  }
  function textControl(row,field){
    const input=el("textarea",{rows:field.language?12:3,spellcheck:"false",value:row.values[field.key],disabled:readonly(),
      "aria-label":`${field.label} for ${row.name}`,oninput:event=>{
        if(readonly())return;
        row.values[field.key]=event.target.value;shellRefresh();
      }});
    input.value=String(row.values[field.key]);
    const vanilla=rowById(state.tab,row.id,state.data.vanilla).values[field.key];
    return provenanceControl({control:input,current:()=>row.values[field.key],vanilla,internal:true,
      apply:value=>{if(readonly())return;row.values[field.key]=String(value);input.value=String(value);shellRefresh()}});
  }
  function enumSummary(field,value){
    const choice=(field.choices||[]).find(candidate=>Number(candidate.value)===Number(value));
    if(choice)return choice.label;
    const number=Number(value),hex=Number.isInteger(number)?`0x${number.toString(16).toUpperCase().padStart(2,"0")}`:String(value);
    return `Unknown / modded (${hex})`;
  }
  function enumControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const current=Number(row.values[field.key]),choices=[...(field.choices||[])];
    for(const value of [current,vanilla]){
      if(!choices.some(choice=>Number(choice.value)===value))choices.push({value,label:enumSummary(field,value)});
    }
    const select=el("select",{disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,onchange:event=>{
      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();
    }},...choices.map(choice=>el("option",{value:choice.value},choice.label)));
    select.value=String(current);
    return provenanceControl({control:select,current:()=>row.values[field.key],vanilla,internal:true,format:value=>enumSummary(field,value),
      apply:value=>{if(readonly())return;row.values[field.key]=Number(value);select.value=String(value);shellRefresh()}});
  }
  function flagMask(field){return field.bitWidth?2**Number(field.bitWidth)-1:0xFFFFFFFF}
  function logicalFlags(field,value){const raw=Number(value)>>>0;return field.invertBits?((~raw)>>>0)&flagMask(field):raw}
  function flagsSummary(field,value){
    const number=logicalFlags(field,value),labels=(field.flags||[]).filter(flag=>(number&Number(flag.value))!==0).map(flag=>flag.label);
    const known=(field.flags||[]).reduce((mask,flag)=>mask|Number(flag.value),0)>>>0,unknown=(number&~known)>>>0;
    if(unknown)labels.push(`Unknown bits 0x${unknown.toString(16).toUpperCase()}`);
    return labels.length?labels.join(", "):"None";
  }
  function flagsControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const raw=()=>Number(row.values[field.key])>>>0;
    const logical=()=>logicalFlags(field,raw());
    const group=toggleRow({label:`${field.label} for ${row.name}`,toggles:(field.flags||[]).map(flag=>({
      label:flag.label,checked:(logical()&Number(flag.value))!==0,disabled:readonly(),help:flag.help,change:checked=>{
        if(readonly())return;
        const bit=Number(flag.value),value=raw();
        row.values[field.key]=field.invertBits?(checked?(value&~bit):(value|bit)):(checked?(value|bit):(value&~bit));
        shellRefresh();
      }
    }))});
    group.style.setProperty("--lex-toggle-minimum","132px");group.style.minWidth="0";group.style.maxWidth="100%";group.style.width="100%";
    return provenanceControl({control:group,current:raw,vanilla,internal:true,format:value=>flagsSummary(field,value),
      apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function referenceRows(field,row){
    let rows=[...(state.records[field.referenceCategory]||[])];
    if(field.referenceScope==="scene")rows=rows.filter(candidate=>candidate.scene===row.scene);
    return rows;
  }
  function candidateValue(field,candidate){return Number(candidate[field.referenceValueKey||"id"])}
  function candidateLabel(candidate){return String(candidate.values?.name||candidate.name||`Record ${candidate.id}`)}
  function referenceChoices(field,row){return referenceRows(field,row).map(candidate=>({value:candidateValue(field,candidate),label:candidateLabel(candidate),category:field.referenceCategory,recordId:Number(candidate.id)}))}
  function inventoryChoices(includeMateria=true){
    const specs=[["items",0],["weapons",128],["armor",256],["accessories",288],...(includeMateria?[["materia",320]]:[])];
    return specs.flatMap(([category,offset])=>(state.records[category]||[]).map(record=>({value:offset+Number(record.id),label:`${candidateLabel(record)} — ${labels[category]||category}`,category,recordId:Number(record.id)})));
  }
  function semanticChoiceSummary(choices,value,emptyValue){
    if(emptyValue!==undefined&&Number(value)===Number(emptyValue))return "None";
    const choice=choices.find(candidate=>Number(candidate.value)===Number(value));
    return choice?.label||enumSummary({choices},value);
  }
  function referenceSearchText(choice){
    const value=Number(choice.value),hex=Number.isInteger(value)?`0x${value.toString(16).toUpperCase()}`:"";
    return `${choice.label||""} ${choice.value} #${choice.value} ${hex}`.toLocaleLowerCase();
  }
  function selectControl(row,field,choiceFactory){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const current=Number(row.values[field.key]);
    const choices=choiceFactory();
    if(field.emptyValue!==undefined&&!choices.some(c=>Number(c.value)===Number(field.emptyValue)))choices.unshift({value:Number(field.emptyValue),label:"None"});
    for(const value of [current,vanilla])if(!choices.some(c=>Number(c.value)===value))choices.push({value,label:semanticChoiceSummary(choices,value,field.emptyValue)});
    const select=el("select",{disabled:readonly(),style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} for ${row.name}`,onchange:event=>{
      if(readonly())return;row.values[field.key]=Number(event.target.value);field.rerenderOnChange?render():shellRefresh();
    }});
    const selectedChoice=()=>choices.find(choice=>Number(choice.value)===Number(row.values[field.key]));
    const openButton=el("button",{type:"button",class:"lex-semantic-reference-open",style:"box-sizing:border-box;min-width:30px;width:30px;max-width:30px;align-self:stretch",title:`Open selected ${field.label.toLowerCase()}`,"aria-label":`Open ${field.label} for ${row.name}`,disabled:true,onclick:event=>{
      event.preventDefault();event.stopPropagation();const choice=selectedChoice();if(!choice?.category||choice.recordId===undefined)return;state.selected[choice.category]=Number(choice.recordId);navigate(choice.category);
    }},"↗");
    const rebuild=(query="")=>{
      const needle=String(query).trim().toLocaleLowerCase(),selected=Number(row.values[field.key]);
      let visible=needle?choices.filter(choice=>referenceSearchText(choice).includes(needle)):choices.slice();
      const currentChoice=choices.find(choice=>Number(choice.value)===selected);
      if(currentChoice&&!visible.some(choice=>Number(choice.value)===selected))visible.unshift(currentChoice);
      select.replaceChildren(...visible.map(choice=>el("option",{value:choice.value},choice.label)));
      select.value=String(selected);
      const choice=selectedChoice();openButton.disabled=!(choice?.category&&choice.recordId!==undefined);
    };
    const searchable=choices.length>=12;
    const search=searchable?el("input",{type:"search",class:"lex-semantic-reference-search",style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%",placeholder:`Search ${field.label.toLowerCase()}…`,disabled:readonly(),"aria-label":`Search ${field.label} for ${row.name}`,oninput:event=>rebuild(event.target.value)}):null;
    rebuild();
    if(searchable)openButton.style.gridRow="1 / span 2";
    const root=el("div",{class:`lex-semantic-reference-control${searchable?" searchable":""}`,style:searchable?"display:grid;grid-template-columns:30px minmax(0,1fr);grid-template-rows:auto auto;align-items:stretch;gap:4px 6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box":"display:grid;grid-template-columns:30px minmax(0,1fr);align-items:stretch;gap:6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box"},...(search?[openButton,search,select]:[openButton,select]));
    return provenanceControl({control:root,current:()=>row.values[field.key],vanilla,internal:true,format:value=>semanticChoiceSummary(choices,value,field.emptyValue),apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function referenceControl(row,field){return selectControl(row,field,()=>referenceChoices(field,row))}
  function inventoryReferenceControl(row,field){return selectControl(row,field,()=>inventoryChoices(field.includeMateria!==false))}
  function shopReferenceControl(row,field){return selectControl(row,field,()=>Number(row.values[field.kindField])===1?(state.records.materia||[]).map(record=>({value:Number(record.id),label:candidateLabel(record),category:"materia",recordId:Number(record.id)})):inventoryChoices(false))}
  function booleanControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    const input=el("input",{type:"checkbox",checked:!!Number(row.values[field.key]),disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,onchange:event=>{if(readonly())return;row.values[field.key]=event.target.checked?1:0;shellRefresh()}});
    input.checked=!!Number(row.values[field.key]);
    return provenanceControl({control:input,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:value=>Number(value)?"Enabled":"Disabled",apply:value=>{if(readonly())return;row.values[field.key]=Number(value)?1:0;render()}});
  }
  function scaledControl(row,field){
    const scale=Number(field.displayScale)||1,key=`${state.tab}/${row.id}/${field.key}`,raw=Number(row.values[field.key]);
    const input=el("input",{type:"number",min:Number(field.minimum)*scale,max:Number(field.maximum)*scale,step:scale,value:raw*scale,disabled:readonly(),"aria-label":`${field.label} for ${row.name}`,oninput:event=>{
      if(readonly())return;const shown=Number(event.target.value),value=shown/scale;
      if(event.target.value===""||!Number.isInteger(value)||!event.target.checkValidity())state.invalid[key]=event.target.value;
      else{delete state.invalid[key];row.values[field.key]=value}shellRefresh();
    }});
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]);
    return provenanceControl({control:input,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:value=>String(Number(value)*scale),apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function statusChangeDecoded(value){
    const raw=Number(value);if(raw===0xFF)return{mode:"none",amount:0};if(raw<0x40)return{mode:"inflict",amount:raw};if(raw<0x80)return{mode:"cure",amount:raw-0x40};if(raw<0xC0)return{mode:"swap",amount:raw-0x80};return{mode:"unknown",amount:raw};
  }
  function statusChangeSummary(value){const data=statusChangeDecoded(value);if(data.mode==="none")return"None";if(data.mode==="unknown")return`Unknown / modded (0x${Number(value).toString(16).toUpperCase()})`;return`${data.mode[0].toUpperCase()+data.mode.slice(1)} — ${data.amount}/63`}
  function statusChangeControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]),initial=statusChangeDecoded(row.values[field.key]);
    const modes=[{value:"none",label:"None"},{value:"inflict",label:"Inflict"},{value:"cure",label:"Cure"},{value:"swap",label:"Swap"}];
    if(initial.mode==="unknown")modes.push({value:"unknown",label:statusChangeSummary(row.values[field.key])});
    const mode=el("select",{style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} mode for ${row.name}`,disabled:readonly()},...modes.map(value=>el("option",{value:value.value},value.label)));
    const amount=el("input",{type:"number",min:0,max:63,step:1,style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} chance or amount for ${row.name}`,disabled:readonly()});
    mode.value=initial.mode;amount.value=String(initial.mode==="unknown"?0:initial.amount);amount.disabled=readonly()||["none","unknown"].includes(initial.mode);
    const root=el("div",{class:"lex-semantic-compound",style:"display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.8fr);gap:6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box"},mode,amount);
    const update=()=>{if(readonly())return;const selected=mode.value;if(selected==="unknown")return;const n=Math.max(0,Math.min(63,Number(amount.value)||0));row.values[field.key]=selected==="none"?0xFF:selected==="inflict"?n:selected==="cure"?0x40+n:0x80+n;amount.disabled=readonly()||selected==="none";root.dispatchEvent(new Event("change",{bubbles:true}));shellRefresh()};
    mode.addEventListener("change",update);amount.addEventListener("input",update);
    return provenanceControl({control:root,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:statusChangeSummary,apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function lootRateDecoded(value){const raw=Number(value)&0xFF;return{mode:raw>=0x80?"steal":"drop",amount:raw&0x7F}}
  function lootRateSummary(value){const data=lootRateDecoded(value),percent=Math.round(data.amount*1000/63)/10;return`${data.mode==="steal"?"Steal":"Drop"} — ${data.amount}/63 (${percent}%)`}
  function lootRateControl(row,field){
    const vanilla=Number(rowById(state.tab,row.id,state.data.vanilla).values[field.key]),initial=lootRateDecoded(row.values[field.key]);
    const mode=el("select",{style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} method for ${row.name}`,disabled:readonly()},el("option",{value:"drop"},"Drop"),el("option",{value:"steal"},"Steal"));
    const amount=el("input",{type:"number",min:0,max:127,step:1,style:"box-sizing:border-box;min-width:0;max-width:100%;width:100%","aria-label":`${field.label} chance for ${row.name}`,disabled:readonly(),value:initial.amount});mode.value=initial.mode;
    const root=el("div",{class:"lex-semantic-compound",style:"display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.8fr);gap:6px;min-width:0;max-width:100%;width:100%;box-sizing:border-box"},mode,amount);
    const update=()=>{if(readonly())return;const n=Math.max(0,Math.min(127,Number(amount.value)||0));row.values[field.key]=(mode.value==="steal"?0x80:0)|n;shellRefresh()};
    mode.addEventListener("change",update);amount.addEventListener("input",update);
    return provenanceControl({control:root,current:()=>Number(row.values[field.key]),vanilla,internal:true,format:lootRateSummary,apply:value=>{if(readonly())return;row.values[field.key]=Number(value);render()}});
  }
  function semanticControl(row,field){
    if(field.dataType==="text")return textControl(row,field);
    if(field.dataType==="enum")return enumControl(row,field);
    if(field.dataType==="flags")return flagsControl(row,field);
    if(field.dataType==="reference")return referenceControl(row,field);
    if(field.dataType==="inventoryReference")return inventoryReferenceControl(row,field);
    if(field.dataType==="shopReference")return shopReferenceControl(row,field);
    if(field.dataType==="boolean")return booleanControl(row,field);
    if(field.dataType==="scaled")return scaledControl(row,field);
    if(field.dataType==="statusChange")return statusChangeControl(row,field);
    if(field.dataType==="lootRate")return lootRateControl(row,field);
    return numberControl(row,field);
  }
  function semanticHelp(field){
    if(field.help)return field.help;
    if(field.dataType==="text")return "This is game-visible text. Byte escapes preserve FF7 control codes; unsupported characters or text that cannot fit are refused on save rather than corrupting the kernel.";
    return "";
  }
  function semanticType(field){
    return {text:"TEXT",enum:"SELECT",flags:"FLAGS",reference:"REF",inventoryReference:"REF",shopReference:"REF",boolean:"BOOL",scaled:"VALUE",statusChange:"STATUS",lootRate:"LOOT"}[field.dataType]||"INT";
  }

  function descriptionControl(row){
    const input=el("textarea",{rows:3,spellcheck:"false",value:row.description||"",disabled:readonly(),
      "aria-label":`Description for ${row.name}`,oninput:event=>{
        if(readonly())return;
        row.description=event.target.value;shellRefresh();
      }});
    input.value=String(row.description||"");
    const vanilla=rowById(state.tab,row.id,state.data.vanilla)?.description||"";
    return provenanceControl({control:input,current:()=>row.description,vanilla,internal:true,
      apply:value=>{if(readonly())return;row.description=String(value);input.value=row.description;shellRefresh()}});
  }
