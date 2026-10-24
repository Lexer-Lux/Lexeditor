window.Ds1Anim = (() => {
  let session = 0;
  const decode = b64 => Uint8Array.from(atob(b64), ch => ch.charCodeAt(0));
  const f32 = b64 => new Float32Array(decode(b64).buffer);
  const u32 = b64 => new Uint32Array(decode(b64).buffer);

  function stop(host) {
    if (host._animViewer) { try { host._animViewer.stop(); } catch (_) {} host._animViewer = null; }
    else {
      host.replaceChildren();
      delete host.dataset.ready;
    }
    delete host._animBones;
    delete host._animMotion;
  }

  async function get(url) {
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || response.statusText);
    return data;
  }

  // Read-only skeletal playback: the model's bind pose comes from its
  // bones, each frame poses them from the sampled motion, and the
  // timeline scrubs frames with the motion's TAE event cues as markers.
  async function mount(host, chrId, motion, timeline, status, onEvent) {
    stop(host);
    timeline.replaceChildren();
    const mine = ++session;
    if (!host.isConnected) return;
    if (!motion) { status.textContent = `${chrId}: no animations found.`; return; }
    if (motion.available === false) { status.textContent = `${motion.file || motion.name}: ${motion.reason || "unreadable"}.`; return; }
    status.replaceChildren(LexeditorUI.loadingStatus(`Loading ${motion.file}`));
    const overlay = LexeditorUI.loadingPanel({label: `Loading ${motion.file}`});
    host.append(overlay);
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (mine !== session || !host.isConnected) { overlay.remove(); return; }
    // The player base ships no model of its own, so its geometry fetch
    // fails: that must not sink the mount, which falls back to the bare
    // Havok skeleton below.
    const [skel, geo, frames] = await Promise.all([
      get(`/api/anim/skeleton?chr=${encodeURIComponent(chrId)}`),
      get(`/api/chr/geometry?chr=${encodeURIComponent(chrId)}&skin=1`).catch(() => null),
      get(`/api/anim/frames?chr=${encodeURIComponent(chrId)}&binder=${encodeURIComponent(motion.binder)}&anim=${encodeURIComponent(motion.file)}`),
    ]);
    if (mine !== session || !host.isConnected) { overlay.remove(); return; }
    // Bones follow the model when it exists, else the Havok skeleton
    // alone (the player base has no visible mesh of its own).
    const names = skel.flver.length ? skel.flver.map(b => b.name) : skel.hka.bones;
    const parents = skel.flver.length ? skel.flver.map(b => b.parent) : skel.hka.parents;
    const mapped = skel.flver.length ? skel.map : skel.hka.bones.map((_, i) => i);
    const bindT = [], bindQ = [], bindS = [];
    for (let i = 0; i < names.length; i++) {
      const hka = mapped[i];
      if (hka >= 0) {
        const pose = skel.hka.pose[hka];
        bindT.push(pose.t);
        bindQ.push(new THREE.Quaternion(pose.q[0], pose.q[1], pose.q[2], pose.q[3]).normalize());
        bindS.push(pose.s);
      } else {
        const bone = skel.flver[i];
        bindT.push(bone.pos);
        // FLVER bone angles are radians in XZY order (soulstruct).
        bindQ.push(new THREE.Quaternion().setFromEuler(new THREE.Euler(bone.rot[0], bone.rot[1], bone.rot[2], "XZY")));
        bindS.push(bone.scale);
      }
    }
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.dataset.viewport = "true";
    host.append(canvas);
    const viewModes = LexeditorUI.modelViewModes(host);
    overlay.remove();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.01, 10000);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(1, 2, 1);
    scene.add(sun);
    const trash = [];
    const rig = new THREE.Group();
    scene.add(rig);
    const mover = new THREE.Group();
    rig.add(mover);
    const bones = names.map((name, i) => {
      const bone = new THREE.Bone();
      bone.name = name;
      bone.position.set(bindT[i][0], bindT[i][1], bindT[i][2]);
      bone.quaternion.copy(bindQ[i]);
      bone.scale.set(bindS[i][0], bindS[i][1], bindS[i][2]);
      return bone;
    });
    // Mapped bones follow the Havok hierarchy: the model carries
    // extra anchors the animation never moves, and hanging an
    // animated bone under one would offset its whole chain. Bones the
    // model only (SFX and dummy anchors) keep the model's own parent.
    const flverOfHka = new Map();
    mapped.forEach((hka, i) => { if (hka >= 0 && !flverOfHka.has(hka)) flverOfHka.set(hka, i); });
    const parentOf = i => {
      const hka = mapped[i];
      if (hka >= 0) {
        const seen = new Set([hka]);
        let hp = skel.hka.parents[hka];
        while (Number.isInteger(hp) && hp >= 0 && hp < skel.hka.parents.length &&
               !flverOfHka.has(hp) && !seen.has(hp)) {
          seen.add(hp);
          hp = skel.hka.parents[hp];
        }
        return flverOfHka.has(hp) ? flverOfHka.get(hp) : -1;
      }
      return parents[i];
    };
    bones.forEach((bone, i) => {
      const p = parentOf(i);
      (p >= 0 && p < bones.length && p !== i ? bones[p] : mover).add(bone);
    });
    mover.updateMatrixWorld(true);
    const skeleton = new THREE.Skeleton(bones, bones.map(bone => bone.matrixWorld.clone().invert()));
    // Test seam: live bone names and world positions, for alignment checks.
    host._animBones = () => bones.map(bone => {
      const at = new THREE.Vector3();
      bone.getWorldPosition(at);
      return {name: bone.name, pos: [at.x, at.y, at.z]};
    });
    const helper = new THREE.SkeletonHelper(mover);
    helper.material.linewidth = 1;
    rig.add(helper);
    const front = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0, side: THREE.FrontSide});
    const double = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0, side: THREE.DoubleSide});
    trash.push(front, double);
    // The same diffuse textures the model drawer shows: without them
    // every animated enemy renders gray.
    const texCache = new Map();
    const texLoader = new THREE.TextureLoader();
    const materialFor = async mesh => {
      const plain = mesh.cull !== false ? front : double;
      const png = mesh.map && geo.textures && geo.textures[mesh.map];
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
    for (const mesh of geo?.meshes || []) {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
      g.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
      if (mesh.uv) g.setAttribute("uv", new THREE.BufferAttribute(f32(mesh.uv), 2));
      g.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
      const ids = u32(mesh.skin_ids);
      let wide = false;
      for (let i = 0; i < ids.length; i++) if (ids[i] > 65535) { wide = true; break; }
      g.setAttribute("skinIndex", wide ? new THREE.BufferAttribute(ids, 4)
                                       : new THREE.Uint16BufferAttribute(ids, 4));
      g.setAttribute("skinWeight", new THREE.Float32BufferAttribute(f32(mesh.skin_weights), 4));
      trash.push(g);
      const skinned = new THREE.SkinnedMesh(g, await materialFor(mesh));
      if (mine !== session || !host.isConnected) {
        controls.dispose();
        renderer.dispose();
        for (const item of trash) item.dispose();
        return;
      }
      skinned.frustumCulled = false;
      // The mesh hangs off the rig, not the root-motion mover: the
      // bones already carry the mover's transform, so parenting the
      // mesh there too would move it twice.
      rig.add(skinned);
      skinned.bind(skeleton);
    }
    mover.updateMatrixWorld(true);
    const box = new THREE.Box3();
    rig.traverse(obj => { if (obj.isMesh) box.expandByObject(obj); });
    if (box.isEmpty()) for (const bone of bones) box.expandByPoint(bone.getWorldPosition(new THREE.Vector3()));
    const size = box.isEmpty() ? 2 : box.getSize(new THREE.Vector3()).length();
    const center = box.isEmpty() ? new THREE.Vector3() : box.getCenter(new THREE.Vector3());
    camera.position.set(center.x + size * 0.6, center.y + size * 0.45, center.z + size * 0.6);
    camera.far = Math.max(100, size * 10);
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    const resize = () => {
      const width = host.clientWidth || 800, height = host.clientHeight || 520;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const resizer = typeof ResizeObserver === "function" ? new ResizeObserver(() => resize()) : null;
    if (resizer) resizer.observe(host);
    else window.addEventListener("resize", resize);

    const count = frames.frames, bonesTracked = frames.bones;
    const pos = f32(frames.translations), quat = f32(frames.rotations), scl = f32(frames.scales);
    const trot = frames.motion ? f32(frames.motion) : null;
    const frameDur = frames.frame_duration || frames.duration / Math.max(count - 1, 1);

    const tmpQ = new THREE.Quaternion(), tmpQ2 = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    const pose = (frameFloat, follow) => {
      const wrapped = ((frameFloat % count) + count) % count;
      const first = Math.floor(wrapped), second = (first + 1) % count, alpha = wrapped - first;
      for (let i = 0; i < bones.length; i++) {
        const hka = mapped[i];
        if (hka < 0) continue;
        const a = (first * bonesTracked + hka), b = (second * bonesTracked + hka);
        bones[i].position.set(
          pos[a * 3] + (pos[b * 3] - pos[a * 3]) * alpha,
          pos[a * 3 + 1] + (pos[b * 3 + 1] - pos[a * 3 + 1]) * alpha,
          pos[a * 3 + 2] + (pos[b * 3 + 2] - pos[a * 3 + 2]) * alpha);
        tmpQ.set(quat[a * 4], quat[a * 4 + 1], quat[a * 4 + 2], quat[a * 4 + 3]);
        tmpQ2.set(quat[b * 4], quat[b * 4 + 1], quat[b * 4 + 2], quat[b * 4 + 3]);
        bones[i].quaternion.copy(tmpQ.slerp(tmpQ2, alpha));
        bones[i].scale.set(
          scl[a * 3] + (scl[b * 3] - scl[a * 3]) * alpha,
          scl[a * 3 + 1] + (scl[b * 3 + 1] - scl[a * 3 + 1]) * alpha,
          scl[a * 3 + 2] + (scl[b * 3 + 2] - scl[a * 3 + 2]) * alpha);
      }
      if (follow && trot) {
        const s = Math.floor(wrapped), t = (s + 1) % count, k = wrapped - s;
        mover.position.set(
          trot[s * 4] + (trot[t * 4] - trot[s * 4]) * k,
          trot[s * 4 + 1] + (trot[t * 4 + 1] - trot[s * 4 + 1]) * k,
          trot[s * 4 + 2] + (trot[t * 4 + 2] - trot[s * 4 + 2]) * k);
        mover.quaternion.setFromAxisAngle(up, trot[s * 4 + 3] + (trot[t * 4 + 3] - trot[s * 4 + 3]) * k);
      } else {
        mover.position.set(0, 0, 0);
        mover.quaternion.identity();
      }
      return wrapped;
    };
    // The shared viewer owns the scrub bar, transport row, shortcuts and
    // loop from here; this file only poses the skeleton and draws it. The
    // status line stays for loading and errors; a loaded motion writes
    // nothing there.
    viewModes.bindScene(scene);
    host._animViewer = LexeditorUI.animationViewer({
      host, timeline, status,
      frames: {count, duration: frames.duration, frameDuration: frameDur,
        events: (frames.events || []).map(event => ({start: event.start, label: event.label, id: event.id}))},
      onEvent,
      follow: {label: "Root motion"},
      render: (shown, playback) => {
        pose(shown, playback.follow);
        controls.update();
        renderer.render(scene, camera);
      },
      dispose: () => {
        delete host._animBones;
        host._animViewer = null;
        if (resizer) resizer.disconnect();
        else window.removeEventListener("resize", resize);
        controls.dispose();
        renderer.dispose();
        for (const item of trash) item.dispose();
      },
    });
    // The motion this viewer plays: event seeks land only while it
    // matches the events scope, never onto an older motion's cues.
    host._animMotion = `${chrId}|${motion.binder || ""}|${motion.file || ""}`;
  }
  return {mount, stop};
})();
