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
  // with dispose() and the canvas. A newer mount or a detached host
  // aborts the load. A snapshot mount ({once:true}) renders one frame
  // for a thumbnail: it never touches the session, so it cannot steal
  // the drawer, and reports its canvas through options.onFrame.
  async function mount(host, geometryUrl, options) {
    stop(host);
    const snapshot = !!options && options.once === true;
    const mine = snapshot ? 0 : ++session;
    const stale = () => !snapshot && mine !== session;
    // No connected check here: the drawer appends the stage after its
    // content factory returns, so a synchronous check always fails. The
    // guards after each wait below still abandon a detached host.
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (stale() || !host.isConnected) return null;
    const response = await fetch(geometryUrl);
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || response.statusText);
    if (stale() || !host.isConnected) return null;
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
    const resize = () => {
      const width = host.clientWidth || 800, height = host.clientHeight || 520;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    let liveFlag = true;
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
    const root = new THREE.Group();
    scene.add(root);
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
    for (const mesh of data.meshes) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
      geo.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
      if (mesh.uv) geo.setAttribute("uv", new THREE.BufferAttribute(f32(mesh.uv), 2));
      geo.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
      trash.push(geo);
      root.add(new THREE.Mesh(geo, await materialFor(mesh)));
      if (stale() || !host.isConnected) { stop(host); return null; }
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
    resize();
    if (snapshot) {
      if (!host.isConnected) { stop(host); return null; }
      renderer.render(scene, camera);
      host.dataset.ready = "true";
      if (options.onFrame) options.onFrame(canvas);
      return {dispose: () => stop(host), canvas};
    }
    window.addEventListener("resize", resize);
    let frames = 0;
    const loop = () => {
      if (!liveFlag || stale() || !host.isConnected) { stop(host); return; }
      controls.update();
      renderer.render(scene, camera);
      if (++frames === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    loop();
    return {dispose: () => stop(host), canvas};
  }
  // Detail headers share bounded snapshots of the same renderer the
  // drawer uses. One temporary WebGL context renders at a time; the
  // cache keys on the geometry URL, like the availability cache, since
  // model files only change under a mod switch.
  const thumbCache = new Map(), thumbPending = new Map();
  let thumbQueue = Promise.resolve();
  function portrait(canvas) {
    const copy = document.createElement("canvas");
    copy.width = canvas.width; copy.height = canvas.height;
    const ctx = copy.getContext("2d");
    ctx.drawImage(canvas, 0, 0);
    const pixels = ctx.getImageData(0, 0, copy.width, copy.height).data;
    let left = copy.width, top = copy.height, right = -1, bottom = -1;
    for (let y = 0; y < copy.height; y++) for (let x = 0; x < copy.width; x++) {
      if (pixels[(y * copy.width + x) * 4 + 3]) {
        left = Math.min(left, x); right = Math.max(right, x);
        top = Math.min(top, y); bottom = Math.max(bottom, y);
      }
    }
    if (right < left) throw new Error("The model rendered no visible geometry");
    const cropped = document.createElement("canvas"), padding = 6;
    cropped.width = right - left + 1 + padding * 2;
    cropped.height = bottom - top + 1 + padding * 2;
    cropped.getContext("2d").drawImage(copy, left, top, right - left + 1, bottom - top + 1,
      padding, padding, right - left + 1, bottom - top + 1);
    return cropped.toDataURL("image/png");
  }
  async function snapshot(geometryUrl) {
    let stage, timer;
    try {
      return await new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error("Model preview timed out")), 15000);
        stage = document.createElement("div");
        stage.style.cssText = "position:fixed;left:-10000px;top:0;width:192px;height:192px;visibility:hidden;pointer-events:none";
        stage.setAttribute("aria-hidden", "true");
        document.body.append(stage);
        mount(stage, geometryUrl, {once: true, onFrame: canvas => resolve(portrait(canvas))})
          .then(task => { if (!task) reject(new Error("Model preview unavailable")); })
          .catch(reject);
      });
    } finally {
      clearTimeout(timer);
      if (stage) { stop(stage); stage.remove(); }
    }
  }
  function thumbnail(options) {
    const image = document.createElement("img");
    image.alt = `${options.label} model`;
    image.className = "ds1-model-thumbnail lex-image-pending";
    const key = options.url;
    requestAnimationFrame(async () => {
      if (!image.isConnected) return;
      try {
        let source = thumbCache.get(key);
        if (source) { thumbCache.delete(key); thumbCache.set(key, source); }
        else {
          let job = thumbPending.get(key);
          if (!job) {
            job = {images: []};
            job.promise = thumbQueue.then(async () => {
              if (!job.images.some(node => node.isConnected)) return null;
              const result = await snapshot(key);
              thumbCache.set(key, result);
              while (thumbCache.size > 32) thumbCache.delete(thumbCache.keys().next().value);
              return result;
            }).finally(() => thumbPending.delete(key));
            thumbQueue = job.promise.catch(() => {});
            thumbPending.set(key, job);
          }
          job.images.push(image);
          source = await job.promise;
        }
        if (image.isConnected && source) {
          image.src = source;
          image.dataset.modelReady = "true";
          image.classList.remove("lex-image-pending");
        }
      } catch (_error) {
        if (image.isConnected) image.replaceWith(window.LexeditorUI.noThumbnail("ds1"));
      }
    });
    return image;
  }
  return {mount, stop, thumbnail};
})();
