"""Viewer handedness and editable transforms agree with game coordinates."""
import base64
import functools
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import struct
import threading

import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]


def test_map_handedness_and_gizmo_round_trips(tmp_path):
    def packed(fmt,values):
        return base64.b64encode(struct.pack(fmt,*values)).decode()
    mesh={'positions':packed('<12f',[-3,0,-3,3,0,-3,3,0,3,-3,0,3]),
          'indices':packed('<6I',[0,2,1,0,3,2])}
    parts=[{'key':f'{i}:0','name':name,'kind':kind,'model':name,
            'pos':[x,0,10],'rot':[0,0,0],'scale':[1,1,1]}
           for i,(name,kind,x) in enumerate([('piece','Map piece',0),('high','Collision',-8),
                                            ('low','Collision',0),('nav','Navigation',8)])]
    view={'parts':parts,'models':{p['model']:{'available':True} for p in parts},'lights':[]}
    items={p['model']:{'meshes':[{**mesh,**({'layer':layer} if layer else {})}]}
           for p,layer in zip(parts,[None,'collisionHigh','collisionLow','navigation'])}
    html='''<!doctype html><style>body{margin:0}#v{width:1000px;height:700px;background:#246080}</style>
    <div id="v"></div><script src="/ui/framework.js"></script><script type="importmap">
    {"imports":{"three":"/plugins/ds1/three.module.js","three/addons/controls/OrbitControls.js":"/plugins/ds1/orbit-controls.js",
    "three/addons/controls/TransformControls.js":"/plugins/ds1/transform-controls.js"}}</script>
    <script src="/plugins/ds1/viewport.js"></script>'''
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/review':body=html.encode();kind='text/html'
            elif self.path.startswith('/api/map/geometries'):body=json.dumps({'items':items}).encode();kind='application/json'
            else:return super().do_GET()
            self.send_response(200);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1000,'height':700});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/review')
                page.evaluate('''async view=>{
                  window.moves=[];window.rotations=[];window.accept=true;
                  window.ctl=await Ds1Viewport.mount(document.querySelector('#v'),'fixture',view,{
                    readOnly:false,collision:{high:true,low:true},navigation:true,
                    onMove:(key,pos)=>{moves.push([key,pos]);return accept},
                    onRotate:(key,rot)=>{rotations.push([key,rot]);return accept}});
                }''',view)
                evidence=page.evaluate('''async()=>{
                  const THREE=await import('three'),host=document.querySelector('#v'),scene=host._viewportScene;
                  const camera=host._viewportCamera;
                  const defaultCamera=camera.position.toArray();
                  camera.position.set(0,3,0);camera.lookAt(0,3,-10);camera.updateMatrixWorld(true);
                  // A game camera facing +Z sees +X on its right. The Three
                  // camera faces converted -Z, without mirroring that landmark.
                  const right=host._viewportProject(8,0,10)[0],left=host._viewportProject(-8,0,10)[0];
                  const colors={};scene.traverse(o=>{if(o.isMesh&&o.userData.collisionLayer&&!o.userData.hiddenCollisionFill)
                    colors[o.userData.collisionLayer]=o.material.color.getHexString()});
                  const hazards=[];
                  for(const filter of [13,14,15]){
                    ctl.updateCollision('1:0',filter);ctl.updateCollision('2:0',filter);
                    const pair={};scene.traverse(o=>{if(o.isMesh&&o.userData.collisionLayer&&!o.userData.hiddenCollisionFill)
                      pair[o.userData.collisionLayer]=o.material.color.getHexString()});
                    hazards.push([pair.collisionHigh,pair.collisionLow]);
                  }
                  ctl.select('0:0');const gizmo=scene.children.find(o=>o.isTransformControlsRoot).controls;
                  gizmo.dispatchEvent({type:'mouseDown'});gizmo.dispatchEvent({type:'objectChange'});
                  gizmo.dispatchEvent({type:'mouseUp'});await Promise.resolve();
                  const noOpMoves=moves.length;
                  gizmo.dispatchEvent({type:'mouseDown'});
                  gizmo.object.position.set(6,7,-8);
                  gizmo.dispatchEvent({type:'objectChange'});gizmo.dispatchEvent({type:'mouseUp'});
                  await Promise.resolve();
                  ctl.setGizmoMode('rotate');gizmo.dispatchEvent({type:'mouseDown'});
                  gizmo.object.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),Math.PI/2));
                  gizmo.dispatchEvent({type:'objectChange'});gizmo.dispatchEvent({type:'mouseUp'});
                  await Promise.resolve();
                  ctl.setGizmoMode('translate');window.accept=false;gizmo.dispatchEvent({type:'mouseDown'});
                  gizmo.object.position.x=99;gizmo.dispatchEvent({type:'objectChange'});gizmo.dispatchEvent({type:'mouseUp'});
                  await Promise.resolve();await Promise.resolve();
                  return {right,left,defaultCamera,colors,hazards,noOpMoves,moves,rotations,handle:gizmo.object.position.toArray()};
                }''')
                assert evidence['right']>500>evidence['left']
                assert evidence['defaultCamera'][2]<-10
                assert len(set(evidence['colors'].values()))==3
                assert evidence['colors']['navigation']=='ec6cff'
                assert all(high!=low for high,low in evidence['hazards'])
                assert evidence['noOpMoves']==0
                assert evidence['moves'][0]==['0:0',[6,7,8]]
                assert evidence['rotations'][0][1]==pytest.approx([0,-90,0])
                assert evidence['handle']==pytest.approx([6,7,-8])
                assert not errors,errors
                page.screenshot(path=str(tmp_path/'game-coordinates.png'))
            finally:browser.close()
    finally:server.shutdown();server.server_close()
