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

  // An asset this mod replaces reads the way an edited record does: its name
  // in the accent, from the list to its heading, whether the replacement is
  // saved or only staged.
  function assetName(row,overridden){return overridden?el("span",{class:"lex-value-modified"},el("output",{},row.name)):row.name}
  const sfxOverridden=row=>!!(row.modFiles?.length||row.audioBase64);
  const sfxFile=row=>String(row.id).startsWith("file:");
  // A mod copy of an enemy's file also holds its stats and AI; the model is
  // only changed when its model sections differ (the server compares them).
  const modelOverridden=row=>!!(row.modelChanged||row.datBase64);
  const textureOverridden=row=>!!row.modFiles?.length;
  function renderSfx(){
    // A shipped sound has no name of its own - "Sound 12" only repeats its
    // ID - so the list shows the ID; a sound a mod adds shows its file name.
    const rows=filtered("sfx",["name","id"]),columns=[
      {key:"id",label:"ID",render:row=>sfxFile(row)?row.name:row.id,
        cellClass:row=>sfxOverridden(row)?"lex-value-modified":""},
      {key:"durationMs",label:"Length",render:row=>assetDuration(row.durationMs)},
      {key:"loop",label:"Loop",render:row=>row.valid?(row.loop?"Yes":"No"):"—"},
      {key:"modFiles",label:"Replaced",render:row=>row.modFiles?.length?`Yes (${row.modFiles.length})`:"—"}];
    showPaged("sfx",rows,columns,sfxDetail,"minmax(90px,1fr) 90px 70px 110px");
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
    return sharedDetail({...row,titleContent:assetName({...row,name:"Sound effect"},sfxOverridden(row))},prefs,sections);
  }

  function modelKindName(kind){return {monster:"Monster",stage:"Battle stage",effect:"Summon mesh",surface:"Effect surface","sound-data":"Sound data","battle-data":"Battle resources",font:"Font",formations:"Formations","effect-data":"Summon data","effect-model":"Effect model",texture:"Texture",nomodel:"No model",body:"Body",edea:"Edea body",weapon:"Weapon","weapon-reduced":"Attack data",locked:"Unsupported",empty:"Empty"}[kind]||kind}
  function renderModels(){
    const rows=filtered("models",["name","file"]),columns=[
      {key:"file",label:"File"},
      {key:"name",label:"Model",render:row=>assetName(row,modelOverridden(row))},
      {key:"modelKind",label:"Kind",render:row=>modelKindName(row.modelKind)},
      {key:"vertices",label:"Vertices",render:row=>row.vertices==null?"—":formatNumber(row.vertices)},
      {key:"timCount",label:"Textures",render:row=>row.timCount??"—"}];
    showPaged("models",rows,columns,modelDetail,"110px minmax(150px,2fr) 90px 80px 70px");
  }
  // The detail pane and preview drawer share the same linked texture cards.
  function modelTextureCards(row,options={}){
    return LexeditorUI.tileGrid((row.tims||[]).map(tim=>{
      const key=`${row.id}#${tim.index}`,palette=Math.max(0,Math.min((tim.paletteCount||1)-1,Number(assetPalettes[key]??0)));
      const targetId=`battle/${row.file}#${tim.index}`,targetLabel=`Texture ${tim.index+1}`;
      const preview=el("img",{src:`/assets/texture.png?id=${encodeURIComponent(targetId)}&palette=${palette}&dataset=${encodeURIComponent(assetDataset())}`,alt:`${row.name}, texture ${tim.index+1}`});
      const link=content=>hoverable({content,targetType:"textures",targetId,targetLabel,
        activate:()=>{state.selected.textures=targetId;state.filters.textures='';navigate("textures")}});
      const paletteSelect=tim.paletteCount>1?selectControl(palette,Array.from({length:tim.paletteCount},(_,id)=>({value:id,name:`Palette ${id+1}`})),value=>{assetPalettes[key]=value;render()}):null;
      if(paletteSelect)paletteSelect.setAttribute("aria-label",`${row.name} texture ${tim.index+1} palette`);
      return LexeditorUI.recordCard({title:link(targetLabel),image:link(preview),
        body:paletteSelect?detailField({label:"PALETTE",help:infoHelp("Palette selection only changes this preview; the game chooses palettes while rendering."),control:paletteSelect}):null});
    }),{minWidth:160,balanced:true});
  }
  // Summon textures can take their palette from a different packed file.
  const pendingSummonTextures=new Map();
  function summonTextureOptions(row,dataset){
    const key=JSON.stringify([row.file,dataset]);
    if(!pendingSummonTextures.has(key))pendingSummonTextures.set(key,
      fetch(`/api/summon-textures?file=${encodeURIComponent(row.file)}&dataset=${encodeURIComponent(dataset)}`).then(async response=>{
        const result=await response.json();if(!response.ok)throw Error(result.error||'Could not read summon textures');return result;
      }).finally(()=>pendingSummonTextures.delete(key)));
    return pendingSummonTextures.get(key);
  }
  function summonTextureThumb(row){
    const image=el('img',{alt:row.name}),dataset=assetDataset();
    const missing=()=>image.replaceWith(LexeditorUI.noImage());
    image.onerror=missing;
    summonTextureOptions(row,dataset).then(result=>{
      const texture=result.rows.find(texture=>texture.palette!=null);
      if(!texture){missing();return;}
      image.src=`/assets/summon-texture.png?file=${encodeURIComponent(row.file)}&dataset=${encodeURIComponent(dataset)}&texture=${texture.id}&palette=${encodeURIComponent(texture.palette)}`;
    }).catch(missing);
    return image;
  }
  function summonTextureCards(row){
    const host=el('div',{},LexeditorUI.loadingPanel({label:'Loading summon textures'})),dataset=assetDataset();
    const base=`file=${encodeURIComponent(row.file)}&dataset=${encodeURIComponent(dataset)}`;
    summonTextureOptions(row,dataset).then(result=>{
      const cards=result.rows.filter(texture=>texture.palettes.length).map(texture=>{
        const image=el('img',{alt:`${row.name}, texture ${texture.id}`});
        const show=palette=>{image.src=`/assets/summon-texture.png?${base}&texture=${texture.id}&palette=${encodeURIComponent(palette)}`;};
        const control=selectControl(texture.palette,texture.palettes,show);
        control.setAttribute('aria-label',`${row.file} texture ${texture.id} preview palette`);
        image.onerror=()=>image.replaceWith(LexeditorUI.detailNote('Could not load this summon texture.'));
        show(texture.palette);
        return LexeditorUI.recordCard({title:texture.name||`Texture ${texture.id}`,image,
          body:detailField({label:'PREVIEW PALETTE',control,help:infoHelp('Changes the colours in this preview. The summon can use different palettes while it plays. This choice does not change the game.')} )});
      });
      host.replaceChildren(cards.length?LexeditorUI.tileGrid(cards,{minWidth:160,balanced:true}):result.rows.length?LexeditorUI.detailNote('No complete palette is available for these textures.'):LexeditorUI.detailNote('No texture uploads were found for this file.'));
    }).catch(error=>host.replaceChildren(LexeditorUI.detailNote(error.message)));
    return host;
  }

  // The first texture page of a battle model, as the record's own picture.
  // A creature whose model the game ships shows the creature; only a record
  // with no page left falls back to the shared placeholder.
  // The header's picture is the model itself, rendered by the same viewer the
  // header opens (Lexer: the Models header showed no image, yet a click
  // showed the model). Enemies and Models share it.
  function modelPageThumb(model){
    if(!model?.file)return null;
    if(model.modelKind==='effect'&&!model.effectMeshes?.some(mesh=>mesh.triangles||mesh.quads))return summonTextureThumb(model);
    if(model.summonFamily!=null&&!model.vertices&&!model.counts?.vertices)return summonTextureThumb(model);
    if(['texture','font'].includes(model.modelKind))return el('img',{src:`/assets/texture.png?id=${encodeURIComponent(`battle/${model.file}#0`)}&palette=0&dataset=${encodeURIComponent(assetDataset())}`,alt:model.name});
    if(!model.vertices&&!model.counts?.vertices)return null;
    return FF8ModelThumbnail({file:model.file,dataset:assetDataset(),label:model.name,revision:model.sha256});
  }
  // Both Enemies and Models open the same geometry viewer from their header.
  function modelPreviewSpec(row,extra=null,options={}){
    if(!row?.file||(!row.vertices&&!row.counts?.vertices))return null;
    if(['effect','surface'].includes(row.modelKind)){
      const meshes=(row.effectMeshes||[]).filter(mesh=>mesh.triangles||mesh.quads);
      if(!meshes.length)return null;
      return {label:`${row.name} geometry`,openLabel:`Open the ${row.name} geometry`,closeLabel:`Close the ${row.name} geometry`,
        content:()=>{
          const host=el('div',{style:'display:contents'});
          const frames=el('div',{style:'display:contents'});
          let selected=meshes[0].id;
          const draw=frame=>{host.querySelector('.lex-model-stage')?.lexDispose?.();host.replaceChildren(FF8ModelViewer({file:row.file,dataset:assetDataset(),label:row.name,objectId:selected,frame,initialView:row.modelKind==='surface'?{yaw:.55,pitch:-.6}:{}}));};
          const show=id=>{selected=id;frames.replaceChildren();const mesh=meshes.find(mesh=>String(mesh.id)===String(id));
            if(mesh.frameCount>1){const control=selectControl(0,Array.from({length:mesh.frameCount},(_,i)=>({value:i,name:`Frame ${i+1}`})),draw);control.setAttribute('aria-label','Surface frame');frames.append(detailField({label:'FRAME',control}));}draw(0);};
          const control=selectControl(meshes[0].id,meshes.map(mesh=>({value:mesh.id,name:`Object ${mesh.id} · ${mesh.vertices} vertices`})),show);
          control.setAttribute('aria-label','Summon mesh object');show(meshes[0].id);
          return LexeditorUI.stack(detailField({label:'OBJECT',control,help:infoHelp(row.modelKind==='surface'?'Select an object and frame to inspect its shape. The effect\'s placement and timing are not shown. Surfaces without matching textures stay plain.':'Each object is shown separately, with textures from its first simulated appearance when known. Animation and placement within the summon are not shown. Morph targets have vertices but no standalone surface.')}),frames,host);
        },onClose:drawer=>{drawer.querySelector('.lex-model-stage')?.lexDispose?.();drawer.replaceChildren();}};
    }
    return {label:`${row.name} model`,
      openLabel:`Open the ${row.name} model`,
      closeLabel:`Close the ${row.name} model`,
      content:()=>{
        let selectedPart=row.modelParts?.[0]?.id;
        let selectedTexture=null;
        const host=el('div',{style:'display:contents'});
        const textureControls=el('div',{style:'display:contents'});
        const show=id=>{selectedPart=id;host.querySelector('.lex-model-stage')?.lexDispose?.();host.replaceChildren(FF8ModelViewer({file:row.file,dataset:assetDataset(),label:row.name,objectId:id,textureSource:selectedTexture,onReady:(_canvas,scene)=>{
          textureControls.replaceChildren();
          if(!scene.textureChoices?.length)return;
          const control=selectControl(selectedTexture||'', [{value:'',name:'Automatic'},...scene.textureChoices.map(name=>({value:name,name}))],value=>{selectedTexture=value||null;show(selectedPart);});
          control.setAttribute('aria-label','Model preview texture');
          textureControls.append(detailField({label:'TEXTURE',control,help:infoHelp('These images fit the same surfaces. Choose one for the preview and GLB export. Automatic leaves ambiguous surfaces plain.')}));
        }}));};
        const controls=[];
        if(row.modelParts?.length){
          const control=selectControl(selectedPart,row.modelParts.map(part=>({value:part.id,name:`Part ${part.id+1} · ${part.vertices} vertices`})),show);
          control.setAttribute('aria-label','Model part');
          controls.push(detailField({label:'PART',control,help:infoHelp('Each part has its own pose. Export GLB saves the selected part. Surfaces stay plain when several textures match.')}));
        }
        show(selectedPart);
        return LexeditorUI.stack(...controls,textureControls,
        LexeditorUI.actionRow(infoHelp(row.modelKind==='stage'?'Drag to turn the stage and use the wheel to zoom. Arrow keys turn it, plus and minus zoom, and Home resets. This preview shows static geometry and textures.':row.modelKind==='effect-model'?'Drag or use arrow keys to turn the model. The wheel, plus and minus zoom, and Home resets the view. Export GLB includes matching textures, its skeleton and animations. Unmatched surfaces stay plain.':'Drag to turn the model and use the wheel to zoom. Arrow keys also turn it; plus and minus zoom, and Home resets the view. The preview shows its first pose; Export GLB includes its textures, skeleton, and animations.'),
          ...(row.modelKind==='stage'?[]:[el('button',{type:'button',onclick:()=>el('a',{href:`/assets/model.glb?file=${encodeURIComponent(row.file)}&dataset=${encodeURIComponent(assetDataset())}${selectedPart==null?'':`&object=${selectedPart}`}${selectedTexture==null?'':`&textureSource=${encodeURIComponent(selectedTexture)}`}`,download:`${row.file.replace(/\.[^.]+$/,'')}${selectedPart==null?'':`-part-${Number(selectedPart)+1}`}.glb`}).click()},'Export GLB')]),...(extra?[extra]:[])),host);
      },
      onClose:drawer=>{drawer.querySelector('.lex-model-stage')?.lexDispose?.();drawer.replaceChildren();}};
  }
  function modelDetail(row,prefs){
    const sections=[];
    if(row.counts)sections.push(detailSection({title:"GEOMETRY",body:LexeditorUI.controlGroup([
      {label:"OBJECTS",control:readonlyField(formatNumber(row.counts.objects))},
      {label:"VERTICES",control:readonlyField(formatNumber(row.counts.vertices))},
      {label:"TRIANGLES",control:readonlyField(formatNumber(row.counts.triangles))},
      {label:"QUADS",control:readonlyField(formatNumber(row.counts.quads))}],{columns:4,stacked:true})}));
    if(row.tims?.length)sections.push(detailSection({title:"TEXTURES",body:modelTextureCards(row)}));
    if(row.motion?.length){
      const multiple=row.motion.length>1;
      const rows=row.motion.flatMap(part=>part.animations.map(animation=>({...animation,part:part.part})));
      sections.push(detailSection({title:'ANIMATIONS',body:[LexeditorUI.controlGroup(row.motion.map(part=>({label:multiple?`PART ${part.part} BONES`:'BONES',control:readonlyField(formatNumber(part.bones))})),{columns:4,stacked:true}),columnList({rows,key:item=>`${item.part}-${item.id}`,localSort:false,template:multiple?'1fr 1fr 1fr':'1fr 1fr',columns:[
        ...(multiple?[{key:'part',label:'Part'}]:[]),{key:'id',label:'Animation'},
        {key:'frames',label:'Frames'}]})],
        help:infoHelp('Frame counts describe the stored poses. Playback timing depends on the game. These animations are read-only.')}));
    }
    if(row.summonFamily!=null)sections.push(detailSection({title:'TEXTURES',body:summonTextureCards(row),help:infoHelp('Shows packed textures and texture uploads found by simulating the summon script. Different uploads can use different parts of a file. Battle-dependent script paths may use other textures.')}));
    if(row.sections?.length||row.effectResources?.length){
      const resources=!!row.effectResources?.length;
      const table=columnList({fill:true,rows:resources?row.effectResources:row.sections,key:section=>section.index,localSort:false,class:"ff8-model-sections",template:resources?"52px minmax(150px,1fr) 110px":"52px minmax(150px,1fr) 110px 110px",columns:[
        {key:"index",label:"#",render:section=>String(section.index)},
        {key:"name",label:resources?"Resource":"Section"},
        {key:"offset",label:"Offset",render:section=>formatNumber(section.offset)},
        ...(resources?[]:[{key:"size",label:"Size",render:section=>assetFileSize(section.size)}])]});
      sections.push(detailSection({title:resources?"RESOURCES":"SECTIONS",body:[table],
        help:infoHelp(resources?"Textures and palettes stored in this file. Their numbers identify them within the summon. Individual resources are not editable.":row.modelKind==='sound-data'?"Parts of this sound file. The sound data is not editable here.":row.modelKind==='battle-data'?"Shared resources used during battle or after a victory. Individual sections are read-only.":"The model's building blocks in file order. Only whole-file replacement is supported; no section is editable.")}));
    }
    const links=[];
    if(row.enemyId!=null)links.push(el("button",{type:"button",onclick:()=>{state.selected.enemies=row.enemyId;navigate("enemies")}},"Open in Enemies"));
    if(row.editor==="encounters")links.push(el("button",{type:"button",onclick:()=>navigate("encounters")},"Open in Encounters"));
    if(links.length)sections.push(detailSection({title:"LINKS",body:[detailField({label:"",control:LexeditorUI.actionRow(...links)})]}));
    const upload=el("input",{type:"file",accept:row.modelKind==='texture'?undefined:".dat,.x,application/octet-stream",hidden:true});
    upload.onchange=()=>assetStageUpload(row,"datBase64",upload,null,file=>{
      const ext=file.name.split(".").pop()?.toLowerCase();
      if(row.modelKind!=='texture'&&!["dat","x"].includes(ext)){showAlert({title:"Unsupported model",message:`${file.name} is not a .dat or .x battle file.`});return null}
      return {datRevert:false};
    });
    const replace=el("button",{type:"button",disabled:state.activeSource!=="mine"||row.modelKind==='sound-data'||(row.modelKind!=='texture'&&!(/\.(dat|x)$/i.test(row.file))),onclick:()=>upload.click()},"Replace"),
      revert=el("button",{type:"button",disabled:state.activeSource!=="mine"||!row.override,onclick:()=>{row.datBase64="";row.datRevert=true;shell.refresh();render()}},"Revert"),
      exportLink=row.sha256?el("a",{href:`/assets/models/${row.file}?dataset=${encodeURIComponent(assetDataset())}`,download:row.file},"Export"):null,
      pending=assetPendingNote(row,"datBase64","Replacement"),
      actions=LexeditorUI.actionRow(...[replace,revert,exportLink].filter(Boolean));
    sections.push(detailSection({title:"FILE",body:[
      detailField({label:"OVERRIDE",control:readonlyField(row.override||"None — shipped file")}),
      detailField({label:"",control:actions}),
      detailField({label:"",control:pending})],
      help:infoHelp([row.note,"Replace writes this battle file into the project's direct/ folder; FFNx loads it instead of the archive copy. Revert deletes the project copy."].filter(Boolean).join(' '))}));
    return detailPanel({title:assetName(row,modelOverridden(row)),icon:modelPageThumb(row)||LexeditorUI.noImage(),meta:`${row.file} · ${assetFileSize(row.sizeBytes)}`,body:sections,modelPreview:modelPreviewSpec(row)});
  }

  function renderTextures(){
    const rows=filtered("textures",["name","id","ffnxBase","source"]),columns=[
      {key:"name",label:"Texture",render:row=>assetName(row,textureOverridden(row))},
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
    return detailPanel({title:assetName(row,textureOverridden(row)),meta,icon,body:sections});
  }
