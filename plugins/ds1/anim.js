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
    if (!chrId) { status.textContent = "Select a character."; return; }
    // A character with no motion (or an unreadable one) still shows its
    // model at rest, the way the model viewer would, instead of an empty
    // viewport: only a playable file fetches frames below.
    const playable = motion && motion.available !== false && motion.file;
    const problem = !motion ? "" : (!motion.file
      ? (motion.reason || "This animation has no playable motion.")
      : `${motion.file}: ${motion.reason || "unreadable"}.`);
    // One throbber: the loading panel owns progress, and the status
    // line stays for errors and completion, not a second spinner.
    status.textContent = "";
    const overlay = LexeditorUI.loadingPanel({label: `Loading ${motion?.file || chrId}`});
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
      playable
        ? get(`/api/anim/frames?chr=${encodeURIComponent(chrId)}&binder=${encodeURIComponent(motion.binder)}&anim=${encodeURIComponent(motion.file)}`)
        : Promise.resolve(null),
    ]);
    if (mine !== session || !host.isConnected) { overlay.remove(); return; }
    // Bones follow the model when it exists, else the Havok skeleton
    // alone (the player base has no visible mesh of its own).
    const hasFlver = !!skel.flver.length;
    const names = hasFlver ? skel.flver.map(b => b.name) : skel.hka.bones;
    const parents = hasFlver ? skel.flver.map(b => b.parent) : skel.hka.parents;
    const mapped = hasFlver ? skel.map : skel.hka.bones.map((_, i) => i);
    // FLVER bone angles are radians in YZX order: composed that way,
    // every mapped bone's rotation matches its Havok rest quaternion
    // exactly (the old XZY reading spun tails and cloth skyward).
    const yzx = rot => new THREE.Quaternion()
      .setFromEuler(new THREE.Euler(rot[0], rot[1], rot[2], "YZX"));
    const composeLocal = (t, q, s) => new THREE.Matrix4().compose(
      new THREE.Vector3(t[0], t[1], t[2]), q, new THREE.Vector3(s[0], s[1], s[2]));
    // The Havok rig lives in its own shifted space: the same pose up to
    // 4m and 10 degrees from the model's bind (c5202's tail, c2280),
    // identity for most rigs. X maps the model bind to the Havok
    // rest, measured where the two meet (the Havok root's model
    // counterpart); the correction group applies X^-1 above the mapped
    // bones, so skinning and the skeleton agree in the model's own
    // space on every character. X keeps only the rigid motion
    // coinciding the two frames at the joint; a change of coordinates
    // cannot rescale the motion, whose amplitudes play
    // at Havok scale (a scale-2 Havok root doubles its children's
    // offsets, it does not shrink the rig to the model).
    const rigidT = new THREE.Vector3(), rigidQ = new THREE.Quaternion(),
      rigidS = new THREE.Vector3(), rigidOne = new THREE.Vector3(1, 1, 1);
    const jointH = new THREE.Vector3(), jointF = new THREE.Vector3(),
      jointTmp = new THREE.Vector3(), denseM = new THREE.Matrix4();
    const rigShift = (() => {
      if (!hasFlver) return new THREE.Matrix4();
      const href = skel.hka.bones.findIndex((name, h) => mapped.includes(h));
      const f = names.findIndex((name, i) => mapped[i] === href);
      if (href < 0 || f < 0) return new THREE.Matrix4();
      const chainWorld = (locals, parentsOf, at) => {
        const chain = [];
        const seen = new Set([at]);
        for (let p = at; Number.isInteger(p) && p >= 0;) {
          chain.unshift(locals[p]);
          const next = parentsOf[p];
          if (!Number.isInteger(next) || next < 0 || next >= locals.length || seen.has(next)) break;
          seen.add(next);
          p = next;
        }
        return chain.reduce((acc, local) => acc.multiply(local), new THREE.Matrix4());
      };
      const flverLocals = skel.flver.map(bone => composeLocal(bone.pos, yzx(bone.rot), bone.scale));
      const hkaLocals = skel.hka.pose.map(pose => composeLocal(pose.t,
        new THREE.Quaternion(pose.q[0], pose.q[1], pose.q[2], pose.q[3]).normalize(), pose.s));
      const flverParents = skel.flver.map(bone => bone.parent);
      const hWorld = chainWorld(hkaLocals, skel.hka.parents, href);
      const fWorld = chainWorld(flverLocals, flverParents, f);
      jointH.setFromMatrixPosition(hWorld);
      jointF.setFromMatrixPosition(fWorld);
      denseM.multiplyMatrices(hWorld, fWorld.invert());
      // The rigid motion coinciding the two frames at the joint: X's
      // rotation, with the translation mapping the model's joint
      // position onto the Havok one (decompose's own translation
      // couples in scale, which the frames do not share).
      denseM.decompose(rigidT, rigidQ, rigidS);
      rigidT.copy(jointH).sub(jointTmp.copy(jointF).applyQuaternion(rigidQ));
      return new THREE.Matrix4().compose(rigidT, rigidQ, rigidOne);
    })();
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
    const correction = new THREE.Group();
    correction.matrixAutoUpdate = false;
    correction.matrix.copy(rigShift).invert();
    mover.add(correction);
    const bones = names.map((name, i) => {
      const bone = new THREE.Bone();
      bone.name = name;
      const hka = mapped[i];
      if (hka >= 0) {
        const rest = skel.hka.pose[hka];
        bone.position.set(rest.t[0], rest.t[1], rest.t[2]);
        bone.quaternion.set(rest.q[0], rest.q[1], rest.q[2], rest.q[3]).normalize();
        bone.scale.set(rest.s[0], rest.s[1], rest.s[2]);
      } else {
        const boneDef = skel.flver[i];
        bone.position.set(boneDef.pos[0], boneDef.pos[1], boneDef.pos[2]);
        bone.quaternion.copy(yzx(boneDef.rot));
        bone.scale.set(boneDef.scale[0], boneDef.scale[1], boneDef.scale[2]);
      }
      return bone;
    });
    // Mapped bones follow the Havok hierarchy: the model carries
    // extra anchors the animation never moves, and hanging an
    // animated bone under one would offset its whole chain. Bones the
    // model only (SFX and dummy anchors, never under a mapped bone)
    // keep the model's own parent under the mover, outside the
    // correction that only the Havok-mapped bones need.
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
      const under = p >= 0 && p < bones.length && p !== i ? bones[p]
        : (mapped[i] >= 0 ? correction : mover);
      under.add(bone);
    });
    mover.updateMatrixWorld(true);
    const skeleton = new THREE.Skeleton(bones, bones.map(bone => bone.matrixWorld.clone().invert()));
    // Test seam: live bone names, world positions, mapped flags and
    // world-matrix peaks, for alignment and finiteness checks.
    host._animBones = () => bones.map((bone, i) => {
      const at = new THREE.Vector3();
      bone.getWorldPosition(at);
      let peak = 0;
      for (const value of bone.matrixWorld.elements)
        if (Number.isFinite(value)) peak = Math.max(peak, Math.abs(value));
        else return {name: bone.name, mapped: mapped[i] >= 0,
          pos: [at.x, at.y, at.z], peak: String(value)};
      return {name: bone.name, mapped: mapped[i] >= 0, pos: [at.x, at.y, at.z], peak};
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

    const dispose = () => {
      delete host._animBones;
      host._animViewer = null;
      if (resizer) resizer.disconnect();
      else window.removeEventListener("resize", resize);
      controls.dispose();
      renderer.dispose();
      for (const item of trash) item.dispose();
    };
    viewModes.bindScene(scene);
    // The motion this viewer plays: event seeks land only while it
    // matches the events scope, never onto an older motion's cues.
    host._animMotion = `${chrId}|${motion?.binder || ""}|${motion?.file || ""}`;
    if (!frames) {
      // Bind pose: no playable motion, so the model simply holds its
      // rest pose (set above) and redraws only as the reader orbits it.
      // An unreadable selection names its reason in the status line; a
      // character with no motions at all explains itself through its
      // disabled Animations tab instead.
      const still = () => { controls.update(); renderer.render(scene, camera); };
      still();
      // Ready, like the playback path once its frames land: the still
      // frame is on screen.
      host.dataset.ready = "true";
      controls.addEventListener("change", still);
      status.textContent = problem;
      host._animViewer = {toEvent: null, stop: () => {
        controls.removeEventListener("change", still);
        dispose();
      }};
      return;
    }

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
      dispose,
    });
  }
  return {mount, stop};
})();
