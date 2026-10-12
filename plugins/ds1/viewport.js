"use strict";
// Read-only 3D map view. Geometries are shared across placements; each
// part only adds a transform. Mounted by editor.js, which owns the page.
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
  async function mount(host, mapId, view, status) {
    stop(host);
    const mine = ++session;
    if (!host.isConnected || !view) return;
    status.textContent = `Loading ${view.parts.length} parts.`;
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (mine !== session || !host.isConnected) return;
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.viewport = "true";
    host.append(canvas);
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
    const counts = {parts: 0, meshes: 0, tris: 0, missing: 0, sky: 0, effect: 0};
    const wanted = [];
    for (const part of view.parts) {
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
    if (mine !== session || !host.isConnected) { renderer.dispose(); return; }
    const geometries = new Map();
    for (const [name, data] of loaded) {
      geometries.set(name, data.meshes.map(mesh => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
        geo.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
        geo.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
        geo.computeBoundingSphere();
        const entry = {geo, sky: isSky(mesh), fx: isEffect(mesh), cull: mesh.cull !== false};
        if (entry.sky) counts.sky++;
        if (entry.fx) counts.effect++;
        return entry;
      }));
    }
    const root = new THREE.Group();
    scene.add(root);
    const skyMeshes = [];
    for (const part of view.parts) {
      const geos = geometries.get(part.model);
      if (!geos) continue;
      const group = new THREE.Group();
      group.position.set(part.pos[0], part.pos[1], part.pos[2]);
      group.rotation.set(part.rot[0] * DEG, part.rot[1] * DEG, part.rot[2] * DEG, ORDER);
      group.scale.set(part.scale[0], part.scale[1], part.scale[2]);
      group.userData.part = {key: part.key, name: part.name, kind: part.kind, model: part.model};
      for (const entry of geos) {
        const mesh = new THREE.Mesh(entry.geo, entry.fx ? effect : entry.cull ? front : double);
        mesh.userData.sky = entry.sky;
        mesh.userData.fx = entry.fx;
        group.add(mesh);
        if (entry.sky) skyMeshes.push(mesh);
        counts.meshes++;
        counts.tris += entry.geo.index.count / 3;
      }
      root.add(group);
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
    const baseStatus = () => `${mapId}: ${plural(counts.parts, "part", "parts")}, ${plural(unique.length, "model", "models")}, ${plural(Math.round(counts.tris), "triangle", "triangles")}${counts.sky ? `, ${plural(counts.sky, "sky mesh", "sky meshes")}` : ""}${counts.effect ? `, ${plural(counts.effect, "effect", "effects")} transparent` : ""}${counts.missing ? `, ${plural(counts.missing, "part has", "parts have")} no visible mesh` : ""}.`;
    status.textContent = baseStatus();
    const ray = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let down = null;
    canvas.addEventListener("pointerdown", event => { down = [event.clientX, event.clientY]; });
    canvas.addEventListener("pointerup", event => {
      if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4) return;
      down = null;
      const rect = canvas.getBoundingClientRect();
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      ray.setFromCamera(pointer, camera);
      const hit = ray.intersectObjects(root.children, true)[0];
      let group = hit ? hit.object : null;
      while (group && !group.userData.part) group = group.parent;
      const label = group ? `${group.userData.part.name} (${group.userData.part.kind}, ${group.userData.part.model})` : "nothing";
      status.textContent = `${baseStatus()} Selected: ${label}.`;
    });
    let frames = 0, live = true;
    host._viewportStop = () => {
      live = false;
      window.removeEventListener("resize", resize);
      controls.dispose();
      renderer.dispose();
      for (const geos of geometries.values()) for (const entry of geos) entry.geo.dispose();
      front.dispose();
      double.dispose();
      effect.dispose();
    };
    const loop = () => {
      if (!live || mine !== session || !host.isConnected) { stop(host); return; }
      controls.update();
      for (const mesh of skyMeshes) mesh.visible = mesh.userData.worldBox.containsPoint(camera.position);
      renderer.render(scene, camera);
      if (++frames === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    loop();
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
    status.textContent = `Loading ${chr.id}.`;
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
    const root = new THREE.Group();
    scene.add(root);
    let tris = 0;
    for (const mesh of data.meshes) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
      geo.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
      geo.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
      trash.push(geo);
      root.add(new THREE.Mesh(geo, mesh.cull !== false ? front : double));
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
      for (const item of trash) item.dispose();
    };
    const loop = () => {
      if (!liveFlag || mine !== session || !host.isConnected) { stop(host); return; }
      controls.update();
      renderer.render(scene, camera);
      if (++frames === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    loop();
  }
  return {mount, mountChr, stop};
})();
