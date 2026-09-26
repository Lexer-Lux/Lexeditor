  // SFX, Models, and Textures tabs. Record identity stays in the master
  // list; previews, facts, and file replacement stay in the detail pane.
  // Staged uploads ride on the row (audioBase64/datBase64) so dirty
  // tracking, history, and Save treat them like any other edit.
  const assetPalettes={};
  function assetDataset(){return state.activeSource==="mine"?"current":state.activeSource}
  function assetFileSize(size){return size==null?"—":size<1024?`${size} B`:size<1048576?`${formatNumber(size/1024,{maximumFractionDigits:1})} KB`:`${formatNumber(size/1048576,{maximumFractionDigits:1})} MB`}
  function assetDuration(ms){return ms==null?"—":`${formatNumber(ms/1000,{maximumFractionDigits:ms<10000?2:0})} s`}
  function assetStageUpload(row,key,input,accept,pick){
    const file=input.files?.[0];if(!file)return;
    const picked=pick(file);
    if(picked===null){input.value="";return}
    const reader=new FileReader();
    reader.onload=()=>{row[key]=String(reader.result).split(",",2)[1]||"";Object.assign(row,picked);shell.refresh();render()};
    reader.onerror=()=>showAlert({title:"Could not read file",message:`${file.name} could not be read.`});
    reader.readAsDataURL(file);input.value="";
  }
  function assetPendingNote(row,key,label){
    return el("div",{class:"world-texture-pending"},row[key]?`${label} selected; Save applies it.`:"No pending replacement.");
  }

  function renderSfx(){
    const rows=filtered("sfx",["name","id"]),columns=[
      {key:"id",label:"ID"},
      {key:"name",label:"Sound"},
      {key:"durationMs",label:"Length",render:row=>assetDuration(row.durationMs)},
      {key:"loop",label:"Loop",render:row=>row.valid?(row.loop?"Yes":"No"):"—"},
      {key:"modFiles",label:"Replaced",render:row=>row.modFiles?.length?`Yes (${row.modFiles.length})`:"—"}];
    showPaged("sfx",rows,columns,sfxDetail,"70px minmax(200px,1.5fr) 90px 70px 110px");
  }
  function sfxDetail(row,prefs){
    if(String(row.id).startsWith("file:"))
      return sharedDetail(row,prefs,[LexeditorUI.detailNote(row.note),
        detailSection({title:"MOD FILE",body:[
          detailField({label:"FILE",control:readonlyField(row.modFiles[0].file)}),
          detailField({label:"SIZE",control:readonlyField(assetFileSize(row.bytes))})]})]);
    const sections=[];
    if(row.valid)sections.push(detailSection({title:"PREVIEW",body:[
      detailField({label:"",control:el("audio",{src:`/assets/sfx/${row.id}?dataset=${encodeURIComponent(assetDataset())}`,controls:true,"aria-label":`Play ${row.name}`})})]}));
    const facts=[
      detailField({label:"FORMAT",control:readonlyField(row.valid?`${row.codec} · ${row.channels===1?"mono":"stereo"} · ${formatNumber(row.rate)} Hz · ${row.bits}-bit`:"—")}),
      detailField({label:"LENGTH",control:readonlyField(assetDuration(row.durationMs))}),
      detailField({label:"LOOP",help:infoHelp("Looping sounds repeat until the game stops them. The flag comes from the shipped sound index."),control:readonlyField(row.valid?(row.loop?"Yes":"No"):"—")}),
      detailField({label:"USED BY",help:infoHelp("Battle actors proved to play this sound, from the battle actor sound table. Most sounds have no proven usage and show none."),control:readonlyField(row.usedBy?.length?row.usedBy.join("; "):"No proven battle usage")})];
    if(!row.valid)facts.push(detailField({label:"",control:LexeditorUI.detailNote(row.note)}));
    sections.push(detailSection({title:"SOUND",body:facts}));
    const modBody=(row.modFiles||[]).map(entry=>detailField({label:"FILE",control:readonlyField(`${entry.file} · ${assetFileSize(entry.sizeBytes)}`)}));
    if(!modBody.length)modBody.push(detailField({label:"",control:LexeditorUI.detailNote("No mod replaces this sound.")}));
    for(const [flag,value] of Object.entries(row.config||{}))modBody.push(detailField({label:String(flag).toUpperCase(),control:readonlyField(Array.isArray(value)?value.join(", "):String(value))}));
    if(state.data.sfx.configError)modBody.push(detailField({label:"",control:LexeditorUI.detailNote(state.data.sfx.configError)}));
    sections.push(detailSection({title:"MOD FILES",body:modBody,
      help:infoHelp("Mod files whose FFNx external name claims this sound. Global files are plain sound IDs; battle, menu, world, and field prefixes replace it in one context.")}));
    if(row.valid){
      const upload=el("input",{type:"file",accept:".ogg,.wav,.flac,.mp3,audio/ogg,audio/wav",hidden:true});
      upload.onchange=()=>assetStageUpload(row,"audioBase64",upload,null,file=>{
        const ext=file.name.split(".").pop()?.toLowerCase();
        if(!["ogg","wav","flac","mp3"].includes(ext)){showAlert({title:"Unsupported audio",message:`${file.name} is not an OGG, WAV, FLAC, or MP3 file.`});return null}
        return {audioExt:ext,audioRevert:false};
      });
      const replace=el("button",{type:"button",disabled:state.activeSource!=="mine",onclick:()=>upload.click()},"Replace"),
        revert=el("button",{type:"button",disabled:state.activeSource!=="mine"||(!row.modFiles?.length&&!row.audioBase64),title:"Remove this sound's replacement",onclick:()=>{row.audioBase64="";row.audioExt="";row.audioRevert=row.modFiles?.length?true:false;shell.refresh();render()}},"Revert"),
        exportLink=el("a",{href:`/assets/sfx/${row.id}?dataset=${encodeURIComponent(assetDataset())}`,download:`ff8-sound-${row.id}.wav`},"Export"),
        pending=assetPendingNote(row,"audioBase64","Replacement");
      const replaceBody=[detailField({label:"",control:LexeditorUI.actionRow(replace,revert,exportLink)})];
      if(state.data.sfx.externalSfx===false)replaceBody.push(detailField({label:"",control:LexeditorUI.detailNote("FFNx external SFX are off, so the game ignores replacements. Turn on use_external_sfx under Tweaks > FFNx.")}));
      replaceBody.push(detailField({label:"",control:pending}));
      sections.push(detailSection({title:"REPLACEMENT",body:replaceBody,
        help:infoHelp("Replace writes sfx/<id>.<ext> into this project; FFNx plays it instead of the shipped sound. Revert deletes the project override.")}));
    }
    return sharedDetail(row,prefs,sections);
  }

  function modelKindName(kind){return {monster:"Monster",nomodel:"No model",body:"Body",edea:"Edea body",weapon:"Weapon","weapon-reduced":"Attack data",locked:"Locked",empty:"Empty"}[kind]||kind}
  function renderModels(){
    const rows=filtered("models",["name","file"]),columns=[
      {key:"file",label:"File"},
      {key:"name",label:"Model"},
      {key:"modelKind",label:"Kind",render:row=>modelKindName(row.modelKind)},
      {key:"vertices",label:"Vertices",render:row=>row.vertices==null?"—":formatNumber(row.vertices)},
      {key:"timCount",label:"Textures",render:row=>row.timCount??"—"}];
    showPaged("models",rows,columns,modelDetail,"110px minmax(150px,2fr) 90px 80px 70px");
  }
  // A model's texture pages as cards. The panel body and the model-preview
  // drawer show the same grid, so it is built once. `inPlace` keeps the pages
  // where the reader already is: a creature's own texture pages are that
  // creature's data, not a reason to leave for the Textures page.
  function modelTextureCards(row,options={}){
    const inPlace=options.inPlace===true;
    return LexeditorUI.tileGrid((row.tims||[]).map(tim=>{
      const key=`${row.id}#${tim.index}`,palette=Math.max(0,Math.min((tim.paletteCount||1)-1,Number(assetPalettes[key]??0)));
      const targetId=`battle/${row.file}#${tim.index}`,targetLabel=`Texture ${tim.index+1}`;
      const preview=el("img",{src:`/assets/texture.png?id=${encodeURIComponent(targetId)}&palette=${palette}&dataset=${encodeURIComponent(assetDataset())}`,alt:`${row.name}, texture ${tim.index+1}`});
      const cardContent=LexeditorUI.stack({fill:false},el("span",{},targetLabel),LexeditorUI.iconSlot({content:preview,shape:'square'}));
      const link=inPlace?cardContent:hoverable({content:cardContent,targetType:"texture",targetId,targetLabel,activate:()=>{state.selected.textures=targetId;navigate("textures")}})
      const paletteSelect=tim.paletteCount>1?selectControl(palette,Array.from({length:tim.paletteCount},(_,id)=>({value:id,name:`Palette ${id+1}`})),value=>{assetPalettes[key]=value;renderModels()}):null;
      if(paletteSelect)paletteSelect.setAttribute("aria-label",`${row.name} texture ${tim.index+1} palette`);
      const card=[link];
      if(paletteSelect)card.push(detailField({label:"PALETTE",help:infoHelp("Palette selection only changes this preview; the game chooses palettes while rendering."),control:paletteSelect}));
      return LexeditorUI.stack({fill:false},...card);
    }),{minWidth:160});
  }
  // The first texture page of a battle model, as the record's own picture.
  // A creature whose model the game ships shows the creature; only a record
  // with no page left falls back to the shared placeholder.
  function modelPageThumb(model){
    const tim=model?.tims?.[0];
    if(!model?.file||!tim)return null;
    const id=`battle/${model.file}#${tim.index}`;
    return el("img",{src:`/assets/texture.png?id=${encodeURIComponent(id)}&palette=0&dataset=${encodeURIComponent(assetDataset())}`,alt:`${model.name} texture page`});
  }
  // What the shared model-preview drawer shows for a battle model. Nothing here
  // draws 3D: what a reader can check without leaving the page is the model's own
  // texture pages, the file facts beside them, and the way on to its record.
  function modelPreviewSpec(row,extra=null,options={}){
    if(!row?.file)return null;
    return {label:`${row.name} model`,
      openLabel:`Open the ${row.name} model`,
      closeLabel:`Close the ${row.name} model`,
      content:()=>LexeditorUI.stack({fill:false},
        LexeditorUI.detailNote([row.file,modelKindName(row.modelKind),
          row.vertices==null?"no vertices":`${formatNumber(row.vertices)} vertices`,
          `${row.timCount??0} textures`].join(" - ")),
        row.tims?.length?modelTextureCards(row,options)
          :LexeditorUI.detailNote("This file has no texture pages to preview."),
        ...(extra?[extra]:[]))};
  }
  function modelDetail(row,prefs){
    const sections=[];
    if(row.counts)sections.push(detailSection({title:"GEOMETRY",body:LexeditorUI.controlGroup([
      {label:"OBJECTS",control:readonlyField(formatNumber(row.counts.objects))},
      {label:"VERTICES",control:readonlyField(formatNumber(row.counts.vertices))},
      {label:"TRIANGLES",control:readonlyField(formatNumber(row.counts.triangles))},
      {label:"QUADS",control:readonlyField(formatNumber(row.counts.quads))}],{columns:4,stacked:true})}));
    if(row.tims?.length)sections.push(detailSection({title:"TEXTURES",body:modelTextureCards(row)}));
    if(row.sections?.length){
      const table=columnList({fill:true,rows:row.sections,key:section=>section.index,localSort:false,class:"ff8-model-sections",template:"52px minmax(150px,1fr) 110px 110px",columns:[
        {key:"index",label:"#",render:section=>String(section.index)},
        {key:"name",label:"Section"},
        {key:"offset",label:"Offset",render:section=>formatNumber(section.offset)},
        {key:"size",label:"Size",render:section=>assetFileSize(section.size)}]});
      sections.push(detailSection({title:"SECTIONS",body:[table],
        help:infoHelp("The model's building blocks in file order. Only whole-file replacement is supported; no section is editable.")}));
    }
    const links=[];
    if(row.enemyId!=null)links.push(el("button",{type:"button",onclick:()=>{state.selected.enemies=row.enemyId;navigate("enemies")}},"Open in Enemies"));
    if(row.editor==="encounters")links.push(el("button",{type:"button",onclick:()=>navigate("encounters")},"Open in Encounters"));
    if(links.length)sections.push(detailSection({title:"LINKS",body:[detailField({label:"",control:LexeditorUI.actionRow(...links)})]}));
    const upload=el("input",{type:"file",accept:".dat,.x,application/octet-stream",hidden:true});
    upload.onchange=()=>assetStageUpload(row,"datBase64",upload,null,file=>{
      const ext=file.name.split(".").pop()?.toLowerCase();
      if(!["dat","x"].includes(ext)){showAlert({title:"Unsupported model",message:`${file.name} is not a .dat or .x battle file.`});return null}
      return {datRevert:false};
    });
    const replace=el("button",{type:"button",disabled:state.activeSource!=="mine",onclick:()=>upload.click()},"Replace"),
      revert=el("button",{type:"button",disabled:state.activeSource!=="mine"||!row.override,onclick:()=>{row.datBase64="";row.datRevert=true;shell.refresh();render()}},"Revert"),
      exportLink=row.sha256?el("a",{href:`/assets/models/${row.file}?dataset=${encodeURIComponent(assetDataset())}`,download:row.file},"Export"):null,
      pending=assetPendingNote(row,"datBase64","Replacement"),
      actions=LexeditorUI.actionRow(...[replace,revert,exportLink].filter(Boolean));
    sections.push(detailSection({title:"FILE",body:[
      detailField({label:"OVERRIDE",control:readonlyField(row.override||"None — shipped file")}),
      detailField({label:"",control:actions}),
      detailField({label:"",control:pending})],
      help:infoHelp([row.note,"Replace writes this battle file into the project's direct/ folder; FFNx loads it instead of the archive copy. Revert deletes the project copy."].filter(Boolean).join(' '))}));
    return detailPanel({title:row.name,meta:`${row.file} · ${assetFileSize(row.sizeBytes)}`,body:sections,modelPreview:modelPreviewSpec(row)});
  }

  function renderTextures(){
    const rows=filtered("textures",["name","id","ffnxBase","source"]),columns=[
      {key:"name",label:"Texture"},
      {key:"source",label:"Source"},
      {key:"width",label:"Size",render:row=>row.width==null?"—":`${row.width} × ${row.height} · ${row.depth}-bit`},
      {key:"modFiles",label:"Mod files",render:row=>row.modFiles?.length?formatNumber(row.modFiles.length):"—"}];
    // The name gets the room: a max-content size column took 287px and left
    // the texture's own name a 38px stub.
    showPaged("textures",rows,columns,textureDetail,"minmax(160px,1fr) max-content max-content max-content",{fixedTemplate:true,defaultSplit:58});
  }
  function textureDetail(row,prefs){
    const sections=[];
    const paletteCount=row.paletteCount||0;
    const isFile=String(row.id).startsWith("file:");
    const previewable=row.mapped||(isFile&&String(row.name||"").toLowerCase().endsWith(".png"));
    let icon=null;
    if(previewable){
      const key=row.id,palette=Math.max(0,Math.min(Math.max(0,paletteCount-1),Number(assetPalettes[key]??0)));
      icon=el("img",{src:`/assets/texture.png?id=${encodeURIComponent(row.id)}&palette=${palette}&dataset=${encodeURIComponent(assetDataset())}`,alt:row.name});
    }else if(isFile){
      sections.push(LexeditorUI.detailNote("Only PNG mod textures can be previewed."));
    }
    const facts=[detailField({label:"SOURCE",control:readonlyField(row.source)})];
    if(row.width!=null)facts.push(detailField({label:"SIZE",control:readonlyField(`${row.width} × ${row.height} · ${row.depth}-bit`)}));
    if(row.ffnxBase)facts.push(detailField({label:"FFNX NAME",help:infoHelp("The external texture name FFNx derives for this asset. A mod file replaces it when its path extends this name; every match is listed below as evidence."),control:readonlyField(row.ffnxBase)}));
    if(previewable&&paletteCount>1){
      const key=row.id,palette=Math.max(0,Math.min(Math.max(0,paletteCount-1),Number(assetPalettes[key]??0)));
      const paletteSelect=selectControl(palette,Array.from({length:paletteCount},(_,id)=>({value:id,name:`Palette ${id+1}`})),value=>{assetPalettes[key]=value;renderTextures()});
      paletteSelect.setAttribute("aria-label",`${row.name} preview palette`);
      facts.push(detailField({label:"PALETTE",help:infoHelp("Palette selection only changes this preview; the game chooses palettes while rendering."),control:paletteSelect}));
    }
    // The texture's caveat is help, not a paragraph in the panel body.
    sections.push(detailSection({title:"TEXTURE",help:row.note?infoHelp(row.note):null,body:facts}));
    const modBody=(row.modFiles||[]).map(entry=>detailField({label:"FILE",control:readonlyField(`${entry.file} · ${assetFileSize(entry.sizeBytes)}`)}));
    if(!modBody.length)modBody.push(detailField({label:"",control:LexeditorUI.detailNote("No mod replaces this texture.")}));
    sections.push(detailSection({title:"MOD FILES",body:modBody,
      help:infoHelp("Mod files whose path extends this texture's FFNx external name. Files under any other path are listed as unmapped mod textures instead.")}));
    // The subtitle is the file this texture belongs to, and it goes where the
    // texture is edited: the Models tab for a model file, the Maps tab for a
    // world one. The hover card names the destination, so the line stays the
    // file's name instead of a whole button's worth of instruction.
    let meta=row.id;
    if(row.editor==="models"&&row.modelFile){
      meta=hoverable({content:row.modelFile,targetType:"models",targetId:row.modelFile,targetLabel:`${row.modelFile} in Models`,activate:()=>{state.selected.models=row.modelFile;navigate("models")}});
    }else if(row.editor==="world"){
      meta=hoverable({content:row.id,targetType:"world",targetId:row.timIndex,targetLabel:`World Texture ${row.timIndex+1} in Maps`,activate:()=>{state.selected.world=row.timIndex;state.worldTab="textures";navigate("world")}});
    }
    return detailPanel({title:row.name,meta,icon,body:sections});
  }
