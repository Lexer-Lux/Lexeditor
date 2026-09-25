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
  // The four header bytes of a formation, as ordinary properties: the name on
  // the left and a help bubble beside it. This row used the stacked part of the
  // shared row component, which puts the name over the box and, with no help
  // passed, leaves the property with no bubble at all - so the same kind of
  // value looked unlike every other property in the editor. Four property
  // rows in one pair of lanes, like the field pages use, because four parts
  // across one lane leaves the longest name - Secondary camera - clipped.
  const encounterHeaderFields=[
    ["Stage","Battle stage number for this formation. It selects the arena the battle is fought in, so two formations with the same stage fight in the same place."],
    ["Flags","Flag byte stored with this formation. Its effect on the battle is not established here, so Lexeditor shows it and saves it without interpretation."],
    ["Main camera","Main camera number stored with this formation. The game's use of this value is not established here."],
    ["Secondary camera","Second camera number stored with this formation. The game's use of this value is not established here."]];
  function encounterDetail(row,prefs){
    const formation=LexeditorUI.tileGrid(['stageId','flags','cameraMain','cameraSecondary'].map((key,index)=>detailField({
      label:encounterHeaderFields[index][0],
      help:infoHelp(encounterHeaderFields[index][1]),
      control:encounterSource(numberControl(row[key],0,255,1,value=>{row[key]=value;shell.refresh()}),row,value=>value?.[key],value=>{row[key]=Number(value);shell.refresh()})
    })),{columns:2});
    const source=(slot,key,control)=>{
      if(!slot.enabled&&key!=='enabled')for(const input of [control,...control.querySelectorAll('input,select,button')])
        if(input.matches('input,select,button'))input.disabled=true;
      return encounterSource(control,row,value=>value?.slots?.find(entry=>entry.slot===slot.slot)?.[key],value=>{slot[key]=value;if(key==='enabled')renderEncounters();shell.refresh()});
    };
    const table=columnList({rows:row.slots,key:slot=>slot.slot,editable:true,fill:true,
      'aria-label':'Formation enemies',columns:[
        {key:'slot',label:'Slot',width:'max-content',render:slot=>slot.slot+1},
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
  function worldNumber(row,key,min,max,label){
    const vanilla=worldRow(state.vanilla,row.kind,row.id),refs=state.references.map(reference=>({name:reference.name,
      shortName:reference.shortName,value:worldRow(state.referenceData[reference.id],row.kind,row.id)?.[key]}))
      .filter(entry=>entry.value!==undefined);
    const control=numberControl(row[key],min,max,1,value=>row[key]=value,{"aria-label":label});
    // The page draws this record - the draw point's marker on its grid, a cell in a
    // table, a route on the map - so a committed edit has to rebuild it. Typing
    // alone changed the stored number and left the drawing where it was, which is
    // why a draw point's dot did not move when its X was edited. The rebuild waits
    // for the change, not every keystroke, so the field keeps focus while typing.
    control.addEventListener("change",()=>{render();shell.refresh()});
    return sourceControl(control,()=>row[key],vanilla?.[key],refs,value=>{row[key]=Number(value);render();shell.refresh()})
  }
  function worldColorHex(value){return `#${(value||[0,0,0]).map(channel=>Math.max(0,Math.min(255,Number(channel)||0)).toString(16).padStart(2,"0")).join("")}`}
  function worldColor(row,key,label){const vanilla=worldRow(state.vanilla,row.kind,row.id),refs=state.references.map(reference=>({name:reference.name,shortName:reference.shortName,value:worldRow(state.referenceData[reference.id],row.kind,row.id)?.[key]})).filter(entry=>entry.value!==undefined),apply=value=>{const hex=Array.isArray(value)?worldColorHex(value):String(value);if(!/^#[0-9a-f]{6}$/i.test(hex))return;row[key]=[1,3,5].map(offset=>parseInt(hex.slice(offset,offset+2),16))},control=el("input",{type:"color",value:worldColorHex(row[key]),"aria-label":label,onchange:event=>{apply(event.target.value);rerenderWorldMap();shell.refresh()}});return sourceControl(control,()=>row[key],vanilla?.[key],refs,apply,worldColorHex)}
  function worldSkySwatch(row){return el("span",{class:"world-sky-swatch","aria-label":`Sky gradient for record ${row.id}`,style:`background:linear-gradient(to bottom,${worldColorHex(row.skyTop)},${worldColorHex(row.skyCenter)},${worldColorHex(row.skyBottom)})`})}
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
  function worldLocationMap(options){
    // Unfilled, so the map takes the section's width and its own aspect ratio: a
    // filled map fills a panel, and a panel's sections have no height to fill.
    const map=LexeditorUI.imageMap({fill:false,columns:32,rows:24,ratio:4/3,label:options.label,
      image:`/assets/world-map.png?dataset=${encodeURIComponent(worldTextureDataset())}&v=${encodeURIComponent(state.data.world.sha256)}`,
      points:options.points,cells:options.cells,select:options.select,place:options.place});
    worldMapNavigation(map,map.lexStage);
    return map;
  }
  function worldDrawPointDetail(row,prefs){
    // The world map itself, not a blank grid: the point sits where the map puts it,
    // and clicking the map moves it there.
    const position=worldDrawPosition(row),map=worldLocationMap({
      label:`Set Draw Point ${row.drawId} position`,
      points:position.y>=96?[]:[{x:position.x/128,y:position.y/96,selected:true,
        label:`Draw Point ${row.drawId}`}],
      place:point=>{Object.assign(row,worldDrawBytes(Math.max(0,Math.min(127,Math.round(point.x*128))),Math.max(0,Math.min(95,Math.round(point.y*96)))));rerenderWorldMap();shell.refresh()}});

    return sharedDetail({...row,name:`DRAW POINT ${row.drawId}`},prefs,[detailSection({className:"world-draw-position",title:"WORLD POSITION",help:infoHelp("Section 34 stores only this world Draw Point's X, Y, and sub-ID bytes. Its magic, quantity, and refill behavior live in FF8_EN.exe and are not invented here."),body:[LexeditorUI.tileGrid([map,LexeditorUI.stack({fill:false},el("p",{class:"world-draw-help"},"Click the map to place the point, or enter exact byte coordinates below."),detailField({label:"X",help:infoHelp(worldPropertyHelp.drawPoint.x),control:worldNumber(row,"x",0,255,`Draw Point ${row.drawId} X`)}),detailField({label:"Y",help:infoHelp(worldPropertyHelp.drawPoint.y),control:worldNumber(row,"y",0,255,`Draw Point ${row.drawId} Y`)}),detailField({label:"SUB-ID",help:infoHelp(worldPropertyHelp.drawPoint.subId),control:worldNumber(row,"subId",0,255,`Draw Point ${row.drawId} sub-ID`)}))],{columns:2,minWidth:300})]})],"world-map-detail world-draw-point");
  }
  function worldFieldReturnDetail(row,prefs){return sharedDetail({...row,name:`FIELD RETURN ${row.id}`},prefs,[detailSection({title:"FIELD → WORLD POSITION",help:infoHelp("OpenVIII proves this as one entry in wmset section 9's field-to-world coordinate table. The entry index is a transition-location index, not a field ID. Lexeditor preserves the unresolved fourth word."),body:[detailField({label:"X",help:infoHelp(worldPropertyHelp.fieldReturn.x),control:worldNumber(row,"x",-2147483648,2147483647,`Field return ${row.id} X`)}),detailField({label:"Y",help:infoHelp(worldPropertyHelp.fieldReturn.y),control:worldNumber(row,"y",-32768,32767,`Field return ${row.id} Y`)}),detailField({label:"Z",help:infoHelp("Z coordinate for this record. Changing it moves the stored world position."),control:worldNumber(row,"z",-2147483648,2147483647,`Field return ${row.id} Z`)}),detailField({label:"UNRESOLVED WORD",help:infoHelp("The final signed 16-bit word in this record has no proved gameplay name. It remains visible and byte-preserved, but cannot be edited as a guessed property."),control:readonlyField(row.unknown)})]})],"world-map-detail world-field-return")}
  function worldSkyDetail(row,prefs){return sharedDetail({...row,name:`SKY RECORD ${row.id}`},prefs,[detailSection({title:"WORLD POSITION",help:infoHelp("OpenVIII identifies these as the signed world coordinates for this sky and ambient colour record. The file stores them in X, Z, Y order; Lexeditor presents the world X, Y, Z order."),body:[detailField({label:"X",help:infoHelp("X coordinate for this record. Changing it moves the stored world position."),control:worldNumber(row,"x",-2147483648,2147483647,`Sky record ${row.id} X`)}),detailField({label:"Y",help:infoHelp("Y coordinate for this record. Changing it moves the stored world position."),control:worldNumber(row,"y",-2147483648,2147483647,`Sky record ${row.id} Y`)}),detailField({label:"Z",help:infoHelp("Z coordinate for this record. Changing it moves the stored world position."),control:worldNumber(row,"z",-2147483648,2147483647,`Sky record ${row.id} Z`)})]}),detailSection({className:"world-sky-colors",title:"SKY AND AMBIENT COLOURS",help:infoHelp("OpenVIII proves five RGB triples in each section 33 record. Lexeditor preserves each unused fourth colour byte and the unresolved record tail."),body:[detailField({label:"SHADOWS",help:infoHelp("Ambient shadow colour for this world colour record. Choose a colour and test the result at this location."),control:worldColor(row,"shadows",`Sky record ${row.id} shadows colour`)}),detailField({label:"VEHICLES",help:infoHelp("Vehicle colour value stored in this world colour record."),control:worldColor(row,"vehicles",`Sky record ${row.id} vehicles colour`)}),detailField({label:"SKY TOP",help:infoHelp("Colour at the top of the sky gradient."),control:worldColor(row,"skyTop",`Sky record ${row.id} sky top colour`)}),detailField({label:"SKY CENTRE",help:infoHelp("Colour in the middle of the sky gradient."),control:worldColor(row,"skyCenter",`Sky record ${row.id} sky centre colour`)}),detailField({label:"SKY BOTTOM",help:infoHelp("Colour at the bottom of the sky gradient."),control:worldColor(row,"skyBottom",`Sky record ${row.id} sky bottom colour`)})]})],"world-map-detail world-sky-detail")}
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
    const cells=segments.map(segment=>({id:segment.id,label:`Select world map cell ${segment.id}`,selected:!picked&&segment.id===selected,
      title:`Cell ${segment.id} · region ${worldRow(state.data,"region",segment.id)?.regionId??"?"} · group ${segment.groupId}`}));
    const points=state.data.world.drawPoints.filter(point=>point.x!==0||point.y!==0).map(point=>{
      const position=worldDrawPosition(point);if(position.y>=96)return null;
      return {x:position.x/128,y:position.y/96,selected:point.id===state.worldMapPoint,
        label:`Select draw point ${point.drawId}`,
        activate:()=>{state.worldMapPoint=point.id;rerenderWorldMap()}};
    }).filter(Boolean);
    const map=LexeditorUI.imageMap({columns:32,rows:24,ratio:4/3,label:"FF8 world map",cells,points,
      image:`/assets/world-map.png?dataset=${encodeURIComponent(worldTextureDataset())}&v=${encodeURIComponent(state.data.world.sha256)}`,
      readout:point=>{
        const cell=segments[point.row*32+point.column];
        if(!cell)return "";
        return `cell ${point.column}, ${point.row} · id ${cell.id} · region `
          +`${worldRow(state.data,"region",cell.id)?.regionId??"?"} · group ${cell.groupId}`;},
      select:id=>{state.worldMapPoint=null;state.selected.world=id;rerenderWorldMap()}});
    worldMapNavigation(map,map.lexStage);
    return LexeditorUI.panelLayout([detailPanel({heading:false,className:"ff8-world-map-panel",body:map}),
      picked?worldMapPointPreview(picked):worldSegmentDetail(row)],"world-map",
      {layoutKey:"ff8-world-map",defaultSizes:[1.6,1]});
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
      body:[detailSection({title:"WORLD POSITION",
        help:infoHelp("The block this draw point is anchored to. The game matches this block and the sub-ID when the action button is pressed."),
        body:[detailField({label:"X",help:infoHelp(worldPropertyHelp.drawPoint.x),control:worldNumber(row,"x",0,255,`Draw point ${row.drawId} X`)}),
          detailField({label:"Y",help:infoHelp(worldPropertyHelp.drawPoint.y),control:worldNumber(row,"y",0,255,`Draw point ${row.drawId} Y`)}),
          detailField({label:"SUB-ID",help:infoHelp(worldPropertyHelp.drawPoint.subId),control:worldNumber(row,"subId",0,255,`Draw point ${row.drawId} sub-ID`)})]}),
        LexeditorUI.detailNote("What this point gives - its spell, whether it refills and whether it draws a high yield - is stored in FF8_EN.exe, so it is not edited here. Open the Draw Points page to move the point on its own grid.")]});
  }
  function worldDetail(row,prefs){
    if(row.kind==="region")return sharedDetail({...row,name:`WORLD MAP CELL ${row.id}`},prefs,[LexeditorUI.tileGrid([
    detailSection({className:"world-region-position",title:"WORLD MAP",
      help:infoHelp("The cell this record carries a region code for. The Map page shows the same grid."),
      body:[worldLocationMap({label:`World map cell ${row.id}`,
        cells:[{id:row.id,label:`Cell ${row.id}`,selected:true,title:`Cell ${row.id} · region ${row.regionId}`}],
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
  function renderWorldMapContent(mount=true){
    const tabsData=[{id:"map",label:"Map",help:"The world map, and nothing else on the panel. Click a cell to inspect its terrain geometry and its region code, or a red dot to inspect a draw point; the corner shows what the pointer is over. Each panel's title opens the page that owns it. Scroll to zoom, drag with the middle mouse button to pan, and double-click to fit the map."},{id:"regions",label:"Regions",help:"The same world-map cells the Map page shows, listed for the region code each one carries. The rules table on the Encounters tab matches that code with the ground type to choose a battle group. Changing a code can change which battles occur there."},{id:"fieldReturns",label:"Field → World",help:"Set world positions used when leaving a field location. The record index identifies a transition location, not a field map ID. Edit coordinates to move the arrival point; the unused word is preserved."},{id:"drawPoints",label:"Draw Points",help:"Move world draw points. Click the placement grid or edit the packed position bytes. What a draw point gives - its spell, whether it refills and whether it draws a high yield - is stored in FF8_EN.exe, not in this file, so this page changes only where the point is."},{id:"skyColors",label:"Sky Colours",help:"Edit sky gradients and ambient colours at stored world positions. Select a record, change its position or colours, then test that area in the game."},{id:"rails",label:"Train Tracks",help:"Edit the points that form a train route and select its two stop points. Coordinates move the route; stop values select points already in that route."},{id:"textures",label:"World Textures",help:"Preview or replace world texture images. Choose a palette for the preview. Export TIM to edit the texture in a compatible tool, then Replace TIM and Save. Palette selection only changes the preview."}],wrap=content=>{const tabs=subtabBar({className:"ff8-world-tabs",tabs:tabsData,active:state.worldTab,label:"World",change:value=>{state.worldTab=value;state.pages.world=0;state.selected.world=null;rerenderWorldMap()}}),root=LexeditorUI.stack(tabs,content);if(mount)$("#main").replaceChildren(root);return root};
    if(state.worldTab==="map"){const toolbar=$("#toolbar");toolbar.replaceChildren();toolbar.hidden=true;return wrap(renderWorldVisual())}
    const kind={regions:"region",fieldReturns:"fieldReturn",drawPoints:"drawPoint",skyColors:"skyColor",rails:"railTrack",textures:"worldTexture"}[state.worldTab],rows=state.data.world.rows.filter(row=>row.kind===kind),query=state.filters.world.trim().toLocaleLowerCase(),matching=rows.filter(row=>!query||JSON.stringify(row).toLocaleLowerCase().includes(query)),[sortKey,sortDirection]=state.sorts.world,visible=[...matching].sort((left,right)=>sortDirection*String(rowSortValue(left,sortKey)).localeCompare(String(rowSortValue(right,sortKey)),undefined,{numeric:true,sensitivity:"base"}));
    const columns=kind==="region"?[{key:"id",label:"CELL",help:worldPropertyHelp.region.cell},{key:"x",label:"X",help:worldPropertyHelp.region.x},{key:"y",label:"Y",help:worldPropertyHelp.region.y},{key:"regionId",label:"REGION CODE",help:worldPropertyHelp.region.regionId}]:kind==="fieldReturn"?[{key:"id",label:"INDEX",help:worldPropertyHelp.fieldReturn.index},{key:"x",label:"X",help:worldPropertyHelp.fieldReturn.x},{key:"y",label:"Y",help:worldPropertyHelp.fieldReturn.y},{key:"z",label:"Z",help:worldPropertyHelp.fieldReturn.z}]:kind==="drawPoint"?[{key:"drawId",label:"DRAW ID",help:worldPropertyHelp.drawPoint.drawId},{key:"x",label:"X",help:worldPropertyHelp.drawPoint.x},{key:"y",label:"Y",help:worldPropertyHelp.drawPoint.y},{key:"subId",label:"SUB-ID",help:worldPropertyHelp.drawPoint.subId}]:kind==="skyColor"?[{key:"id",label:"RECORD",help:"Identifier of this sky colour record."},{key:"skyTop",label:"SKY GRADIENT",help:"Preview of the top, centre, and bottom sky colours.",render:worldSkySwatch}]:kind==="railTrack"?[{key:"id",label:"TRACK",help:"Identifier of the train route."},{key:"pointCount",label:"POINTS",help:"Number of points forming the route."},{key:"trainStop1",label:"STOP 1",help:"First stop point in this route."},{key:"trainStop2",label:"STOP 2",help:"Second stop point in this route."}]:[{key:"id",label:"TEXTURE",help:"Identifier of the world texture."},{key:"name",label:"ASSET",help:"Name of the texture image record."},{key:"paletteCount",label:"PALETTES",help:"Number of colour tables in this indexed image."},{key:"depth",label:"BPP",help:"Bits per pixel, which determines how pixel indices refer to palette colours."}];
    delete state.columnPrefs.world;
    const content=showPaged("world",visible,columns,worldDetail,kind==="skyColor"?"90px minmax(180px,1fr)":"90px repeat(3,minmax(80px,1fr))",{defaultSplit:43,minLeft:360,minRight:460},false);
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
      detailField({label:"Recipe text",className:"lex-detail-field-stacked",showType:false,pin:prefs?.pinButton("text","Recipe text"),help:infoHelp("Message shown in the game for this recipe. Line breaks here also appear in the game. Update it when you change the ingredients or quantities; it does not set the conversion itself."),control:refineSource(text,row,"text",value=>row.text=String(value??""))})
    ],"refine-detail");
  }
