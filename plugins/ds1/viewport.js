"use strict";
// 3D map view. Geometries are shared across placements; each part only
// adds a transform. Clicking a placement selects it, the gizmo drags it,
// and editor.js commits the move. Collision and navigation geometry is baked
// in world space in the Havok packfiles, which this version does not decode,
// so those parts are counted, never drawn. Mounted by editor.js, which owns
// the page and the edit bar. Map lights draw as small marker
// octahedra; see the lights loop below.
window.Ds1Viewport = (() => {
  let session = 0;
  const DEG = Math.PI / 180;
  // MSB rotation application order; axis-aligned pieces render the same
  // under any order, so multi-axis rotations are the unverified case.
  const ORDER = "XYZ";
  // Base64 straight into bytes: atob plus a charCodeAt pass over
  // some 200MB of geometry showed up in map opens, and one pass over
  // the encoded text decodes several times faster. Inputs are the
  // server's own padded base64, always a multiple of four chars.
  const B64TABLE = (() => {
    const table = new Uint8Array(256).fill(255);
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    for (let i = 0; i < chars.length; i++) table[chars.charCodeAt(i)] = i;
    table[61] = 0;
    return table;
  })();
  function b64(text) {
    const length = text.length;
    const pad = length >= 2 && text.charCodeAt(length - 1) === 61
      ? (text.charCodeAt(length - 2) === 61 ? 2 : 1) : 0;
    const out = new Uint8Array((length * 3 >> 2) - pad);
    let at = 0;
    for (let i = 0; i < length; i += 4) {
      const a = B64TABLE[text.charCodeAt(i)], b = B64TABLE[text.charCodeAt(i + 1)];
      const c = B64TABLE[text.charCodeAt(i + 2)], d = B64TABLE[text.charCodeAt(i + 3)];
      out[at++] = (a << 2) | (b >> 4);
      if (at < out.length) out[at++] = ((b & 15) << 4) | (c >> 2);
      if (at < out.length) out[at++] = ((c & 3) << 6) | d;
    }
    return out;
  }
  const f32 = text => {
    const bytes = b64(text);
    return new Float32Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 4));
  };
  const u32 = text => {
    const bytes = b64(text);
    return new Uint32Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 4));
  };
  function stop(host) {
    if (host && host._viewportStop) {
      try { host._viewportStop(); } catch (_ignored) {}
      delete host._viewportStop;
    }
  }
  // hooks: {readOnly, onSelect(key, info|null), onMove(key, pos),
  // onRotate(key, rot), requestMod()}. Commits resolve false when refused,
  // and the part snaps back. Returns a controller with select(key),
  // moveTo(key, pos), turnTo(key, rot), setGizmoMode(mode), aim() and dispose().
  async function mount(host, mapId, view, hooks = {}) {
    stop(host);
    const mine = ++session;
    if (!host.isConnected || !view) return null;
    const loading=LexeditorUI.loadingPanel({label:`Loading ${view.parts.length} parts`});host.replaceChildren(loading);
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    const {TransformControls} = await import("three/addons/controls/TransformControls.js");
    if (mine !== session || !host.isConnected) return null;
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.viewport = "true";
    const viewModes = LexeditorUI.modelViewModes(host);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 10000);
    camera.position.set(0, 30, 60);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(1, 2, 1);
    scene.add(sun);
    const front = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0, side: THREE.FrontSide});
    const double = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0, side: THREE.DoubleSide});
    // Skyboxes enclose the map, so framing skips them; with the
    // winding fix they render correctly from inside like any mesh.
    // Matched by material name, the only sky signal in the format.
    const isSky = mesh => (mesh.mat_def || "").toLowerCase().includes("sky");
    // Additive-blend effects (light shafts, clouds, glows) are transparent
    // in the game; opaque here they would occlude the map.
    const isEffect = mesh => (mesh.mat_def || "").toLowerCase().includes("_add");
    // Alpha-test (_Alp) materials are cutouts in the game: foliage
    // leaves and damage, stain and water decals floating just above
    // a surface. Opaque here they draw their empty texels as black
    // quads and fight the surface beneath (a fully transparent
    // Depths decal drew black everywhere), so textured ones cut at
    // half alpha and sit slightly above their surface. Untextured
    // ones stay solid, as before.
    const isCutout = mesh => (mesh.mat_def || "").toLowerCase().includes("_alp");
    const effect = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 1, metalness: 0,
      side: THREE.DoubleSide, transparent: true, opacity: 0.25, depthWrite: false});
    // Water shaders ([We]) name no diffuse, only a bump map, so the
    // gray fallback lit by the rig rendered lakes and sewers flat
    // white. Translucent blue reads as water and stays out of the way.
    const isWater = mesh => (mesh.mat_def || "").toLowerCase().includes("water");
    const water = new THREE.MeshStandardMaterial({color: 0x2f6f9e, roughness: 0.35, metalness: 0,
      side: THREE.DoubleSide, transparent: true, opacity: 0.65, depthWrite: false});
    // One texture per diffuse name AND content: two models in one map
    // can wear different bytes under one name (an object keeps its own
    // binder texture while a piece resolves the same name from the area
    // archive), so the cache keys on both. Identical bytes still load
    // once and placements keep sharing materials as before.
    const texCache = new Map();
    const matCache = new Map();
    // Short content digest for cache keys: length plus djb2 over the
    // base64 PNG. Collisions across a map's handful of textures are
    // not a practical concern; exact bytes would bloat every key.
    const texDigest = png => {
      let hash = 5381;
      for (let index = 0; index < png.length; index++)
        hash = ((hash << 5) + hash + png.charCodeAt(index)) | 0;
      return `${png.length}.${(hash >>> 0).toString(36)}`;
    };
    const texKey = (tex, png) => `${tex.length}:${tex}:${texDigest(png)}`;
    const texLoader = new THREE.TextureLoader();
    const disposable = [];
    const textureFor = async (tex, png) => {
      const key = texKey(tex, png);
      if (!texCache.has(key)) {
        try {
          const image = await texLoader.loadAsync(`data:image/png;base64,${png}`);
          image.colorSpace = THREE.SRGBColorSpace;
          // DS1 textures are DirectX bytes: v0 is the first stored row,
          // so the GL flip would stand every texture on its head, and
          // tiling UVs run far past [0,1], so clamp would smear them.
          image.flipY = false;
          image.wrapS = image.wrapT = THREE.RepeatWrapping;
          // Test seam: the flags the map textures loaded with.
          host._viewportTex = {flipY: image.flipY, wrapS: image.wrapS, wrapT: image.wrapT};
          texCache.set(key, image);
          disposable.push(image);
        } catch (_error) {
          return null;
        }
      }
      return texCache.get(key);
    };
    const lightCache = new Map();
    const lightTextureFor = async (tex, png) => {
      const key = texKey(tex, png);
      if (!lightCache.has(key)) {
        try {
          const image = await texLoader.loadAsync(`data:image/png;base64,${png}`);
          image.colorSpace = THREE.SRGBColorSpace;
          // Same DirectX bytes as the diffuse, but an atlas-ranged UV
          // set on channel 1: clamp, never tile.
          image.flipY = false;
          image.wrapS = image.wrapT = THREE.ClampToEdgeWrapping;
          image.channel = 1;
          lightCache.set(key, image);
          disposable.push(image);
        } catch (_error) {
          return null;
        }
      }
      return lightCache.get(key);
    };
    const materialFor = (mesh, texturesByName, fx, waterMesh, cutout) => {
      const plain = waterMesh ? water : fx ? effect : mesh.cull !== false ? front : double;
      const png = mesh.map && texturesByName && texturesByName[mesh.map];
      const image = mesh.map && mesh.uv && png ? texCache.get(texKey(mesh.map, png)) : null;
      if (!image) return plain;
      const litPng = mesh.light && mesh.uv1 && texturesByName && texturesByName[mesh.light];
      const lit = !fx && litPng ? lightCache.get(texKey(mesh.light, litPng)) : null;
      const key = `${texKey(mesh.map, png)}|${mesh.cull !== false ? "f" : "d"}|${fx ? "x" : "o"}|${lit ? texKey(mesh.light, litPng) : "-"}|${cutout ? "c" : "o"}`;
      if (!matCache.has(key)) {
        // Baked meshes skip the scene rig exactly like the game: map
        // times light, nothing else. Basic divides the light by pi, so
        // the intensity puts the baked values back to authored levels.
        // Cutouts discard their empty texels instead of drawing them
        // black, and the offset lifts them off the surface beneath.
        // Effects already blend, so they cut nothing.
        const cut = cutout && !fx
          ? {alphaTest: 0.5, polygonOffset: true, polygonOffsetFactor: -1,
             polygonOffsetUnits: -1}
          : {};
        const textured = fx
          ? new THREE.MeshStandardMaterial({map: image, roughness: 1, metalness: 0,
              side: THREE.DoubleSide, transparent: true, opacity: 0.25, depthWrite: false})
          : lit
            ? new THREE.MeshBasicMaterial({map: image, lightMap: lit,
                lightMapIntensity: Math.PI, ...cut})
            : new THREE.MeshStandardMaterial({map: image, roughness: 0.95, metalness: 0,
                side: mesh.cull !== false ? THREE.FrontSide : THREE.DoubleSide, ...cut});
        matCache.set(key, textured);
        disposable.push(textured);
      }
      return matCache.get(key);
    };
    // Collision and navigation parts have no model to load and no honest
    // drawing: their geometry is world-baked Havok data. Skipped, not drawn.
    const isMarker = part => part.kind === "Collision" || part.kind === "Navigation";
    const wanted = [];
    for (const part of view.parts) {
      if (isMarker(part)) continue;
      const info = view.models[part.model];
      if (info && info.available) wanted.push(part.model);
    }
    const unique = [...new Set(wanted)];
    // Progressive loading: geometry streams in batches and each batch
    // renders as it arrives, so the view is usable before the whole
    // map has loaded. The canvas mounts on the first batch (the
    // loading panel stays until then); data-ready still means every
    // model is in and the camera is framed.
    const BATCH = 16;
    const pngById = new Map();
    const seenIds = new Set();
    const geometries = new Map();
    const root = new THREE.Group();
    scene.add(root);
    const groups = new Map();
    // Map lights are unlit markers, not scene lighting: a hundred
    // real point lights would stall the renderer, so each light is
    // one small warm octahedron at its point. Clicking selects it
    // and the gizmo drags it like any placement; the shared point
    // note on its position fields says what moves along.
    const lightGeo = new THREE.OctahedronGeometry(0.5);
    const lightMat = new THREE.MeshBasicMaterial({color: 0xffc46b});
    for (const light of view.lights || []) {
      const group = new THREE.Group();
      group.position.set(light.pos[0], light.pos[1], light.pos[2]);
      group.userData.part = {key: light.key, name: light.name, kind: "Light",
        model: "", movable: true};
      group.add(new THREE.Mesh(lightGeo, lightMat));
      root.add(group);
      groups.set(light.key, group);
    }
    const skyMeshes = [];
    const box = new THREE.Box3();
    let mapDiag = 0, skyDiag = 0;
    let canvasOn = false, fullyLoaded = false, userMoved = false, progress = null;
    controls.addEventListener("start", () => { userMoved = true; });
    const MOVABLE = new Set([1, 2, 4, 9, 10]);
    const place = (group, part) => {
      group.position.set(part.pos[0], part.pos[1], part.pos[2]);
      group.rotation.set(part.rot[0] * DEG, part.rot[1] * DEG, part.rot[2] * DEG, ORDER);
      group.scale.set(part.scale[0], part.scale[1], part.scale[2]);
      group.userData.part = {key: part.key, name: part.name, kind: part.kind, model: part.model,
        movable: MOVABLE.has(Number(String(part.key).split(":")[0]))};
    };
    const frameCamera = () => {
      if (box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3()).length();
      camera.position.set(center.x + size * 0.6, center.y + size * 0.45, center.z + size * 0.6);
      camera.far = Math.max(1000, size * 10);
      camera.updateProjectionMatrix();
      controls.target.copy(center);
      controls.update();
    };
    // The depth buffer's precision dies with range: near 0.1 under a
    // far plane past the horizon shimmered every distant overlap.
    // Fit both planes to the map's own box instead, every frame, so
    // coplanar ground patches stop fighting at any zoom.
    const fitDepth = () => {
      if (box.isEmpty()) return;
      const dist = box.distanceToPoint(camera.position);
      const span = Math.max(mapDiag, skyDiag);
      camera.near = dist > 0 ? Math.max(dist * 0.5, 0.05) : 0.1;
      camera.far = dist + span * 1.2 + 1;
      camera.updateProjectionMatrix();
    };
    const resize = () => {
      const width = host.clientWidth || 800, height = host.clientHeight || 520;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    // The stage flexes with its panel, so divider drags resize it
    // without a window resize: watch the host itself (as mountChr).
    const resizer = typeof ResizeObserver === "function" ? new ResizeObserver(() => resize()) : null;
    if (resizer) resizer.observe(host);
    else window.addEventListener("resize", resize);
    let selected = null;
    // The highlight is a box, not a tint: the mesh materials are shared
    // across placements, so tinting one would tint them all.
    const highlight = new THREE.BoxHelper(new THREE.Object3D(), 0xffd34d);
    highlight.visible = false;
    scene.add(highlight);
    const gizmo = new TransformControls(camera, canvas);
    scene.add(gizmo.getHelper());
    // Test seam: project a world point to page pixels, so drag tests
    // can grab the gizmo without hunting pixels in screenshots.
    host._viewportProject = (x, y, z) => {
      const rect = canvas.getBoundingClientRect();
      const point = new THREE.Vector3(x, y, z).project(camera);
      return [rect.left + (point.x + 1) / 2 * rect.width, rect.top + (1 - point.y) / 2 * rect.height];
    };
    const readOnly = hooks.readOnly !== false;
    const select = key => {
      selected = key && groups.has(key) ? key : null;
      const group = selected ? groups.get(selected) : null;
      if (group && group.userData.part.movable) gizmo.attach(group);
      else gizmo.detach();
      if (group) {
        highlight.setFromObject(group);
        highlight.visible = true;
      } else highlight.visible = false;
      if (hooks.onSelect) hooks.onSelect(selected, group ? {...group.userData.part} : null);
    };
    let startPos = null, startRot = null, gizmoMode = "translate", spinStart = false;
    gizmo.addEventListener("dragging-changed", event => { controls.enabled = !event.value; });
    gizmo.addEventListener("mouseDown", () => {
      if (!selected) return;
      startPos = groups.get(selected).position.clone();
      startRot = groups.get(selected).rotation.clone();
      spinStart = gizmoMode === "rotate";
      if (readOnly && hooks.requestMod) hooks.requestMod();
    });
    gizmo.addEventListener("objectChange", () => {
      if (!selected) return;
      const group = groups.get(selected);
      highlight.setFromObject(group);
    });
    const snapBack = (group, back, backRot) => {
      group.position.copy(back);
      if (backRot) group.rotation.copy(backRot);
      highlight.setFromObject(group);
    };
    gizmo.addEventListener("mouseUp", () => {
      if (!selected || !startPos) return;
      const group = groups.get(selected);
      const spinning = spinStart;
      const pos = spinning
        ? [group.rotation.x / DEG, group.rotation.y / DEG, group.rotation.z / DEG]
        : [group.position.x, group.position.y, group.position.z];
      const start = spinning ? startRot : startPos;
      const moved = spinning
        ? pos.some((axis, index) => axis !== start.getComponent(index) / DEG)
        : pos.some((axis, index) => axis !== start.getComponent(index));
      const back = startPos.clone(), backRot = startRot.clone();
      startPos = null; startRot = null;
      const commit = spinning ? hooks.onRotate : hooks.onMove;
      if (readOnly) {
        // Vanilla readers were just offered a mod; nothing is committed,
        // so the part snaps back to where it stands.
        snapBack(group, back, backRot);
      } else if (moved && commit) {
        // A refused commit (a second drag mid-save, a failed write)
        // snaps back too; the page reports why.
        Promise.resolve(commit(selected, pos)).then(ok => {
          if (ok === false) snapBack(group, back, backRot);
        });
      }
    });
    const ray = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let down = null, downPos = null, downRot = null;
    canvas.addEventListener("pointerdown", event => {
      down = [event.clientX, event.clientY];
      const current = selected && groups.get(selected);
      downPos = current ? current.position.clone() : null;
      downRot = current ? current.rotation.clone() : null;
    });
    canvas.addEventListener("pointerup", event => {
      if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
      down = null;
      // A released gizmo drag lands here too, but only a drag that
      // actually moved the part vetoes selection: the gizmo's pickers
      // keep a constant screen size, so vetoing on them freezes
      // selection anywhere near the selected part. A plain click on or
      // beside the handles selects what is under the cursor.
      const current = selected && groups.get(selected);
      const settled = !current || !downPos
        || (current.position.x === downPos.x && current.position.y === downPos.y && current.position.z === downPos.z
          && current.rotation.x === downRot.x && current.rotation.y === downRot.y && current.rotation.z === downRot.z);
      downPos = null; downRot = null;
      if (!settled) return;
      const rect = canvas.getBoundingClientRect();
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      ray.setFromCamera(pointer, camera);
      const hit = ray.intersectObjects(root.children.filter(obj => obj.visible), true)[0];
      let group = hit ? hit.object : null;
      while (group && !group.userData.part) group = group.parent;
      const key = group ? group.userData.part.key : null;
      if (key !== selected) select(key);
    });
    const controller = {
      select,
      focus(focusKey) {
        const group = focusKey && groups.get(focusKey);
        if (!group) return false;
        group.updateWorldMatrix(true, false);
        const target = new THREE.Vector3();
        group.getWorldPosition(target);
        const span = new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3()).length() || 4;
        const offset = camera.position.clone().sub(controls.target);
        if (!offset.lengthSq()) offset.set(1, 0.7, 1);
        offset.normalize().multiplyScalar(Math.min(Math.max(span * 2, 8), 24));
        controls.target.copy(target);
        camera.position.copy(target).add(offset);
        return true;
      },
      moveTo(key, pos) {
        const group = key && groups.get(key);
        if (!group || !group.userData.part.movable) return;
        group.position.set(pos[0], pos[1], pos[2]);
        if (key === selected) highlight.setFromObject(group);
      },
      turnTo(key, rot) {
        const group = key && groups.get(key);
        if (!group || !group.userData.part.movable) return;
        group.rotation.set(rot[0] * DEG, rot[1] * DEG, rot[2] * DEG);
        if (key === selected) highlight.setFromObject(group);
      },
      scaleTo(key, scale) {
        const group = key && groups.get(key);
        if (!group || !group.userData.part.movable) return;
        group.scale.set(scale[0], scale[1], scale[2]);
        if (key === selected) highlight.setFromObject(group);
      },
      setGizmoMode(mode) {
        gizmoMode = mode === "rotate" ? "rotate" : "translate";
        gizmo.setMode(gizmoMode);
      },
      aim() { return [controls.target.x, controls.target.y, controls.target.z]; },
      dispose() { stop(host); }
    };
    let frames = 0, live = true;
    host._viewportStop = () => {
      live = false;
      if (resizer) resizer.disconnect();
      delete host._viewportProject;
      delete host._viewportScene;
      delete host._viewportCamera;
      window.removeEventListener("resize", resize);
      controls.dispose();
      gizmo.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
      if (progress) progress.remove();
      delete host.dataset.ready;
      for (const geos of geometries.values()) for (const entry of geos) entry.geo.dispose();
      front.dispose();
      double.dispose();
      effect.dispose();
      for (const item of disposable) item.dispose();
      highlight.dispose();
      lightGeo.dispose();
      lightMat.dispose();
    };
    const loop = () => {
      if (!live || mine !== session || !host.isConnected) { stop(host); return; }
      controls.update();
      fitDepth();
      for (const mesh of skyMeshes) mesh.visible = mesh.userData.worldBox.containsPoint(camera.position);
      renderer.render(scene, camera);
      if (fullyLoaded && ++frames === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    viewModes.bindScene(scene);
    // Test seam: the checks find lightmapped materials through this.
    host._viewportScene = scene;
    host._viewportCamera = camera;
    const mountCanvas = () => {
      if (canvasOn) return;
      canvasOn = true;
      host.append(canvas);
      loading.remove();
      resize();
      frameCamera();
      loop();
    };
    const showProgress = (done, total) => {
      if (!progress) {
        progress = document.createElement("div");
        progress.style.cssText = "position:absolute;right:8px;bottom:8px;z-index:5;pointer-events:none;";
        host.append(progress);
      }
      progress.replaceChildren(LexeditorUI.loadingStatus(`Loading models ${done}/${total}`));
    };
    const ingest = async batch => {
      if (mine !== session || !host.isConnected) return false;
      mountCanvas();
      const fresh = new Map();
      for (const [name, data] of batch)
        for (const [tex, png] of Object.entries(data.textures || {})) {
          const key = texKey(tex, png);
          if (!texCache.has(key) && !fresh.has(key)) fresh.set(key, [tex, png]);
        }
      await Promise.all([...fresh.values()].map(([tex, png]) => textureFor(tex, png)));
      if (mine !== session || !host.isConnected) return false;
      const freshLit = new Map();
      for (const [name, data] of batch)
        for (const mesh of data.meshes || []) {
          const png = mesh.light && (data.textures || {})[mesh.light];
          if (mesh.light && mesh.uv1 && png) {
            const key = texKey(mesh.light, png);
            if (!lightCache.has(key) && !freshLit.has(key)) freshLit.set(key, [mesh.light, png]);
          }
        }
      await Promise.all([...freshLit.values()].map(([tex, png]) => lightTextureFor(tex, png)));
      if (mine !== session || !host.isConnected) return false;
      for (const [name, data] of batch) {
        geometries.set(name, data.meshes.map(mesh => {
          const geo = new THREE.BufferGeometry();
          geo.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
          geo.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
          if (mesh.uv) geo.setAttribute("uv", new THREE.BufferAttribute(f32(mesh.uv), 2));
          if (mesh.uv1) geo.setAttribute("uv1", new THREE.BufferAttribute(f32(mesh.uv1), 2));
          geo.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
          geo.computeBoundingSphere();
          geo.computeBoundingBox();
          const entry = {geo, sky: isSky(mesh), fx: isEffect(mesh), cull: mesh.cull !== false};
          entry.mat = materialFor(mesh, data.textures, entry.fx, isWater(mesh), isCutout(mesh));
          return entry;
        }));
      }
      const names = new Set(batch.map(([name]) => name));
      for (const part of view.parts) {
        if (isMarker(part) || groups.has(part.key)) continue;
        const geos = geometries.get(part.model);
        if (!geos || !names.has(part.model)) continue;
        const group = new THREE.Group();
        place(group, part);
        for (const entry of geos) {
          const mesh = new THREE.Mesh(entry.geo, entry.mat);
          mesh.userData.sky = entry.sky;
          mesh.userData.fx = entry.fx;
          group.add(mesh);
          if (entry.sky) skyMeshes.push(mesh);
        }
        root.add(group);
        groups.set(part.key, group);
        group.updateWorldMatrix(true, true);
        for (const mesh of group.children) {
          if (mesh.userData.sky) {
            mesh.userData.worldBox = mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld);
          } else if (!mesh.userData.fx) {
            box.expandByObject(mesh);
          }
        }
      }
      if (!box.isEmpty()) mapDiag = box.getSize(new THREE.Vector3()).length();
      for (const mesh of skyMeshes)
        skyDiag = Math.max(skyDiag, mesh.userData.worldBox.getSize(new THREE.Vector3()).length());
      // Keep the growing scene framed unless the reader already took
      // the camera; the final frame still matches a full load exactly.
      if (!userMoved) frameCamera();
      return true;
    };
    // One request per batch of models instead of one per model; each
    // batch renders as it arrives. Texture blobs ride the shared
    // content-id store as before, so repeats cross the wire once.
    for (let at = 0; at < unique.length; at += BATCH) {
      if (mine !== session || !host.isConnected) { stop(host); return null; }
      const names = unique.slice(at, at + BATCH);
      const known = [...seenIds].join(",");
      const response = await fetch(`/api/map/geometries?map=${encodeURIComponent(mapId)}&models=${names.map(encodeURIComponent).join(",")}` + (known ? `&known=${encodeURIComponent(known)}` : ""));
      const data = await response.json();
      if (!response.ok || data.error) { stop(host); throw new Error(data.error || response.statusText); }
      const batch = [];
      for (const name of names) {
        const item = (data.items || {})[name];
        if (!item || item.error) continue;
        for (const [tex, digest] of Object.entries(item.texture_ids || {})) {
          if (item.textures && item.textures[tex]) {
            pngById.set(digest, item.textures[tex]);
            seenIds.add(digest);
          }
        }
        const rebuilt = {};
        for (const [tex, digest] of Object.entries(item.texture_ids || {}))
          if (pngById.has(digest)) rebuilt[tex] = pngById.get(digest);
        item.textures = rebuilt;
        batch.push([name, item]);
      }
      if (!await ingest(batch)) { stop(host); return null; }
      showProgress(Math.min(at + BATCH, unique.length), unique.length);
    }
    if (mine !== session || !host.isConnected) { stop(host); return null; }
    mountCanvas();
    // The final frame matches a full load exactly unless the reader
    // already orbited the partial view; then their camera stands.
    if (!userMoved) frameCamera();
    if (progress) { progress.remove(); progress = null; }
    fullyLoaded = true;
    return controller;
  }
  // Read-only character view: bind-pose mesh, the body's own
  // hitbox, and one attack's hit slots as spheres and capsules. Only
  // the dummies the viewed attack's slots name light up as dots;
  // a slot that names a point the model lacks is reported, not drawn.
  async function mountChr(host, view, attackId, status) {
    stop(host);
    const mine = ++session;
    if (!host.isConnected || !view) return;
    host.dataset.dots = "0";
    const chr = (view.chrs || []).find(entry => entry.available) || (view.chrs || [])[0];
    if (!chr) { status.textContent = `${view.name}: no placed character model.`; return; }
    if (!chr.available) { status.textContent = `${view.name}: ${chr.id} — ${chr.reason || "model unavailable"}.`; return; }
    status.replaceChildren(LexeditorUI.loadingStatus(`Loading ${chr.id}`));
    const loading = LexeditorUI.loadingPanel({label: `Loading ${chr.id}`});
    host.replaceChildren(loading);
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (mine !== session || !host.isConnected) return;
    const response = await fetch(`/api/chr/geometry?chr=${encodeURIComponent(chr.id)}`);
    const data = await response.json();
    if (!response.ok || data.error) { loading.remove(); throw new Error(data.error || response.statusText); }
    if (mine !== session || !host.isConnected) return;
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.viewport = "true";
    host.append(canvas);
    const viewModes = LexeditorUI.modelViewModes(host);
    loading.remove();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.01, 10000);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(1, 2, 1);
    scene.add(sun);
    const trash = [];
    const front = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0, side: THREE.FrontSide});
    const double = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0, side: THREE.DoubleSide});
    trash.push(front, double);
    const texCache = new Map();
    const texLoader = new THREE.TextureLoader();
    const materialFor = async mesh => {
      const plain = mesh.cull !== false ? front : double;
      const png = mesh.map && data.textures && data.textures[mesh.map];
      if (!png || !mesh.uv) return plain;
      if (!texCache.has(mesh.map)) {
        try {
          const tex = await texLoader.loadAsync(`data:image/png;base64,${png}`);
          tex.colorSpace = THREE.SRGBColorSpace;
          // DirectX bytes, as on the map: no GL flip, tiled wrap.
          tex.flipY = false;
          tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
          texCache.set(mesh.map, tex);
          trash.push(tex);
        } catch (_error) {
          return plain;
        }
      }
      const textured = new THREE.MeshStandardMaterial({map: texCache.get(mesh.map),
        roughness: 0.95, metalness: 0, side: mesh.cull !== false ? THREE.FrontSide : THREE.DoubleSide});
      trash.push(textured);
      return textured;
    };
    const root = new THREE.Group();
    scene.add(root);
    let tris = 0;
    for (const mesh of data.meshes) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
      geo.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
      if (mesh.uv) geo.setAttribute("uv", new THREE.BufferAttribute(f32(mesh.uv), 2));
      geo.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
      trash.push(geo);
      root.add(new THREE.Mesh(geo, await materialFor(mesh)));
      tris += geo.index.count / 3;
    }
    const byId = new Map((chr.dummies || []).map(dummy => [dummy.id, new THREE.Vector3(dummy.pos[0], dummy.pos[1], dummy.pos[2])]));
    const attack = (view.attacks || []).find(entry => entry.id === attackId);
    // Green dots mark the viewed attack's anchors, not every model
    // point: a dummy lights up only when one of the attack's slots
    // names it, so an idle rig stays clean while a hitbox's ends show
    // even when the slot itself has no size yet.
    const wanted = new Set();
    for (const slot of (attack && attack.slots) || []) {
      if (typeof slot.first === "number") wanted.add(slot.first);
      if (slot.shape === "capsule" && typeof slot.second === "number") wanted.add(slot.second);
    }
    const shown = [...byId].filter(([id]) => wanted.has(id));
    const body = view.body || {};
    const box = new THREE.Box3();
    root.traverse(obj => { if (obj.isMesh) box.expandByObject(obj); });
    for (const [, point] of shown) box.expandByPoint(point);
    // The frame fits everything the stage shows: meshes, the viewed
    // attack's anchors, its hitboxes, and the body capsule. Hitboxes
    // count as bounds, or a lone anchor would frame to a point and
    // park the camera inside the hitbox it was meant to show.
    const pad = (center, radius) => {
      box.expandByPoint(new THREE.Vector3(center.x - radius, center.y - radius, center.z - radius));
      box.expandByPoint(new THREE.Vector3(center.x + radius, center.y + radius, center.z + radius));
    };
    for (const slot of (attack && attack.slots) || []) {
      if (!slot.active) continue;
      const first = byId.get(slot.first);
      if (!first) continue;
      pad(first, slot.radius);
      if (slot.shape === "capsule") {
        const second = byId.get(slot.second);
        if (second) pad(second, slot.radius);
      }
    }
    if (body.radius > 0 && body.height > 0) {
      pad(new THREE.Vector3(0, body.offset || 0, 0), body.radius);
      pad(new THREE.Vector3(0, (body.offset || 0) + body.height, 0), body.radius);
    }
    const span = box.isEmpty() ? 0 : box.getSize(new THREE.Vector3()).length();
    const size = span < 1e-6 ? 2 : span;
    const dotGeo = new THREE.SphereGeometry(Math.max(size * 0.004, 0.005), 8, 8);
    const dotMat = new THREE.MeshBasicMaterial({color: 0x44dd66});
    trash.push(dotGeo, dotMat);
    for (const [, point] of shown) {
      const dot = new THREE.Mesh(dotGeo, dotMat);
      dot.position.copy(point);
      root.add(dot);
    }
    host.dataset.dots = String(shown.length);
    let bodyShown = false;
    if (body.radius > 0 && body.height > 0) {
      const geo = new THREE.CapsuleGeometry(body.radius, Math.max(body.height - body.radius * 2, 0), 8, 16);
      const mat = new THREE.MeshBasicMaterial({color: 0x3388ff, transparent: true, opacity: 0.3, depthWrite: false});
      trash.push(geo, mat);
      const capsule = new THREE.Mesh(geo, mat);
      capsule.position.set(0, (body.offset || 0) + body.height / 2, 0);
      root.add(capsule);
      bodyShown = true;
    }
    const hitMat = new THREE.MeshBasicMaterial({color: 0xff5533, transparent: true, opacity: 0.4, depthWrite: false});
    trash.push(hitMat);
    const up = new THREE.Vector3(0, 1, 0);
    let live = 0, missing = 0;
    for (const slot of (attack && attack.slots) || []) {
      if (!slot.active) continue;
      const a = byId.get(slot.first);
      if (!a) { missing++; continue; }
      const b = slot.shape === "capsule" ? byId.get(slot.second) : null;
      if (slot.shape === "capsule" && b && a.distanceTo(b) > 1e-6) {
        const geo = new THREE.CapsuleGeometry(slot.radius, a.distanceTo(b), 8, 16);
        trash.push(geo);
        const mesh = new THREE.Mesh(geo, hitMat);
        mesh.position.set((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
        mesh.quaternion.setFromUnitVectors(up, b.clone().sub(a).normalize());
        root.add(mesh);
      } else {
        if (slot.shape === "capsule") missing++;
        const geo = new THREE.SphereGeometry(slot.radius, 16, 12);
        trash.push(geo);
        const mesh = new THREE.Mesh(geo, hitMat);
        mesh.position.copy(a);
        root.add(mesh);
      }
      live++;
    }
    if (!box.isEmpty()) {
      const center = box.getCenter(new THREE.Vector3());
      camera.position.set(center.x + size * 0.6, center.y + size * 0.45, center.z + size * 0.6);
      camera.far = Math.max(100, size * 10);
      camera.updateProjectionMatrix();
      controls.target.copy(center);
      controls.update();
    }
    const resize = () => {
      const width = host.clientWidth || 800, height = host.clientHeight || 520;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    // The stage flexes with its panel, so divider drags resize it
    // without a window resize: watch the host itself (anim.js).
    const resizer = typeof ResizeObserver === "function" ? new ResizeObserver(() => resize()) : null;
    if (resizer) resizer.observe(host);
    else window.addEventListener("resize", resize);
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    const short = n => +Number(n).toFixed(3);
    let text = `${chr.id}: ${plural(data.meshes.length, "mesh", "meshes")}, ${plural(Math.round(tris), "triangle", "triangles")}, ${plural(byId.size, "model point", "model points")}. `;
    text += attack ? `Attack "${attack.name}": ${plural(live, "live hitbox", "live hitboxes")}` : "No linked attack";
    if (missing) text += `, ${plural(missing, "slot points", "slots point")} at a missing model point`;
    text += bodyShown ? `. Body R ${short(body.radius)} x H ${short(body.height)}.` : ".";
    if ((view.chrs || []).length > 1) text += ` Also wears ${(view.chrs || []).filter(entry => entry.id !== chr.id).map(entry => entry.id).join(", ")}.`;
    status.textContent = text;
    let frames = 0, liveFlag = true;
    host._viewportStop = () => {
      liveFlag = false;
      if (resizer) resizer.disconnect();
      window.removeEventListener("resize", resize);
      controls.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
      delete host.dataset.ready;
      delete host.dataset.dots;
      for (const item of trash) item.dispose();
    };
    const loop = () => {
      if (!liveFlag || mine !== session || !host.isConnected) { stop(host); return; }
      controls.update();
      renderer.render(scene, camera);
      if (++frames === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    viewModes.bindScene(scene);
    loop();
  }
  return {mount, mountChr, stop};
})();
