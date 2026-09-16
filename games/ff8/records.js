  function renderItems(){const rows=filtered("items",["name","id"]),columns=[{key:"id",label:"ID"},{key:"name",label:"Item",render:row=>itemLabel(row)},{key:"buyPrice",label:"Buy",render:row=>gilValue(row.buyPrice)},{key:"sellPrice",label:"Sell",render:row=>gilValue(row.sellPrice)},{key:"sellMultiplier",label:"Sell %",pinned:false,render:row=>unitField(numberValue(row.sellMultiplier*5),"%")},{key:"iconId",label:"Menu icon",pinned:false,render:row=>itemIcon(row)}];showPaged("items",rows,columns,itemDetail,"70px minmax(210px,2fr) 90px 90px")}
  function itemDetail(row,prefs){const vanilla=rowOf(state.vanilla,"items",row.id),sell=readonlyField(row.sellPrice);const updateSell=()=>{row.sellPrice=Math.round((row.buyPrice/20)*row.sellMultiplier);sell.value=formatNumber(row.sellPrice);shell.refresh()},setSellMultiplier=value=>{row.sellMultiplier=Math.max(0,Math.min(255,Math.round(Number(value)||0)));updateSell()},buy=sourceControl(unitField(numberControl(row.buyPrice,0,655350,10,value=>{row.buyPrice=value;updateSell()}),"G",{unitClass:"ff8-gil-unit"}),()=>row.buyPrice,vanilla.buyPrice,referenceValues("items",row.id,value=>value?.buyPrice),value=>{row.buyPrice=value;updateSell()},value=>`${formatNumber(value)} G`,{internal:true}),sellRate=sourceControl(unitField(numberControl(row.sellMultiplier*5,0,1275,5,value=>setSellMultiplier(value/5)),"%"),()=>row.sellMultiplier,vanilla.sellMultiplier,referenceValues("items",row.id,value=>value?.sellMultiplier),setSellMultiplier,value=>`${formatNumber(Number(value)*5)}%`,{internal:true});return sharedDetail(row,prefs,[detailSection({className:"item-price-section",title:"PRICES",body:[
    detailField({className:"ff8-price-equation-row",label:"BUY PRICE",help:infoHelp("Sell price is derived from this item's buy price and sell percentage; changing either changes the gil returned when the item is sold to a shop."),control:el("div",{class:"ff8-price-equation"},el("span",{class:"ff8-equation-term lex-pinnable-property"},buy,prefs?.pinButton("buyPrice","Buy price")),el("span",{class:"ff8-equation-symbol"},"×"),el("span",{class:"ff8-equation-term lex-pinnable-property"},sellRate,prefs?.pinButton("sellMultiplier","Sell percentage")),el("span",{class:"ff8-equation-symbol"},"="),el("span",{class:"ff8-equation-term lex-pinnable-property"},unitField(sell,"G",{unitClass:"ff8-gil-unit"}),prefs?.pinButton("sellPrice","Sell price")),el("span",{},"SELL PRICE"))})]}),
    menuItemSection(row.id),
    row.id<33?el("p",{class:"readonly-note"},"This item also has battle behavior in kernel.bin. Those fields are not editable here until cross-file saving is validated."):null],"","",itemIcon(row))}

  function renderShops(){const rows=filtered("shops",["name","id"]);showPaged("shops",rows,[{key:"id",label:"ID"},{key:"name",label:"Shop"}],shopDetail,"74px minmax(260px,1fr)")}
  function removeShopSlot(row,slot){slot.itemId=0;slot.itemName=state.data.shops.items.find(item=>item.id===0)?.name||"Nothing";slot.rare=false;renderShops();shell.refresh()}
  function shopDetail(row,prefs){
    const vanilla=rowOf(state.vanilla,"shops",row.id),entries=[...state.data.shops.items].sort((a,b)=>a.id===0?-1:b.id===0?1:a.name.localeCompare(b.name));
    const controls=new Map(row.slots.map(slot=>{
      const vanillaSlot=vanilla.slots[slot.slot],refs=referenceValues("shops",row.id,value=>value?.slots?.[slot.slot]);
      const setItem=value=>{slot.itemId=Number(value);slot.itemName=state.data.shops.items.find(item=>item.id===Number(value))?.name||`Item ${value}`;renderShops();shell.refresh()},origin=()=>{state.selected.shops=row.id;navigate("shops")};
      const item=sourceControl(itemSearchControl(slot.itemId,`Select the Item for ${row.name}.`,setItem,origin),()=>slot.itemId,vanillaSlot.itemId,refs.map(entry=>({...entry,value:entry.value?.itemId})),setItem,value=>{const target=itemById(value)||state.data.shops.items.find(entry=>Number(entry.id)===Number(value))||{id:value,name:`Item ${value}`};return itemDisplay(target)});
      const rare=sourceControl(el("input",{type:"checkbox",checked:slot.rare,"aria-label":`Rare stock: ${slot.itemName}`,onchange:event=>{slot.rare=event.target.checked;shell.refresh()}}),()=>slot.rare,vanillaSlot.rare,refs.map(entry=>({...entry,value:entry.value?.rare})),value=>slot.rare=value,booleanMark);
      return [slot.slot,{item,rare,slotControl:el("button",{type:"button",class:"shop-slot-clear",title:`Set slot ${slot.slot+1} to Nothing`,"aria-label":`Clear slot ${slot.slot+1}`,onclick:()=>removeShopSlot(row,slot)},el("span",{class:"shop-slot-number"},String(slot.slot+1)))}];
    }));
    state.shopSlotSort||=["slot",1];const [sortKey,sortDir]=state.shopSlotSort,sorted=[...row.slots].sort((a,b)=>sortDir*String(sortKey==="item"?a.itemName:a[sortKey]??"").localeCompare(String(sortKey==="item"?b.itemName:b[sortKey]??""),undefined,{numeric:true}));
    const table=columnList({rows:sorted,key:slot=>slot.slot,class:"ff8-shop-table ff8-record-list",template:"54px minmax(150px,1fr) 110px",sortState:{key:sortKey,dir:sortDir},sort:key=>{state.shopSlotSort=[key,sortKey===key?-sortDir:1];renderShops()},columns:[{key:"slot",label:"Slot",sortable:true,render:slot=>controls.get(slot.slot).slotControl},{key:"item",label:"Item",sortable:true,render:slot=>controls.get(slot.slot).item},{key:"rare",label:el("span",{},"Rare",infoHelp("Rare stock is hidden until the player has Tonberry's Familiar menu ability.")),sortable:true,cellClass:"rare",render:slot=>controls.get(slot.slot).rare}]});
    return sharedDetail(row,prefs,table,"shop-detail");
  }

  function displayFieldValue(field){if(!field)return "";if(field.lookup?.type==="enum")return field.lookup.entries.find(entry=>Number(entry.value??entry.id)===Number(field.value))?.name??field.value;if(field.control==="boolean")return field.value?"✓":"×";return field.value}
  function weaponColumns(){const base=[{key:"id",label:"ID",width:"58px"},{key:"name",label:"Weapon"},{key:"upgradePrice",label:"Price",numeric:true,sortValue:row=>row.upgradePrice,render:row=>gilValue(row.upgradePrice)}],sample=state.data.weapons.rows[0];return base.concat((sample?.fields||[]).map(field=>({key:`field:${field.field}`,label:field.label,pinned:false,numeric:field.control!=="boolean"&&field.lookup?.type!=="enum",sortValue:row=>row.fields.find(value=>value.field===field.field)?.value??"",render:row=>displayFieldValue(row.fields.find(value=>value.field===field.field))})))}
  function renderWeapons(){const rows=filtered("weapons",["name","id"]);showPaged("weapons",rows,weaponColumns(),weaponDetail,"70px minmax(220px,2fr) 120px")}
  function weaponDataField(label,control,help="",prefs=null,key=""){return detailField({className:"weapon-data-field",label,help:help?infoHelp(help):null,control,pin:prefs?.pinButton(key,label)})}
  function weaponDetail(row,prefs){
    const vanilla=rowOf(state.vanilla,"weapons",row.id);
    const price=sourceControl(unitField(numberControl(row.upgradePrice,0,2550,10,value=>row.upgradePrice=value),"G",{unitClass:"ff8-gil-unit"}),()=>row.upgradePrice,vanilla.upgradePrice,referenceValues("weapons",row.id,value=>value?.upgradePrice),value=>row.upgradePrice=value,value=>`${formatNumber(value)} G`,{internal:true});
    const dataFields=row.fields.map(field=>weaponDataField(field.label,fieldSourceControl(field,"weapons",row.id,{internal:true}),field.help,prefs,`field:${field.field}`));
    const ingredients=row.ingredients.map(ingredient=>{const vanillaIngredient=vanilla.ingredients[ingredient.slot],refs=referenceValues("weapons",row.id,value=>value?.ingredients?.[ingredient.slot]),setItem=value=>{const itemId=Number(value);ingredient.itemId=itemId;ingredient.quantity=itemId===0?0:Math.max(1,Number(ingredient.quantity)||1);renderWeapons();shell.refresh()},origin=()=>{state.selected.weapons=row.id;navigate("weapons")},item=sourceControl(itemSearchControl(ingredient.itemId,`Select the Item for ${row.name}.`,setItem,origin),()=>ingredient.itemId,vanillaIngredient.itemId,refs.map(entry=>({...entry,value:entry.value?.itemId})),setItem,value=>state.data.weapons.items.find(item=>item.id===value)?.name||`Item ${value}`,{internal:true}),quantity=ingredient.itemId===0?null:sourceControl(numberControl(ingredient.quantity,1,255,1,value=>ingredient.quantity=value,{"aria-label":`Quantity for ingredient ${ingredient.slot+1}`}),()=>ingredient.quantity,vanillaIngredient.quantity,refs.map(entry=>({...entry,value:entry.value?.quantity})),value=>ingredient.quantity=value,undefined,{internal:true});return detailField({className:"weapon-ingredient-row",label:`ITEM ${ingredient.slot+1}`,control:el("div",{class:"weapon-ingredient-control"},item,quantity)})});
    return sharedDetail(row,prefs,[detailSection({className:"weapon-section weapon-data",title:"DATA",body:dataFields}),detailSection({className:"weapon-section weapon-cost",title:"COST",body:[detailField({className:"weapon-cost-price",label:"PRICE",control:price,pin:prefs?.pinButton("upgradePrice","Price")}),...ingredients]})],"weapon-detail")
  }

  function magicIcons(row){
    const icons=[],seen=new Set(),fields=row.fields||[],append=(kind,field)=>{if(!field?.value||field.lookup?.type!=="flags")return;for(const entry of field.lookup.entries){const mask=Number(entry.mask??entry.value),id=kind==="element"?elementIcons[entry.name]:statusIcons[entry.name];if(!id||seen.has(id)||(Number(field.value)&mask)!==mask)continue;seen.add(id);icons.push(conceptIcon(kind,entry.name))}};
    // Only the attack's Element field describes its menu element. Junction
    // element fields are separate data and previously repeated the same icon.
    append("element",fields.find(field=>field.field==="element"));
    const statusFields=fields.filter(field=>field.field==="status_1"||field.field==="status_2"),statusCount=statusFields.reduce((sum,field)=>sum+(field.lookup?.entries||[]).filter(entry=>(Number(field.value)&Number(entry.mask??entry.value))===Number(entry.mask??entry.value)).length,0);
    // A small status set identifies an inflicted/support effect. Large sets
    // such as Esuna describe all statuses affected, not icons to show on its
    // name, so do not turn them into a wall of unrelated symbols.
    if(statusCount<=3)statusFields.forEach(field=>append("status",field));
    return icons.slice(0,3)
  }
  function magicLabel(row){return el("span",{class:"ff8-magic-label"},...magicIcons(row),el("span",{},row.name))}
  function compactMagicFields(fields,view,rowId,className="",columns=fields.length){return el("div",{class:`ff8-inline-field-grid ${className}`.trim(),style:`--ff8-inline-columns:${Math.max(1,columns)}`},...fields.filter(Boolean).map(field=>el("label",{class:"ff8-inline-field"},el("span",{class:"ff8-inline-field-label"},el("span",{class:"ff8-inline-field-label-text"},field.label)),fieldSourceControl(field,view,rowId))))}
  // The type shown beside a composite half comes from the kernel schema, not
  // from a placeholder: a half labelled VALUE used to be typed "VAL", which
  // told the reader nothing.
  function kernelTypeCode(field){
    if(!field)return "";
    if(field.lookup?.type==="flags")return "FLG";
    if(field.lookup)return "ENUM";
    if(field.control==="boolean")return "BOOL";
    return "INT";
  }
  function magicComposite(valueField,flagsField,rowId,className=""){// Each half of a composite carries its own type rail and help marker, so
  // a grouped row is still self-describing per variable.
  const half=(field,label)=>el("label",{class:"magic-composite-value"},el("span",{class:"lex-toggle-rail"},el("span",{class:"lex-toggle-type"},kernelTypeCode(field)),field.help?infoHelp(field.help):null),el("span",{class:"magic-composite-value-label"},label),fieldSourceControl(field,"magic",rowId));return el("div",{class:`magic-composite ${className}`.trim()},valueField?half(valueField,className.includes("attack-flags")?"TYPE":"VALUE"):null,flagsField?fieldSourceControl(flagsField,"magic",rowId):null)}
  function magicCompatibility(fields,rowId){return el("div",{class:"magic-compatibility-grid"},...fields.map(field=>{const gf=gfByName(field.label);return el("label",{class:"magic-compatibility-entry",title:field.label},gf?el("img",{src:`/assets/portraits/gfs/${gf.id}.png`,alt:field.label}):el("span",{class:"ff8-portrait-fallback"},"?"),fieldSourceControl(field,"magic",rowId))}))}
  function magicLeadingPanel(row){return el("section",{class:"magic-compat-column"},compatibilityPanel(row.fields.filter(field=>field.group==="GF Compatibility"),"magic",row.id))}
  function magicDetail(row,prefs){
    const fields=new Map(row.fields.map(field=>[field.field,field])),used=new Set(),take=name=>{const field=fields.get(name);if(field)used.add(name);return field},many=names=>names.map(take).filter(Boolean);
    const status1=take("status_1"),status2=take("status_2");
    const generalRows=[
      detailField({label:"STATUS WINDOW",control:fieldSourceControl(take("status_window_flags"),"magic",row.id)}),
      detailField({label:"TARGET INFO",control:fieldSourceControl(take("target_info"),"magic",row.id)}),
      detailField({label:"ATTACK FLAGS",control:magicComposite(take("attack_flags_type"),take("attack_flags"),row.id,"magic-attack-flags")}),
      detailField({label:"ELEMENT",control:fieldSourceControl(take("element"),"magic",row.id)}),
      detailField({label:"STATUS 1",help:status1?.help?infoHelp(status1.help):null,control:fieldSourceControl(status1,"magic",row.id)}),
      detailField({label:"STATUS 2",help:status2?.help?infoHelp(status2.help):null,control:fieldSourceControl(status2,"magic",row.id)}),
      detailField({label:"STATUS ACCURACY",control:fieldSourceControl(take("status_accuracy"),"magic",row.id)}),
    ];
    if(state.data.settings.gfHpCasting)generalRows.unshift(detailField({label:"GF HP COST",help:infoHelp("GF HP spent when this spell is confirmed through the battle Magic command. Requires a junctioned GF, Monogamy and No Magic Consumption."),control:el("input",{type:"number",min:0,max:9999,step:1,value:state.data.settings.gfHpCastingCosts[row.id],"aria-label":`GF HP cost for ${row.name}`,oninput:event=>{if(event.target.validity.valid){state.data.settings.gfHpCastingCosts[row.id]=Number(event.target.value);shell.refresh()}}})}));
    const generalRemainder=row.fields.filter(field=>field.group==="General"&&!used.has(field.field));
    generalRemainder.forEach(field=>used.add(field.field));
    if(generalRemainder.length)generalRows.unshift(detailField({label:"ATTACK DATA",control:compactMagicFields(generalRemainder,"magic",row.id,"",Math.min(6,generalRemainder.length))}));
    const junctionRows=[
      detailField({label:"JUNCTION (STATS)",control:multiNumberRow(many(["j_hp","j_str","j_vit","j_mag","j_spr","j_spd","j_eva","j_hit","j_luck"]).map(field=>({label:field.label.replace(/^J-/,""),title:field.label,control:fieldSourceControl(field,"magic",row.id)})),{columns:3,className:"magic-junction-stats"})}),
      detailField({label:"J-ELEMENT (ATTACK)",control:magicComposite(take("j_elem_attack_value"),take("j_elem_attack"),row.id)}),
      detailField({label:"J-ELEMENT (DEFENSE)",control:magicComposite(take("j_elem_defense_value"),take("j_elem_defense"),row.id)}),
      detailField({label:"J-STATUS (ATTACK)",control:magicComposite(take("j_status_attack_value"),take("j_status_attack"),row.id)}),
      detailField({label:"J-STATUS (DEFENSE)",control:magicComposite(take("j_status_defense_value"),take("j_status_defend"),row.id)}),
    ];
    const compat=row.fields.filter(field=>field.group==="GF Compatibility");compat.forEach(field=>used.add(field.field));
    const body=tabbedPanel({className:"magic-detail-tabs",tabs:[{id:"attack",label:"Attack Data",help:"Change what this spell does when cast: damage, targets, elements, and status effects."},{id:"junction",label:"Junction",help:"Change the stat bonuses and attack or defence effects granted when this spell is junctioned."}],active:state.magicDetailTab||"attack",label:"Magic details",change:value=>{state.magicDetailTab=value;renderKernel("magic","Magic")},content:state.magicDetailTab==="junction"?junctionRows:generalRows});
    const detail=sharedDetail({...row,titleContent:magicLabel(row)},prefs,body,"magic-detail");
    return detail;
  }
  function abilityIcon(row){const icon=itemIcon(row);icon.classList.add("ff8-ability-icon");icon.dataset.abilityType=row?.abilityType||"Unknown";icon.title=row?.abilityType||"Unknown ability type";if(row?.iconId==null)icon.append(el("span",{},"?"));return icon}
  function abilityLabel(row){return el("span",{class:"ff8-item-display ff8-ability-label"},abilityIcon(row),el("span",{},row.name))}
  function recordHoverLabel(view,row,content){return hoverable({class:"ff8-record-hover-label",content,targetType:view,targetId:row.id,targetLabel:row.name,activate:()=>{state.selected[view]=row.id;navigate(view)}})}
  // FF8 keeps its ability definitions in one kernel section per category,
  // each record carrying its AP-to-learn cost. They are ordinary kernel
  // sections, so each category renders through the shared kernel view.
  const abilityCategories=[["abilityJunction","Junction"],["abilityCommand","Command"],["abilityStat","Stat Boost"],["abilityCharacter","Character"],["abilityParty","Party"],["abilityGf","GF"],["abilityMenu","Menu"]];
  state.abilityTab=state.abilityTab||abilityCategories[0][0];
  function renderAbilities(){
    const active=abilityCategories.some(([key])=>key===state.abilityTab)
      ? state.abilityTab : abilityCategories[0][0];
    const label=abilityCategories.find(([key])=>key===active)[1];
    renderKernel(active,`${label} abilities`);
    // The category bar belongs in the toolbar, as Starting Data does it;
    // putting it inside #main breaks the list/detail grid.
    const toolbar=$("#toolbar");
    toolbar.hidden=false;
    toolbar.replaceChildren(subtabBar({
      tabs:abilityCategories.map(([id,name])=>({id,label:name})),
      active,
      label:"Ability category",
      change:value=>{state.abilityTab=value;renderAbilities()},
    }));
  }
  function renderKernel(view,label){const rows=filtered(view,["name","id"]),sample=state.data[view].rows[0],columns=[{key:"id",label:"ID"},{key:"name",label,render:row=>recordHoverLabel(view,row,view==="magic"?magicLabel(row):row.abilityType?abilityLabel(row):row.name)},...(sample?.fields||[]).map(field=>({key:`field:${field.field}`,label:field.label,pinned:false,numeric:field.control!=="boolean"&&field.lookup?.type!=="enum",sortValue:row=>row.fields.find(value=>value.field===field.field)?.value??"",render:row=>displayFieldValue(row.fields.find(value=>value.field===field.field))}))];showPaged(view,rows,columns,view==="magic"?magicDetail:(row,prefs)=>sharedDetail(row.abilityType?{...row,titleContent:abilityLabel(row)}:row,prefs,fieldGroups(row.fields,view,row.id,false,prefs)),"74px minmax(180px,1fr)",view==="magic"?{leadingPanel:magicLeadingPanel,minLeading:260,defaultLeadingWidth:20,minLeft:260,minRight:430}:{})}
  function matchingTextRow(dataset,row){return dataset?.text?.rows?.find(value=>value.source===row.source&&value.sectionId===row.sectionId&&value.recordId===row.recordId&&value.slot===row.slot)}
  function textDetail(row,prefs){
    const input=el("textarea",{rows:8,"aria-label":`Text for ${row.name}`,oninput:event=>{row.value=event.target.value;shell.refresh()}});input.value=row.value;
    const references=state.references.map(reference=>{const value=matchingTextRow(state.referenceData[reference.id],row);return value?{name:reference.name,shortName:reference.shortName,value:value.value}:null}).filter(Boolean);
    const control=sourceControl(input,()=>row.value,matchingTextRow(state.vanilla,row)?.value,references,value=>row.value=String(value??""),undefined,{internal:true});
    const boundaries={
      mngrp:"Menu text stays inside its original fixed-size mngrp.bin section. An edit that does not fit is rejected; all other menu data remains unchanged.",
      kernel:"Kernel text rebuilds its linked offsets and section table while preserving unrelated kernel data.",
      exe_card_names:"Card names are saved as ff8/en/exe/card_names.msd in this mod. FFNx replaces the game's card-name lookup at runtime; Lexeditor never changes FF8_EN.exe.",
      exe_draw_point:"Draw-point text is saved as ff8/en/exe/draw_point.msd in this mod. FFNx replaces the game's message pointer at runtime; Lexeditor never changes FF8_EN.exe.",
      exe_card_texts:"Card text is saved as ff8/en/exe/card_texts.msd in this mod. FFNx replaces the two card-text pointers at runtime; Lexeditor never changes FF8_EN.exe.",
    };
    const boundary=boundaries[row.source]||"This text source is not writable.";
    const roleSuffix=` ${row.role}`,title=row.name.endsWith(roleSuffix)?row.name.slice(0,-roleSuffix.length):row.name;
    return sharedDetail({...row,id:row.recordId,name:title},prefs,detailSection({className:"kernel-text-editor",title:"TEXT",body:detailField({className:"lex-detail-field-stacked",label:row.role,help:infoHelp(`FF8 text supports game tokens such as {Squall} and {L2}. Unsupported characters are rejected when you save. ${boundary}`),control})}),"",row.role);
  }
  function renderText(){const rows=filtered("text",["sourceLabel","section","recordId","role","value"]),columns=[{key:"sourceLabel",label:"Source",width:"95px"},{key:"sectionId",label:"Section",numeric:true,width:"70px"},{key:"recordId",label:"Record",numeric:true,width:"70px"},{key:"role",label:"Field",width:"minmax(106px,.55fr)"},{key:"value",label:"Text",grow:1}];showPaged("text",rows,columns,textDetail,"95px 70px 70px minmax(106px,.55fr) minmax(160px,1fr)")}
  const characterCurveOrder=["HP","STR","VIT","MAG","SPR","SPD","LUCK"];
  const characterCurveKind={HP:"hp",STR:"standard",VIT:"standard",MAG:"standard",SPR:"standard",SPD:"linear",LUCK:"linear"};
  function integerDivision(numerator,denominator){return denominator?Math.trunc(numerator/denominator):Number.NaN}
  function characterCurveValue(stat,fields,level,raw=false){
    const coefficients=[1,2,3,4].map(index=>Number(fields.find(field=>field.field===`${stat.toLocaleLowerCase()}_${index}`)?.value??0));
    const [A,B,C,D]=coefficients,kind=characterCurveKind[stat];
    if(kind==="hp")return level*A-integerDivision(10*level*level,B)+C;
    if(kind==="standard"){if(A===0&&B===1&&C===0&&D===1)return 0;const base=integerDivision(integerDivision(level*A,10)+integerDivision(level,B)-integerDivision(level*level,2*D)+C,4);return raw?base:Math.min(255,Math.max(0,base))}
    const base=level*A+integerDivision(level,B)-integerDivision(level,D)+C;return raw?base:Math.min(255,base);
  }
  function characterCurveRange(stat,fields){
    const values=Array.from({length:100},(_,i)=>characterCurveValue(stat,fields,i+1,true)).filter(Number.isFinite);
    return {min:Math.min(0,...values),max:Math.max(stat==="HP"?9999:255,...values)};
  }
  function characterCurveFormula(stat){
    if(stat==="HP")return "HP(L)=L*A-trunc(10*L*L/B)+C";
    if(["STR","VIT","MAG","SPR"].includes(stat))return `${stat}(L)=trunc((trunc(L*A/10)+trunc(L/B)-trunc(L*L/(2*D))+C)/4); 0 if A=C=0, B=D=1`;
    return `${stat}(L)=L*A+trunc(L/B)-trunc(L/D)+C`;
  }
  // Formulas are set as mathematics rather than as source. A variable stays a
  // coloured letter, but the operators become the symbols a reader expects: a
  // multiplication dot instead of an asterisk, a division slash with air around
  // it. Keep truncation explicit: negative values truncate toward zero.
  function mathText(part){
    return String(part)
      .replace(/\s*\*\s*/g, "\u00b7")
      .replace(/\s*\/\s*/g, " \u2215 ")
      .replace(/=/g, " = ")
      .replace(/\s{2,}/g, " ");
  }
  function coloredCurveFormula(text){const fragment=document.createDocumentFragment();String(text).split(/\b([ABCD])\b/g).forEach(part=>fragment.append(/^[ABCD]$/.test(part)?el("span",{class:`lex-curve-variable-${part.toLocaleLowerCase()}`},part):mathText(part)));return fragment}
  function characterXpValue(fields,level){
    const A=Number(fields.find(field=>field.field==="exp_linear")?.value??0),B=Number(fields.find(field=>field.field==="exp_quadratic")?.value??0),progress=Math.max(0,level-1);
    return 10*progress*A+Math.floor(progress*progress*B/256);
  }
  // One scale for every character's experience curve, so a cheap character
  // reads as cheap. A hundred thousand covers the vanilla curves with room
  // above them; a curve that goes further takes the axis it needs.
  function characterXpRange(fields){
    return {min:0,max:Math.max(100000,Math.ceil(characterXpValue(fields,100)/10000)*10000)};
  }
  function characterStatGrowth(fields,rowId,expFields=[]){
    const cards=characterCurveOrder.map(stat=>{
      const statFields=fields.filter(field=>field.subgroup===stat).sort((left,right)=>left.field.localeCompare(right.field,undefined,{numeric:true}));
      const variables=statFields.filter(field=>!field.readonly).map((field,index)=>({label:"ABCD"[index],control:fieldSourceControl(field,"characters",rowId,{internal:true})}));
      // Show the signed formula result. Recompute the range after every edit.
      return curveEditor({title:stat,className:"ff8-character-curve",overlayExtrema:true,variables,domain:{min:1,max:100},range:()=>characterCurveRange(stat,statFields),graphLabel:`${stat} raw base from level 1 to level 100, before limits, junctions and bonuses. Negative values are shown.`,evaluate:level=>characterCurveValue(stat,statFields,level,true),formula:coloredCurveFormula(characterCurveFormula(stat)),invalidText:"A DIVISOR IS 0"});
    });
    if(expFields.length)cards.push(curveEditor({title:"XP",className:"ff8-character-curve",overlayExtrema:true,variables:expFields.map((field,index)=>({label:"AB"[index],control:fieldSourceControl(field,"characters",rowId,{internal:true})})),domain:{min:1,max:100},range:()=>characterXpRange(expFields),graphLabel:"Cumulative experience required from level 1 to level 100",evaluate:level=>characterXpValue(expFields,level),formula:coloredCurveFormula("XP(L) = 10 * (L - 1) * A + floor((L - 1)^2 * B / 256)")}));
    return detailSection({className:"character-stat-growth",title:"STAT GROWTH",help:infoHelp("Each card shows the signed formula result before limits, junctions and bonuses, including negative values. For STR, VIT, MAG and SPR, A=0, B=1, C=0, D=1 selects exact zero growth in the runtime. Other negative bases are floored at zero in the game."),body:el("div",{class:"character-curve-grid"},...cards)});
  }
  // GF HP and next-level EXP, from the two routines that compute them:
  // getGFhpForLvl at 0x496120 reads the three HP modifiers out of the GF record
  // and returns HPMod3 + level*HPMod1 + 10*level^2/HPMod2, and
  // GetGFLevelFromExperience at 0x4960c0 walks levels while experience is at
  // least 10*mod1*L + mod2*L^2/256. Both were read out of FF8_EN.exe rather
  // than inferred from the shape of the data.
  const gfCurveValue=(kind,fields,level)=>{
    const at=name=>Number(fields.find(field=>field.field===name)?.value)||0;
    if(kind==="HP"){
      const divisor=at("gf_hp_modifier_2");
      if(!divisor)return null;
      return at("gf_hp_modifier_3")+level*at("gf_hp_modifier_1")+Math.floor(10*level*level/divisor);
    }
    return 10*at("gf_level_modifier_1")*level+Math.floor(at("gf_level_modifier_2")*level*level/256);
  };
  function gfStatGrowth(fields,rowId){
    const pick=names=>names.map(name=>fields.find(field=>field.field===name)).filter(Boolean);
    const hpFields=pick(["gf_hp_modifier_1","gf_hp_modifier_2","gf_hp_modifier_3"]);
    const expFields=pick(["gf_level_modifier_1","gf_level_modifier_2"]);
    const cards=[];
    const axis=kind=>{
      const peak=Math.max(...Array.from({length:100},(_,index)=>Number(gfCurveValue(kind,fields,index+1))||0));
      return{min:0,max:Math.max(1,Math.ceil(peak*1.08/5)*5)};
    };
    if(hpFields.length===3)cards.push(curveEditor({title:"HP",className:"ff8-character-curve gf-level-curve",overlayExtrema:true,
      variables:hpFields.map((field,index)=>({label:"ABC"[index],control:fieldSourceControl(field,"gfs",rowId,{internal:true})})),
      domain:{min:1,max:100},range:()=>axis("HP"),
      graphLabel:"GF HP from level 1 to level 100",
      evaluate:level=>gfCurveValue("HP",fields,level),
      formula:coloredCurveFormula("HP(L) = C + L * A + floor(10 * L^2 / B)"),
      invalidText:"A DIVISOR IS 0"}));
    if(expFields.length===2)cards.push(curveEditor({title:"XP",className:"ff8-character-curve gf-level-curve",overlayExtrema:true,
      variables:expFields.map((field,index)=>({label:"AB"[index],control:fieldSourceControl(field,"gfs",rowId,{internal:true})})),
      domain:{min:1,max:100},range:()=>axis("XP"),
      graphLabel:"Cumulative experience required from level 1 to level 100",
      evaluate:level=>gfCurveValue("XP",fields,level),
      formula:coloredCurveFormula("XP(L) = 10 * L * A + floor(L^2 * B / 256)")}));
    if(!cards.length)return null;
    return detailSection({className:"gf-stat-growth",title:"LEVEL CURVES",
      help:infoHelp("The HP curve controls this GF's maximum HP as it levels; the XP curve controls the cumulative experience thresholds for GF levels. Both use FF8's verified game routines."),
      body:el("div",{class:"character-curve-grid"},...cards)});
  }
  function characterDetail(row){
    const visible=row.fields.filter(field=>field.field!=="gender"&&field.name!=="gender"&&field.label!=="Gender"),growth=visible.filter(field=>field.group==="Stat coefficients"),exp=visible.filter(field=>["exp_linear","exp_quadratic"].includes(field.field)),other=visible.filter(field=>field.group!=="Stat coefficients"&&!exp.includes(field));
    const limitBreak=detailSection({className:"character-limit-break",title:"LIMIT BREAK",body:el("div",{class:"character-limit-break-row"},...other.map(field=>detailField({className:"character-limit-break-field",label:field.label,help:field.help?infoHelp(field.help):null,control:fieldSourceControl(field,"characters",row.id)})))});
    return [limitBreak,characterStatGrowth(growth,row.id,exp)];
  }
  function genderIcon(value,small=false){const female=Number(value)===1;return el("span",{class:`ff8-gender-symbol ${female?"female":"male"}${small?" small":""}`,title:female?"Female":"Male","aria-label":female?"Female":"Male"},female?"♀":"♂")}
  function portraitTabs(view,rows,selected,detailId,select){const ordered=[...rows].sort((a,b)=>a.name.localeCompare(b.name,undefined,{sensitivity:"base"})),active=ordered.find(row=>row.id===selected);const tabs=el("div",{class:"ff8-portrait-tabs",role:"tablist","aria-label":view==="gfs"?"Guardian Forces":"Characters",style:`--portrait-count:${ordered.length}`},...ordered.map(row=>{const button=el("button",{id:`${view}-tab-${row.id}`,type:"button",role:"tab","aria-controls":detailId,"aria-selected":String(row.id===selected),"aria-label":row.name,title:row.name,class:`ff8-portrait-tab${row.id===selected?" active":""}`,onclick:()=>select(row.id)},el("img",{src:`/assets/portraits/${view}/${row.id}.png`,alt:"",onerror:()=>button.classList.add("missing-portrait")}),el("span",{class:"ff8-portrait-fallback","aria-hidden":"true"},"?"));return button}));const name=el("strong",{class:"ff8-portrait-selected-name"},active?.name||"");if(view==="characters"&&active){const isGender=field=>field.field==="gender"||field.name==="gender"||field.label==="Gender",gender=active.fields.find(isGender),vanilla=rowOf(state.vanilla,"characters",active.id)?.fields?.find(isGender),refs=referenceValues("characters",active.id,value=>value?.fields?.find(isGender)?.value);if(gender){const button=el("button",{type:"button",class:`ff8-gender ${Number(gender.value)===1?"female":"male"}`,title:`${Number(gender.value)===1?"Female":"Male"}. Click to change.`,"aria-label":`Gender: ${Number(gender.value)===1?"Female":"Male"}. Click to change.`,onclick:()=>{gender.value=Number(gender.value)===1?0:1;renderCharacters();shell.refresh()}},genderIcon(gender.value));name.append(sourceControl(button,()=>gender.value,vanilla?.value,refs,value=>{gender.value=value},value=>genderIcon(value,true)))}}return el("div",{class:"ff8-portrait-selector"},name,tabs,recordId(active?.id,{class:"ff8-portrait-selected-id"}))}
