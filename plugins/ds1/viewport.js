"use strict";
// 3D map view. Geometries are shared across placements; each part only
// adds a transform. Clicking a placement selects it, the gizmo drags it,
// and editor.js commits the move. Collision and navigation geometry is baked
// in world space in the Havok packfiles, which this version does not decode,
// so those parts are counted, never drawn. Mounted by editor.js, which owns
// the page and the edit bar.
window.Ds1Viewport = (() => {
  let session = 0;
  const DEG = Math.PI / 180;
  // MSB rotation application order; axis-aligned pieces render the same
  // under any order, so multi-axis rotations are the unverified case.
  const ORDER = "XYZ";
  function b64(text) {
    const raw = atob(text);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
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
  async function mount(host, mapId, view, status, hooks = {}) {
    stop(host);
    const mine = ++session;
    if (!host.isConnected || !view) return null;
    status.replaceChildren(LexeditorUI.loadingStatus(`Loading ${view.parts.length} parts`));
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    const {TransformControls} = await import("three/addons/controls/TransformControls.js");
    if (mine !== session || !host.isConnected) return null;
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.viewport = "true";
    host.append(canvas);
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
    // in the game; opaque here they would occlude the map. Alpha-test (_Alp)
    // materials stay opaque: most are foliage cutouts, solid without textures.
    const isEffect = mesh => (mesh.mat_def || "").toLowerCase().includes("_add");
    const effect = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 1, metalness: 0,
      side: THREE.DoubleSide, transparent: true, opacity: 0.25, depthWrite: false});
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
    const materialFor = (mesh, texturesByName, fx) => {
      const plain = fx ? effect : mesh.cull !== false ? front : double;
      const png = mesh.map && texturesByName && texturesByName[mesh.map];
      const image = mesh.map && mesh.uv && png ? texCache.get(texKey(mesh.map, png)) : null;
      if (!image) return plain;
      const key = `${texKey(mesh.map, png)}|${mesh.cull !== false ? "f" : "d"}|${fx ? "x" : "o"}`;
      if (!matCache.has(key)) {
        const textured = fx
          ? new THREE.MeshStandardMaterial({map: image, roughness: 1, metalness: 0,
              side: THREE.DoubleSide, transparent: true, opacity: 0.25, depthWrite: false})
          : new THREE.MeshStandardMaterial({map: image, roughness: 0.95, metalness: 0,
              side: mesh.cull !== false ? THREE.FrontSide : THREE.DoubleSide});
        matCache.set(key, textured);
        disposable.push(textured);
      }
      return matCache.get(key);
    };
    // Collision and navigation parts have no model to load and no honest
    // drawing: their geometry is world-baked Havok data. Counted, not drawn.
    const isMarker = part => part.kind === "Collision" || part.kind === "Navigation";
    const counts = {parts: 0, meshes: 0, tris: 0, missing: 0, sky: 0, effect: 0, collision: 0, navigation: 0};
    const wanted = [];
    for (const part of view.parts) {
      if (isMarker(part)) {
        if (part.kind === "Collision") counts.collision++;
        else counts.navigation++;
        continue;
      }
      const info = view.models[part.model];
      if (!info || !info.available) counts.missing++;
      else wanted.push(part.model);
    }
    const unique = [...new Set(wanted)];
    const loaded = await Promise.all(unique.map(async name => {
      const response = await fetch(`/api/map/geometry?map=${encodeURIComponent(mapId)}&model=${encodeURIComponent(name)}`);
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || response.statusText);
      return [name, data];
    }));
    if (mine !== session || !host.isConnected) { renderer.dispose(); return null; }
    const wantedPngs = new Map();
    for (const [name, data] of loaded)
      for (const [tex, png] of Object.entries(data.textures || {})) {
        const key = texKey(tex, png);
        if (!wantedPngs.has(key)) wantedPngs.set(key, [tex, png]);
      }
    await Promise.all([...wantedPngs.values()].map(([tex, png]) => textureFor(tex, png)));
    if (mine !== session || !host.isConnected) { renderer.dispose(); return null; }
    const geometries = new Map();
    for (const [name, data] of loaded) {
      geometries.set(name, data.meshes.map(mesh => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
        geo.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
        if (mesh.uv) geo.setAttribute("uv", new THREE.BufferAttribute(f32(mesh.uv), 2));
        geo.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
        geo.computeBoundingSphere();
        const entry = {geo, sky: isSky(mesh), fx: isEffect(mesh), cull: mesh.cull !== false};
        entry.mat = materialFor(mesh, data.textures, entry.fx);
        if (entry.sky) counts.sky++;
        if (entry.fx) counts.effect++;
        return entry;
      }));
    }
    const root = new THREE.Group();
    scene.add(root);
    const groups = new Map();
    const MOVABLE = new Set([1, 2, 4, 9, 10]);
    const place = (group, part) => {
      group.position.set(part.pos[0], part.pos[1], part.pos[2]);
      group.rotation.set(part.rot[0] * DEG, part.rot[1] * DEG, part.rot[2] * DEG, ORDER);
      group.scale.set(part.scale[0], part.scale[1], part.scale[2]);
      group.userData.part = {key: part.key, name: part.name, kind: part.kind, model: part.model,
        movable: MOVABLE.has(Number(String(part.key).split(":")[0]))};
    };
    const skyMeshes = [];
    for (const part of view.parts) {
      if (isMarker(part)) {
        counts.parts++;
        continue;
      }
      const geos = geometries.get(part.model);
      if (!geos) continue;
      const group = new THREE.Group();
      place(group, part);
      for (const entry of geos) {
        const mesh = new THREE.Mesh(entry.geo, entry.mat);
        mesh.userData.sky = entry.sky;
        mesh.userData.fx = entry.fx;
        group.add(mesh);
        if (entry.sky) skyMeshes.push(mesh);
        counts.meshes++;
        counts.tris += entry.geo.index.count / 3;
      }
      root.add(group);
      groups.set(part.key, group);
      counts.parts++;
    }
    root.updateMatrixWorld(true);
    for (const mesh of skyMeshes) {
      mesh.geometry.computeBoundingBox();
      mesh.userData.worldBox = mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld);
    }
    const box = new THREE.Box3();
    root.traverse(obj => { if (obj.isMesh && !obj.userData.sky && !obj.userData.fx) box.expandByObject(obj); });
    if (!box.isEmpty()) {
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3()).length();
      camera.position.set(center.x + size * 0.6, center.y + size * 0.45, center.z + size * 0.6);
      camera.far = Math.max(1000, size * 10);
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
    window.addEventListener("resize", resize);
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    const short = n => +Number(n).toFixed(3);
    const baseStatus = () => `${mapId}: ${plural(counts.parts, "part", "parts")}, ${plural(unique.length, "model", "models")}, ${plural(Math.round(counts.tris), "triangle", "triangles")}${counts.sky ? `, ${plural(counts.sky, "sky mesh", "sky meshes")}` : ""}${counts.effect ? `, ${plural(counts.effect, "effect", "effects")} transparent` : ""}${counts.collision ? `, ${plural(counts.collision, "collision part", "collision parts")}` : ""}${counts.navigation ? `, ${plural(counts.navigation, "navigation part", "navigation parts")}` : ""}${counts.missing ? `, ${plural(counts.missing, "part has", "parts have")} no visible mesh` : ""}.`;
    let selected = null, selectedText = "";
    const showStatus = () => {
      status.textContent = selectedText ? `${baseStatus()} Selected: ${selectedText}.` : baseStatus();
    };
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
    const describe = group => {
      const info = group.userData.part;
      const at = group.position;
      return `${info.name} (${info.kind}, ${info.model}) at ${short(at.x)}, ${short(at.y)}, ${short(at.z)}`;
    };
    const select = key => {
      selected = key && groups.has(key) ? key : null;
      const group = selected ? groups.get(selected) : null;
      if (group && group.userData.part.movable) gizmo.attach(group);
      else gizmo.detach();
      if (group) {
        highlight.setFromObject(group);
        highlight.visible = true;
        selectedText = describe(group);
      } else {
        highlight.visible = false;
        selectedText = "";
      }
      showStatus();
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
      selectedText = describe(group);
      showStatus();
    });
    const snapBack = (group, back, backRot) => {
      group.position.copy(back);
      if (backRot) group.rotation.copy(backRot);
      highlight.setFromObject(group);
      selectedText = describe(group);
      showStatus();
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
    showStatus();
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
        if (key === selected) {
          highlight.setFromObject(group);
          selectedText = describe(group);
          showStatus();
        }
      },
      turnTo(key, rot) {
        const group = key && groups.get(key);
        if (!group || !group.userData.part.movable) return;
        group.rotation.set(rot[0] * DEG, rot[1] * DEG, rot[2] * DEG);
        if (key === selected) {
          highlight.setFromObject(group);
          selectedText = describe(group);
          showStatus();
        }
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
      delete host._viewportProject;
      window.removeEventListener("resize", resize);
      controls.dispose();
      gizmo.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
      delete host.dataset.ready;
      for (const geos of geometries.values()) for (const entry of geos) entry.geo.dispose();
      front.dispose();
      double.dispose();
      effect.dispose();
      for (const item of disposable) item.dispose();
      highlight.dispose();
    };
    const loop = () => {
      if (!live || mine !== session || !host.isConnected) { stop(host); return; }
      controls.update();
      for (const mesh of skyMeshes) mesh.visible = mesh.userData.worldBox.containsPoint(camera.position);
      renderer.render(scene, camera);
      if (++frames === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    viewModes.bindScene(scene);
    loop();
    return controller;
  }
  // Read-only character view: bind-pose mesh, dummy points, the
  // body's own hitbox, and one attack's hit slots as spheres and
  // capsules. Points resolve on the enemy's own model; a slot that
  // names a point the model lacks is reported, not drawn.
  async function mountChr(host, view, attackId, status) {
    stop(host);
    const mine = ++session;
    if (!host.isConnected || !view) return;
    const chr = (view.chrs || []).find(entry => entry.available) || (view.chrs || [])[0];
    if (!chr) { status.textContent = `${view.name}: no placed character model.`; return; }
    if (!chr.available) { status.textContent = `${view.name}: ${chr.id} — ${chr.reason || "model unavailable"}.`; return; }
    status.replaceChildren(LexeditorUI.loadingStatus(`Loading ${chr.id}`));
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (mine !== session || !host.isConnected) return;
    const response = await fetch(`/api/chr/geometry?chr=${encodeURIComponent(chr.id)}`);
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || response.statusText);
    if (mine !== session || !host.isConnected) return;
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.viewport = "true";
    host.append(canvas);
    const viewModes = LexeditorUI.modelViewModes(host);
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
    const box = new THREE.Box3();
    root.traverse(obj => { if (obj.isMesh) box.expandByObject(obj); });
    for (const point of byId.values()) box.expandByPoint(point);
    const size = box.isEmpty() ? 2 : box.getSize(new THREE.Vector3()).length();
    const dotGeo = new THREE.SphereGeometry(Math.max(size * 0.004, 0.005), 8, 8);
    const dotMat = new THREE.MeshBasicMaterial({color: 0x44dd66});
    trash.push(dotGeo, dotMat);
    for (const point of byId.values()) {
      const dot = new THREE.Mesh(dotGeo, dotMat);
      dot.position.copy(point);
      root.add(dot);
    }
    const body = view.body || {};
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
    const attack = (view.attacks || []).find(entry => entry.id === attackId);
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
    window.addEventListener("resize", resize);
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
      window.removeEventListener("resize", resize);
      controls.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
      delete host.dataset.ready;
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
