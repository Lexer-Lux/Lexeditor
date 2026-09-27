  function renderEnemies(){const rows=filtered("enemies",["name","filename","id","scanDescription"]),sample=state.data.enemies.rows.find(row=>row.available),columns=[{key:"id",label:"ID"},{key:"name",label:"Enemy",render:row=>recordHoverLabel("enemies",row,enemyDisplayName(row.name))},{key:"scanDescription",label:"Scan description",pinned:false},...(sample?.fields||[]).map(field=>({key:`field:${field.field}`,label:field.label,pinned:false,numeric:field.control!=="boolean"&&field.lookup?.type!=="enum",sortValue:row=>row.fields.find(value=>value.field===field.field)?.value??"",render:row=>row.fields.find(value=>value.field===field.field)?.value??""}))];showPaged("enemies",rows,columns,enemyDetail,"74px minmax(180px,1fr)",{leadingPanel:enemyLeadingPanel,minLeading:460,panelSizes:[48,18,34],minLeft:220,minRight:430})}

  function encounterName(row){const names=row.slots.filter(slot=>slot.enabled).map(slot=>enemyDisplayName(slot.enemyName)),summary=[...new Set(names)].slice(0,3).join(", ");return summary||`Encounter ${row.id}`}
  function encounterReferences(id,read){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:read(rowOf(state.referenceData[reference.id],"encounters",id))})).filter(entry=>entry.value!==undefined)}
  function encounterSource(control,row,read,apply,format=value=>String(value)){return sourceControl(control,()=>read(row),read(rowOf(state.vanilla,"encounters",row.id)),encounterReferences(row.id,read),apply,format,{internal:control?.matches?.('input[type="number"],input[inputmode="decimal"]')===true})}
  function encounterLevelRule(raw){raw=Number(raw);if(raw===252)return{mode:"ultimecia",value:1};if(raw>=1&&raw<=100)return{mode:"fixed",value:raw};if(raw>=101&&raw<=200)return{mode:"maximum",value:raw-100};return{mode:"special",value:1}}
  function encounterLevelControl(slot){
    const rule=encounterLevelRule(slot.level),apply=(mode,value=rule.value)=>{const bounded=Math.max(1,Math.min(100,Math.round(Number(value)||1)));slot.level=mode==="ultimecia"?252:mode==="maximum"?100+bounded:bounded;slot.levelRule=encounterLevelRule(slot.level);shell.refresh()};
    const mode=el("select",{"aria-label":"Enemy level rule",onchange:event=>{apply(event.target.value);renderEncounters()}},el("option",{value:"fixed"},"Fixed level"),el("option",{value:"maximum"},"Maximum level"),el("option",{value:"ultimecia"},"Ultimecia Castle: random 1–100"));
    if(rule.mode==="special")mode.append(el("option",{value:"special"},`Special (${slot.level})`));
    mode.value=rule.mode;
    return LexeditorUI.stack({fill:false},mode,...(["fixed","maximum"].includes(rule.mode)?[numberControl(rule.value,1,100,1,value=>apply(rule.mode,value),{"aria-label":"Enemy level rule value"})]:[]));
  }
  // Keep the four formation properties together. Only the arena selector has
  // established editing semantics; preserve the three unresolved header values.
  const encounterHeaderFields=[
    ["Stage","Battle stage number for this formation. It selects the arena the battle is fought in, so two formations with the same stage fight in the same place."],
    ["Flags","These battle settings are not understood yet, so this value is read-only."],
    ["Main camera","This may select the main battle camera. Its effect is not confirmed, so this value is read-only."],
    ["Secondary camera","This may select a second battle camera. Its effect is not confirmed, so this value is read-only."]];
  function encounterDetail(row,prefs){
    const formation=LexeditorUI.multiNumberRow(['stageId','flags','cameraMain','cameraSecondary'].map((key,index)=>({
      label:encounterHeaderFields[index][0],
      help:encounterHeaderFields[index][1],
      control:index===0?encounterSource(numberControl(row[key],0,255,1,value=>{row[key]=value;shell.refresh()},{'aria-label':'Formation stage'}),row,value=>value?.[key],value=>{row[key]=Number(value);shell.refresh()}):LexeditorUI.readonlyField(row[key])
    })),{columns:4,stacked:true});
    const source=(slot,key,control)=>{
      if(!slot.enabled&&key!=='enabled')for(const input of [control,...control.querySelectorAll('input,select,button')])
        if(input.matches('input,select,button'))input.disabled=true;
      return encounterSource(control,row,value=>value?.slots?.find(entry=>entry.slot===slot.slot)?.[key],value=>{slot[key]=value;if(key==='enabled')renderEncounters();shell.refresh()});
    };
    const table=columnList({rows:row.slots,key:slot=>slot.slot,editable:true,fill:true,
      'aria-label':'Formation enemies',columns:[
        {key:'slot',label:'Slot',width:'max-content',render:slot=>LexeditorUI.numberValue(slot.slot+1)},
        {key:'enemyId',label:'Enemy',grow:2,render:slot=>source(slot,'enemyId',enemySearchControl(slot.enemyId,`Choose enemy for slot ${slot.slot+1}`,value=>{slot.enemyId=Number(value);slot.enemyName=enemyById(value).name;shell.refresh()},()=>navigate('encounters')))},
        ...['enabled','visible','loaded','targetable'].map(key=>({key,label:key==='enabled'?LexeditorUI.enabledMark:key[0].toUpperCase()+key.slice(1),render:slot=>source(slot,key,el('input',{type:'checkbox',checked:slot[key],'aria-label':`Slot ${slot.slot+1} ${key}`,onchange:event=>{slot[key]=event.target.checked;if(key==='enabled')renderEncounters();shell.refresh()}}))})),
        ...['x','y','z'].map(key=>({key,label:key.toUpperCase(),grow:1,render:slot=>source(slot,key,numberControl(slot[key],-32768,32767,1,value=>{slot[key]=value;shell.refresh()},{'aria-label':`Slot ${slot.slot+1} ${key}`}))})),
        {key:'level',label:'Level rule',grow:2,render:slot=>source(slot,'level',encounterLevelControl(slot))}
      ]});
    return LexeditorUI.stack(
      detailPanel({heading:false,body:[formation]}),
      table
    );
  }
  // The Encounters tab itself lives in encounters_ui.js: the formation list
  // above is its Formations subtab, beside Rules and Groups.

  function worldRow(dataset,kind,id){return dataset?.world?.rows?.find(row=>row.kind===kind&&Number(row.id)===Number(id))}
  function worldNumber(row,key,min,max,label,refresh=render){
    const vanilla=worldRow(state.vanilla,row.kind,row.id),refs=state.references.map(reference=>({name:reference.name,
      shortName:reference.shortName,value:worldRow(state.referenceData[reference.id],row.kind,row.id)?.[key]}))
      .filter(entry=>entry.value!==undefined);
    const control=numberControl(row[key],min,max,1,value=>row[key]=value,{"aria-label":label});
    // The page draws this record - the draw point's marker on its grid, a cell in a
    // table, a route on the map - so a committed edit has to rebuild it. Typing
    // alone changed the stored number and left the drawing where it was, which is
    // why a draw point's dot did not move when its X was edited. The rebuild waits
    // for the change, not every keystroke, so the field keeps focus while typing.
    control.addEventListener("change",()=>{refresh();shell.refresh()});
    return sourceControl(control,()=>row[key],vanilla?.[key],refs,value=>{row[key]=Number(value);refresh();shell.refresh()})
  }
  // Where a signed world coordinate lands on the map image: 2048 stored units
  // to a block, on the 128 by 96 grid the draw points use, centred on the
  // origin. codex/ff8/world-terrain.md holds the evidence for the conversion.
  function worldMapFraction(x, z){
    return {x:(Number(x)/2048+64)/128, y:(Number(z)/2048+48)/96};
  }
  function worldColorHex(value){return `#${(value||[0,0,0]).map(channel=>Math.max(0,Math.min(255,Number(channel)||0)).toString(16).padStart(2,"0")).join("")}`}
  function worldColor(row,key,label){const vanilla=worldRow(state.vanilla,row.kind,row.id),refs=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:worldRow(state.referenceData[reference.id],row.kind,row.id)?.[key]})).filter(entry=>entry.value!==undefined),apply=value=>{const hex=Array.isArray(value)?worldColorHex(value):String(value);if(!/^#[0-9a-f]{6}$/i.test(hex))return;row[key]=[1,3,5].map(offset=>parseInt(hex.slice(offset,offset+2),16))},control=el("input",{type:"color",value:worldColorHex(row[key]),"aria-label":label,onchange:event=>{apply(event.target.value);rerenderWorldMap();shell.refresh()}});return sourceControl(control,()=>row[key],vanilla?.[key],refs,apply,worldColorHex)}
  // The shared full-cell layout gives this visual value its dimensions. The
  // label repeats the colours for readers who cannot see the gradient.
  function worldSkySwatch(row){
    const colors=[row.skyTop,row.skyCenter,row.skyBottom].map(worldColorHex);
    return el("span",{class:"world-sky-swatch",
      "aria-label":`Sky gradient for record ${row.id}: top ${colors[0]}, centre ${colors[1]}, bottom ${colors[2]}`,
      style:"display:block;width:100%;align-self:stretch;border-radius:0;"
        +`background:linear-gradient(to bottom,${colors[0]},${colors[1]},${colors[2]})`});
  }
  function railPointNumber(row,point,key){const find=dataset=>worldRow(dataset,"railTrack",row.id)?.points?.[point.id]?.[key],refs=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:find(state.referenceData[reference.id])})).filter(entry=>entry.value!==undefined),update=value=>point[key]=Number(value);return sourceControl(numberControl(point[key],-2147483648,2147483647,1,update,{"aria-label":`Track ${row.id} point ${point.id} ${key.toLocaleUpperCase()}`}),()=>point[key],find(state.vanilla),refs,update)}
  function railTrackDetail(row,prefs){
    const vanilla=worldRow(state.vanilla,"railTrack",row.id),refs=key=>state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:worldRow(state.referenceData[reference.id],"railTrack",row.id)?.[key]})).filter(entry=>entry.value!==undefined),choices=row.points.map(point=>({value:point.id,name:`Point ${point.id}`})),stop=(key,label)=>{const control=selectControl(row[key],choices,value=>row[key]=value);control.setAttribute("aria-label",label);return sourceControl(control,()=>row[key],vanilla?.[key],refs(key),value=>row[key]=Number(value),value=>`Point ${value}`)},points=columnList({rows:row.points,key:point=>point.id,class:"rail-point-table ff8-record-list",editable:true,template:"70px repeat(3,minmax(110px,1fr))",columns:[{key:"id",label:"POINT",numberedId:true,sortable:false,render:point=>point.id},{key:"x",label:"X",help:"X world coordinate of this route point. Changing it moves the point.",numeric:true,sortable:false,render:point=>railPointNumber(row,point,"x")},{key:"y",label:"Y",help:"Y world coordinate of this route point. Changing it moves the point.",numeric:true,sortable:false,render:point=>railPointNumber(row,point,"y")},{key:"z",label:"Z",help:"Z world coordinate of this route point. Changing it moves the point.",numeric:true,sortable:false,render:point=>railPointNumber(row,point,"z")}]});
    return sharedDetail({...row,name:`TRAIN TRACK ${row.id}`},prefs,[detailSection({title:"TRAIN STOPS",body:[detailField({label:"STOP 1",help:infoHelp("Together with Stop 2, this keypoint defines one endpoint of the rail route used by this train track."),control:stop("trainStop1","Train stop 1")}),detailField({label:"STOP 2",help:infoHelp("Together with Stop 1, this keypoint defines the other endpoint of the rail route used by this train track."),control:stop("trainStop2","Train stop 2")})]}),detailSection({className:"rail-track-points",title:"KEYPOINTS",help:infoHelp("Ordered points that define this train route. X, Y, and Z are stored world coordinates. Move points to change the route; the number of points remains fixed."),body:[points]})],"world-map-detail world-rail");
  }
  const worldTexturePalettes={};
  function worldTextureDataset(){return state.activeSource==="mine"?"current":state.activeSource}
  function worldTextureDetail(row,prefs){
    const palette=Math.max(0,Math.min(row.paletteCount-1,Number(worldTexturePalettes[row.id]??0))),dataset=worldTextureDataset(),query=`dataset=${encodeURIComponent(dataset)}&palette=${palette}&v=${encodeURIComponent(row.sha256)}`,preview=el("img",{src:`/assets/world-textures/${row.id}.png?${query}`,alt:`${row.name}, palette ${palette+1}`}),paletteSelect=selectControl(palette,Array.from({length:row.paletteCount},(_,id)=>({value:id,name:`Palette ${id+1}`})),value=>{worldTexturePalettes[row.id]=value;rerenderWorldMap()}),upload=el("input",{type:"file",accept:".tim,application/octet-stream",hidden:true}),replace=el("button",{type:"button",disabled:state.activeSource!=="mine",onclick:()=>upload.click()},"Replace TIM"),pending=el("div",{class:"world-texture-pending"},row.timBase64?"Replacement selected; Save applies it.":"No pending replacement."),exportLink=el("a",{href:`/assets/world-textures/${row.id}.tim?dataset=${encodeURIComponent(dataset)}`,download:`world-texture-${row.id+1}.tim`},"Export TIM");
    paletteSelect.setAttribute("aria-label",`${row.name} preview palette`);upload.onchange=async event=>{const file=event.target.files?.[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{row.timBase64=String(reader.result).split(",",2)[1]||"";pending.textContent=`${file.name} selected; Save validates and applies it.`;shell.refresh()};reader.onerror=()=>showAlert({title:"Could not read TIM",message:"The selected TIM file could not be read."});reader.readAsDataURL(file);event.target.value=""};
    const metadata=LexeditorUI.controlGroup([
      {label:"Size",control:readonlyField(`${row.width} × ${row.height}`)},
      {label:"Depth",control:readonlyField(`${row.depth} bits`)},
      {label:"Palettes",control:readonlyField(row.paletteCount)}]);
    const controls=LexeditorUI.stack({fill:false},detailField({label:"Preview palette",help:infoHelp("Choose the colours used to display this indexed image. This changes only the preview."),control:paletteSelect}),metadata,LexeditorUI.actionRow(exportLink,replace,upload),pending);
    return sharedDetail(row,prefs,[detailSection({title:"World texture",body:LexeditorUI.tileGrid([LexeditorUI.figureGrid([{media:preview,caption:row.name}]),controls])})]);

  }
  // Packed block coordinates: FF8UltimateEditor/Cid/drawmapwidget.py.
  function worldDrawPosition(point){return {x:point.x&127,y:2*point.y+(point.x>>7)}}
  function worldDrawBytes(x,y){return {x:(x&127)|((y&1)<<7),y:y>>1}}
  // A click on the map, read back as what the record stores: a draw point is a
  // block of the 128 by 96 grid, and a field return is a world coordinate. These
  // are the other direction of the two conversions that put a marker on the map.
  function worldDrawBlock(point){return {x:Math.max(0,Math.min(127,Math.round(point.x*128))),
    y:Math.max(0,Math.min(95,Math.round(point.y*96)))}}
  function worldMapCoordinate(point){return {x:Math.round((point.x*128-64)*2048),
    z:Math.round((point.y*96-48)*2048)}}
  const worldVisualView={scale:1,x:0,y:0};
  function worldMapNavigation(panel,stage){
    const view=worldVisualView,apply=()=>{stage.style.transform=`translate(${view.x}px,${view.y}px) scale(${view.scale})`};apply();
    panel.addEventListener('wheel',event=>{
      event.preventDefault();event.stopPropagation();
      const box=panel.getBoundingClientRect(),ratio=box.width/panel.offsetWidth;
      const x=(event.clientX-box.left)/ratio-panel.clientWidth/2,y=(event.clientY-box.top)/ratio-panel.clientHeight/2;
      const next=Math.max(1,Math.min(8,view.scale*Math.exp(-event.deltaY*.0015))),factor=next/view.scale;
      view.x=x-(x-view.x)*factor;view.y=y-(y-view.y)*factor;view.scale=next;
      if(next===1){view.x=0;view.y=0}apply();
    },{passive:false});
    let drag=null;
    panel.addEventListener('pointerdown',event=>{if(event.button!==1)return;event.preventDefault();panel.setPointerCapture(event.pointerId);drag={x:event.clientX,y:event.clientY}});
    panel.addEventListener('pointermove',event=>{if(!drag)return;const ratio=panel.getBoundingClientRect().width/panel.offsetWidth;view.x+=(event.clientX-drag.x)/ratio;view.y+=(event.clientY-drag.y)/ratio;drag={x:event.clientX,y:event.clientY};apply()});
    panel.addEventListener('pointerup',()=>{drag=null});panel.addEventListener('pointercancel',()=>{drag=null});
    panel.addEventListener('auxclick',event=>{if(event.button===1)event.preventDefault()});
    panel.addEventListener('dblclick',()=>{Object.assign(view,{scale:1,x:0,y:0});apply()});
  }
  // One world property, one description. The list column and the panel field for
  // the same value used to say different things - the column sent the reader to
  // the record for "coordinate-specific help" while the field explained the
  // value - so what a reader learned depended on where the pointer happened to
  // be. Both read this table now, and a fact either one had is kept.
  const worldPropertyHelp={
    region:{
      cell:"World grid cell number. Select it to edit its region code.",
      x:"Read-only X cell coordinate in the world-map grid.",
      y:"Read-only Y cell coordinate in the world-map grid.",
      regionId:"The code stored for this cell. Many cells can carry the same code. "
        +"It combines with the ground type of the terrain to choose the world-map encounter "
        +"rule and encounter group; the rules table is on the Encounters tab."},
    fieldReturn:{
      index:"Transition-location index, not a field map ID.",
      x:"X coordinate for this record. Changing it moves the stored world position.",
      y:"Y coordinate for this record. Changing it moves the stored world position.",
      z:"Z coordinate for this record. Changing it moves the stored world position."},
    worldToField:{
      x:"Where the player appears in the field, in the field's walkmesh units. Changing it moves the arrival point.",
      y:"Where the player appears in the field, on the walkmesh's other ground axis. Changing it moves the arrival point.",
      z:"The walkmesh triangle the player starts on. In every entry of the game it is the triangle under X and Y, so keep them together.",
      fieldId:"ID of the field the game loads from this position. The Field page lists the same IDs, so compare an entry against that list before changing it."},
    drawPoint:{
      drawId:"Identifier of this world draw point.",
      x:"Block column of the draw point's anchor: the low seven bits are the column and the "
        +"top bit is the odd or even row of the pair. X and Y together are the block id the "
        +"game matches against where the player stands.",
      y:"Block row of the anchor: twice this value plus the top bit of X. The game matches "
        +"this block id first, then the sub-ID, when the action button is pressed.",
      subId:"Several draw points can share one block. The game scans the block for the record "
        +"whose block id matches where the player stands and whose sub-ID equals the location "
        +"index there, then uses that record's number. Copy the sub-ID from a draw point that "
        +"already works in this block instead of inventing one."}};
  // Where a record sits on the world map, for a panel that has to show it. The
  // map carries the same markers and the same click the Map page uses, so a
  // point can be placed from the page that owns it.
  // One map, two sizes. `points` is asked for again after each placement, so the
  // marker in the panel and the marker in the magnifier both show where the
  // record is now.
  function worldLocationOptions(options){
    return {fill:false,columns:32,rows:24,ratio:4/3,label:options.label,
      image:`/assets/world-map.png?dataset=${encodeURIComponent(worldTextureDataset())}&v=${encodeURIComponent(state.data.world.sha256)}`,
      points:typeof options.points==="function"?options.points():options.points,
      cells:options.cells,select:options.select,place:options.place,
      readout:options.readout,note:options.note};
  }
  function worldLocationMap(options){
    // Unfilled, so the map takes the section's width and its own aspect ratio: a
    // filled map fills a panel, and a panel's sections have no height to fill.
    const map=LexeditorUI.imageMap({...worldLocationOptions(options),
      magnify:()=>worldLocationOptions(options)});
    worldMapNavigation(map,map.lexStage);
    return map;
  }
  function worldDrawPointDetail(row,prefs){
    const editable=()=>state.activeSource==='mine'&&document.documentElement.dataset.lexProjectReadonly!=='true';
    const fields=refresh=>[['x','X'],['y','Y'],['subId','SUB-ID']].map(([key,label])=>{
      const control=worldNumber(row,key,0,255,`Draw Point ${row.drawId} ${label}`,refresh);
      if(!editable())control.querySelectorAll('input,select,button').forEach(node=>node.disabled=true);
      return detailField({label,help:infoHelp(worldPropertyHelp.drawPoint[key]),control});
    });
    // The panel's map is a picture of where the point is. Clicking it opens the
    // large map, and the large map is where the point is placed: a stray click on
    // a panel must never move game data.
    const spec=()=>worldLocationOptions({
      label:`Set Draw Point ${row.drawId} position`,
      points:()=>{const at=worldDrawPosition(row);return at.y>=96?[]:[{x:at.x/128,y:at.y/96,selected:true,
        label:`Draw Point ${row.drawId}`}];},
      readout:point=>{const block=worldDrawBlock(point);return `block ${block.x}, ${block.y}`},
      place:editable()?point=>{const block=worldDrawBlock(point);Object.assign(row,worldDrawBytes(block.x,block.y));rerenderWorldMap();shell.refresh()}:null});
    const map=LexeditorUI.imageMap({...spec(),place:null,magnify:null});
    worldMapNavigation(map,map.lexStage);
    map.classList.add("world-draw-map");
    // The large map keeps the same click that places the point, and the panel
    // states the rule on its bar, as the shared finder does.
    // The marker is a button and stops its own click, so the map listens on the
    // way down: any click on the picture opens the large map.
    map.addEventListener("click",event=>{if(event.target.closest("input,a"))return;
      LexeditorUI.mapMagnifier({label:`Draw Point ${row.drawId}`,minSizes:[480,300],
        details:({refresh})=>detailPanel({title:`Draw Point ${row.drawId}`,
          body:detailSection({body:fields(()=>{rerenderWorldMap();refresh()})})}),
        magnify:()=>({...spec(),note:editable()
          ?`Click the map to place Draw Point ${row.drawId}, or edit its position on the right.`
          :'This source is read-only. Select an editable mod to move this draw point.'})});},true);

    // The list shows the draw point's own draw ID, so the panel does too.
    return sharedDetail({...row,id:row.drawId,name:`DRAW POINT ${row.drawId}`},prefs,[detailSection({className:"world-draw-position",help:infoHelp("Section 34 stores only this world Draw Point's X, Y, and sub-ID bytes. Its magic, quantity, and refill behavior live in FF8_EN.exe and are not invented here."),body:[LexeditorUI.tileGrid([map,LexeditorUI.stack({fill:false},...fields())],{columns:2,minWidth:300})]})],"world-map-detail world-draw-point");
  }
  function worldFieldReturnDetail(row,prefs){
    const editable=()=>state.activeSource==='mine'&&document.documentElement.dataset.lexProjectReadonly!=='true';
    const fields=refresh=>{
      const number=(key,label,minimum,maximum)=>{
        const control=worldNumber(row,key,minimum,maximum,`Field return ${row.id} ${label}`,refresh);
        if(!editable())control.querySelectorAll('input,select,button').forEach(node=>node.disabled=true);
        return control;
      };
      return [detailField({label:"X",help:infoHelp(worldPropertyHelp.fieldReturn.x),control:number("x","X",-2147483648,2147483647)}),
        detailField({label:"Y",help:infoHelp(worldPropertyHelp.fieldReturn.y),control:number("y","Y",-32768,32767)}),
        detailField({label:"Z",help:infoHelp("Where the player appears, north to south. Changing it moves this return point."),control:number("z","Z",-2147483648,2147483647)})];
    };
    // Like a draw point: the panel's map is a picture of where the player
    // returns. Clicking it opens the large map, and the large map is where
    // the point is placed - a click on the panel never moves game data
    // (Lexer, 2026-09-27).
    const spec=()=>worldLocationOptions({
      label:`Set field return ${row.id} position`,
      points:()=>{const at=worldMapFraction(row.x,row.z);
        return (row.x===0&&row.z===0)||at.x<0||at.x>1||at.y<0||at.y>1?[]
          :[{x:at.x,y:at.y,selected:true,label:`Field return ${row.id}`}];},
      readout:point=>{const at=worldMapCoordinate(point);return `x ${formatNumber(at.x)}, z ${formatNumber(at.z)}`},
      place:editable()?point=>{const at=worldMapCoordinate(point);row.x=at.x;row.z=at.z;rerenderWorldMap();shell.refresh()}:null});
    const map=LexeditorUI.imageMap({...spec(),place:null,magnify:null});
    worldMapNavigation(map,map.lexStage);
    map.addEventListener("click",event=>{if(event.target.closest("input,a"))return;
      LexeditorUI.mapMagnifier({label:`Field return ${row.id}`,minSizes:[480,300],
        details:({refresh})=>detailPanel({title:`Field return ${row.id}`,
          body:detailSection({body:fields(()=>{rerenderWorldMap();refresh()})})}),
        magnify:()=>({...spec(),note:editable()
          ?`Click the map to place field return ${row.id}, or edit its position on the right.`
          :'This source is read-only. Select an editable mod to move this return point.'})});},true);
    return sharedDetail({...row,name:`FIELD RETURN ${row.id}`},prefs,[
      detailSection({title:"FIELD → WORLD POSITION",help:infoHelp("Where the player appears on the world map after leaving a field by this exit. Click the map to open the large map and move the point. The number is the exit's own index, not a field ID."),body:[LexeditorUI.tileGrid([map,LexeditorUI.stack({fill:false},...fields(()=>rerenderWorldMap()),
        detailField({label:"UNRESOLVED WORD",help:infoHelp("What this value does is not known. It stays exactly as stored."),control:readonlyField(row.unknown)}))],{columns:2,minWidth:300})]})],"world-map-detail world-field-return")}
  function worldSkyDetail(row,prefs,titleContent=null,note=""){return sharedDetail({...row,name:`SKY RECORD ${row.id}`,...(titleContent?{titleContent}:{})},prefs,[detailSection({title:"WORLD POSITION",help:infoHelp("The record holds two world coordinates and then a fade distance, in the stored order X, Z, RANGE. The first two say where the zone applies; the third says how far its colours fade."),body:[detailField({label:"X",help:infoHelp("X coordinate for this record. Changing it moves the stored world position."),control:worldNumber(row,"x",-2147483648,2147483647,`Sky record ${row.id} X`)}),detailField({label:"RANGE",help:infoHelp("Fade distance in world units. The shipped records use round values - 16384, 24576, 40960 - which is how a distance reads rather than a coordinate. How the game fades between zones is not established."),control:worldNumber(row,"y",-2147483648,2147483647,`Sky record ${row.id} fade range`)}),detailField({label:"Z",help:infoHelp("World Z coordinate of this lighting zone. The zone applies around the point X, Z."),control:worldNumber(row,"z",-2147483648,2147483647,`Sky record ${row.id} Z`)})]}),detailSection({className:"world-sky-colors",title:"SKY AND AMBIENT COLOURS",help:infoHelp("OpenVIII proves five RGB triples in each section 33 record. Lexeditor preserves each unused fourth colour byte and the unresolved record tail."),body:[detailField({label:"SHADOWS",help:infoHelp("Ambient shadow colour for this world colour record. Choose a colour and test the result at this location."),control:worldColor(row,"shadows",`Sky record ${row.id} shadows colour`)}),detailField({label:"VEHICLES",help:infoHelp("Vehicle colour value stored in this world colour record."),control:worldColor(row,"vehicles",`Sky record ${row.id} vehicles colour`)}),detailField({label:"SKY TOP",help:infoHelp("Colour at the top of the sky gradient."),control:worldColor(row,"skyTop",`Sky record ${row.id} sky top colour`)}),detailField({label:"SKY CENTRE",help:infoHelp("Colour in the middle of the sky gradient."),control:worldColor(row,"skyCenter",`Sky record ${row.id} sky centre colour`)}),detailField({label:"SKY BOTTOM",help:infoHelp("Colour at the bottom of the sky gradient."),control:worldColor(row,"skyBottom",`Sky record ${row.id} sky bottom colour`)})]})],"world-map-detail world-sky-detail",note)}
  function worldSegmentDetail(row){
    const region=worldRow(state.data,"region",row.id),blocks=LexeditorUI.tileGrid(row.blocks.map(block=>detailSection({title:`Block ${block.id}`,body:[detailField({label:"Polygons",control:readonlyField(block.polygonCount)}),detailField({label:"Vertices",control:readonlyField(block.vertexCount)})]})));
    // One world-map cell, shown for its terrain. The word "segment" belongs to
    // the WMX file, which stores one 0x9000-byte segment per cell; the thing a
    // reader selects here is a cell of the map, and the Regions page lists the
    // same cells for the region code each one carries.
    const title=hoverable({content:`WORLD MAP CELL ${row.id}`,targetType:"regions",targetId:row.id,
      targetLabel:`world map cell ${row.id}`,
      activate:()=>{state.worldTab="regions";state.selected.world=row.id;state.worldMapPoint=null;rerenderWorldMap()}});
    return sharedDetail({...row,name:`WORLD MAP CELL ${row.id}`,titleContent:title},null,[
      detailSection({title:"MAP POSITION",body:[detailField({label:"X",help:infoHelp(worldPropertyHelp.region.x),control:readonlyField(row.x)}),detailField({label:"Y",help:infoHelp(worldPropertyHelp.region.y),control:readonlyField(row.y)}),detailField({label:"REGION CODE",help:infoHelp(worldPropertyHelp.region.regionId),control:worldNumber(region,"regionId",0,255,`World map cell ${row.id} region code`)})]}),
      detailSection({title:"WMX GEOMETRY",help:infoHelp("Deling proves the group ID at the start of each 0x9000-byte WMX segment, which holds one cell's terrain. Lexeditor changes only that value and preserves all polygon topology and unknown bytes."),body:[detailField({label:"GROUP ID",help:infoHelp("Stored geometry group for this cell. Its full effect in the game is not established. This is not the encounter group; use the Rules page on the Encounters tab to change battles."),control:worldNumber(row,"groupId",0,4294967295,`World map cell ${row.id} group ID`)}),detailField({label:"POLYGONS",help:infoHelp("Number of terrain faces in this cell. This count is read-only."),control:readonlyField(row.polygonCount)}),detailField({label:"GROUND TYPES",help:infoHelp("Terrain codes used by the polygons in this cell. A ground code and the region code select an encounter rule on the Encounters tab. These are stored codes, not counts."),control:el("span",{class:"world-ground-list"},row.groundTypes.join(", ")||"None")})]}),
      detailSection({title:"BLOCKS",help:infoHelp("Each world-map cell holds 16 smaller terrain blocks. Polygons are the faces that form the terrain; vertices are the points at their corners. These counts describe the stored geometry."),body:[blocks]})
    ],"world-map-detail world-segment-detail");
  }
  function renderWorldVisual(){
    const segments=state.data.world.rows.filter(row=>row.kind==="worldSegment").slice(0,32*24);
    const selected=Math.max(0,Math.min(segments.length-1,Number(state.selected.world??0))),row=segments[selected];state.selected.world=selected;
    if(!row)return LexeditorUI.detailNote("World geometry is unavailable.");
    // What the map shows on the right: the cell the reader last picked, or a draw
    // point picked from the map itself. Each panel's title leads to the page that
    // owns the record.
    const picked=state.worldMapPoint==null?null:state.data.world.drawPoints.find(point=>point.id===state.worldMapPoint);
    const pickedSky=state.worldMapSky==null?null:state.data.world.rows.find(row=>row.kind==="skyColor"&&row.id===state.worldMapSky);
    const cells=segments.map(segment=>({id:segment.id,label:`Select world map cell ${segment.id}`,selected:!picked&&!pickedSky&&segment.id===selected,
      title:`Cell ${segment.id} · region ${worldRow(state.data,"region",segment.id)?.regionId??"?"} · group ${segment.groupId}`}));
    const points=state.data.world.drawPoints.filter(point=>point.x!==0||point.y!==0).map(point=>{
      const position=worldDrawPosition(point);if(position.y>=96)return null;
      return {x:position.x/128,y:position.y/96,selected:point.id===state.worldMapPoint,
        label:`Select draw point ${point.drawId}`,
        activate:()=>{state.worldMapPoint=point.id;state.worldMapSky=null;rerenderWorldMap()}};
    }).filter(Boolean);
    const skyRows=state.data.world.rows.filter(row=>row.kind==="skyColor");
    for(const record of skyRows){
      if(record.x===0&&record.z===0)continue;
      const at=worldMapFraction(record.x,record.z);
      if(at.x<0||at.x>1||at.y<0||at.y>1)continue;
      points.push({x:at.x,y:at.y,selected:state.worldMapSky===record.id,className:"world-sky-point",
        label:`Select sky record ${record.id}`,
        activate:()=>{state.worldMapSky=record.id;state.worldMapPoint=null;rerenderWorldMap()}});
    }
    const map=LexeditorUI.imageMap({columns:32,rows:24,ratio:4/3,label:"FF8 world map",cells,points,
      image:`/assets/world-map.png?dataset=${encodeURIComponent(worldTextureDataset())}&v=${encodeURIComponent(state.data.world.sha256)}`,
      readout:point=>{
        const cell=segments[point.row*32+point.column];
        if(!cell)return "";
        return `cell ${point.column}, ${point.row} · id ${cell.id} · region `
          +`${worldRow(state.data,"region",cell.id)?.regionId??"?"} · group ${cell.groupId}`;},
      select:id=>{state.worldMapPoint=null;state.worldMapSky=null;state.selected.world=id;rerenderWorldMap()}});
    worldMapNavigation(map,map.lexStage);
    return LexeditorUI.panelLayout([detailPanel({heading:false,className:"ff8-world-map-panel",body:map}),
      pickedSky?worldSkyDetail(pickedSky,null,worldSkyMapTitle(pickedSky),`World ${formatNumber(pickedSky.x)}, ${formatNumber(pickedSky.z)} · fade ${formatNumber(pickedSky.y)}`):picked?worldMapPointPreview(picked):worldSegmentDetail(row)],"world-map",
      {layoutKey:"ff8-world-map",defaultSizes:[1.6,1]});
  }
  // A sky zone picked on the map is the same record the Sky Colours page
  // shows, so it draws that page's panel rather than a shorter copy. Only the
  // title differs: here it leads to the page that owns the record.
  function worldSkyMapTitle(row){
    return hoverable({content:`SKY RECORD ${row.id}`,targetType:"skyColors",targetId:row.id,
      targetLabel:`sky record ${row.id}`,
      activate:()=>{state.worldTab="skyColors";state.selected.world=row.id;state.worldMapSky=null;
        state.pages.world=0;state.filters.world="";state.modOnly=false;rerenderWorldMap()}});
  }
  // The Map page's panel for a draw point picked from the map: where it is, the
  // way to its own page through the title, and the reminder that what it gives is
  // not in this file.
  function worldMapPointPreview(row){
    const position=worldDrawPosition(row);
    const title=hoverable({content:`DRAW POINT ${row.drawId}`,targetType:"drawPoints",targetId:row.drawId,
      targetLabel:`draw point ${row.drawId}`,
      activate:()=>{state.worldTab="drawPoints";state.selected.world=row.id;state.worldMapPoint=null;
        state.pages.world=0;state.filters.world="";state.modOnly=false;rerenderWorldMap()}});
    return detailPanel({title,className:"world-map-detail world-draw-point",meta:`Block ${position.x}, ${position.y}`,
      help:"Where this draw point sits on the world map. Its spell, its refill and whether it gives a high yield are set in the game's program, and this editor does not change them yet.",
      body:[detailSection({title:"WORLD POSITION",
        help:infoHelp("The block this draw point is anchored to. The game matches this block and the sub-ID when the action button is pressed."),
        body:[detailField({label:"X",help:infoHelp(worldPropertyHelp.drawPoint.x),control:worldNumber(row,"x",0,255,`Draw point ${row.drawId} X`)}),
          detailField({label:"Y",help:infoHelp(worldPropertyHelp.drawPoint.y),control:worldNumber(row,"y",0,255,`Draw point ${row.drawId} Y`)}),
          detailField({label:"SUB-ID",help:infoHelp(worldPropertyHelp.drawPoint.subId),control:worldNumber(row,"subId",0,255,`Draw point ${row.drawId} sub-ID`)})]})]});
  }
  function worldDetail(row,prefs){
    if(row.kind==="region")return sharedDetail({...row,name:`WORLD MAP CELL ${row.id}`},prefs,[LexeditorUI.tileGrid([
    detailSection({className:"world-region-position",title:"WORLD MAP",
      help:infoHelp("The cell this record carries a region code for. The Map page shows the same grid."),
      body:[worldLocationMap({label:`World map cell ${row.id}`,
        cells:[{id:row.id,column:row.x,row:row.y,label:`Cell ${row.id}`,selected:true,title:`Cell ${row.id} · region ${row.regionId}`}],
        select:id=>{state.selected.world=id;rerenderWorldMap()}})]}),
    detailSection({title:"REGION CODE",help:infoHelp("This is the same world-map cell the Map page shows; this page lists the cells for the code each one carries."),body:[detailField({label:"X",help:infoHelp("Read-only X cell coordinate in the world-map grid."),control:readonlyField(row.x)}),detailField({label:"Y",help:infoHelp("Read-only Y cell coordinate in the world-map grid."),control:readonlyField(row.y)}),detailField({label:"REGION CODE",help:infoHelp(worldPropertyHelp.region.regionId),control:worldNumber(row,"regionId",0,255,"World map cell region code")})]})],{columns:2,minWidth:300})],"world-map-detail");
    if(row.kind==="railTrack")return railTrackDetail(row,prefs);
    if(row.kind==="worldTexture")return worldTextureDetail(row,prefs);
    if(row.kind==="drawPoint")return worldDrawPointDetail(row,prefs);
    if(row.kind==="fieldReturn")return worldFieldReturnDetail(row,prefs);
    if(row.kind==="skyColor")return worldSkyDetail(row,prefs);
    // Encounter rules and groups are records of this file too, but they are
    // edited on the Encounters tab; nothing on this tab selects them.
    return LexeditorUI.notice({message:`This world record kind (${row.kind}) is not edited on this page.`});
  }
  // The world-to-field table: the entries that send a world position into a
  // field, one per place. It is a file of its own (main.fs, wm2field.tbl), so it
  // is read and saved through its own endpoints while sitting on this tab.
  function worldToFieldName(fieldId){
    const field=state.data.fields.rows.find(row=>Number(row.mapId)===Number(fieldId));
    return field?.name||`Field ${fieldId}`;
  }
  function worldToFieldNumber(row,key,label,minimum,maximum){
    const vanilla=rowOf(state.vanilla,"wm2field",row.id);
    const rebuild=()=>{renderWorldMap();shell.refresh()};
    const control=numberControl(row[key],minimum,maximum,1,value=>{row[key]=value;rebuild()},
      {"aria-label":label});
    control.addEventListener("change",rebuild);
    return sourceControl(control,()=>row[key],vanilla?.[key],
      referenceValues("wm2field",row.id,value=>value?.[key]),value=>{row[key]=Number(value);rebuild()},
      value=>formatNumber(value));
  }
  // The table stores where the player arrives inside the field: X and Y on
  // the field's walkmesh and the triangle under them (all 72 entries fall in
  // their own triangle; codex/ff8/wm2field.md). The picture is the field's
  // own background with that point on it.
  const worldToFieldPictures=new Map();
  function worldToFieldHeight(triangle,x,y){
    const [a,b,c]=triangle.vertices,det=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y);
    if(!det)return (a.z+b.z+c.z)/3;
    const u=((b.y-c.y)*(x-c.x)+(c.x-b.x)*(y-c.y))/det,v=((c.y-a.y)*(x-c.x)+(a.x-c.x)*(y-c.y))/det;
    return u*a.z+v*b.z+(1-u-v)*c.z;
  }
  function drawWorldToFieldPoint(row,field,canvas,geometry){
    const ctx=canvas.getContext("2d");if(!ctx||!geometry)return;
    canvas.width=geometry.width;canvas.height=geometry.height;
    const camera=field.camera?.cameras?.[0],triangle=field.walkmesh?.triangles?.find(entry=>entry.id===Number(row.z));
    if(!camera)return;
    const at=vertex=>{const projected=fieldProject(camera,vertex);return projected&&{x:projected.x+geometry.left,y:projected.y+geometry.top}};
    if(triangle){const corners=triangle.vertices.map(at);if(corners.every(Boolean)){
      ctx.beginPath();corners.forEach((point,index)=>ctx[index?"lineTo":"moveTo"](point.x,point.y));ctx.closePath();
      ctx.fillStyle="rgba(255,144,0,.3)";ctx.fill();ctx.strokeStyle="#ff9000";ctx.lineWidth=2;ctx.stroke()}}
    const z=triangle?worldToFieldHeight(triangle,Number(row.x),Number(row.y)):0,point=at({x:Number(row.x),y:Number(row.y),z});
    if(!point)return;
    ctx.save();ctx.shadowColor="#ff4040";ctx.shadowBlur=10;ctx.beginPath();ctx.arc(point.x,point.y,6,0,Math.PI*2);
    ctx.fillStyle="#ff4040";ctx.fill();ctx.lineWidth=2;ctx.strokeStyle="#ffffff";ctx.stroke();ctx.restore();
  }
  function worldToFieldPicture(row,field){
    if(!field)return LexeditorUI.noImage();
    const image=el("img",{class:"field-background-image lex-overlay-base",alt:`${field.name} background`}),
      canvas=el("canvas",{class:"field-overlay-canvas lex-overlay-layer","aria-hidden":"true"}),
      stack=el("div",{class:"field-preview-stack lex-overlay-stack world-to-field-picture",style:"visibility:hidden"},image,canvas);
    const dataset=state.activeSource==="mine"?"current":state.activeSource,cacheKey=`${dataset}:${field.key}`;
    const show=picture=>{image.onload=()=>{stack.style.visibility=""};image.src=picture.url;drawWorldToFieldPoint(row,field,canvas,picture.geometry)};
    (async()=>{
      // The walkmesh arrives with the field (a read another page started is
      // awaited too); render again so the triangle control takes its real
      // upper bound.
      if(!field._loaded){await ensureFieldDetail(field);
        for(let wait=0;field._loading&&wait<600;wait++)await new Promise(resolve=>setTimeout(resolve,100));
        if(!stack.isConnected)return;
        if(field._loaded&&state.worldTab==="worldToField"){renderWorldMap();return}}
      if(field._error||!field.background?.tiles?.length){stack.replaceWith(LexeditorUI.noImage());return}
      let picture=worldToFieldPictures.get(cacheKey);
      if(!picture){
        const view=fieldBackgroundPreviewState(field),states=view.states.map(value=>{const [parameter,stateValue]=value.split(":").map(Number);return{parameter,state:stateValue}});
        const [response,geometry]=await Promise.all([fetch("/api/field/background-preview",post({map:field.key,dataset,edits:[],activeStates:states,enabledLayers:view.layers,hideBackground:false})),
          api("/api/field/background-geometry",post({map:field.key,dataset,edits:[]})).catch(()=>null)]);
        if(!response.ok){stack.replaceWith(LexeditorUI.noImage());return}
        picture={url:URL.createObjectURL(await response.blob()),geometry};
        worldToFieldPictures.set(cacheKey,picture);
      }
      show(picture);
    })().catch(error=>{console.warn("world-to-field picture",error);stack.replaceWith(LexeditorUI.noImage())});
    return stack;
  }
  function worldToFieldDetail(row,prefs){
    const field=state.data.fields.rows.find(entry=>Number(entry.mapId)===Number(row.fieldId));
    const triangles=field?._loaded?field.walkmesh?.triangles?.length:0;
    const title=field?hoverable({content:field.name,targetType:"fields",targetId:field.id,targetLabel:field.name,
      activate:()=>{state.selected.fields=field.id;state.filters.fields="";navigate("fields")}}):`Field ${row.fieldId}`;
    return sharedDetail({...row,name:field?.name||`Field ${row.fieldId}`,titleContent:title},prefs,[
      detailSection({title:"ARRIVAL IN THE FIELD",help:infoHelp("Where the player appears in the field when this entry takes them in from the world map. The picture marks the point and its walkmesh triangle."),body:[
        LexeditorUI.tileGrid([worldToFieldPicture(row,field),LexeditorUI.stack({fill:false},
          detailField({label:"X",help:infoHelp(worldPropertyHelp.worldToField.x),control:worldToFieldNumber(row,"x",`World to field ${row.id} X`,-32768,32767)}),
          detailField({label:"Y",help:infoHelp(worldPropertyHelp.worldToField.y),control:worldToFieldNumber(row,"y",`World to field ${row.id} Y`,-32768,32767)}),
          detailField({label:"TRIANGLE",help:infoHelp(worldPropertyHelp.worldToField.z),control:worldToFieldNumber(row,"z",`World to field ${row.id} Z`,0,triangles?triangles-1:65535)}),
          detailField({label:"FIELD ID",help:infoHelp(worldPropertyHelp.worldToField.fieldId),control:worldToFieldNumber(row,"fieldId",`World to field ${row.id} field ID`,0,65535)}),
          detailField({label:"PRESERVED",help:infoHelp("What these values do is not known. They stay exactly as stored."),control:readonlyField(`1 byte · ${wm2fieldReserved} bytes, preserved`)}))],{columns:2,minWidth:300})]})],
      "world-map-detail world-to-field");
  }
  const wm2fieldReserved=15;
  function renderWorldToField(){
    const rows=state.data.wm2field.rows,query=state.filters.wm2field.trim().toLocaleLowerCase(),
      matching=rows.filter(row=>!query||JSON.stringify(row).toLocaleLowerCase().includes(query)),
      [sortKey,sortDirection]=state.sorts.wm2field,
      visible=[...matching].sort((left,right)=>sortDirection*String(rowSortValue(left,sortKey)).localeCompare(String(rowSortValue(right,sortKey)),undefined,{numeric:true,sensitivity:"base"}));
    delete state.columnPrefs.wm2field;
    return showPaged("wm2field",visible,[
      {key:"id",label:"ENTRY"},
      {key:"fieldId",label:"FIELD",help:worldPropertyHelp.worldToField.fieldId,render:row=>worldToFieldName(row.fieldId)},
      {key:"x",label:"X",help:worldPropertyHelp.worldToField.x},
      {key:"y",label:"Y",help:worldPropertyHelp.worldToField.y},
      {key:"z",label:"TRIANGLE",help:worldPropertyHelp.worldToField.z}],
      worldToFieldDetail,"74px minmax(150px,1fr) repeat(3,minmax(70px,1fr))",
      {noun:"world to field entries"},false);
  }
  function renderWorldMapContent(mount=true){
    const tabsData=[{id:"map",label:"Map",help:"The world map, and nothing else on the panel. Click a cell to inspect its terrain geometry and its region code, or a red dot to inspect a draw point; the corner shows what the pointer is over. Each panel's title opens the page that owns it. Scroll to zoom, drag with the middle mouse button to pan, and double-click to fit the map."},{id:"regions",label:"Regions",help:"The same world-map cells the Map page shows, listed for the region code each one carries. The rules table on the Encounters tab matches that code with the ground type to choose a battle group. Changing a code can change which battles occur there."},{id:"fieldReturns",label:"Field → World",help:"Set world positions used when leaving a field location. The record index identifies a transition location, not a field map ID. Edit coordinates to move the arrival point; the unused word is preserved."},{id:"worldToField",label:"World → Field",help:"Where the player arrives in a field when they enter it from the world map: the field, and the point and walkmesh triangle they start on. The table does not store a world-map position; which entry the game uses is decided by its own code, so test a change in the game."},{id:"drawPoints",label:"Draw Points",help:"Move world draw points. Click the placement grid or edit the packed position bytes. What a draw point gives - its spell, whether it refills and whether it draws a high yield - is stored in FF8_EN.exe, not in this file, so this page changes only where the point is."},{id:"skyColors",label:"Sky Colours",help:"Edit sky gradients and ambient colours at stored world positions. Each record holds two world coordinates and a fade distance, then two light colours and three fog colours. How the game chooses and blends zones is not established, so test any change in the game."},{id:"rails",label:"Train Tracks",help:"Edit the points that form a train route and select its two stop points. Coordinates move the route; stop values select points already in that route."},{id:"textures",label:"World Textures",help:"Preview or replace world texture images. Choose a palette for the preview. Export TIM to edit the texture in a compatible tool, then Replace TIM and Save. Palette selection only changes the preview."}],wrap=content=>{const tabs=subtabBar({className:"ff8-world-tabs",tabs:tabsData,active:state.worldTab,label:"World",change:value=>{state.worldTab=value;state.pages.world=0;state.selected.world=null;rerenderWorldMap()}}),root=LexeditorUI.stack(tabs,content);if(mount)$("#main").replaceChildren(root);return root};
    if(state.worldTab==="map"){const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;return wrap(renderWorldVisual())}
    if(state.worldTab==="worldToField")return wrap(renderWorldToField());
    const kind={regions:"region",fieldReturns:"fieldReturn",drawPoints:"drawPoint",skyColors:"skyColor",rails:"railTrack",textures:"worldTexture"}[state.worldTab],rows=state.data.world.rows.filter(row=>row.kind===kind),query=state.filters.world.trim().toLocaleLowerCase(),matching=rows.filter(row=>!query||JSON.stringify(row).toLocaleLowerCase().includes(query)),[sortKey,sortDirection]=state.sorts.world,visible=[...matching].sort((left,right)=>sortDirection*String(rowSortValue(left,sortKey)).localeCompare(String(rowSortValue(right,sortKey)),undefined,{numeric:true,sensitivity:"base"}));
    const columns=kind==="region"?[{key:"id",label:"CELL",help:worldPropertyHelp.region.cell},{key:"x",label:"X",help:worldPropertyHelp.region.x},{key:"y",label:"Y",help:worldPropertyHelp.region.y},{key:"regionId",label:"REGION CODE",help:worldPropertyHelp.region.regionId}]:kind==="fieldReturn"?[{key:"id",label:"INDEX",help:worldPropertyHelp.fieldReturn.index},{key:"x",label:"X",help:worldPropertyHelp.fieldReturn.x},{key:"y",label:"Y",help:worldPropertyHelp.fieldReturn.y},{key:"z",label:"Z",help:worldPropertyHelp.fieldReturn.z}]:kind==="drawPoint"?[{key:"drawId",label:"DRAW ID",help:worldPropertyHelp.drawPoint.drawId},{key:"x",label:"X",help:worldPropertyHelp.drawPoint.x},{key:"y",label:"Y",help:worldPropertyHelp.drawPoint.y},{key:"subId",label:"SUB-ID",help:worldPropertyHelp.drawPoint.subId}]:kind==="skyColor"?[{key:"id",label:"RECORD",help:"Identifier of this sky colour record."},{key:"skyTop",label:"SKY GRADIENT",grow:1,cellClass:"lex-cell-fill",help:"Preview of the top, centre, and bottom sky colours.",render:worldSkySwatch}]:kind==="railTrack"?[{key:"id",label:"TRACK",help:"Identifier of the train route."},{key:"pointCount",label:"POINTS",help:"Number of points forming the route."},{key:"trainStop1",label:"STOP 1",help:"First stop point in this route."},{key:"trainStop2",label:"STOP 2",help:"Second stop point in this route."}]:[{key:"id",label:"TEXTURE",help:"Identifier of the world texture."},{key:"name",label:"ASSET",help:"Name of the texture image record."},{key:"paletteCount",label:"PALETTES",help:"Number of colour tables in this indexed image."},{key:"depth",label:"BPP",help:"Bits per pixel, which determines how pixel indices refer to palette colours."}];
    delete state.columnPrefs.world;
    const content=showPaged("world",visible,columns,worldDetail,kind==="skyColor"?"90px minmax(180px,1fr)":"90px minmax(80px,1fr) minmax(80px,1fr) minmax(80px,1fr)",{defaultSplit:43,minLeft:360,minRight:460,fixedTemplate:kind!=="skyColor"},false);
    return wrap(content);
  }
  function renderWorldMap(){return renderWorldMapContent(true)}

  function refineRow(dataset,table,id){return dataset?.refine?.rows?.find(row=>row.table===table&&Number(row.id)===Number(id))}
  function refineReferences(row,field){return state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:refineRow(state.referenceData[reference.id],row.table,row.id)?.[field]})).filter(entry=>entry.value!==undefined)}
  function refineChoice(type,value){return state.data.refine.choices[type]?.find(entry=>Number(entry.id)===Number(value))?.name??`${type} ${value}`}
  function setRefineEntity(row,side,value){row[`${side}Id`]=Number(value);row[`${side}Name`]=refineChoice(row[`${side}Type`],value);row.name=`${row.inputName} → ${row.outputName}`;shell.refresh()}
  function refineEntityControl(row,side){
    const type=row[`${side}Type`],field=`${side}Id`,set=value=>setRefineEntity(row,side,value),origin=()=>{state.refineTab=row.table;state.selected.refine=row.id;navigate("refine")},prompt=`Select the ${type} used as this recipe's ${side}.`;
    if(type==="item")return itemSearchControl(row[field],prompt,set,origin);
    if(type==="magic")return magicSearchControl(row[field],prompt,set,origin);
    return selectControl(row[field],state.data.refine.choices[type]||[],set);
  }
  function refineSource(control,row,field,apply,format){const vanilla=refineRow(state.vanilla,row.table,row.id);return sourceControl(control,()=>row[field],vanilla?.[field],refineReferences(row,field),apply,format,{internal:true})}
  function refineDetail(row,prefs){
    const text=LexeditorUI.textArea({rows:7,maxlength:600,"aria-label":`Displayed refine text for ${row.name}`,oninput:event=>{row.text=event.target.value;shell.refresh()}});text.value=row.text;
    const label=`${state.data.refine.tables.find(table=>table.id===row.table)?.name||row.table} ${row.id+1}`;
    const recipeFields=["input","output"].flatMap(side=>{
      const field=`${side}Id`,quantity=`${side}Quantity`,apply=value=>setRefineEntity(row,side,value);
      return [detailField({label:"",showType:false,pin:prefs?.pinButton(`${side}Name`,side==="input"?"Input":"Output"),control:refineSource(refineEntityControl(row,side),row,field,apply,value=>refineChoice(row[`${side}Type`],value))}),detailField({label:"",showType:false,pin:prefs?.pinButton(quantity,side==="input"?"Needed":"Received"),dataType:"INT",min:0,max:255,control:refineSource(numberControl(row[quantity],0,255,1,value=>{row[quantity]=value;shell.refresh()},{"aria-label":`${side} quantity for refine recipe`}),row,quantity,value=>{row[quantity]=Number(value);shell.refresh()})})];
    });
    return sharedDetail({...row,id:row.id+1,name:label},prefs,[
      el("div",{class:"lex-recipe-row"},
        LexeditorUI.quantityChoice(recipeFields[0],recipeFields[1]),
        el("span",{"aria-label":"produces"},"→"),
        LexeditorUI.quantityChoice(recipeFields[2],recipeFields[3])),
      detailField({label:hoverable({content:"Recipe text",targetType:"text",targetId:refineTextRecord(row).id,targetLabel:`recipe text for ${label}`,activate:()=>openRefineText(row)}),className:"lex-detail-field-stacked lex-text-editor",showType:false,pin:prefs?.pinButton("text","Recipe text"),help:infoHelp("Message shown in the game for this recipe. Line breaks here also appear in the game. Update it when you change the ingredients or quantities; it does not set the conversion itself."),control:refineSource(text,row,"text",value=>row.text=String(value??""))})
    ],"refine-detail");
  }
