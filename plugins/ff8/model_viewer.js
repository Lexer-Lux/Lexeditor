/* Battle geometry uses the shared model stage; this module only draws the mesh. */
window.FF8ModelViewer = function ({file,dataset,label,objectId=null,textureSource=null,frame=0,onReady,onError,initialView={},terrain=null,markers=[],onSelect,onViewChange}) {
  const ui=LexeditorUI,stage=ui.modelStage(),canvas=ui.el('canvas',{tabindex:0,style:'position:absolute;inset:0','aria-label':`${label}: drag or use arrow keys to rotate; wheel or plus and minus to zoom`});
  stage.lexMessage.replaceChildren(ui.loadingPanel({label:'Loading model'}));
  stage.append(canvas);
  const gl=canvas.getContext('webgl',{alpha:true,antialias:true,preserveDrawingBuffer:true});
  if(!gl){stage.lexMessage.textContent='A 3D graphics context is unavailable.';onError?.(new Error(stage.lexMessage.textContent));return stage;}
  const isStage=/^a0stg\d+\.x$/i.test(file),homeYaw=terrain?0:initialView.yaw??(isStage ? .6 : 0),homePitch=terrain?1:initialView.pitch??(isStage ? -.6 : 0);
  const homeZoom=terrain?1.5:.9,maxZoom=terrain?32:4;
  let yaw=initialView.yaw??homeYaw,pitch=initialView.pitch??homePitch,zoom=initialView.zoom??homeZoom,pan=[...(initialView.pan||[0,0])],drag=null,disposed=false,attached=false,program=null;
  const markerViews=[];
  const buffers=[],textures=[],meshes=[],abort=new AbortController();
  const resize=new ResizeObserver(()=>draw());
  const lifetime=new MutationObserver(()=>{if(stage.isConnected)attached=true;else if(attached)dispose();});
  resize.observe(stage);lifetime.observe(document.documentElement,{subtree:true,childList:true});
  function dispose(){if(disposed)return;disposed=true;abort.abort();resize.disconnect();lifetime.disconnect();
    buffers.forEach(buffer=>gl.deleteBuffer(buffer));textures.forEach(texture=>gl.deleteTexture(texture));
    if(program)gl.deleteProgram(program);gl.getExtension('WEBGL_lose_context')?.loseContext();}
  stage.lexDispose=dispose;
  function shader(type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(shader);gl.deleteShader(shader);throw Error(message);}return shader;}
  function draw(picking=false){if(disposed||!program||!stage.isConnected)return;
    const rect=stage.getBoundingClientRect(),ratio=Math.min(window.devicePixelRatio||1,2);
    canvas.width=Math.max(1,Math.round(rect.width*ratio));canvas.height=Math.max(1,Math.round(rect.height*ratio));
    gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.useProgram(program);gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
    gl.uniform4f(gl.getUniformLocation(program,'view'),yaw,pitch,zoom,canvas.width/canvas.height);
    gl.uniform2f(gl.getUniformLocation(program,'pan'),...pan);
    gl.uniform1f(gl.getUniformLocation(program,'picking'),picking?1:0);
    for(const mesh of meshes){gl.bindBuffer(gl.ARRAY_BUFFER,mesh.buffer);
      const attributes=terrain?[['position',3,0],['uv',2,12],['segment',1,20]]:[['position',3,0],['uv',2,12],['normal',3,20],['vertexColor',3,32]];
      for(const [name,size,offset] of attributes){
        const attribute=gl.getAttribLocation(program,name);if(attribute<0)continue;gl.enableVertexAttribArray(attribute);gl.vertexAttribPointer(attribute,size,gl.FLOAT,false,terrain?24:44,offset);}
      gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,mesh.texture);gl.uniform1i(gl.getUniformLocation(program,'image'),0);
      gl.drawArrays(gl.TRIANGLES,0,mesh.count);}
    if(picking)return;
    stage.dataset.rendered='true';stage.dataset.rotation=`${yaw},${pitch}`;stage.dataset.zoom=String(zoom);stage.dataset.pan=pan.join(',');
    onViewChange?.({yaw,pitch,zoom,pan:[...pan]});
    for(const {node,point} of markerViews){
      const cy=Math.cos(yaw),sy=Math.sin(yaw),cx=Math.cos(pitch),sx=Math.sin(pitch);
      const x=cy*point[0]+sy*point[2],z=-sy*point[0]+cy*point[2];
      const y=cx*point[1]-sx*z,depth=3/zoom-(sx*point[1]+cx*z);
      const px=(x+pan[0])*1.732/(canvas.width/canvas.height)/depth,py=(y+pan[1])*1.732/depth;
      node.hidden=depth<=.001||Math.abs(px)>1||Math.abs(py)>1;
      node.style.left=`${(px+1)*50}%`;node.style.top=`${(1-py)*50}%`;
    }
  }
  function texture(color){const value=gl.createTexture();textures.push(value);gl.bindTexture(gl.TEXTURE_2D,value);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array(color||[180,195,215,255]));
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);return value;}
  canvas.addEventListener('contextmenu',event=>{if(terrain)event.preventDefault();});
  canvas.addEventListener('pointerdown',event=>{if(event.button!==0&&!(terrain&&event.button===2))return;drag={x:event.clientX,y:event.clientY,startX:event.clientX,startY:event.clientY,pan:terrain&&(event.button===2||event.shiftKey),moved:false};canvas.setPointerCapture(event.pointerId);canvas.classList.add('dragging');canvas.focus();});
  canvas.addEventListener('pointermove',event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
    drag.moved ||= Math.hypot(event.clientX-drag.startX,event.clientY-drag.startY)>3;
    if(drag.pan){const scale=3.5/zoom/Math.max(1,stage.clientHeight);pan[0]+=dx*scale;pan[1]-=dy*scale;}
    else{yaw+=dx*.012;pitch=Math.max(-1.5,Math.min(1.5,pitch+dy*.012));}drag.x=event.clientX;drag.y=event.clientY;draw();});
  canvas.addEventListener('pointerup',event=>{if(!terrain||!onSelect||!drag||drag.moved||drag.pan||!program)return;
    const box=canvas.getBoundingClientRect(),pixel=new Uint8Array(4);
    draw(true);gl.readPixels(Math.floor((event.clientX-box.left)/box.width*canvas.width),Math.floor((box.bottom-event.clientY)/box.height*canvas.height),1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);draw();
    const id=pixel[0]+pixel[1]*256-1;if(pixel[3]&&id>=0&&id<768)onSelect(id);});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(type,()=>{drag=null;canvas.classList.remove('dragging');});
  canvas.addEventListener('wheel',event=>{event.preventDefault();zoom=Math.max(.2,Math.min(maxZoom,zoom*Math.exp(-event.deltaY*.001)));draw();},{passive:false});
  canvas.addEventListener('keydown',event=>{const previousYaw=yaw,previousPitch=pitch;let used=true;switch(event.key){case'ArrowLeft':yaw-=.1;break;case'ArrowRight':yaw+=.1;break;case'ArrowUp':pitch-=.1;break;case'ArrowDown':pitch+=.1;break;case'+':case'=':zoom*=1.1;break;case'-':zoom/=1.1;break;case'Home':yaw=homeYaw;pitch=homePitch;zoom=.9;break;default:used=false;}
    if(terrain&&event.shiftKey&&event.key.startsWith('Arrow')){yaw=previousYaw;pitch=previousPitch;
      if(event.key==='ArrowLeft')pan[0]-=.1/zoom;if(event.key==='ArrowRight')pan[0]+=.1/zoom;if(event.key==='ArrowUp')pan[1]+=.1/zoom;if(event.key==='ArrowDown')pan[1]-=.1/zoom;}
    if(event.key==='Home'){zoom=homeZoom;pan=[0,0];}
    if(used){event.preventDefault();event.stopPropagation();pitch=Math.max(-1.5,Math.min(1.5,pitch));zoom=Math.max(.2,Math.min(maxZoom,zoom));draw();}});
  (async()=>{try{
    if(terrain){
      const response=await fetch(terrain.mesh,{signal:abort.signal});if(!response.ok)throw Error('Could not load the world terrain');
      const data=new Float32Array(await response.arrayBuffer());if(disposed)return;
      if(!data.length||data.length%18)throw Error('The world terrain mesh is incomplete');
      const minimum=[Infinity,Infinity,Infinity],maximum=[-Infinity,-Infinity,-Infinity];
      for(let i=0;i<data.length;i+=6)for(let axis=0;axis<3;axis++){minimum[axis]=Math.min(minimum[axis],data[i+axis]);maximum[axis]=Math.max(maximum[axis],data[i+axis]);}
      const center=minimum.map((value,index)=>(value+maximum[index])/2),radius=Math.max(...maximum.map((value,index)=>(value-minimum[index])/2),.001);
      const markerSegments=new Map(markers.map(marker=>[Math.floor(marker.y*24)*32+Math.floor(marker.x*32),[]]));
      for(let i=0;i<data.length;i+=18)markerSegments.get(data[i+5])?.push(i);
      for(const marker of markers){
        const x=marker.x*128,z=marker.y*96,id=Math.floor(z/4)*32+Math.floor(x/4);let height=0;
        for(const i of markerSegments.get(id)||[]){
          const ax=data[i],az=data[i+2],bx=data[i+6],bz=data[i+8],cx=data[i+12],cz=data[i+14];
          const denominator=(bz-cz)*(ax-cx)+(cx-bx)*(az-cz);if(Math.abs(denominator)<1e-8)continue;
          const a=((bz-cz)*(x-cx)+(cx-bx)*(z-cz))/denominator,b=((cz-az)*(x-cx)+(ax-cx)*(z-cz))/denominator,c=1-a-b;
          if(a>=-.001&&b>=-.001&&c>=-.001)height=Math.max(height,a*data[i+1]+b*data[i+7]+c*data[i+13]);
        }
        const node=ui.el('button',{type:'button',class:`lex-image-map-point ${marker.selected?'selected':''} ${marker.className||''}`,'aria-label':marker.label,title:marker.label,onclick:event=>{event.stopPropagation();marker.activate?.();}});
        stage.append(node);markerViews.push({node,point:[(x-center[0])/radius,(height+.03-center[1])/radius,-(z-center[2])/radius]});
      }
      for(let i=0;i<data.length;i+=6){data[i]=(data[i]-center[0])/radius;data[i+1]=(data[i+1]-center[1])/radius;data[i+2]=-(data[i+2]-center[2])/radius;}
      const vertex=shader(gl.VERTEX_SHADER,`attribute vec3 position;attribute vec2 uv;attribute float segment;uniform vec4 view;uniform vec2 pan;varying vec2 tex;varying float cell;
        void main(){float cy=cos(view.x),sy=sin(view.x),cx=cos(view.y),sx=sin(view.y);vec3 q=vec3(cy*position.x+sy*position.z,position.y,-sy*position.x+cy*position.z);vec3 p=vec3(q.x,cx*q.y-sx*q.z,sx*q.y+cx*q.z);float depth=3./view.z-p.z;gl_Position=vec4((p.x+pan.x)*1.732/view.w,(p.y+pan.y)*1.732,1.00002*depth-.002,depth);tex=uv;cell=segment+1.;}`);
      const fragment=shader(gl.FRAGMENT_SHADER,`precision highp float;varying vec2 tex;varying float cell;uniform sampler2D image;uniform float picking;void main(){vec4 color=texture2D(image,tex);if(color.a<.5)discard;gl_FragColor=picking>.5?vec4(mod(cell,256.)/255.,floor(cell/256.)/255.,0.,1.):color;}`);
      program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);gl.deleteShader(vertex);gl.deleteShader(fragment);
      if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
      const buffer=gl.createBuffer();buffers.push(buffer);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
      const tex=texture();meshes.push({buffer,texture:tex,count:data.length/6});
      const imageResponse=await fetch(terrain.atlas,{signal:abort.signal});if(!imageResponse.ok)throw Error('Could not load the world textures');
      const image=await createImageBitmap(await imageResponse.blob());if(disposed){image.close();return;}
      gl.bindTexture(gl.TEXTURE_2D,tex);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);image.close();
      stage.lexMessage.hidden=true;stage.dataset.texturesReady='true';draw();onReady?.(canvas,{terrain:true});return;
    }
    const response=await fetch(`/api/model-scene?file=${encodeURIComponent(file)}&dataset=${encodeURIComponent(dataset)}${objectId==null?'':`&object=${encodeURIComponent(objectId)}`}${textureSource==null?'':`&textureSource=${encodeURIComponent(textureSource)}`}&frame=${encodeURIComponent(frame)}`,{signal:abort.signal});
    const scene=await response.json();if(!response.ok)throw Error(scene.error||'Could not decode this model');if(disposed)return;
    const vertex=shader(gl.VERTEX_SHADER,`attribute vec3 position;attribute vec2 uv;attribute vec3 normal;attribute vec3 vertexColor;uniform vec4 view;varying vec2 tex;varying float light;varying vec3 tint;
      vec3 rotate(vec3 p){float cy=cos(view.x),sy=sin(view.x),cx=cos(view.y),sx=sin(view.y);vec3 q=vec3(cy*p.x+sy*p.z,p.y,-sy*p.x+cy*p.z);return vec3(q.x,cx*q.y-sx*q.z,sx*q.y+cx*q.z);}
      void main(){vec3 p=rotate(position);gl_Position=vec4(p.x*view.z/view.w,p.y*view.z,p.z*.25,1.);tex=uv;tint=vertexColor;light=.45+.55*abs(dot(rotate(normal),normalize(vec3(.3,.5,1.))));}`);
    const fragment=shader(gl.FRAGMENT_SHADER,`precision mediump float;varying vec2 tex;varying float light;varying vec3 tint;uniform sampler2D image;void main(){vec4 color=texture2D(image,tex);if(color.a<.5)discard;gl_FragColor=vec4(color.rgb*light*tint,color.a);}`);
    program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);gl.deleteShader(vertex);gl.deleteShader(fragment);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
    const minimum=[Infinity,Infinity,Infinity],maximum=[-Infinity,-Infinity,-Infinity];
    for(const point of scene.positions)point.forEach((value,index)=>{minimum[index]=Math.min(minimum[index],value);maximum[index]=Math.max(maximum[index],value);});
    const center=minimum.map((value,index)=>(value+maximum[index])/2),radius=Math.max(...maximum.map((value,index)=>(value-minimum[index])/2),.001);
    const groups=new Map();for(const face of scene.triangles){const values=groups.get(face.texture)||[];groups.set(face.texture,values);
      const points=face.indices.map(index=>scene.positions[index].map((value,axis)=>(value-center[axis])/radius));
      const a=points[1].map((value,index)=>value-points[0][index]),b=points[2].map((value,index)=>value-points[0][index]);
      const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],length=Math.hypot(...n)||1;
      points.forEach((point,index)=>values.push(...point,...face.uv[index],...n.map(value=>value/length),...(face.colors?.[index]||[1,1,1])));}
    const loads=[];
    for(const [index,values] of groups){const buffer=gl.createBuffer();buffers.push(buffer);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);
      const rgb=-index-2,color=index<-1?[(rgb&255),(rgb>>8)&255,(rgb>>16)&255,255]:null;
      const tex=texture(color);meshes.push({buffer,texture:tex,count:values.length/11});if(index<0)continue;
      loads.push(new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>{if(!disposed){gl.bindTexture(gl.TEXTURE_2D,tex);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);draw();}resolve();};image.onerror=()=>reject(new Error(`Could not load texture ${index+1} for ${file}.`));
        image.src=scene.textureImages?.[index]||`/assets/texture.png?id=${encodeURIComponent(`battle/${file}#${scene.textures[index]}`)}&palette=${scene.texturePalettes?.[index]??0}&dataset=${encodeURIComponent(dataset)}`;}));}
    stage.lexMessage.hidden=true;draw();await Promise.all(loads);if(!disposed){stage.dataset.texturesReady='true';draw();onReady?.(canvas,scene);}
  }catch(error){if(!disposed){stage.lexMessage.replaceChildren(ui.detailNote(error.message));stage.lexMessage.hidden=false;stage.dataset.error=error.message;onError?.(error);}}})();
  return stage;
};

