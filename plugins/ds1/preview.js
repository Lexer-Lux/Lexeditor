"use strict";
// One-record model drawer: a plain three.js mesh view for the weapon,
// armor and enemy detail panels. The same materials, framing, resize and
// dispose loop as the enemy Models screen, without its hitbox and body
// overlays. Mounted by editor.js, which owns the drawer and its status.
window.Ds1Preview = (() => {
  let session = 0;
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
    if (host && host._previewStop) {
      try { host._previewStop(); } catch (_ignored) {}
      delete host._previewStop;
    }
  }
  // Mounts the geometry at geometryUrl into host and returns a controller
  // with dispose(). opts.status reports "N meshes, M triangles" once the
  // mesh lands. A newer mount or a detached host aborts the load.
  async function mount(host, geometryUrl, opts = {}) {
    stop(host);
    const mine = ++session;
    // No connected check here: the drawer appends the stage after its
    // content factory returns, so a synchronous check always fails. The
    // guards after each wait below still abandon a detached host.
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (mine !== session || !host.isConnected) return null;
    const response = await fetch(geometryUrl);
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || response.statusText);
    if (mine !== session || !host.isConnected) return null;
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.preview = "true";
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
    const box = new THREE.Box3();
    root.traverse(obj => { if (obj.isMesh) box.expandByObject(obj); });
    const size = box.isEmpty() ? 2 : box.getSize(new THREE.Vector3()).length();
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
    opts.status?.(`${plural(data.meshes.length, "mesh", "meshes")}, ${plural(Math.round(tris), "triangle", "triangles")}`);
    let frames = 0, liveFlag = true;
    host._previewStop = () => {
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
    loop();
    return {dispose: () => stop(host), canvas};
  }
  return {mount, stop};
})();
