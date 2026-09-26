"use strict";
const {el,columnList,detailPanel,detailSection,detailField,readonlyField,recordId,infoHelp,pagedListDetail,panelLayout,infoIcon}=LexeditorUI;
const $=selector=>document.querySelector(selector);
const TABS=[{id:"text",label:"Text"},{id:"scenes",label:"Areas"},{id:"worlds",label:"Worlds"},{id:"worldnav",label:"World Exits"},{id:"animations",label:"Tiles"},{id:"exits",label:"Area Exits"},{id:"treasure",label:"Treasure"},{id:"gameplay",label:"Gameplay"},{id:"palettes",label:"Palettes"}];
const FACING=[[0,"Up"],[1,"Down"],[2,"Left"],[3,"Right"]];
const KINDS=[["weapon","Weapon"],["armor","Armor"],["helmet","Helmet"],["accessory","Accessory"],["consumable","Consumable"],["item","Item"],["gold","Gold"]];
const state={tab:"text",source:"mine",busy:true,error:"",dashboard:null,dataMap:{rows:[]},changes:[],language:"en",textFiles:[],textPath:"",text:{rows:[]},paletteFiles:[],palettePath:"",palette:{rows:[]},scenes:{rows:[]},areaMode:"settings",sceneMapFiles:[],sceneMapPath:"",sceneMap:{rows:[]},sceneProps:{rows:[]},sceneRender:{token:""},worlds:{rows:[]},worldMode:"settings",worldFiles:[],worldFilePath:"",worldMap:{rows:[]},worldProps:{rows:[]},worldMusic:{rows:[]},worldColors:{rows:[]},worldNavigation:{rows:[]},animations:{rows:[]},graphicsSets:{rows:[]},assemblies:{rows:[]},spriteHeaders:{rows:[]},spriteAssemblies:{rows:[]},tileMode:"animations",gameplayMode:"weapons",exits:{rows:[]},treasure:{rows:[]},weapons:{rows:[]},armor:{rows:[]},helmets:{rows:[]},dirty:new Map(),selected:{text:null,scenes:null,scenemaps:null,sceneprops:null,worlds:null,worldmaps:null,worldprops:null,worldmusic:null,worldcolors:null,worldnav:null,animations:null,tilesets:null,assemblies:null,sprites:null,spriteassemblies:null,exits:null,treasure:null,weapons:null,armor:null,helmets:null,palettes:null},page:{text:0,scenes:0,scenemaps:0,sceneprops:0,worlds:0,worldmaps:0,worldprops:0,worldmusic:0,worldcolors:0,worldnav:0,animations:0,tilesets:0,assemblies:0,sprites:0,spriteassemblies:0,exits:0,treasure:0,weapons:0,armor:0,helmets:0,palettes:0},pageSize:{text:18,scenes:18,scenemaps:18,sceneprops:18,worlds:18,worldmaps:18,worldprops:18,worldmusic:18,worldcolors:18,worldnav:18,animations:18,tilesets:18,assemblies:18,sprites:18,spriteassemblies:18,exits:18,treasure:18,weapons:18,armor:18,helmets:18,palettes:18},query:{text:"",scenes:"",scenemaps:"",sceneprops:"",worlds:"",worldmaps:"",worldprops:"",worldmusic:"",worldcolors:"",worldnav:"",animations:"",tilesets:"",assemblies:"",sprites:"",spriteassemblies:"",exits:"",treasure:"",weapons:"",armor:"",helmets:"",palettes:""},sort:{text:{key:"key",dir:1},scenes:{key:"id",dir:1},scenemaps:{key:"layer",dir:1},sceneprops:{key:"startTile",dir:1},worlds:{key:"id",dir:1},worldmaps:{key:"layer",dir:1},worldprops:{key:"tileIndex",dir:1},worldmusic:{key:"index",dir:1},worldcolors:{key:"index",dir:1},worldnav:{key:"tableId",dir:1},animations:{key:"fileId",dir:1},tilesets:{key:"id",dir:1},assemblies:{key:"tileId",dir:1},sprites:{key:"id",dir:1},spriteassemblies:{key:"fileId",dir:1},exits:{key:"sceneId",dir:1},treasure:{key:"sceneId",dir:1},weapons:{key:"id",dir:1},armor:{key:"id",dir:1},helmets:{key:"id",dir:1},palettes:{key:"index",dir:1}},mapPage:0,mapQuery:"",mapStatus:"",mapSort:["filename",1],exportResult:null};
const spriteImageCache=new Map(),spriteFrameSelection=new Map();
async function api(path,body){const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw new Error(value.error||`Request failed (${response.status})`);return value}
function setToolbar(...nodes){$("#toolbar").replaceChildren(...nodes.filter(Boolean))}
function readonly(){return state.busy||state.source!=="mine"}
function dirtyCount(){return state.dirty.size}
function pendingChanges(){return [...state.dirty.values()].flatMap(entry=>Object.entries(entry.values).map(([field,after])=>({label:`${entry.tab} / ${entry.token} / ${field}`,before:entry.original[field],after})))}
function remember(tab,row,values){const key=`${tab}:${row.token}`,entry=state.dirty.get(key)||{tab,token:row.token,original:{},values:{}};for(const [field,value] of Object.entries(values)){if(!(field in entry.original))entry.original[field]=row[field];entry.values[field]=value;row[field]=value;if(entry.original[field]===value){delete entry.values[field];delete entry.original[field]}}if(Object.keys(entry.values).length)state.dirty.set(key,entry);else state.dirty.delete(key);shell.refresh()}
function rows(tab){if(tab==="text")return state.text.rows||[];if(tab==="scenes")return state.scenes.rows||[];if(tab==="scenemaps")return state.sceneMap.rows||[];if(tab==="sceneprops")return state.sceneProps.rows||[];if(tab==="worlds")return state.worlds.rows||[];if(tab==="worldmaps")return state.worldMap.rows||[];if(tab==="worldprops")return state.worldProps.rows||[];if(tab==="worldmusic")return state.worldMusic.rows||[];if(tab==="worldcolors")return state.worldColors.rows||[];if(tab==="worldnav")return state.worldNavigation.rows||[];if(tab==="animations")return state.animations.rows||[];if(tab==="tilesets")return state.graphicsSets.rows||[];if(tab==="assemblies")return state.assemblies.rows||[];if(tab==="sprites")return state.spriteHeaders.rows||[];if(tab==="spriteassemblies")return state.spriteAssemblies.rows||[];if(tab==="exits")return state.exits.rows||[];if(tab==="palettes")return state.palette.rows||[];if(tab==="treasure")return state.treasure.rows||[];if(tab==="weapons")return state.weapons.rows||[];if(tab==="armor")return state.armor.rows||[];return state.helmets.rows||[]}
function sorted(tab){const q=state.query[tab].toLocaleLowerCase(),{key,dir}=state.sort[tab];return [...rows(tab)].filter(row=>!q||JSON.stringify(row).toLocaleLowerCase().includes(q)).sort((a,b)=>{const left=a[key],right=b[key],r=typeof left==="string"?String(left).localeCompare(String(right)):Number(left)-Number(right);return r*dir})}
function sort(tab,key){const active=state.sort[tab];state.sort[tab]=active.key===key?{key,dir:-active.dir}:{key,dir:1};state.page[tab]=0;render()}
function numberField(tab,row,key,min,max,help){return {dataType:"INT",min,max,help:help?infoHelp(help):null,control:el("input",{type:"number",min,max,step:1,value:row[key],disabled:readonly(),oninput:event=>{if(event.target.value!=="")remember(tab,row,{[key]:Number(event.target.value)})}})}}
function boolField(tab,row,key,help){return {dataType:"BOOL",help:help?infoHelp(help):null,control:el("input",{type:"checkbox",checked:!!row[key],disabled:readonly(),onchange:event=>remember(tab,row,{[key]:event.target.checked})})}}
function selectField(tab,row,key,choices,help){const control=el("select",{disabled:readonly(),onchange:event=>{const raw=event.target.value,value=choices.some(([v])=>typeof v==="number")?Number(raw):raw;remember(tab,row,{[key]:value});render()}},...choices.map(([value,label])=>{const option=el("option",{value},label);option.selected=String(row[key])===String(value);return option}));return {dataType:"ENUM",help:help?infoHelp(help):null,control}}
function master(tab,view,columns){return columnList({rows:view.rows,key:row=>row.token,selected:view.selected,select:view.select,columns,sortState:state.sort[tab],sort:key=>sort(tab,key),refresh:render})}
function records(tab,columns,detail,noun){const filtered=sorted(tab);if(!filtered.length)return el("div",{class:"lex-notice"},`No ${noun} match this view.`);if(!filtered.some(row=>row.token===state.selected[tab]))state.selected[tab]=filtered[0].token;return pagedListDetail({addDisabledReason:"Chrono Trigger keeps this data in fixed tables the game reads by number; a new entry has no slot.",rows:filtered,key:row=>row.token,selected:state.selected[tab],page:state.page[tab],pageSize:state.pageSize[tab],noun,splitKey:`chrono-${tab}`,rowsKey:`chrono-${tab}`,defaultSplit:48,minLeft:320,minRight:380,search:{key:`chrono-${tab}`,value:state.query[tab],label:`Search ${noun}`,change:value=>{state.query[tab]=value;state.page[tab]=0;render()}},sync:next=>{state.page[tab]=next.page;state.pageSize[tab]=next.pageSize;if(next.selected!==null)state.selected[tab]=next.selected},change:next=>{state.page[tab]=next.page;state.pageSize[tab]=next.pageSize;if(next.selected!==null)state.selected[tab]=next.selected;render()},master:view=>master(tab,view,columns),detail})}
function textDetail(row){const control=el("textarea",{value:row.text,disabled:readonly(),oninput:event=>remember("text",row,{text:event.target.value})});return detailPanel({title:row.key,meta:state.text.path||"",body:[detailSection({title:"MESSAGE",body:[detailField({label:"TEXT",dataType:"STRING",control,help:infoHelp("Text displayed for this keyed Steam message. Its record key and original line ending are preserved on save.")}),detailField({label:"KEY",control:readonlyField(row.key)}),detailField({label:"SOURCE FILE",control:readonlyField(state.text.path||"")})]})]})}
function textView(){return records("text",[{key:"key",label:"Key",sortable:true},{key:"text",label:"Text",sortable:true}],textDetail,"messages")}
function sceneDetail(row){return detailPanel({title:row.name,identity:recordId(row.id),meta:row.path,body:[
  detailSection({title:"AREA",body:[
    detailField({label:"MUSIC",...numberField("scenes",row,"musicIndex",0,65535,"Music track reference loaded with this area.")}),
    detailField({label:"MAP",...numberField("scenes",row,"mapIndex",0,65535,"Map layout reference used by this area.")}),
    detailField({label:"EVENT SCRIPT",...numberField("scenes",row,"scriptIndex",0,65535,"Field event script reference used when this area loads.")}),
  ]}),
  detailSection({title:"GRAPHICS",body:[
    detailField({label:"L1/L2 TILESET",...numberField("scenes",row,"layer12TilesetIndex",0,65535,"Graphics-set reference for the first two map layers.")}),
    detailField({label:"L1/L2 ASSEMBLY",...numberField("scenes",row,"layer12AssemblyIndex",0,65535,"Tile-assembly reference for the first two map layers.")}),
    detailField({label:"L3 TILESET",...numberField("scenes",row,"layer3TilesetIndex",0,65535,"Graphics-set reference for the third map layer.")}),
    detailField({label:"PALETTE",...numberField("scenes",row,"paletteIndex",0,65535,"Color-palette reference used by this area.")}),
    detailField({label:"PALETTE ANIMATION",...numberField("scenes",row,"paletteAnimationIndex",0,65535,"Palette-animation set selected by this area.")}),
    detailField({label:"CHIP ANIMATION",...numberField("scenes",row,"chipAnimationIndex",0,65535,"Animated-tile descriptor selected by this area.")}),
  ]}),
  detailSection({title:"CAMERA",body:[
    detailField({label:"FULL MAP",...boolField("scenes",row,"cameraUnbounded","Steam uses 0x80 in the left camera byte to disable the stored scroll rectangle and allow the full map.")}),
    detailField({label:"LEFT",...numberField("scenes",row,"scrollLeft",0,255,"Left edge of the stored camera rectangle, in map tiles. FULL MAP overrides this with the Steam 0x80 sentinel on save.")}),
    detailField({label:"TOP",...numberField("scenes",row,"scrollTop",0,255,"Top edge of the stored camera rectangle, in map tiles.")}),
    detailField({label:"RIGHT",...numberField("scenes",row,"scrollRight",0,255,"Stored right camera edge. The runtime interprets the normal bounded value as inclusive.")}),
    detailField({label:"BOTTOM",...numberField("scenes",row,"scrollBottom",0,255,"Stored bottom camera edge. The runtime interprets the normal bounded value as inclusive.")}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"PC WORD",control:readonlyField(`0x${row.unknownWord.toString(16).padStart(4,"0").toUpperCase()}`,{format:false}),help:infoHelp("This PC-only word has no established gameplay meaning in the audited source and is preserved unchanged.")}),
    detailField({label:"TRAILING BYTES",control:readonlyField(String(row.trailingBytes)),help:infoHelp("Any bytes after the documented 24-byte Steam header are preserved unchanged.")}),
  ]}),
]})}
function scenesView(){return records("scenes",[
  {key:"id",label:"ID",numberedId:true,sortable:true},
  {key:"name",label:"Area",sortable:true},
  {key:"musicIndex",label:"Music",numeric:true,sortable:true},
  {key:"mapIndex",label:"Map",numeric:true,sortable:true},
  {key:"scriptIndex",label:"Script",numeric:true,sortable:true},
],sceneDetail,"areas")}
const SCROLL_SPEED_CHOICES=[[0,"0 px/s"],[1,"+3.75 px/s"],[2,"+7.5 px/s"],[3,"+15 px/s"],[4,"+30 px/s"],[5,"+60 px/s"],[6,"+120 px/s"],[7,"+240 px/s"],[8,"0 px/s (code 8)"],[9,"-3.75 px/s"],[10,"-7.5 px/s"],[11,"-15 px/s"],[12,"-30 px/s"],[13,"-60 px/s"],[14,"-120 px/s"],[15,"-240 px/s"]];
function sceneRenderDetail(row){return detailPanel({title:`Area map ${row.mapId}`,identity:recordId(row.mapId),meta:row.path,body:[
  detailSection({title:"LAYER 2 SCROLL",body:[
    detailField({label:"L2 X SPEED",...selectField("scenerender",row,"scrollL2XCode",SCROLL_SPEED_CHOICES,"Stored four-bit horizontal scroll-speed code.")}),
    detailField({label:"L2 Y SPEED",...selectField("scenerender",row,"scrollL2YCode",SCROLL_SPEED_CHOICES,"Stored four-bit vertical scroll-speed code.")}),
  ]}),
  detailSection({title:"LAYER 3 SCROLL",body:[
    detailField({label:"L3 X SPEED",...selectField("scenerender",row,"scrollL3XCode",SCROLL_SPEED_CHOICES,"Stored four-bit horizontal scroll-speed code.")}),
    detailField({label:"L3 Y SPEED",...selectField("scenerender",row,"scrollL3YCode",SCROLL_SPEED_CHOICES,"Stored four-bit vertical scroll-speed code.")}),
  ]}),
  detailSection({title:"MAIN SCREEN",body:[
    detailField({label:"LAYER 1 MAIN",...boolField("scenerender",row,"layer1Main")}),
    detailField({label:"LAYER 2 MAIN",...boolField("scenerender",row,"layer2Main")}),
    detailField({label:"LAYER 3 MAIN",...boolField("scenerender",row,"layer3Main")}),
    detailField({label:"SPRITES MAIN",...boolField("scenerender",row,"spritesMain")}),
  ]}),
  detailSection({title:"SUB SCREEN",body:[
    detailField({label:"LAYER 1 SUB",...boolField("scenerender",row,"layer1Sub")}),
    detailField({label:"LAYER 2 SUB",...boolField("scenerender",row,"layer2Sub")}),
    detailField({label:"LAYER 3 SUB",...boolField("scenerender",row,"layer3Sub")}),
    detailField({label:"SPRITES SUB",...boolField("scenerender",row,"spritesSub")}),
  ]}),
  detailSection({title:"EFFECTS",body:[
    detailField({label:"LAYER 1 EFFECT",...boolField("scenerender",row,"effectLayer1")}),
    detailField({label:"LAYER 2 EFFECT",...boolField("scenerender",row,"effectLayer2")}),
    detailField({label:"LAYER 3 EFFECT",...boolField("scenerender",row,"effectLayer3")}),
    detailField({label:"SPRITES EFFECT",...boolField("scenerender",row,"effectSprites")}),
    detailField({label:"DEFAULT COLOR",...boolField("scenerender",row,"effectDefaultColor")}),
    detailField({label:"HALF INTENSITY",...boolField("scenerender",row,"effectHalfIntensity")}),
    detailField({label:"SUBTRACT",...boolField("scenerender",row,"effectSubtract")}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"LAYER 3 ENABLED",control:readonlyField(row.layer3Enabled?"Yes":"No"),help:infoHelp("This shares the preserved dimension/mode byte and is not rewritten here.")}),
    detailField({label:"SCROLL MODE BITS",control:readonlyField(`0x${Number(row.scrollModeBits).toString(16).toUpperCase()}`,{format:false})}),
    detailField({label:"DIMENSION / MODE BYTE",control:readonlyField(`0x${Number(row.preservedBitsByte).toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
    detailField({label:"UNKNOWN EFFECT BIT",control:readonlyField(row.unknownEffectBit3?"Set":"Clear"),help:infoHelp("Effect bit 0x08 is unmodelled and preserved unchanged.")}),
  ]}),
]})}
function sceneRenderView(){return panelLayout([sceneRenderDetail(state.sceneRender)],{layoutKey:"chrono-scene-render",defaultSizes:[100]})}
function sceneMapDetail(row){const low=row.layer===3?0:(row.upperBank?256:0),high=low+255;const bank=row.layer===3?"Layer 3 · 0-255":row.upperBank?"Upper · 256-511":"Lower · 0-255";return detailPanel({title:`Layer ${row.layer} · ${row.xTile}, ${row.yTile}`,identity:recordId(row.mapId),meta:state.sceneMap.path||"",body:[
  detailSection({title:"MAP TILE",body:[
    detailField({label:"TILE INDEX",...numberField("scenemaps",row,"tileIndex",low,high,"Stored Steam scene-map tile reference. Layer 1/2 must stay in the bank selected by the preserved RLE property stream.")}),
    detailField({label:"BANK",control:readonlyField(bank)}),
    detailField({label:"STORED BYTE",control:readonlyField(String(row.storedTile))}),
    detailField({label:"LAYER",control:readonlyField(String(row.layer))}),
    detailField({label:"X TILE",control:readonlyField(String(row.xTile))}),
    detailField({label:"Y TILE",control:readonlyField(String(row.yTile))}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"PROPERTY BYTES",control:readonlyField(String(state.sceneMap.propertyBytes??0)),help:infoHelp("The complete RLE-compressed scene property stream is preserved unchanged.")}),
    detailField({label:"SCREEN FLAGS",control:readonlyField(`0x${Number(state.sceneMap.screenFlags||0).toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
    detailField({label:"EFFECT FLAGS",control:readonlyField(`0x${Number(state.sceneMap.effectFlags||0).toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
  ]}),
]})}
function sceneMapsView(){return records("scenemaps",[
  {key:"layer",label:"Layer",numeric:true,sortable:true},
  {key:"xTile",label:"X",numeric:true,sortable:true},
  {key:"yTile",label:"Y",numeric:true,sortable:true},
  {key:"tileIndex",label:"Tile",numeric:true,sortable:true},
],sceneMapDetail,"area map tiles")}
function sceneCollisionChoices(value){const names=["None","Full","45° NW","45° NE","45° SW","45° SE","30° NW","30° NE","30° SW","30° SE","22° NW","22° NE","22° SW","22° SE","75° NW","75° NE","75° SW","75° SE","75° NW duplicate","75° NE duplicate","75° SW duplicate","75° SE duplicate","Stairs SW-NE","Stairs SE-NW","Left half","Top half","SW","SE","NE","NW","Ladder"];const choices=names.map((label,index)=>[index,label]);if(!choices.some(([code])=>code===value))choices.unshift([value,`Unknown ${value} (preserve)`]);return choices}
function scenePropertyDetail(row){const directions=[[0,"North"],[1,"South"],[2,"East"],[3,"West"]];return detailPanel({title:`Run ${row.runId} · tiles ${row.startTile}-${row.endTile}`,identity:recordId(row.mapId),meta:state.sceneProps.path||"",body:[
  detailSection({title:"RLE RUN",body:[
    detailField({label:"REPEAT COUNT",control:readonlyField(String(row.repeatCount)),help:infoHelp("This existing run length is preserved; Lexeditor never splits or resizes the RLE stream.")}),
    detailField({label:"COMPRESSED",control:readonlyField(row.compressed?"Yes":"No")}),
    detailField({label:"COVERED TILES",control:readonlyField(String(row.coveredTiles))}),
    detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false})}),
  ]}),
  detailSection({title:"TILE BANKS + COLLISION",body:[
    detailField({label:"L1 UPPER BANK",...boolField("sceneprops",row,"layer1UpperBank","Adds 256 to layer-1 tile references for every tile covered by this property run.")}),
    detailField({label:"L2 UPPER BANK",...boolField("sceneprops",row,"layer2UpperBank","Adds 256 to layer-2 tile references for every tile covered by this property run.")}),
    detailField({label:"COLLISION",...selectField("sceneprops",row,"collisionCode",sceneCollisionChoices(row.collisionCode),"Documented scene collision shape code.")}),
    detailField({label:"DOOR TRIGGER",...boolField("sceneprops",row,"doorTrigger","Door-trigger flag from the stored scene property byte.")}),
    detailField({label:"NPC BATTLE COLLISION",...boolField("sceneprops",row,"npcCollisionBattle","NPC collision flag used during battle contexts.")}),
    detailField({label:"NPC COLLISION",...boolField("sceneprops",row,"npcCollision","NPC collision flag.")}),
  ]}),
  detailSection({title:"MOVEMENT + Z",body:[
    detailField({label:"MOVE DIRECTION",...selectField("sceneprops",row,"moveDirection",directions,"Conveyor/movement direction encoded in the property byte.")}),
    detailField({label:"MOVE SPEED",...numberField("sceneprops",row,"moveSpeed",0,3,"Two-bit movement speed code.")}),
    detailField({label:"Z PLANE",...numberField("sceneprops",row,"zPlane",0,3,"Two-bit Z-plane code.")}),
    detailField({label:"IGNORE Z",...boolField("sceneprops",row,"collisionIgnoreZ","Collision ignores Z-plane separation.")}),
    detailField({label:"INVERT COLLISION",...boolField("sceneprops",row,"collisionInverted","Inverts the stored collision interpretation.")}),
    detailField({label:"Z NEUTRAL",...boolField("sceneprops",row,"zNeutral","Marks neutral Z behavior.")}),
  ]}),
  detailSection({title:"SPRITE PRIORITY",body:[
    detailField({label:"TOP ABOVE ALL",...boolField("sceneprops",row,"priorityTop","Top half of sprites renders above all layers.")}),
    detailField({label:"BOTTOM ABOVE ALL",...boolField("sceneprops",row,"priorityBottom","Bottom half of sprites renders above all layers.")}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"UNKNOWN BYTE 2 BIT 5",control:readonlyField(row.unknownSecondBit5?"Set":"Clear"),help:infoHelp("Unmodelled bit preserved unchanged.")}),
    detailField({label:"UNKNOWN BYTE 3 BIT 4",control:readonlyField(row.unknownThirdBit4?"Set":"Clear"),help:infoHelp("Unmodelled bit preserved unchanged.")}),
  ]}),
]})}
function scenePropsView(){return records("sceneprops",[
  {key:"startTile",label:"Start",numeric:true,sortable:true},
  {key:"repeatCount",label:"Repeat",numeric:true,sortable:true},
  {key:"collisionName",label:"Collision",sortable:true},
  {key:"moveDirectionName",label:"Move",sortable:true},
],scenePropertyDetail,"scene property runs")}
function areasSurface(){if(state.areaMode==="render")return sceneRenderView();if(state.areaMode==="map")return sceneMapsView();if(state.areaMode==="properties")return scenePropsView();return scenesView()}
function areaToolbar(){const mode=el("select",{"aria-label":"Area data",onchange:event=>switchAreaMode(event.target.value)},
  ...[["settings","Settings"],["render","Render settings"],["map","Map tiles"],["properties","Tile properties"]].map(([value,label])=>{const option=el("option",{value},label);option.selected=value===state.areaMode;return option}));
  const controls=[el("label",{},"Area data",mode)];
  if(state.areaMode!=="settings"){const file=el("select",{"aria-label":"Area map file",onchange:event=>switchSceneMapFile(event.target.value)},...state.sceneMapFiles.map(row=>{const option=el("option",{value:row.path},row.label);option.selected=row.path===state.sceneMapPath;return option}));controls.push(el("label",{},"File",file))}
  return controls}
function worldDetail(row){const graphics12=Array.from({length:8},(_,index)=>detailField({label:`L1/L2 GRAPHICS ${index}`,...numberField("worlds",row,`layer12Graphics${index}`,0,255,"Graphics-set reference stored in this fixed Steam world header.")}));const graphics3=Array.from({length:2},(_,index)=>detailField({label:`L3 GRAPHICS ${index}`,...numberField("worlds",row,`layer3Graphics${index}`,0,255,"Layer 3 graphics-set reference stored in this fixed Steam world header.")}));const sprites=Array.from({length:4},(_,index)=>detailField({label:`SPRITE GRAPHICS ${index}`,...numberField("worlds",row,`spriteGraphics${index}`,0,255,"World sprite graphics-set reference.")}));return detailPanel({title:row.name,identity:recordId(row.id),meta:"Game/common/bankc6.bin",body:[
  detailSection({title:"WORLD DATA",body:[
    detailField({label:"MAP",...numberField("worlds",row,"mapIndex",0,255,"World map tile-data reference.")}),
    detailField({label:"MAP PROPERTIES",...numberField("worlds",row,"mapPropertiesIndex",0,255,"World tile-property reference.")}),
    detailField({label:"PALETTE",...numberField("worlds",row,"paletteIndex",0,255,"World palette reference.")}),
    detailField({label:"MUSIC PROPERTIES",...numberField("worlds",row,"musicPropertiesIndex",0,255,"World music-transition data reference.")}),
    detailField({label:"EXITS / TRIGGERS",...numberField("worlds",row,"exitsIndex",0,255,"World exit and trigger table reference.")}),
    detailField({label:"SCRIPT",...numberField("worlds",row,"scriptIndex",0,255,"World event-script reference.")}),
  ]}),
  detailSection({title:"TILESETS",body:[
    detailField({label:"L1/L2 ASSEMBLY",...numberField("worlds",row,"layer12AssemblyIndex",0,255,"Layer 1/2 tile-assembly reference.")}),
    detailField({label:"L3 ASSEMBLY",...numberField("worlds",row,"layer3AssemblyIndex",0,255,"Layer 3 tile-assembly reference.")}),
    ...graphics12,...graphics3,
  ]}),
  detailSection({title:"SPRITES",body:sprites}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"PALETTE ANIMATION BYTE",control:readonlyField(String(row.paletteAnimationIndex)),help:infoHelp("CTViewer documents this header byte, but the Steam runtime uses the world index for palette animation instead. Lexeditor shows and preserves the byte rather than inventing semantics.")}),
    detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false}),help:infoHelp("Start of this fixed 23-byte world header inside Game/common/bankc6.bin.")}),
  ]}),
]})}
function worldsView(){return records("worlds",[
  {key:"id",label:"ID",numberedId:true,sortable:true},
  {key:"mapIndex",label:"Map",numeric:true,sortable:true},
  {key:"paletteIndex",label:"Palette",numeric:true,sortable:true},
  {key:"musicPropertiesIndex",label:"Music",numeric:true,sortable:true},
  {key:"scriptIndex",label:"Script",numeric:true,sortable:true},
],worldDetail,"worlds")}
function worldMapDetail(row){const low=row.layer===1?0:256,high=row.layer===1?255:511;return detailPanel({title:`Layer ${row.layer} · ${row.xTile}, ${row.yTile}`,identity:recordId(row.mapId),meta:state.worldMap.path||"",body:[
  detailSection({title:"MAP TILE",body:[
    detailField({label:"TILE INDEX",...numberField("worldmaps",row,"tileIndex",low,high,"Stored world-map tile reference. Layer 2 uses the upper 256-tile bank.")}),
    detailField({label:"LAYER",control:readonlyField(String(row.layer))}),
    detailField({label:"X TILE",control:readonlyField(String(row.xTile))}),
    detailField({label:"Y TILE",control:readonlyField(String(row.yTile))}),
  ]}),
  detailSection({title:"PRESERVED",body:[detailField({label:"TRAILING BYTES",control:readonlyField(String(state.worldMap.trailingBytes??0))})]}),
]})}
function worldMapsView(){return records("worldmaps",[
  {key:"layer",label:"Layer",numeric:true,sortable:true},
  {key:"xTile",label:"X",numeric:true,sortable:true},
  {key:"yTile",label:"Y",numeric:true,sortable:true},
  {key:"tileIndex",label:"Tile",numeric:true,sortable:true},
],worldMapDetail,"world map tiles")}
function worldPropertyChoices(value){const choices=[[0,"Nothing"],[1,"Blocks walking"],[2,"Blocks landing"],[3,"Blocks flying"],[4,"Exit / trigger"]];if(!choices.some(([code])=>code===value))choices.unshift([value,`Unknown ${value} (preserve)`]);return choices}
function worldPropertyDetail(row){return detailPanel({title:`Tile ${row.tileIndex}`,identity:recordId(row.fileId),meta:state.worldProps.path||"",body:[
  detailSection({title:"CHIP PROPERTIES",body:[
    detailField({label:"TOP LEFT",...selectField("worldprops",row,"topLeft",worldPropertyChoices(row.topLeft),"Property for the top-left 8×8 chip.")}),
    detailField({label:"TOP RIGHT",...selectField("worldprops",row,"topRight",worldPropertyChoices(row.topRight),"Property for the top-right 8×8 chip.")}),
    detailField({label:"BOTTOM LEFT",...selectField("worldprops",row,"bottomLeft",worldPropertyChoices(row.bottomLeft),"Property for the bottom-left 8×8 chip.")}),
    detailField({label:"BOTTOM RIGHT",...selectField("worldprops",row,"bottomRight",worldPropertyChoices(row.bottomRight),"Property for the bottom-right 8×8 chip.")}),
  ]}),
  detailSection({title:"PRESERVED",body:[detailField({label:"TRAILING BYTES",control:readonlyField(String(state.worldProps.trailingBytes??0))})]}),
]})}
function worldPropsView(){return records("worldprops",[
  {key:"tileIndex",label:"Tile",numberedId:true,sortable:true},
  {key:"topLeft",label:"TL",numeric:true,sortable:true},
  {key:"topRight",label:"TR",numeric:true,sortable:true},
  {key:"bottomLeft",label:"BL",numeric:true,sortable:true},
  {key:"bottomRight",label:"BR",numeric:true,sortable:true},
],worldPropertyDetail,"world tile properties")}
function worldMusicDetail(row){return detailPanel({title:`Music block ${row.xTile}, ${row.yTile}`,identity:recordId(row.fileId),meta:state.worldMusic.path||"",body:[
  detailSection({title:"MUSIC",body:[
    detailField({label:"LEFT MUSIC",...numberField("worldmusic",row,"leftMusic",0,15,"Four-bit music-list index for the left half of this stored transition byte.")}),
    detailField({label:"RIGHT MUSIC",...numberField("worldmusic",row,"rightMusic",0,15,"Four-bit music-list index for the right half of this stored transition byte.")}),
    detailField({label:"X TILE",control:readonlyField(String(row.xTile))}),
    detailField({label:"Y TILE",control:readonlyField(String(row.yTile))}),
  ]}),
  detailSection({title:"PRESERVED",body:[detailField({label:"TRAILING BYTES",control:readonlyField(String(state.worldMusic.trailingBytes??0))})]}),
]})}
function worldMusicView(){return records("worldmusic",[
  {key:"xTile",label:"X",numeric:true,sortable:true},
  {key:"yTile",label:"Y",numeric:true,sortable:true},
  {key:"leftMusic",label:"Left",numeric:true,sortable:true},
  {key:"rightMusic",label:"Right",numeric:true,sortable:true},
],worldMusicDetail,"world music blocks")}
function worldColorDetail(row){const picker=el("input",{type:"color",value:row.hex.toLowerCase(),disabled:readonly(),oninput:event=>{remember("worldcolors",row,{hex:event.target.value.toUpperCase()});render()}});return detailPanel({title:`Color ${row.index}`,identity:recordId(row.index),meta:state.worldColors.path||"",body:[
  detailSection({title:"COLOR",body:[
    detailField({label:"COLOR",dataType:"STRING",control:picker,help:infoHelp("Existing RGB555 color used by Steam world palette animation data.")}),
    detailField({label:"HEX",control:readonlyField(row.hex)}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"BIT 15",control:readonlyField(row.preservedBit15?"Set":"Clear")}),
    detailField({label:"TRAILING BYTES",control:readonlyField(String(state.worldColors.trailingBytes??0))}),
  ]}),
]})}
function worldColorsView(){return records("worldcolors",[
  {key:"index",label:"ID",numberedId:true,sortable:true},
  {key:"hex",label:"Color",sortable:true},
  {key:"red5",label:"R/31",numeric:true,sortable:true},
  {key:"green5",label:"G/31",numeric:true,sortable:true},
  {key:"blue5",label:"B/31",numeric:true,sortable:true},
],worldColorDetail,"world animation colors")}
function worldsSurface(){if(state.worldMode==="map")return worldMapsView();if(state.worldMode==="properties")return worldPropsView();if(state.worldMode==="music")return worldMusicView();if(state.worldMode==="colors")return worldColorsView();return worldsView()}
function worldToolbar(){const mode=el("select",{"aria-label":"World data",onchange:event=>switchWorldMode(event.target.value)},
  ...[["settings","Settings"],["map","Map tiles"],["properties","Tile properties"],["music","Music transitions"],["colors","Palette animation colors"]].map(([value,label])=>{const option=el("option",{value},label);option.selected=value===state.worldMode;return option}));
  const controls=[el("label",{},"World data",mode)];
  if(state.worldMode!=="settings"){const file=el("select",{"aria-label":"World file",onchange:event=>switchWorldFile(event.target.value)},...state.worldFiles.map(row=>{const option=el("option",{value:row.path},row.label);option.selected=row.path===state.worldFilePath;return option}));controls.push(el("label",{},"File",file))}
  return controls}
function worldNavigationDetail(row){const meta=`Event table ${row.tableId}`;if(row.recordType==="trigger")return detailPanel({title:`Trigger ${row.recordId}`,identity:recordId(row.tableId),meta,body:[
  detailSection({title:"TRIGGER",body:[
    detailField({label:"ENABLED",...boolField("worldnav",row,"enabled","Bit 7 of the stored X coordinate enables this overworld trigger.")}),
    detailField({label:"X TILE",...numberField("worldnav",row,"xTile",0,127,"Overworld trigger X tile.")}),
    detailField({label:"Y TILE",...numberField("worldnav",row,"yTile",0,255,"Overworld trigger Y tile.")}),
    detailField({label:"SCRIPT ADDRESS",...numberField("worldnav",row,"scriptAddressIndex",0,Math.max(0,row.scriptAddressCount-1),"Index into this EventTable's preserved world-script address list.")}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false})}),
  ]}),
]});const destination=row.scripted?[
  detailField({label:"TYPE",control:readonlyField("Scripted")}),
  detailField({label:"SCRIPT ADDRESS",...numberField("worldnav",row,"scriptAddressIndex",0,Math.max(0,Math.min(3,row.scriptAddressCount-1)),"Script-address index encoded in the existing scripted exit. Lexeditor does not convert exit types.")}),
]:[
  detailField({label:"TYPE",control:readonlyField("Scene destination")}),
  detailField({label:"SCENE",...numberField("worldnav",row,"destinationScene",0,65535,"Destination scene. 0x1FF is reserved for scripted exits and rejected on save.")}),
  detailField({label:"FACING",...selectField("worldnav",row,"facing",FACING,"Party facing after arrival.")}),
];return detailPanel({title:`${row.scripted?"Scripted exit":"Exit"} ${row.recordId}`,identity:recordId(row.tableId),meta,body:[
  detailSection({title:"OVERWORLD POSITION",body:[
    detailField({label:"ENABLED",...boolField("worldnav",row,"enabled","Bit 7 of the stored X coordinate enables this overworld exit.")}),
    detailField({label:"X TILE",...numberField("worldnav",row,"xTile",0,127,"Overworld exit X tile.")}),
    detailField({label:"Y TILE",...numberField("worldnav",row,"yTile",0,63,"Lower six bits store the overworld Y tile; upper bits are preserved.")}),
    detailField({label:"NAME INDEX",...numberField("worldnav",row,"nameIndex",0,255,"Index into the first 106 strings of Localize/<language>/msg/w_map.txt.")}),
    detailField({label:"RESOLVED NAME",control:readonlyField(row.name||"Name unavailable")}),
  ]}),
  detailSection({title:"DESTINATION",body:[
    ...destination,
    detailField({label:"X TILE",...numberField("worldnav",row,"targetX",0,255,"Stored destination X coordinate.")}),
    detailField({label:"Y TILE",...numberField("worldnav",row,"targetY",0,255,"Stored destination Y coordinate.")}),
    detailField({label:"HALF TILE LEFT",...boolField("worldnav",row,"halfTileLeft","Offsets arrival eight pixels left.")}),
    detailField({label:"HALF TILE UP",...boolField("worldnav",row,"halfTileUp","Offsets arrival eight pixels upward.")}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"Y FLAG BITS",control:readonlyField(`0x${row.unknownYBits.toString(16).padStart(2,"0").toUpperCase()}`,{format:false}),help:infoHelp("The unmodelled upper Y bits are preserved byte-for-byte.")}),
    detailField({label:"FACING FLAG BITS",control:readonlyField(`0x${row.unknownFacingBits.toString(16).padStart(2,"0").toUpperCase()}`,{format:false}),help:infoHelp("Bits not used for facing or half-tile shifts are preserved byte-for-byte.")}),
    detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false})}),
  ]}),
]})}
function worldNavigationView(){return records("worldnav",[
  {key:"tableId",label:"Table",numberedId:true,sortable:true},
  {key:"recordType",label:"Type",sortable:true},
  {key:"recordId",label:"Record",numberedId:true,sortable:true},
  {key:"name",label:"Name",sortable:true},
  {key:"scripted",label:"Scripted",sortable:true},
],worldNavigationDetail,"world navigation records")}
function durationChoices(code){const choices=[[0x10,"16 ticks"],[0x20,"12 ticks"],[0x40,"8 ticks"],[0x80,"4 ticks"]];if(!choices.some(([value])=>value===code))choices.unshift([code,`Unknown 0x${code.toString(16).padStart(2,"0").toUpperCase()} (preserve)`]);return choices}
function animationDetail(row){if(!row.editable)return detailPanel({title:`Animation ${row.animationId}`,identity:recordId(row.fileId),meta:row.path,body:[el("p",{class:"lex-notice"},"This animation contains a chip offset that is not aligned to the documented 32-byte Steam chip boundary. It is preserved read-only."),detailSection({title:"PRESERVED",body:[detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false})}),detailField({label:"TRAILING BYTES",control:readonlyField(String(row.fileTrailingBytes))})]})]});const frames=[];for(let index=0;index<row.frameCount;index++){frames.push(detailField({label:`FRAME ${index} DURATION`,...selectField("animations",row,`durationCode${index}`,durationChoices(row[`durationCode${index}`]),"Only the documented duration high nibble is edited; the unknown low nibble is preserved.")}),detailField({label:`FRAME ${index} SOURCE CHIP`,...numberField("animations",row,`sourceChip${index}`,0,2047,"First source chip of the four-chip animation frame.")}),detailField({label:`FRAME ${index} LOW BITS`,control:readonlyField(`0x${row[`durationLowBits${index}`].toString(16).toUpperCase()}`,{format:false}),help:infoHelp("Unknown duration-byte low nibble, preserved unchanged.")}))}return detailPanel({title:`Animation ${row.animationId}`,identity:recordId(row.fileId),meta:row.path,body:[
  detailSection({title:"ANIMATION",body:[
    detailField({label:"DESTINATION CHIP",...numberField("animations",row,"destinationChip",0,2047,"First destination chip of the four-chip animated region.")}),
    detailField({label:"FRAME COUNT",control:readonlyField(String(row.frameCount)),help:infoHelp("Frame counts are fixed; this editor never resizes an animation.")}),
  ]}),
  detailSection({title:"FRAMES",body:frames}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false})}),
    detailField({label:"TRAILING BYTES",control:readonlyField(String(row.fileTrailingBytes))}),
  ]}),
]})}
function animationsView(){return records("animations",[
  {key:"fileId",label:"Set",numberedId:true,sortable:true},
  {key:"animationId",label:"Animation",numberedId:true,sortable:true},
  {key:"frameCount",label:"Frames",numeric:true,sortable:true},
  {key:"destinationChip",label:"Destination",numeric:true,sortable:true},
],animationDetail,"chip animations")}
function graphicsSetDetail(row){const fields=Array.from({length:8},(_,index)=>detailField({label:`GRAPHICS SET ${index}`,...numberField("tilesets",row,`graphicsSet${index}`,0,255,index===6?"Animated-chip graphics set. 255 means unused.":"Graphics-set reference. 255 means this slot is unused.")}));return detailPanel({title:`Tileset ${row.id}`,identity:recordId(row.id),meta:row.path,body:[detailSection({title:"GRAPHICS SETS",body:fields}),detailSection({title:"PRESERVED",body:[detailField({label:"TRAILING BYTES",control:readonlyField(String(row.trailingBytes))})]})]})}
function graphicsSetsView(){return records("tilesets",[
  {key:"id",label:"ID",numberedId:true,sortable:true},
  {key:"graphicsSet0",label:"Set 0",numeric:true,sortable:true},
  {key:"graphicsSet6",label:"Animated",numeric:true,sortable:true},
  {key:"graphicsSet7",label:"Set 7",numeric:true,sortable:true},
],graphicsSetDetail,"tileset graphics tables")}
function assemblyDetail(row){return detailPanel({title:`Tile ${row.tileId} · ${row.cornerName}`,identity:recordId(row.fileId),meta:row.path,body:[
  detailSection({title:"CHIP",body:[
    detailField({label:"CHIP INDEX",...numberField("assemblies",row,"chipIndex",0,1023,"8×8 source chip used for this 16×16 tile corner.")}),
    detailField({label:"PALETTE",...numberField("assemblies",row,"paletteIndex",0,15,"Palette bank selected for this corner.")}),
    detailField({label:"FLIP HORIZONTAL",...boolField("assemblies",row,"flipHorizontal","Mirror this chip horizontally.")}),
    detailField({label:"FLIP VERTICAL",...boolField("assemblies",row,"flipVertical","Mirror this chip vertically.")}),
    detailField({label:"PRIORITY",...boolField("assemblies",row,"priority","Draw this chip with the Steam priority flag set.")}),
  ]}),
  detailSection({title:"IDENTITY",body:[
    detailField({label:"LAYER",control:readonlyField(row.kind==="layer12"?"Layer 1/2":"Layer 3")}),
    detailField({label:"CORNER",control:readonlyField(row.cornerName)}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"UNKNOWN PRIORITY BITS",control:readonlyField(`0x${row.unknownPriorityBits.toString(16).padStart(2,"0").toUpperCase()}`,{format:false}),help:infoHelp("Only bit 0 of the third byte is documented as priority; all other bits are preserved.")}),
    detailField({label:"BYTE OFFSET",control:readonlyField(`0x${row.byteOffset.toString(16).toUpperCase()}`,{format:false})}),
    detailField({label:"TRAILING BYTES",control:readonlyField(String(row.fileTrailingBytes))}),
  ]}),
]})}
function assembliesView(){return records("assemblies",[
  {key:"kind",label:"Layer",sortable:true},
  {key:"fileId",label:"Set",numberedId:true,sortable:true},
  {key:"tileId",label:"Tile",numberedId:true,sortable:true},
  {key:"corner",label:"Corner",numeric:true,sortable:true},
  {key:"chipIndex",label:"Chip",numeric:true,sortable:true},
  {key:"paletteIndex",label:"Palette",numeric:true,sortable:true},
],assemblyDetail,"tile corners")}
function loadSpriteImageData(id,frame){const key=`${id}:${frame}:${state.source}`;let entry=spriteImageCache.get(key);if(!entry){entry={status:"loading",data:null,error:""};spriteImageCache.set(key,entry);api(`/api/sprite-image?index=${id}&bitmap=${frame}&source=${state.source}`).then(result=>{entry.status="ready";entry.data=result;render()}).catch(error=>{entry.status="error";entry.error=error.message;render()})}return entry}
function spriteImageField(id){const frame=spriteFrameSelection.get(id)??0,cache=loadSpriteImageData(id,frame);const img=cache.status==="ready"?el("img",{src:`data:image/png;base64,${cache.data.pngBase64}`,alt:`Sprite ${id} frame ${frame}`}):null;const message=cache.status==="loading"?"Loading sprite…":cache.status==="error"?`Image unavailable: ${cache.error}`:img?"":"No image";const icon=LexeditorUI.iconSlot({content:img,message});const frames=cache.status==="ready"?cache.data.frames:[frame];const controls=[];if(frames.length>1){controls.push(el("label",{},"Frame",el("select",{"aria-label":`Sprite ${id} frame`,onchange:event=>{spriteFrameSelection.set(id,Number(event.target.value));render()}},...frames.map(value=>{const option=el("option",{value},`Frame ${value}`);option.selected=value===frame;return option}))))}
  const upload=el("input",{type:"file",accept:"image/*",disabled:readonly(),onchange:async event=>{const file=event.target.files[0];if(!file)return;try{const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(reader.error);reader.readAsDataURL(file)});const meta=cache.status==="ready"?cache.data:await api(`/api/sprite-image?index=${id}&bitmap=${frame}&source=${state.source}`);const saved=await api("/api/sprite-image/save",{index:id,bitmap:frame,sha256:meta.sha256,imageBase64:dataUrl.split(",")[1]});spriteImageCache.set(`${id}:${frame}:mine`,{status:"ready",data:saved,error:""});render()}catch(error){state.error=error.message;render()}finally{event.target.value=""}}});
  controls.push(el("label",{},"Replace this frame",upload));
  return {icon,controls}}
function spriteDetail(row){const image=spriteImageField(row.id);const body=[
  detailSection({title:"GRAPHIC",body:[detailField({label:"FRAME",control:el("div",{},...image.controls)}),detailField({label:"SOURCE",control:readonlyField(`Game/chara/bmp/c${String(row.id).padStart(3,"0")}_${spriteFrameSelection.get(row.id)??0}.bmp`)}),detailField({label:"REPLACEMENT",control:readonlyField("A replacement image must exactly match the current frame's pixel size."),help:infoHelp("CTViewer's PC renderer reads this exact bitmap. Frame 0 of a sprite also supplies the 16-color palette shared by every other frame, so replacing frame 0 changes colors everywhere for this sprite.")})]}),
  detailSection({title:"DESCRIPTOR",body:[
    detailField({label:"SIZE GROUP CODE",...numberField("sprites",row,"sizeGroupCode",0,3,"The low two descriptor bits are documented as the number/size code for four-tile groups. Other size bits remain preserved.")}),
    detailField({label:"PRIMARY ENEMY",...boolField("sprites",row,"primaryEnemy","Documented primary-enemy flag, bit 0x08.")}),
    detailField({label:"ANIMATION SET",...numberField("sprites",row,"animationIndex",0,255,"Sprite animation-set index.")}),
  ]}),
  detailSection({title:"PC-IGNORED REFERENCES",body:[
    detailField({label:"STORED BITMAP",control:readonlyField(String(row.storedBitmapIndex)),help:infoHelp("CTViewer shows the current-PC runtime replaces this stored reference with the sprite ID. Lexeditor preserves it.")}),
    detailField({label:"STORED ASSEMBLY",control:readonlyField(String(row.storedAssemblyIndex)),help:infoHelp("The current-PC runtime replaces this stored reference with the sprite ID.")}),
    detailField({label:"STORED PALETTE",control:readonlyField(String(row.storedPaletteIndex)),help:infoHelp("The current-PC runtime replaces this stored reference with the sprite ID.")}),
  ]}),
];if(row.enemyDescriptor)body.push(detailSection({title:"ENEMY HAND POSITION",body:[
  detailField({label:"HAND X",...numberField("sprites",row,"handX",-128,127,"Signed enemy hand X position used in battle mode.")}),
  detailField({label:"HAND Y",...numberField("sprites",row,"handY",-128,127,"Signed enemy hand Y position used in battle mode.")}),
]}));body.push(detailSection({title:"PRESERVED",body:[
  detailField({label:"UNKNOWN SIZE FLAGS",control:readonlyField(`0x${row.unknownSizeFlags.toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
  detailField({label:"UNKNOWN FLAGS",control:readonlyField(`0x${row.unknownFlags.toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
  ...(row.enemyDescriptor?[
    detailField({label:"ENEMY UNKNOWN 1",control:readonlyField(`0x${row.enemyUnknown1.toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
    detailField({label:"ENEMY UNKNOWN 2",control:readonlyField(`0x${row.enemyUnknown2.toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
    detailField({label:"ENEMY UNKNOWN 3",control:readonlyField(`0x${row.enemyUnknown3.toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
  ]:[]),
  detailField({label:"TRAILING BYTES",control:readonlyField(String(row.trailingBytes))}),
]}));return detailPanel({icon:image.icon,title:`Sprite ${row.id}`,identity:recordId(row.id),meta:row.path,body})}
function spritesView(){return records("sprites",[
  {key:"id",label:"ID",numberedId:true,sortable:true},
  {key:"animationIndex",label:"Animation",numeric:true,sortable:true},
  {key:"sizeGroupCode",label:"Size",numeric:true,sortable:true},
  {key:"primaryEnemy",label:"Primary enemy",sortable:true},
],spriteDetail,"sprite descriptors")}
function spriteAssemblyDetail(row){return detailPanel({title:`Frame ${row.frameId} · tile ${row.tileId}`,identity:recordId(row.fileId),meta:row.path,body:[
  detailSection({title:"SPRITE TILE",body:[
    detailField({label:"CHIP INDEX",...numberField("spriteassemblies",row,"chipIndex",0,32767,"Decoded current-PC sprite source chip index. The odd stored source bit remains preserved.")}),
    detailField({label:"X OFFSET",...numberField("spriteassemblies",row,"x",-128,127,"Signed X offset for this existing tile.")}),
    detailField({label:"Y OFFSET",...numberField("spriteassemblies",row,"y",-128,127,"Signed Y offset for this existing tile.")}),
    detailField({label:"FLIP HORIZONTAL",...boolField("spriteassemblies",row,"flipHorizontal","Documented PC sprite-cell flip-X bit.")}),
    detailField({label:"TOP / BOTTOM",control:readonlyField(row.y<-24?"Top":"Bottom"),help:infoHelp("CTViewer classifies tiles above Y=-24 as the top half of the sprite.")}),
  ]}),
  detailSection({title:"FRAME",body:[
    detailField({label:"FRAME ID",control:readonlyField(String(row.frameId))}),
    detailField({label:"TILE ID",control:readonlyField(String(row.tileId))}),
    detailField({label:"FRAME TILE COUNT",control:readonlyField(String(row.frameTileCount)),help:infoHelp("The existing tile count is never resized.")}),
    detailField({label:"FRAME COUNT",control:readonlyField(String(row.frameCount)),help:infoHelp("The file's existing frame count is preserved.")}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"ODD SOURCE BIT",control:readonlyField(row.weirdSourceBit?"Set":"Clear"),help:infoHelp("CTViewer identifies stored bit 0x08 as an unexplained source-index bit. Lexeditor preserves it.")}),
    detailField({label:"UNKNOWN FLAGS",control:readonlyField(`0x${row.unknownFlags.toString(16).padStart(2,"0").toUpperCase()}`,{format:false})}),
    detailField({label:"HEADER WORD",control:readonlyField(`0x${row.headerWord.toString(16).padStart(4,"0").toUpperCase()}`,{format:false})}),
    detailField({label:"PREFIX",control:readonlyField(row.prefixHex,{format:false})}),
    detailField({label:"TRAILING BYTES",control:readonlyField(String(row.fileTrailingBytes))}),
  ]}),
]})}
function spriteAssembliesView(){return records("spriteassemblies",[
  {key:"fileId",label:"Sprite",numberedId:true,sortable:true},
  {key:"frameId",label:"Frame",numberedId:true,sortable:true},
  {key:"tileId",label:"Tile",numberedId:true,sortable:true},
  {key:"chipIndex",label:"Chip",numeric:true,sortable:true},
  {key:"x",label:"X",numeric:true,sortable:true},
  {key:"y",label:"Y",numeric:true,sortable:true},
],spriteAssemblyDetail,"sprite assembly tiles")}
function tilesView(){if(state.tileMode==="tilesets")return graphicsSetsView();if(state.tileMode==="assemblies")return assembliesView();if(state.tileMode==="sprites")return spritesView();if(state.tileMode==="spriteassemblies")return spriteAssembliesView();return animationsView()}
function tileToolbar(){const select=el("select",{"aria-label":"Tile data",onchange:event=>switchTileMode(event.target.value)},
  ...[["animations","Animations"],["tilesets","Graphics sets"],["assemblies","Assemblies"],["sprites","Sprite descriptors"],["spriteassemblies","Sprite assemblies"]].map(([value,label])=>{const option=el("option",{value},label);option.selected=value===state.tileMode;return option}));
  return [el("label",{},"Tile data",select)]}
function exitDetail(row){return detailPanel({title:`Exit ${row.exitId}`,identity:recordId(row.sceneId),meta:`Scene ${row.sceneId}`,body:[detailSection({title:"TRIGGER",body:[detailField({label:"X TILE",...numberField("exits",row,"xTile",0,255,"Start tile of the exit trigger.")}),detailField({label:"Y TILE",...numberField("exits",row,"yTile",0,255,"Start tile of the exit trigger.")}),detailField({label:"LENGTH",...numberField("exits",row,"lengthTiles",1,128,"Number of tiles spanned by the trigger.")}),detailField({label:"ORIENTATION",...selectField("exits",row,"orientation",[["horizontal","Horizontal"],["vertical","Vertical"]],"Direction the trigger extends from its start tile.")})]}),detailSection({title:"DESTINATION",body:[detailField({label:"LOCATION ID",...numberField("exits",row,"destinationId",0,511,"Scene IDs are direct. IDs 496–511 address world maps.")}),detailField({label:"LOCATION TYPE",control:readonlyField(row.destinationId>=496?"World map":"Scene")}),detailField({label:"X TILE",...numberField("exits",row,"targetX",0,255,"Stored destination X coordinate.")}),detailField({label:"Y TILE",...numberField("exits",row,"targetY",0,255,"Stored destination Y coordinate.")}),detailField({label:"FACING",...selectField("exits",row,"facing",FACING,"Direction the party faces after arrival.")}),detailField({label:"HALF TILE LEFT",...boolField("exits",row,"halfTileLeft","Offsets the destination eight pixels left.")}),detailField({label:"HALF TILE UP",...boolField("exits",row,"halfTileUp","Offsets the destination eight pixels upward.")}),detailField({label:"PRESERVED BITS",control:readonlyField(`0x${row.unknownFacingBits.toString(16).padStart(2,"0").toUpperCase()}`,{format:false}),help:infoHelp("Unmodelled upper flag bits are preserved byte-for-byte.")})]})]})}
function exitsView(){return records("exits",[{key:"sceneId",label:"Scene",numberedId:true,sortable:true},{key:"exitId",label:"Exit",numberedId:true,sortable:true},{key:"destinationId",label:"Destination",numeric:true,sortable:true},{key:"orientation",label:"Shape",sortable:true}],exitDetail,"exits")}
function treasureDetail(row){if(row.alias)return detailPanel({title:`Treasure ${row.treasureId}`,identity:recordId(row.sceneId),meta:`Scene ${row.sceneId}`,body:[detailSection({title:"ALIAS",body:[detailField({label:"OTHER SCENE",control:readonlyField(String(row.aliasScene)),help:infoHelp("A 0,0 position redirects treasure lookup to another scene. Alias records remain read-only.")}),detailField({label:"PRESERVED WORD",control:readonlyField(`0x${row.trailingWord.toString(16).padStart(4,"0").toUpperCase()}`,{format:false})})]})]});if(!row.editable)return detailPanel({title:`Treasure ${row.treasureId}`,identity:recordId(row.sceneId),meta:`Scene ${row.sceneId}`,body:[el("p",{class:"lex-notice"},"This record uses an unknown contents encoding and is preserved read-only.")]});const contents=row.kind==="gold"?[detailField({label:"GOLD",...numberField("treasure",row,"gold",0,65534,"Steam stores treasure gold in increments of two.")})]:[detailField({label:"ITEM INDEX",...numberField("treasure",row,"localIndex",0,511,"Index within the selected Steam item category.")}),detailField({label:"RESOLVED ITEM",control:readonlyField(row.itemName||"Name unavailable")})];return detailPanel({title:`Treasure ${row.treasureId}`,identity:recordId(row.sceneId),meta:`Scene ${row.sceneId}`,body:[detailSection({title:"POSITION",body:[detailField({label:"X TILE",...numberField("treasure",row,"xTile",0,255,"Chest X tile. 0,0 together is reserved for an alias.")}),detailField({label:"Y TILE",...numberField("treasure",row,"yTile",0,255,"Chest Y tile. 0,0 together is reserved for an alias.")})]}),detailSection({title:"CONTENTS",body:[detailField({label:"TYPE",...selectField("treasure",row,"kind",KINDS,"Known Steam treasure encoding family.")}),...contents,detailField({label:"PRESERVED WORD",control:readonlyField(`0x${row.trailingWord.toString(16).padStart(4,"0").toUpperCase()}`,{format:false}),help:infoHelp("The final PC treasure word has no established meaning here and is never rewritten.")})]})]})}
function treasureView(){return records("treasure",[{key:"sceneId",label:"Scene",numberedId:true,sortable:true},{key:"treasureId",label:"Chest",numberedId:true,sortable:true},{key:"kind",label:"Contents",sortable:true},{key:"itemName",label:"Item",sortable:true}],treasureDetail,"treasure records")}

// The palette as the game uses it: 256 colours in one picture. The list below
// shows one colour at a time, which is what made these pages read as numbers
// that refer to something the reader cannot see. Styling is inline because a
// plugin stylesheet may hold theme tokens only.
const paletteColorCache=new Map();
function paletteStrip(rows,selected,onPick,label){
  const cells=rows.map(row=>{const chosen=Number(row.index)===Number(selected);
    const cell=el("button",{type:"button",title:`${row.index} · ${row.hex}`,
      "aria-label":`Colour ${row.index} ${row.hex}${chosen?" (selected)":""}`,
      "aria-pressed":chosen?"true":"false",
      style:`background:${row.hex};border:1px solid rgba(0,0,0,.35);height:20px;padding:0;`
        +(chosen?"outline:2px solid var(--lex-accent);outline-offset:-2px;z-index:1;":""),
      onclick:event=>{event.preventDefault();onPick?.(row.index)}});
    return cell;});
  return el("div",{class:"ct-palette-strip",role:"group","aria-label":label||"The whole palette",
    style:"display:grid;grid-template-columns:repeat(32,1fr);gap:1px;padding:6px;"
      +"background:var(--lex-panel-2);overflow:auto"},...cells);
}
async function paletteColorsFor(path,id){
  const key=`${path}:${state.source}`;
  if(paletteColorCache.has(key))return paletteColorCache.get(key);
  const payload=await api(`/api/palette?path=${encodeURIComponent(path)}&source=${state.source}`);
  paletteColorCache.set(key,payload.rows||[]);
  return payload.rows||[];
}
function paletteDetail(row){const picker=el("input",{type:"color",value:row.hex.toLowerCase(),disabled:readonly(),oninput:event=>{remember("palettes",row,{hex:event.target.value.toUpperCase()});render()}});return detailPanel({title:`Color ${row.index}`,identity:recordId(row.index),meta:state.palette.path||"",body:[
  detailSection({title:"COLOR",body:[
    detailField({label:"COLOR",dataType:"STRING",control:picker,help:infoHelp("The Steam palette stores five bits each of red, green and blue. Lexeditor quantizes the chosen color to those exact RGB555 levels when saving.")}),
    detailField({label:"HEX",control:readonlyField(row.hex)}),
  ]}),
  detailSection({title:"PRESERVED",body:[
    detailField({label:"BIT 15",control:readonlyField(row.preservedBit15?"Set":"Clear"),help:infoHelp("The audited renderer ignores bit 15. Lexeditor never changes it.")}),
    detailField({label:"FILE PREFIX",control:readonlyField(state.palette.prefixHex||"",{format:false})}),
    detailField({label:"TRAILING BYTES",control:readonlyField(String(state.palette.trailingBytes??0))}),
  ]}),
]})}
function palettesView(){const rows=state.palette.rows||[];
  const pick=index=>{state.selected.palettes=String(index);render()};
  const strip=paletteStrip(rows,rows.find(row=>row.token===state.selected.palettes)?.index,pick,`${state.palette.path||"Palette"} colours`);
  return LexeditorUI.stack(strip,records("palettes",[
  {key:"index",label:"ID",numberedId:true,sortable:true},
  {key:"hex",label:"Color",sortable:true},
  {key:"red5",label:"R/31",numeric:true,sortable:true},
  {key:"green5",label:"G/31",numeric:true,sortable:true},
  {key:"blue5",label:"B/31",numeric:true,sortable:true},
],paletteDetail,"colors"))}
function infoView(){const actions=el("div",{class:"lex-action-row"},el("button",{type:"button",disabled:state.busy||dirtyCount()>0||state.source!=="mine",onclick:exportCtp},"Export CTP"),el("button",{type:"button",disabled:state.busy,onclick:()=>refreshInfo(true)},"Refresh"));return panelLayout([detailPanel({className:"lex-information-panel",icon:infoIcon(),title:"Chrono Trigger",meta:"Steam replacement plugin",body:[detailSection({title:"GAME",body:[detailField({label:"INSTALL",control:readonlyField(state.dashboard?.game?.root||"")}),detailField({label:"ARCHIVE",control:readonlyField(state.dashboard?.game?.archive||"")}),detailField({label:"RESOURCES",control:readonlyField(String(state.dashboard?.game?.resourceCount??0))})]}),detailSection({title:"PROJECT",body:[detailField({label:"FOLDER",control:readonlyField(state.dashboard?.project?.root||"")}),detailField({label:"CHANGED FILES",control:readonlyField(String(state.changes.length))}),detailField({label:"ACTIONS",control:actions}),...(state.exportResult?[detailField({label:"LAST EXPORT",control:readonlyField(state.exportResult.path)})]:[])]}),LexeditorUI.modLoaderSection({loader:"Lexeditor exports standard Chrono Trigger .ctp ZIP packages. No runtime loader is bundled by this plugin.",output:"Each CTP contains only changed Game/... and Localize/... resources at resources.bin-relative paths. The installed resources.bin remains unchanged.",order:"Runtime load order belongs to the external loader. Lexeditor exports one project and does not claim semantic merging between separate CTP mods.",safety:"Project writes stay outside the game folder; export never repacks or overwrites resources.bin.",removal:"Remove the exported CTP from the loader's mod location, or revert the project override in Lexeditor."}),LexeditorUI.creditsPanel("chrono-trigger")]})],{layoutKey:"chrono-info",defaultSizes:[100]})}
function dataMapView(){const view=LexeditorUI.dataMap({rows:state.dataMap.rows||[],query:state.mapQuery,status:state.mapStatus,page:state.mapPage,sort:state.mapSort,pageSize:100,open:row=>row.target&&navigate(row.target),changeQuery:value=>{state.mapQuery=value;state.mapPage=0;render()},changeStatus:value=>{state.mapStatus=value;state.mapPage=0;render()},changePage:value=>{state.mapPage=value;render()},changeSort:key=>{const [active,dir]=state.mapSort;state.mapSort=[key,active===key?-dir:1];render()}});state.mapPage=view.page;setToolbar(view.controls);return view.content}
function paletteToolbar(){const file=el("select",{onchange:async event=>{state.palettePath=event.target.value;await loadPalette()}},...state.paletteFiles.map(row=>{const option=el("option",{value:row.path},row.label);option.selected=row.path===state.palettePath;return option}));return [el("label",{},"Palette",file)]}
function textToolbar(){const language=el("select",{onchange:async event=>{state.language=event.target.value;await loadTextFiles(true)}},...(state.dashboard?.languages||[]).map(value=>{const option=el("option",{value},value);option.selected=value===state.language;return option}));const file=el("select",{onchange:async event=>{state.textPath=event.target.value;await loadText()}},...state.textFiles.map(value=>{const option=el("option",{value},value.split("/").pop());option.selected=value===state.textPath;return option}));return [el("label",{},"Language",language),el("label",{},"File",file)]}
function render(){if(state.busy){setToolbar();$("#main").replaceChildren(el("div",{class:"lex-notice",role:"status"},"Loading Chrono Trigger data…"));shell?.refresh?.();return}if(state.error){setToolbar();$("#main").replaceChildren(el("div",{class:"lex-notice",role:"alert"},state.error));shell?.refresh?.();return}if(state.tab==="info"){setToolbar();$("#main").replaceChildren(infoView())}else if(state.tab==="datamap"){$("#main").replaceChildren(dataMapView())}else if(state.tab==="text"){setToolbar(...textToolbar());$("#main").replaceChildren(textView())}else if(state.tab==="scenes"){setToolbar(...areaToolbar());$("#main").replaceChildren(areasSurface())}else if(state.tab==="worlds"){setToolbar(...worldToolbar());$("#main").replaceChildren(worldsSurface())}else if(state.tab==="worldnav"){setToolbar();$("#main").replaceChildren(worldNavigationView())}else if(state.tab==="animations"){setToolbar(...tileToolbar());$("#main").replaceChildren(tilesView())}else if(state.tab==="exits"){setToolbar();$("#main").replaceChildren(exitsView())}else if(state.tab==="treasure"){setToolbar();$("#main").replaceChildren(treasureView())}else{setToolbar(...paletteToolbar());$("#main").replaceChildren(palettesView())}shell?.refresh?.()}
async function loadPaletteFiles(reset=false){const result=await api("/api/palette-files");state.paletteFiles=result.rows||[];if(reset||!state.paletteFiles.some(row=>row.path===state.palettePath))state.palettePath=state.paletteFiles[0]?.path||"";await loadPalette(false)}
async function loadPalette(draw=true){state.palette=state.palettePath?await api(`/api/palette?path=${encodeURIComponent(state.palettePath)}&source=${state.source}`):{rows:[]};state.selected.palettes=state.palette.rows[0]?.token??null;if(draw){state.busy=false;render()}}
async function loadTextFiles(reset=false){const result=await api(`/api/text-files?language=${encodeURIComponent(state.language)}`);state.textFiles=result.rows;if(reset||!state.textFiles.includes(state.textPath))state.textPath=state.textFiles[0]||"";await loadText(false)}
async function loadText(draw=true){state.text=state.textPath?await api(`/api/messages?path=${encodeURIComponent(state.textPath)}&source=${state.source}`):{rows:[]};state.selected.text=state.text.rows[0]?.token??null;if(draw){state.busy=false;render()}}
async function loadAreaMode(){if(state.areaMode==="settings"){state.scenes=await api(`/api/scenes?source=${state.source}&language=${encodeURIComponent(state.language)}`);state.selected.scenes=state.scenes.rows[0]?.token??null;return}const files=await api("/api/scene-map-files");state.sceneMapFiles=files.rows||[];if(!state.sceneMapFiles.some(row=>row.path===state.sceneMapPath))state.sceneMapPath=state.sceneMapFiles[0]?.path||"";const encoded=encodeURIComponent(state.sceneMapPath);if(state.areaMode==="render"){state.sceneRender=state.sceneMapPath?await api(`/api/scene-render-settings?path=${encoded}&source=${state.source}`):{token:""}}
else if(state.areaMode==="map"){state.sceneMap=state.sceneMapPath?await api(`/api/scene-map?path=${encoded}&source=${state.source}`):{rows:[]};state.selected.scenemaps=state.sceneMap.rows[0]?.token??null}else{state.sceneProps=state.sceneMapPath?await api(`/api/scene-properties?path=${encoded}&source=${state.source}`):{rows:[]};state.selected.sceneprops=state.sceneProps.rows[0]?.token??null}}
async function loadWorldMode(){if(state.worldMode==="settings"){state.worlds=await api(`/api/worlds?source=${state.source}`);state.selected.worlds=state.worlds.rows[0]?.token??null;return}const kind={map:"tiles",properties:"properties",music:"music",colors:"colors"}[state.worldMode];const files=await api(`/api/world-files?kind=${kind}`);state.worldFiles=files.rows||[];if(!state.worldFiles.some(row=>row.path===state.worldFilePath))state.worldFilePath=state.worldFiles[0]?.path||"";const encoded=encodeURIComponent(state.worldFilePath);if(state.worldMode==="map"){state.worldMap=state.worldFilePath?await api(`/api/world-map?path=${encoded}&source=${state.source}`):{rows:[]};state.selected.worldmaps=state.worldMap.rows[0]?.token??null}else if(state.worldMode==="properties"){state.worldProps=state.worldFilePath?await api(`/api/world-properties?path=${encoded}&source=${state.source}`):{rows:[]};state.selected.worldprops=state.worldProps.rows[0]?.token??null}else if(state.worldMode==="music"){state.worldMusic=state.worldFilePath?await api(`/api/world-music?path=${encoded}&source=${state.source}`):{rows:[]};state.selected.worldmusic=state.worldMusic.rows[0]?.token??null}else{state.worldColors=state.worldFilePath?await api(`/api/world-colors?path=${encoded}&source=${state.source}`):{rows:[]};state.selected.worldcolors=state.worldColors.rows[0]?.token??null}}
async function loadTab(){state.busy=true;state.error="";render();try{if(state.tab==="text")await loadTextFiles(false);else if(state.tab==="scenes")await loadAreaMode();else if(state.tab==="worlds")await loadWorldMode();else if(state.tab==="worldnav"){state.worldNavigation=await api(`/api/world-navigation?source=${state.source}&language=${encodeURIComponent(state.language)}`);state.selected.worldnav=state.worldNavigation.rows[0]?.token??null}else if(state.tab==="animations"){if(state.tileMode==="tilesets"){state.graphicsSets=await api(`/api/graphics-sets?source=${state.source}`);state.selected.tilesets=state.graphicsSets.rows[0]?.token??null}else if(state.tileMode==="assemblies"){state.assemblies=await api(`/api/tile-assemblies?source=${state.source}`);state.selected.assemblies=state.assemblies.rows[0]?.token??null}else if(state.tileMode==="sprites"){state.spriteHeaders=await api(`/api/sprite-headers?source=${state.source}`);state.selected.sprites=state.spriteHeaders.rows[0]?.token??null}else if(state.tileMode==="spriteassemblies"){state.spriteAssemblies=await api(`/api/sprite-assemblies?source=${state.source}`);state.selected.spriteassemblies=state.spriteAssemblies.rows[0]?.token??null}else{state.animations=await api(`/api/chip-animations?source=${state.source}`);state.selected.animations=state.animations.rows[0]?.token??null}}else if(state.tab==="exits"){state.exits=await api(`/api/exits?source=${state.source}`);state.selected.exits=state.exits.rows[0]?.token??null}else if(state.tab==="treasure"){state.treasure=await api(`/api/treasure?source=${state.source}&language=${encodeURIComponent(state.language)}`);state.selected.treasure=state.treasure.rows[0]?.token??null}else if(state.tab==="palettes")await loadPaletteFiles(false);else if(state.tab==="info")await refreshInfo(false)}catch(error){state.error=error.message}finally{state.busy=false;render()}}
async function switchAreaMode(value){const next=["render","map","properties"].includes(value)?value:"settings";if(next===state.areaMode)return;if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved area edits before changing area data?",confirmLabel:"Discard",cancelLabel:"Stay"}))return;state.dirty.clear();state.areaMode=next;state.sceneMapPath="";await loadTab()}
async function switchSceneMapFile(value){if(value===state.sceneMapPath)return;if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved area-map edits before changing files?",confirmLabel:"Discard",cancelLabel:"Stay"}))return;state.dirty.clear();state.sceneMapPath=value;await loadTab()}
async function switchWorldMode(value){const next=["settings","map","properties","music","colors"].includes(value)?value:"settings";if(next===state.worldMode)return;if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved world edits before changing world data?",confirmLabel:"Discard",cancelLabel:"Stay"}))return;state.dirty.clear();state.worldMode=next;state.worldFilePath="";await loadTab()}
async function switchWorldFile(value){if(value===state.worldFilePath)return;if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved world edits before changing files?",confirmLabel:"Discard",cancelLabel:"Stay"}))return;state.dirty.clear();state.worldFilePath=value;await loadTab()}
async function switchTileMode(value){const next=["animations","tilesets","assemblies","sprites","spriteassemblies"].includes(value)?value:"animations";if(next===state.tileMode)return;if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved tile edits before changing tile data?",confirmLabel:"Discard",cancelLabel:"Stay"}))return;state.dirty.clear();state.tileMode=next;await loadTab()}
async function navigate(tab){const areaModeByTarget={scenes:"settings",scenerender:"render",scenemaps:"map",sceneprops:"properties"};const tileModeByTarget={animations:"animations",tilesets:"tilesets",assemblies:"assemblies",sprites:"sprites",spriteassemblies:"spriteassemblies"};const worldModeByTarget={worlds:"settings",worldmaps:"map",worldprops:"properties",worldmusic:"music",worldcolors:"colors"};const requestedArea=areaModeByTarget[tab]||null,requestedTile=tileModeByTarget[tab]||null,requestedWorld=worldModeByTarget[tab]||null;const nextTab=requestedArea?"scenes":requestedTile?"animations":requestedWorld?"worlds":tab;const modeChanged=(requestedArea&&requestedArea!==state.areaMode)||(requestedTile&&requestedTile!==state.tileMode)||(requestedWorld&&requestedWorld!==state.worldMode);if(nextTab===state.tab&&!modeChanged)return;if(dirtyCount()&&!await LexeditorUI.confirmAction({title:"Unsaved changes",message:"Discard unsaved Chrono Trigger edits before changing pages?",confirmLabel:"Discard",cancelLabel:"Stay"}))return;state.dirty.clear();if(requestedArea){state.areaMode=requestedArea;state.sceneMapPath=""}if(requestedTile)state.tileMode=requestedTile;if(requestedWorld){state.worldMode=requestedWorld;state.worldFilePath=""}state.tab=nextTab;await loadTab()}
async function save(){if(readonly()||!dirtyCount())return;state.busy=true;render();try{const editTab=state.tab==="scenes"?({settings:"scenes",render:"scenerender",map:"scenemaps",properties:"sceneprops"}[state.areaMode]):state.tab==="animations"?state.tileMode:state.tab==="worlds"?({settings:"worlds",map:"worldmaps",properties:"worldprops",music:"worldmusic",colors:"worldcolors"}[state.worldMode]):state.tab;const edits=[...state.dirty.values()].filter(entry=>entry.tab===editTab).map(entry=>({token:entry.token,values:entry.values}));if(editTab==="text"){const textEdits=edits.map(entry=>{const row=state.text.rows.find(row=>row.token===entry.token);return {line:row.line,key:row.key,text:entry.values.text}});state.text=await api("/api/messages/save",{path:state.text.path,sha256:state.text.sha256,edits:textEdits})}else if(editTab==="scenes"){for(const entry of edits){const row=state.scenes.rows.find(row=>row.token===entry.token);const saved=await api("/api/scenes/save",{id:row.id,sha256:row.sha256,language:state.language,values:entry.values});Object.assign(row,saved)}}else if(editTab==="scenerender"){const values=edits[0]?.values||{};state.sceneRender=await api("/api/scene-render-settings/save",{path:state.sceneRender.path,sha256:state.sceneRender.sha256,values})}else if(editTab==="scenemaps")state.sceneMap=await api("/api/scene-map/save",{path:state.sceneMap.path,sha256:state.sceneMap.sha256,edits});else if(editTab==="sceneprops")state.sceneProps=await api("/api/scene-properties/save",{path:state.sceneProps.path,sha256:state.sceneProps.sha256,edits});else if(editTab==="exits")state.exits=await api("/api/exits/save",{dataSha256:state.exits.dataSha256,offsetSha256:state.exits.offsetSha256,edits});else if(editTab==="treasure")state.treasure=await api("/api/treasure/save",{dataSha256:state.treasure.dataSha256,offsetSha256:state.treasure.offsetSha256,language:state.language,edits});else if(editTab==="worlds")state.worlds=await api("/api/worlds/save",{sha256:state.worlds.sha256,edits});else if(editTab==="worldmaps")state.worldMap=await api("/api/world-map/save",{path:state.worldMap.path,sha256:state.worldMap.sha256,edits});else if(editTab==="worldprops")state.worldProps=await api("/api/world-properties/save",{path:state.worldProps.path,sha256:state.worldProps.sha256,edits});else if(editTab==="worldmusic")state.worldMusic=await api("/api/world-music/save",{path:state.worldMusic.path,sha256:state.worldMusic.sha256,edits});else if(editTab==="worldcolors")state.worldColors=await api("/api/world-colors/save",{path:state.worldColors.path,sha256:state.worldColors.sha256,edits:edits.map(entry=>({token:entry.token,hex:entry.values.hex}))});else if(editTab==="worldnav"){const groups=new Map();for(const entry of edits){const row=state.worldNavigation.rows.find(row=>row.token===entry.token);if(!row)continue;const group=groups.get(row.path)||{path:row.path,sha256:row.sha256,edits:[]};group.edits.push(entry);groups.set(row.path,group)}for(const group of groups.values()){const saved=await api("/api/world-navigation/save",{path:group.path,sha256:group.sha256,language:state.language,edits:group.edits});state.worldNavigation.rows=state.worldNavigation.rows.filter(row=>row.path!==group.path).concat(saved.rows)}state.worldNavigation.rows.sort((a,b)=>a.tableId-b.tableId||(a.recordType==="exit"?0:1)-(b.recordType==="exit"?0:1)||a.recordId-b.recordId)}else if(editTab==="animations"){const groups=new Map();for(const entry of edits){const row=state.animations.rows.find(row=>row.token===entry.token);if(!row)continue;const group=groups.get(row.path)||{path:row.path,sha256:row.sha256,edits:[]};group.edits.push(entry);groups.set(row.path,group)}for(const group of groups.values()){const saved=await api("/api/chip-animations/save",{path:group.path,sha256:group.sha256,edits:group.edits});state.animations.rows=state.animations.rows.filter(row=>row.path!==group.path).concat(saved.rows)}state.animations.rows.sort((a,b)=>a.fileId-b.fileId||a.animationId-b.animationId)}else if(editTab==="tilesets"){for(const entry of edits){const row=state.graphicsSets.rows.find(row=>row.token===entry.token);const saved=await api("/api/graphics-sets/save",{path:row.path,sha256:row.sha256,values:entry.values});Object.assign(row,saved)}}else if(editTab==="sprites"){for(const entry of edits){const row=state.spriteHeaders.rows.find(row=>row.token===entry.token);if(!row)continue;const saved=await api("/api/sprite-headers/save",{path:row.path,sha256:row.sha256,values:entry.values});Object.assign(row,saved)}}else if(editTab==="spriteassemblies"){const groups=new Map();for(const entry of edits){const row=state.spriteAssemblies.rows.find(row=>row.token===entry.token);if(!row)continue;const group=groups.get(row.path)||{path:row.path,sha256:row.sha256,edits:[]};group.edits.push(entry);groups.set(row.path,group)}for(const group of groups.values()){const saved=await api("/api/sprite-assemblies/save",{path:group.path,sha256:group.sha256,edits:group.edits});state.spriteAssemblies.rows=state.spriteAssemblies.rows.filter(row=>row.path!==group.path).concat(saved.rows)}state.spriteAssemblies.rows.sort((a,b)=>a.fileId-b.fileId||a.frameId-b.frameId||a.tileId-b.tileId)}else if(editTab==="assemblies"){const groups=new Map();for(const entry of edits){const row=state.assemblies.rows.find(row=>row.token===entry.token);if(!row)continue;const group=groups.get(row.path)||{path:row.path,sha256:row.sha256,edits:[]};group.edits.push(entry);groups.set(row.path,group)}for(const group of groups.values()){const saved=await api("/api/tile-assemblies/save",{path:group.path,sha256:group.sha256,edits:group.edits});state.assemblies.rows=state.assemblies.rows.filter(row=>row.path!==group.path).concat(saved.rows)}state.assemblies.rows.sort((a,b)=>String(a.kind).localeCompare(String(b.kind))||a.fileId-b.fileId||a.tileId-b.tileId||a.corner-b.corner)}else state.palette=await api("/api/palette/save",{path:state.palette.path,sha256:state.palette.sha256,edits:edits.map(entry=>({token:entry.token,hex:entry.values.hex}))});state.dirty.clear();await refreshInfo(false)}catch(error){state.error=error.message;throw error}finally{state.busy=false;render()}}
async function discard(){state.dirty.clear();await loadTab()}
async function switchSource(value){if(dirtyCount())await discard();state.source=String(value)==="vanilla"?"vanilla":"mine";await loadTab()}
async function refreshInfo(draw=true){const [dashboard,changes,map]=await Promise.all([api("/api/dashboard"),api("/api/changes"),api("/api/datamap")]);state.dashboard=dashboard;state.changes=changes.rows;state.dataMap=map;if(draw){state.busy=false;render()}}
async function exportCtp(){state.busy=true;render();try{state.exportResult=await api("/api/export",{});await refreshInfo(false)}catch(error){state.error=error.message}finally{state.busy=false;render()}}
const shell=LexeditorUI.mountShell({host:"#lexeditor-shell",brand:"LEXEDITOR",plugin:{id:"chrono-trigger",name:"Chrono Trigger",themeName:"chrono-trigger",theme:{accent:"#d3a348","accent-text":"#1c1608"}},tabs:TABS,activeTab:()=>state.tab,navigate,help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open Chrono Trigger Data Map",info:()=>navigate("info"),infoActive:()=>state.tab==="info",infoTitle:"Open Chrono Trigger plugin information",projectSources:()=>[{key:"vanilla",label:"Vanilla",path:state.dashboard?.game?.archive||"Installed resources.bin"}],projectActiveSource:()=>state.source,selectProjectSource:switchSource,pendingChanges,dirtyCount,readonly,save,discard});
Promise.all([api("/api/dashboard"),api("/api/datamap"),api("/api/changes")]).then(async([dashboard,map,changes])=>{state.dashboard=dashboard;state.dataMap=map;state.changes=changes.rows;state.language=dashboard.defaultLanguage||"en";await loadTextFiles(false);state.busy=false;render();LexeditorUI.finishPluginLoading()}).catch(error=>{state.busy=false;state.error=error.message;render();LexeditorUI.finishPluginLoading()});
