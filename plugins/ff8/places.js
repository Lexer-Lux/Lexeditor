  function renderRefine(){
    const query=state.filters.refine.trim().toLocaleLowerCase(),rows=state.data.refine.rows.filter(row=>row.table===state.refineTab&&(!query||[row.id,row.groupName,row.inputName,row.outputName,row.text].some(value=>String(value??"").toLocaleLowerCase().includes(query)))),[sortKey,sortDirection]=state.sorts.refine,visible=[...rows].sort((left,right)=>sortDirection*String(rowSortValue(left,sortKey)).localeCompare(String(rowSortValue(right,sortKey)),undefined,{numeric:true,sensitivity:"base"}));
    const columns=[
      {key:"id",label:"ID",width:"58px",render:row=>row.id+1},
      {key:"groupName",label:"ABILITY",width:"minmax(120px,.65fr)",headerTitle:"Refine ability",render:row=>el("span",{title:row.groupDescription},row.groupName)},
      {key:"name",label:"RECIPE",width:"minmax(180px,1fr)",render:row=>el("span",{title:`${row.inputName} → ${row.outputName}`},`${row.inputName} → ${row.outputName}`)},
      ...[
        ["inputName","Input"],["inputQuantity","Needed"],
        ["outputName","Output"],["outputQuantity","Received"],
        ["text","Recipe text"]
      ].map(([key,label])=>({key,label,pinned:false,numeric:key.endsWith("Quantity")||key==="unknown",width:key.endsWith("Quantity")||key==="unknown"?"80px":"minmax(120px,1fr)"}))
    ];
    // The identification column held 36px, which is narrower than the record
    // mark plus the two digits it shows, so the id clipped itself. The name
    // columns keep their share; the id takes the few pixels it needs.
    delete state.columnPrefs.refine;showPaged("refine",visible,columns,refineDetail,"48px minmax(60px,.7fr) minmax(60px,1fr)",{defaultSplit:55,minLeft:210,minRight:430,maxBarrels:5});
    const content=$("#main").firstElementChild,tabs=subtabBar({className:"refine-tabs",tabs:state.data.refine.tables.map(table=>({id:table.id,label:table.name})),active:state.refineTab,label:"Refine recipe tables",change:value=>{state.refineTab=value;state.pages.refine=0;state.selected.refine=null;renderRefine()}});$("#main").replaceChildren(LexeditorUI.stack(tabs,content));
  }

  function fieldMapRow(dataset,key){return dataset?.fields?.rows?.find(row=>row.key===key)}
  async function ensureFieldDetail(row){
    // A failed lazy read must remain a stable error state. Retrying it from the
    // render path created an endless request/render loop that made the detail
    // pane alternate between its full height and a clipped loading panel.
    if(row._loaded||row._loading||row._error)return;row._loading=true;
    try{
      const dataset=state.activeSource==="mine"?"current":state.activeSource;
      const current=await api(`/api/field?map=${encodeURIComponent(row.key)}&dataset=${encodeURIComponent(dataset)}`),vanilla=state.activeSource==="mine"?await api(`/api/field?map=${encodeURIComponent(row.key)}&dataset=vanilla`):current;
      Object.assign(row,current,{_loaded:true,_loading:false});
      const vanillaRow=fieldMapRow(state.vanilla,row.key);if(vanillaRow)Object.assign(vanillaRow,clone(vanilla),{_loaded:true,_loading:false});
      const baseIndex=state.base.fields?.findIndex(value=>value.key===row.key)??-1;if(baseIndex>=0)state.base.fields[baseIndex]=clone(row);touchHistoryBaseRow("fields",row.key);
      await Promise.all(state.references.map(async reference=>{const referenceRow=fieldMapRow(state.referenceData[reference.id],row.key);if(!referenceRow)return;try{const value=await api(`/api/field?map=${encodeURIComponent(row.key)}&dataset=${encodeURIComponent(`reference:${reference.id}`)}`);Object.assign(referenceRow,clone(value),{_loaded:true,_loading:false})}catch(error){referenceRow._error=error.message||String(error)}}));
    }catch(error){row._loading=false;row._error=error.message||String(error)}
    if(state.tab==="fields")renderFields();shell.refresh();
  }
  function fieldParamControl(row,entry){
    const param=entry.param,vanilla=fieldMapRow(state.vanilla,row.key)?.players?.[entry.player.id]?.params?.[param.id];
    if(!param.editable)return readonlyField(`Unsupported opcode 0x${Number(param.opcode).toString(16).toLocaleUpperCase()}`);
    return sourceControl(numberControl(param.value,0,0xFFFFFF,1,value=>param.value=value,{"aria-label":`${row.name} ${entry.player.entity} ${param.name}`}),()=>param.value,vanilla?.value,[],value=>param.value=Number(value));
  }
  function fieldEntranceControl(row,kind,entry,field,axis=null){
    const collection=kind==="gateway"?"gateways":"triggers",vanilla=fieldMapRow(state.vanilla,row.key)?.entrances?.[collection]?.[entry.id],read=value=>axis?value?.[field]?.[axis]:value?.[field],minimum=field==="fieldId"?0:field==="doorId"?0:-32768,maximum=field==="fieldId"?32767:field==="doorId"?255:32767,label=`${row.name} ${kind} ${entry.id+1} ${field}${axis?` ${axis}`:""}`;
    return sourceControl(numberControl(read(entry),minimum,maximum,1,value=>{if(axis)entry[field][axis]=value;else entry[field]=value;refreshFieldOverlay()},{"aria-label":label}),()=>read(entry),read(vanilla),[],value=>{if(axis)entry[field][axis]=Number(value);else entry[field]=Number(value);refreshFieldOverlay()});
  }
  function fieldGatewayTargetControl(row,entry){
    const vanilla=fieldMapRow(state.vanilla,row.key)?.entrances?.gateways?.[entry.id]?.fieldId;
    const target=state.data.fields.rows.find(value=>value.mapId===entry.fieldId),label=target?.name||'Unused';
    const change=value=>{entry.fieldId=Number(value);refreshFieldOverlay();rerenderFields();shell.refresh()};
    const originalFilter=state.filters.fields,originalPage=state.pages.fields;
    const origin=()=>{state.fieldTargetSearch=false;state.selected.fields=row.id;state.filters.fields=originalFilter;state.pages.fields=originalPage;state.fieldDetailTab='exits';navigate('fields')};
    const link=hoverable({content:label,targetType:'fields',targetId:target?.id,targetLabel:label,
      activate:()=>{if(target){state.selected.fields=target.id;state.filters.fields=target.name;state.pages.fields=0;navigate('fields')}}});
    const finder=el('button',{type:'button','aria-label':'Choose target field',title:'Choose target field',onclick:()=>beginSearcher({
      type:'fields',prompt:'Choose the field loaded by this exit.',origin,
      target:()=>{state.fieldTargetSearch=true;state.filters.fields='';state.pages.fields=0;navigate('fields')},accept:id=>{
        const chosen=state.data.fields.rows.find(value=>value.id===id);
        if(chosen?.mapId!=null)change(chosen.mapId);
        else showAlert('This field is not in the game map list and cannot be an exit destination.');
      }})},LexeditorUI.selectionIcon());
    const control=LexeditorUI.inlineLabel(LexeditorUI.choiceField(link,finder),el('button',{type:'button',disabled:entry.fieldId===32767,
      title:'Disable this exit',onclick:()=>change(32767)},'Unused'));
    return sourceControl(control,()=>entry.fieldId,vanilla,[],change,value=>state.data.fields.rows.find(field=>field.mapId===Number(value))?.name||'Unused');
  }

  function fieldPointControl(row,kind,entry,point){return LexeditorUI.controlGroup(["x","y","z"].map(axis=>({label:axis.toLocaleUpperCase(),help:infoHelp(`${axis.toLocaleUpperCase()} field coordinate of this point. Moving an endpoint changes the crossing line; moving Destination changes the arrival position.`),control:fieldEntranceControl(row,kind,entry,point,axis)})))}
  function fieldDialogueReferences(row,lineId){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:fieldMapRow(state.referenceData[reference.id],row.key)?.dialogue?.[lineId]?.text})).filter(entry=>entry.value!==undefined)}
  function fieldDialogueSection(row){const vanilla=fieldMapRow(state.vanilla,row.key);if(!row.dialogue?.length)return LexeditorUI.notice({message:"This field map has no dialogue lines."});return detailSection({title:"DIALOGUE",help:infoHelp("Dialogue shown by this field's scripts. Edit a line to change its message; keep its number and control codes. Some unused fields contain Japanese test text that the current Western decoder displays incorrectly. This editor does not translate it."),body:LexeditorUI.stack({fill:false},...row.dialogue.map(line=>{const area=LexeditorUI.textArea({rows:3,"aria-label":`${row.name} dialogue line ${line.id}`,oninput:event=>{line.text=event.target.value;shell.refresh()}});area.value=line.text;const control=sourceControl(area,()=>line.text,vanilla?.dialogue?.[line.id]?.text,fieldDialogueReferences(row,line.id),value=>line.text=String(value));return detailField({label:`#${line.id}`,control})}))})}
  function fieldScriptReferences(row,methodId){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:fieldMapRow(state.referenceData[reference.id],row.key)?.scripts?.methods?.find(method=>method.id===methodId)?.source})).filter(entry=>entry.value!==undefined)}
  function fieldScriptsSection(row){const methods=row.scripts?.methods||[];if(!methods.length)return LexeditorUI.notice({message:"This field map has no JSM methods."});let methodId=Number(state.fieldScriptSelection[row.key]);if(!methods.some(method=>method.id===methodId))methodId=methods[0].id;state.fieldScriptSelection[row.key]=methodId;const method=methods.find(value=>value.id===methodId),vanilla=fieldMapRow(state.vanilla,row.key)?.scripts?.methods?.find(value=>value.id===methodId),picker=selectControl(methodId,methods.map(value=>({id:value.id,name:`${value.id} · ${value.name}`})),value=>{state.fieldScriptSelection[row.key]=Number(value);rerenderFields()},{"aria-label":`${row.name} field script`}),area=LexeditorUI.codeField({rows:18,wrap:"off",readOnly:!method.editable,"aria-label":`${row.name} script ${method.id}`,oninput:event=>{method.source=event.target.value;shell.refresh()}});area.value=method.source;const source=sourceControl(area,()=>method.source,vanilla?.source,fieldScriptReferences(row,method.id),value=>method.source=String(value),value=>`${String(value??"").split(/\r?\n/).filter(Boolean).length} lines`);return detailSection({title:"FIELD SCRIPTS",help:infoHelp(`Scripts control events and actions in this location. Select a script, then edit its instructions, one per line. Keep opcode names and operand order. Labels mark branch destinations. Save validates and rebuilds branches; unsupported methods remain read-only. There are ${row.scripts.opcodeCount} recognised opcode names.`),body:[LexeditorUI.controlGroup([{label:"Script",control:picker},LexeditorUI.detailNote(`${method.groupType.toLocaleUpperCase()} GROUP ${method.groupId} · ${method.instructionCount} WORDS`)]),!method.editable?LexeditorUI.detailNote("This method has an unknown opcode or a branch outside the method, so it remains read-only."):null,source]})}
  function fieldEncounterReferences(row,kind,slot=null){return state.references.map(reference=>{const encounters=fieldMapRow(state.referenceData[reference.id],row.key)?.randomEncounters,value=kind==="rate"?encounters?.rate:encounters?.formations?.[slot];return{name:reference.name,shortName:reference.shortName,value}}).filter(entry=>entry.value!==undefined)}
  function fieldEncounterSection(row){const encounters=row.randomEncounters;if(!encounters?.formations?.length)return LexeditorUI.notice({message:"This field map has no MRT/RAT random encounter pair."});const vanilla=fieldMapRow(state.vanilla,row.key)?.randomEncounters,choices=(state.data.encounters?.rows||[]).map(entry=>({id:entry.id,name:`${entry.id} · ${entry.name}`})),format=value=>choices.find(entry=>Number(entry.id)===Number(value))?.name||value,fields=encounters.formations.map((value,slot)=>{const apply=next=>encounters.formations[slot]=Number(next),control=selectControl(value,choices,apply);control.setAttribute("aria-label",`${row.name} random encounter formation ${slot+1}`);return detailField({label:`FORMATION ${slot+1}`,help:infoHelp("Battle formation selected by this field's MRT random encounter table."),control:sourceControl(control,()=>encounters.formations[slot],vanilla?.formations?.[slot],fieldEncounterReferences(row,"formation",slot),apply,format),dataType:"ENUM"})}),setRate=value=>encounters.rate=Number(value),rate=numberControl(encounters.rate,0,255,1,setRate,{"aria-label":`${row.name} random encounter rate`});fields.push(detailField({label:"ENCOUNTER RATE",help:infoHelp("Stored random encounter rate for this field. The exact conversion to time or distance between battles is not established here. Saving applies this value to all four rate entries."),control:sourceControl(rate,()=>encounters.rate,vanilla?.rate,fieldEncounterReferences(row,"rate"),setRate),dataType:"INT",min:0,max:255}));return detailSection({className:"field-encounter-section",title:"RANDOM ENCOUNTERS",help:infoHelp("Choose the four battle formations available for random encounters in this field. Inspect their enemies in the Encounters tab. Encounter Rate controls the stored rate for this field."),body:LexeditorUI.tileGrid(fields)})}
  function fieldBackgroundTile(dataset,row,tileId){return fieldMapRow(dataset,row.key)?.background?.tiles?.[tileId]}
  function fieldBackgroundReferences(row,tileId,field){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:fieldBackgroundTile(state.referenceData[reference.id],row,tileId)?.[field]})).filter(entry=>entry.value!==undefined)}
  function fieldBackgroundEdits(row){const base=state.base.fields?.find(value=>value.key===row.key)?.background,edits=[];if(!base)return edits;for(const tile of row.background?.tiles||[]){const before=base.tiles?.[tile.id];if(!before)continue;const edit={tile:tile.id};for(const field of row.background.editableFields||[])if(tile[field]!==before[field])edit[field]=tile[field];if(Object.keys(edit).length>1)edits.push(edit)}return edits}
  function fieldBackgroundPreviewState(row){let value=state.fieldBackgroundPreview[row.key];if(!value){value={layers:[...(row.background?.layers||[])],states:(row.background?.parameterStates||[]).filter(entry=>entry.state===0).map(entry=>`${entry.parameter}:${entry.state}`),hide:false,overlay:true};state.fieldBackgroundPreview[row.key]=value}return value}
  async function refreshFieldBackgroundPreview(row,image,status){const preview=fieldBackgroundPreviewState(row),token=Symbol("field-background-preview");image.lexRequest=token;status.textContent="Rendering field background...";try{const dataset=state.activeSource==="mine"?"current":state.activeSource,edits=fieldBackgroundEdits(row),geometryPromise=preview.overlay?api("/api/field/background-geometry",post({map:row.key,dataset,edits})).catch(()=>null):Promise.resolve(null),response=await fetch("/api/field/background-preview",post({map:row.key,dataset,edits,activeStates:preview.states.map(value=>{const [parameter,stateValue]=value.split(":").map(Number);return{parameter,state:stateValue}}),enabledLayers:preview.layers,hideBackground:preview.hide,highlightTile:state.fieldBackgroundSelection[row.key]??0}));if(!response.ok){const problem=await response.json().catch(()=>({}));throw new Error(problem.error||`HTTP ${response.status}`)}const blob=await response.blob(),geometry=await geometryPromise;if(image.lexRequest!==token||!image.isConnected)return;const url=URL.createObjectURL(blob),old=image.lexObjectUrl;image.lexObjectUrl=url;image.onload=()=>{if(old)URL.revokeObjectURL(old)};image.src=url;image.lexGeometry=geometry;image.lexBaseStatus=`${row.background.variant} MAP - ${formatNumber(row.background.tileCount)} tiles - ${image.alt}`;const note=drawFieldOverlay(row,image.lexOverlay,geometry);status.textContent=`${image.lexBaseStatus}${note?" - "+note:""}`}catch(error){if(image.lexRequest===token){status.textContent=`Preview unavailable: ${error.message||error}`}}}
  function fieldBackgroundControl(row,tile,field,label,minimum,maximum,help){const vanilla=fieldBackgroundTile(state.vanilla,row,tile.id),references=fieldBackgroundReferences(row,tile.id,field),apply=value=>{tile[field]=field==="draw"?Boolean(value):Number(value);const image=document.querySelector(`.field-background-image[data-field-key="${CSS.escape(row.key)}"]`),status=image?.lexStatus;if(image&&status)refreshFieldBackgroundPreview(row,image,status);shell.refresh()};let control;if(field==="draw")control=el("input",{type:"checkbox",checked:tile.draw,"aria-label":`${row.name} tile ${tile.id} draw`,onchange:event=>apply(event.target.checked)});else control=numberControl(tile[field],minimum,maximum,1,apply,{"aria-label":`${row.name} tile ${tile.id} ${label}`});return detailField({label,help:infoHelp(help),control:sourceControl(control,()=>tile[field],vanilla?.[field],references,apply,field==="draw"?booleanMark:undefined),dataType:field==="draw"?"BOOL":"INT",min:field==="draw"?undefined:minimum,max:field==="draw"?undefined:maximum})}
  function fieldProject(camera,vertex){
    // Deling WalkmeshGLWidget::paintGL: axis rows over 4096 with the Y row
    // negated, position over 4096 with Y negated, fovy of 2*atan(112/zoom)
    // on the 320x224 screen centred at (160,112). The 4096 scale cancels in
    // the projection, so raw units project directly. Behind the camera or a
    // degenerate axis set has no screen point and returns null.
    const forward=camera.axis[2],up0=camera.axis[1],forwardLength=Math.hypot(forward.x,forward.y,forward.z);
    if(!forwardLength)return null;
    const fx=forward.x/forwardLength,fy=forward.y/forwardLength,fz=forward.z/forwardLength,ux=-up0.x,uy=-up0.y,uz=-up0.z;
    let sx=fy*uz-fz*uy,sy=fz*ux-fx*uz,sz=fx*uy-fy*ux;
    const length=Math.hypot(sx,sy,sz);if(!(length>0))return null;sx/=length;sy/=length;sz/=length;
    const tx=sy*fz-sz*fy,ty=sz*fx-sx*fz,tz=sx*fy-sy*fx;
    // CA stores the view translation, not the eye position. Recover the eye
    // with the transposed rotation, as Deling's lookAt setup does.
    const eye=axis=>-(camera.position.x*camera.axis[0][axis]+camera.position.y*camera.axis[1][axis]+camera.position.z*camera.axis[2][axis])/4096;
    const dx=vertex.x-eye('x'),dy=vertex.y-eye('y'),dz=vertex.z-eye('z');
    const depth=dx*fx+dy*fy+dz*fz;if(!(depth>0))return null;
    // MAP tile coordinates are centred on the screen origin. The image's
    // bounds offset is applied once by the caller, not another 160/112 here.
    return {x:camera.zoom*(dx*sx+dy*sy+dz*sz)/depth,y:-camera.zoom*(dx*tx+dy*ty+dz*tz)/depth};
  }
  function fieldOverlayCameraId(row){const count=row.camera?.cameras?.length||0;if(!count)return null;return Math.max(0,Math.min(count-1,Number(state.fieldCameraSelection[row.key])||0))}
  function drawFieldOverlay(row,canvas,geometry){
    // Deling draws walkmesh edges white (blue where the edge has no
    // neighbour), used exits red, and used triggers green over the
    // background. Segments with an end behind the camera are skipped.
    canvas.lexRow=row;canvas.lexGeometry=geometry||null;
    const ctx=canvas.getContext("2d");if(!ctx)return "";
    const clear=()=>{if(canvas.width)ctx.clearRect(0,0,canvas.width,canvas.height)},preview=state.fieldBackgroundPreview[row.key],cameraId=fieldOverlayCameraId(row);
    if(preview&&preview.overlay===false){clear();return "overlay off"}
    if(!geometry||cameraId===null||!row.walkmesh?.triangles?.length){clear();return !geometry?"overlay unavailable":cameraId===null?"no camera setups":"no walkmesh"}
    canvas.width=geometry.width;canvas.height=geometry.height;
    const camera=row.camera.cameras[cameraId],point=vertex=>{const projected=fieldProject(camera,vertex);return projected?{x:projected.x+geometry.left,y:projected.y+geometry.top}:null},selected=state.fieldWalkmeshSelection[row.key]??-1;
    for(const triangle of row.walkmesh.triangles){if(triangle.id!==selected)continue;const corners=triangle.vertices.map(point);if(!corners.every(Boolean))continue;ctx.beginPath();ctx.moveTo(corners[0].x,corners[0].y);ctx.lineTo(corners[1].x,corners[1].y);ctx.lineTo(corners[2].x,corners[2].y);ctx.closePath();ctx.fillStyle="rgba(255,144,0,.35)";ctx.fill()}
    for(const triangle of row.walkmesh.triangles){const highlight=triangle.id===selected;for(let edge=0;edge<3;edge++){const from=triangle.vertices[edge],to=triangle.vertices[(edge+1)%3],p=point(from),q=point(to);if(!p||!q)continue;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.strokeStyle=highlight?"#ff9000":from.adjacent===-1?"rgba(102,153,204,.9)":"rgba(255,255,255,.85)";ctx.lineWidth=highlight?3:1;ctx.stroke()}}
    const gateId=state.fieldGatewaySelection[row.key]??-1;
    for(const gate of row.entrances?.gateways||[]){if(gate.fieldId===32767)continue;const p=point(gate.exitA),q=point(gate.exitB);if(!p||!q)continue;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.strokeStyle=gate.id===gateId?"#ffffff":"#ff0000";ctx.lineWidth=gate.id===gateId?3:2;ctx.stroke()}
    const triggerId=state.fieldTriggerSelection[row.key]??-1;
    for(const trigger of row.entrances?.triggers||[]){if(trigger.doorId===255)continue;const p=point(trigger.lineA),q=point(trigger.lineB);if(!p||!q)continue;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.strokeStyle=trigger.id===triggerId?"#ffffff":"#00ff00";ctx.lineWidth=trigger.id===triggerId?3:2;ctx.stroke()}
    return `overlay: camera ${cameraId+1}`;
  }
  function refreshFieldOverlay(){for(const canvas of document.querySelectorAll("canvas.field-overlay-canvas"))if(canvas.lexRow)drawFieldOverlay(canvas.lexRow,canvas,canvas.lexGeometry)}
  function fieldPreviewPanel(row){
    const background=row.background;
    if(!background?.tiles?.length){const message=background?.error?`This background is read-only: ${background.error}`:"This field map has no MAP/MIM background.";return {preview:LexeditorUI.detailNote(message),editor:LexeditorUI.detailNote(message)}}
    const tileId=Math.max(0,Math.min(background.tileCount-1,Number(state.fieldBackgroundSelection[row.key])||0));
    state.fieldBackgroundSelection[row.key]=tileId;
    const preview=fieldBackgroundPreviewState(row),tile=background.tiles[tileId];
    if(state.fieldDetailTab==='walkmesh')preview.overlay=true;
    const image=el("img",{class:"field-background-image lex-overlay-base","data-field-key":row.key,alt:`${row.name} composed background`});
    const overlay=el("canvas",{class:"field-overlay-canvas lex-overlay-layer","aria-hidden":"true"});
    image.lexOverlay=overlay;
    const media=el("div",{class:"field-preview-stack lex-overlay-stack"},image,overlay);
    media.addEventListener('click',event=>{
      if(state.fieldDetailTab!=='walkmesh'||!image.lexGeometry)return;
      const cameraId=fieldOverlayCameraId(row);if(cameraId===null)return;
      const box=overlay.getBoundingClientRect(),x=(event.clientX-box.left)*overlay.width/box.width,y=(event.clientY-box.top)*overlay.height/box.height;
      for(const triangle of row.walkmesh?.triangles||[]){
        const points=triangle.vertices.map(vertex=>fieldProject(row.camera.cameras[cameraId],vertex));
        if(!points.every(Boolean))continue;
        const path=new Path2D();points.forEach((point,index)=>path[index?'lineTo':'moveTo'](point.x+image.lexGeometry.left,point.y+image.lexGeometry.top));path.closePath();
        if(overlay.getContext('2d').isPointInPath(path,x,y)){state.fieldWalkmeshSelection[row.key]=triangle.id;rerenderFields();break;}
      }
    });
    const status=LexeditorUI.detailNote("Rendering field background...");image.lexStatus=status;
    status.classList.add('lex-media-status');status.hidden=true;status.setAttribute('role','status');
    new MutationObserver(()=>{status.hidden=!status.textContent.startsWith('Preview unavailable:')}).observe(status,{childList:true});
    const redraw=()=>refreshFieldBackgroundPreview(row,image,status);
    const picker=numberControl(tileId,0,background.tileCount-1,1,value=>{state.fieldBackgroundSelection[row.key]=Number(value);rerenderFields()},{"aria-label":`${row.name} selected background tile`});
    const cameras=row.camera?.cameras||[],overlayCamId=cameras.length?fieldOverlayCameraId(row):null;
    const overlayToggle=LexeditorUI.toggleRow({toggles:[{label:"Walkmesh overlay",checked:preview.overlay!==false,help:"Project walkable triangles, exits, and triggers over the background through the selected camera. This changes only the preview.",change:checked=>{preview.overlay=checked;const note=drawFieldOverlay(row,overlay,image.lexGeometry);if(image.lexBaseStatus)status.textContent=`${image.lexBaseStatus}${note?" - "+note:""}`}}]});
    const overlayCamera=cameras.length?detailField({label:"Overlay camera",help:infoHelp("Camera used to project the walkmesh overlay. This is the same selection as the Camera page."),control:selectControl(overlayCamId,cameras.map(entry=>({id:entry.id,name:`Camera ${entry.id+1}`})),value=>{state.fieldCameraSelection[row.key]=Number(value);rerenderFields()})}):null;
    const layers=LexeditorUI.toggleRow({label:"Preview layers",toggles:background.layers.map(layer=>({label:`Layer ${layer}`,checked:preview.layers.includes(layer),change:checked=>{preview.layers=checked?[...new Set([...preview.layers,layer])]:preview.layers.filter(value=>value!==layer);redraw()}}))});
    const states=background.parameterStates.length?LexeditorUI.toggleRow({label:"Preview parameter states",toggles:background.parameterStates.map(entry=>{
      const key=`${entry.parameter}:${entry.state}`;
      return {label:`P${entry.parameter} S${entry.state}`,checked:preview.states.includes(key),change:checked=>{preview.states=checked?[...new Set([...preview.states,key])]:preview.states.filter(value=>value!==key);redraw()}};
    })}):LexeditorUI.detailNote("No conditional states");
    const definitions=[
    ["x","DESTINATION X",-32768,32767,"Horizontal destination of this 16 by 16 tile."],["y","DESTINATION Y",-32768,32767,"Vertical destination of this 16 by 16 tile."],["z","DESTINATION Z",0,65535,"Draw-order depth stored by this tile."],["sourceX","SOURCE X",0,255,"Horizontal source coordinate in the MIM texture."],["sourceY","SOURCE Y",0,255,"Vertical source coordinate in the MIM texture."],["texture","TEXTURE",0,15,"MIM texture page selected by this tile."],["palette","PALETTE",0,15,"MIM palette selected by indexed-colour tiles."],["blend","ALPHA",0,3,"Two-bit alpha mode stored in the packed texture word."],["draw","DRAW",0,1,"When off, this tile draws black instead of its MIM pixels."],["depth","COLOUR TYPE",0,3,"Stored colour-depth selector used to read the MIM pixels."],["layer","LAYER",0,255,"New-format background layer used by the preview filter."],["blendType","ALPHA TYPE",0,4,"New-format pixel blend operation."],["parameter","PARAMETER",0,255,"Field-script background parameter. 255 is unconditional."],["state","STATE",0,255,"State paired with the background parameter."]
  ];
    const fields=definitions.filter(([field])=>background.editableFields.includes(field)).map(([field,label,min,max,help])=>fieldBackgroundControl(row,tile,field,label,min,max,help));
    const editor=LexeditorUI.stack({fill:false},...[overlayToggle,overlayCamera,
      detailField({label:"Tile",control:picker,help:infoHelp("Select an existing tile to edit. This does not add a tile.")}),
      detailField({label:"Layers",control:layers,help:infoHelp("Show or hide layers in the preview. These filters do not change the game.")}),
      detailField({label:"Parameter states",control:states,help:infoHelp("P is the parameter number and S is its required state. These filters change only the preview.")}),
      LexeditorUI.toggleRow({toggles:[{label:"Hide unconditional background",checked:preview.hide,help:"Hide tiles with parameter 255 to inspect conditional tiles. This changes only the preview.",change:checked=>{preview.hide=checked;redraw()}}]}),
      LexeditorUI.tileGrid(fields)].filter(Boolean));
    requestAnimationFrame(redraw);
    const view=LexeditorUI.imageMap({media,label:`${row.name} background and walkmesh`});view.append(status);
    return {preview:view,editor};
  }
  function fieldWalkmeshVertex(dataset,row,triangleId,vertexId){return fieldMapRow(dataset,row.key)?.walkmesh?.triangles?.[triangleId]?.vertices?.[vertexId]}
  function fieldWalkmeshControl(row,triangle,vertex,field){const vanilla=fieldWalkmeshVertex(state.vanilla,row,triangle.id,vertex.id),references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:fieldWalkmeshVertex(state.referenceData[reference.id],row,triangle.id,vertex.id)?.[field]})).filter(entry=>entry.value!==undefined),minimum=field==="adjacent"?-1:-32768,maximum=field==="adjacent"?row.walkmesh.triangleCount-1:32767,apply=value=>{vertex[field]=Number(value);refreshFieldOverlay()};return sourceControl(numberControl(vertex[field],minimum,maximum,1,apply,{"aria-label":`${row.name} triangle ${triangle.id} vertex ${vertex.id} ${field}`}),()=>vertex[field],vanilla?.[field],references,apply)}
  function fieldWalkmeshSection(row){
    const mesh=row.walkmesh;
    if(!mesh?.triangles?.length)return LexeditorUI.detailNote(mesh?.error?`This walkmesh is read-only: ${mesh.error}`:"This field map has no walkmesh.");
    const triangleId=Math.max(0,Math.min(mesh.triangleCount-1,Number(state.fieldWalkmeshSelection[row.key])||0));
    state.fieldWalkmeshSelection[row.key]=triangleId;
    const vertexPanel=LexeditorUI.stack({fill:false});
    const showVertices=triangle=>vertexPanel.replaceChildren(...triangle.vertices.map(vertex=>detailSection({title:`Vertex ${vertex.id+1}`,body:LexeditorUI.tileGrid(
      ["x","y","z","adjacent"].map(field=>detailField({label:field==="adjacent"?`Edge ${vertex.id+1}`:field.toLocaleUpperCase(),
        help:infoHelp(field==="adjacent"?"Neighbour triangle across this edge. Use -1 for no neighbour.":`${field.toLocaleUpperCase()} coordinate of this corner. Changing it reshapes the walkable triangle.`),
        control:fieldWalkmeshControl(row,triangle,vertex,field)})))})));
    const select=value=>{state.fieldWalkmeshSelection[row.key]=Math.max(0,Math.min(mesh.triangleCount-1,Number(value)||0));showVertices(mesh.triangles[state.fieldWalkmeshSelection[row.key]]);refreshFieldOverlay()};
    const picker=numberControl(triangleId,0,mesh.triangleCount-1,1,select,{"aria-label":`${row.name} selected walkmesh triangle`});
    showVertices(mesh.triangles[triangleId]);
    return LexeditorUI.stack({fill:false},detailField({label:"Triangle",help:infoHelp("Select the triangle to edit by its zero-based number, or click it in the background preview above. The selected triangle is orange. This selects an existing triangle; it does not change the triangle count."),control:picker}),vertexPanel);
  }
  const fieldDetailTabs=[{id:"camera",label:"Camera",help:"Edit the fixed camera setups stored in this field's .ca file. Each camera has three axis vectors, a position, and a zoom. The preview overlay uses the selected camera."},{id:"walkmesh",label:"Walkmesh",help:"The walkmesh is the surface on which characters can move. Select a triangle by number or click it in the preview above. Orange marks the selected triangle. Move its corners with X, Y and Z, and set which neighbour each edge leads to. The preview uses the selected field camera."},{id:"exits",label:"Exits",help:"Edit the gateway exit lines that leave this field. Crossing an exit line loads the target field and places the player at its destination point."},{id:"doors",label:"Doors",help:"Enable door triggers and set which field script door line each one opens. A trigger with Used off stores door ID 255 and never fires."},{id:"ranges",label:"Camera Ranges",help:"Camera ranges limit how far the view can scroll across this location. Screen ranges define the field screen bounds. Set the top, bottom, left and right edges for the selected range. Some field formats omit these values; those ranges are read-only. The selected field's .inf header is quoted here as its variant and byte size: the variant decides which ranges the file actually stores, and a range it does not store shows Deling's defaults and cannot be edited."},{id:"movie",label:"Movie Camera",help:"Edit the movie camera frames stored in this field's .msk file. Each frame holds four vertices that steer the camera during scripted sequences."},{id:"misc",label:"Misc.",help:"Edit this field's header values, random encounters, and Triple Triad player parameters. Parts of the location that are not editable are listed too."},{id:"scripts",label:"Field Scripts",help:"Edit the JSM field scripts that control events in this location, one instruction per line. Saving validates the methods and rebuilds branches."},{id:"dialogue",label:"Dialogue",help:"Edit the dialogue lines shown by this field's scripts. Keep each line's number and control codes. Unused fields may hold untranslated test text."},{id:"triggers",label:"Triggers",help:"Edit the trigger lines that start field script door or event actions when crossed. Each trigger fires the door ID set on the Doors page."}];
  function fieldDetailHelp(id){return infoHelp(fieldDetailTabs.find(tab=>tab.id===id).help)}
  function fieldCameraControl(row,camera,field,axis=null){
    const vector=field.startsWith("axis")?Number(field.slice(4)):null,vanilla=fieldMapRow(state.vanilla,row.key)?.camera?.cameras?.[camera.id];
    const read=value=>vector===null?(axis?value?.[field]?.[axis]:value?.[field]):value?.axis?.[vector]?.[axis],write=(target,val)=>{if(vector===null){if(axis)target[field][axis]=val;else target[field]=val}else target.axis[vector][axis]=val};
    const minimum=field==="zoom"?1:field==="position"?-2147483648:-32768;
    const maximum=field==="zoom"?65535:field==="position"?2147483647:32767;
    const label=`${row.name} camera ${camera.id+1} ${field}${axis?" "+axis:""}`;
    const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(fieldMapRow(state.referenceData[reference.id],row.key)?.camera?.cameras?.[camera.id])})).filter(entry=>entry.value!==undefined);
    return sourceControl(numberControl(read(camera),minimum,maximum,1,value=>{write(camera,value);refreshFieldOverlay();shell.refresh()},{"aria-label":label}),()=>read(camera),read(vanilla),references,value=>{write(camera,Number(value));refreshFieldOverlay()});
  }
  function fieldCameraSection(row){
    const cameras=row.camera?.cameras||[];
    if(!cameras.length)return LexeditorUI.detailNote(row.camera?.error?`These cameras are read-only: ${row.camera.error}`:"This field map has no camera setups.");
    const cameraId=Math.max(0,Math.min(cameras.length-1,Number(state.fieldCameraSelection[row.key])||0));
    state.fieldCameraSelection[row.key]=cameraId;
    const camera=cameras[cameraId];
    const picker=selectControl(cameraId,cameras.map(entry=>({id:entry.id,name:`Camera ${entry.id+1} of ${cameras.length}`})),value=>{state.fieldCameraSelection[row.key]=Number(value);rerenderFields()});
    const vectors=[0,1,2].map(vector=>detailSection({title:`Axis ${vector+1}`,body:LexeditorUI.controlGroup(["x","y","z"].map(axis=>({label:axis.toLocaleUpperCase(),help:infoHelp(`Axis ${vector+1} ${axis.toLocaleUpperCase()} component. The three axes aim the fixed camera; the preview overlay projects through them.`),control:fieldCameraControl(row,camera,"axis"+vector,axis)})))}));
    return detailSection({title:"Camera",help:fieldDetailHelp("camera"),body:LexeditorUI.stack({fill:false},detailField({label:"Camera",control:picker}),detailField({label:"Zoom",help:infoHelp("Camera zoom. Higher values narrow the view. Zero is rejected because the game projection would divide by zero."),control:fieldCameraControl(row,camera,"zoom")}),detailSection({title:"Position",body:LexeditorUI.controlGroup(["x","y","z"].map(axis=>({label:axis.toLocaleUpperCase(),help:infoHelp(`Camera position ${axis.toLocaleUpperCase()} in field coordinates. Moving it moves the viewpoint.`),control:fieldCameraControl(row,camera,"position",axis)})))}),...vectors)});
  }
  function fieldMovieSection(row){
    const frames=row.movie?.frames||[];
    if(!frames.length)return LexeditorUI.detailNote(row.movie?.error?`These movie frames are read-only: ${row.movie.error}`:"This field map has no movie camera frames.");
    const frameId=Math.max(0,Math.min(frames.length-1,Number(state.fieldMovieSelection[row.key])||0));
    state.fieldMovieSelection[row.key]=frameId;
    const frame=frames[frameId],vanilla=fieldMapRow(state.vanilla,row.key)?.movie?.frames?.[frameId];
    const picker=selectControl(frameId,frames.map(entry=>({id:entry.id,name:`Frame ${entry.id+1} of ${frames.length}`})),value=>{state.fieldMovieSelection[row.key]=Number(value);rerenderFields()});
    const points=frame.points.map((point,pointId)=>detailSection({title:`Point ${pointId+1}`,body:LexeditorUI.controlGroup(["x","y","z"].map(axis=>{const read=value=>value?.points?.[pointId]?.[axis],references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(fieldMapRow(state.referenceData[reference.id],row.key)?.movie?.frames?.[frame.id])})).filter(entry=>entry.value!==undefined);return{label:axis.toLocaleUpperCase(),help:infoHelp(`Frame vertex ${axis.toLocaleUpperCase()}. The four vertices steer the movie camera through this frame.`),control:sourceControl(numberControl(point[axis],-32768,32767,1,value=>point[axis]=value,{"aria-label":`${row.name} movie frame ${frame.id+1} point ${pointId+1} ${axis}`}),()=>point[axis],read(vanilla),references,value=>point[axis]=Number(value))}}))}));
    return detailSection({title:"Movie camera",help:fieldDetailHelp("movie"),body:LexeditorUI.stack({fill:false},detailField({label:"Frame",control:picker}),...points)});
  }
  function fieldExitsSection(row){
    const gateways=row.entrances?.gateways||[];
    if(!gateways.length)return LexeditorUI.notice({message:"This field map has no INF gateway records."});
    const gateId=Math.max(0,Math.min(gateways.length-1,Number(state.fieldGatewaySelection[row.key])||0));
    state.fieldGatewaySelection[row.key]=gateId;
    const entry=gateways[gateId];
    const tabs={label:"Exits",shortcuts:false,tabs:gateways.map(candidate=>({id:candidate.id,label:String(candidate.id+1)})),active:gateId,change:value=>{state.fieldGatewaySelection[row.key]=Number(value);rerenderFields()}};
    return LexeditorUI.tabbedPanel({...tabs,content:LexeditorUI.stack({fill:false},detailField({label:"Target field",help:infoHelp("The field loaded after the player crosses this exit line. Choose Unused to disable the exit."),control:fieldGatewayTargetControl(row,entry)}),detailField({label:"Exit line A",help:infoHelp("First endpoint of the line the player crosses to leave this field."),control:fieldPointControl(row,"gateway",entry,"exitA")}),detailField({label:"Exit line B",help:infoHelp("Second endpoint of the line the player crosses to leave this field."),control:fieldPointControl(row,"gateway",entry,"exitB")}),detailField({label:"Destination",help:infoHelp("Player position after the target field loads."),control:fieldPointControl(row,"gateway",entry,"destination")}))});
  }
  function fieldDoorsSection(row){
    const triggers=row.entrances?.triggers||[];
    if(!triggers.length)return LexeditorUI.notice({message:"This field map has no INF trigger records."});
    const triggerId=Math.max(0,Math.min(triggers.length-1,Number(state.fieldTriggerSelection[row.key])||0));
    state.fieldTriggerSelection[row.key]=triggerId;
    const entry=triggers[triggerId],vanilla=fieldMapRow(state.vanilla,row.key)?.entrances?.triggers?.[entry.id];
    const tabs={label:"Doors",shortcuts:false,tabs:triggers.map(candidate=>({id:candidate.id,label:String(candidate.id+1)})),active:triggerId,change:value=>{state.fieldTriggerSelection[row.key]=Number(value);rerenderFields()}};
    const used=entry.doorId!==255;
    const setUsed=value=>{entry.doorId=(value&&vanilla&&vanilla.doorId!==255)?vanilla.doorId:value?0:255;refreshFieldOverlay();rerenderFields();shell.refresh()};
    const doorRefs=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:fieldMapRow(state.referenceData[reference.id],row.key)?.entrances?.triggers?.[entry.id]?.doorId})).filter(item=>item.value!==undefined);
    const check=el("input",{type:"checkbox",checked:used,"aria-label":`${row.name} door ${entry.id+1} used`,onchange:event=>setUsed(event.target.checked)});
    const usedControl=sourceControl(check,()=>entry.doorId!==255,vanilla?.doorId!==undefined?vanilla.doorId!==255:undefined,doorRefs.map(ref=>({name:ref.name,shortName:ref.shortName,value:ref.value!==255})),value=>setUsed(value===true||value==="true"),booleanMark);
    const idControl=sourceControl(numberControl(used?entry.doorId:0,0,254,1,value=>{entry.doorId=value;refreshFieldOverlay()},{"aria-label":`${row.name} door ${entry.id+1} ID`,disabled:!used}),()=>entry.doorId,vanilla?.doorId,doorRefs,value=>{entry.doorId=Number(value);refreshFieldOverlay()});
    return LexeditorUI.tabbedPanel({...tabs,content:LexeditorUI.stack({fill:false},detailField({label:"Used",help:infoHelp("When off, this trigger stores door ID 255 and never fires. When on, crossing its trigger line opens the door below."),control:usedControl}),detailField({label:"Door ID",help:infoHelp("The field script door line opened when the player crosses this trigger. 255 disables the trigger."),control:idControl}))});
  }
  function fieldRangeControl(row,collection,entry,edge){
    const vanilla=fieldMapRow(state.vanilla,row.key)?.entrances?.[collection]?.[entry.id];
    const read=value=>value?.[edge];
    const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(fieldMapRow(state.referenceData[reference.id],row.key)?.entrances?.[collection]?.[entry.id])})).filter(item=>item.value!==undefined);
    return sourceControl(numberControl(entry[edge],-32768,32767,1,value=>entry[edge]=value,{"aria-label":`${row.name} ${collection} ${entry.id+1} ${edge}`}),()=>entry[edge],read(vanilla),references,value=>entry[edge]=Number(value));
  }
  function fieldRangesSection(row){
    const ranges=row.entrances?.cameraRanges||[],screens=row.entrances?.screenRanges||[];
    if(!ranges.length&&!screens.length)return LexeditorUI.notice({message:"This field map has no INF header."});
    const rangeId=Math.max(0,Math.min(ranges.length-1,Number(state.fieldCameraRangeSelection[row.key])||0));
    state.fieldCameraRangeSelection[row.key]=rangeId;
    const screenId=Math.max(0,Math.min(screens.length-1,Number(state.fieldScreenRangeSelection[row.key])||0));
    state.fieldScreenRangeSelection[row.key]=screenId;
    const range=ranges[rangeId],screen=screens[screenId],edges=["top","bottom","right","left"];
    const fields=(collection,entry)=>entry.present?LexeditorUI.controlGroup(edges.map(edge=>({label:edge.toLocaleUpperCase(),help:infoHelp(`The ${edge} edge of this range in field coordinates.`),control:fieldRangeControl(row,collection,entry,edge)}))):LexeditorUI.stack({fill:false},LexeditorUI.detailNote("This INF variant does not store this range. The values are Deling's defaults and cannot be edited."),LexeditorUI.tileGrid(edges.map(edge=>detailField({label:edge.toLocaleUpperCase(),control:readonlyField(entry[edge])}))));
    return detailSection({title:"Camera ranges",help:fieldDetailHelp("ranges"),body:LexeditorUI.stack({fill:false},detailField({label:"Camera range",control:selectControl(rangeId,ranges.map(candidate=>({id:candidate.id,name:`Camera range ${candidate.id+1}${candidate.present?"":" (absent)"}`})),value=>{state.fieldCameraRangeSelection[row.key]=Number(value);rerenderFields()})}),fields("cameraRanges",range),detailField({label:"Screen range",control:selectControl(screenId,screens.map(candidate=>({id:candidate.id,name:`Screen range ${candidate.id+1}${candidate.present?"":" (absent)"}`})),value=>{state.fieldScreenRangeSelection[row.key]=Number(value);rerenderFields()})}),fields("screenRanges",screen))});
  }
  function fieldHeaderControl(row,field,minimum,maximum,label){
    const vanilla=fieldMapRow(state.vanilla,row.key)?.entrances?.header;
    const references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:fieldMapRow(state.referenceData[reference.id],row.key)?.entrances?.header?.[field]})).filter(item=>item.value!==undefined);
    return sourceControl(numberControl(row.entrances.header[field],minimum,maximum,1,value=>row.entrances.header[field]=value,{"aria-label":label}),()=>row.entrances.header[field],vanilla?.[field],references,value=>row.entrances.header[field]=Number(value));
  }
  function fieldHeaderSection(row){
    const header=row.entrances?.header;
    if(!header)return LexeditorUI.notice({message:"This field map has no INF header."});
    const pvp=header.pvp===null||header.pvp===undefined?LexeditorUI.stack({fill:false},detailField({label:"PVP",control:readonlyField(`${header.pvpDefault} (default)`)}),LexeditorUI.detailNote("This INF variant does not store PVP. Deling uses 12 when it is absent.")):detailField({label:"PVP",help:infoHelp("PVP value stored in this field's .inf header. Its gameplay effect is not established here."),control:fieldHeaderControl(row,"pvp",0,65535,`${row.name} PVP`)});
    return detailSection({title:"Field header",help:infoHelp("Header values stored in this field's .inf file. The name and unknown bytes stay read-only and byte-preserved."),body:LexeditorUI.tileGrid([detailField({label:"Name",control:readonlyField(header.name||"")}),detailField({label:"Control",help:infoHelp("Movement orientation byte. Deling shows this as the walkmesh page navigation value."),control:fieldHeaderControl(row,"control",0,255,`${row.name} control`)}),detailField({label:"Unknown",control:readonlyField(header.unknown||"")}),detailField({label:"Camera focus",help:infoHelp("Camera focus height on the playable character."),control:fieldHeaderControl(row,"focus",-32768,32767,`${row.name} camera focus`)}),pvp])});
  }
  function fieldMiscSection(row){
    const entries=row.players.flatMap(player=>player.params.map(param=>({id:`${player.id}-${param.id}`,player,param}))),table=columnList({rows:entries,key:entry=>entry.id,class:"ff8-record-list field-card-table",editable:true,localSort:false,columns:[{key:"entity",label:"Entity",render:entry=>entry.player.entity},{key:"script",label:"Script",render:entry=>entry.player.script},{key:"parameter",label:"Parameter",help:"One of the seven values consumed by the CARDGAME field opcode.",render:entry=>entry.param.name},{key:"mode",label:"Source",help:"Literal stores a number in the script. Savemap reads the numbered runtime variable. Editing the value preserves this source type.",render:entry=>entry.param.mode==="literal"?"Literal":entry.param.mode==="variable"?"Savemap":"Unsupported"},{key:"value",label:"Value",help:"The exact 24-bit literal or savemap-variable number stored by this push instruction.",numeric:true,render:entry=>fieldParamControl(row,entry)}]});
    return LexeditorUI.stack({fill:false},fieldHeaderSection(row),fieldEncounterSection(row),entries.length?detailSection({title:"TRIPLE TRIAD PLAYERS",help:infoHelp("Parameters passed by field scripts when starting a card game. Literal values are stored directly; Savemap values refer to runtime variables. Editing a variable number changes which variable is read."),body:table}):LexeditorUI.notice({message:"This map has no CARDGAME calls."}),detailSection({title:"NOT YET EDITABLE",help:infoHelp("These parts of the location are listed for reference. This editor cannot change them yet."),body:LexeditorUI.detailNote(row.unsupported.join(" / "))}));
  }
  function fieldTriggersSection(row){
    const triggers=row.entrances?.triggers||[];
    if(!triggers.length)return LexeditorUI.notice({message:"This field map has no INF trigger records."});
    const triggerId=Math.max(0,Math.min(triggers.length-1,Number(state.fieldTriggerSelection[row.key])||0));
    state.fieldTriggerSelection[row.key]=triggerId;
    const entry=triggers[triggerId];
    const tabs={label:"Triggers",shortcuts:false,tabs:triggers.map(candidate=>({id:candidate.id,label:String(candidate.id+1)})),active:triggerId,change:value=>{state.fieldTriggerSelection[row.key]=Number(value);rerenderFields()}};
    return LexeditorUI.tabbedPanel({...tabs,content:LexeditorUI.stack({fill:false},detailField({label:"Door",help:infoHelp("Door ID fired by this trigger. Change it on the Doors page."),control:readonlyField(entry.doorId===255?"Unused":`Door ${entry.doorId}`)}),detailField({label:"Trigger line A",help:infoHelp("First endpoint of the door or event trigger line."),control:fieldPointControl(row,"trigger",entry,"lineA")}),detailField({label:"Trigger line B",help:infoHelp("Second endpoint of the door or event trigger line."),control:fieldPointControl(row,"trigger",entry,"lineB")}))});
  }
  function fieldDetailSubtab(row,active){
    if(active==="walkmesh")return fieldWalkmeshSection(row);
    if(active==="exits")return fieldExitsSection(row);
    if(active==="doors")return fieldDoorsSection(row);
    if(active==="ranges")return fieldRangesSection(row);
    if(active==="movie")return fieldMovieSection(row);
    if(active==="misc")return fieldMiscSection(row);
    if(active==="scripts")return fieldScriptsSection(row);
    if(active==="dialogue")return fieldDialogueSection(row);
    if(active==="triggers")return fieldTriggersSection(row);
    return fieldCameraSection(row);
  }
  function fieldDetail(row,prefs){
    if(!row._loaded){ensureFieldDetail(row);return sharedDetail(row,prefs,[el("div",{class:"field-empty"},row._error?`This map could not be opened: ${row._error}`:"Reading this field map...")],"field-map-detail",row.key)}
    const tabs=[{id:"background",label:"Background",help:"The background is built from image tiles. Select a tile to change its position or texture. Preview filters and the walkmesh overlay do not change the game."},...fieldDetailTabs].sort((a,b)=>a.label.localeCompare(b.label));
    const active=tabs.some(tab=>tab.id===state.fieldDetailTab)?state.fieldDetailTab:"background";
    state.fieldDetailTab=active;
    const background=fieldPreviewPanel(row);
    const preview=LexeditorUI.detailPanel({title:row.name.toLocaleUpperCase(),headingOverlay:true,body:background.preview,className:"field-map-detail"});
    let body=active==="background"?background.editor:fieldDetailSubtab(row,active);
    // The selected tab already supplies its name and help. Keep only that
    // section's contents, while preserving headers for actual child groups.
    // Asking the framework for the parts keeps the shared class names here.
    const parts=LexeditorUI.sectionParts(body);
    if(parts.content)body=parts.content;
    const editor=LexeditorUI.tabbedPanel({tabs,active,label:"Field detail",change:value=>{state.fieldDetailTab=value;rerenderFields()},content:LexeditorUI.detailPanel({heading:false,body})});
    return LexeditorUI.panelLayout([preview,editor],{orientation:"vertical",layoutKey:"ff8-field-detail",defaultSizes:[1,1]});
  }
  function buildFields(){const rows=filtered("fields",["name","key","group","mapId"]).filter(row=>!state.fieldTargetSearch||row.mapId!=null);return showPaged("fields",rows,[{key:"mapId",label:"MAP ID",help:"Number used to identify this field in MAPLIST. A dash means the archive is not listed; it may contain unused or test content.",numeric:true,numberedId:true,render:row=>row.mapId??"—"},{key:"name",label:"FIELD MAP",help:"Internal field archive name. Select a row to edit that location."},{key:"group",label:"GROUP",help:"Archive folder prefix used to organise fields. This is not an encounter group."},{key:"listed",label:"MAPLIST",help:"Whether this field appears in the game map list. A cross means it is not listed; it does not mean the archive is missing.",render:row=>row.listed?"✓":"×"}],fieldDetail,"90px minmax(180px,1fr) 90px 90px",{defaultSplit:34,minLeft:330,minRight:680},false)}
  function renderFields(){const root=buildFields();$("#main").replaceChildren(root);return root}
  function rerenderFields(){renderFields()}
  function rerenderWorldMap(){renderWorldMap()}

  function initOwner(dataset,kind,id=0){const init=dataset?.init;if(!init)return null;if(kind==="general"||kind==="config")return init[kind];if(kind==="gf")return init.gfs.rows.find(row=>Number(row.id)===Number(id));if(kind==="character")return init.characters.rows.find(row=>Number(row.id)===Number(id));return null}
  function initFieldSource(field,kind,id=0){const vanilla=initOwner(state.vanilla,kind,id)?.fields?.find(value=>value.field===field.field),references=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:initOwner(state.referenceData[reference.id],kind,id)?.fields?.find(value=>value.field===field.field)?.value})).filter(entry=>entry.value!==undefined);return sourceControl(fieldControl(field),()=>field.value,vanilla?.value,references,value=>field.value=field.control==="boolean"?Boolean(value):Number(value))}
  function startingFields(fields,kind,id=0){return LexeditorUI.tileGrid(fields.map(field=>detailField({label:field.label,help:field.help?infoHelp(field.help):null,control:initFieldSource(field,kind,id),dataType:field.control==="boolean"?"BOOL":field.lookup?.type==="enum"?"ENUM":field.lookup?.type==="flags"?"FLAGS":"INT",min:field.minimum,max:field.maximum})))}
  function startingPicker(label,value,rows,change){return detailField({label,control:selectControl(value,rows.map(row=>({id:row.id,name:row.name})),change)})}
  function initNestedReferences(read){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(state.referenceData[reference.id]?.init)})).filter(entry=>entry.value!==undefined)}
  function startingMagicControl(character,slot){const vanilla=state.vanilla.init.characters.rows.find(row=>row.id===character.id)?.magics[slot.slot],choices=state.data.init.choices.magic,setMagic=value=>{slot.magicId=Number(value);if(slot.magicId===0)slot.quantity=0;renderStartingData();shell.refresh()},magic=sourceControl(selectControl(slot.magicId,choices,setMagic),()=>slot.magicId,vanilla?.magicId,initNestedReferences(init=>init?.characters.rows.find(row=>row.id===character.id)?.magics[slot.slot]?.magicId),setMagic,value=>choices.find(entry=>Number(entry.id)===Number(value))?.name||value),quantity=sourceControl(numberControl(slot.quantity,0,100,1,value=>slot.quantity=value,{"aria-label":`Starting Magic quantity ${slot.slot+1}`}),()=>slot.quantity,vanilla?.quantity,initNestedReferences(init=>init?.characters.rows.find(row=>row.id===character.id)?.magics[slot.slot]?.quantity),value=>slot.quantity=Number(value));return{magic,quantity}}
  function startingInventoryControls(slot){const vanilla=state.vanilla.init.inventory.rows[slot.slot],choices=state.data.init.choices.items,setItem=value=>{slot.itemId=Number(value);if(slot.itemId===0)slot.quantity=0;renderStartingData();shell.refresh()},item=sourceControl(itemSelectControl(slot.itemId,choices,setItem),()=>slot.itemId,vanilla.itemId,initNestedReferences(init=>init?.inventory.rows[slot.slot]?.itemId),setItem,value=>choices.find(entry=>Number(entry.id)===Number(value))?.name||value),quantity=sourceControl(numberControl(slot.quantity,0,100,1,value=>slot.quantity=value,{"aria-label":`Starting item quantity ${slot.slot+1}`}),()=>slot.quantity,vanilla.quantity,initNestedReferences(init=>init?.inventory.rows[slot.slot]?.quantity),value=>slot.quantity=Number(value));return{item,quantity}}
  function renderStartingData(){
    const tabs=[{id:"general",label:"General",help:"Set the party, progress and options used when a new game begins."},{id:"characters",label:"Characters",help:"Set each character’s initial stats, equipment, status and magic stock."},{id:"inventory",label:"Inventory",help:"Set the items and quantities given at the start of a new game."}],toolbar=$("#toolbar");toolbar.hidden=false;toolbar.replaceChildren(subtabBar({tabs,active:state.startingTab,label:"Starting data",change:value=>{state.startingTab=value;renderStartingData()}}));
    let body,title;
    if(state.startingTab==="characters"){
      const rows=state.data.init.characters.rows,row=rows.find(value=>value.id===state.selected.startingCharacter)||rows[0];state.selected.startingCharacter=row.id;const pageSize=state.pageSizes.startingMagic,pages=Math.max(1,Math.ceil(row.magics.length/pageSize));state.pages.startingMagic=Math.min(state.pages.startingMagic,pages-1);const visible=row.magics.slice(state.pages.startingMagic*pageSize,(state.pages.startingMagic+1)*pageSize),controls=new Map(visible.map(slot=>[slot.slot,startingMagicControl(row,slot)])),table=columnList({rows:visible,key:slot=>slot.slot,class:"starting-magic-table ff8-record-list",editable:true,template:"70px minmax(180px,1fr) minmax(90px,130px)",columns:[{key:"slot",label:"Slot",render:slot=>slot.slot+1},{key:"magic",label:"Magic",render:slot=>controls.get(slot.slot).magic},{key:"quantity",label:"Quantity",numeric:true,render:slot=>controls.get(slot.slot).quantity}]}),pageBar=pager({page:state.pages.startingMagic,pages,total:row.magics.length,pageSize,noun:"magic slots",change:value=>{state.pages.startingMagic=value;renderStartingData()}});title="STARTING CHARACTERS";body=[startingPicker("CHARACTER",row.id,rows,value=>{state.selected.startingCharacter=value;state.pages.startingMagic=0;renderStartingData()}),detailSection({title:"CHARACTER STATE",body:startingFields(row.fields,"character",row.id)}),detailSection({title:"MAGIC STOCK",body:[table,pageBar]})];
    }else if(state.startingTab==="inventory"){
      const rows=state.data.init.inventory.rows,pageSize=state.pageSizes.startingInventory,pages=Math.max(1,Math.ceil(rows.length/pageSize));state.pages.startingInventory=Math.min(state.pages.startingInventory,pages-1);const visible=rows.slice(state.pages.startingInventory*pageSize,(state.pages.startingInventory+1)*pageSize),controls=new Map(visible.map(slot=>[slot.slot,startingInventoryControls(slot)])),table=columnList({rows:visible,key:slot=>slot.slot,class:"starting-inventory-table ff8-record-list lex-page-sized-table",editable:true,template:"70px minmax(220px,1fr) minmax(90px,140px)",columns:[{key:"slot",label:"Slot",render:slot=>slot.slot+1},{key:"item",label:"Item",render:slot=>controls.get(slot.slot).item},{key:"quantity",label:"Quantity",numeric:true,render:slot=>controls.get(slot.slot).quantity}]});table.style.setProperty("--lex-page-row-count",String(pageSize));const pageBar=pager({inline:true,page:state.pages.startingInventory,pages,total:rows.length,pageSize,noun:"inventory slots",change:value=>{state.pages.startingInventory=value;renderStartingData()}});title="STARTING INVENTORY";body=LexeditorUI.pagedPane(table,pageBar);
    }else{title="STARTING DATA";body=[detailSection({title:"PARTY AND PROGRESS",body:startingFields(state.data.init.general.fields,"general")}),detailSection({title:"CONFIG",body:startingFields(state.data.init.config.fields,"config")})]}
    $("#main").replaceChildren(detailPanel({heading:false,body}));
  }
