"use strict";
  // Undeclared columns size to their longest value, and Warband's ids and mesh
  // names are long enough to push the table past its panel and cut the last
  // column in half. Bounded widths let the long ones ellipsise instead.
  function itemColumns(){return [{key:"name",label:"Name",width:"minmax(9em,1.4fr)",render:row=>el("span",{title:row.name},row.name)},{key:"id",label:"ID",width:"minmax(6em,.8fr)"},{key:"type",label:"Type",width:"minmax(6em,.7fr)"},{key:"inventoryMesh",label:"Inventory mesh",width:"minmax(7em,1fr)"}];}
  function renderItems(){
    const view="items",columns=itemColumns(),query=state.filters.items||"";
    const filtered=sorted(search(state.items.rows,query,["name","id","type","inventoryMesh"]),view);
    $("#toolbar").replaceChildren();
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec("items",item=>Object.keys(state.itemEdits[itemEditKey(item)]?.fields||{}).length>0),rows:filtered,key:row=>row.id,slots:false,fit:{minRowHeight:36},page:state.pages.items,pageSize:state.pageSizes.items,selected:state.selectedItem,noun:"items",splitKey:"warband-items",className:"warband-paged-table warband-items",defaultSplit:43,
      search:{key:"warband-items",value:query,placeholder:"Search items…",change:value=>{state.filters.items=value;state.pages.items=0;renderItems();}},
      master:({rows,selected,select})=>columnList({rows,key:row=>row.id,columns:columns.map(column=>({...column,sortable:true})),sortState:{key:state.sorts.items[0],dir:state.sorts.items[1]},sort:key=>sort("items",key),selected,selectedClass:"selected",select,class:"warband-record-list","aria-label":"Warband items"}),
      detail:()=>warbandItemDetail(state.items.rows.find(row=>row.id===state.selectedItem)),sync:next=>{state.pages.items=next.page;state.pageSizes.items=next.pageSize;state.selectedItem=next.selected||"";},change:next=>{state.pages.items=next.page;state.pageSizes.items=next.pageSize;state.selectedItem=next.selected||"";renderItems();}}));
  }

  function warbandEyeIcon(){
    const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("width","22");svg.setAttribute("height","22");
    const path=document.createElementNS(ns,"path");path.setAttribute("fill","none");path.setAttribute("stroke","currentColor");path.setAttribute("stroke-width","1.8");path.setAttribute("d","M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z");svg.append(path);return svg;
  }

  function disposeWarbandPreview(){
    if(window.__warbandPreview){window.__warbandPreview.forEach(controller=>controller.dispose());delete window.__warbandPreview;}
  }
  function itemEditKey(item){return String(item.recordIndex??item.line??item.id);}
  function effectiveItemField(item,key){return state.itemEdits[itemEditKey(item)]?.fields?.[key]??item.fields?.[key]??"";}
  function setItemField(item,key,value){
    const recordKey=itemEditKey(item),base=String(item.fields?.[key]??""),next=String(value);
    if(next===base){const existing=state.itemEdits[recordKey];if(existing?.fields)delete existing.fields[key];if(existing&&!Object.keys(existing.fields).length)delete state.itemEdits[recordKey];}
    else{const existing=state.itemEdits[recordKey]||(state.itemEdits[recordKey]={recordIndex:item.recordIndex,originalId:item.id,fields:{}});existing.fields[key]=next;}
    shell.refresh();
  }
  function itemTypeFromFlags(flags){return (String(flags).match(/\bitp_type_([a-z0-9_]+)/i)||[])[1]||"";}
  function setItemType(item,value){
    const clean=String(value).trim().replace(/^itp_type_/i,""),flags=String(effectiveItemField(item,"flags"));if(!clean)return;
    const token=`itp_type_${clean}`,next=/\bitp_type_[a-z0-9_]+/i.test(flags)?flags.replace(/\bitp_type_[a-z0-9_]+/i,token):(flags.trim()?`${token}|${flags}`:token);
    setItemField(item,"flags",next);const control=document.querySelector('[data-lex-property="flags"] textarea');if(control)control.value=next;
  }
  function itemWeightFromStats(stats){return (String(stats).match(/\bweight\(([^)]+)\)/)||[])[1]?.trim()||"";}
  function setItemWeight(item,value){
    const clean=String(value).trim();if(!clean)return;const stats=String(effectiveItemField(item,"stats"));
    const next=/\bweight\([^)]+\)/.test(stats)?stats.replace(/\bweight\([^)]+\)/,`weight(${clean})`):(stats.trim()?`weight(${clean})|${stats}`:`weight(${clean})`);
    setItemField(item,"stats",next);const control=document.querySelector('[data-lex-property="stats"] textarea');if(control)control.value=next;
  }
  const ITEM_HELP={
    id:"Module System identifier referenced by troops, shops, scripts, and other records. Renaming it here does not rewrite those references.",
    name:"Player-facing item name compiled into the module's item data.",
    type:"The itp_type_* flag defines the item's fundamental equipment/use class and changes how Warband interprets its other stats.",
    value:"Base item price before merchant, trade-skill, abundance, and other economy adjustments.",
    weight:"Inventory/equipment weight from the weight(...) stat macro; Warband uses it for encumbrance and other weight-sensitive behavior.",
    meshes:"Meshes used to render the item. The first mesh is also the source for Lexeditor's generated inventory icon.",
    flags:"Item behavior flags control equipment class, merchandise/civilian availability, handedness, and other engine behavior.",
    capabilities:"Weapon capability expression controlling supported attacks and animations; non-weapons commonly leave this at zero.",
    stats:"Gameplay stat macros for weight, abundance, armor, speed, reach, damage, ammunition, and related item values.",
    modifierBits:"Controls which generated item modifiers such as rusty, balanced, masterwork, or lordly may apply.",
    factions:"Optional faction list restricting where merchandise for this item may appear."
  };
  function itemExpressionControl(item,key){return LexeditorUI.codeField({value:effectiveItemField(item,key),oninput:event=>setItemField(item,key,event.target.value)});}
  function itemFieldLabel(key){return ({meshes:"Meshes",flags:"Flags",capabilities:"Capabilities",value:"Value",stats:"Stats",modifierBits:"Modifier bits",factions:"Factions"})[key]||key.replace(/^extra/,"Extra field ");}
  function warbandItemDetail(item){
    disposeWarbandPreview();
    if(!item)return detailPanel({className:"warband-item-detail",title:"Select an item"});
    const thumbnail=LexeditorUI.iconSlot({className:"warband-item-thumbnail",message:item.inventoryMesh?"Preparing icon…":"No mesh"}),thumbnailMessage=thumbnail.lexMessage;
    const readOnly=state.activeSource!=="mine";
    const core=detailGroup({title:"Item",body:[
      detailField({label:"ID",property:"id",dataType:"STRING",description:ITEM_HELP.id,control:el("input",{value:effectiveItemField(item,"id"),disabled:readOnly,oninput:event=>setItemField(item,"id",event.target.value)})}),
      detailField({label:"Name",property:"name",dataType:"STRING",description:ITEM_HELP.name,control:el("input",{value:effectiveItemField(item,"name"),disabled:readOnly,oninput:event=>setItemField(item,"name",event.target.value)})}),
      detailField({label:"Type",property:"type",dataType:"STRING",description:ITEM_HELP.type,control:el("input",{value:itemTypeFromFlags(effectiveItemField(item,"flags")),disabled:readOnly,onchange:event=>setItemType(item,event.target.value)})}),
      detailField({label:"Value",property:"value",dataType:"EXPR",description:ITEM_HELP.value,control:el("input",{value:effectiveItemField(item,"value"),disabled:readOnly,oninput:event=>setItemField(item,"value",event.target.value)})}),
      detailField({label:"Weight",property:"weight",dataType:"FLOAT",description:ITEM_HELP.weight,control:el("input",{type:"number",step:"any",value:itemWeightFromStats(effectiveItemField(item,"stats")),disabled:readOnly,onchange:event=>setItemWeight(item,event.target.value)})})
    ]});
    const sourceFields=(item.fieldOrder||[]).filter(key=>!["id","name","value"].includes(key));
    const source=detailGroup({title:"Module System fields",body:sourceFields.map(key=>detailField({label:itemFieldLabel(key),property:key,dataType:"EXPR",description:ITEM_HELP[key]||"",control:(()=>{const control=itemExpressionControl(item,key);control.disabled=readOnly;return control;})()}))});
    // The heading icon is the shared 3D viewer control: pressing it slides the
    // model out of the panel, and the same slot carries the close mark. The
    // panel had the icon and the renderer but never the control, so the viewer
    // was there and unreachable.
    const detail=detailPanel({className:"warband-item-detail",icon:thumbnail,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(item.name,24)),identity:item.id,body:[core,source],
      modelPreview:item.inventoryMesh?{
        label:`${item.name} model`,
        openLabel:`Open the ${item.name} model`,
        closeLabel:`Close the ${item.name} model`,
        content:warbandPreviewStage(item),
      }:null});
    if(item.inventoryMesh)requestAnimationFrame(()=>loadWarbandIcon(item,detail,thumbnail,thumbnailMessage));
    return detail;
  }
  // The drawer's own stage. The icon in the heading stays a still thumbnail;
  // this is the turnable model behind it.
  function warbandPreviewStage(item){
    const stage=LexeditorUI.modelStage({className:"warband-preview-stage",busy:Boolean(item.inventoryMesh),message:"This item has no inventory mesh."}),message=stage.lexMessage;
    if(item.inventoryMesh)requestAnimationFrame(()=>loadWarbandIcon(item,stage,stage,message));
    return stage;
  }

  async function loadWarbandIcon(item,detail,thumbnail,message){
    const url=`/api/item-icon?mesh=${encodeURIComponent(item.inventoryMesh)}`;
    try{
      while(detail.isConnected){
        const response=await fetch(url);
        if(!detail.isConnected)return;
        if(response.status===202){await new Promise(resolve=>setTimeout(resolve,750));continue;}
        if(!response.ok){const error=await response.json();throw new Error(error.error||"Icon unavailable");}
        const blob=await response.blob();if(!detail.isConnected)return;
        const objectUrl=URL.createObjectURL(blob),image=el("img",{alt:`${item.name} inventory icon`});
        image.onload=image.onerror=()=>URL.revokeObjectURL(objectUrl);image.src=objectUrl;thumbnail.replaceChildren(image);return;
      }
    }catch(error){if(detail.isConnected){message.textContent="Icon unavailable";message.title=error.message;}}
  }

  async function createWarbandRenderer(canvas,data,interactive=true){
    const image=new Image();if(!data.texture)throw new Error("The material has no resolved texture.");
    await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error("The Warband DDS texture could not be loaded."));image.src=data.texture;});
    const gl=canvas.getContext("webgl2",{antialias:true,alpha:false});if(!gl)throw new Error("This window cannot start the WebGL 2 model renderer.");
    const compile=(type,source)=>{const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(shader));return shader;};
    const vertex=compile(gl.VERTEX_SHADER,`#version 300 es\nin vec3 aPosition;in vec3 aNormal;in vec2 aUv;uniform float uYaw,uPitch,uZoom,uAspect;out vec3 vNormal;out vec2 vUv;vec3 ry(vec3 v,float a){float c=cos(a),s=sin(a);return vec3(c*v.x+s*v.z,v.y,-s*v.x+c*v.z);}vec3 rx(vec3 v,float a){float c=cos(a),s=sin(a);return vec3(v.x,c*v.y-s*v.z,s*v.y+c*v.z);}void main(){vec3 p=rx(ry(aPosition,uYaw),uPitch),n=rx(ry(aNormal,uYaw),uPitch);vNormal=n;vUv=aUv;gl_Position=vec4(p.x*uZoom/uAspect,p.y*uZoom,p.z*.25,1.0);}`);
    const fragment=compile(gl.FRAGMENT_SHADER,`#version 300 es\nprecision highp float;in vec3 vNormal;in vec2 vUv;uniform sampler2D uDiffuse;uniform float uHasTexture;out vec4 outColor;vec3 linearize(vec3 c){return pow(max(c,vec3(0.0)),vec3(2.2));}void main(){vec3 n=normalize(vNormal);if(!gl_FrontFacing)n=-n;vec3 base=mix(vec3(.55,.48,.36),linearize(texture(uDiffuse,vUv).rgb),uHasTexture);float key=max(dot(n,normalize(vec3(-.3,.7,.65))),0.0),fill=max(dot(n,normalize(vec3(.7,.2,.5))),0.0);vec3 color=base*(.28+.82*key+.20*fill);color=color/(color+vec3(.62));outColor=vec4(pow(color,vec3(1.0/2.2)),1.0);}`);
    const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
    const g=data.geometry,b=g.bounds,center=b.min.map((value,index)=>(value+b.max[index])/2),largest=Math.max(...b.max.map((value,index)=>value-b.min[index]),.0001),scale=1.8/largest;
    const positions=new Float32Array(g.positions.length*3),normals=new Float32Array(g.normals.length*3),uvs=new Float32Array(g.texCoords.length*2);g.positions.forEach((row,index)=>{positions[index*3]=(row[0]-center[0])*scale;positions[index*3+1]=(row[2]-center[2])*scale;positions[index*3+2]=-(row[1]-center[1])*scale;});g.normals.forEach((row,index)=>{normals[index*3]=row[0];normals[index*3+1]=row[2];normals[index*3+2]=-row[1];});g.texCoords.forEach((row,index)=>{uvs[index*2]=row[0];uvs[index*2+1]=row[1];});
    const vao=gl.createVertexArray();gl.bindVertexArray(vao);const buffers=[];const attribute=(name,size,data)=>{const location=gl.getAttribLocation(program,name),buffer=gl.createBuffer();buffers.push(buffer);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,size,gl.FLOAT,false,0,0);};attribute("aPosition",3,positions);attribute("aNormal",3,normals);attribute("aUv",2,uvs);const indices=new Uint32Array(g.triangles.flat()),indexBuffer=gl.createBuffer();buffers.push(indexBuffer);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,indexBuffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);
    const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([170,148,112,255]));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.generateMipmap(gl.TEXTURE_2D);let hasTexture=0;if(data.texture){gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);gl.generateMipmap(gl.TEXTURE_2D);hasTexture=1;}
    const uniform=name=>gl.getUniformLocation(program,name),yawU=uniform("uYaw"),pitchU=uniform("uPitch"),zoomU=uniform("uZoom"),aspectU=uniform("uAspect"),hasTextureU=uniform("uHasTexture");let yaw=0,pitch=-.18,zoom=1,dragging=false,lastX=0,lastY=0,disposed=false;
    const draw=()=>{if(disposed)return;const rect=canvas.getBoundingClientRect(),ratio=Math.min(devicePixelRatio||1,2),width=Math.max(1,Math.floor(rect.width*ratio)),height=Math.max(1,Math.floor(rect.height*ratio));if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}gl.viewport(0,0,width,height);gl.clearColor(.07,.055,.035,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.useProgram(program);gl.uniform1f(yawU,yaw);gl.uniform1f(pitchU,pitch);gl.uniform1f(zoomU,zoom);gl.uniform1f(aspectU,width/height);gl.uniform1f(hasTextureU,hasTexture);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);gl.bindVertexArray(vao);gl.drawElements(gl.TRIANGLES,indices.length,gl.UNSIGNED_INT,0);};
    const down=event=>{dragging=true;lastX=event.clientX;lastY=event.clientY;canvas.classList.add("dragging");canvas.setPointerCapture(event.pointerId);},move=event=>{if(!dragging)return;yaw+=(event.clientX-lastX)*.012;pitch=Math.max(-1.45,Math.min(1.45,pitch+(event.clientY-lastY)*.012));lastX=event.clientX;lastY=event.clientY;draw();},up=event=>{dragging=false;canvas.classList.remove("dragging");if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId);},wheel=event=>{event.preventDefault();zoom=Math.max(.35,Math.min(2.8,zoom*Math.exp(-event.deltaY*.001)));draw();};const reset=()=>{yaw=0;pitch=-.18;zoom=1;draw();};if(interactive){canvas.addEventListener("pointerdown",down);canvas.addEventListener("pointermove",move);canvas.addEventListener("pointerup",up);canvas.addEventListener("pointercancel",up);canvas.addEventListener("wheel",wheel,{passive:false});canvas.addEventListener("dblclick",reset);}let observerFrame=0;const observer=new ResizeObserver(()=>{if(observerFrame)cancelAnimationFrame(observerFrame);observerFrame=requestAnimationFrame(()=>{observerFrame=0;draw();});});observer.observe(canvas);requestAnimationFrame(draw);
    return{dispose(){disposed=true;observer.disconnect();if(observerFrame)cancelAnimationFrame(observerFrame);for(const [event,handler] of [["pointerdown",down],["pointermove",move],["pointerup",up],["pointercancel",up],["wheel",wheel],["dblclick",reset]])canvas.removeEventListener(event,handler);gl.deleteShader(vertex);gl.deleteShader(fragment);buffers.forEach(buffer=>gl.deleteBuffer(buffer));gl.deleteTexture(texture);gl.deleteVertexArray(vao);gl.deleteProgram(program);}};
  }
