"use strict";
  function lootNumber(parent,key,label,step="1",minimum="0",maximum="100000",note=""){
    return LexeditorUI.detailField({label,help:note?infoHelp(note):null,control:el("input",{type:"number",step,min:minimum,max:maximum,value:String(parent[key]),oninput:event=>{parent[key]=event.target.value.trim()===""?"":Number(event.target.value);state.lootDirty=true;shell.refresh();}})});
  }
  function lootFlag(parent,key,label,note=""){return LexeditorUI.detailField({label,help:note?infoHelp(note):null,control:el("input",{type:"checkbox",checked:!!parent[key],onchange:event=>{parent[key]=event.target.checked;state.lootDirty=true;shell.refresh();},"aria-label":label})});}
  // The corpse loot table itself, read out of the script that holds it. There
  // is no drops XML in this game: the items are constants compiled into
  // lootcorpsegenericnoanim.wsc, and a patched copy of that script is written
  // into the mod folder, where the game already picks up loose overrides by
  // archive path.
  function lootScriptItem(slot){
    const edited=state.lootScriptEdits[slot.index];
    return edited===undefined?slot.item:edited;
  }
  function lootScriptDirty(){return Object.keys(state.lootScriptEdits).length}
  function lootScriptCard(){
    const script=state.lootScript,title="Corpse loot table";
    // The save button is held here rather than re-rendering the section on
    // every keystroke: a full render would rebuild the box being typed into.
    let saveButton=null;
    if(!script)return LexeditorUI.detailSection({title,body:[LexeditorUI.detailNote("Reading the script that holds it…")]});
    if(!script.available)return LexeditorUI.detailSection({title,
      help:infoHelp("The table lives in a compiled script inside content.rpf. Lexeditor reads it through the same RPF6 bridge it uses everywhere else; this is what stopped it."),
      body:[LexeditorUI.notice({tone:"warning",message:script.reason||"The loot script could not be read."})]});
    const fields=script.slots.map(slot=>{
      const input=el("input",{type:"number",min:0,max:slot.maximum,step:1,
        value:String(lootScriptItem(slot)),"aria-label":`Loot branch ${slot.index+1} item`,
        oninput:event=>{
          const value=Number(event.target.value);
          if(value===slot.vanilla)delete state.lootScriptEdits[slot.index];
          else state.lootScriptEdits[slot.index]=value;
          if(saveButton)saveButton.disabled=!lootScriptDirty();
          shell.refresh();
        }});
      return LexeditorUI.detailField({label:`Branch ${slot.index+1}`,
        help:slot.maximum<script.maximum
          ? infoHelp(`This branch is encoded as a short push and can only hold 0 to ${slot.maximum}. A larger item would move every address after it in the script.`)
          : null,
        control:provenanceControl({control:input,current:()=>lootScriptItem(slot),vanilla:slot.vanilla,internal:true,apply:value=>applyControlValue(input,value)})});
    });
    saveButton=el("button",{type:"button",class:"primary",disabled:!lootScriptDirty(),onclick:()=>saveLootScript()},"Write the loot override");
    return LexeditorUI.detailSection({title,
      help:infoHelp("Each branch of the game's LootType switch and the item enum it hands over, read straight out of the script's bytecode. Saving writes a patched copy of the script into the mod folder; the game loads that instead of the archived one, and the original archive is never touched."),
      body:[fact("Script",script.path),fact("Override",script.overrideExists?`Override in place: ${script.override}`:"No override written yet."),
        ...fields,LexeditorUI.actionRow(saveButton)]});
  }
  async function loadLootScript(){
    try{state.lootScript=await api("/api/loot/script")}
    catch(error){state.lootScript={available:false,reason:error.message}}
  }
  async function saveLootScript(){
    const slots=Object.entries(state.lootScriptEdits)
      .map(([index,item])=>({index:Number(index),item:Number(item)}));
    if(!slots.length)return;
    try{
      await api("/api/loot/script/save",{method:"POST",
        headers:{"Content-Type":"application/json"},body:JSON.stringify({slots})});
      state.lootScriptEdits={};
      await loadLootScript();
      LexeditorUI.showToast?.("The loot override was written into the mod folder.");
    }catch(error){LexeditorUI.showToast?.(error.message||String(error),true)}
    renderLoot();
  }

  function renderLoot(){
    $("#toolbar").replaceChildren(el("span",{},"Corpse loot from the installed WSC context"),el("span",{},state.loot?.file||""));
    if(!state.loot?.available||!state.lootDocument){$("#main").replaceChildren(unavailable("Loot ASI override is unavailable",state.loot?.reason||"The project file could not be loaded."));shell.refresh();return;}
    const doc=state.lootDocument,bonus=doc.corpseBonusItem,money=doc.money,base=money.baseRoll;
    const bonusNumber=(entry,field,label)=>el("input",{type:"number",min:"0",max:"100000",step:"1",
      "aria-label":`${label} for item ${entry.itemEnum}`,value:String(entry[field]),
      oninput:event=>{entry[field]=event.target.value.trim()===""?"":Number(event.target.value);state.lootDirty=true;shell.refresh();}});
    const bonusTable=columnList({class:"loot-table","aria-label":"Corpse bonus items",
      rows:bonus.entries,key:entry=>entry.itemEnum,editable:true,localSort:false,
      template:"minmax(90px,1fr) minmax(90px,1fr) minmax(90px,1fr)",
      columns:[{key:"itemEnum",label:"Item enum"},
        {key:"quantity",label:"Quantity",render:entry=>bonusNumber(entry,"quantity","Quantity")},
        {key:"weight",label:"Weight",render:entry=>bonusNumber(entry,"weight","Weight")}]});
    const source=LexeditorUI.detailSection({title:"Corpse bonus item (ASI override)",
      help:infoHelp("Not an RPF replacement: LexerRDR.asi owns this schema-versioned project file, and it accepts only the five item IDs proven in Function_117."),
      body:[lootNumber(bonus,"chancePercent","Bonus roll chance (%)","1","0","100","How often looting a body rolls for a bonus item at all. At 0 no body ever yields one; at 100 every body rolls, and the table below then decides which item comes up."),bonusTable]});
    const moneyCard=LexeditorUI.detailSection({title:"Money paths (ASI override)",body:[LexeditorUI.detailNote(`Function_123: ${money.decoratorPaths.map(path=>`${path.decorator} = ${path.operation}`).join(" · ")}`),lootNumber(base.range,"minimum","Base minimum","0.01",undefined,undefined,"The low end of the money a body carries before any multiplier below is applied. The game picks a value between this and the maximum."),lootNumber(base.range,"maximum","Base maximum","0.01",undefined,undefined,"The high end of that same range. Set it equal to the minimum to give every body the same amount."),lootFlag(base,"applyStatScale","Apply stat scale","Multiply the rolled amount by the game's own difficulty and progression scale, so late-game bodies carry more. Off pays the raw roll everywhere."),lootFlag(base,"applyItem17Multiplier","Apply item 17 multiplier","Honour the multiplier the game attaches to item slot 17, which is how it grants a player bonus to money found. Off ignores that bonus."),lootFlag(base,"applyFinalMultiplier","Apply final multiplier","Apply the last multiplier in the chain, after the other two. This is the one to turn off to see the raw roll.")]});
    const evidence=LexeditorUI.detailSection({title:"Which script this is reading",body:[fact("Archive",doc.source?.archive||"Not supplied"),fact("Script",doc.source?.script||"Not supplied"),LexeditorUI.logView((doc.source?.functions||[]).map(fn=>`${fn.name} @ ${fn.positionHex} / ${fn.positionDecimal}\n${fn.role}`).join("\n\n"))]});
    // Two questions come up on this page every time: where the ordinary
    // per-enemy drop list is edited, and whether enemies carry drop tables of
    // their own somewhere else. Both are answered here rather than left for
    // the reader to conclude from the absence of a table.
    const scope=LexeditorUI.detailSection({title:"What this tab covers",
      help:infoHelp("Searched, not assumed. content.rpf holds the corpse loot logic at content/release64/scripting/gringo/commonscripts/lootcorpsegenericnoanim.wsc, and Lexeditor's RPF6 bridge decompiles it. What a body yields is a switch on a LootType decorator carried by the ped: each branch adds a fixed item enum, written into the script rather than looked up from a table, in Function_90 at bytecode offset 0x36F4. None of the 183 XML files in the archive is a drops table. Editing the script itself is possible and not yet built: the game already loads loose overrides by archive path for non-XML files, so a modified copy of that script would be picked up, and what is missing is writing the item enums back into its bytecode. Until then the two cards below patch the running functions, which is the seam that exists today."),
      body:[LexeditorUI.detailText("Loot here is compiled script, not a data table. A body's items come from a switch on its LootType inside lootcorpsegenericnoanim.wsc in content.rpf, and no XML in the archive holds a drops table. The table below is that switch, read out of the script's bytecode and written back as a loose override; the two cards under it patch the running functions instead, which is how the bonus roll and the money are reached.")]});
    $("#main").replaceChildren(LexeditorUI.settingsColumns([scope,lootScriptCard(),source,moneyCard,evidence]));shell.refresh();
    if(!state.lootScript)loadLootScript().then(()=>renderLoot());
  }