// Cards share bounded snapshots of the same renderer used by the model drawer.
// Only one temporary WebGL context is active, even across eight formations.
(() => {
  const cache=new Map(),pending=new Map();
  let queue=Promise.resolve();
  function portrait(canvas){
    const copy=document.createElement('canvas');copy.width=canvas.width;copy.height=canvas.height;
    const ctx=copy.getContext('2d');ctx.drawImage(canvas,0,0);
    const pixels=ctx.getImageData(0,0,copy.width,copy.height).data;
    let left=copy.width,top=copy.height,right=-1,bottom=-1;
    for(let y=0;y<copy.height;y++)for(let x=0;x<copy.width;x++)if(pixels[(y*copy.width+x)*4+3]){
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
    }
    if(right<left)throw Error('The model rendered no visible geometry');
    const cropped=document.createElement('canvas'),padding=6;
    cropped.width=right-left+1+padding*2;cropped.height=bottom-top+1+padding*2;
    cropped.getContext('2d').drawImage(copy,left,top,right-left+1,bottom-top+1,
      padding,padding,right-left+1,bottom-top+1);
    return cropped.toDataURL('image/png');
  }
  async function snapshot(options){
    let stage,timer;
    try{
      return await new Promise((resolve,reject)=>{
        timer=setTimeout(()=>reject(new Error('Model preview timed out')),15000);
        stage=FF8ModelViewer({...options,initialView:/^a0stg\d+\.x$/i.test(options.file)?{}:{yaw:.55,pitch:.15},onReady:canvas=>resolve(portrait(canvas)),onError:reject});
        stage.style.cssText='position:fixed;left:-10000px;top:0;width:192px;height:192px;min-height:0;visibility:hidden;pointer-events:none';
        stage.setAttribute('aria-hidden','true');
        document.body.append(stage);
      });
    }finally{clearTimeout(timer);stage?.lexDispose?.();stage?.remove();}
  }
  window.FF8ModelThumbnail = options => {
    const image=LexeditorUI.el('img',{alt:`${options.label} model`,class:'ff8-model-thumbnail lex-image-pending'});
    const key=JSON.stringify([options.dataset,options.file,options.revision]);
    // Wait for the card to mount before scheduling work. Discard queued work
    // when every card waiting for it has left the page.
    requestAnimationFrame(async()=>{
      if(!image.isConnected)return;
      try{
        let source=cache.get(key);
        if(source){cache.delete(key);cache.set(key,source);}
        else{
          let job=pending.get(key);
          if(!job){
            job={images:[]};
            job.promise=queue.then(async()=>{
              if(!job.images.some(node=>node.isConnected))return null;
              const result=await snapshot(options);
              cache.set(key,result);
              while(cache.size>32)cache.delete(cache.keys().next().value);
              return result;
            }).finally(()=>pending.delete(key));
            queue=job.promise.catch(()=>{});
            pending.set(key,job);
          }
          job.images.push(image);
          source=await job.promise;
        }
        if(image.isConnected&&source){image.src=source;image.dataset.modelReady='true';image.classList.remove('lex-image-pending');}
      }catch(_error){if(image.isConnected)image.replaceWith(LexeditorUI.noImage('Model preview unavailable'));}
    });
    return image;
  };
})();
