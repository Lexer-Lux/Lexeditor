window.Ds1Anim = (() => {
  let session = 0;
  const decode = b64 => Uint8Array.from(atob(b64), ch => ch.charCodeAt(0));
  const f32 = b64 => new Float32Array(decode(b64).buffer);
  const u32 = b64 => new Uint32Array(decode(b64).buffer);

  function stop(host) {
    if (host._animStop) { try { host._animStop(); } catch (_) {} host._animStop = null; }
    host.replaceChildren();
    delete host.dataset.ready;
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
  async function mount(host, chrId, motion, timeline, status) {
    stop(host);
    timeline.replaceChildren();
    const mine = ++session;
    if (!host.isConnected) return;
    if (!motion) { status.textContent = `${chrId}: no animations found.`; return; }
    if (motion.available === false) { status.textContent = `${motion.file}: ${motion.reason || "unreadable"}.`; return; }
    status.textContent = `Loading ${motion.file}.`;
    const THREE = await import("three");
    const {OrbitControls} = await import("three/addons/controls/OrbitControls.js");
    if (mine !== session || !host.isConnected) return;
    const [skel, geo, frames] = await Promise.all([
      get(`/api/anim/skeleton?chr=${encodeURIComponent(chrId)}`),
      get(`/api/chr/geometry?chr=${encodeURIComponent(chrId)}&skin=1`),
      get(`/api/anim/frames?chr=${encodeURIComponent(chrId)}&binder=${encodeURIComponent(motion.binder)}&anim=${encodeURIComponent(motion.file)}`),
    ]);
    if (mine !== session || !host.isConnected) return;
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
        bindQ.push(new THREE.Quaternion().setFromEuler(new THREE.Euler(bone.rot[0], bone.rot[1], bone.rot[2], "YZX")));
        bindS.push(bone.scale);
      }
    }
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
    bones.forEach((bone, i) => { (parents[i] >= 0 ? bones[parents[i]] : mover).add(bone); });
    mover.updateMatrixWorld(true);
    const skeleton = new THREE.Skeleton(bones, bones.map(bone => bone.matrixWorld.clone().invert()));
    const helper = new THREE.SkeletonHelper(mover);
    helper.material.linewidth = 1;
    rig.add(helper);
    const gray = new THREE.MeshStandardMaterial({color: 0x9aa3ad, roughness: 0.95, metalness: 0});
    trash.push(gray);
    for (const mesh of geo.meshes) {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(f32(mesh.positions), 3));
      g.setAttribute("normal", new THREE.BufferAttribute(f32(mesh.normals), 3));
      g.setIndex(new THREE.BufferAttribute(u32(mesh.indices), 1));
      const ids = u32(mesh.skin_ids);
      let wide = false;
      for (let i = 0; i < ids.length; i++) if (ids[i] > 65535) { wide = true; break; }
      g.setAttribute("skinIndex", wide ? new THREE.BufferAttribute(ids, 4)
                                       : new THREE.Uint16BufferAttribute(ids, 4));
      g.setAttribute("skinWeight", new THREE.Float32BufferAttribute(f32(mesh.skin_weights), 4));
      trash.push(g);
      const skinned = new THREE.SkinnedMesh(g, gray);
      skinned.frustumCulled = false;
      mover.add(skinned);
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
    window.addEventListener("resize", resize);

    const count = frames.frames, bonesTracked = frames.bones;
    const pos = f32(frames.translations), quat = f32(frames.rotations), scl = f32(frames.scales);
    const trot = frames.motion ? f32(frames.motion) : null;
    const frameDur = frames.frame_duration || frames.duration / Math.max(count - 1, 1);
    const state = {time: 0, playing: true, follow: false};
    timeline.style.display = "flex";
    timeline.style.gap = "8px";
    timeline.style.alignItems = "center";
    timeline.style.flexWrap = "wrap";
    const playButton = document.createElement("button");
    playButton.type = "button";
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-label", "Play or pause");
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = String(count - 1);
    slider.step = "0.01";
    slider.value = "0";
    slider.setAttribute("aria-label", "Frame");
    slider.style.flex = "1";
    slider.style.minWidth = "120px";
    const readout = document.createElement("span");
    readout.dataset.animReadout = "true";
    const followLabel = document.createElement("label");
    const follow = document.createElement("input");
    follow.type = "checkbox";
    followLabel.append(follow, document.createTextNode(" Root motion"));
    const markers = document.createElement("div");
    markers.className = "lex-anim-markers";
    markers.style.position = "relative";
    markers.style.flexBasis = "100%";
    markers.style.height = "12px";
    for (const event of frames.events || []) {
      const tick = document.createElement("button");
      tick.type = "button";
      tick.className = "lex-anim-marker";
      tick.title = `${event.label} (${event.start.toFixed(2)}s)`;
      tick.style.position = "absolute";
      tick.style.top = "0";
      tick.style.left = `${Math.min(event.start / frames.duration, 1) * 100}%`;
      tick.style.width = "4px";
      tick.style.height = "12px";
      tick.style.padding = "0";
      tick.style.border = "none";
      tick.style.background = "#b26a00";
      tick.style.cursor = "pointer";
      tick.setAttribute("aria-label", tick.title);
      tick.onclick = () => { state.time = event.start % frames.duration; };
      markers.append(tick);
    }
    timeline.append(playButton, slider, readout, followLabel, markers);
    playButton.onclick = () => {
      state.playing = !state.playing;
      playButton.textContent = state.playing ? "Pause" : "Play";
    };
    slider.oninput = () => { state.time = parseFloat(slider.value) * frameDur; };
    follow.onchange = () => { state.follow = follow.checked; };

    const tmpQ = new THREE.Quaternion(), tmpQ2 = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    const pose = frameFloat => {
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
      if (state.follow && trot) {
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
    const fps = (1 / frameDur).toFixed(1);
    status.textContent = `${motion.file}: ${count} frames at ${fps} fps, ${bones.length} bones` +
      (frames.events && frames.events.length ? `, ${frames.events.length} event cues.` : ", no event cues.");

    let frames2 = 0, liveFlag = true, last = performance.now();
    host._animStop = () => {
      liveFlag = false;
      window.removeEventListener("resize", resize);
      controls.dispose();
      renderer.dispose();
      for (const item of trash) item.dispose();
    };
    const loop = now => {
      if (!liveFlag || mine !== session || !host.isConnected) { stop(host); return; }
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      if (state.playing) state.time = (state.time + dt) % frames.duration;
      const shown = pose(state.time / frameDur);
      if (document.activeElement !== slider) slider.value = String(shown);
      readout.textContent = `${shown.toFixed(1)} / ${count - 1} frames · ${state.time.toFixed(2)}s`;
      controls.update();
      renderer.render(scene, camera);
      if (++frames2 === 2) host.dataset.ready = "true";
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
  return {mount, stop};
})();
