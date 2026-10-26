"use strict";

(() => {
  const sharedAssetBase = new URL(".", document.currentScript?.src || document.baseURI);
  const embeddedEditor = window.parent !== window && window.name === "lexeditor-editor";
  if (embeddedEditor) {
    let nextCall = 0;
    const pending = new Map();
    window.pywebview = {api: new Proxy({}, {get: (_target, method) => (...args) => new Promise((resolve, reject) => {
      const id = ++nextCall;
      pending.set(id, {resolve, reject});
      parent.postMessage({type: "lexeditor-host-call", id, method, args}, "*");
    })})};
    addEventListener("message", event => {
      if (event.source !== parent) return;
      const message = event.data;
      if (message?.type === "lexeditor-host-result") {
        const call = pending.get(message.id);
        if (!call) return;
        pending.delete(message.id);
        if (message.error) call.reject(new Error(message.error));
        else call.resolve(message.result);
      } else if (message?.type === "lexeditor-host-event" &&
        ["__lexeditorRequestWindowClose", "__lexeditorNavigateHistory", "__lexeditorApplyWindowState"].includes(message.name)) {
        window[message.name]?.(...message.args);
      }
    });
    document.documentElement.classList.remove("lex-transition-entry", "lex-transition-loading");
    setTimeout(() => dispatchEvent(new Event("pywebviewready")), 0);
  }
  const transitionKind = embeddedEditor ? null : new URLSearchParams(location.search).get("lexTransition");
  if (["load", "resume"].includes(transitionKind)) {
    document.documentElement.classList.add("lex-transition-entry");
  }
  let transitionSurface = null;
  let transitionBackdrop = null;
  let transitionBackdropReady = null;

  const rawHostCall = name => new Promise((resolve, reject) => {
    const invoke = () => Promise.resolve(window.pywebview?.api?.[name]?.()).then(resolve, reject);
    if (window.pywebview?.api?.[name]) invoke();
    else window.addEventListener("pywebviewready", invoke, {once: true});
  });

  const wrapTransitionSurface = () => {
    if (transitionSurface) return transitionSurface;
    transitionSurface = document.createElement("div");
    transitionSurface.className = "lex-plugin-transition-surface";
    [...document.body.children].filter(node => node.tagName !== "SCRIPT" &&
      !node.classList?.contains("lex-plugin-loading-screen") &&
      !node.classList?.contains("lex-plugin-transition-backdrop"))
      .forEach(node => transitionSurface.append(node));
    document.body.prepend(transitionSurface);
    return transitionSurface;
  };

  const ensureTransitionBackdrop = async () => {
    if (transitionBackdropReady) return transitionBackdropReady;
    transitionBackdropReady = (async () => {
      const payload = await rawHostCall("transition_snapshot");
      if (!payload?.html) return null;
      transitionBackdrop = document.createElement("iframe");
      transitionBackdrop.className = "lex-plugin-transition-backdrop";
      transitionBackdrop.setAttribute("aria-hidden", "true");
      transitionBackdrop.tabIndex = -1;
      transitionBackdrop.srcdoc = payload.html;
      document.body.prepend(transitionBackdrop);
      // "load" only means the document parsed. Sliding before the iframe has
      // actually painted shows an empty backdrop, which reads as the menu
      // contents flickering out. Wait for load, then for real paint, with a
      // longer safety net so a slow snapshot cannot hang the transition.
      await new Promise(resolve => {
        transitionBackdrop.addEventListener("load", resolve, {once: true});
        setTimeout(resolve, 400);
      });
      await waitForPaint();
      await waitForPaint();
      return transitionBackdrop;
    })();
    return transitionBackdropReady;
  };

  const animateSurface = async (node, from, to) => {
    if (!node?.animate) return;
    const duration = 300;
    const animation = node.animate([
      {transform: `translate3d(${from},0,0)`}, {transform: `translate3d(${to},0,0)`},
    ], {duration, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards"});
    try {
      await Promise.race([animation.finished, new Promise(resolve => setTimeout(resolve, duration + 80))]);
    } catch (_error) {}
    node.style.transform = `translate3d(${to},0,0)`;
    await waitForPaint();
    animation.cancel();
  };

  const waitForPaint = () => Promise.race([
    new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    new Promise(resolve => setTimeout(resolve, 80)),
  ]);

  const settleTransitionSurface = () => transitionSurface?.classList.add("settled");
  const panDocument = async (from, to) => {
    if (embeddedEditor) return;
    const surface = wrapTransitionSurface();
    if (to === "100vw") {
      // Dropping "settled" flips the surface from relative back to fixed.
      // Doing that in the same frame the slide starts is a layout jump, which
      // is the flicker at the beginning of this direction. Let the new
      // positioning paint once before anything moves.
      surface.classList.remove("settled");
      await waitForPaint();
      const backdrop = await ensureTransitionBackdrop();
      if (backdrop) backdrop.style.transform = "translateX(-100vw)";
      await Promise.all([
        animateSurface(surface, from, to),
        backdrop ? animateSurface(backdrop, "-100vw", "0") : Promise.resolve(),
      ]);
      return;
    }
    if (from === "100vw" && transitionBackdrop) {
      await Promise.all([
        animateSurface(surface, from, to),
        animateSurface(transitionBackdrop, "0", "-100vw"),
      ]);
      settleTransitionSurface();
      // The blink at the end was the backdrop going while the destination had
      // not painted yet. Fading it only stretched that gap out. Wait for the
      // destination to actually paint, then drop the backdrop in one frame.
      await waitForPaint();
      await waitForPaint();
      transitionBackdrop.remove();
      transitionBackdrop = null;
      transitionBackdropReady = null;
    } else {
      await animateSurface(surface, from, to);
    }
    settleTransitionSurface();
  };

  if (["load", "resume"].includes(transitionKind)) {
    wrapTransitionSurface().style.transform = "translateX(100vw)";
    transitionBackdropReady = ensureTransitionBackdrop();
    transitionBackdropReady.finally(async () => {
      await waitForPaint();
      document.documentElement.classList.remove("lex-transition-entry");
    });
  }

  document.addEventListener("wheel", event => {
    if (event.ctrlKey) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, {capture:true, passive:false});

  // The title is navigation chrome, including after returning to the chooser.
  // Handle pointer input before the browser starts a text-selection gesture.
  const protectBrandText = event => {
    const brand=event.target.closest?.(".lex-brand-button,.chooser-title");
    if (!brand || (event.type==="pointerdown" && event.button!==0)) return;
    event.preventDefault();
    const selection=window.getSelection();
    if (selection && (brand.contains(selection.anchorNode) || brand.contains(selection.focusNode)))
      selection.removeAllRanges();
  };
  document.addEventListener("pointerdown", protectBrandText, {capture:true});
  document.addEventListener("selectstart", protectBrandText, {capture:true});
  for (const name of ['mousedown','mouseup','dblclick'])
    window.addEventListener(name,protectBrandText,{capture:true});
  document.addEventListener('selectionchange',()=>{
    const selection=window.getSelection();
    if (selection && [selection.anchorNode,selection.focusNode].some(node=>
      node?.parentElement?.closest('.lex-brand-button,.chooser-title')))
      selection.removeAllRanges();
  });

  // Spelling marks belong to the active editor, never a read-only value.
  document.documentElement.spellcheck=false;
  document.addEventListener('focusin',event=>{
    const field=event.target;
    if(field.matches?.('textarea,input[type="text"],[contenteditable="true"]') && !field.readOnly)
      field.spellcheck=field.inputMode!=='decimal' && !field.closest('.lex-code-editor');
  });
  document.addEventListener('focusout',event=>{
    if(event.target.matches?.('textarea,input,[contenteditable="true"]'))event.target.spellcheck=false;
  });

  // One matcher for every glow path: a pinned column's pin: prefix is
  // stripped before comparing, so pin:sellValue lights the sellValue
  // field, its cells, and (off-tab) its tab, and the bare sellValue
  // key lights the pinned column back.
  const stripPinPrefix = key => String(key ?? "").replace(/^pin:/, "");
  const glowSelector = key => {
    const raw = String(key ?? "");
    const base = stripPinPrefix(raw);
    // The match runs both ways: a header carries its pin: prefix while
    // its property does not, so an unprefixed key also matches the
    // pinned column, and hovering the field lights its header back.
    const columns = raw === base
      ? [`[data-column-key="${CSS.escape(raw)}"]`, `[data-column-key="pin:${CSS.escape(raw)}"]`]
      : [`[data-column-key="${CSS.escape(raw)}"]`, `[data-column-key="${CSS.escape(base)}"]`];
    return [...columns, `[data-lex-property="${CSS.escape(base)}"]`].join(",");
  };
  const element = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    // A textarea or a select has no value attribute: setting one left every
    // Warband and Palworld text box empty. Their value is set as a property,
    // once the options or the text are in.
    const propertyValue = /^(textarea|select)$/i.test(tag) && attrs.value !== undefined && attrs.value !== null;
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "value" && propertyValue) continue;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (value === true) node.setAttribute(key, "");
      else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value);
    }
    for (const child of children.flat(Infinity)) {
      if (child !== null && child !== undefined && child !== false) node.append(child);
    }
    if (propertyValue) node.value = String(attrs.value);
    return node;
  };

  const uiScaleControl = () => {
    const value = element("output", {}, "100%");
    const slider = element("input", {type:"range", min:50, max:150, step:5, value:100,
      "aria-label":"UI scale", "aria-valuetext":"100%"});
    let pending = null, running = false;
    // Five-percent increments only: the slider quantizes drags and keys,
    // and stored or scripted values snap on the way in.
    const snap = raw => Math.min(150, Math.max(50, Math.round(Number(raw) / 5) * 5));
    const applyBarScale = percent => document.documentElement.style.setProperty("--lex-ui-scale", String(percent / 100));
    const show = raw => { const percent=snap(raw); slider.value=percent; value.textContent=`${percent}%`; slider.setAttribute("aria-valuetext",`${percent}%`); };
    const apply = async () => {
      if(running)return;
      running=true;
      try {
        while(pending!==null){const percent=pending;pending=null;const result=await callWindow("ui_scale",percent);applyBarScale(result?.percent||percent);}
      } catch(error){showToast(`Could not change UI scale: ${error.message||error}`,true);}
      finally{running=false;}
    };
    slider.addEventListener("input",()=>show(Number(slider.value)));
    slider.addEventListener("change",()=>{pending=snap(slider.value);apply();});
    const initialize=async()=>{try{const result=await callWindow("ui_scale");if(result?.percent&&!running){show(result.percent);applyBarScale(result.percent);}}catch(_error){}};
    if(window.pywebview?.api)initialize();else window.addEventListener("pywebviewready",initialize,{once:true});
    return element("label",{class:"lex-ui-scale",title:"UI scale. Right-click to reset to 100%.",
      "data-lex-history-control":true,oncontextmenu:event=>{
        event.preventDefault();show(100);pending=100;apply();
      }},slider,value);
  };

  let pluginLoadingScreen = null;
  const semanticSoundSlots = new Set(["confirm", "back", "move", "launch", "exit", "save"]);
  let themeSoundUrls = {};
  const activeThemeSounds = new Set();
  const themeSoundGain = value => {
    const level = Math.max(0, Math.min(100, Number(value) || 0)) / 100;
    return level * level;
  };
  const stopThemeSounds = () => {
    for (const audio of activeThemeSounds) {
      try { audio.pause(); audio.currentTime = 0; } catch (_error) {}
    }
    activeThemeSounds.clear();
  };
  const configureThemeSounds = value => {
    const rows = Array.isArray(value) ? value : (value?.rows || []);
    themeSoundUrls = Object.fromEntries(rows
      .filter(row => semanticSoundSlots.has(row.slot) && row.available && row.url)
      .map(row => [row.slot, row.url]));
    return {...themeSoundUrls};
  };
  const playThemeSound = slot => {
    if (!semanticSoundSlots.has(slot) || sharedSettingsSnapshot?.soundEnabled === false) return false;
    const url = themeSoundUrls[slot];
    if (!url) return false;
    const gain = themeSoundGain(sharedSettingsSnapshot?.soundVolumePercent ?? 50);
    if (gain <= 0) return false;
    try {
      const audio = new Audio(url);
      audio.preload = "auto";
      audio.volume = gain;
      activeThemeSounds.add(audio);
      const release = () => activeThemeSounds.delete(audio);
      audio.addEventListener?.("ended", release, {once:true});
      audio.addEventListener?.("error", release, {once:true});
      audio.play().catch(() => {});
      return true;
    } catch (_error) { return false; }
  };
  // The loading quote is remembered for the next page in this window. A page
  // whose storage is refused (a sandboxed or embedded document, a browser
  // set to block it) threw on the first read, and the throw stopped the whole
  // framework from loading: every game came up blank.
  const sessionQuote = {
    get: () => { try { return sessionStorage.getItem("lex-loading-quote"); } catch (_error) { return null; } },
    set: value => { try { sessionStorage.setItem("lex-loading-quote", value); } catch (_error) {} },
  };
  const loadingParameters = new URLSearchParams(location.search);
  const loadingStartedAt = (() => {
    const supplied = Number(loadingParameters.get("lexLoadStarted"));
    return Number.isFinite(supplied) && supplied > 0 ? supplied : Date.now();
  })();
  window.addEventListener('lexeditor-loading-status', event => {
    if (!pluginLoadingScreen) return;
    let status = pluginLoadingScreen.querySelector('.lex-plugin-loading-status');
    if (!status) {
      status = element('p', {class:'lex-plugin-loading-status'});
      pluginLoadingScreen.append(status);
    }
    status.textContent = String(event.detail?.message || '');
  });
  if (document.getElementById("lexeditor-shell") && transitionKind !== "resume") {
    pluginLoadingScreen = element("div", {
      class: ["lex-plugin-loading-screen",
        loadingParameters.get("lexLoadStarted") ? "continued" : ""].filter(Boolean).join(" "),
      role: "status", "aria-live": "polite",
      "aria-label": "Loading game editor",
    }, element("blockquote", {class: "lex-plugin-loading-quote"},
      loadingParameters.get("lexQuote") || sessionQuote.get() || "Loading editor…"),
    element("span", {class: "lex-plugin-loading-pulse", "aria-hidden": "true"}));
    document.body.append(pluginLoadingScreen);
    // The root already painted an identical screen; hand over without a blink.
    document.documentElement.classList.add("lex-loading-live");
    if(loadingParameters.get("lexQuote"))sessionQuote.set(loadingParameters.get("lexQuote"));
    for(const type of ["keydown","pointerdown","click"])document.addEventListener(type,event=>{
      if(document.documentElement.classList.contains("lex-loading-live")){event.preventDefault();event.stopImmediatePropagation();}
    },true);
  }

  const finishPluginLoading = async () => {
    const screen = pluginLoadingScreen;
    pluginLoadingScreen = null;
    if (screen || (embeddedEditor && loadingParameters.get("lexTransition") === "load")) {
      let settings = sharedSettingsSnapshot;
      if (!settings) {
        try { settings = rememberSharedSettings(await callWindow("lexeditor_settings")); }
        catch (_error) {}
      }
      const seconds = Math.max(0, Math.min(10,
        Number(settings?.loadingTransitionMinimumSeconds ?? 1.5) || 0));
      const remaining = seconds * 1000 - (Date.now() - loadingStartedAt);
      if (remaining > 0) await new Promise(resolve => setTimeout(resolve, remaining));
    }
    if (embeddedEditor) {
      await document.fonts.ready;
      await rawHostCall("editor_ready");
    }
    if (["load", "resume"].includes(transitionKind)) {
      const backdrop = await transitionBackdropReady;
      await Promise.all([
        animateSurface(transitionSurface, "100vw", "0"),
        backdrop ? animateSurface(backdrop, "0", "-100vw") : Promise.resolve(),
      ]);
      settleTransitionSurface();
      await waitForPaint();
      backdrop?.remove();
      transitionBackdrop = null;
      transitionBackdropReady = null;
    }
    document.documentElement.classList.remove("lex-transition-loading", "lex-loading-live");
    if (screen) screen.classList.add("closing");
    if (screen) setTimeout(() => screen.remove(), 360);
    const url = new URL(location.href);
    url.searchParams.delete("lexTransition");
    url.searchParams.delete("lexQuote");
    url.searchParams.delete("lexLoadStarted");
    history.replaceState(history.state, "", `${url.pathname}${url.search}${url.hash}`);
    playThemeSound("launch");
  };

  // Short-lived confirmations. One stack, oldest dropped first, so a burst of
  // copies cannot bury the screen.
  let toastStack = null;
  // A toast takes the pointer: pointing at it holds it, a click dismisses it.
  // It used to ignore the pointer and fade when hovered, which is exactly why
  // it could not be clicked away.
  const showToast = (message, options = {}) => {
    if (!toastStack || !toastStack.isConnected) {
      toastStack = element("div", {class: "lex-toast-stack", role: "status", "aria-live": "polite"});
      document.body.append(toastStack);
    }
    // A game may seat its toasts under the window bar; say where that ends, on
    // the root, where a game's own token that reads it is declared.
    const header = document.querySelector(".lex-shell-header");
    if (header) document.documentElement.style.setProperty("--lex-shell-header-bottom",
      `${Math.round(header.getBoundingClientRect().bottom)}px`);
    const tone = options === true ? "warning" : options.tone;
    const toast = element("div", {class: ["lex-toast", tone ? `lex-tone-${tone}` : ""].filter(Boolean).join(" ")}, message);
    toastStack.append(toast);
    while (toastStack.children.length > 4) toastStack.firstElementChild.remove();
    // Long enough to read - Lexer: "the toasts disappear way too quick and
    // can't be dispelled by clicking them". A toast stays at least four
    // seconds and longer for longer text, waits while it is pointed at, and a
    // click sends it away at once.
    const text = String(toast.textContent || "");
    const readFor = Number(options.duration) || Math.min(10000, Math.max(4000, text.length * 70));
    let timer = 0;
    const leave = () => {
      clearTimeout(timer);
      if (toast.classList.contains("leaving")) return;
      toast.classList.add("leaving");
      setTimeout(() => toast.remove(), 220);
    };
    const wait = delay => { clearTimeout(timer); timer = setTimeout(leave, delay); };
    toast.title = "Click to dismiss";
    toast.addEventListener("click", leave);
    toast.addEventListener("pointerenter", () => clearTimeout(timer));
    toast.addEventListener("pointerleave", () => wait(1500));
    wait(Math.max(900, readFor));
    return toast;
  };

  const copyText = async (text, options = {}) => {
    const done = copied => {
      if (options.quiet !== true) {
        showToast(copied ? (options.message || "Copied.") : "Could not copy that.", !copied);
      }
      return copied;
    };
    try {
      await navigator.clipboard.writeText(text);
      return done(true);
    } catch (_error) {
      // WebView clipboard permissions vary; fall back to a scratch selection.
      const scratch = element("textarea", {
        style: "position:fixed;top:-1000px;left:-1000px;opacity:0", value: text,
      });
      document.body.append(scratch);
      scratch.select();
      let copied = false;
      try { copied = document.execCommand("copy"); } catch (_ignored) {}
      scratch.remove();
      return done(copied);
    }
  };

  const copyIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    // Cropped to the drawing. On a 0 0 24 24 box the two sheets only reach from
    // 4 to 20 across, so a third of the button was blank margin built into the
    // icon - which read as a button adrift in a column too wide for it, on top
    // of whatever the column itself was reserving.
    svg.setAttribute("viewBox", "4 2 16 20");
    svg.setAttribute("aria-hidden", "true");
    for (const d of ["M9 9h10v12H9z", "M5 15V3h10v2"]) {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "currentColor");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };

  // The remove mark beside the copy icon in record headings: a bin, drawn
  // in the same stroke as the copy icon and cropped to the drawing.
  const removeIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "3 3 18 18");
    svg.setAttribute("aria-hidden", "true");
    for (const d of ["M4 7h16", "M9.5 7V5h5v2", "M6.5 7l.8 13h9.4l.8-13", "M10 10.5v7M14 10.5v7"]) {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "currentColor");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };

  // The add mark on header buttons that add something new: a bare plus,
  // drawn in the same stroke as the copy and remove icons and cropped
  // to the drawing.
  const addIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "3 3 18 18");
    svg.setAttribute("aria-hidden", "true");
    for (const d of ["M12 5v14M5 12h14"]) {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "currentColor");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };

  // The section mark on the dev-mode Add-section header button: a panel
  // block with a header divider, drawn in the same stroke as the copy
  // and remove icons. A bare plus here read as the record add button
  // that lives in the list panel.
  const sectionIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "3 3 18 18");
    svg.setAttribute("aria-hidden", "true");
    for (const d of ["M4 4h16v16H4z", "M4 9h16"]) {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "currentColor");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };

  // One "no image" mark for every place a picture is missing: a record with
  // no art of its own, or an image that failed to load. It replaces the
  // browser's broken-image glyph and alt text ("[mapid] composed background").
  const noImage = (label = "No image") => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const frame = document.createElementNS(namespace, "path");
    frame.setAttribute("d", "M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M3 3l18 18");
    svg.append(frame);
    return element("span", {class: "lex-no-image", role: "img", "aria-label": label, title: label}, svg);
  };

  // A model that exists but has no still picture: the placeholder behind
  // the magnifier. Plugins register their own art; everyone else gets the
  // shared mark. The art is UI chrome, never game art: game art ships
  // only as real record pictures, decoded at runtime.
  const noThumbnailMakers = new Map();
  const registerNoThumbnail = (plugin, make) => {
    if (make == null) noThumbnailMakers.delete(plugin);
    else noThumbnailMakers.set(plugin, make);
  };
  const noThumbnail = (plugin = "", label = "No thumbnail") => {
    const make = plugin ? noThumbnailMakers.get(plugin) : null;
    const art = make ? make(label) : noImage(label);
    if (art instanceof Element) art.classList.add("lex-no-thumbnail");
    return art;
  };
  document.addEventListener("error", event => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || image.dataset.lexNoImage === "off" || !image.isConnected) return;
    if (image.nextElementSibling?.classList.contains("lex-no-image-standin")) return;
    const standin = noImage(image.alt ? `No image: ${image.alt}` : "No image");
    standin.classList.add("lex-no-image-standin");
    image.after(standin);
    image.hidden = true;
    image.addEventListener("load", () => { image.hidden = false; standin.remove(); }, {once: true});
  }, true);

  const newButton = (attrs = {}) => {
    const {class: className = "", title = "Add", "aria-label": ariaLabel = title, ...rest} = attrs;
    return element("button", {
      type: "button", ...rest,
      class: ["lex-new-button lex-ui-symbol", className].filter(Boolean).join(" "),
      title, "aria-label": ariaLabel,
    }, element("span", {class: "lex-new-button-plus", "aria-hidden": "true"}, "+"));
  };

  // Actions that wait quietly over their host: invisible until the host is
  // hovered, half-visible then, and full under the pointer or keyboard
  // focus. hoverActions(host, {actions, align, label, overlay}) marks the
  // host, adds the bar and returns it. Each action either builds a square
  // button ({key, label, title, icon, className, disabled, onClick}) or
  // adopts a ready-made one ({key, node}). An inline bar sits in the flow
  // instead of overlaying the host's corner.
  const HOVER_ALIGN = {"top-left": "lex-hover-actions-tl", "top-right": "lex-hover-actions-tr",
    "bottom-left": "lex-hover-actions-bl", "bottom-right": "lex-hover-actions-br"};
  const hoverActions = (host, options = {}) => {
    const bar = element("div", {
      class: ["lex-hover-actions", HOVER_ALIGN[options.align] || "lex-hover-actions-tr",
        options.overlay === false ? "lex-hover-actions-inline" : ""].filter(Boolean).join(" "),
      role: "toolbar", "aria-label": options.label || "Actions",
    }, ...(options.actions || []).map(action => {
      if (action.node instanceof Element) {
        if (action.key) action.node.dataset.hoverAction = action.key;
        return action.node;
      }
      return element("button", {
        type: "button", disabled: !!action.disabled,
        class: ["lex-new-button", "lex-hover-action", action.className || ""].filter(Boolean).join(" "),
        ...(action.key ? {"data-hover-action": action.key} : {}),
        title: action.title || action.label || "",
        "aria-label": action.label || action.title || "Action",
        onclick: event => action.onClick?.(event),
      }, action.icon || action.label || "");
    }));
    if (host instanceof Element) {
      host.classList.add("lex-hover-actions-host");
      host.append(bar);
    }
    return bar;
  };

  // A tab strip for caller-owned tabs (collapsible panels, detail panels):
  // given order, no shortcuts, optional dev rename. Not subtabBar: that one
  // sorts, and its rename keys belong to page subtabs.
  const tabStrip = (options = {}) => {
    const bar = element("div", {
      class: ["lex-tabstrip", options.className || ""].filter(Boolean).join(" "),
      role: "tablist", "aria-label": options.label || "Views",
    });
    const buttons = new Map();
    for (const tab of options.tabs || []) {
      const on = tab.id === options.active;
      // A disabled tab stays focusable (a truly disabled button eats
      // its tooltip): aria-disabled grays it, the click is a no-op,
      // and the reason rides on the title.
      const off = !!tab.disabled;
      const button = element("button", {type: "button",
        class: ["lex-subtab-button", "lex-tabstrip-button", on ? "active" : ""].filter(Boolean).join(" "),
        role: "tab", "aria-selected": String(on), tabindex: on ? "0" : "-1",
        "data-tabstrip-id": tab.id,
        ...(off ? {"aria-disabled": "true", title: tab.disabledReason || "Unavailable"} : {}),
        onclick: () => { if (!off) options.change?.(tab.id); },
      }, element("span", {class: "lex-tab-label lex-tabstrip-label"}, tab.label ?? tab.id));
      if (typeof options.onRename === "function") {
        button.addEventListener("dblclick", event => {
          if (!sharedSettingsSnapshot?.developerMode) return;
          event.preventDefault();
          event.stopPropagation();
          options.onRename(tab.id, button);
        });
      }
      if (options.holdToSave) holdToSaveDefaultView(button);
      bar.append(button);
      buttons.set(tab.id, button);
    }
    bar.setActive = id => {
      for (const [key, button] of buttons) {
        const on = key === id;
        button.classList.toggle("active", on);
        button.setAttribute("aria-selected", String(on));
        button.tabIndex = on ? 0 : -1;
      }
    };
    bar.setLabel = (id, label) => {
      buttons.get(id)?.querySelector(".lex-tabstrip-label")?.replaceChildren(label);
    };
    return bar;
  };

  // Kept for later use: no screen uses collapsible panels right now.
  // A side panel that shrinks to a clickable handle and expands pushing its
  // siblings over. {tabs:[{id,label,content}], active, onChange, side, label,
  // width, collapsed, viewKey, className, attrs}. Collapse state stays
  // personal (plain localStorage, never shipped); pass no viewKey for
  // session-only memory.
  const collapsiblePanel = (options = {}) => {
    const side = options.side === "right" ? "right" : "left";
    const storeKey = options.viewKey ? `lex-collapsible-${options.viewKey}` : null;
    const stored = name => {
      try { return storeKey ? localStorage.getItem(`${storeKey}.${name}`) : null; }
      catch (_error) { return null; }
    };
    const remember = (name, value) => {
      if (!storeKey) return;
      try { localStorage.setItem(`${storeKey}.${name}`, value); } catch (_error) {}
    };
    const tabs = (options.tabs || []).map(tab => ({
      ...tab,
      label: stored(`label.${tab.id}`) || tab.label,
    }));    const root = element("section", {
      ...(options.attrs || {}),
      class: ["lex-collapsible-panel", `lex-collapsible-${side}`, options.className || ""].filter(Boolean).join(" "),
      "aria-label": options.label || "Side panel",
    });
    const panes = new Map();
    const paneBox = element("div", {class: "lex-collapsible-panes"},
      ...tabs.map(tab => {
        const pane = element("div", {class: "lex-collapsible-pane", role: "tabpanel",
          "data-tabstrip-pane": tab.id}, tab.content || []);
        panes.set(tab.id, pane);
        return pane;
      }));
    const show = id => {
      const next = tabs.some(tab => tab.id === id) ? id : tabs[0]?.id;
      if (next === undefined) return;
      strip.setActive(next);
      for (const [key, pane] of panes) pane.hidden = key !== next;
      remember("tab", next);
      options.onChange?.(next);
    };
    const strip = tabs.length ? tabStrip({tabs, active: stored("tab") || options.active,
      label: options.label || "Side panel views", className: "lex-collapsible-tabs",
      change: show, holdToSave: true,
      onRename: async id => {
        const tab = tabs.find(entry => entry.id === id);
        const label = await promptText({title: "Rename panel tab", label: "Tab name",
          value: tab?.label || "", confirmLabel: "Rename"});
        if (!label) return;
        tab.label = label;
        remember(`label.${id}`, label);
        strip.setLabel(id, label);
      }}) : null;
    const body = element("div", {class: "lex-collapsible-body"},
      strip || null, tabs.length ? paneBox : (options.content || []));
    const chevron = element("span", {class: "lex-collapsible-chevron", "aria-hidden": "true"});
    const handle = element("button", {type: "button", class: "lex-collapsible-handle",
      onclick: () => setCollapsed(!root.classList.contains("lex-collapsible-collapsed")),
    }, element("span", {class: "lex-collapsible-grip", "aria-hidden": "true"}),
      chevron,
      element("span", {class: "lex-collapsible-tag", "aria-hidden": "true"}, options.label || ""));
    const setCollapsed = collapsed => {
      root.classList.toggle("lex-collapsible-collapsed", collapsed);
      root.style.width = collapsed ? "" : (options.width || "320px");
      handle.setAttribute("aria-expanded", String(!collapsed));
      const name = options.label || "side panel";
      handle.setAttribute("aria-label", collapsed ? `Expand ${name}` : `Collapse ${name}`);
      handle.title = collapsed ? `Expand ${name}` : `Collapse ${name}`;
      const inward = side === "left" ? "\u2039" : "\u203A";
      const outward = side === "left" ? "\u203A" : "\u2039";
      chevron.textContent = collapsed ? outward : inward;
      remember("collapsed", collapsed ? "1" : "0");
    };
    root.append(body, handle);
    if (strip) show(stored("tab") || options.active);
    setCollapsed(stored("collapsed") !== null ? stored("collapsed") === "1" : !!options.collapsed);
    root.setCollapsed = setCollapsed;
    root.showTab = show;
    return root;
  };

  let infoHelpSequence = 0;
  let activeHelpPopup = null;

  const closeHelpPopup = () => {
    if (!activeHelpPopup) return;
    if (activeHelpPopup.classList.contains("lex-help-editing") && activeHelpPopup.commitEdit) {
      activeHelpPopup.commitEdit();
      return;
    }
    liveHoverPopups.delete(activeHelpPopup.lexHoverEntry);
    activeHelpPopup.cleanup?.();
    activeHelpPopup.remove();
    activeHelpPopup = null;
  };

  // Optional descriptions for callers that need accessible control summaries.
  // These are not installed as hover tooltips.
  const controlHelp = control => {
    if (!(control instanceof Element) || !control.matches("button,input,select,textarea,[role='button'],[role='slider'],[role='separator']")) return "";
    const authored = String(control.getAttribute("aria-description") || "").trim();
    if (authored) return authored;
    const explicit = String(control.getAttribute("aria-label") || "").trim();
    const labelNode = control.labels?.[0] || control.closest?.("label");
    const fieldLabel = control.closest?.(".lex-detail-field")?.querySelector?.(".lex-detail-field-label");
    const visible = control.matches("button,[role='button']") ? String(control.textContent || "").trim() : "";
    const placeholder = String(control.getAttribute("placeholder") || "").trim();
    const name = (explicit || labelNode?.textContent || fieldLabel?.textContent || visible || placeholder)
      ?.replace(/\s+/g, " ").trim();
    if (!name) return "";
    let text;
    const type = String(control.getAttribute("type") || "").toLocaleLowerCase();
    if (control.matches("button,[role='button']")) text = name.endsWith(".") ? name : `${name}.`;
    else if (type === "checkbox" || type === "radio") text = `Enable or disable ${name}.`;
    else if (control.tagName === "SELECT") text = `Choose ${name}.`;
    else if (type === "range" || type === "number" || control.getAttribute("role") === "slider") text = `Set ${name}.`;
    else if (control.getAttribute("role") === "separator") text = `Resize ${name}.`;
    else text = `Edit ${name}.`;
    const facts = [];
    const min = control.getAttribute("min") ?? control.getAttribute("aria-valuemin");
    const max = control.getAttribute("max") ?? control.getAttribute("aria-valuemax");
    const step = control.getAttribute("step");
    if (min !== null && max !== null && min !== "" && max !== "") facts.push(`Range: ${min} to ${max}.`);
    else if (min !== null && min !== "") facts.push(`Minimum: ${min}.`);
    else if (max !== null && max !== "") facts.push(`Maximum: ${max}.`);
    if (step && step !== "any" && !["checkbox","radio"].includes(type)) facts.push(`Step: ${step}.`);
    const unit = control.closest?.(".lex-unit-field")?.querySelector?.(".lex-unit")?.textContent?.trim();
    if (unit) facts.push(`Unit: ${unit}.`);
    const apply = control.dataset?.lexApplyRequirement || control.closest?.("[data-lex-apply-requirement]")?.dataset?.lexApplyRequirement;
    if (apply) facts.push(`Apply: ${String(apply).trim()}`);
    return [text, ...facts].join(" ");
  };

  const installControlHelp = (root = document.body) => {
    // Keep descriptions available to assistive tools, without native hover boxes.
    const strip = node => {
      if (!(node instanceof Element)) return;
      for (const control of [node, ...node.querySelectorAll('[title]')]) {
        const text = control.getAttribute('title');
        if (!text) continue;
        control.dataset.lexTitle = text;
        if (!control.hasAttribute('aria-description')) control.setAttribute('aria-description', text);
        control.removeAttribute('title');
      }
      for (const title of [node, ...node.querySelectorAll('svg title')]) {
        if (!title.matches('svg title')) continue;
        const svg=title.closest('svg');
        if (!svg.hasAttribute('aria-label')) svg.setAttribute('aria-label',title.textContent);
        title.remove();
      }
    };
    strip(root);
    const observer = new MutationObserver(records => records.forEach(record => {
      if (record.type === 'attributes') strip(record.target);
      else record.addedNodes.forEach(strip);
    }));
    observer.observe(root, {childList:true, subtree:true, attributes:true, attributeFilter:['title']});
    // Generic hover text is opt-in. Help bubbles and save previews own their
    // popups independently, so this layer must never obscure them.
    let tip = null, tipTimer = 0, tipOwner = null;
    const hideTip = () => { clearTimeout(tipTimer); tip?.remove(); tip = null; tipOwner = null; };
    const showTip = owner => {
      const text = owner.dataset.lexTitle;
      if (!text || !owner.isConnected || sharedSettingsSnapshot?.showHoverTooltips !== true) return;
      tip = element("div", {class: "lex-hover-tip", role: "tooltip"}, text);
      document.body.append(tip);
      const box = owner.getBoundingClientRect(), size = tip.getBoundingClientRect(), pad = 8;
      const below = box.bottom + 6 + size.height <= window.innerHeight - pad;
      tip.style.left = `${Math.round(Math.max(pad, Math.min(box.left + box.width / 2 - size.width / 2, window.innerWidth - size.width - pad)))}px`;
      tip.style.top = `${Math.round(below ? box.bottom + 6 : Math.max(pad, box.top - 6 - size.height))}px`;
    };
    const over = event => {
      const owner = event.target.closest?.("[data-lex-title]");
      if (owner === tipOwner) return;
      hideTip();
      if (sharedSettingsSnapshot?.showHoverTooltips !== true || !owner ||
          owner.closest(".lex-info-help,.lex-save-icon") || !root.contains(owner)) return;
      tipOwner = owner;
      tipTimer = setTimeout(() => showTip(owner), 450);
    };
    document.addEventListener("pointerover", over, true);
    document.addEventListener("pointerdown", hideTip, true);
    document.addEventListener("keydown", hideTip, true);
    window.addEventListener("scroll", hideTip, true);
    window.addEventListener("lexeditor-settings-changed", hideTip);
    return () => {
      observer.disconnect();
      hideTip();
      document.removeEventListener("pointerover", over, true);
      document.removeEventListener("pointerdown", hideTip, true);
      document.removeEventListener("keydown", hideTip, true);
      window.removeEventListener("scroll", hideTip, true);
      window.removeEventListener("lexeditor-settings-changed", hideTip);
    };
  };

  const infoHelp = (text, attrs = {}) => {
    if (text instanceof Element && text.matches('.lex-info-help') && !Object.keys(attrs).length) return text;
    const shipped = typeof text === "string" ? text : null;
    const shown = () => shipped === null ? text : savedLabel(helpKey(shipped), shipped);
    const isCleared = () => shipped !== null && shown() === "";
    // Cleared help is gone everywhere: clearing means gone. Ctrl+Z brings
    // the text back, and the next mount shows the marker again.
    if (isCleared()) return document.createTextNode("");
    const {
      class: className = "", title = text, "aria-label": ariaLabel = text,
      onclick = null, symbol = "?", ...rest
    } = attrs;
    const interactive = typeof onclick === "function";
    const popupId = `lex-help-${++infoHelpSequence}`;
    const marker = element(interactive ? "button" : "span", {
      ...(interactive ? {type: "button", onclick} : {tabindex: "0"}),
      ...rest,
      class: ["lex-info-help", className].filter(Boolean).join(" "),
      "data-lex-control": "help",
      "aria-label": ariaLabel, "aria-describedby": popupId,
    }, element("span", {"aria-hidden": "true"}, symbol));
    let closeTimer = null;
    const cancelClose = () => { clearTimeout(closeTimer); closeTimer = null; };
    const scheduleClose = () => {
      cancelClose();
      closeTimer = setTimeout(() => {
        if (activeHelpPopup?.id === popupId &&
            !marker.matches(":hover,:focus-within") &&
            !activeHelpPopup.matches(":hover,:focus-within")) closeHelpPopup();
      }, 150);
    };
    const open = () => {
      cancelClose();
      if (activeHelpPopup?.id === popupId) return;
      closeHelpPopup();
      // A developer can reword what the bubble says. The shipped string stays
      // the key, so a bubble reworded here reads the new text on every screen
      // that shows the same explanation.
      const popup = element("div", {
        id: popupId, class: "lex-help-popover", role: "tooltip", tabindex: "0",
      }, text instanceof Node ? text.cloneNode(true)
        : String(shown() ?? title ?? ""));
      document.body.append(popup);
      if (shipped !== null && sharedSettingsSnapshot?.developerMode) {
        // The bubble itself never takes the pointer, so the editor is started
        // from the marker and the popover takes the pointer only while it is
        // being edited.
        popup.startEditing = () => {
          popup.classList.add("lex-help-editing");
          const before = shown();
          const editor = element("textarea", {class: "lex-help-edit", value: shown()});
          popup.replaceChildren(editor);
          editor.focus();
          editor.select();
          let finished = false;
          const finish = async (commit, reopen = true) => {
            if (finished) return;
            finished = true;
            popup.classList.remove("lex-help-editing");
            const typed = editor.value.trim();
            // An empty edit clears the bubble instead of restoring the shipped
            // text, so a developer can delete help that should not be there.
            const next = typed;
            if (!commit) {
              popup.replaceChildren(String(shown()));
              // The editor's own blur schedules the bubble's close; keep the
              // wording on screen while the reader is still looking at it.
              cancelClose();
              popup.focus();
              position();
              return;
            }
            try {
              if (next === shipped) localStorage.removeItem(helpKey(shipped));
              else localStorage.setItem(helpKey(shipped), next);
            } catch (_error) {}
            // The editor took the pointer, and the bubble's close timers key on
            // the pointer being back on the marker, so reopen it to face the
            // reader with the wording that was just saved.
            closeHelpPopup();
            if (next === "") marker.remove();
            else if (reopen) open();
            // A bubble has no lasting node, so undoing a rewording puts the text
            // back for the next time it opens rather than under the pointer.
            pushLabelUndo({key: helpKey(shipped), tabId: activePageTab(), before,
              after: next, shipped, node: null});
            labelRedo.length = 0;
            const saved = await storeLabel(helpKey(shipped), activePageTab(), next, shipped);
            labelHistoryChanged();
            try {
              // "Shipped" only when the shared default kept the text.
              if (saved) {
                showToast(next === shipped ? "The shipped help text is back."
                                           : next === "" ? "The help text is cleared."
                                           : "The new help text is now the shipped one.");
              } else {
                showToast(next === shipped ? "The shipped help text is back on this device."
                                           : next === "" ? "The help text is cleared on this device."
                                           : "The new help text is saved on this device.");
              }
            } catch (_error) {}
          };
          // Enter or clicking away keeps the new wording; Shift+Enter starts a
          // new line; Escape puts the old one back. Clicking away used to throw
          // the edit away and only Ctrl+Enter kept it, so a reworded bubble
          // looked as if it had been ignored.
          editor.addEventListener("keydown", keyEvent => {
            keyEvent.stopPropagation();
            if (keyEvent.key === "Escape") { keyEvent.preventDefault(); finish(false); }
            else if (keyEvent.key === "Enter" && !keyEvent.shiftKey) {
              keyEvent.preventDefault();
              finish(true);
            }
          });
          editor.addEventListener("blur", () => finish(true));
          // A click outside closes the bubble and removes the editor before
          // it can blur; closing it keeps the wording all the same.
          popup.commitEdit = () => finish(true, false);
        };
      }
      const position = () => {
        if (!marker.isConnected || !popup.isConnected) return;
        const anchor = marker.getBoundingClientRect();
        const bounds = popup.getBoundingClientRect();
        const gap = 9;
        const left = Math.max(8, Math.min(anchor.left + anchor.width / 2 - bounds.width / 2,
          window.innerWidth - bounds.width - 8));
        let top = anchor.bottom + gap;
        let side = "below";
        if (top + bounds.height > window.innerHeight - 8) {
          top = Math.max(8, anchor.top - bounds.height - gap);
          side = "above";
        }
        popup.style.left = `${left}px`;
        popup.style.top = `${top}px`;
        popup.dataset.side = side;
        popup.style.setProperty("--lex-help-anchor", `${Math.max(12,
          Math.min(bounds.width - 12, anchor.left + anchor.width / 2 - left))}px`);
      };
      const escape = event => { if (event.key === "Escape") closeHelpPopup(); };
      const close = () => closeHelpPopup();
      const onScroll = event => {
        if (popup.contains(event.target)) return;
        // Keyboard focus can scroll the marker - or the bubble itself, which is
        // focusable so its own text can be read - into view after opening help.
        // A hover can land its own scroll the same way; while the marker is
        // still under the pointer the bubble follows it instead of dying.
        if (marker.matches(":hover") || marker.matches(":focus-within") || popup.matches(":focus-within")) position();
        else close();
      };
      popup.addEventListener("pointerenter", cancelClose);
      popup.addEventListener("pointerleave", scheduleClose);
      popup.addEventListener("focus", cancelClose);
      popup.addEventListener("blur", scheduleClose);
      window.addEventListener("resize", close, {once: true});
      window.addEventListener("scroll", onScroll, {capture: true});
      document.addEventListener("keydown", escape);
      popup.cleanup = () => {
        cancelClose();
        document.removeEventListener("keydown", escape);
        window.removeEventListener("resize", close);
        window.removeEventListener("scroll", onScroll, true);
      };
      activeHelpPopup = popup;
      popup.lexHoverEntry = {anchor: marker, close: closeHelpPopup};
      liveHoverPopups.add(popup.lexHoverEntry);
      position();
    };
    marker.addEventListener("pointerenter", open);
    marker.addEventListener("pointerleave", scheduleClose);
    marker.addEventListener("focus", open);
    // A help marker can sit inside a checkbox label or clickable record.
    // Reading help must not activate the control that contains it.
    marker.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
    });
    marker.addEventListener("dblclick", event => {
      if (!sharedSettingsSnapshot?.developerMode) return;
      event.preventDefault();
      event.stopPropagation();
      open();
      activeHelpPopup?.startEditing?.();
    });
    marker.addEventListener("blur", scheduleClose);
    marker.addEventListener("keydown", event => {
      if (event.key === "ArrowDown" && activeHelpPopup?.id === popupId) {
        event.preventDefault(); activeHelpPopup.focus();
      }
    });
    return marker;
  };

  let modLoadingPromise = null;
  const modLoadingPanel = pluginId => {
    const section = element("section", {class: "lex-plugin-mod-loading", "aria-label": "Mod Loading"},
      element("h2", {}, "Mod Loading"), element("p", {role: "status"}, "Loading mod-loading details…"));
    modLoadingPromise ||= fetch(new URL("mod-loading.json", sharedAssetBase)).then(response => {
      if (!response.ok) throw new Error("The packaged mod-loading file is missing.");
      return response.json();
    }).catch(error => { modLoadingPromise = null; throw error; });
    modLoadingPromise.then(data => {
      const game = data.plugins?.[pluginId];
      if (!game) throw new Error(`Mod Loading details have not been supplied for ${pluginId}.`);
      const list = element("ul", {class: "lex-mod-loading-list"});
      [["Mod Loader", game.loader], ["Mod Structure", game.structure], ["Overriding", game.overriding]].forEach(([label, value]) => {
        list.append(element("li", {}, element("strong", {}, `${label}:`), ` ${value}`));
      });
      section.replaceChildren(element("h2", {}, "Mod Loading"), list);
    }).catch(error => section.replaceChildren(element("h2", {}, "Mod Loading"),
      element("p", {role: "alert"}, error.message)))
      .finally(() => section.closest(".lex-tweaks-paged")?.lexFitPage?.());
    return section;
  };

  let creditsPromise = null;
  const creditsPanel = pluginId => {
    const section = element("section", {class: "lex-plugin-credits", "aria-label": "Credits"},
      element("h2", {}, "Credits"), element("p", {role: "status"}, "Loading local credits…"));
    const link = row => {
      let url;
      try { url = new URL(row.url); } catch (_) { return element("strong", {}, row.name); }
      return url.protocol === "https:" ? element("a", {href: url.href, target: "_blank", rel: "noopener noreferrer"}, row.name)
        : element("strong", {}, row.name);
    };
    creditsPromise ||= fetch(new URL("credits.json", sharedAssetBase)).then(response => {
      if (!response.ok) throw new Error("The packaged credits file is missing.");
      return response.json();
    }).catch(error => { creditsPromise = null; throw error; });
    creditsPromise.then(data => {
      const game = data.plugins[pluginId];
      if (!game) throw new Error(`Credits have not been supplied for ${pluginId}.`);
      section.replaceChildren(element("h2", {}, "Credits"));
      const rows = (title, entries) => {
        if (!entries?.length) return;
        section.append(element("h3", {}, title), ...entries.map(row =>
          element("div", {class: "lex-credit-entry"}, link(row), element("p", {}, row.role))));
      };
      rows("Game integration", game.contributions);
      rows("Special thanks", game.thanks);
      rows("Shared application", data.shared?.contributions);
      const notices = [...(game.licenses || []), ...(data.shared?.licenses || [])];
      section.append(element("h3", {}, "Licenses and notices"), element("p", {},
        "These notices are included locally; opening them does not require an internet connection. Game assets remain the property of their respective owners."));
      if (notices.length) notices.forEach(row => section.append(element("details", {},
        element("summary", {}, row.name), element("pre", {tabindex: 0}, row.text))));
      else section.append(element("p", {}, "No third-party code license is embedded in this plugin’s metadata. Consult the separate helper’s own distribution for its license."));
      // A frozen distribution supplies notices for the exact Python packages it bundles.
      fetch(new URL("distribution-notices.json", sharedAssetBase)).then(response => response.ok ? response.json() : [])
        .then(entries => entries.forEach(row => section.append(element("details", {},
          element("summary", {}, row.name), element("pre", {tabindex: 0}, row.text))))).catch(() => {})
        .finally(() => section.closest(".lex-tweaks-paged")?.lexFitPage?.());
    }).catch(error => section.replaceChildren(element("h2", {}, "Credits"),
      element("p", {role: "alert"}, error.message)))
      .finally(() => section.closest(".lex-tweaks-paged")?.lexFitPage?.());
    section.addEventListener("toggle", () => section.closest(".lex-tweaks-paged")?.lexFitPage?.(), true);
    return section;
  };

  const syncInfoPanels = (pluginId, active) => {
    const main = document.querySelector("#main");
    if (!main) return;
    main.classList.toggle("lex-showing-info", !!active);
    if (!active) return;
    // Existing Info pages vary, but all use the shared shell. Keep credits inside
    // their scrollable detail body when present, and never create a second header.
    const parent = main.querySelector(".lex-information-panel .lex-detail-panel-body") || main;
    const added = [];
    if (!main.querySelector(".lex-plugin-mod-loading")) added.push(modLoadingPanel(pluginId));
    if (!main.querySelector(".lex-plugin-credits")) added.push(creditsPanel(pluginId));
    const paged = parent.closest(".lex-tweaks-paged");
    if (paged?.lexAppendCards) paged.lexAppendCards(...added);
    else parent.append(...added);
  };

  const unitField = (control, unit, attrs = {}) => {
    // Frames are the \u{1D453} symbol everywhere, never the word: one glyph
    // that reads at any panel width, like every other unit.
    if (String(unit || "").toLowerCase() === "frames" || String(unit || "").toLowerCase() === "frame")
      unit = "\u{1D453}";
    const scalar = control instanceof Element
      ? (control.matches("input,select,textarea,output,.lex-readonly-field") ? control
        : control.querySelector("input,select,textarea,output,.lex-readonly-field")) : null;
    const boxed = attrs.boxed ?? !!scalar;
    const prefix = attrs.position === "prefix";
    const reserve = Math.max(1.8, String(unit || "").length * .45 + .9);
    const field = element("span", {
      class: [
        "lex-unit-field",
        boxed ? "lex-unit-field-boxed" : "lex-unit-field-static",
        prefix ? "lex-unit-field-prefix" : "lex-unit-field-suffix",
        attrs.class || "",
      ].filter(Boolean).join(" "),
      title: attrs.title,
      style: boxed ? `--lex-unit-reserve:${reserve}em` : null,
      // A reference beside the value reads its unit from here.
      "data-lex-unit": unit || null, "data-lex-unit-position": unit ? (prefix ? "prefix" : "suffix") : null,
    }, control, unit ? element("span", {
    class: ["lex-unit", unit === "×" ? "lex-unit-multiplier" : "", attrs.unitClass || ""].filter(Boolean).join(" "),
    "aria-hidden": "true",
    }, unit) : null);
    if (boxed && unit && !prefix) followUnit(field, scalar || control);
    return field;
  };

  // The unit belongs to the number, so it travels with it. Pinned to the far
  // edge of the box it marked where the box ended rather than where the value
  // did, and on a wide panel that put a "G" a screen's width away from the
  // price it qualifies. The unit is placed just after the last glyph of the
  // value instead, measured in the box's own font.
  //
  // It stops short of whatever the box has reserved on its right: an internal
  // reference rail keeps its lane, so "50,000 G" and its "V 30,000" never
  // collide however long the number gets. When the value is long enough to
  // reach that lane the unit parks against it, which is the old behaviour and
  // the correct one at that width.
  // A box under this width cannot fit its value, its unit, its vanilla
  // reference and its stepper at a readable size: it compacts instead.
  const COMPACT_BOX_WIDTH = 120;
  const placeCompactBox = (host, box) => {
    if (host && box && box.clientWidth > 0)
      host.classList.toggle("lex-compact-box", box.clientWidth < COMPACT_BOX_WIDTH);
  };
  const followUnit = (field, control) => {
    const unitNode = field.querySelector(":scope > .lex-unit");
    if (!unitNode || !(control instanceof HTMLElement)) return;
    const place = () => {
      if (!field.isConnected) return;
      const text = control.value ?? control.textContent ?? "";
      const style = getComputedStyle(control);
      const measured = textWidth(String(text),
        `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`);
      const start = parseFloat(style.paddingLeft) || 0;
      const border = parseFloat(style.borderLeftWidth) || 0;
      const gap = (parseFloat(style.fontSize) || 12) * .12;
      // The right-hand limit is where the box stops reserving room for
      // whatever else lives in it - a reference, a lock, a stepper.
      // The reserve is in em (it pads the box in CSS); the limit is in px.
      const reserved = (parseFloat(getComputedStyle(field).getPropertyValue("--lex-unit-reserve")) || 0)
        * (parseFloat(style.fontSize) || 16);
      const limit = Math.max(0, field.clientWidth - unitNode.offsetWidth - reserved);
      const left = Math.min(border + start + measured + gap, limit);
      const next = `${Math.round(left)}px`;
      if (unitNode.style.left !== next) unitNode.style.left = next;
      placeCompactBox(field.closest?.(".lex-source-control-internal"), field);
    };
    control.addEventListener("input", place);
    control.addEventListener("change", place);
    if(typeof ResizeObserver!=="undefined"){
      const observer=new ResizeObserver(place);observer.observe(control);observer.observe(unitNode);
    }
    new MutationObserver(place).observe(control,{attributes:true,attributeFilter:['style','class']});
    field.lexPlaceUnit = place;
    requestAnimationFrame(place);
    document.fonts?.ready?.then(place);
  };

  // Measuring text without laying it out, so a unit can be placed against a
  // value the box has not been asked to re-render.
  let measuringContext = null;
  const textWidth = (text, font) => {
    if (!text) return 0;
    measuringContext = measuringContext || document.createElement("canvas").getContext("2d");
    if (!measuringContext) return String(text).length * 7;
    if (font) measuringContext.font = font;
    return measuringContext.measureText(String(text)).width;
  };

  const formatNumber = (value, options = {}) => {
    if (value === null || value === undefined || value === "") return String(value ?? "");
    const numeric = typeof value === "bigint" ? value
      : typeof value === "string" && /^[+-]?\d{16,}$/.test(value.trim()) ? BigInt(value.trim())
      : typeof value === "number" ? value : Number(value);
    if (typeof numeric !== "bigint" && !Number.isFinite(numeric)) return String(value);
    return new Intl.NumberFormat("en-US", {
      useGrouping: true,
      maximumFractionDigits: 20,
      ...options,
    }).format(numeric);
  };

  // Exact wide integers keep the browser's bounded numeric control, while
  // validation and stepping use decimal strings and BigInt rather than double.
  const exactIntegerInput = (options = {}) => {
    const low = BigInt(options.min), high = BigInt(options.max);
    if (low > high) throw new RangeError("Invalid integer bounds");
    const input = element("input", {type:"number", min:String(low), max:String(high), step:1,
      value:String(options.value), "aria-label":options.label,
      "data-lex-exact-integer":"true", "data-lex-value-type":"INT"});
    const validate = () => {
      input.setCustomValidity("");
      const text = input.value;
      if (!/^[+-]?\d+$/.test(text)) {
        input.setCustomValidity("Enter a whole number.");
        return null;
      }
      const value = BigInt(text);
      if (value < low || value > high) {
        input.setCustomValidity(`Enter a number from ${low} through ${high}.`);
        return null;
      }
      const issue = options.validate?.(value, text);
      if (issue) { input.setCustomValidity(issue); return null; }
      return value;
    };
    const commit = () => {
      if (input.disabled || input.readOnly || refusesEdit(input)) return false;
      const value = validate();
      if (value === null) { input.reportValidity(); return false; }
      input.value = String(value);
      options.change?.(input.value);
      return true;
    };
    input.addEventListener("change", commit);
    const step = direction => {
      if (input.disabled || input.readOnly || refusesEdit(input)) return;
      const value = validate();
      if (value === null) { input.reportValidity(); return; }
      const next = value + BigInt(direction);
      if (next < low || next > high) return;
      input.value = String(next);
      input.dispatchEvent(new Event("input", {bubbles:true}));
      input.dispatchEvent(new Event("change", {bubbles:true}));
    };
    input.addEventListener("keydown", event => {
      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        event.preventDefault(); step(event.key === "ArrowUp" ? 1 : -1);
      }
    });
    const arrow = (direction, label) => element("button", {type:"button", tabindex:"-1",
      class:direction > 0 ? "lex-stepper-up" : "lex-stepper-down", "aria-label":label,
      onpointerdown:event=>event.preventDefault(), onclick:()=>step(direction)});
    const root = element("div", {class:"lex-source-control lex-has-stepper lex-exact-integer"}, input,
      element("span", {class:"lex-stepper"}, arrow(1, "Increase"), arrow(-1, "Decrease")));
    root.focus = () => input.focus();
    root.select = () => input.select();
    root.lexCommitInteger = commit;
    root.lexValidateInteger = () => validate() !== null;
    input.lexValidateInteger = root.lexValidateInteger;
    validate();
    return root;
  };

  // What a value box holds, as a number. A plugin is free to paint its number
  // the way a player reads it - "50,000" rather than 50000 - so reading the box
  // with a bare Number() returns NaN for every grouped value. That is what put
  // the fill and the handle of a fifty-thousand gil price hard against the left
  // edge of its own slider, and what made committing such a field look out of
  // range and flash rejected.
  const readNumeric = node => {
    const text = String(node?.value ?? "").trim();
    if (!text) return NaN;
    return Number(text.replace(/,/g, "").replace(/\s/g, ""));
  };
  // Writing one back in the shape the box was already using, so a drag does not
  // strip the separators out from under the reader mid-gesture.
  const writeNumeric = (node, value) => {
    const grouped = /\d,\d/.test(String(node.value ?? ""));
    node.value = grouped ? formatNumber(value) : String(value);
  };

  const numberValue = (value, attrs = {}) => {
    const {class: className = "", format = {}, ...rest} = attrs;
    return element("span", {
      ...rest,
      class: ["lex-number", className].filter(Boolean).join(" "),
    }, formatNumber(value, format));
  };

  // Align numbers on their decimal boundary. Integer magnitude grows to the
  // left; fractional precision grows to the right.
  const magnitudeValue = (value, attrs = {}) => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return numberValue(value, attrs);
    const formatted = formatNumber(numeric, attrs.format || {});
    const [integer, fraction = ""] = formatted.split(".");
    return element("span", {
      class: ["lex-number lex-magnitude", attrs.class || ""].filter(Boolean).join(" "),
      style: `--lex-magnitude-integers:${Math.max(1, Number(attrs.integerDigits) || integer.length)}ch;--lex-magnitude-fractions:${Math.max(0, Number(attrs.fractionDigits) || fraction.length)}ch`,
    }, element("span", {class: "lex-magnitude-integer"}, integer),
    fraction ? element("span", {class: "lex-magnitude-decimal", "aria-hidden": "true"}, ".") : null,
    element("span", {class: "lex-magnitude-fraction"}, fraction));
  };

  const readonlyField = (value, attrs = {}) => {
    const {class: className = "", format = true, ...rest} = attrs;
    const display = typeof format === "function"
      ? format(value)
      : (format ? formatNumber(value) : String(value ?? ""));
    return element("input", {
      type: "text", value: display, disabled: true, readonly: true,
      "data-lex-value-type": typeof value === "number" && Number.isFinite(value) ? (Number.isInteger(value) ? "INT" : "FLOAT") : "STRING",
      tabindex: "-1", "aria-readonly": "true", ...rest,
      class: ["lex-readonly-field", className].filter(Boolean).join(" "),
    });
  };

  // One sound's preview, the SFX layout every game shares: a playable
  // sound renders an audio element the detail panel adopts into its
  // heading player with a scrubber, and a sound with no playable file
  // says so in its preview row instead.
  const soundPreview = (options = {}) => detailField({
    label: "",
    control: options.src
      ? element("audio", {src: options.src, controls: true, "aria-label": options.label || "Play sound"})
      : readonlyField(options.note || "No preview"),
    help: options.help || null,
  });

  // Numbered record identity is a prefix unit. The shared helper owns the
  // hash, spacing, and muted tone in lists and detail headings.
  // Record ids are padded to the widest id in the active record set, so a
  // column of them lines up and a detail heading matches its table.
  let recordIdWidth = 1;
  // The width of the WHOLE record set, not of whatever page is on screen.
  // A table paged to ids 960-999 measured three digits and printed #999, while
  // the same table's #1023 elsewhere printed four - the padding changed as the
  // reader turned the page. The paged preset measures every record and sets
  // this floor; a bare table can only widen it, never narrow it.
  let recordIdFloor = 1;
  const setRecordIdWidth = (rows, options = {}) => {
    const widths = (rows || [])
      .map(row => row?.id)
      .filter(value => value !== null && value !== undefined && /^#?\d+$/.test(String(value).trim()))
      .map(value => String(value).trim().replace(/^#/, "").length);
    const measured = widths.length ? Math.max(...widths) : 1;
    if (options.wholeSet) recordIdFloor = measured;
    if (options.floor) recordIdFloor = Math.max(1, Number(options.floor) || 1);
    recordIdWidth = Math.max(measured, recordIdFloor);
  };
  const recordId = (value, attrs = {}) => {
    const {class: className = "", ...rest} = attrs;
    // An identity that is already drawn is already done. A table column that
    // renders U.recordId itself is numbered by the grid as well, so wrapping it
    // again printed "##0": one prefix from the cell, one from the id.
    if (!className && !Object.keys(rest).length && value instanceof Element
        && value.classList.contains("lex-record-id")) return value;
    let content = value instanceof Node ? value : String(value ?? "").replace(/^#/, "");
    if (!(value instanceof Node) && /^\d+$/.test(content)) content = content.padStart(recordIdWidth, "0");
    return element("span", {
      ...rest,
      class: ["lex-record-id", className].filter(Boolean).join(" "),
    }, element("span", {class: "lex-record-id-prefix", "aria-hidden": "true"}, "#"), content);
  };

  // One shared Detail heading owns the optional icon or live-preview slot,
  // record identity, metadata, and actions. Games supply themed content.
  // Where a panel's body arranges its sections: stacked by default, or the
  // first section beside the others, for a record with a picture.
  const DETAIL_BODY_LAYOUTS = {stacked: "", beside: "lex-detail-panel-beside", row: "lex-detail-panel-row"};

  // A NAME property whose value is the heading's text is the heading. Lexer:
  // "names should not be shown in the details panel as a property if the
  // header shows the name. instead, i should just be able to edit the name
  // from there." Its own input moves into the heading, handlers and all, so
  // it edits exactly what it edited before; a read-only one stays read-only.
  const headingNameField = options => {
    if (options.titleControl || typeof options.renameRecord === "function") return null;
    if (typeof options.title !== "string" && typeof options.title !== "number") return null;
    const title = String(options.title).trim();
    if (!title) return null;
    for (const node of [options.body].flat()) {
      if (!(node instanceof Element)) continue;
      for (const field of [node, ...node.querySelectorAll(".lex-detail-field")]) {
        if (!field.matches(".lex-detail-field")) continue;
        const label = field.querySelector(":scope > .lex-detail-field-label > .lex-detail-field-label-text");
        if (label?.textContent.trim().toLowerCase() !== "name") continue;
        const input = field.querySelector(':scope > .lex-detail-field-control > input:is([type="text"],:not([type]))');
        if (input && input.value.trim() === title) return {field, input};
      }
    }
    return null;
  };

  // A record that is a sound plays from its own heading: the thumbnail slot is
  // a play/pause button and the line under the heading is the sound's
  // progress, which can be dragged to scrub. Lexer asked for this on FF8's SFX
  // and Warband's Sounds. One sound plays at a time across the page.
  let playingRecordAudio = null;
  const formatClock = seconds => {
    const whole = Math.max(0, Math.floor(Number(seconds) || 0));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  };
  const claimRecordAudio = audio => {
    if (playingRecordAudio && playingRecordAudio !== audio) playingRecordAudio.pause();
    playingRecordAudio = audio;
  };
  const audioPlayButton = ({src, label} = {}) => {
    const audio = new Audio();
    audio.preload = "metadata";
    audio.src = src;
    const name = label || "sound";
    const glyph = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    glyph.setAttribute("viewBox", "0 0 24 24");
    glyph.setAttribute("aria-hidden", "true");
    const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
    glyph.append(shape);
    const button = element("button", {type: "button", class: "lex-audio-play"}, glyph);
    const paint = () => {
      const playing = !audio.paused && !audio.ended;
      shape.setAttribute("d", playing ? "M7 5h4v14H7zM13 5h4v14h-4z" : "M8 5v14l11-7z");
      button.title = `${playing ? "Pause" : "Play"} ${name}`;
      button.setAttribute("aria-label", button.title);
    };
    button.addEventListener("click", event => {
      event.stopPropagation();
      if (audio.paused || audio.ended) {
        claimRecordAudio(audio);
        audio.play().catch(() => showToast(`Could not play ${name}.`, true));
      } else audio.pause();
    });
    // A cell that re-renders mid-play orphans its button; the orphan stops
    // instead of playing on where no pause button can reach it.
    audio.addEventListener("timeupdate", () => { if (!button.isConnected) audio.pause(); });
    for (const type of ["play", "pause", "ended"])
      audio.addEventListener(type, paint);
    paint();
    return {button, audio};
  };
  const recordAudio = options => {
    const {button, audio} = audioPlayButton(options);
    const label = options.label || "sound";
    const scrub = element("input", {type: "range", class: "lex-audio-scrub", min: "0", max: "0", step: "0.01",
      value: "0", "aria-label": `Position in ${label}`, "data-lex-autofit": "false"});
    const paint = () => {
      const length = Number.isFinite(audio.duration) ? audio.duration : 0;
      scrub.max = String(length);
      if (!scrub.matches(":active")) scrub.value = String(audio.currentTime || 0);
      scrub.style.setProperty("--lex-audio-progress", `${length ? (audio.currentTime / length) * 100 : 0}%`);
      scrub.setAttribute("aria-valuetext", `${formatClock(audio.currentTime)} of ${formatClock(length)}`);
      scrub.title = scrub.getAttribute("aria-valuetext");
    };
    const stopIfGone = () => { if (!button.isConnected) audio.pause(); };
    scrub.addEventListener("input", () => {
      audio.currentTime = Number(scrub.value) || 0;
      paint();
    });
    for (const type of ["play", "pause", "ended", "timeupdate", "loadedmetadata", "durationchange"])
      audio.addEventListener(type, () => { stopIfGone(); paint(); });
    paint();
    return {button, scrub, audio};
  };
  // A table column of per-row play buttons: every sound row plays from the
  // table, under the same one-sound-at-a-time policy as the detail header.
  const audioColumn = ({key = "play", label = "", width = "44px", src, name} = {}) => ({key, label, width,
    sortable: false,
    render: row => {
      const url = typeof src === "function" ? src(row) : src;
      if (!url) return "\u2014";
      const title = typeof name === "function" ? name(row) : (row?.name ?? label);
      return audioPlayButton({src: url, label: title}).button;
    }});

  // A panel whose body carries a sound player (FF8's SFX preview row) plays
  // from its heading instead: the player's source moves up, and the row that
  // held it goes, with its section when that was all the section held.
  const adoptBodyAudio = options => {
    if (options.audio || options.icon) return options;
    const body = [options.body].flat();
    for (const node of body) {
      if (!(node instanceof Element)) continue;
      const player = node.matches("audio[src]") ? node : node.querySelector("audio[src]");
      if (!player) continue;
      const row = player.closest(".lex-detail-field") || player;
      const section = row.closest(".lex-detail-section");
      row.remove();
      const emptied = section && !section.querySelector(":scope > .lex-detail-section-content > *") ? section : null;
      emptied?.remove();
      const label = (player.getAttribute("aria-label") || "").replace(/^Play\s+/i, "") || undefined;
      return {...options, audio: {src: player.getAttribute("src"), label},
        body: body.filter(item => item !== row && item !== emptied)};
    }
    return options;
  };

  // An identifier such as ADVERT_WHR_QUARTER_SHOES has no space to wrap at,
  // so a narrow heading clipped it. It may break after its own separators
  // instead, never inside a word; <wbr> adds no text, so copying the name and
  // a game's bitmap redraw read exactly what they did before.
  const breakableName = value => typeof value !== "string" ? [value]
    : value.split(/(?<=[_./\\])(?=.)/).flatMap((part, index) => index ? [element("wbr"), part] : [part]);

  // Detail tabs a developer arranges: right-click a panel heading to add a
  // tab, drag properties or whole sections onto tabs. Layouts live under one
  // localStorage key per page, so the shipped-default flow carries them for
  // everyone; shapes are hashed, so each distinct panel shape keeps its own.
  // Panels render one column; nothing paginates anymore.
  const detailTabsKey = () => `${shellPluginId()}-${activePageTab()}.detailtabs`;
  const detailNodeKey = (node, seen) => {
    const base = node.classList.contains("lex-detail-section")
      ? `s:${node.dataset.lexLayoutSection ?? node.getAttribute("aria-label") ?? node.tagName}`
      : node.classList.contains("lex-detail-field")
        ? `f:${node.dataset.lexLayoutField ?? node.tagName}`
        : `n:${node.tagName}`;
    const count = (seen.get(base) || 0) + 1;
    seen.set(base, count);
    return count > 1 ? `${base}#${count}` : base;
  };
  // One record shape's detail tabs, shipped like any other view default.
  // The key carries the page token the host requires; the local cache keeps
  // every shape together for fast reads.
  const detailShapeKey = shape => `${shellPluginId()}-${activePageTab()}.detailtabs.${shape}`;
  const shipDetailLayout = (shape, layout) => {
    const key = detailShapeKey(shape);
    callWindow("save_default_view", shellPluginId(), activePageTab(),
      {[key]: JSON.stringify({...layout, updatedAt: Date.now()})}).catch(() => {});
  };
  const loadDetailLayouts = () => {
    let cached = null;
    try {
      const parsed = JSON.parse(localStorage.getItem(detailTabsKey()) || "");
      if (parsed && typeof parsed === "object" && parsed.shapes) cached = parsed;
    } catch (_error) {}
    const shapes = {...(cached?.shapes || {})};
    // Shipped layouts arrive as one key per shape (the host seeds them into
    // storage at startup); the newer copy of each shape wins.
    try {
      const prefix = `${shellPluginId()}-${activePageTab()}.detailtabs.`;
      for (let index = 0; index < localStorage.length; index++) {
        const name = localStorage.key(index);
        if (!name?.startsWith(prefix)) continue;
        const entry = JSON.parse(localStorage.getItem(name) || "null");
        if (!entry || !Array.isArray(entry.tabs)) continue;
        const shape = name.slice(prefix.length);
        if ((entry.updatedAt || 0) >= ((shapes[shape] || {}).updatedAt || 0)) shapes[shape] = entry;
      }
    } catch (_error) {}
    return {shapes};
  };
  const saveDetailLayouts = (shape, layout) => {
    const all = loadDetailLayouts();
    all.shapes[shape] = {...layout, updatedAt: Date.now()};
    const entries = Object.entries(all.shapes).sort((a, b) => (b[1].updatedAt || 0) - (a[1].updatedAt || 0));
    all.shapes = Object.fromEntries(entries.slice(0, 12));
    try { localStorage.setItem(detailTabsKey(), JSON.stringify(all)); } catch (_error) {}
  };
  const detailBody = (bodyClass, body, paginate) => {
    const nodes = [body || []].flat(Infinity).filter(node => node !== null && node !== undefined && node !== false);
    const box = element("div", {class: bodyClass}, nodes);
    const ctx = detailTabsContext(box);
    box._detailTabs = ctx;
    ctx.render();
    // A shape the developer gave its own tabs keeps those panes; every other
    // body made only of sections flows into columns, `paginate: false`
    // keeping one column and an object passing options through.
    if (ctx.hasTabs()) return box;
    const sections = nodes.length > 0 && nodes.every(node =>
      node instanceof Element && node.classList.contains("lex-detail-section"));
    const flow = paginate === false ? null
      : paginate ? (typeof paginate === "object" ? paginate : {})
      : sections ? {inline: true} : null;
    if (!flow) return box;
    const paged = paginateSettings(box, flow);
    paged._detailTabs = ctx;
    return paged;
  };
  const detailTabsContext = box => {
    const dev = () => !!sharedSettingsSnapshot?.developerMode;
    const seen = new Map();
    // Custom sections the developer added live in the property layout,
    // so rebuild them before keying: then they deal into their recorded
    // tab like shipped sections. Customs only, never a full restore:
    // moving fields now would key later builds on a moved schema and
    // orphan the stored layout. The later full restore adopts these.
    const probe = buildPropertyState(box, layoutFields(box));
    let customSpecs = null;
    try { customSpecs = JSON.parse(localStorage.getItem(probe.key) || "null")?.sections; } catch (_error) {}
    placeCustomSections(probe, customSpecs);
    const home = [...box.childNodes];
    const nodeByKey = new Map();
    const shells = new Map();
    const fields = new Map();
    const order = [];
    const keyNodes = node => {
      const key = detailNodeKey(node, seen);
      nodeByKey.set(key, node);
      return key;
    };
    for (const node of home) {
      if (!(node instanceof Element)) continue;
      const key = keyNodes(node);
      order.push(key);
      if (node.classList.contains("lex-detail-section")) {
        const content = node.querySelector(":scope > .lex-detail-section-content") || node;
        const kids = [...content.childNodes];
        const keys = [];
        for (const field of content.querySelectorAll(":scope > .lex-detail-field")) {
          const fkey = keyNodes(field);
          fields.set(fkey, field);
          keys.push(fkey);
        }
        shells.set(key, {node, content, kids, fields: keys});
      } else if (node.classList.contains("lex-detail-field")) {
        fields.set(key, node);
      }
    }
    // The shape is the shipped nodes only: customs join the keys so they
    // deal, but counting them would orphan every saved tab set.
    const shape = textDigest([...nodeByKey].filter(([, node]) =>
      node.dataset?.lexCustomSection !== "true").map(([key]) => key).sort().join("\n"));
    const stored = loadDetailLayouts().shapes[shape];
    const layout = stored && Array.isArray(stored.tabs) ? {
      tabs: stored.tabs.filter(tab => tab && tab.id).map(tab => ({id: String(tab.id), label: tab.label ?? String(tab.id)})),
      shells: stored.shells || {},
      fields: stored.fields || {},
      active: stored.active ?? null,
    } : {tabs: [], shells: {}, fields: {}, active: null};
    const persist = () => saveDetailLayouts(shape, layout);
    // Structural changes ship; switching the active tab stays local.
    const persistShared = () => {
      persist();
      shipDetailLayout(shape, layout);
    };
    const tabIds = () => layout.tabs.map(tab => tab.id);
    const firstTab = () => layout.tabs[0]?.id;
    const validTab = id => tabIds().includes(id) ? id : firstTab();
    const shellTab = key => validTab(layout.shells[key]);
    const fieldTab = key => {
      if (layout.fields[key] !== undefined) return validTab(layout.fields[key]);
      for (const [skey, shell] of shells) if (shell.fields.includes(key)) return shellTab(skey);
      return firstTab();
    };
    let strip = null;
    const panes = new Map();
    const show = id => {
      const next = validTab(id);
      layout.active = next;
      persist();
      strip?.setActive(next);
      for (const [key, pane] of panes) pane.hidden = key !== next;
    };
    const enableDrag = () => {
      for (const [key, field] of fields) {
        field.draggable = true;
        if (field._detailDragKey) continue;
        field._detailDragKey = key;
        field.addEventListener("dragstart", event => {
          if (!dev()) { event.preventDefault(); return; }
          event.dataTransfer.setData("text/lex-detail-node", JSON.stringify({key: field._detailDragKey, shell: false}));
          event.dataTransfer.effectAllowed = "move";
          field.classList.add("lex-dragging");
        });
        field.addEventListener("dragend", () => field.classList.remove("lex-dragging"));
      }
      for (const [key, shell] of shells) {
        const title = shell.node.querySelector(":scope > .lex-detail-section-title");
        if (!title || title._detailDragKey) continue;
        title.draggable = true;
        title._detailDragKey = key;
        title.addEventListener("dragstart", event => {
          if (!dev()) { event.preventDefault(); return; }
          event.dataTransfer.setData("text/lex-detail-node", JSON.stringify({key: title._detailDragKey, shell: true}));
          event.dataTransfer.effectAllowed = "move";
          shell.node.classList.add("lex-dragging");
        });
        title.addEventListener("dragend", () => shell.node.classList.remove("lex-dragging"));
      }
    };
    const render = () => {
      box.querySelector(":scope > .lex-detail-tabstrip-wrap")?.remove();
      for (const pane of panes.values()) {
        while (pane.firstChild) box.append(pane.firstChild);
        pane.remove();
      }
      panes.clear();
      for (const shell of shells.values()) for (const kid of shell.kids) shell.content.append(kid);
      for (const node of home) box.append(node);
      if (!layout.tabs.length) return;
      const wrap = element("div", {class: "lex-detail-tabstrip-wrap"});
      strip = tabStrip({tabs: layout.tabs, active: validTab(layout.active), label: "Detail views",
        className: "lex-detail-tabs", change: show,
        onRename: async id => {
          const tab = layout.tabs.find(entry => entry.id === id);
          const label = await promptText({title: "Rename detail tab", label: "Tab name",
            value: tab?.label || "", confirmLabel: "Rename"});
          if (!label) return;
          tab.label = label;
          persistShared();
          strip.setLabel(id, label);
        }});
      // Hold-right fills a tab with a new section, or removes it when it
      // holds nothing (bindTabHold below). Saving the view stays on page
      // and subtab bars, so this strip keeps no holdToSave.
      for (const button of strip.querySelectorAll(".lex-tabstrip-button")) {
        bindTabHold(button);
        button.addEventListener("dragover", event => {
          if (!dev() || ![...event.dataTransfer.types].includes("text/lex-detail-node")) return;
          event.preventDefault();
          button.classList.add("lex-drop-target");
        });
        button.addEventListener("dragleave", () => button.classList.remove("lex-drop-target"));
        button.addEventListener("drop", event => {
          button.classList.remove("lex-drop-target");
          if (!dev()) return;
          event.preventDefault();
          let dropped = null;
          try { dropped = JSON.parse(event.dataTransfer.getData("text/lex-detail-node")); } catch (_error) {}
          if (!dropped || !tabIds().includes(button.dataset.tabstripId)) return;
          if (dropped.shell && shells.has(dropped.key)) {
            layout.shells[dropped.key] = button.dataset.tabstripId;
            for (const fkey of shells.get(dropped.key).fields) delete layout.fields[fkey];
          } else if (fields.has(dropped.key)) {
            layout.fields[dropped.key] = button.dataset.tabstripId;
          } else {
            return;
          }
          persistShared();
          render();
        });
      }
      wrap.append(strip);
      box.prepend(wrap);
      for (const tab of layout.tabs) {
        const pane = element("div", {class: "lex-detail-tabpane", role: "tabpanel",
          "data-tabstrip-pane": tab.id, hidden: tab.id !== validTab(layout.active)});
        panes.set(tab.id, pane);
        box.append(pane);
      }
      const dealt = [];
      for (const key of order) {
        const node = nodeByKey.get(key);
        if (!node) continue;
        if (shells.has(key)) {
          const here = shellTab(key);
          const stays = shells.get(key).fields.filter(fkey => fieldTab(fkey) === here);
          if (!stays.length && shells.get(key).fields.length) continue;
          panes.get(here)?.append(node);
          for (const fkey of shells.get(key).fields) {
            if (fieldTab(fkey) !== here && fields.get(fkey)) dealt.push([fieldTab(fkey), fields.get(fkey)]);
          }
        } else {
          panes.get(fields.has(key) ? fieldTab(key) : firstTab())?.append(node);
        }
      }
      for (const [tab, field] of dealt) panes.get(tab)?.append(field);
      // Tabs take over from column pages: the pager dealt these sections
      // into columns, so its empty columns, off-page hold and page footer
      // go, and its resize refits stop (they would deal the panes apart).
      box.querySelectorAll(":scope > .lex-tweak-column, :scope > .lex-tweak-off-page")
        .forEach(node => node.remove());
      const paged = box.closest(".lex-tweaks-paged");
      paged?.lexPageObserver?.disconnect();
      paged?.querySelector(":scope > .lex-tweaks-pages")?.remove();
      const scroller = box.closest(".lex-tweaks-scroll");
      if (scroller) scroller.style.overflowY = "auto";
    };
    const addTab = async () => {
      const label = await promptText({title: "New detail tab", label: "Tab name", confirmLabel: "Create"});
      if (!label) return;
      let id = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "tab";
      if (tabIds().includes(id)) {
        let serial = 2;
        while (tabIds().includes(`${id}-${serial}`)) serial++;
        id = `${id}-${serial}`;
      }
      layout.tabs.push({id, label});
      layout.active = id;
      persistShared();
      render();
    };
    // An empty tab goes the way of an empty section: hold-right removes
    // it, and only it - assignments clean up so no later render can deal
    // a detached node back. Like adding a tab, this ships without undo:
    // nothing is lost but the tab itself.
    const removeTab = id => {
      layout.tabs = layout.tabs.filter(tab => tab.id !== id);
      for (const map of [layout.shells, layout.fields])
        for (const key of Object.keys(map)) if (map[key] === id) delete map[key];
      if (!tabIds().includes(layout.active)) layout.active = firstTab() ?? null;
      persistShared();
      render();
      enableDrag();
    };
    // Hold-right on a tab fills it with a new section; on a tab holding
    // nothing, it removes the tab instead. A tab whose sections drifted
    // elsewhere keeps its assignments, so the hold says where to drag
    // them instead of orphaning them onto the first tab.
    const fillOrRemoveTab = (id, button) => {
      const pane = [...box.children].find(node => node.dataset?.tabstripPane === id);
      const label = button.querySelector(".lex-tabstrip-label")?.textContent?.trim() || "This tab";
      if (pane && pane.childElementCount > 0) {
        const panel = box.closest(".lex-detail-panel") || box;
        const fieldInside = panel.querySelector(".lex-detail-field[data-lex-layout-field]");
        const state = preparePropertyLayout(fieldInside ? propertyRoot(fieldInside) : panel);
        const before = capturePropertyLayout(state);
        const taken = new Set((state.custom || []).map(spec => spec.id));
        let sectionId = `custom-${Date.now().toString(36)}`;
        if (taken.has(sectionId)) {
          let serial = 2;
          while (taken.has(`${sectionId}-${serial}`)) serial++;
          sectionId = `${sectionId}-${serial}`;
        }
        placeCustomSections(state, [...(state.custom || []), {id: sectionId, title: "New section", after: ""}]);
        const node = panel.querySelector(`[data-lex-layout-section="${sectionId}"]`);
        if (node) adoptShell(registerShell(node), id);
        const after = capturePropertyLayout(state);
        const apply = layout => { storePropertyLayout(state, layout); reapplyStoredLayout(state); };
        pushLabelUndo({before, after, apply}); labelRedo.length = 0; labelHistoryChanged();
        void apply(after);
        showToast(`Added a section to ${label}. Double-click its heading to name it, and drag properties into it. `
          + "To remove this tab, drag its sections onto other tabs, then hold right on it.");
        return;
      }
      const assigned = [...Object.values(layout.shells), ...Object.values(layout.fields)].includes(id);
      if (assigned) {
        showToast("That tab still holds sections whose properties moved elsewhere. "
          + "Drag its sections onto another tab, then hold right again.");
        return;
      }
      removeTab(id);
      showToast("Removed the empty tab.");
    };
    const bindTabHold = button => {
      button.addEventListener("pointerdown", event => {
        if (event.button !== 2 || !dev()) return;
        clearTimeout(hideTimer);
        hideHeld = false;
        button.classList.add("lex-property-holding");
        hideTimer = setTimeout(() => {
          button.classList.remove("lex-property-holding");
          hideHeld = true;
          fillOrRemoveTab(button.dataset.tabstripId, button);
        }, 700);
      });
      button.addEventListener("contextmenu", event => event.preventDefault());
    };
    const activeTab = () => validTab(layout.active);
    // A section created after the first render joins the keys under the
    // same rules, so it keeps this key on every rebuild and deals into
    // its recorded tab. Registering twice answers the first key: the
    // counter behind keyNodes must not advance for a known node.
    const registerShell = (node, afterNode = null) => {
      for (const [key, entry] of nodeByKey) if (entry === node) return key;
      const key = keyNodes(node);
      nodeByKey.set(key, node);
      const afterKey = afterNode ? [...nodeByKey].find(([, entry]) => entry === afterNode)?.[0] : null;
      const at = afterKey ? order.indexOf(afterKey) : -1;
      if (at >= 0) order.splice(at + 1, 0, key);
      else order.push(key);
      const content = node.querySelector(":scope > .lex-detail-section-content") || node;
      shells.set(key, {node, content, kids: [...content.childNodes], fields: []});
      return key;
    };
    const adoptShell = (key, tab) => {
      if (!shells.has(key)) return;
      layout.shells[key] = validTab(tab);
      persistShared();
      render();
      enableDrag();
    };
    // A removed custom leaves the keys as well as the store, so a later
    // render cannot deal its detached node back onto the page.
    const forgetShell = node => {
      for (const [key, entry] of [...nodeByKey]) {
        if (entry !== node) continue;
        nodeByKey.delete(key);
        shells.delete(key);
        delete layout.shells[key];
        const at = order.indexOf(key);
        if (at >= 0) order.splice(at, 1);
      }
      persistShared();
    };
    enableDrag();
    return {render, addTab, activeTab, registerShell, adoptShell, forgetShell,
      hasTabs: () => layout.tabs.length > 0};
  };

  // A custom section joins its panel active tab: placed at the body end
  // by the property layout, it would otherwise sit outside the panes,
  // visible on every tab. Panels without tabs keep it where it landed.
  const adoptCustomIntoActivePane = (panel, specId, afterNode = null) => {
    const ctx = panel._DetailTabs;
    if (!ctx?.hasTabs?.()) return;
    const node = panel.querySelector(`[data-lex-layout-section="${specId}"]`);
    if (!node) return;
    ctx.adoptShell(ctx.registerShell(node, afterNode), ctx.activeTab());
  };
  // The header button adds a section at the end of the active tab (or
  // the panel, without tabs): double-click names it, drags fill it,
  // exactly like the hold-right gesture it mirrors. One store serves
  // both: the property layout owns the section, the detail tabs only
  // record which tab shows it.
  const addDetailHeader = panel => {
    const fieldInside = panel.querySelector(".lex-detail-field[data-lex-layout-field]");
    const state = preparePropertyLayout(fieldInside ? propertyRoot(fieldInside) : panel);
    const before = capturePropertyLayout(state);
    const taken = new Set((state.custom || []).map(spec => spec.id));
    let id = `custom-${Date.now().toString(36)}`;
    if (taken.has(id)) {
      let serial = 2;
      while (taken.has(`${id}-${serial}`)) serial++;
      id = `${id}-${serial}`;
    }
    const spec = {id, title: "New section", after: ""};
    placeCustomSections(state, [...(state.custom || []), spec]);
    adoptCustomIntoActivePane(panel, spec.id);
    const after = capturePropertyLayout(state);
    const apply = layout => { storePropertyLayout(state, layout); reapplyStoredLayout(state); };
    pushLabelUndo({before, after, apply}); labelRedo.length = 0; labelHistoryChanged();
    void apply(after);
    showToast("Added a section. Double-click its heading to name it, and drag properties into it. "
      + "To remove a section, drag its properties out, then hold right on its heading.");
  };
  const detailPanel = (options = {}) => {
    options = adoptBodyAudio(options);
    const sound = options.audio?.src ? recordAudio(options.audio) : null;
    if (sound) options = {...options, icon: sound.button};
    const bodyClass = ["lex-detail-panel-body", DETAIL_BODY_LAYOUTS[options.bodyLayout] || ""].filter(Boolean).join(" ");
    const nameField = headingNameField(options);
    if (nameField) {
      const pin = nameField.field.querySelector('.lex-column-pin');
      const section = nameField.field.closest(".lex-detail-section");
      nameField.field.remove();
      const emptied = section && !section.querySelector(":scope > .lex-detail-section-content > *") ? section : null;
      emptied?.remove();
      options = {...options, titleControl: nameField.input,
        actions: pin ? [pin, ...[options.actions || []].flat()] : options.actions,
        body: [options.body].flat().filter(node => node !== nameField.field && node !== emptied)};
    }
    // A record's name is the heading, so the heading is where it is edited. It
    // was an ordinary property row lower down the panel instead, which meant
    // the name appeared twice and the copy at the top - the one being read -
    // was the copy that could not be changed. A panel that hands over
    // `renameRecord` gets a heading that can be typed into in place.
    const title = options.titleControl
        ? element("h2", {class:"lex-detail-panel-title lex-detail-panel-rename"}, options.titleControl)
        : typeof options.renameRecord === "function"
        ? element("h2", {class: "lex-detail-panel-title lex-detail-panel-rename"},
          element("input", {
            type: "text",
            value: String(options.title ?? ""),
            "aria-label": options.renameLabel || "Record name",
            title: options.renameLabel || "Record name",
            oninput: event => options.renameRecord(event.target.value, event),
          }))
        : element("h2", {class: "lex-detail-panel-title"},
          element("span", {class: "lex-detail-panel-name"}, ...breakableName(options.title ?? "")));
    // The name is the one thing on a record people most often want to paste
    // somewhere else, so it copies like any property value, from its right.
    const titleText = () => {
      const field = title.querySelector('input:not([type="checkbox"]),select,textarea');
      if (field) return field.tagName === "SELECT"
        ? (field.selectedOptions[0]?.textContent || field.value) : field.value;
      const bitmap = title.querySelector(".lex-bitmap-text[aria-label]");
      if (bitmap) return bitmap.getAttribute("aria-label");
      const name = title.querySelector(".lex-detail-panel-name") || title;
      return name.textContent.trim();
    };
    // A heading reads: its name, the help bubble, the copy button, then a
    // thing finder when the panel can pick a different record from here.
    if (options.help) title.append(infoHelp(options.help));
    // No title copy button: its glyph read as a second duplicate button
    // next to the real one, so the heading keeps name, help and finder only.
    if (typeof options.find === "function") {
      const label = options.findTitle || "Find a different record";
      title.append(element("button", {type: "button", class: "lex-title-finder", title: label,
        "aria-label": label, onclick: event => { event.stopPropagation(); options.find(event); }},
        selectionIcon()));
    }
    const identity = element("div", {class: "lex-detail-panel-identity"},
      title,
      // The identity slot is the big ghosted record number, sized to the
      // heading and laid over its right end. A long string there runs straight
      // through the title, so anything longer than a short code is shown as
      // the ordinary subtitle line instead of as the watermark.
      options.identity
        ? element("div", {class: typeof options.identity === "string" && options.identity.length > 8
            ? "lex-detail-panel-meta" : "lex-detail-panel-id"}, options.identity)
        : null,
      options.meta ? element("div", {class: "lex-detail-panel-meta"}, options.meta) : null);
    const heading = options.heading === false ? null : element("div", {
      class: ["lex-detail-panel-heading", options.icon ? "" : "no-icon", options.actions ? "" : "no-actions"].filter(Boolean).join(" "),
    },
      options.icon ? element("div", {class: sound
        ? "lex-detail-panel-icon lex-detail-panel-icon-audio"
        : "lex-detail-panel-icon",
        ...(options.previewPin ? {"data-lex-preview-pin": options.previewPin.key,
          "data-lex-preview-pin-label": options.previewPin.label || "Icon"} : {}),
        // The record's picture can be pinned as a table column like any
        // property: its pin sits on the thumbnail's corner, and a right-click
        // on the thumbnail places or removes it.
        oncontextmenu: options.iconPin ? event => { event.preventDefault(); options.iconPin.click(); } : null,
      }, options.icon, options.iconPin || null) : null,
      identity,
      options.actions ? element("div", {class: "lex-detail-panel-actions"}, options.actions) : null,
      sound ? sound.scrub : null);
    if (sound && heading) heading.classList.add("lex-audio-heading");
    const bodyBox = detailBody(bodyClass, options.body, options.paginate);
    if (heading) heading.addEventListener("contextmenu", event => {
      if (!sharedSettingsSnapshot?.developerMode) return;
      event.preventDefault();
      bodyBox._detailTabs?.addTab();
    });
    const panel = element("section", {
      ...(options.attrs || {}),
      class: ["lex-detail-panel", "lex-detail", options.headingOverlay ? "lex-detail-panel-media" : "", options.tone ? `lex-panel-tone-${options.tone}` : "", heading ? "" : "no-heading", options.className || ""].filter(Boolean).join(" "),
    }, heading, bodyBox);
    panel._DetailTabs = bodyBox._detailTabs;
    if (heading) {
      let actions = heading.querySelector(":scope > .lex-detail-panel-actions");
      if (!actions) {
        actions = element("div", {class: "lex-detail-panel-actions"});
        heading.append(actions);
        heading.classList.remove("no-actions");
      }
      // The enable switch is always the rightmost control, so in a header
      // that ends with one the dev-mode button goes before it, never after.
      const addHeader = element("button", {type: "button", class: "lex-header-icon lex-detail-add-header",
        title: "Add section (Developer Mode)", "aria-label": "Add section",
        onclick: () => addDetailHeader(panel)}, sectionIcon());
      const last = actions.lastElementChild;
      if (last?.matches?.('input[type="checkbox"]')) actions.insertBefore(addHeader, last);
      else actions.append(addHeader);
    }
    return panel;
  };
  // Every record pane lays its sections out the same way: in as many columns
  // as the pane is wide, a section too tall for its column going on in the
  // next. That used to be a per-call `paginate` flag, so three panes had it
  // and the rest stayed one long column however wide the window was. Now any
  // body made only of sections flows; `paginate: false` keeps one column,
  // and an object still passes options through.
  const sectionFlow = (bodyClass, body, paginate, onlyFlow = false) => {
    const nodes = [body || []].flat(Infinity).filter(node => node !== null && node !== undefined && node !== false);
    const sections = nodes.length > 0 && nodes.every(node =>
      node instanceof Element && node.classList.contains("lex-detail-section"));
    // Unpaged flows lay out sections and bare fields alike; anything else
    // passes through untouched, the way paginate:false left it.
    const unpaged = paginate && typeof paginate === "object" && paginate.unpaged === true;
    const flowable = sections || (unpaged && nodes.length > 0 && nodes.every(node =>
      node instanceof Element && node.classList.contains("lex-detail-field")));
    const flow = paginate === false ? null
      : paginate ? (typeof paginate === "object" ? paginate : {})
      : sections ? {inline: true} : null;
    // A tab's content that does not flow is left exactly as it was given.
    if (onlyFlow && (!flow || (unpaged && !flowable))) return null;
    const box = element("div", {class: bodyClass}, nodes);
    return flow ? paginateSettings(box, flow) : box;
  };

  // A panel can own local navigation without turning those choices into
  // application-level tabs. Plugins provide the active key and content; this
  // shared component owns the tab semantics and stable panel geometry.
  // A panel may contain a second tabbed panel for choices within that view.
  // Each bar remains a sibling of its own content, never a child of a bar.
  const NESTED_TAB_ERROR =
    "Put nested panel tabs inside the panel content, not inside another tab bar.";
  const guardNestedTabs = root => {
    if (!(root instanceof Element)) return root;
    requestAnimationFrame(() => {
      if (!root.isConnected) return;
      const nested = root.querySelector(".lex-subtab-bar .lex-subtab-bar:not([hidden])");
      if (nested) throw new Error(NESTED_TAB_ERROR);
    });
    return root;
  };

  // A property a developer dragged onto another panel tab lives there now.
  // Caller-owned tabs render only the active one, so the move cannot be a
  // DOM rearrangement: it is a membership override the caller honors when
  // it rebuilds, keyed by the accepting tabs and the caller's own shape.
  // Neither side's arrangement orphans: the tab a field left still finds
  // its layout by counting the ghost, and the tab it joined finds its own
  // by discounting the arrival (adoptFieldTabLayout). Only the override
  // ships; every reader derives the same migrated layouts from it.
  const fieldTabOverridesKey = shape => `${shellPluginId()}-${activePageTab()}.fieldtabs.${shape}`;
  const readFieldTabOverrides = shape => {
    if (!shape) return {};
    try {
      const stored = JSON.parse(localStorage.getItem(fieldTabOverridesKey(shape)) || "null");
      return stored && typeof stored === "object" ? stored : {};
    } catch (_error) { return {}; }
  };
  const writeFieldTabOverrides = (shape, map) => {
    const key = fieldTabOverridesKey(shape);
    const value = JSON.stringify(map);
    try { localStorage.setItem(key, value); } catch (_error) {}
    callWindow("save_default_view", shellPluginId(), activePageTab(), {[key]: value}).catch(() => {});
  };
  const fieldTabHiddenKey = shape => `${shellPluginId()}-${activePageTab()}.fieldtabs.${shape}.hidden`;
  const readFieldTabHidden = shape => {
    if (!shape) return [];
    try {
      const stored = JSON.parse(localStorage.getItem(fieldTabHiddenKey(shape)) || "null");
      return Array.isArray(stored) ? stored.filter(id => typeof id === "string") : [];
    } catch (_error) { return []; }
  };
  const writeFieldTabHidden = (shape, ids) => {
    const key = fieldTabHiddenKey(shape);
    const value = JSON.stringify(ids);
    try { localStorage.setItem(key, value); } catch (_error) {}
    callWindow("save_default_view", shellPluginId(), activePageTab(), {[key]: value}).catch(() => {});
  };
  // Tabs the reader removed, minus any a property moved back to: overrides
  // and undo can still deal members to a hidden tab's group, and a tab with
  // members is alive again whether or not the store was cleaned.
  const visibleFieldTabs = (tabs, shape, members) => {
    const hidden = readFieldTabHidden(shape);
    if (!hidden.length) return [...(tabs || [])];
    return (tabs || []).filter(tab => !hidden.includes(String(tab.id)) || (members?.[tab.id]?.length > 0));
  };
  const refreshSubtabBar = bar => {
    const options = bar?.__lexSubtabOptions;
    if (!bar || !options) return;
    if (!bar.isConnected) return;
    const active = bar.querySelector(".lex-subtab-button.active")?.dataset.subtab;
    const hadFocus = bar.contains(document.activeElement);
    const next = subtabBar(options);
    bar.replaceWith(next);
    if (hadFocus) (active && next.querySelector(`.lex-subtab-button[data-subtab="${active}"]`)
      || next.querySelector(".lex-subtab-button"))?.focus({preventScroll: true});
  };
  // Moves caller-built field nodes across its tab groups per the stored
  // overrides, and answers the shape the panel marks itself with. A move
  // whose target is gone (or whose field the record lacks) stays put.
  const applyFieldTabOverrides = (groups, tabs, options = {}) => {
    const accept = [...new Set(options.accept || [])];
    const shape = textDigest([...accept].sort().join("\n") + "\n" + String(options.callerShape || ""));
    const entries = Object.entries(readFieldTabOverrides(shape));
    if (!entries.length) return shape;
    // A move whose target tab exists but holds no group yet (an empty tab
    // the caller accepts drops onto) starts that tab's group: refusing it
    // would strand the override and the drop would silently do nothing.
    // Tabs outside accept keep the old behavior and stay put.
    const groupOf = id => {
      const tab = (tabs || []).find(tab => tab.id === id);
      if (!tab) return undefined;
      if (!groups.has(tab.label)) {
        if (!accept.includes(tab.id)) return undefined;
        groups.set(tab.label, []);
      }
      return groups.get(tab.label);
    };
    const find = fieldKey => {
      for (const list of groups.values()) {
        const at = list.findIndex(node => node?.dataset?.lexLayoutField === fieldKey);
        if (at >= 0) return {list, at};
      }
      return null;
    };
    for (const [fieldKey, rule] of entries) {
      const target = groupOf(rule?.to);
      const found = find(fieldKey);
      if (!target || !found || found.list === target) continue;
      target.push(...found.list.splice(found.at, 1));
    }
    return shape;
  };
  const tabbedPanel = (options = {}) => {
    const suppliedTabs = options.tabs || [];
    // A misc tab is written with its full stop and comes last, after
    // every named area, with a tweaks tab after it when a panel has one.
    const tabRank = tab => {
      const id = String(tab.id).toLocaleLowerCase();
      return id === "tweaks" ? 2 : id === "misc" ? 1 : 0;
    };
    const tabTitle = tab => {
      const name = shownSubtabName(tab);
      return String(tab.id).toLocaleLowerCase() === "misc" && name === "Misc"
        ? "Misc." : name;
    };
    const members = options.fieldTabs?.members;
    const shape = options.fieldTabs?.shape;
    const flagged = [...suppliedTabs].sort((a,b)=>tabRank(a)-tabRank(b)
      ||tabTitle(a).localeCompare(tabTitle(b),undefined,{numeric:true,sensitivity:"base"}))
      .map(tab => {
        // A tab with no members is an empty husk the overrides drained: gray
        // it with a reason, which keeps it focusable and drop-revivable where
        // native disabled would eat both. Bespoke content tabs never derive.
        const isEmpty = tab.empty === true || (tab.empty !== false && tab.bespoke !== true
          && !!members && !(members[tab.id]?.length > 0));
        const disabled = tab.disabled || isEmpty;
        if (!disabled) return tab;
        return {...tab, disabled: true,
          disabledReason: tab.disabledReason || (isEmpty ? "This tab has no properties." : undefined),
          ...(isEmpty ? {isEmptyTab: true} : {})};
      });
    const tabs = flagged;
    const visible = visibleFieldTabs(flagged, shape, members);
    const live = visible.filter(tab => !tab.disabled);
    const active = (visible.some(tab => tab.id === options.active)
        && !flagged.find(tab => tab.id === options.active)?.disabled)
      ? options.active
      : (live[0] || visible[0])?.id;
    const selected = tabs.find(tab => tab.id === active);
    const content = typeof options.content === "function"
      ? options.content(active, selected)
      : options.content;
    const contentNodes = [content || []].flat(Infinity).filter(Boolean);
    const empty = contentNodes.length === 1 && contentNodes[0] instanceof Element
      && contentNodes[0].classList.contains("lex-notice");
    const bar = subtabBar({
      tabs,
      active,
      label: options.label || "Panel views",
      className: "lex-tabbed-panel-tabs",
      shortcuts: false,
      change: options.change,
      fieldTabs: options.fieldTabs,
    });
    return guardNestedTabs(element("section", {
      ...(options.attrs || {}),
      class: ["lex-tabbed-panel", options.className || ""].filter(Boolean).join(" "),
    }, bar, element("div", {
      class: ["lex-tabbed-panel-content", empty ? "lex-tabbed-panel-empty" : "", options.contentClassName || ""].filter(Boolean).join(" "),
      role: "tabpanel",
      "aria-label": selected?.label || "Panel content",
    }, sectionFlow("lex-detail-panel-body", content, options.paginate, true) || content || [])));
  };

  // A select that shows one of hundreds of choices holds only that choice
  // until someone reaches for it. FF8's AI view has a few hundred opcode and
  // branch selects, and building every option of every one up front was
  // twenty-five thousand elements and six seconds of frozen window.
  // `entries` is an array of {value, label} or a function returning one.
  const lazyOptions = (control, entries) => {
    if (!(control instanceof HTMLSelectElement)) return control;
    let filled = false;
    const fill = () => {
      if (filled) return;
      filled = true;
      const value = control.value;
      const list = typeof entries === "function" ? entries() : entries;
      control.replaceChildren(...list.map(entry => element("option", {value: entry.value, disabled: !!entry.disabled}, entry.label)));
      control.value = value;
    };
    for (const type of ["pointerdown", "focus", "keydown"]) control.addEventListener(type, fill);
    control.lexFillOptions = fill;
    return control;
  };

  // Keep the visible value legible when a bounded control contains a long
  // enum label. Width changes and value changes use the same measurement path.
  //
  // Fitting is reset, read, write. Done one control at a time, each read came
  // straight after the previous control's write and cost a full layout, which
  // on FF8's AI view was half a second for four hundred selects. Resizes and
  // first fits are therefore gathered and done together: every reset, then
  // every read, then every write.
  const autoFitQueue = new Set();
  // Numbers that share a row - and rows that share a panel - share one size.
  // Fitted one input at a time, a long value shrank while a short neighbour
  // kept full size, so one coordinate row held three different fonts (DS1
  // maps: "-170.125" small beside full-size "-100.5" and "30.25"). The scope
  // is every vector row in the panel, the way list text is fitted per list;
  // a row outside any panel is its own scope. Unscoped controls fit alone,
  // as before, so editing one value never refits untouched controls.
  const autoFitScope = control => {
    if (control.closest?.(".lex-multi-number"))
      return control.closest(".lex-detail-panel") || control.closest(".lex-multi-number");
    return control.closest?.(".lex-detail-section")
      || control.closest?.(".lex-tabbed-panel-content")
      || control.closest?.(".lex-detail-panel")
      || null;
  };
  const autoFitMates = control => {
    const scope = autoFitScope(control);
    if (!scope) return [control];
    if (scope.classList.contains("lex-multi-number")) {
      const mates = [...scope.querySelectorAll("input,select,textarea,.lex-readonly-field")]
        .filter(node => node.__lexAutoFitUpdate && node.isConnected);
      return mates.length ? mates : [control];
    }
    if (control.closest?.(".lex-multi-number")) {
      const rows = [...scope.querySelectorAll(".lex-multi-number")];
      const mates = rows.flatMap(row =>
        [...row.querySelectorAll("input,select,textarea,.lex-readonly-field")])
        .filter(node => node.__lexAutoFitUpdate && node.isConnected);
      return mates.length ? mates : [control];
    }
    const mates = [...scope.querySelectorAll("input,select,textarea,.lex-readonly-field")]
      .filter(node => node.__lexAutoFitUpdate && node.isConnected);
    return mates.length ? mates : [control];
  };
  const addAutoFit = control => {
    autoFitQueue.add(control);
  };
  const flushAutoFit = () => {
    const controls = [...autoFitQueue].filter(control => control.isConnected);
    autoFitQueue.clear();
    const queued = new Set(controls);
    controls.forEach(control => control.__lexAutoFitReset());
    const fits = controls.map(control => control.__lexAutoFitMeasure());
    controls.forEach((control, index) => { control.__lexAutoFitCached = fits[index] || null; });
    const byScope = new Map();
    controls.forEach((control, index) => {
      const fit = fits[index];
      if (!fit) return;
      const scope = autoFitScope(control);
      if (!scope) {
        control.__lexAutoFitApply({size: fit.size, height: fit.size > fit.natural ? fit.height : 0});
        return;
      }
      if (!byScope.has(scope)) byScope.set(scope, []);
      byScope.get(scope).push(control);
    });
    for (const [scope, members] of byScope) {
      const seen = new Set(members);
      const sizes = members.map(control => control.__lexAutoFitCached.size);
      const extra = [];
      // Multi-number rows mate across rows, not across the scope; everywhere
      // else one scan finds every mate.
      const candidates = scope.querySelector(".lex-multi-number")
        ? members.flatMap(control => autoFitMates(control))
        : [...scope.querySelectorAll("input,select,textarea,.lex-readonly-field")];
      for (const mate of candidates) {
        if (seen.has(mate) || !mate.__lexAutoFitUpdate || !mate.isConnected || !mate.__lexAutoFitCached) continue;
        seen.add(mate);
        sizes.push(mate.__lexAutoFitCached.size);
        extra.push(mate);
      }
      const size = Math.min(...sizes);
      const share = node => {
        const cached = node.__lexAutoFitCached;
        node.__lexAutoFitApply({size, height: size > cached.natural ? cached.height : 0});
      };
      members.forEach(share);
      extra.forEach(share);
    }
  };
  // An edit queues only the edited control. Its mates keep their cached
  // fits: their values did not change, so neither did their sizes, and
  // measuring the whole scope per keystroke is the lag this guard exists
  // to forbid. Only a cold registration pulls its mates along.
  const queueAutoFit = (control, mates = false) => {
    if (!autoFitQueue.size) requestAnimationFrame(flushAutoFit);
    addAutoFit(control);
    if (mates && autoFitScope(control)) autoFitMates(control).forEach(mate => autoFitQueue.add(mate));
  };
  // One observer for every fitted control, held here for the life of the page.
  const autoFitObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(entries => {
      // New geometry voids the cached fit; the flush re-measures the control
      // and the scope minimum still reaches its mates through their caches.
      entries.forEach(entry => {
        delete entry.target.__lexAutoFitCached;
        addAutoFit(entry.target);
      });
      flushAutoFit();
    })
    : null;
  const autoFitControlText = (control, options = {}) => {
    const readOnlyBox = control instanceof HTMLElement && control.classList.contains("lex-readonly-field");
    if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement || readOnlyBox)) return control;
    if (control.dataset.lexAutofit === "false") return control;
    if (control.__lexAutoFitUpdate) {
      queueAutoFit(control);
      return control;
    }
    const minimum = Math.max(8, Number(options.minimum) || (control instanceof HTMLSelectElement ? 8 : 11));
    // The size the text needs, read with the control at its natural size.
    const measure = () => {
      // Off-page controls have no width. Fitting them to zero made their font
      // tiny, so pagination measured a shorter card than the one later shown.
      if (!control.getClientRects().length || control.clientWidth <= 0) return null;
      const style = getComputedStyle(control);
      // A table cell's value is the table's text: it may shrink to fit a
      // narrow column but never grows past the rows around it, which a box
      // the height of the row otherwise invited.
      // An instruction step reads the same way: a short opcode such as "If"
      // must not tower over the operands beside it.
      const naturalSize = Number.parseFloat(style.fontSize) || 0;
      const maximum = control instanceof HTMLTextAreaElement || control.closest(".lex-column-list, .lex-instruction-controls")
        ? naturalSize || 16
        : Math.min(naturalSize || 28, Math.max(minimum,Math.min(28,control.clientHeight*.78)));
      // A parked unit sits left of the reserved lane, inside the text's
      // own room: the value must end before the unit starts, so the unit's
      // width counts against the text like padding. Short values never bind
      // on it (the unit follows them instead), so only long values shrink.
      const parkedUnit = control.closest?.(".lex-unit-field")?.querySelector?.(":scope > .lex-unit");
      const padLeft = Number.parseFloat(style.paddingLeft) || 0;
      const border = (Number.parseFloat(style.borderLeftWidth) || 0) +
        (Number.parseFloat(style.borderRightWidth) || 0);
      // A select face runs to its arrow: padding-right sits shadowed under
      // the arrow zone, so counting it shrank faces like "Walk to Target"
      // that fit with daylight to spare. The arrow glyph starts ~13px from
      // the client edge (pixel-measured); 15 keeps a gap. An inner
      // reference rail still paints over the face, so its lane counts.
      const internalRail = control instanceof HTMLSelectElement ? Number.parseFloat(
        style.getPropertyValue("--lex-internal-reference-width")) || 0 : 0;
      const horizontal = control instanceof HTMLSelectElement
        ? padLeft + border + 15 + internalRail
        : padLeft + (Number.parseFloat(style.paddingRight) || 0) + border + 2;
      const withUnit = horizontal + (parkedUnit ? parkedUnit.offsetWidth || 0 : 0);
      const available = Math.max(1, control.clientWidth - withUnit);
      const value = control instanceof HTMLSelectElement
        ? control.selectedOptions[0]?.textContent || ""
        : readOnlyBox ? (control.value ?? control.textContent ?? "").trim()
        : control.value || control.placeholder || "";
      const canvas = autoFitControlText.canvas ||= document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context || !value) return null;
      context.font = `${style.fontStyle} ${style.fontWeight} ${maximum}px ${style.fontFamily}`;
      const measured = context.measureText(value).width;
      const natural = naturalSize;
      // Padding in em grows with the font, so a size that fits at the natural
      // size can overflow once applied: the box that measured room for "0"
      // grew its own padding past the digit. The padded bound holds padding
      // proportional to the size, which is exact for em padding and
      // conservative for pixels; it only ever binds when growing, so
      // shrinking a long value fits exactly as before.
      const paddingRight = Number.parseFloat(style.paddingRight) || 0;
      const rate = measured / Math.max(1, maximum);
      const padded = natural > 0 && rate > 0
        ? (available + paddingRight) / (rate + paddingRight / natural) : maximum;
      const size = Math.max(minimum,Math.min(maximum,
        maximum*available/Math.max(1,measured),padded));
      // The ceiling above is read from the box's natural height, and that
      // height comes from the text. Enlarged digits would make the box taller,
      // the next fit would read a taller box, and every numeric property grew
      // instead of filling. Text larger than the natural font therefore keeps
      // the natural box: the digits fill it, the box stays where it was.
      // The scope fit may apply a smaller size than this control asked
      // for, so the height is captured unconditionally and the caller
      // decides whether the applied size outgrew the natural box.
      return {size, natural, height: control.getBoundingClientRect().height};
    };
    // The reference overlay inside this value box, if one is mounted.
    const referenceOverlay = () => control.closest?.(".lex-source-control-internal")
      ?.querySelector?.(":scope > .lex-reference-values") || null;
    const reset = () => {
      control.style.fontSize = "";
      control.style.height = "";
      control.style.boxSizing = "";
      referenceOverlay()?.style.setProperty("font-size", "");
    };
    const apply = fit => {
      if (!fit) return;
      if (fit.height) {
        control.style.boxSizing = "border-box";
        control.style.height = `${fit.height}px`;
      }
      control.style.fontSize = `${fit.size}px`;
      // The reference shares the value box, so it shares the value's fitted
      // size: a value that shrank beside a full-size reference reads as two
      // programs. The overlay only sets the em the lane clamp counts in, so
      // a lane narrower than the reference still shrinks it further.
      referenceOverlay()?.style.setProperty("font-size", `${fit.size}px`);
    };
    const update = () => {
      const mates = autoFitMates(control).filter(node => node.isConnected);
      mates.forEach(node => node.__lexAutoFitReset());
      const fits = mates.map(node => node.__lexAutoFitMeasure());
      const asked = fits.filter(Boolean).map(fit => fit.size);
      if (!asked.length) return;
      const size = Math.min(...asked);
      mates.forEach((node, index) => {
        if (fits[index]) node.__lexAutoFitApply({size,
          height: size > fits[index].natural ? fits[index].height : 0});
      });
    };
    // An edit commonly emits both events. Fit once in the next frame so
    // handlers do not repeatedly force layout across a large detail panel.
    const queueUpdate = () => queueAutoFit(control);
    control.addEventListener("input", queueUpdate);
    control.addEventListener("change", queueUpdate);
    control.__lexAutoFitUpdate = update;
    control.__lexAutoFitMeasure = measure;
    control.__lexAutoFitReset = reset;
    control.__lexAutoFitApply = apply;
    autoFitObserver?.observe(control);
    queueAutoFit(control, true);
    return control;
  };
  document.fonts?.addEventListener?.("loadingdone", event => {
    if (!event.fontfaces.length) return;
    document.querySelectorAll("input,select,textarea").forEach(control => {
      if (control.__lexAutoFitUpdate) queueAutoFit(control);
    });
  });

  // Every value box on a panel should end at the same edge, so the reference
  // rail takes the widest requirement in that panel rather than each control
  // keeping its own.
  const alignReferenceRailsNow = (containers = [document]) => {
    const controlsFor=(container,selector)=>[
      ...(container instanceof Element&&container.matches(selector)?[container]:[]),
      ...(container.querySelectorAll?.(selector)||[])
    ];
    // Every read first, then every write, then one read of the probes and
    // their writes: two layouts for the whole pass. Reading a row after the
    // previous row's write forced a layout per property, and with each caller
    // running its own pass, switching records laid the page out dozens of
    // times (Lexer: "OBSCENE amounts of lag every time i do LITERALLY
    // ANYTHING").
    const panels = new Map();
    for (const container of containers)
      controlsFor(container, ".lex-source-control[data-lex-rail-tag]").forEach(control => {
        const panel = control.closest(".lex-detail-panel-body, .lex-detail-panel, .lex-detail") || container;
        if (!panels.has(panel)) panels.set(panel, null);
      });
    const outside = [...panels.keys()].map(panel => {
      const controls = [...panel.querySelectorAll(".lex-source-control[data-lex-rail-tag]")];
      // Each entry gets an equal share of the space beside the property it
      // annotates, so a deeper stack is a smaller stack rather than a taller
      // row. The share is taken from the PROPERTY ROW, not from the value box
      // inside it: dividing the shorter box by three left a three-deep stack
      // at seven pixels.
      const caps = controls.map(control => {
        const count = control.querySelector(":scope > .lex-reference-values")?.children.length || 0;
        const row = control.closest(".lex-detail-field") || control;
        return count ? {count, height: row.getBoundingClientRect().height} : null;
      });
      return {panel, controls, caps};
    }).filter(entry => entry.controls.length);
    // An inside rail lives in the value box, so its share comes from that box
    // rather than from the property row: it is capped at the box's own height.
    // These controls have no outside rail, so their share is measured on its
    // own - a graph card's variable drawer is a panel with nothing else in it.
    const insideRails = [];
    const seenInside = new Set();
    for (const container of containers)
      controlsFor(container, ".lex-source-control[data-lex-inside-rail]").forEach(control => {
        if (seenInside.has(control)) return;
        seenInside.add(control);
        const count = control.querySelector(":scope > .lex-reference-values")?.children.length || 0;
        if (!count) return;
        // The box the rail shares is the control's own input, not the grid
        // cell around it, which is taller than the box inside it.
        const box = control.querySelector("input:not([type=checkbox]), select, output, textarea")
          || control.querySelector(":scope > .lex-unit-field, :scope > .lex-readonly-field") || control;
        const cap = Math.max(12, Math.round(box.getBoundingClientRect().height) - 2);
        const fontSize = Math.max(8, parseFloat(getComputedStyle(control).fontSize) || 16);
        insideRails.push({control, cap, count, fontSize, boxWidth: control.getBoundingClientRect().width});
      });

    // Writes, and every probe mounted at once.
    for (const {controls, caps} of outside) {
      controls.forEach((control, index) => {
        const measured = caps[index];
        if (!measured) {
          control.style.removeProperty("--lex-reference-slot");
          control.style.removeProperty("--lex-reference-cap");
          return;
        }
        const cap = Math.max(12, Math.round(measured.height) - 4);
        control.style.setProperty("--lex-reference-cap", `${cap}px`);
        control.style.setProperty("--lex-reference-slot", `${Math.max(6, Math.floor(cap / measured.count))}px`);
      });
    }
    // The outside rail is reserved in advance from the longest tag and the
    // longest value any control on the panel can ever put in it, measured in
    // a hidden copy of a real entry rather than from the entries on screen,
    // so the value boxes never move as values change. The probe is pinned to
    // the largest type a stack ever uses, because a deeper stack only ever
    // draws smaller.
    for (const entry of outside) {
      const longest = (attribute, floor) => entry.controls
        .map(control => control.dataset[attribute] || "")
        .reduce((widest, text) => text.length > widest.length ? text : widest, floor);
      entry.probe = element("div", {
        class: "lex-source-strip lex-reference-values lex-reference-probe",
        "aria-hidden": "true",
      }, element("span", {class: "lex-reference-value"},
        element("span", {class: "lex-reference-tag"}, longest("lexRailTag", "V")),
        element("span", {class: "lex-reference-text"}, longest("lexRailValue", "000"))));
      (entry.controls[0].parentElement || entry.panel).append(entry.probe);
    }
    for (const rail of insideRails) {
      const {control, cap, count, fontSize} = rail;
      control.style.setProperty("--lex-reference-cap", `${cap}px`);
      control.style.setProperty("--lex-reference-slot", `${Math.max(6, Math.floor(cap / count))}px`);
      // The lane is measured from the longest entry this rail can paint, at
      // the size it paints it (an inside rail draws at the value's own size),
      // and at the rail's preferred size, before its own reservation
      // constrains it - measuring the constrained font fed the previous width
      // back into the next reservation.
      const probe = element("span", {class: "lex-reference-value lex-reference-probe-value",
        "aria-hidden": "true"},
        element("span", {class: "lex-reference-tag"}, control.dataset.lexInsideTag || "V"),
        element("span", {class: "lex-reference-text"}, control.dataset.lexInsideValue || ""));
      probe.style.fontSize = `${fontSize}px`;
      control.append(probe);
      rail.probe = probe;
    }

    // One read of every probe, then their writes.
    for (const entry of outside) {
      entry.tag = Math.ceil(entry.probe.querySelector(".lex-reference-tag").getBoundingClientRect().width);
      entry.text = Math.ceil(entry.probe.querySelector(".lex-reference-text").getBoundingClientRect().width);
    }
    const widths = insideRails.map(({probe}) => Math.ceil(probe.getBoundingClientRect().width) + 2);
    for (const entry of outside) {
      entry.probe.remove();
      // tag + the column gap the stack opens between the two + the value, and
      // two pixels so the last glyph is not flush against the panel edge.
      const widest = entry.tag + entry.text + 6;
      const changed = entry.panel.style?.getPropertyValue("--lex-panel-reference-rail-width") !== `${widest}px`;
      entry.panel.style?.setProperty("--lex-panel-reference-rail-width", `${widest}px`);
      entry.panel.style?.setProperty("--lex-reference-tag-width", `${entry.tag}px`);
      if (changed && entry.panel instanceof Element)
        entry.panel.querySelectorAll("input,select,textarea").forEach(node => {
          if (node.__lexAutoFitUpdate) {
            delete node.__lexAutoFitCached;
            queueAutoFit(node);
          }
        });
      for (const control of entry.controls) {
        control.style.setProperty("--lex-reference-requested-width", `${widest}px`);
        control.style.setProperty("--lex-reference-tag-width", `${entry.tag}px`);
      }
    }
    insideRails.forEach(({control, probe, fontSize, boxWidth}, index) => {
      probe.remove();
      const width = widths[index];
      if (width <= 2) return;
      const laneKey = "--lex-internal-reference-requested-width";
      if (control.style.getPropertyValue(laneKey) !== `${width}px`) {
        control.style.setProperty(laneKey, `${width}px`);
        const fitted = control.querySelector("input,select,textarea");
        if (fitted?.__lexAutoFitUpdate) {
          delete fitted.__lexAutoFitCached;
          queueAutoFit(fitted);
        }
      }
      // The lane is capped at 35% of the box. Only when that cap is narrower
      // than the reference needs does the reference shrink, and only by that
      // much.
      const lane = boxWidth ? Math.min(width, boxWidth * 0.35) : width;
      control.style.setProperty("--lex-reference-fit", `${Math.max(8, fontSize * Math.min(1, lane / width))}px`);
    });
  };
  // Every value box on a panel should end at the same edge, so the reference
  // rail takes the widest requirement in that panel rather than each control
  // keeping its own. Callers ask for it as often as they like; the work is
  // done once, before the next paint, over everything asked for.
  const pendingRailContainers = new Set();
  let railFrame = 0;
  const flushReferenceRails = () => {
    cancelAnimationFrame(railFrame);
    railFrame = 0;
    const containers = [...pendingRailContainers].filter(node => node === document || node.isConnected);
    pendingRailContainers.clear();
    if (!containers.length) return;
    const outer = containers.includes(document) ? [document]
      : containers.filter(node => !containers.some(other => other !== node && other.contains(node)));
    alignReferenceRailsNow(outer);
  };
  const alignReferenceRails = (container = document) => {
    pendingRailContainers.add(container);
    if (!railFrame) railFrame = requestAnimationFrame(flushReferenceRails);
  };

  // Refresh every mounted reference display from its live control value. This
  // is the single update path for all plugins and all control types.
  const refreshReferences = (container = document) => {
    container.querySelectorAll?.(".lex-source-control").forEach(node => node.refreshReference?.());
    container.querySelectorAll?.("[data-lex-record-provenance]").forEach(node => node.refreshRecordProvenance?.());
    alignReferenceRails(container);
  };
  // Reserve newly mounted rails immediately, including panels added after
  // fonts are ready. A successfully loaded face can change their text width;
  // failed font requests do not require another pass over every control.
  document.fonts?.addEventListener?.("loadingdone", event => {
    if(event.fontfaces.length)alignReferenceRails(document);
  });
  new MutationObserver(records=>{
    const roots=new Set();
    const healed=new Set();
    for(const record of records){
      for(const node of record.addedNodes){
        if(node instanceof Element&&node.isConnected&&
          (node.matches('.lex-source-control')||node.querySelector('.lex-source-control')))roots.add(node);
      }
      for(const node of record.removedNodes){
        if(!(node instanceof Element))continue;
        const gone=node.matches('input,select,textarea')?[node]:[...node.querySelectorAll('input,select,textarea')];
        if(!gone.some(control=>control.__lexAutoFitUpdate))continue;
        const scope=record.target instanceof Element&&record.target.isConnected?record.target:null;
        if(!scope)continue;
        for(const control of scope.querySelectorAll('input,select,textarea'))healed.add(control);
      }
    }
    for(const root of roots)alignReferenceRails(root.closest('.lex-detail-panel-body, .lex-detail-panel, .lex-detail')||root);
    for(const control of healed)if(control.__lexAutoFitUpdate&&control.isConnected)queueAutoFit(control);
  }).observe(document.documentElement,{childList:true,subtree:true});

  // A section heading is renamed the same way a property name is: a
  // developer double-clicks it, types, and the wording ships for everyone
  // who sees that title. Like a field label, the key is the page tab plus the
  // shipped title, so every copy of a heading within one tab (a section dealt
  // across paginated columns repeats it) reads one chosen wording.
  const sectionTitleKey = title =>
    `${shellPluginId()}-${activePageTab()}.section.${title}.label`;
  // Shared Detail internals. A game supplies its theme and field controls;
  // this component owns the repeated section and field structure.
  const detailSection = (options = {}) => {
    const shippedTitle = typeof options.title === "string" ? options.title : "";
    // A collapsible section's own summary already owns its click (open or
    // close); renaming it in place there would fight the native toggle, so
    // only a plain section heading gets the double-click editor.
    const titleText = shippedTitle && !options.collapsible
      ? (() => {
          const node = element("span", {class: "lex-detail-section-title-text",
            "data-lex-label-key": sectionTitleKey(shippedTitle)},
            savedLabel(sectionTitleKey(shippedTitle), shippedTitle));
          node.addEventListener("dblclick", event => {
            if (!sharedSettingsSnapshot?.developerMode) return;
            event.preventDefault();
            event.stopPropagation();
            renameInPlace(sectionTitleKey(shippedTitle), activePageTab(), shippedTitle, node);
          });
          return node;
        })()
      : options.title;
    return element(options.collapsible ? "details" : "section", {
      ...(options.attrs || {}),
      class: ["lex-detail-section", options.className || ""].filter(Boolean).join(" "),
      "data-lex-layout-section": options.layoutKey || shippedTitle,
      "aria-label": options.ariaLabel || shippedTitle || null,
      ...(options.collapsible && options.open ? {open: true} : {}),
    }, options.title ? element(options.collapsible ? "summary" : "h3", {class: "lex-detail-section-title"},
      titleText, options.help || null) : null,
    element("div", {class: "lex-detail-section-content"}, options.body || []));
  };

  // What a section says when it holds nothing. A section with no rows used to
  // invent one - a property named for the storage state rather than for
  // anything in the game - and the reader could not tell the invented row from
  // a real one. A note is not a property: no label column, no control, no pin.
  // A page that rearranges a section - FF8 moves a GF's abilities under its own
  // tabs - asks for its parts instead of querying the shared class names.
  // The icon box of a panel, for a page that renders a model or a preview into
  // it - RDR2 draws its weapon models there.
  const panelIcon = panel => panel?.querySelector(".lex-detail-panel-icon") || null;

  const sectionParts = section => ({
    title: section?.querySelector(":scope > .lex-detail-section-title") || null,
    content: section?.querySelector(":scope > .lex-detail-section-content, :scope > .lex-detail-panel-body") || null,
  });

  // Every piece of the shell's own text a game may want to redraw - Warband
  // and FF7 Remake paint these in the game's bitmap font. Asking for them keeps
  // the class names inside the framework.
  const shellTextNodes = (root = document) => [
    ...root.querySelectorAll(".lex-brand-button h1"),
    ...root.querySelectorAll(".lex-shell-header nav button .lex-tab-label-text"),
    // The name inside a heading, so a redraw leaves its copy button alone.
    ...[...root.querySelectorAll(".lex-detail-panel-title")]
      .map(title => title.querySelector(":scope > .lex-detail-panel-name") || title),
  ];

  // Close any shared dialog that is open, without knowing how one is built.
  const dismissDialogs = (root = document) =>
    root.querySelectorAll(".lex-dialog-backdrop").forEach(node => node.remove());

  // Something the reader has to act on, above the content it concerns:
  // a title, a sentence, and the one button that deals with it.
  const notice = (options = {}) => element("div", {
    class: ["lex-notice", options.tone ? `lex-tone-${options.tone}` : "", options.className || ""].filter(Boolean).join(" "),
    role: "status",
  }, element("div", {class: "lex-notice-text"},
    options.title ? element("strong", {}, options.title) : null,
    options.message ? element("span", {}, options.message) : null),
  options.action || null);

  // Buttons that act on the thing above them, in one wrapping row.
  const actionRow = (...children) => {
    const options=children[0] && typeof children[0]==='object' && !Array.isArray(children[0]) && !(children[0] instanceof Node) ? children.shift() : {};
    return element("div", {class:["lex-action-row",options.fillFirst?"lex-action-row-fill-first":"",options.className||""].filter(Boolean).join(" ")}, ...children);
  };

  // A table that is its own pane, with its pager under it.
  const pagedPane = (content, pagerNode) => {
    const body = element("div", {class: "lex-paged-pane-content"}, content);
    const root = element("div", {class: "lex-paged-pane"}, body, pagerNode);
    wheelPages(root, direction => {
      const label = direction > 0 ? "Next page" : "Previous page";
      pagerNode?.querySelector(`button[aria-label="${label}"]`)?.click();
    }, () => body.scrollHeight > body.clientHeight + 1);
    return root;
  };

  // One instruction per row, with a stable footer outside the page content.
  // Callers supply controls and meaning; sizing and reordering are shared.
  const instructionList = (options = {}) => {
    const rows = options.rows || [];
    let pageSize = options.pageSize || 8, page = options.page || 0, dragged = null, pageTimer;
    const body = element("div", {class:"lex-instruction-list", role:"list"});
    const footer = element("div", {class:"lex-instruction-footer"});
    const root = pagedPane(body, footer);
    root.classList.add("lex-instruction-pane");
    const repaint = () => {
      const pages = Math.max(1, Math.ceil(rows.length / pageSize));
      page = Math.max(0, Math.min(page, pages - 1));
      options.changePage?.(page,pageSize);
      body.replaceChildren(...rows.slice(page * pageSize, (page + 1) * pageSize).map((row, offset) => {
        const index = page * pageSize + offset;
        const editable = options.editable !== false && row.editable !== false;
        let controlGesture=false;
        const dragAttrs = {
          draggable:String(editable), tabindex:editable?0:-1, "aria-label":`Instruction ${index + 1}`,
          "aria-description":"Drag to reorder. With keyboard focus, press Alt and an arrow key.",
          onpointerdown:event=>{controlGesture=!!event.target.closest("input,select,textarea,button,[contenteditable=true]");},
          ondragstart:event=>{if(!editable||controlGesture){event.preventDefault();return;}dragged=index;event.dataTransfer.effectAllowed="move";event.dataTransfer.setData("text/plain",String(index));},
          ondragend:()=>{dragged=null;clearTimeout(pageTimer);},
          onkeydown:event=>{
            if (!editable || event.target!==event.currentTarget || !event.altKey || !["ArrowUp","ArrowDown"].includes(event.key)) return;
            event.preventDefault();
            const target=index+(event.key==="ArrowUp"?-1:1);
            if(target>=0&&target<rows.length)options.move?.(index,target);
          }};
        const description=element("div",{class:"lex-instruction-description"},options.describe?.(row,index));
        return element("div", {class:"lex-instruction-row",role:"listitem",...dragAttrs,
          oninput:()=>{description.textContent=options.describe?.(row,index)||'';},
          "data-instruction-index":index,"data-offset":row.offset,
          ondragover:event=>{if(dragged!==null&&editable){event.preventDefault();event.dataTransfer.dropEffect="move";}},
          ondrop:event=>{if(dragged===null||!editable)return;event.preventDefault();const from=dragged;dragged=null;if(from!==index)options.move?.(from,index);}},
          element("span",{class:"lex-instruction-index","aria-hidden":"true"},index+1),
          element("div",{class:"lex-instruction-controls"},options.controls?.(row,index)),
          description,
          element("div",{class:"lex-instruction-actions"},
            element("button",{type:"button",disabled:!editable,"aria-label":`Insert after instruction ${index+1}`,onclick:()=>options.insert?.(index)},"+"),
            element("button",{type:"button",disabled:!editable,"aria-label":`Delete instruction ${index+1}`,onclick:()=>options.remove?.(index)},"−")));
      }));
      if(!rows.length)body.append(element("button",{type:"button",disabled:options.editable===false,onclick:()=>options.insert?.(-1)},"Add instruction"));
      footer.replaceChildren(pager({inline:true,page,pages,pageSize,total:rows.length,noun:"instructions",change:value=>{page=value;repaint();}}));
      for(const [label,delta] of [["Previous page",-1],["Next page",1]]){
        const button=footer.querySelector(`[aria-label="${label}"]`);
        button?.addEventListener('dragover',event=>{
          if(dragged===null||button.disabled)return;
          event.preventDefault();
          if(!pageTimer)pageTimer=setTimeout(()=>{pageTimer=null;if(dragged!==null){page+=delta;repaint();}},600);
        });
        button?.addEventListener('dragleave',()=>{clearTimeout(pageTimer);pageTimer=null;});
      }
    };
    repaint();
    const resize = new ResizeObserver(() => {
      if(!root.isConnected)return;
      const available=root.querySelector('.lex-paged-pane-content').clientHeight;
      const height=96;
      const count=Math.max(1,Math.floor(available / height));
      if(available>0&&count!==pageSize){page=Math.floor(page*pageSize/count);pageSize=count;repaint();}
    });
    resize.observe(root);
    return root;
  };

  // Graphs side by side, as many to a row as fit at a readable width.
  const tileGrid = (cards = [], options = {}) => {
    const minimum = Math.max(80,Number(options.minWidth)||320);
    const grid = element("div", {
    class:"lex-tile-grid",
    style:`--lex-tile-min-width:${minimum}px;${options.columns ? `--lex-tile-columns:repeat(${Math.max(1,Math.floor(options.columns))},minmax(0,1fr))` : ""}`,
    }, ...cards);
    if (options.balanced && !options.columns) {
      const balance = () => {
        if (!grid.isConnected || !grid.clientWidth) return;
        const css = getComputedStyle(grid), gap = parseFloat(css.columnGap) || 0;
        const width = grid.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight);
        const count = [...grid.children].filter(child => !child.hidden && getComputedStyle(child).display !== "none").length;
        const maximum = Math.max(1, Math.floor((width + gap) / (minimum + gap)));
        // Use the fewest rows that fit, then distribute their columns evenly:
        // six cards with room for five become two rows of three, not five + one.
        const columns = Math.max(1, Math.ceil(count / Math.ceil(Math.max(1, count) / maximum)));
        grid.style.setProperty("--lex-tile-columns", `repeat(${columns},minmax(0,1fr))`);
      };
      new ResizeObserver(balance).observe(grid);
      new MutationObserver(balance).observe(grid, {childList:true, attributes:true, attributeFilter:["hidden"], subtree:true});
    }
    return grid;
  };
  const curveGrid = (...cards) => {
    const options=cards[0] && !(cards[0] instanceof Node) ? cards.shift() : {};
    const grid=tileGrid(cards,options);
    grid.classList.add("lex-curve-grid");
    return grid;
  };

  // A game as the home screen shows it: its cover, or its initial when there
  // is no cover, over its name. A faded card is a game that is not involved.
  const gameCard = (options = {}) => {
    const name = String(options.name || "");
    return element("span", {
      class: ["lex-game-card", options.faded ? "faded" : ""].filter(Boolean).join(" "),
      title: options.title || name,
    }, options.cover
      ? element("img", {class: "lex-game-card-cover", src: options.cover, alt: ""})
      : element("span", {class: "lex-game-card-cover lex-game-card-initial", "aria-hidden": "true"}, name.slice(0, 1).toUpperCase()),
    element("span", {class: "lex-game-card-name"}, name));
  };

  // A preview of a game record. The caller supplies shared links and controls;
  // this frame keeps the name, picture and hover action consistent everywhere.
  const recordCard = (options = {}) => element("article", {
    class:["lex-record-card", options.className || ""].filter(Boolean).join(" "),
  }, element("header", {class:"lex-record-card-header"},
    element("h3", {class:"lex-record-card-title"}, options.title ?? ""),
    options.identity == null ? null : element("span", {class:"lex-record-card-id"}, options.identity)),
  element("div", {class:"lex-record-card-image"}, options.image || noImage()),
  options.body == null ? null : element("div", {class:"lex-record-card-body"}, options.body),
  options.action ? element("div", {class:"lex-record-card-action"}, options.action) : null);

  // The component catalogue's frame for one live sample: the component at the
  // size it really is, or across the pane when it is a page-wide one.
  const componentSample = (content, options = {}) => element("section", {
    class: ["lex-component-sample", options.glyph ? "glyph" : "", options.wide ? "wide" : ""].filter(Boolean).join(" "),
  }, content);

  // A bar over the content it switches: the bar keeps its height and the
  // content takes the rest of the page.
  const toolbar = (...children) => element("div", {class:"lex-toolbar"}, ...children);
  const inlineLabel = (...children) => {
    const options=children[0] && typeof children[0]==='object' && !(children[0] instanceof Node) ? children.shift() : {};
    return element("span", {class:`lex-inline-label${options.imageFit==='row'?' lex-inline-label-row-image':''}`}, ...children);
  };
  // Source identity is supplied by the plugin; modifying a vanilla record
  // does not make it a newly created record.
  const recordSource = (options = {}) => {
    if (options.vanilla) return null;
    if (options.created) return element("span", {class:"lex-ui-symbol lex-record-source",
      role:"img", title:"Created in this mod", "aria-label":"Created in this mod"}, "✒️");
    // A changed record is not a new one: the delta says its values differ
    // from the game's own, while the pen stays reserved for added rows.
    if (options.modified) return element("span", {class:"lex-ui-symbol lex-record-source",
      role:"img", title:"Changed from vanilla", "aria-label":"Changed from vanilla"}, "Δ");
    if (!options.icon || !options.label) return null;
    return element("span", {class:"lex-record-source", role:"img",
      title:options.label, "aria-label":options.label}, options.icon);
  };
  const choiceField = (value, action, options={}) => element("span", {
    class:["lex-choice-field",options.fillValue?"lex-choice-field-fill":"",options.hoverAction?"lex-choice-field-hover":""].filter(Boolean).join(" ")}, value, action);
  const quantityChoice = (choice, quantity) => element("div", {class:"lex-quantity-choice"},
    choice, element("span", {class:"lex-quantity-mark","aria-hidden":"true"}, "×"), quantity);
  const iconValue = ({icon,label,toggle,control}) => element("div",{class:"lex-icon-value"},
    element("label",{class:"lex-icon-value-toggle",title:`${label}: toggle immunity`},toggle,element("span",{class:"lex-icon-value-art"},icon),
      element("span",{},label)),control);
  const textArea = (options = {}) => element("textarea", {rows:4, ...options,
    class:["lex-text-area", options.class || ""].filter(Boolean).join(" ")});

  // Buttons that insert canned snippets (a game's text <?tags?> and the
  // like) at the caret of a text box the caller owns. Groups keep a long
  // list short: [{label, tags}] with each tag {label, insert, title,
  // caretBack?}. The title tells what the tag does; caretBack parks the
  // caret that many characters back inside the insert (for an id the
  // reader must fill in). The box keeps its own input and change
  // handlers: both fire, so the edit commits like a typed one.
  const tagBar = ({groups = [], target, help = null} = {}) => {
    // A function target re-resolves per click against the live panel: a
    // commit rebuilds the detail, and an element held from the last render
    // would take the insert with it into the detached tree.
    const box = () => (typeof target === "function" ? target(bar) : target);
    const insert = tag => {
      const node = box();
      if (!node) return;
      const start = node.selectionStart ?? node.value.length;
      const end = node.selectionEnd ?? node.value.length;
      const snippet = String(tag.insert ?? "");
      node.value = node.value.slice(0, start) + snippet + node.value.slice(end);
      const caret = start + snippet.length - (Number(tag.caretBack) || 0);
      // Focusing selects the whole box a frame later; that would swallow
      // the caret this insert just placed, so the next tag click would
      // replace all the text. Borrowing the focus-restore flag skips it.
      node.lexRestoringFocus = true;
      node.focus();
      node.setSelectionRange(caret, caret);
      requestAnimationFrame(() => requestAnimationFrame(() => { delete node.lexRestoringFocus; }));
      node.dispatchEvent(new Event("input", {bubbles: true}));
      node.dispatchEvent(new Event("change", {bubbles: true}));
    };
    const folds = groups.map((group, index) => element("details",
      {class: "lex-tag-group", ...(index === 0 ? {open: true} : {})},
      element("summary", {class: "lex-tag-group-name"}, group.label),
      element("div", {class: "lex-tag-buttons"}, ...(group.tags || []).map(tag =>
        element("button", {type: "button", class: "lex-tag-button", title: tag.title || tag.insert,
          onclick: () => insert(tag)}, tag.label)))));
    const bar = element("div", {class: "lex-tag-bar"}, help, ...folds);
    return bar;
  };

  const stack = (...children) => {
    const options=children[0] && typeof children[0]==="object" && !(children[0] instanceof Node)
      ? children.shift() : {};
    return element("div", {...(options.attrs||{}),class:["lex-stack",options.fill===false?"lex-stack-natural":"",options.compact?"lex-stack-compact":"",options.className||""].filter(Boolean).join(" ")}, ...children);
  };

  // Text in a game's own bitmap font. The game measures its glyphs; each is
  // {width, quad} or {width, text} for a character the font lacks. A quad is
  // where the glyph sits in its slot and where it sits in the atlas, which the
  // stylesheet names as --lex-bitmap-atlas.
  const bitmapText = (options = {}) => options.canvas
    ? element("span", {class:"lex-bitmap-text", "aria-label":options.label}, options.canvas)
    : element("span", {
    class: "lex-bitmap-text",
    "aria-label": options.label,
    style: `--lex-bitmap-line-height:${options.lineHeight}px`,
  }, ...(options.glyphs || []).map(glyph => {
    const quad = glyph.quad;
    const mask = quad
      ? `${quad.atlasWidth}px ${quad.atlasHeight}px`
      : "";
    const at = quad ? `${-quad.u}px ${-quad.v}px` : "";
    return element("span", {class: "lex-bitmap-glyph-slot", style: `width:${glyph.width}px`},
      quad
        ? element("i", {class: "lex-bitmap-glyph", "aria-hidden": "true",
          style: `left:${quad.left}px;top:${quad.top}px;width:${quad.width}px;height:${quad.height}px;` +
            `-webkit-mask-size:${mask};mask-size:${mask};-webkit-mask-position:${at};mask-position:${at}`})
        : (glyph.text ?? ""));
  }));

  // A turnable model: a renderer draws its canvas into the stage, and the
  // message says what is happening until it has. A loading stage holds the
  // shared loading panel, like every other loading surface. The message
  // node is stage.lexMessage.
  const modelStage = (options = {}) => {
    const message = element("div", {class: "lex-model-stage-message"}, options.message ?? "");
    const stage = element("div", {class: ["lex-model-stage", options.className || ""].filter(Boolean).join(" ")}, message);
    stage.lexMessage = message;
    if (options.modes !== false) modelViewModes(stage);
    return stage;
  };

  // Corner buttons toggling how a 3D view is drawn: Regular (the renderer's
  // own lighting), Fullbright (every face at full color, no shading) and
  // Wireframe. modelStage mounts them; modelViewModes puts the same buttons
  // on any other host (the DS1 map and animation views). bindScene connects
  // the three.js scene the buttons retint, once the renderer has added every
  // mesh; clicks before that only move the pressed state. No three.js import
  // here: wireframe and emissive are plain material flags, so the helper only
  // walks the scene graph and every plugin's renderer gets the same modes.
  const modelViewModeIcon = mode => {
    const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
    for (const [key, value] of Object.entries({viewBox: "0 0 24 24", "aria-hidden": "true",
      fill: "none", stroke: "currentColor", "stroke-width": "2",
      "stroke-linecap": "round", "stroke-linejoin": "round"})) svg.setAttribute(key, value);
    const shape = (tag, attrs) => {
      const node = document.createElementNS(ns, tag);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      svg.append(node);
    };
    if (mode === "regular") {
      // A shaded sphere: half lit, half dark.
      shape("circle", {cx: "12", cy: "12", r: "7"});
      shape("path", {d: "M12 5a7 7 0 0 1 0 14z", fill: "currentColor", stroke: "none"});
    } else if (mode === "fullbright") {
      // A sun: every face lit as if noon.
      shape("circle", {cx: "12", cy: "12", r: "4", fill: "currentColor", stroke: "none"});
      shape("path", {d: "M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"});
    } else if (mode === "follow") {
      // Crossed arrows: the root carries the skeleton through space.
      shape("path", {d: "M12 3v18M3 12h18"});
      shape("path", {d: "M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"});
    } else if (mode === "skeleton") {
      // A bone chain: joints and the bones between them.
      shape("path", {d: "M12 5L6 19M12 5l6 14"});
      for (const [cx, cy] of [[12, 5], [6, 19], [18, 19]])
        shape("circle", {cx: String(cx), cy: String(cy), r: "2.4", fill: "currentColor", stroke: "none"});
    } else {
      // A grid square: edges only, no faces.
      shape("rect", {x: "4", y: "4", width: "16", height: "16"});
      shape("path", {d: "M4 12h16M12 4v16"});
    }
    return svg;
  };
  const MODEL_VIEW_MODES = [
    {id: "regular", label: "Regular", title: "Regular: the renderer's own lighting"},
    {id: "fullbright", label: "Fullbright", title: "Fullbright: every face at full color, no shading"},
    {id: "wireframe", label: "Wireframe", title: "Wireframe: edges only, no faces"},
  ];
  // What each material looked like before any mode touched it, so Regular
  // restores exactly that. Keyed weakly: a disposed scene takes its entries.
  const modelViewModeStash = new WeakMap();
  const modelViewModeLightStash = new WeakMap();
  const applyModelViewMode = (scene, mode) => {
    if (!scene || typeof scene.traverse !== "function") return;
    const bright = mode === "fullbright";
    scene.traverse(obj => {
      if (!obj || typeof obj !== "object") return;
      // Fullbright is unlit: the lamps go out while it lasts, so a
      // shaded material shows only its own glow. Regular and
      // Wireframe put the rig back exactly as it was.
      if (obj.isLight) {
        if (!modelViewModeLightStash.has(obj))
          modelViewModeLightStash.set(obj, {visible: obj.visible});
        obj.visible = bright ? false : modelViewModeLightStash.get(obj).visible;
      }
      const mats = Array.isArray(obj.material) ? obj.material : obj.material ? [obj.material] : [];
      for (const mat of mats) {
        if (!mat || typeof mat !== "object") continue;
        if (!modelViewModeStash.has(mat)) {
          const saved = {
            emissive: mat.emissive && typeof mat.emissive.getHex === "function" ? mat.emissive.getHex() : null,
            emissiveMap: mat.emissiveMap || null,
            emissiveIntensity: mat.emissiveIntensity ?? 1,
            wireframe: !!mat.wireframe,
          };
          // Only what the material actually carries, so lighter
          // fakes and helper materials pass through untouched.
          for (const key of ["lightMap", "aoMap", "vertexColors"])
            if (key in mat) saved[key] = mat[key];
          modelViewModeStash.set(mat, saved);
        }
        const saved = modelViewModeStash.get(mat);
        if ("wireframe" in mat) mat.wireframe = mode === "wireframe" ? true : saved.wireframe;
        // Baked and darkened surfaces join the glow: no light or
        // occlusion map and no darkening vertex colours, so an
        // unlit material shows its own map at full brightness.
        if ("lightMap" in saved) mat.lightMap = bright ? null : saved.lightMap;
        if ("aoMap" in saved) mat.aoMap = bright ? null : saved.aoMap;
        // Lines and points keep their vertex colors: on a helper line the
        // vertex colors are the colors, not a darkening tint, and the lines
        // are unlit already, so Fullbright gains nothing by stripping them.
        if ("vertexColors" in saved && !mat.isLineBasicMaterial && !mat.isLineDashedMaterial && !mat.isPointsMaterial)
          mat.vertexColors = bright ? false : saved.vertexColors;
        if (mat.emissive && typeof mat.emissive.setHex === "function") {
          // The material glows in its own colors, textured or flat,
          // and with the lamps out that glow is the whole picture.
          // Lines and points have no emissive and are unlit already,
          // so they are left alone.
          if (bright) {
            if (mat.map) { mat.emissive.setHex(0xffffff); mat.emissiveMap = mat.map; }
            else if (mat.color && typeof mat.color.getHex === "function") {
              mat.emissive.setHex(mat.color.getHex()); mat.emissiveMap = null;
            } else mat.emissive.setHex(0xffffff);
            if ("emissiveIntensity" in mat) mat.emissiveIntensity = 1;
          } else {
            mat.emissive.setHex(saved.emissive ?? 0x000000);
            mat.emissiveMap = saved.emissiveMap;
            if ("emissiveIntensity" in mat) mat.emissiveIntensity = saved.emissiveIntensity;
          }
        }
        // Swapping maps changes the compiled shader.
        mat.needsUpdate = true;
      }
    });
  };
  const modelViewModes = host => {
    // Remounting clears the host (animationViewer.stop replaces its
    // children), which detaches the bar while the cached controller
    // survives. Re-attach it so the buttons - and the mode - persist.
    if (host.lexViewModes) {
      const cached = host.lexViewModes;
      if (cached.bar && !cached.bar.isConnected) host.append(cached.bar);
      return cached;
    }
    let mode = "regular", scene = null;
    const buttons = new Map();
    const paint = () => {
      for (const [id, button] of buttons) {
        const on = id === mode;
        button.classList.toggle("active", on);
        button.setAttribute("aria-pressed", String(on));
      }
    };
    const setMode = next => {
      if (!MODEL_VIEW_MODES.some(entry => entry.id === next)) return;
      mode = next;
      paint();
      if (scene) applyModelViewMode(scene, mode);
    };
    const bar = element("div", {class: "lex-model-view-modes", role: "group", "aria-label": "View mode"},
      ...MODEL_VIEW_MODES.map(entry => {
        const button = element("button", {type: "button", class: "lex-model-view-mode",
          "data-view-mode": entry.id, title: entry.title, "aria-label": entry.label,
          "aria-pressed": String(entry.id === mode),
          onclick: () => setMode(entry.id),
        }, modelViewModeIcon(entry.id));
        buttons.set(entry.id, button);
        return button;
      }));
    paint();
    host.append(bar);
    const controller = {
      bar,
      mode: () => mode,
      setMode,
      bindScene: next => { scene = next || null; if (scene) applyModelViewMode(scene, mode); },
    };
    host.lexViewModes = controller;
    host.lexSetViewMode = setMode;
    host.lexBindScene = controller.bindScene;
    return controller;
  };

  // What fills a detail heading's icon box: a picture, a small stage, or a
  // line saying why there is neither yet. The line is slot.lexMessage.
  const iconSlot = (options = {}) => {
    const message = options.content ? null
      : element("div", {class: "lex-icon-slot-message"}, options.message ?? "");
    const slot = element("div", {class: ["lex-icon-slot", options.shape === 'square' ? 'lex-icon-slot-square' : '', options.className || ""].filter(Boolean).join(" ")},
      options.content || message);
    slot.lexMessage = message;
    return slot;
  };

  // Pictures side by side, each over its caption: [{media, caption}].
      // A grid of figures: media with a caption. A grid may put the caption
      // above the media and add a footer under it, which is how a battle
      // position names the enemy over its box and gives the level below.
      const figureGrid = (items = [], options = {}) => element("div", {
        class: ["lex-figure-grid", options.captionAbove ? "lex-figure-caption-above" : ""]
          .filter(Boolean).join(" "),
      }, ...items.map(item => {
        const caption = item.caption == null ? null : element("figcaption", {}, item.caption);
        return element("figure", {...(item.attrs || {})},
          options.captionAbove ? caption : null,
          item.media ?? null,
          options.captionAbove ? null : caption,
          item.footer == null ? null : element("div", {class: "lex-figure-footer"}, item.footer));
      }));

  // The large view behind a map's magnifier: the caller's own map options drawn
  // bigger, with a crosshair and a live readout. A placement runs the caller's
  // handler and then redraws this view, so the marker shows where the record is
  // now instead of where it was when the panel was drawn.
  const mapMagnifier = (options = {}) => {
    const opener=document.activeElement;
    const backdrop=element("div",{class:"lex-dialog-backdrop lex-map-magnifier-backdrop","data-lex-history-control":true});
    const {bar,context,prompt:note,cancel:done}=selectionBar({prompt:options.label||"Map",
      contextLabel:"Return to the map record",closeLabel:"Close large map"});
    const body=element("div",{class:"lex-map-magnifier-body"});
    const mapHost=element("div",{class:"lex-map-magnifier-map"});
    const detailsHost=element("div",{class:"lex-map-magnifier-details"});
    const close=()=>{document.removeEventListener("keydown",onKey,true);window.removeEventListener("resize",fit);observer?.disconnect();backdrop.remove();if(opener?.isConnected)opener.focus();};
    const onKey=event=>{if(event.key==="Escape"){event.preventDefault();event.stopImmediatePropagation();close();}};
    const draw=()=>{
      const spec=options.magnify()||{},place=spec.place;
      // The placing hint only where a click places something.
      note.textContent=spec.note||(place?"Point at the map to read the value, then click to place the point.":options.label||"Map");
      mapHost.replaceChildren(imageMap({...spec,fill:true,magnify:null,crosshair:true,
        place:place?point=>{place(point);draw();}:undefined}));
      if(options.details)detailsHost.replaceChildren(options.details({refresh:draw}));
    };
    body.append(options.details?panelLayout([mapHost,detailsHost],"",{
      defaultSizes:[3,1],minSizes:options.minSizes||[480,280],stackBelowMinimum:true,
    }):mapHost);
    done.onclick=close;
    context.onclick=close;
    context.replaceChildren(element("span",{class:"lex-ui-symbol","aria-hidden":"true"},"↩"));
    backdrop.append(element("section",{class:"lex-dialog lex-map-magnifier-dialog",role:"dialog","aria-modal":"true",
      "aria-label":`${options.label||"Map"}, full size`},
      bar,body));
    const menu=document.querySelector(".lex-shell-command-row");
    const fit=()=>backdrop.style.top=`${menu?.getBoundingClientRect().bottom||0}px`;
    const observer=menu?new ResizeObserver(fit):null;
    observer?.observe(menu);
    window.addEventListener("resize",fit);
    document.body.append(backdrop);
    fit();
    document.addEventListener("keydown",onKey,true);
    draw();
    done.focus();
    return backdrop;
  };

  // Map coordinates are fractions of the image, independent of UI zoom.
  const imageMap = (options = {}) => {
    // A map with a corner readout answers "what is under the pointer" there,
    // so its cells and markers carry no hover tooltip on top of it (Lexer:
    // "hovering in the world map shouldn't bring up some weird info thing.
    // that's what the coords in the bottom left are for").
    const tooltip=text=>typeof options.readout==="function"||options.crosshair?null:text;
    const stage=element("div",{class:"lex-image-map-stage",style:`aspect-ratio:${Number(options.ratio)||4/3};--lex-map-columns:${Number(options.columns)||1};--lex-map-rows:${Number(options.rows)||1}`},
      options.media || (options.image?element("img",{src:options.image,alt:options.label||"Map",draggable:false}):null));
    if(options.cells?.length)stage.append(element("div",{class:"lex-image-map-cells"},...options.cells.map(cell=>
      element("button",{type:"button",class:[cell.selected?"selected":"",cell.fill?"lex-map-cell-filled":""].filter(Boolean).join(" "),title:tooltip(cell.title||cell.label),
        style:[Number.isInteger(cell.column)&&Number.isInteger(cell.row)
          ?`grid-column:${cell.column+1};grid-row:${cell.row+1}`:"",cell.fill?`--lex-map-cell-fill:${cell.fill}`:""].filter(Boolean).join(";")||null,
        "aria-label":cell.label,"aria-pressed":!!cell.selected,onclick:()=>options.select?.(cell.id)}))));
    for(const point of options.points||[])stage.append(element("button",{type:"button",class:`lex-image-map-point${point.selected?" selected":""}${point.className?" "+point.className:""}`,
      style:`left:${point.x*100}%;top:${point.y*100}%`,title:tooltip(point.label),"aria-label":point.label,
      onclick:event=>{event.stopPropagation();point.activate?.();}}));
    if(options.place)stage.addEventListener("click",event=>{
      if(event.target.closest("button"))return;
      const box=stage.getBoundingClientRect();
      options.place({x:Math.max(0,Math.min(1,(event.clientX-box.left)/box.width)),y:Math.max(0,Math.min(1,(event.clientY-box.top)/box.height))});
    });
    // What the pointer is over, in the map's own corner: the reader is looking at
    // the map, so the answer belongs beside it rather than in another panel. The
    // large view keeps that line and adds a crosshair, because the reader who
    // opens it is placing a point and has to see which pixel they are on.
    let readout=null;
    if(typeof options.readout==="function"||options.crosshair){
      const columns=Math.max(1,Number(options.columns)||1),rows=Math.max(1,Number(options.rows)||1);
      readout=element("div",{class:"lex-image-map-readout","aria-live":"polite",hidden:!options.crosshair});
      const crosshair=options.crosshair?element("div",{class:"lex-map-crosshair","aria-hidden":"true"},element("span",{})):null;
      if(crosshair)stage.append(crosshair);
      stage.addEventListener("pointermove",event=>{
        const box=stage.getBoundingClientRect();
        if(!box.width||!box.height)return;
        const x=Math.max(0,Math.min(1,(event.clientX-box.left)/box.width));
        const y=Math.max(0,Math.min(1,(event.clientY-box.top)/box.height));
        if(crosshair){crosshair.style.left=`${x*100}%`;crosshair.style.top=`${y*100}%`;crosshair.hidden=false;}
        const text=typeof options.readout==="function"
          ? options.readout({x,y,column:Math.min(columns-1,Math.floor(x*columns)),
              row:Math.min(rows-1,Math.floor(y*rows))})
          : `${Math.round(x*100)}%, ${Math.round(y*100)}%`;
        readout.textContent=text==null?"":String(text);
        readout.hidden=!readout.textContent;});
      stage.addEventListener("pointerleave",()=>{readout.hidden=!options.crosshair;if(crosshair)crosshair.hidden=true;});
    }
    // A region, so its label is announced; a bare div's aria-label is not.
    const root=element("div",{class:options.fill===false?"lex-image-map lex-image-map-natural":"lex-image-map",role:"region","aria-label":options.label||"Map"},stage);
    root.style.setProperty("--lex-map-ratio", String(Number(options.ratio)||4/3));
    // The readout sits in the map's frame, not on the stage: a zoomed or
    // panned stage carried it out of view (Lexer: "they disappear when you
    // zoom in").
    if(readout)root.append(readout);
    // Buttons that change how the map is drawn, such as a lens, sit in the
    // frame's top-left corner; the magnifier keeps the top-right one.
    if(options.tools?.length)root.append(element("div",{class:"lex-image-map-tools"},...options.tools));
    const image=stage.querySelector('img');
    if(image&&!options.ratio){const fit=()=>{if(!image.naturalWidth||!image.naturalHeight)return;const ratio=image.naturalWidth/image.naturalHeight;root.style.setProperty('--lex-map-ratio',String(ratio));stage.style.aspectRatio=String(ratio)};image.addEventListener('load',fit);fit();}
    root.lexStage=stage;
    const sideControls=[];
    root.lexSideControls = ({left,right}={}) => {
      sideControls.splice(0).forEach(node=>node.remove());
      for(const [side,content] of [['left',left],['right',right]]){
        if(!content)continue;
        const controls=element('div',{class:`lex-image-map-side-controls ${side}`},content);
        sideControls.push(controls);root.append(controls);
      }
    };
    // A map in a panel is small, and a stored coordinate is not. The magnifier
    // opens the same map at the size of the window, with the same markers and the
    // same click, so a point is placed against the art. `magnify` returns that
    // view's options from the caller's own state, so each placement redraws the
    // markers where the record is now.
    if(typeof options.magnify==="function")
      root.append(element("button",{type:"button",class:"lex-image-map-magnify",
        title:"Open the large map","aria-label":`Open the large map: ${options.label||"map"}`,
        onclick:event=>{event.stopPropagation();mapMagnifier(options);}},magnifyIcon()));
    // A small preview map is a way into the large one: a click anywhere on it
    // opens the large map, and the magnifier shows over the whole picture on
    // hover, as a model thumbnail's does (Lexer: "clicking it ANYWHERE should
    // enter the bigger version").
    if(typeof options.magnify==="function"&&options.magnifyOnClick){
      root.classList.add("lex-image-map-click-magnify");
      root.addEventListener("click",event=>{event.preventDefault();event.stopPropagation();mapMagnifier(options);},true);
    }
    return root;
  };

  const statCard = (options = {}) => element("div", {class:"lex-stat-card"},
    // A card without art says so with the shared mark behind its ranks.
    options.image ? element("img", {src:options.image,alt:options.label || "",
      onerror:event=>{event.target.hidden=true;}})
      : Object.assign(noImage(options.label ? `No art for ${options.label}` : "No card art"), {className:"lex-no-image lex-no-image-standin"}),
    element("div", {class:"lex-stat-card-ranks"}, ...(options.ranks || [])),
    // A game that names the card's type in a word rather than one glyph asks
    // for a corner wide enough to hold the word.
    options.corner ? element("div", {class:["lex-stat-card-corner", options.cornerWord ? "lex-stat-card-corner-word" : ""]
      .filter(Boolean).join(" ")}, options.corner) : null,
    options.footer ? element("div", {class:"lex-stat-card-footer"}, options.footer) : null);

  const choicePopover = (options = {}) => {
    const buttons=(options.choices || []).map(choice =>
      element("button", {type:"button","aria-label":choice.label,onclick:()=>{popup.hidePopover();options.select?.(choice.value);}},
        choice.icon || null, element("span",{},choice.label)));
    const popup = element("div", {class:"lex-choice-popover",popover:"auto",role:"group",
      "aria-label":options.label || "Choose a value"});
    // A long choice list filters as the reader types, so a 4,000-effect
    // picker stays usable where a dropdown would freeze the pane.
    if (options.search) {
      const box = element("input", {type:"search", class:"lex-choice-popover-search",
        placeholder:typeof options.search === "string" ? options.search : "Search",
        "aria-label":typeof options.search === "string" ? options.search : "Search choices"});
      box.addEventListener("input", () => {
        const needle = box.value.trim().toLocaleLowerCase();
        buttons.forEach((button, index) => {
          const label = String((options.choices || [])[index]?.label || "");
          button.hidden = !!needle && !label.toLocaleLowerCase().includes(needle);
        });
      });
      popup.append(box, ...buttons);
    } else popup.append(...buttons);
    popup.addEventListener("keydown", event => {
      if (!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const live=buttons.filter(button=>!button.hidden), step=["ArrowUp","ArrowLeft"].includes(event.key)?-1:1;
      live[(live.indexOf(document.activeElement)+step+live.length)%live.length]?.focus();
    });
    popup.openFor = anchor => {
      if (!popup.isConnected) document.body.append(popup);
      popup.showPopover();
      const boundary=options.boundary?.(anchor);
      const bounds=boundary?.getBoundingClientRect() || {left:0,top:0,right:innerWidth,bottom:innerHeight,width:innerWidth,height:innerHeight};
      if(boundary){popup.style.maxWidth=`${bounds.width-8}px`;popup.style.maxHeight=`${bounds.height-8}px`;}
      const at=anchor.getBoundingClientRect(),box=popup.getBoundingClientRect();
      popup.style.left=`${Math.max(bounds.left+4,Math.min(at.right-box.width,bounds.right-box.width-4))}px`;
      popup.style.top=`${Math.max(bounds.top+4,Math.min(at.bottom+4,bounds.bottom-box.height-4))}px`;
      if(boundary){
        const leave=event=>{if(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom)popup.hidePopover();};
        document.addEventListener("pointermove",leave);
        const cleanup=event=>{if(event.newState==="closed"){
          document.removeEventListener("pointermove",leave);popup.removeEventListener("toggle",cleanup);
        }};
        popup.addEventListener("toggle",cleanup);
      }
      (popup.querySelector(".lex-choice-popover-search") || popup.querySelector("button"))?.focus();
    };
    popup.addEventListener("toggle",event=>{if(event.newState==="closed")popup.remove();});
    return popup;
  };

  // Records joined by arrows on a stage the caller has laid out. Each node is
  // {id, x, y, label, sub, missing}, with (x, y) its centre; each edge runs
  // from the top of `from` up to the bottom of `to`, so the graph reads
  // bottom-up. Pressing a node marks it and calls select(node).
  const TREE_NODE = {width: 170, height: 56};
  const treeGraph = (options = {}) => {
    const {width = 0, height = 0, nodes = [], edges = []} = options;
    const byId = new Map(nodes.map(node => [node.id, node]));
    const half = TREE_NODE.height / 2;
    const stage = element("div", {class: "lex-tree-graph-stage", style: `width:${width}px;height:${height}px`});
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("aria-hidden", "true");
    for (const edge of edges) {
      const from = byId.get(edge.from), to = byId.get(edge.to);
      if (!from || !to) continue;
      const top = from.y - half, bottom = to.y + half, middle = (top + bottom) / 2;
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("d", `M${from.x},${top} V${middle} H${to.x} V${bottom} m-5,7 l5,-7 l5,7`);
      svg.append(path);
    }
    stage.append(svg);
    for (const node of nodes) {
      stage.append(element("button", {
        type: "button",
        class: ["lex-tree-graph-node", node.missing ? "missing" : ""].filter(Boolean).join(" "),
        style: `left:${node.x - TREE_NODE.width / 2}px;top:${node.y - half}px`,
        "data-node": node.id,
        "aria-pressed": String(node.id === options.selected),
        onclick: () => {
          stage.querySelectorAll(":scope > .lex-tree-graph-node").forEach(button =>
            button.setAttribute("aria-pressed", String(button.dataset.node === node.id)));
          options.select?.(node);
        },
      }, element("strong", {}, node.label ?? node.id), node.sub ? element("small", {}, node.sub) : null));
    }
    return element("div", {class: "lex-tree-graph", "aria-label": options.label || null}, options.note || null, stage);
  };

  // An expression or a source line, edited as text.
  const codeField = (attrs = {}) => {
    const {class: className = "", ...rest} = attrs;
    return element("textarea", {...rest, spellcheck: "false",
      class: ["lex-code-field", className].filter(Boolean).join(" ")});
  };

  // Prose in a section: a manual page, an explanation. Its line breaks are
  // the author's.
  const loadingPanel = (options = {}) => element("div", {
    class: ["lex-panel-loading", options.className || ""].filter(Boolean).join(" "),
    role: "status", "aria-label": options.label || "Loading", "aria-busy": "true",
  }, element("span", {class:"lex-plugin-loading-pulse", "aria-hidden":"true"}));
  // A status bar's loading state: the standard pulse beside its label,
  // for bars whose text later changes to results or errors. Callers show
  // it with status.replaceChildren(loadingStatus("Loading map")) and go
  // back to plain text once loading finishes.
  const loadingStatus = (label = "Loading") => element("span", {
    class: "lex-loading-status", role: "status", "aria-busy": "true",
  }, element("span", {class: "lex-plugin-loading-pulse", "aria-hidden": "true"}),
  element("span", {class: "lex-loading-status-label"}, label));
  const detailText = text => element("p", {class: "lex-detail-text"}, text);

  // A word or two that classifies a record - Project or Vanilla - in a
  // heading's action slot. A tone colours it.
  const badge = (text, options = {}) => element("span", {
    title:options.title,
    class: ["lex-badge", options.tone ? `lex-tone-${options.tone}` : ""].filter(Boolean).join(" "),
  }, text);

  // A log's text as it was written.
  const logView = text => element("pre", {class: "lex-log"}, text);

  const detailNote = (text, options = {}) => element("p", {
    class: ["lex-detail-note", options.className || ""].filter(Boolean).join(" "),
  }, text);

  const anchorDetailPin = (pin, control, input, outward = false) => {
    if (!(pin instanceof Element) || !(control instanceof Element) || !(input instanceof Element)) return;
    const position = () => {
      if (!pin.isConnected || !control.isConnected || !input.isConnected) return;
      const owner = control.getBoundingClientRect();
      const target = input.getBoundingClientRect();
      const icon = pin.getBoundingClientRect();
      if (!owner.width || !target.height || !icon.width) return;
      const checkbox = input.matches('input[type="checkbox"]');
      const wideBoolean = checkbox && document.documentElement.dataset.lexBooleanStyle !== "arrow";
      if (checkbox && !wideBoolean) {
        // Keep the whole icon inside the row, above the leader near the box.
        // Rectangles include UI zoom; positioned offsets use unscaled pixels.
        const scale = owner.width / control.offsetWidth || 1;
        pin.style.setProperty("left", `${(target.left - owner.left - icon.width - 6 * scale) / scale}px`, "important");
        pin.style.setProperty("top", `${(target.top - owner.top - icon.height / 2) / scale}px`, "important");
        pin.style.setProperty("right", "auto", "important");
        return;
      }
      const inset = Math.min(3, target.height * .1);
      if (wideBoolean) {
        // Wide boolean boxes keep the pin the way every other value box
        // does: the whole icon inside the box's top-right corner. Aiming
        // the drawn tip at the corner hung the mark half past the box
        // edge, where the panel body sliced it off.
        const boolScale = owner.width / control.offsetWidth || 1;
        pin.style.setProperty("left", `${(target.right - owner.left - inset - icon.width) / boolScale}px`, "important");
        pin.style.setProperty("top", `${(target.top - owner.top + inset) / boolScale}px`, "important");
        pin.style.setProperty("right", "auto", "important");
        return;
      }
      // The Boxicons pin tip is at 3.71,21.71 in its 24-by-24 view box.
      const tipX = icon.width * 3.71 / 24;
      const tipY = icon.height * 21.71 / 24;
      // The drawn pin leans up and to the right of that tip. A tip set on the
      // value box's own right edge therefore hung the whole mark past the edge
      // of the row, and the panel body - which clips its overflow - cut the
      // pin's right side off. The tip is nudged left so the mark lands inside
      // the row, and a little further down.
      //
      // The nudge is half the mark's own overhang, not all of it. Moving the
      // tip by the whole overhang put the pin's body in the middle of the
      // value box, which Lexer saw at once: "pins too far left now". This
      // amount leaves the mark at the box's corner and inside the row.
      const overhangX = Math.min(icon.width - tipX, 8);
      const dropY = Math.min(4, target.height * .2);
      const outside = outward && !wideBoolean;
      const targetX = target.right + (outside ? inset : -inset - overhangX);
      const targetY = target.top + (outside ? -inset : inset + dropY);
      const scale = owner.width / control.offsetWidth || 1;
      // The mark belongs at the box's corner and inside the row. Past the
      // row it reads as clipped, and its pixels count as overflow: a few
      // of them vetoed the pager's split and left a scrollbar beside it.
      // A part's pin stays in its own box; a field's may use the row.
      const row = control.matches(".lex-detail-part-control") ? null
        : control.closest(".lex-detail-field");
      const edge = row ? Math.min(owner.right, row.getBoundingClientRect().right) : owner.right;
      const left = Math.max(2 - tipX, Math.min((targetX - owner.left - tipX) / scale,
        (edge - owner.left - icon.width) / scale - 1));
      pin.style.setProperty("left", `${left}px`, "important");
      pin.style.setProperty("top", `${(targetY - owner.top - tipY) / scale}px`, "important");
      pin.style.setProperty("right", "auto", "important");
    };
    requestAnimationFrame(position);
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(position);
      observer.observe(control);
      observer.observe(input);
    }
  };

  // A row can hold more than one control: three numbers, or a number and a
  // switch. Rather than a component per combination - multiNumberRow, toggleRow,
  // and whatever the next shape would have been - a row takes a list of parts.
  // One row holding several properties of any kind - numbers, choices,
  // switches, bare controls - side by side. Named parts wrap to a new row
  // before their controls become too narrow. Bare controls keep equal lanes.
  // toggleRow and multiNumberRow use this row with their parts pre-made.
  const detailPart = (part, options = {}) => {
    if (part instanceof Element && part.matches(".lex-toggle")) return part;
    const control = part instanceof Element ? part : part.control;
    const caption = element("label", {class: "lex-detail-part-label lex-multi-number-label"},
      part instanceof Element ? "" : (part.label ?? ""),
      !(part instanceof Element) && part.help ? infoHelp(part.help) : null);
    const item = element("div", {
      class: "lex-detail-part lex-multi-number-item",
      title: (part instanceof Element ? "" : part.title) || undefined,
    }, caption, element("span", {class: "lex-detail-part-control lex-multi-number-control"}, control));
    if (part.pin) {
      item.classList.add('lex-pinnable-property');
      const owner=item.querySelector('.lex-detail-part-control');
      owner.append(part.pin);
      anchorDetailPin(part.pin,owner,owner.querySelector('input,select,textarea'));
    }
    // The part is a plain box, not a label: as a <label> it adopted its first
    // labelable descendant, which became the copy button once there was one.
    const field = item.querySelector("input,select,textarea");
    if (field) {
      if (!field.id) field.id = `lex-part-${Math.random().toString(36).slice(2, 9)}`;
      caption.setAttribute("for", field.id);
    }
    const input = options.copy ? item.querySelector('input:not([type="checkbox"]),select,textarea') : null;
    item.prepend(input
      ? copyValueButton(() => input.tagName === "SELECT"
        ? (input.selectedOptions[0]?.textContent || input.value)
        : input.value, `Copy ${typeof part.label === "string" ? part.label : "this value"}`)
      : element("span", {class: "lex-detail-part-spare", "aria-hidden": "true"}));
    return item;
  };
  const detailParts = (parts, options = {}) => {
    const list = (parts || []).filter(Boolean);
    const switches = list.length > 0 && list.every(part => part instanceof Element && part.matches(".lex-toggle"));
    const columns = Math.max(1, Number(options.columns) || Math.min(3, list.length) || 1);
    return element("div", {
      class: ["lex-detail-parts", switches ? "lex-detail-parts-switches" : "", !switches && list.every(part=>part instanceof Element) ? "lex-detail-parts-bare" : "", options.stacked ? "lex-detail-parts-stacked" : "", options.nowrap ? "lex-detail-parts-nowrap" : "", options.fixedFirst ? "lex-detail-parts-fixed-first" : "", options.className || ""]
        .filter(Boolean).join(" "),
      style: `--lex-part-columns:${columns};--lex-multi-number-columns:${columns}`,
      "data-lex-copy-parts": options.copy ? "" : null,
      role: options.role, "aria-label": options.label,
    }, ...list.map(part => detailPart(part, options)));
  };

  const controlGroup = (parts, options = {}) => detailParts(parts, options);

  // Small geometric glyphs for damage, status and weakness kinds: a
  // label about fire carries a flame, one about bleeding a drop. Game art
  // stays with its own pipeline (FF8 renders its menu icons); these are the
  // shared fallback wherever a label names a kind. Unknown kinds draw
  // nothing rather than guessing.
  const TYPE_GLYPHS = {
    physical: ['#cfcfcf', '<rect x="7" y="1" width="2" height="9"/><path d="M7 10h2l-1 3z"/><rect x="4.5" y="10.5" width="7" height="1.6"/><rect x="7.4" y="12" width="1.2" height="3"/>'],
    magic: ['#5aa9ff', '<path d="M8 1l1.6 5.4L15 8l-5.4 1.6L8 15l-1.6-5.4L1 8l5.4-1.6z"/>'],
    fire: ['#ff7a3c', '<path d="M8 1c2 3 4 5 4 8.5a4 4.5 0 1 1-8 0C4 7 5.5 5.5 6.5 4c.3 1.5 1 2 1.5 2.2C7.6 4.5 7.8 2.5 8 1z"/>'],
    lightning: ['#ffd94d', '<path d="M9 1l-5 8h3l-1 6 6-8.5H8.8z"/>'],
    slash: ['#d8d8d8', '<path d="M2 14L11 2h2L4 14z"/>'],
    strike: ['#b09a7a', '<rect x="4.5" y="1.5" width="7" height="5" rx="1"/><rect x="7.2" y="6" width="1.6" height="9"/>'],
    thrust: ['#d8d8d8', '<path d="M8 1l2.5 12h-5z"/>'],
    poison: ['#b06ac9', '<path d="M8 2s-3.5 5-3.5 8a3.5 3.5 0 0 0 7 0C11.5 7 8 2 8 2z"/>'],
    toxic: ['#8a6a2a', '<path d="M8 2s-3.5 5-3.5 8a3.5 3.5 0 0 0 7 0C11.5 7 8 2 8 2z"/>'],
    bleed: ['#d43a3a', '<path d="M8 2s-3.5 5-3.5 8a3.5 3.5 0 0 0 7 0C11.5 7 8 2 8 2z"/>'],
    curse: ['#9aa3ad', '<circle cx="8" cy="8" r="5" fill="none" stroke-width="2"/>'],
    divine: ['#e8c67a', '<ellipse cx="8" cy="8" rx="5" ry="2.4" fill="none" stroke-width="1.8"/>'],
    occult: ['#7a5ac9', '<path d="M11 2a6.5 6.5 0 1 0 0 12 8 8 0 1 1 0-12z"/>'],
    abyssal: ['#a02622', '<circle cx="8" cy="8" r="5" fill="#000" stroke-width="1.5"/>'],
    str: ['#7fd08a', '<rect x="3" y="3" width="10" height="10" rx="1"/>'],
    dex: ['#6ad0c9', '<path d="M4 2l6 6-6 6V2z"/><path d="M9 2l6 6-6 6V2z"/>'],
    int: ['#b48ae0', '<circle cx="8" cy="8" r="5" fill="none" stroke-width="2"/><circle cx="8" cy="8" r="1.6"/>'],
    fth: ['#e08aa0', '<path d="M8 1l5 7-5 7-5-7z"/>'],
    vit: ['#e05a5a', '<path d="M8 13.5 C5.5 11.5 3.5 9.4 3.5 7 C3.5 5.3 4.8 4.2 6.3 4.2 C7 4.2 7.7 4.5 8 5.1 C8.3 4.5 9 4.2 9.7 4.2 C11.2 4.2 12.5 5.3 12.5 7 C12.5 9.4 10.5 11.5 8 13.5 z"/>'],
    wil: ['#5aa9e0', '<path d="M3 3.5h10v2H3zM3 7h10v2H3zM3 10.5h10v2H3z"/>'],
    end: ['#a3c14a', '<path d="M9 1.5 L4.5 9 H7.5 L7 14.5 L11.5 7 H8.5 Z"/>'],
    luc: ['#c9c9c9', '<circle cx="8" cy="8" r="5" fill="none" stroke-width="2.5"/>'],
    physicalDef: ['#cfcfcf', '<path d="M8 1l5 2v4.5c0 3.4-2.4 5.4-5 6.8-2.6-1.4-5-3.4-5-6.8V3z"/>'],
    magicDef: ['#5aa9ff', '<path d="M8 1l5 2v4.5c0 3.4-2.4 5.4-5 6.8-2.6-1.4-5-3.4-5-6.8V3z"/>'],
    fireDef: ['#ff7a3c', '<path d="M8 1l5 2v4.5c0 3.4-2.4 5.4-5 6.8-2.6-1.4-5-3.4-5-6.8V3z"/>'],
    lightningDef: ['#ffd94d', '<path d="M8 1l5 2v4.5c0 3.4-2.4 5.4-5 6.8-2.6-1.4-5-3.4-5-6.8V3z"/>'],
    faith: ['#e08aa0', '<path d="M8 1l5 7-5 7-5-7z"/>'],
    weight: ['#9aa3ad', '<path d="M8 1a3 3 0 0 1 3 3v1H5V4a3 3 0 0 1 3-3z"/><circle cx="8" cy="10.5" r="4"/>'],
    durability: ['#c9c9c9', '<rect x="2.5" y="2" width="11" height="4" rx="1"/><rect x="7" y="6" width="2" height="8"/>'],
    hp: ['#e05a5a', '<rect x="2" y="6" width="12" height="4.5" rx="2"/>'],
    mp: ['#5aa9ff', '<rect x="2" y="6" width="12" height="4.5" rx="2"/>'],
    stamina: ['#7fd08a', '<rect x="2" y="6" width="12" height="4.5" rx="2"/>'],
    humanity: ['#f0f0f0', '<circle cx="8" cy="8" r="3.5"/>'],
    stability: ['#8fa3b8', '<path d="M8 1l5 2v4.5c0 3.4-2.4 5.4-5 6.8-2.6-1.4-5-3.4-5-6.8V3z" fill="none" stroke-width="1.8"/><path d="M5.5 8l2 2 3.5-4" fill="none" stroke-width="1.8"/>'],
    souls: ['#ffe9a8', '<path d="M8 2.5l1.1 4.4 4.4 1.1-4.4 1.1L8 13.5l-1.1-4.4-4.4-1.1 4.4-1.1z"/>'],
    poise: ['#c9a86a', '<rect x="2" y="5" width="12" height="2.2" rx="1"/><rect x="2" y="9" width="12" height="2.2" rx="1"/>'],
    slot: ['#e8c67a', '<rect x="3" y="3" width="10" height="10" rx="2" fill="none" stroke-width="2"/>'],
    att: ['#8a9ae0', '<rect x="4" y="2" width="8" height="12" rx="1.5" fill="none" stroke-width="1.6"/><path d="M6 5.5h4v1.4H6zM6 8h4v1.4H6zM6 10.5h4v1.4H6z"/>'],
    res: ['#8a9a5b', '<path d="M8 2l4.5 2.6v5.2L8 12.4l-4.5-2.6V4.6z" fill="none" stroke-width="1.8"/>'],
    soulLv: ['#ffe9a8', '<path d="M3.5 10.5L8 6l4.5 4.5" fill="none" stroke-width="2.2"/>'],
    critical: ['#e05a5a', '<path d="M2 14L11 2h2L4 14z"/><path d="M14 14L5 2H3l9 12z"/>'],
    gems: ['#6ad0ff', '<path d="M8 1.5L14 6l-6 8.5L2 6z" fill="none" stroke-width="1.6"/><path d="M2 6h12M8 1.5L5.8 6 8 14.5 10.2 6 8 1.5" fill="none" stroke-width="1"/>'],
  };
  const typeGlyph = kind => {
    // Keys match the names plugins send, camelCase included; the
    // lowercase probe keeps older all-lowercase kinds resolving.
    const name = String(kind || '');
    const found = TYPE_GLYPHS[name] || TYPE_GLYPHS[name.toLocaleLowerCase()];
    if (!found) return null;
    const [color, shapes] = found;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('fill', color);
    svg.setAttribute('stroke', color);
    svg.innerHTML = shapes;
    return element('span', {class: 'lex-type-glyph', 'aria-hidden': 'true'}, svg);
  };
  const detailField = (options = {}) => {
    if (Array.isArray(options.controls)) {
      options = {...options, control: detailParts(options.controls)};
    }
    const control = options.control instanceof Element && options.control.matches('input[type="checkbox"]')
      ? element("div", {class:"lex-source-control no-reference"}, options.control)
      : options.control;
    const pin = options.pin || null;
    const composite = control instanceof Element &&
      (control.matches(".lex-detail-parts") || control.querySelector(".lex-detail-parts"));
    // A group has no single scalar type or range. Its individual controls do.
    const input = control instanceof Element && !composite
      ? (control.matches("input,select,textarea,output,.lex-readonly-field")
        ? control : control.querySelector("input,select,textarea,output,.lex-readonly-field"))
      : null;
    const inputType = String(input?.type || "").toLocaleLowerCase();
    const step = input?.getAttribute?.("step") ?? input?.dataset?.step;
    const numericLike = inputType === "number" || (
      ["numeric", "decimal"].includes(String(input?.inputMode || "").toLocaleLowerCase()) &&
      step !== null && step !== undefined && step !== "");
    // A linked face carries no input to sniff, so its caller names the lock
    // state outright; every other control keeps the sniffed state it has.
    const readOnly = options.readOnly === true || Boolean(input && (
      input.readOnly || input.disabled || input.tagName === "OUTPUT" ||
      input.classList?.contains("lex-readonly-field")));
    // One checkbox is a boolean; several in one property are the bits of one
    // stored value, which is a different type and reads as FLG.
    const checkboxCount = control instanceof Element
      ? (control.matches("input[type=checkbox]") ? 1 : control.querySelectorAll("input[type=checkbox]").length)
      : 0;
    const inferredType = input?.dataset?.lexValueType || (inputType === "checkbox" ? (checkboxCount > 1 ? "FLAGS" : "BOOL")
      : numericLike && (step === null || step === "" || (step !== "any" && Number.isInteger(Number(step)))) ? "INT"
      : numericLike ? "FLOAT"
      : input?.tagName === "SELECT" ? "ENUM"
      : input?.tagName === "TEXTAREA" ? "TEXT"
      // No control to read a type from. "VALUE" said nothing except that the
      // guess failed, so the rail carries no type name instead.
      : input ? "STRING" : "");
    const declaredType = String(options.dataType || "").toLocaleUpperCase();
    const dataType = declaredType && declaredType !== "READ ONLY" ? declaredType : inferredType;
    const min = options.min ?? input?.getAttribute?.("min") ?? input?.dataset?.min;
    const max = options.max ?? input?.getAttribute?.("max") ?? input?.dataset?.max;
    const rangeText = options.range || ((min !== null && min !== undefined && min !== "") ||
      (max !== null && max !== undefined && max !== "")
      ? `(${min === null || min === undefined || min === "" ? "…" : formatNumber(min)}-${max === null || max === undefined || max === "" ? "…" : formatNumber(max)})` : "");
    if (input && !readOnly && dataType === "INT" && !input.dataset.lexExactInteger && !input.dataset.lexValidateNumber) {
      if (!input.hasAttribute("step")) input.step = "1";
      input.inputMode = "numeric";
      let lastValid = /^-?\d+$/.test(String(input.value)) ? String(input.value) : "0";
      input.addEventListener("beforeinput", event => {
        if (event.data && /[.eE]/.test(event.data)) event.preventDefault();
      });
      input.addEventListener("keydown", event => {
        if ([".", "Decimal", "e", "E"].includes(event.key)) event.preventDefault();
      });
      input.addEventListener("paste", event => {
        const value = event.clipboardData?.getData("text")?.trim() || "";
        if (value && !/^-?\d+$/.test(value)) event.preventDefault();
      });
      input.addEventListener("input", () => {
        if (/^-?\d+$/.test(input.value)) lastValid = input.value;
      });
      input.addEventListener("change", () => {
        let repaired = false;
        if (!/^-?\d+$/.test(input.value)) { input.value = lastValid; repaired = true; }
        let value = Number(input.value);
        if (min !== null && min !== undefined && min !== "" && Number.isFinite(Number(min))) value = Math.max(Number(min), value);
        if (max !== null && max !== undefined && max !== "" && Number.isFinite(Number(max))) value = Math.min(Number(max), value);
        const normalized = String(Math.trunc(value));
        if (input.value !== normalized) {
          input.value = normalized;
          repaired = true;
        }
        if (repaired) input.dispatchEvent(new Event("input", {bubbles: true}));
        lastValid = input.value;
      });
    }
    // Provenance controls own their reference-rail width. Keep the pin inside
    // that same coordinate system so it stays at the live field's top-right
    // corner instead of drifting into the label on narrow Detail rows.
    if (pin && control instanceof Element && control.classList.contains("lex-source-control")) {
      control.append(pin);
      anchorDetailPin(pin, control, input, inputType === "checkbox");
    }
    const lock = readOnly ? document.createElementNS("http://www.w3.org/2000/svg", "svg") : null;
    if (lock) {
      lock.setAttribute("class", "lex-field-readonly-lock");
      lock.setAttribute("viewBox", "0 0 24 24");
      lock.setAttribute("aria-hidden", "true");
      const body = document.createElementNS("http://www.w3.org/2000/svg", "path");
      body.setAttribute("d", "M17 8h-1V6a4 4 0 0 0-8 0v2H7a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2Zm-7-2a2 2 0 0 1 4 0v2h-4V6Zm2 11a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z");
      lock.append(body);
    }
    // Vertical type labels have one row's height to live in. Shrinking a long
    // word to fit turned "STRING" into a 6.7px smudge, so the rail uses short
    // codes and keeps a legible floor instead.
    const TYPE_CODES = {STRING: "STR", FLOAT: "FLT", INTEGER: "INT",
                        "READ ONLY": "RO", BOOLEAN: "BOOL", FLAGS: "FLG"};
    const typeName = element("span", {class: "lex-field-type-name"},
      TYPE_CODES[dataType] || dataType);
    const typeRange = rangeText ? element("span", {class: "lex-field-type-range"}, rangeText) : null;
    // The metadata rail already displays the type and numeric range. An info
    // bubble appears only when the caller authored semantic help. Never fabricate
    // a ? from the label, storage type, bounds, step, unit, or edit operation.
    const labelText = (options.label instanceof Node ? options.label.textContent : String(options.label || "value")).trim();
    const suppliedHelp = options.help instanceof Element
      ? String(options.help.getAttribute("aria-label") || options.help.getAttribute("title") || "").trim()
      : String(options.description || "").trim();
    const helpMarker = options.help || (suppliedHelp ? infoHelp(suppliedHelp) : null);
    if (input) {
      if (!input.getAttribute("aria-label") && labelText) input.setAttribute("aria-label", labelText);
      // Keep authored help available to assistive technology.
      if (suppliedHelp && !input.getAttribute("aria-description"))
        input.setAttribute("aria-description", suppliedHelp);
    }
    const typeRail = element("div", {class: "lex-field-type-rail"},
      typeName, typeRange);
    const directCheckboxes = control instanceof Element
      ? (control.matches('input[type="checkbox"]') ? 1 : control.querySelectorAll('input[type="checkbox"]').length)
      : 0;
    const booleanField = dataType === "BOOL" && directCheckboxes === 1;
    const arrow = booleanField ? element("span", {class: "lex-field-boolean-arrow", "aria-hidden": "true"}) : null;
    const node = element("div", {
      ...(options.attrs || {}),
      class: ["lex-detail-field", "lex-pinnable-property", booleanField ? "lex-boolean-field" : "",
        input?.tagName === "TEXTAREA" ? "lex-detail-field-stacked" : "",
        options.tone ? `lex-tone-${options.tone}` : "", options.className || ""].filter(Boolean).join(" "),
      "data-lex-type": dataType,
      "data-lex-layout-field": options.property || pin?.getAttribute?.("data-lex-pin-column") || labelText,
      "data-lex-property": options.property
        || pin?.getAttribute?.("data-lex-pin-column") || null,
      "data-lex-icon": options.icon || null,
      "data-lex-readonly": String(readOnly),
      // The property name is wrapped so it is a real flex item. Left as a bare
      // text node it was an anonymous item the leader arrow could shrink to
      // nothing, which wrapped "CAN SELL" one letter per line and drove the
      // label fitter down to its six-pixel floor.
      }, element("div", {class: "lex-detail-field-label"},
      options.icon ? typeGlyph(options.icon) : null,
      labelNode(options),
      helpMarker ? element("span", {class:"lex-field-help"}, helpMarker) : null,
      // The arrow used to live inside the label, which forced a boolean's
      // label column to span the whole row so the arrow had somewhere to run -
      // and that is why a boolean's name started at the far left while every
      // other name sat in the label column. It is its own track now, between
      // the label column and the control, so the name keeps the column it
      // shares with the rest of the panel.
      booleanField ? null : arrow),
    booleanField ? arrow : null,
    element("div", {class: "lex-detail-field-control"}, control,
      pin && pin.parentElement !== control ? pin : null),
    options.showType === false ? null : typeRail);
    // The leader arrow shares the checkbox's grid row, so it points at the
    // middle of the box whatever else the row is carrying and however tall the
    // row turns out to be. Anchored to the row instead, it tracked the row's
    // centre and drifted off the box as soon as anything sat under it.
    if (booleanField && arrow &&
        control instanceof Element && control.matches(".lex-source-control")) {
      control.append(arrow);
    }
    // The rail runs down the side of one row, so its type name has to fit that
    // row's height. A long name (or a range shown on focus) is set smaller
    // rather than being allowed to run into the rows above and below.
    const fitTypeRail = () => {
      const height = node.clientHeight - 4;
      const shown = typeRange && node.matches(":focus-within") ? typeRange : typeName;
      const characters = Math.max(1, (shown.textContent || "").trim().length);
      if (height <= 0) return;
      const size = `${Math.max(8, Math.min(9.5, height / (characters * 0.82)))}px`;
      if (shown.style.fontSize !== size) shown.style.fontSize = size;
    };
    if (typeof ResizeObserver === "function") new ResizeObserver(fitTypeRail).observe(node);
    node.addEventListener("focusin", fitTypeRail);
    node.addEventListener("focusout", fitTypeRail);
    node.addEventListener("mouseenter", fitTypeRail);
    node.addEventListener("mouseleave", fitTypeRail);
    requestAnimationFrame(fitTypeRail);

    // Rejecting a value has to be visible, so the rail flashes and shakes and
    // shows the type or range the field will actually accept.
    const rejectValue = () => {
      typeRail.classList.remove("rejected");
      void typeRail.offsetWidth;
      typeRail.classList.add("rejected");
      setTimeout(() => typeRail.classList.remove("rejected"), 420);
    };
    if (lock) {
      // Upright, inside the value box, hard against its right edge. A face
      // carries the property key instead of an input, so the keyed element
      // hosts the lock: the field node would span the label too, and the
      // wrapper would put the lock over the finder's button.
      const keyed = control instanceof Element
        ? (control.matches("[data-field-key]") ? control : control.querySelector("[data-field-key]"))
        : null;
      const host = control instanceof Element && control.matches(".lex-unit-field")
        ? control : (input?.parentElement || keyed || node);
      host.classList.add("lex-has-readonly-lock");
      host.append(lock);
      // A checkbox is smaller than the lock's margin, so right-aligned the
      // lock was drawn over the tick. It stands just left of the box instead,
      // placed the way the pin is beside a checkbox.
      if (inputType === "checkbox" && input) {
        const place = () => {
          if (!lock.isConnected || !input.isConnected) return;
          const owner = host.getBoundingClientRect(), target = input.getBoundingClientRect();
          if (!owner.width || !target.width) return;
          const scale = owner.width / host.offsetWidth || 1;
          lock.style.right = `${(owner.right - target.left) / scale + 4}px`;
        };
        requestAnimationFrame(place);
        if (typeof ResizeObserver !== "undefined") new ResizeObserver(place).observe(host);
      }
    }
    if (pin && input && !control?.classList?.contains("lex-source-control"))
      anchorDetailPin(pin, node.querySelector(".lex-detail-field-control"), input);
    node.lexRejectValue = rejectValue;

    // A bounded number draws its own value as a fill behind the box, and on
    // hover the fill slides out into a slider for rough adjustment.
    const lowBound = min === null || min === undefined || min === "" ? null : Number(min);
    const highBound = max === null || max === undefined || max === "" ? null : Number(max);
    // The slider always spans the whole accepted range. A second, narrower
    // span computed from the data read as a second range (Lexer), so the
    // handle moves in exactly what the field accepts.
    const [sliderLow, sliderHigh] = [lowBound, highBound];
    // Native arrows move by 1 when step is "any": without this, float
    // fields changed through whole numbers from the keyboard too.
    if (input && !readOnly && ["FLOAT", "F32", "F64", "ANGLE32"].includes(dataType)
        && (input.step === "any" || !Number.isFinite(Number(input.step)))) {
      input.addEventListener("keydown", event => {
        if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
        event.preventDefault();
        const at = readNumeric(input);
        const base = Number.isFinite(at) ? at : 0;
        const floor = input.min === "" ? -Infinity : Number(input.min);
        const ceiling = input.max === "" ? Infinity : Number(input.max);
        const next = Math.max(Number.isFinite(floor) ? floor : -Infinity,
          Math.min(Number.isFinite(ceiling) ? ceiling : Infinity,
            Number((base + (event.key === "ArrowUp" ? 0.1 : -0.1)).toPrecision(12))));
        if (next === base) return;
        writeNumeric(input, next);
        input.dispatchEvent(new Event("input", {bubbles: true}));
        input.dispatchEvent(new Event("change", {bubbles: true}));
      });
    }
    // Wide ranges still have a coarse slider; direct entry retains precise
    // control. A field's declared bounds, not an arbitrary span cutoff,
    // determine whether it has a range to show.
    if (input && !readOnly && numericLike && !input.dataset.lexExactInteger &&
        Number.isFinite(lowBound) && Number.isFinite(highBound) && highBound > lowBound) {
      const fill = element("span", {class: "lex-value-fill", "aria-hidden": "true"});
      const handle = element("span", {class: "lex-value-handle", "aria-hidden": "true"});
      fill.append(handle);
      const ratio = () => {
        const value = readNumeric(input);
        if (!Number.isFinite(value)) return 0;
        return Math.max(0, Math.min(1, (value - sliderLow) / (sliderHigh - sliderLow)));
      };
      const paint = () => {
        fill.style.setProperty("--lex-value-ratio", String(ratio()));
        // A face, stepper or lock beside the input makes the host taller
        // or wider than the box, and the fill then paints outside the
        // box. Measure the box and pin the fill to it - but only when
        // they differ, so normal fields keep their pure-CSS geometry
        // (the reference rail's inset included).
        const host = fill.parentElement;
        const target = input.getBoundingClientRect();
        const owner = host?.getBoundingClientRect();
        if (!host || !target.width || !target.height || !owner.width || !owner.height) return;
        if (Math.abs(owner.width - target.width) < 2 && Math.abs(owner.height - target.height) < 2 &&
            Math.abs(owner.left - target.left) < 2 && Math.abs(owner.top - target.top) < 2) {
          fill.style.left = fill.style.top = fill.style.width = fill.style.height = "";
          return;
        }
        const scale = owner.width / host.offsetWidth || 1;
        fill.style.left = `${(target.left - owner.left) / scale + 1}px`;
        fill.style.top = `${(target.top - owner.top) / scale + 1}px`;
        fill.style.width = `${target.width / scale - 2}px`;
        fill.style.height = `${target.height / scale - 2}px`;
      };
      input.__lexValueSliderPaint = paint;
      input.addEventListener("input", paint);
      input.addEventListener("change", paint);
      if (typeof ResizeObserver === "function") new ResizeObserver(paint).observe(node);
      requestAnimationFrame(paint);
      const box = () => (control instanceof Element && control.matches(".lex-unit-field")
        ? control : input);
      const setFromPointer = event => {
        if (input.disabled || input.readOnly || refusesEdit(input)) return;
        const bounds = box().getBoundingClientRect();
        const share = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
        // A float field's step is "any": snapping to step 1 would drag
        // it through whole numbers only. Without a usable step the
        // pointer position stands, rounded past float dust.
        const declared = Number(input.step);
        const snap = Number.isFinite(declared) && declared > 0 ? declared : 0;
        const raw = sliderLow + share * (sliderHigh - sliderLow);
        const snapped = snap > 0 ? Math.round(raw / snap) * snap : Number(raw.toPrecision(12));
        const nextValue = Math.max(sliderLow, Math.min(sliderHigh, snapped));
        if (readNumeric(input) === nextValue) return;
        writeNumeric(input, nextValue);
        paint();
        // A plugin still needs the input event so local previews (for example,
        // a curve) can update. Mark drag events so it can avoid refreshing the
        // complete shell for every pointer pixel.
        input.lexValueSliderDragging = true;
        input.dispatchEvent(new Event("input", {bubbles: true}));
      };
      handle.addEventListener("pointerdown", event => {
        if (input.disabled || input.readOnly || refusesEdit(input)) return;
        event.preventDefault();
        handle.setPointerCapture(event.pointerId);
        node.classList.add("lex-value-dragging");
        input.lexValueSliderDragging = true;
        let pendingPointer = null;
        let paintFrame = 0;
        const queuePointer = moved => {
          pendingPointer = moved;
          if (paintFrame) return;
          paintFrame = requestAnimationFrame(() => {
            paintFrame = 0;
            const next = pendingPointer;
            pendingPointer = null;
            if (next) setFromPointer(next);
          });
        };
        const flushPointer = () => {
          if (paintFrame) cancelAnimationFrame(paintFrame);
          paintFrame = 0;
          const next = pendingPointer;
          pendingPointer = null;
          if (next) setFromPointer(next);
        };
        const move = moved => queuePointer(moved);
        let stopped = false;
        // A drag that ends off-window never sees its pointerup: the
        // window losing focus ends it instead, or the slider keeps
        // following the pointer and swallowing its hover events.
        const blurStop = () => stop();
        const stop = () => {
          if (stopped) return;
          stopped = true;
          flushPointer();
          handle.removeEventListener("pointermove", move);
          handle.removeEventListener("pointerup", stop);
          handle.removeEventListener("pointercancel", stop);
          window.removeEventListener("blur", blurStop);
          node.classList.remove("lex-value-dragging");
          input.lexValueSliderDragging = false;
          input.dispatchEvent(new Event("change", {bubbles: true}));
        };
        handle.addEventListener("pointermove", move);
        handle.addEventListener("pointerup", stop);
        handle.addEventListener("pointercancel", stop);
        window.addEventListener("blur", blurStop);
      });
      node.classList.add("lex-has-value-fill");
      // The fill is drawn behind the value box, so it has to be positioned
      // against THAT box. Prepending it to whatever happened to be the input's
      // parent worked where the parent was a unit field or a provenance
      // control - both of which are positioned and box-shaped - and failed
      // everywhere else: with a bare input the nearest positioned ancestor is
      // the field control, which is as tall as the whole property row, so the
      // fill painted the row from top to bottom. A host of its own means the
      // box the fill measures is always the box the reader sees.
      const fillHost = control instanceof Element && control.matches(".lex-unit-field")
        ? control
        : input.parentElement?.matches?.(".lex-source-control-internal,.lex-unit-field")
          ? input.parentElement
          : (() => {
            const host = element("span", {class: "lex-value-host"});
            input.replaceWith(host);
            host.append(input);
            return host;
          })();
      fillHost?.prepend(fill);
      requestAnimationFrame(paint);
    }

    if (input && !readOnly && inputType !== "checkbox") {
      // Selecting the whole value on focus keeps a drag inside the field from
      // competing with the slider handle that shares the same box.
      input.addEventListener("focus", () => {
        if (!input.lexRestoringFocus) requestAnimationFrame(() => input.select?.());
      });
      if (numericLike) {
        input.addEventListener("beforeinput", event => {
          if (event.data && /[^0-9.eE+-]/.test(event.data)) { event.preventDefault(); rejectValue(); }
        });
        input.addEventListener("change", () => {
          const value = readNumeric(input);
          const low = min === null || min === undefined || min === "" ? -Infinity : Number(min);
          const high = max === null || max === undefined || max === "" ? Infinity : Number(max);
          if (!Number.isFinite(value) || value < low || value > high) rejectValue();
        });
      }
    }

    // Right-click restores whatever the record shipped with.
    node.addEventListener("contextmenu", event => {
      const source = node.querySelector(".lex-source-control");
      if (!source?.lexRevert) return;
      event.preventDefault();
      source.lexRevert(event);
      input?.__lexValueSliderPaint?.();
      showToast("Restored the vanilla value");
    });

    // A property holds one variable in the ordinary case and several in a
    // multi-variable one - a stat block, a junction set. One button for a
    // property that holds four numbers copied the first of them and called it
    // the property, so a property with its own idea of what it is worth says
    // so, a multi-variable property gives each variable its own button, and
    // only a single-variable property is copied as a whole.
    const declared = control instanceof Element
      ? (typeof control.lexCopyValue === "function" ? control
         : [...control.querySelectorAll("*")].find(node => typeof node.lexCopyValue === "function"))
      : null;
    const variables = control instanceof Element
      ? control.querySelectorAll('input:not([type="checkbox"]):not([type="range"]),select,textarea').length
      : 0;
    if (declared) node.querySelector(".lex-detail-field-control")?.prepend(
      copyValueButton(() => declared.lexCopyValue(), "Copy this property"));
    else if (input && inputType !== "checkbox" && variables <= 1 && !control?.classList?.contains("lex-multi-number")) {
      node.querySelector(".lex-detail-field-control")?.prepend(copyValueButton(() => input.tagName === "SELECT"
        ? (input.selectedOptions[0]?.textContent || input.value)
        : input.value));
    }
    return node;
  };

  const copyValueButton = (read, label = "Copy this value") => element("button", {
    type: "button", class: "lex-copy-value", tabindex: "-1",
    title: label, "aria-label": label,
    onclick: async event => {
      event.preventDefault();
      event.stopPropagation();
      const text = String(read() ?? "");
      const copied = await copyText(text, {quiet: true});
      showToast(copied ? `Copied: "${text}"` : "Could not reach the clipboard", !copied);
    },
  }, copyIcon());

  // Public names describe the panel archetype, not one historic view. A Detail
  // panel is made from groups of rows. Every row shares the panel's one label
  // division, while games only supply controls and theme overrides.
  // A row of related on/off switches shown as one property. Multi-toggle rows
  // kept being rebuilt per plugin and kept collapsing into unreadable strips,
  // so this is the one implementation: labels stay full size and the row wraps
  // onto as many lines as it needs instead of shrinking to fit one.
  // A wrapped row of switches is balanced, not filled: the grid takes as many
  // columns as fit, and when that leaves a ragged last line the columns are
  // cut to the fewest that still need the same number of lines. Eight switches
  // where five fit read as four and four, not five and three.
  const balanceToggleRow = row => {
    const count = row.childElementCount, style = getComputedStyle(row);
    const width = row.clientWidth - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0);
    if (!count || width <= 0) return;
    const probe = element("span", {style: "position:absolute;visibility:hidden;width:var(--lex-toggle-basis,11em)"});
    row.append(probe);
    let basis = probe.getBoundingClientRect().width || 176;
    probe.remove();
    // Include each switch's full label, help, checkbox and padding before
    // choosing columns. A fixed em basis can split a name and its help mark.
    for (const toggle of Array.from(row.children)) {
      if (!toggle.classList.contains("lex-toggle")) continue;
      const sample = toggle.cloneNode(true);
      sample.style.cssText = "position:absolute;visibility:hidden;width:max-content;max-width:none;min-width:0;";
      sample.querySelector(".lex-toggle-name").style.cssText = "white-space:nowrap;flex:none;";
      row.append(sample);
      basis = Math.max(basis, sample.getBoundingClientRect().width);
      sample.remove();
    }
    basis = Math.min(width, Math.ceil(basis));
    const gap = parseFloat(style.columnGap) || 0;
    const fit = Math.max(1, Math.min(count, Math.floor((width + gap) / (basis + gap))));
    const columns = Math.ceil(count / Math.ceil(count / fit));
    if (row.style.getPropertyValue("--lex-toggle-fit-columns") !== String(columns))
      row.style.setProperty("--lex-toggle-fit-columns", String(columns));
  };
  // One observer for every switch row on the page.
  const toggleRowObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(entries => entries.forEach(entry => balanceToggleRow(entry.target)))
    : null;
  const toggleRow = (options = {}) => {
    const toggles = (options.toggles || []).map(toggle => {
      const input = toggle.control || element("input", {
        type: "checkbox",
        checked: !!toggle.checked,
        disabled: !!toggle.disabled,
        "aria-label": toggle.label,
        onchange: event => toggle.change?.(event.target.checked, event),
      });
      // The type rail stays fixed; help belongs beside the property name.
      const rail = element("span", {class: "lex-toggle-rail"},
        element("span", {class: "lex-toggle-type"}, "BOOL"));
      const name = labelNode(toggle);
      // Renaming a name inside a label must not activate its checkbox.
      name.addEventListener("click", event => {
        if (sharedSettingsSnapshot?.developerMode) event.preventDefault();
      });
      const label = element("label", {
        class: ["lex-toggle", toggle.className || ""].filter(Boolean).join(" "),
        "data-lex-toggle": toggle.key || toggle.label || "",
      }, rail, toggle.decorateControl ? toggle.decorateControl(input) : input,
      toggle.icon || null, element("span", {class: "lex-toggle-name"}, name,
        toggle.help ? infoHelp(toggle.help) : null));
      // A switch that is also a table column carries its pin in its corner,
      // the same place every other pinnable property keeps one.
      if (toggle.pin) {
        label.classList.add("lex-pinnable-property");
        label.append(toggle.pin);
      }
      return label;
    });
    const root = detailParts([...(options.leading || []),...toggles], {
      stacked: !!options.leading?.length,
      className: ["lex-toggle-row", "lex-detail-parts-switches", options.className || ""].filter(Boolean).join(" "),
      role: "group",
      label: options.label || "Toggles",
    });
    if (options.minimum) root.style.setProperty("--lex-toggle-minimum", `${options.minimum}px`);
    if (options.columns) root.style.setProperty("--lex-toggle-columns", String(options.columns));
    toggleRowObserver?.observe(root);
    // A row of switches is one property holding one number. Copying it copies
    // that number - the bare flag word the game actually stores - not a list
    // of the labels drawn over it. A caller that knows the word passes it; a
    // caller that does not gets the bits its switches imply, which is where
    // `bit` on a switch matters when the flags are not consecutive.
    root.lexCopyValue = () => {
      if (options.value !== undefined) {
        return typeof options.value === "function" ? options.value() : options.value;
      }
      return (options.toggles || []).reduce((word, toggle, index) => {
        const bit = Number.isInteger(toggle.bit) ? toggle.bit : index;
        const on = toggles[index]?.querySelector('input[type="checkbox"]')?.checked;
        return on ? word + 2 ** bit : word;
      }, 0);
    };
    return root;
  };

  const detailGroup = detailSection;
  const detailRow = detailField;

  // One property that holds several numbers - a stat block, a set of junction
  // values - laid out as ordinary label-then-box pairs rather than captions
  // stacked over boxes, which is what every other property in the editor does.
  const multiNumberRow = (entries = [], options = {}) => detailParts(
    // The caller's help text and pin travel with the part. Dropping them here
    // left a multi-number property unable to carry a help bubble at all, which
    // is why one form of the same property had one and another did not.
    entries.filter(Boolean).map(entry => ({label: entry.label, control: entry.control,
      title: entry.title, help: entry.help, pin: entry.pin})),
    {columns: options.columns, stacked: options.stacked, nowrap: options.nowrap, copy: !options.stacked,
     className: ["lex-multi-number", options.className || ""].filter(Boolean).join(" ")});

  // Nested navigation is a shared control. Plugins provide only labels,
  // active state, and the page-owned change callback.
  // A page with one subtab has no choice to offer, so it shows no bar. A bar
  // with a single tab in it reads as a control that does nothing.
  // Subtabs read in alphabetical order, the same rule the tabbed panel and
  // the page tabs follow (a Misc tab, then Tweaks, come last). An image bar
  // keeps the game's own order - GF and character portraits.
  // Holding the right button on a subtab saves the page's view as the shipped
  // default, as it does on the page tab: a subtab's layout is stored under its
  // page, so the page is what gets saved (Lexer: the hold did nothing on a
  // subtab). Developer mode only, like the page tab.
  // A mod's place in the load order, moved the same way in every list of
  // mods (the mod selector and the Mods tab): drag a row onto another, or
  // Alt+Up / Alt+Down with the row focused. `index` is the row's place in the
  // list, `movable(i)` whether the row at i takes part, and `move(from, by)`
  // moves the row at `from` by `by` places. A press on one of the row's own
  // controls (`controls`, a selector) never starts a drag.
  const MOD_ORDER_TYPE = "application/x-lex-mod";
  const modOrderGestures = ({index, movable, move, controls = "input,button"}) => {
    let controlGesture = false;
    // The row under the pointer shows where the drop lands: a line above
    // it or below it, the way a dragged header marks its target cell.
    const showLine = (row, after) => {
      row.parentElement?.querySelectorAll(".lex-drop-before,.lex-drop-after").forEach(node => {
        if (node !== row) node.classList.remove("lex-drop-before", "lex-drop-after");
      });
      row.classList.toggle("lex-drop-before", !after);
      row.classList.toggle("lex-drop-after", after);
    };
    const clearLines = row => {
      row.parentElement?.querySelectorAll(".lex-drop-before,.lex-drop-after").forEach(node =>
        node.classList.remove("lex-drop-before", "lex-drop-after"));
    };
    const pastMiddle = event => {
      const rect = event.currentTarget.getBoundingClientRect();
      return event.clientY > rect.top + rect.height / 2;
    };
    return {
      draggable: "true", tabindex: 0,
      "aria-description": "Drag to a new position. Alt+Up or Alt+Down moves one place.",
      onpointerdown: event => { controlGesture = !!event.target.closest(controls); },
      ondragstart: event => {
        if (controlGesture) { event.preventDefault(); return; }
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData(MOD_ORDER_TYPE, String(index));
        event.currentTarget.classList.add("dragging");
      },
      onkeydown: event => {
        if (event.target !== event.currentTarget || !event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        const by = event.key === "ArrowUp" ? -1 : 1;
        if (movable(index + by)) move(index, by);
      },
      ondragover: event => {
        if (event.dataTransfer.types.includes(MOD_ORDER_TYPE)) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
          showLine(event.currentTarget, pastMiddle(event));
        }
      },
      ondragleave: event => {
        event.currentTarget.classList.remove("lex-drop-before", "lex-drop-after");
      },
      ondragend: event => {
        event.currentTarget.classList.remove("dragging");
        clearLines(event.currentTarget);
      },
      ondrop: event => {
        clearLines(event.currentTarget);
        const from = Number(event.dataTransfer.getData(MOD_ORDER_TYPE));
        if (!Number.isInteger(from) || !movable(from)) return;
        event.preventDefault();
        // The line says the slot: above the row takes its place, below it
        // takes the next one. Beside itself both are a no-op.
        const slot = pastMiddle(event) ? index + 1 : index;
        const to = slot <= from ? slot : slot - 1;
        if (to !== from) move(from, to - from);
      },
    };
  };
  // Packaged default views, fetched once per plugin.
  const defaultViewsCache = new Map();
  const packagedDefaults = pluginId => {
    if (!defaultViewsCache.has(pluginId))
      defaultViewsCache.set(pluginId,
        callWindow("default_views", pluginId).then(result => result?.views || {}).catch(() => ({})));
    return defaultViewsCache.get(pluginId);
  };
  // Reset returns to the shipped default view, not to an empty one: the
  // stored keys under the token are cleared, then the packaged ones come
  // back. Anyone may reset; only developers save.
  const resetStoredView = async (pluginId, tabId, token) => {
    try {
      for (let index = localStorage.length - 1; index >= 0; index -= 1) {
        const key = localStorage.key(index);
        if (key && key.includes(token)) localStorage.removeItem(key);
      }
    } catch (_error) {}
    try {
      const views = await packagedDefaults(pluginId);
      for (const [key, value] of Object.entries(views[tabId] || {}))
        if (key.includes(token)) localStorage.setItem(key, String(value));
    } catch (_error) {}
  };
  // A tab or subtab with no shipped default wears a hollow dot, so it is
  // visible which ones reset to a curated view and which reset to bare.
  const markMissingDefaultView = (button, pluginId, tabId, token) => {
    packagedDefaults(pluginId).then(views => {
      const entries = Object.entries(views[tabId] || {});
      const has = token ? entries.some(([key]) => key.includes(token)) : entries.length > 0;
      if (!has && button.isConnected && !button.querySelector(":scope > .lex-tab-no-default"))
        button.append(element("span", {class: "lex-tab-no-default", "aria-hidden": "true",
          title: "No saved default view"}));
    }).catch(() => {});
  };
  // A fresh save clears the hollow dots it earned: drop the cached
  // packaged defaults, strip every dot, and re-mark, so only tabs
  // still without a default keep theirs.
  const refreshMissingDefaultViews = (pluginId, tabId) => {
    defaultViewsCache.delete(pluginId);
    document.querySelectorAll(".lex-tab-no-default").forEach(dot => dot.remove());
    document.querySelectorAll(".lex-shell-header nav button[data-tab]").forEach(button =>
      markMissingDefaultView(button, pluginId, button.dataset.tab, ""));
    document.querySelectorAll(".lex-subtab-button").forEach(button => {
      if (button.dataset.subtab)
        markMissingDefaultView(button, pluginId, tabId, `${pluginId}-${tabId}-${button.dataset.subtab}`);
    });
  };
  const holdToSaveDefaultView = (button, onReset) => {    let timer = 0, saved = false;
    button.addEventListener("pointerdown", event => {
      if (event.button !== 2 || !sharedSettingsSnapshot?.developerMode) return;
      saved = false;
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const plugin = shellPluginId(), page = activePageTab();
        if (!plugin || !page) return;
        const token = `${plugin}-${page}`, preferences = {};
        try {
          for (let index = 0; index < localStorage.length; index += 1) {
            const key = localStorage.key(index);
            if (key && key.includes(token)) preferences[key] = localStorage.getItem(key);
          }
          if (!Object.keys(preferences).length) {
            const name = document.querySelector(".lex-shell-header nav button.active .lex-tab-label-text")?.textContent || page;
            showToast(`${name} has no view settings to save.`);
            return;
          }
          const result = await callWindow("save_default_view", plugin, page, preferences);
          saved = !!result?.saved;
          const name = document.querySelector(".lex-shell-header nav button.active .lex-tab-label-text")?.textContent || page;
          if (saved) {
            showToast(`${name} is now the shipped default view.`);
            refreshMissingDefaultViews(plugin, page);
          }
        } catch (error) {
          showAlert({title: "Could not save the default view", message: error.message || String(error)});
        }
      }, 700);
    });
    for (const type of ["pointerup", "pointercancel", "pointerleave"])
      button.addEventListener(type, () => clearTimeout(timer));
    button.addEventListener("contextmenu", event => {
      event.preventDefault();
      clearTimeout(timer);
      if (saved) { saved = false; return; }
      const plugin = shellPluginId(), page = activePageTab();
      const sub = button.dataset.subtab;
      if (!plugin || !page || !sub || typeof onReset !== "function") return;
      resetStoredView(plugin, page, `${plugin}-${page}-${sub}`).then(() => {
        window.dispatchEvent(new CustomEvent("lexeditor-view-reset",
          {detail: {plugin, tab: page, sub}}));
        onReset(sub);
      });
    });
  };
  // The last subtab click, for telling a double-click from two singles.
  // It lives outside the bar because a switch rebuilds the bar: the second
  // click lands on a new element, so the bar itself cannot remember it.
  let lastSubtabClick = null;
  const subtabBar = (options = {}) => {
    const bar = subtabBarSorted(options);
    bar.querySelectorAll(".lex-subtab-button").forEach(button => {
      holdToSaveDefaultView(button, sub => options.change?.(sub));
      const plugin = shellPluginId(), page = activePageTab(), sub = button.dataset.subtab;
      if (plugin && page && sub)
        markMissingDefaultView(button, plugin, page, `${plugin}-${page}-${sub}`);
    });
    return bar;
  };
  const subtabBarSorted = (options = {}) => {
    if (options.images || options.order === "given") return subtabBarElement(options);
    const rank = tab => ({tweaks: 2, misc: 1})[String(tab.id).toLocaleLowerCase()] || 0;
    const name = tab => shownSubtabName(tab);
    const tabs = [...(options.tabs || [])].sort((a, b) => rank(a) - rank(b)
      || name(a).localeCompare(name(b), undefined, {numeric: true, sensitivity: "base"}));
    return subtabBarElement({...options, tabs});
  };
  // A renamed subtab rejoins the bar in alphabetical order: the bar sorted
  // itself when it was built, and the rename must not leave it unsorted.
  // Given-order and image bars never sort, and the positional shortcut
  // badges follow their slots (the keys themselves read DOM order).
  const resortSubtabBar = bar => {
    if (!(bar instanceof Element) || !bar.classList.contains("lex-subtab-bar")) return;
    if (bar.classList.contains("lex-subtab-bar-images") || bar.dataset.lexSort === "given") return;
    const rank = id => ({tweaks: 2, misc: 1})[String(id).toLocaleLowerCase()] || 0;
    const buttons = [...bar.querySelectorAll(":scope > .lex-subtab-button")];
    const name = button => button.querySelector(".lex-tab-label-text")?.textContent.trim()
      || button.dataset.subtab || "";
    buttons.sort((a, b) => rank(a.dataset.subtab) - rank(b.dataset.subtab)
      || name(a).localeCompare(name(b), undefined, {numeric: true, sensitivity: "base"}));
    buttons.forEach(button => bar.append(button));
    const shortcuts = bar.dataset.lexSubtabShortcuts !== "false";
    buttons.forEach((button, index) => {
      const badge = button.querySelector(":scope > .lex-tab-shortcut");
      const key = shortcutKeyFor(index + 1);
      if (!shortcuts || !key) { badge?.remove(); return; }
      if (badge) { badge.textContent = `⇧${key}`; return; }
      button.append(element("span", {class: "lex-tab-shortcut", "aria-hidden": "true"}, `⇧${key}`));
    });
  };
  const resortSubtabOf = node => resortSubtabBar(node?.closest?.(".lex-subtab-bar"));
  const subtabBarElement = (options = {}) => {
    const full = options.tabs || [];
    const fieldTabs = options.fieldTabs;
    const shape = fieldTabs?.shape;
    const visible = shape ? visibleFieldTabs(full, shape, fieldTabs.members) : [...full];
    const hidden = shape
      ? readFieldTabHidden(shape).filter(id => full.some(tab => String(tab.id) === id)
        && !(fieldTabs.members?.[id]?.length > 0))
      : [];
    if (visible.length < (options.showSingle ? 1 : 2) && !hidden.length)
      return element("div", {class: "lex-subtab-bar lex-subtab-bar-single", hidden: true});
    const bar = element("div", {
    class: ["lex-subtab-bar", options.flush === true ? "lex-subtab-bar-flush" : "",
      options.images ? "lex-subtab-bar-images" : "",
      options.className || ""].filter(Boolean).join(" "),
    role: "tablist",
    "data-lex-subtab-shortcuts": String(options.shortcuts !== false),
    "aria-label": options.label || "Subsections",
    "data-lex-sort": options.order === "given" ? "given" : null,
    }, ...visible.map((tab, index) => {
      // A subtab is renamed in place the way a page tab is, and the name is
      // stored under the page tab that owns it, which is where the shippable
      // view defaults for this screen live.
      const subtabKey = () =>
        `${shellPluginId()}-${activePageTab()}.sub.${tab.id}.label`;
      const labelText = element("span", {class: "lex-tab-label-text"},
        savedLabel(subtabKey(), tab.label));
      labelText.addEventListener("dblclick", event => {
        if (!sharedSettingsSnapshot?.developerMode) return;
        event.preventDefault();
        event.stopPropagation();
        renameInPlace(subtabKey(), activePageTab(), tab.label, labelText);
      });
      return element("button", {
      type: "button",
      ...(tab.attrs || {}),
      // A tab with a reason stays focusable (a truly disabled button
      // eats its tooltip): aria-disabled grays it with the not-allowed
      // cursor and the reason rides on the title. Otherwise native.
      disabled:!!tab.disabled && !tab.disabledReason,
      ...(!!tab.disabled && tab.disabledReason ? {"aria-disabled": "true", title: tab.disabledReason} : {}),
      class: ["lex-subtab-button", tab.id === options.active ? "active" : ""].filter(Boolean).join(" "),
      "data-subtab": String(tab.id),
      role: "tab",
      "aria-selected": String(tab.id === options.active),
      tabindex: tab.id === options.active ? "0" : "-1",
      // Clicking the active subtab changes nothing: re-running change
      // would rebuild the strip (wiping the rename box a double-click
      // just opened) for no visible effect. A double-click on an INACTIVE
      // subtab is a rename, caught here rather than in the label's own
      // dblclick listener: the first click rebuilds the strip, so that
      // listener would never see both clicks on one node.
      onclick: event => {
        const button = event.currentTarget;
        // A cross-tab drop lands through a stale bar: the target's button
        // still wears its pre-drop gray, and the click that lands the move
        // must pass it once. The re-render replaces the button; a bar with
        // no change handler never takes drops, so the flag never sticks.
        if (button.dataset.lexReviveClick) delete button.dataset.lexReviveClick;
        else if (tab.disabled) return;
        const bar = button.closest(".lex-subtab-bar");
        const stamp = `${activePageTab()}|${bar?.getAttribute("aria-label") || ""}|${tab.id}`;
        const now = Date.now();
        const secondClick = sharedSettingsSnapshot?.developerMode && lastSubtabClick
          && lastSubtabClick.stamp === stamp && now - lastSubtabClick.at < 500
          && !button.querySelector(".lex-label-rename");
        lastSubtabClick = {stamp, at: now};
        if (secondClick) {
          const label = button.querySelector(".lex-tab-label-text");
          if (label) renameInPlace(subtabKey(), activePageTab(), tab.label, label);
          return;
        }
        if (button.classList.contains("active")) return;
        options.change?.(tab.id);
      },
    }, element("span", {class: "lex-tab-label"}, labelText),
  tab.help ? (() => {
    const help = infoHelp(tab.help);
    help.addEventListener("click", event => event.stopPropagation());
    help.addEventListener("keydown", event => {
      event.stopPropagation();
      if (event.key === "Enter" || event.key === " ") event.preventDefault();
    });
    return help;
  })() : null,
  (key => key && options.shortcuts !== false ? element("span", {
    class: "lex-tab-shortcut", "aria-hidden": "true",
  }, `⇧${key}`) : "")(shortcutKeyFor(index + 1)),
  tab.isEmptyTab && options.change && visible.length > 1 ? (() => {
    // An empty husk goes with one click; hiding the last tab would strand
    // the panel, so it keeps no button. Hiding the active tab switches away
    // through change (the caller re-renders); otherwise the bar refreshes in
    // place, and undo replays the same refresh from its own entry.
    const remove = element("span", {class: "lex-subtab-remove", role: "button", tabindex: "0",
      title: `Remove the empty ${tab.label} tab`, "aria-label": `Remove ${tab.label} tab`}, "×");
    const hide = event => {
      event.preventDefault();
      event.stopPropagation();
      const at = remove.closest(".lex-subtab-bar");
      if (!at || !shape) return;
      const before = readFieldTabHidden(shape);
      const id = String(tab.id);
      if (before.includes(id)) return;
      const after = [...before, id];
      // The hide replaces the bar (or the caller re-renders past it), so by
      // undo time `at` is detached and a refresh of it is a no-op: find the
      // live bar for this shape instead.
      const apply = ids => {
        writeFieldTabHidden(shape, ids);
        const live = at.isConnected ? at : document.querySelector(
          `.lex-tabbed-panel-tabs[data-lex-fieldtabs="${shape}"]`) || at;
        refreshSubtabBar(live);
      };
      writeFieldTabHidden(shape, after);
      pushLabelUndo({before, after, apply});
      labelRedo.length = 0;
      labelHistoryChanged();
      const current = at.querySelector(".lex-subtab-button.active")?.dataset.subtab;
      if (current === id) {
        const next = visibleFieldTabs(full, shape, fieldTabs.members).find(candidate => !candidate.disabled);
        if (next) options.change(next.id);
        else refreshSubtabBar(at);
      } else refreshSubtabBar(at);
    };
    remove.addEventListener("click", hide);
    remove.addEventListener("keydown", event => {
      event.stopPropagation();
      if (event.key === "Enter" || event.key === " ") hide(event);
    });
    return remove;
  })() : null);
    }),
    ...(hidden.length ? [element("button", {type: "button", class: "lex-subtab-restore",
      title: `Show ${hidden.length} hidden tab${hidden.length === 1 ? "" : "s"}`,
      "aria-label": `Show ${hidden.length} hidden tab${hidden.length === 1 ? "" : "s"}`,
      onclick: event => {
        event.stopPropagation();
        const at = event.currentTarget.closest(".lex-subtab-bar");
        choicePopover({label: "Hidden tabs", search: hidden.length > 6 ? "Search hidden tabs" : false,
          choices: hidden.map(id => ({label: full.find(tab => String(tab.id) === id)?.label || id, value: id})),
          select: value => {
            writeFieldTabHidden(shape, readFieldTabHidden(shape).filter(kept => kept !== value));
            if (at) refreshSubtabBar(at);
          }}).openFor(event.currentTarget);
      }}, `+${hidden.length}`)] : []));
    bar.__lexSubtabOptions = options;
    // A caller that honors membership overrides marks its bar here, where
    // every build (and every bar refresh) lands it, so drops onto its tabs
    // move properties there. Only its accepting tabs (its field groups,
    // never its bespoke tabs) take the drop. A header hover glows the tab
    // holding its property when the field itself is off-screen; the caller
    // names each tab's members.
    if (fieldTabs?.shape) {
      bar.dataset.lexFieldtabs = fieldTabs.shape;
      const accept = new Set(fieldTabs.accept || []);
      for (const button of bar.querySelectorAll(":scope > .lex-subtab-button"))
        if (accept.has(button.dataset.subtab)) button.dataset.lexAcceptFields = "true";
    }
    if (fieldTabs?.members) {
      const known = new Map();
      for (const [tabId, keys] of Object.entries(fieldTabs.members))
        for (const key of [keys || []].flat())
          if (!known.has(String(key))) known.set(String(key), tabId);
      bar.lexTabMembers = known;
    }
    return bar;
  };

  // The key that selects the Nth tab, matching the shortcut sequence:
  // 1-9, then 0 for the tenth, then - and = for the eleventh and twelfth.
  // Positions past that have no key, so they get no badge.
  const shortcutKeyFor = position => (
    position <= 9 ? String(position)
    : position === 10 ? "0"
    : position === 11 ? "-"
    : position === 12 ? "=" : "");

  const mathFormula = (source, options = {}) => {
    // A curve's variables decide which identifiers take a color: each
    // spelling (the label plus its extra tokens) maps to its key, so
    // DS1's T_lo lights with the T1-T5 family while FF8's A-D keep
    // their letters. No variables means no coloring anywhere.
    const spellings = new Map();
    for (const variable of options.variables || []) {
      const key = String(variable.key || variable.label || "").trim().toLocaleLowerCase();
      if (!key) continue;
      for (const spelling of [variable.label, ...(variable.tokens || [])]) {
        const text = String(spelling || "").trim();
        if (text && !spellings.has(text)) spellings.set(text, key);
      }
    }
    const [expression, ...notes] = String(source).split(";");
    const normalized = expression.replaceAll("−","-").replaceAll("·","*")
      .replaceAll("×","*").replaceAll("⌊","floor(").replaceAll("⌋",")").replaceAll("²","^2");
    const namespace = "http://www.w3.org/1998/Math/MathML";
    const node = (tag, ...children) => {
      const result = document.createElementNS(namespace, tag);
      result.append(...children);
      return result;
    };
    const tokens = normalized.match(/[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[()+\-*/^=,]/g) || [];
    let index = 0;
    const priority = {"=": 1, "+": 2, "-": 2, "*": 3, "/": 3, "^": 4};
    const atom = () => {
      const token = tokens[index++];
      if (token == null) throw new Error("Missing expression");
      if (token === "-") return node("mrow", node("mo", "−"), atom());
      if (token === "(") {
        const value = parse(1);
        if (tokens[index++] !== ")") throw new Error("Missing closing parenthesis");
        return node("mrow", node("mo", "("), value, node("mo", ")"));
      }
      if (/^\d/.test(token)) return node("mn", token);
      if (!/^[A-Za-z_]/.test(token)) throw new Error("Unexpected token");
      const name = node("mi", token);
      const colored = spellings.get(token);
      if (colored) name.setAttribute("class", `lex-curve-variable-${colored}`);
      if (tokens[index] !== "(") return name;
      index++;
      const argument = parse(1);
      if (tokens[index++] !== ")") throw new Error("Missing function argument");
      if (token === "floor") return node("mrow", node("mo", "⌊"), argument, node("mo", "⌋"));
      if (token === "trunc") name.setAttribute("mathvariant", "normal");
      return node("mrow", name, node("mo", "("), argument, node("mo", ")"));
    };
    const parse = minimum => {
      let left = atom();
      while ((priority[tokens[index]] || 0) >= minimum) {
        const operator = tokens[index++], rank = priority[operator];
        const right = parse(rank + (operator === "^" ? 0 : 1));
        left = operator === "/" ? node("mfrac", left, right)
          : operator === "^" ? node("msup", left, right)
          : node("mrow", left, node("mo", operator === "*" ? "·" : operator === "-" ? "−" : operator), right);
      }
      return left;
    };
    try {
      if (tokens.join("") !== normalized.replace(/\s/g,"")) throw new Error("Unsupported notation");
      const value = parse(1);
      if (index !== tokens.length) throw new Error("Unsupported expression");
      const math = node("math", value);
      math.setAttribute("aria-label", expression);
      return element("span", {class:"lex-math-formula", title:String(source)}, math,
        notes.length ? element("small", {}, notes.join(";")) : null);
    } catch (_error) {
      return element("span", {class:"lex-math-formula"}, String(source));
    }
  };

  const curveEditor = (options = {}) => {
    const domain = options.domain || {min: 1, max: 100};
    const getRange = () => {
      const value = typeof options.range === "function" ? options.range() : options.range;
      return value || {min: 0, max: 255};
    };
    const initialRange = getRange();
    const svgNamespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNamespace, "svg");
    svg.setAttribute("class", "lex-curve-svg");
    svg.setAttribute("viewBox", "0 0 320 160");
    let graphHeight = 160;
    // The viewBox is only matched while the layout drives the box. Under a
    // content-driven ancestor the box height falls back to the intrinsic
    // ratio, so adopting our own box back would grow every pass (#527).
    let lastBoxWidth = 0, lastBoxHeight = 0, wroteViewBox = false, heldSize = false;
    // Match the viewBox to the available rectangle, keeping text uniformly
    // scaled without adding letterbox space above and below the graph.
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", options.graphLabel || `${options.title || "Value"} curve`);
    const grid = document.createElementNS(svgNamespace, "path");
    grid.setAttribute("class", "lex-curve-grid-lines");
    grid.setAttribute("d", "M0 0H320 M0 40H320 M0 80H320 M0 120H320 M0 160H320 M0 0V160 M80 0V160 M160 0V160 M240 0V160 M320 0V160");
    const line = document.createElementNS(svgNamespace, "path");
    line.setAttribute("class", "lex-curve-line");
    line.setAttribute("fill", "none");
    const curveId = `lex-curve-${curveEditor.sequence = (curveEditor.sequence || 0) + 1}`;
    line.setAttribute("id", curveId);
    const fill = document.createElementNS(svgNamespace, "path");
    fill.setAttribute("class", "lex-curve-fill");
    // A theme's shadow under the line is a second stroke, not a CSS filter: a
    // filter re-rasterised the path without smoothing, which is the jagged
    // edge Lexer kept seeing on FF8's graphs.
    const lineShadow = document.createElementNS(svgNamespace, "path");
    lineShadow.setAttribute("class", "lex-curve-line-shadow");
    lineShadow.setAttribute("fill", "none");
    const rangeLow = document.createElementNS(svgNamespace, "text");
    rangeLow.setAttribute("class", "lex-curve-range-value lex-curve-range-low");
    rangeLow.setAttribute("text-anchor", "start");
    const rangeHigh = document.createElementNS(svgNamespace, "text");
    rangeHigh.setAttribute("class", "lex-curve-range-value lex-curve-range-high");
    rangeHigh.setAttribute("text-anchor", "end");
    const formulaText = document.createElementNS(svgNamespace, "text");
    formulaText.setAttribute("class", "lex-curve-path-formula");
    formulaText.setAttribute("dy", "-7");
    const mathematical = options.formula?.classList?.contains("lex-math-formula");
    const mathOverlay = mathematical ? options.formula.cloneNode(true) : null;
    let mathSource = mathOverlay?.querySelector(":scope > math");
    const mathAtoms = [];
    const addAtom = source => {
      if (source.localName === "mrow") {
        [...source.children].forEach(addAtom);
        return;
      }
      // Fractions and powers stay whole; splitting their descendants would
      // lose the mathematical grouping. Ordinary terms turn independently.
      const math = document.createElementNS(mathSource.namespaceURI, "math");
      math.append(source.cloneNode(true));
      const visual = element("span", {class:"lex-curve-math-atom", "aria-hidden":"true"}, math);
      mathOverlay.append(visual);
      mathAtoms.push({source, visual});
    };
    if (mathSource) {
      mathOverlay.classList.add("lex-curve-math-follow");
      mathOverlay.setAttribute("role", "img");
      mathOverlay.setAttribute("aria-label", options.formula.title || mathSource.getAttribute("aria-label") || mathSource.textContent);
      mathSource.classList.add("lex-curve-math-source");
      mathSource.setAttribute("aria-hidden", "true");
      [...mathSource.children].forEach(addAtom);
    }
    if (mathematical) formulaText.style.display = "none";
    const formulaPath = document.createElementNS(svgNamespace, "textPath");
    // Glyphs on a textPath rotate to the LOCAL segment slope. On a nearly
    // straight line the sampling jaggies are steep over a few units, so an
    // occasional letter swings ~45 degrees and collides with its neighbours.
    // The text rides its own copy of the curve whose slope is averaged across
    // roughly one glyph width, which leaves the drawn line untouched.
    const formulaGuideId = `${curveId}-text`;
    const formulaGuide = document.createElementNS(svgNamespace, "path");
    formulaGuide.setAttribute("id", formulaGuideId);
    formulaGuide.setAttribute("fill", "none");
    formulaGuide.setAttribute("stroke", "none");
    formulaPath.setAttribute("href", `#${formulaGuideId}`);
    formulaPath.setAttribute("startOffset", "50%");
    formulaPath.setAttribute("text-anchor", "middle");
    const curveVariables = (options.variables || []).map(variable => ({
      key: String(variable.key || variable.label || "").trim().toLocaleLowerCase(),
      spellings: [variable.label, ...(variable.tokens || [])].map(spelling =>
        String(spelling || "").trim()).filter(Boolean),
    })).filter(entry => entry.key && entry.spellings.length);
    const curveVariableSet = new Set(curveVariables.map(entry => entry.key));
    const spellingKey = new Map();
    for (const entry of curveVariables)
      for (const spelling of entry.spellings)
        if (!spellingKey.has(spelling.toLocaleLowerCase()))
          spellingKey.set(spelling.toLocaleLowerCase(), entry.key);
    const curveVariableKeys = curveVariables.map(entry => entry.key);
    const formulaContent = source => {
      if (source?.cloneNode) return source.cloneNode(true);
      const text = String(source ?? "");
      if (!spellingKey.size) return text;
      const escaped = [...spellingKey.keys()]
        .sort((left, right) => right.length - left.length)
        .map(key => key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      const matcher = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");
      const fragment = document.createDocumentFragment();
      let offset = 0;
      for (const match of text.matchAll(matcher)) {
        if (match.index > offset) fragment.append(text.slice(offset, match.index));
        fragment.append(element("span",
          {class: `lex-curve-variable-${spellingKey.get(match[0].toLocaleLowerCase())}`}, match[0]));
        offset = match.index + match[0].length;
      }
      if (offset < text.length) fragment.append(text.slice(offset));
      return fragment;
    };
    const appendFormulaTokens = (target, source) => {
      if (source == null) return;
      if (source.nodeType === Node.TEXT_NODE) {
        target.append(document.createTextNode(source.textContent || ""));
        return;
      }
      if (source.nodeType != null) {
        if (source.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
          [...source.childNodes].forEach(child => appendFormulaTokens(target, child));
          return;
        }
        const token = document.createElementNS(svgNamespace, "tspan");
        if (source.className) token.setAttribute("class", String(source.className));
        [...source.childNodes].forEach(child => appendFormulaTokens(token, child));
        target.append(token);
        return;
      }
      target.append(document.createTextNode(String(source)));
    };
    appendFormulaTokens(formulaPath, formulaContent(options.formula));
    formulaText.append(formulaPath);
    const guide = document.createElementNS(svgNamespace, "line");
    guide.setAttribute("class", "lex-curve-guide");
    const marker = document.createElementNS(svgNamespace, "path");
    marker.setAttribute("class", "lex-curve-point-marker");
    // Bars are a second reading of the same samples, drawn into their own
    // group so switching mode is a class change rather than a rebuild.
    const bars = document.createElementNS(svgNamespace, "g");
    bars.setAttribute("class", "lex-curve-bars");
    svg.append(grid, fill, bars, lineShadow, line, formulaGuide, rangeLow, rangeHigh, formulaText, guide, marker);

    const minimum = element("output", {class: "lex-curve-minimum"}, "—");
    const maximum = element("output", {class: "lex-curve-maximum"}, "—");
    const status = element("span", {class: "lex-curve-status", "aria-live": "polite"});
    const axisTop = element("span", {class: "lex-curve-axis lex-curve-axis-top"}, formatNumber(initialRange.max));
    const axisBottom = element("span", {class: "lex-curve-axis lex-curve-axis-bottom"}, formatNumber(initialRange.min));
    // Switch between the smooth line and a bar reading of the same samples.
    // The mode is a class on the plot, so nothing is redrawn. The toggle rides
    // in the variable drawer whenever one exists: the drawer overlays the
    // plot's bottom edge, so a toggle parked there ends up underneath it.
    const modeToggle = element("button", {
      type: "button",
      class: "lex-curve-mode-toggle",
      title: "Switch between line and bar view",
      "aria-pressed": "false",
      onclick: event => {
        event.preventDefault();
        event.stopPropagation();
        const bar = plot.classList.toggle("lex-curve-bar-mode");
        modeToggle.setAttribute("aria-pressed", String(bar));
        modeToggle.textContent = bar ? "LINE" : "BARS";
      },
    }, "BARS");
    const variables = element("div", {class: "lex-curve-variables lex-curve-variable-strip"},
      ...(options.variables || []).map(variable => {
        const key = String(variable.key || variable.label || "").trim().toLocaleLowerCase();
        return element("label", {class: "lex-curve-variable", "data-curve-variable": key},
          element("span", {class: `lex-curve-variable-name lex-curve-variable-${key}`}, variable.label), variable.control);
      }),
      ...(curveVariableKeys.length ? [modeToggle] : []));
    const tooltip = element("output", {class:"lex-curve-tooltip", "aria-live":"polite"});
    const hoverExtrema = element("div", {class:"lex-curve-hover-extrema", "aria-hidden":"true"},
      element("output", {class:"lex-curve-hover-minimum", title:"Curve minimum"}, "—"),
      element("output", {class:"lex-curve-hover-maximum", title:"Curve maximum"}, "—"));
    // The title is drawn INTO the plot, behind the drawing, so "centred in the
    // graph" means the graph rather than the card around it. The heading keeps
    // the text for a screen reader and stops painting it.
    const plot = element("div", {
      class: "lex-curve-plot",
      "data-curve-title": options.title || "CURVE",
      style:`--lex-curve-title-chars:${Math.max(1,String(options.title||"CURVE").length)}`,
    },
      svg,
      mathOverlay,
      axisTop,
      axisBottom,
      element("span", {class: "lex-curve-axis lex-curve-axis-start"}, formatNumber(domain.min)),
      element("span", {class: "lex-curve-axis lex-curve-axis-end"}, formatNumber(domain.max)),
      // Both axes are named, in the margin the plot now reserves for them.
      element("span", {class: "lex-curve-axis-name lex-curve-axis-name-x"},
        options.xLabel || "LEVEL"),
      element("span", {class: "lex-curve-axis-name lex-curve-axis-name-y"},
        options.yLabel || options.title || "VALUE"),
      options.overlayExtrema ? hoverExtrema : null,
      ...(curveVariableKeys.length ? [] : [modeToggle]),
      tooltip);
    const formulaBlock = element("div", {class: "lex-curve-formula"}, formulaContent(options.formula));
    const title = element("h4", {},
      element("span", {class: "lex-curve-heading-title"}, String(options.title || "CURVE").toLocaleUpperCase()));
    if (options.extremaInTitle) title.append(
      " ", element("span", {class: "lex-curve-heading-extrema"}, "[", minimum, " TO ", maximum, "]"));
    if (options.formulaInTitle && options.formula) title.append(
      " ", element("span", {class: "lex-curve-heading-formula"}, options.formula));
    const root = element("article", {
      class: ["lex-curve-editor", options.className || ""].filter(Boolean).join(" "),
      "data-curve-title": options.title || "CURVE",
      style:`--lex-curve-title-chars:${Math.max(1,String(options.title||"CURVE").length)}`,
      ...(options.attrs || {}),
    },
      element("header", {class: "lex-curve-heading"},
        title,
        options.extremaInTitle || options.overlayExtrema ? null : element("div", {class: "lex-curve-extrema"},
          element("span", {}, "MIN ", minimum),
          element("span", {}, "MAX ", maximum))),
      curveVariableKeys.length ? variables : null,
      plot,
      formulaBlock,
      status);

    const variableKeys = curveVariableSet;
    const linkFormulaTokens = () => {
      root.querySelectorAll("[data-curve-variable]").forEach(node => {
        if (node.classList.contains("lex-curve-variable")) return;
        delete node.dataset.curveVariable;
      });
      const formulaTokens = [...root.querySelectorAll(".lex-curve-path-formula [class], .lex-curve-math-atom [class]")];
      formulaTokens.forEach(token => {
        const match = [...token.classList].find(name => {
          if (!name.startsWith("lex-curve-variable-")) return false;
          const key = name.slice("lex-curve-variable-".length);
          return variableKeys.has(key);
        });
        if (match) token.dataset.curveVariable = match.slice("lex-curve-variable-".length);
      });
    };
    linkFormulaTokens();
    const highlightVariable = key => {
      for (const entry of root.querySelectorAll(".lex-curve-variable")) {
        entry.classList.toggle("lex-curve-variable-active",
          Boolean(key) && entry.dataset.curveVariable === key);
      }
      root.querySelectorAll("[data-curve-variable]").forEach(node =>
        node.classList.toggle("lex-curve-variable-highlight", !!key && node.dataset.curveVariable === key));
    };
    root.addEventListener("pointerover", event => highlightVariable(event.target.closest("[data-curve-variable]")?.dataset.curveVariable || ""));
    root.addEventListener("pointerout", event => {
      if (!root.contains(event.relatedTarget)) highlightVariable("");
      else highlightVariable(event.relatedTarget?.closest?.("[data-curve-variable]")?.dataset.curveVariable || "");
    });
    root.addEventListener("focusin", event => highlightVariable(event.target.closest("[data-curve-variable]")?.dataset.curveVariable || ""));
    root.addEventListener("focusout", event => highlightVariable(event.relatedTarget?.closest?.("[data-curve-variable]")?.dataset.curveVariable || ""));
    const clearProbe = () => {
      tooltip.textContent = "";
      guide.removeAttribute("x1");
      guide.removeAttribute("x2");
      guide.removeAttribute("y1");
      guide.removeAttribute("y2");
      marker.removeAttribute("d");
    };
    root.addEventListener("pointermove", event => {
      const bounds = svg.getBoundingClientRect();
      if (!bounds.width || !bounds.height || !svg.contains(event.target)) return;
      const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
      const x = Math.round(domain.min + ratio * (domain.max - domain.min));
      const raw = options.evaluate?.(x);
      const y = Number(raw);
      if (raw == null || !Number.isFinite(y)) { clearProbe(); return; }
      const range = getRange();
      const spanX = Math.max(1, domain.max - domain.min);
      const spanY = Math.max(1, range.max - range.min);
      // In bar mode a value owns a slot, not a point: the line's x for level N
      // is the slot's left edge, so the guide and the X marker landed in the
      // gap between two bars rather than on the bar being read.
      const slots = Math.max(1, domain.max - domain.min + 1);
      const barMode = plot.classList.contains("lex-curve-bar-mode");
      const graphX = barMode
        ? ((x - domain.min) + .5) / slots * 320
        : (x - domain.min) / spanX * 320;
      const bounded = Math.max(range.min, Math.min(range.max, y));
      const graphY = graphHeight - (bounded - range.min) / spanY * graphHeight;
      const cursorY = Math.max(0, Math.min(graphHeight, (event.clientY - bounds.top) / bounds.height * graphHeight));
      guide.setAttribute("x1", graphX.toFixed(2));
      guide.setAttribute("x2", graphX.toFixed(2));
      guide.setAttribute("y1", cursorY.toFixed(2));
      guide.setAttribute("y2", graphY.toFixed(2));
      marker.setAttribute("d", `M${(graphX - 4).toFixed(2)} ${(graphY - 4).toFixed(2)}L${(graphX + 4).toFixed(2)} ${(graphY + 4).toFixed(2)}M${(graphX + 4).toFixed(2)} ${(graphY - 4).toFixed(2)}L${(graphX - 4).toFixed(2)} ${(graphY + 4).toFixed(2)}`);
      tooltip.textContent = `(${formatNumber(x)}, ${formatNumber(y, options.valueFormat || {})})`;
      options.onProbe?.(x);
      const plotBounds = plot.getBoundingClientRect();
      const tooltipBounds = tooltip.getBoundingClientRect();
      const inset = 4;
      const halfWidth = tooltipBounds.width / 2;
      /* Centre the readout on the pointer across neighbouring graph space.
         Clamp only at the real edge - the nearest panel that clips or
         scrolls, else the window. Clamping to each small plot made the label
         drift from the cursor near every card boundary; clamping only to the
         window let it poke out of its panel, which grew a scrollbar and
         shifted the graphs when the pointer came in from the right (GFs). */
      let edge = {left:0, right:innerWidth};
      for (let node = plot.parentElement; node && node !== document.body; node = node.parentElement) {
        if (!/auto|scroll|hidden|clip/.test(getComputedStyle(node).overflowX)) continue;
        const box = node.getBoundingClientRect();
        edge = {left:box.left + node.clientLeft, right:box.left + node.clientLeft + node.clientWidth};
        break;
      }
      const viewportCenter = Math.max(edge.left + inset + halfWidth,
        Math.min(edge.right - inset - halfWidth, event.clientX));
      tooltip.style.left = `${viewportCenter - plotBounds.left}px`;
      tooltip.style.top = `${Math.max(8, bounds.top - plotBounds.top + graphY / graphHeight * bounds.height)}px`;
    });
    plot.addEventListener("pointerleave", () => { clearProbe(); highlightVariable(""); });

    const fitFormula = () => {
      formulaText.style.removeProperty("font-size");
      formulaPath.setAttribute("startOffset", "50%");
      formulaText.setAttribute("dy", "-7");
      const natural = formulaText.getComputedTextLength?.() || 0;
      const pathLength = line.getTotalLength?.() || 0;
      // Use most of the drawn line. The old .78 factor, the 256 cap and a 76
      // unit reserve together left a 51-character formula only 175 units, so
      // it had to shrink to 6.6px to fit and became unreadable.
      const endsReserve = 44;
      const available = Math.min(300, Math.max(0, pathLength * .92 - endsReserve));
      // NO letter-spacing stretch. Spreading the text to fill the path turned
      // every formula into "S T R ( L ) = c l a m p", which reads as spaced
      // gibberish rather than as an equation. The text is set at its natural
      // spacing, centred on the path, and only the TYPE SIZE gives way when
      // the equation is too long for the line.
      if (available > 0 && natural > available) {
        const baseSize = parseFloat(getComputedStyle(formulaText).fontSize) || 10;
        let size = baseSize;
        let width = natural;
        for (let pass = 0; pass < 10 && width > available && size > 4.5; pass++) {
          size = Math.max(4.5, size * (available / width) * .98);
          formulaText.style.fontSize = `${size}px`;
          width = formulaText.getComputedTextLength?.() || width;
        }
      }
      const box = formulaText.getBBox?.();
      if (box && pathLength > 0) {
        const leftInset = 16, rightInset = 304;
        let offset = 50;
        if (box.x < leftInset) offset += (leftInset - box.x) / pathLength * 100;
        if (box.x + box.width > rightInset) offset -= (box.x + box.width - rightInset) / pathLength * 100;
        formulaPath.setAttribute("startOffset", `${Math.max(10, Math.min(90, offset))}%`);
        const shifted = formulaText.getBBox();
        let dy = -7;
        if (shifted.y < 4) dy += 4 - shifted.y;
        if (shifted.y + shifted.height > 156) dy -= shifted.y + shifted.height - 156;
        formulaText.setAttribute("dy", String(dy));
      }
    };

    // Real hitboxes, not an estimate: every rendered glyph is asked for its
    // own start point, rotation and extent, turned into the quad it actually
    // occupies, and tested against its neighbours with a separating axis.
    // The viewport height follows the card. Measure angles and overlaps in
    // screen space so resizing and browser zoom keep glyph geometry uniform.
    const plotScale = () => {
      const box = svg.getBoundingClientRect();
      return {x: (box.width || 320) / 320, y: (box.height || graphHeight) / graphHeight};
    };
    const glyphQuads = () => {
      const count = formulaText.getNumberOfChars?.() ?? 0;
      if (!count) return null;
      const characters = formulaText.textContent || "";
      // Height from the type size, NOT from getExtentOfChar: that returns the
      // AXIS-ALIGNED box of an already-rotated glyph, so rotating it again
      // inflates every letter and reports collisions on a dead straight line.
      // The baseline start and end points give the advance exactly, whatever
      // the rotation, and the em box gives the height.
      const size = parseFloat(getComputedStyle(formulaText).fontSize) || 10;
      const rise = size * .74, drop = size * .2;
      const quads = [];
      for (let index = 0; index < count; index++) {
        if (!characters[index] || characters[index] === " ") continue;
        let start, end;
        try {
          start = formulaText.getStartPositionOfChar(index);
          end = formulaText.getEndPositionOfChar(index);
        } catch { return null; }
        const advanceX = end.x - start.x, advanceY = end.y - start.y;
        const advance = Math.hypot(advanceX, advanceY);
        if (!(advance > 0)) continue;
        const alongX = advanceX / advance, alongY = advanceY / advance;
        const upX = alongY, upY = -alongX;
        const corner = (along, up) => ({
          x: start.x + alongX * along + upX * up,
          y: start.y + alongY * along + upY * up,
        });
        // The advance is wider than the ink; a tenth off each side stands in
        // for the side bearings, so this tests ink against ink.
        const bearing = Math.min(advance * .1, .9);
        quads.push([corner(bearing, rise), corner(advance - bearing, rise),
          corner(advance - bearing, -drop), corner(bearing, -drop)]);
      }
      if (quads.length < 2) return null;
      const zoom = plotScale();
      return quads.map(quad => quad.map(point => ({x: point.x * zoom.x, y: point.y * zoom.y})));
    };
    const quadsCollide = (a, b) => {
      let worst = Infinity;
      for (const source of [a, b]) {
        for (let index = 0; index < 4; index++) {
          const from = source[index], to = source[(index + 1) % 4];
          const length = Math.hypot(to.x - from.x, to.y - from.y) || 1;
          const axisX = -(to.y - from.y) / length, axisY = (to.x - from.x) / length;
          const span = quad => {
            let low = Infinity, high = -Infinity;
            for (const point of quad) {
              const projected = point.x * axisX + point.y * axisY;
              if (projected < low) low = projected;
              if (projected > high) high = projected;
            }
            return [low, high];
          };
          const [aLow, aHigh] = span(a), [bLow, bHigh] = span(b);
          const depth = Math.min(aHigh, bHigh) - Math.max(aLow, bLow);
          if (depth <= 0) return 0;
          if (depth < worst) worst = depth;
        }
      }
      return worst;
    };
    // Returns the worst penetration in screen pixels, so the search can be
    // inspected rather than only obeyed.
    const formulaWorstBite = () => {
      const quads = glyphQuads();
      if (!quads) return 0;
      // Neighbouring glyph boxes abut by design, so a shared edge is not a
      // collision - only a real bite out of the letter beside it is. Three
      // back, because a tight corner can throw a glyph past its neighbour.
      let worst = 0;
      for (let index = 1; index < quads.length; index++) {
        for (let other = index - 1; other >= Math.max(0, index - 3); other--) {
          worst = Math.max(worst, quadsCollide(quads[index], quads[other]));
        }
      }
      return worst;
    };
    // Closest to the curve first, then progressively straighter. FOLLOWING
    // the line is the point, so the ladder gives up curvature before it gives
    // up angle: text at 45 screen degrees is perfectly readable, text that has
    // wandered off the line it describes is not. The last rung is flat, so the
    // search always ends somewhere legible.
    const guideSteps = [
      {angle: 46, sigma: 9}, {angle: 46, sigma: 16}, {angle: 40, sigma: 26},
      {angle: 34, sigma: 40}, {angle: 24, sigma: 80}, {angle: 0, sigma: 320},
    ];
    const layoutFormula = buildGuide => {
      const bites = [];
      for (let step = 0; step < guideSteps.length; step++) {
        formulaGuide.setAttribute("d", buildGuide(guideSteps[step]));
        fitFormula();
        bites.push(Number(formulaWorstBite().toFixed(3)));
        root.dataset.formulaGuideBites = bites.join(",");
        if (step === guideSteps.length - 1 || bites[step] <= .2) {
          // Which gentleness this curve settled on, so the search can be seen
          // to be doing something rather than assumed to be.
          root.dataset.formulaGuideStep = String(step);
          return step;
        }
      }
    };

    const positionMath = () => {
      if (!mathOverlay || !root.isConnected || !line.getAttribute("d")) return;
      const length = line.getTotalLength(), matrix = svg.getScreenCTM();
      if (!length || !matrix) return;
      const bounds = plot.getBoundingClientRect(), scale = bounds.width / plot.offsetWidth || 1;
      if (mathSource) {
        const overlayBounds = mathOverlay.getBoundingClientRect();
        const unit = Math.hypot(matrix.a, matrix.b) / scale;
        if (!unit) return;
        mathOverlay.style.removeProperty("font-size");
        const available = length * unit * .8;
        const naturalWidth = mathSource.getBoundingClientRect().width / scale;
        if (naturalWidth > available) {
          const size = parseFloat(getComputedStyle(mathOverlay).fontSize);
          mathOverlay.style.fontSize = `${size * available / naturalWidth}px`;
        }
        const sourceBounds = mathSource.getBoundingClientRect();
        for (const {source, visual} of mathAtoms) {
          const box = source.getBoundingClientRect();
          const offset = (box.left + box.width / 2 - sourceBounds.left - sourceBounds.width / 2) / scale;
          const distance = Math.max(0, Math.min(length, length / 2 + offset / unit));
          // The tilt is measured over a window of about two levels of the x
          // axis, not over the term's own width. A stat that grows in whole
          // points moves up one step about every level, and a narrow window
          // can sit entirely inside one step: neighbouring terms then took
          // wildly different angles and the equation read as a seesaw with
          // each term tilted to nothing in particular. A window this wide
          // averages the steps and still follows a curve that really bends.
          const delta = Math.max(2, Math.min(8, length / 40));
          const sample = at => {
            const point = line.getPointAtLength(Math.max(0, Math.min(length, at)));
            return new DOMPoint(point.x, point.y).matrixTransform(matrix);
          };
          const center = sample(distance), before = sample(distance - delta), after = sample(distance + delta);
          const angle = Math.atan2(after.y - before.y, after.x - before.x);
          visual.style.left = `${(center.x - overlayBounds.left) / scale + Math.sin(angle) * 7}px`;
          visual.style.top = `${(center.y - overlayBounds.top) / scale - Math.cos(angle) * 7}px`;
          // Bounded like the single-formula case: a curve that climbs and then
          // comes back down - a MAG curve with a large quadratic term does -
          // turns a term nearly on its side, and the equation reads as a seesaw
          // instead of as a formula. It still follows the curve; it just stops
          // short of the point where following it costs the reader the text.
          const degrees = Math.max(-40, Math.min(40, angle * 180 / Math.PI));
          visual.style.setProperty("--lex-formula-angle", `${degrees}deg`);
        }
        return;
      }
      const point = ratio => {
        const value = line.getPointAtLength(length * ratio);
        return new DOMPoint(value.x,value.y).matrixTransform(matrix);
      };
      const center = point(.5), before = point(.47), after = point(.53);
      const angle = Math.max(-40,Math.min(40,Math.atan2(after.y-before.y,after.x-before.x)*180/Math.PI));
      mathOverlay.style.left = `${(center.x-bounds.left)/scale}px`;
      mathOverlay.style.top = `${(center.y-bounds.top)/scale-7}px`;
      mathOverlay.style.setProperty("--lex-formula-angle",`${angle}deg`);
      mathOverlay.style.removeProperty("font-size");
      const available = svg.getBoundingClientRect().width / scale * .84;
      if (mathOverlay.scrollWidth > available) {
        const size = parseFloat(getComputedStyle(mathOverlay).fontSize);
        mathOverlay.style.fontSize = `${Math.max(7.5,size*available/mathOverlay.scrollWidth)}px`;
      }
    };
    if (mathOverlay && typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(positionMath);
      observer.observe(plot);
    }
    if (mathOverlay) document.fonts?.ready.then(positionMath);

    // The samples joined by a curve through every one of them, instead of a
    // straight line between each pair. A level's value is a number at that
    // level, and the polyline said something else: a stat that grew by one
    // every five levels came out as five flat steps and a jump, which is the
    // staircase a reader saw. The tangents are Fritsch-Carlson, so the curve
    // passes through each sample and never overshoots one: a stat that only
    // rises never dips between two levels.
    const curvePath = points => {
      const flat = () => points.map(([x, y], index) =>
        `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
      if (points.length < 3) return flat();
      const slopes = points.slice(1).map(([x, y], index) =>
        (y - points[index][1]) / ((x - points[index][0]) || 1));
      const tangents = points.map((_, index) => {
        if (index === 0) return slopes[0];
        if (index === points.length - 1) return slopes[slopes.length - 1];
        const before = slopes[index - 1], after = slopes[index];
        if (before * after <= 0) return 0;
        const runBack = points[index][0] - points[index - 1][0];
        const runForward = points[index + 1][0] - points[index][0];
        const first = 2 * runForward + runBack, second = runForward + 2 * runBack;
        return (first + second) / (first / before + second / after);
      });
      // Fritsch-Carlson's monotonicity pass: clamp the tangents of any interval
      // whose ends would otherwise turn the curve past its own samples.
      for (let index = 0; index < points.length - 1; index += 1) {
        const run = points[index + 1][0] - points[index][0];
        const slope = run ? (points[index + 1][1] - points[index][1]) / run : 0;
        if (!slope) { tangents[index] = 0; tangents[index + 1] = 0; continue; }
        const alpha = tangents[index] / slope, beta = tangents[index + 1] / slope;
        const overshoot = alpha * alpha + beta * beta;
        if (overshoot > 9) {
          const scale = 3 / Math.sqrt(overshoot);
          tangents[index] = scale * alpha * slope;
          tangents[index + 1] = scale * beta * slope;
        }
      }
      const commands = [`M${points[0][0].toFixed(2)} ${points[0][1].toFixed(2)}`];
      for (let index = 1; index < points.length; index += 1) {
        const [x0, y0] = points[index - 1], [x1, y1] = points[index];
        const third = (x1 - x0) / 3;
        commands.push(`C${(x0 + third).toFixed(2)} ${(y0 + tangents[index - 1] * third).toFixed(2)} `
          + `${(x1 - third).toFixed(2)} ${(y1 - tangents[index] * third).toFixed(2)} `
          + `${x1.toFixed(2)} ${y1.toFixed(2)}`);
      }
      return commands.join(" ");
    };
    const draw = () => {
      const bounds=svg.getBoundingClientRect();
      if(bounds.width>0&&bounds.height>0){
        // A box that moves right after our own viewBox write, with width
        // unchanged, is following us rather than the layout (#527): hold the
        // sizing so the loop settles instead of growing. The hold lasts until
        // the box moves on its own or the width changes; both adopt again.
        const adopt=()=>{
          const aspect=320*bounds.height/bounds.width;
          wroteViewBox=Math.abs(aspect-graphHeight)>1e-6;
          if(wroteViewBox){graphHeight=aspect;heldSize=false;}
        };
        if(bounds.width!==lastBoxWidth)adopt();
        else if(bounds.height===lastBoxHeight){if(!heldSize)adopt();}
        else if(!wroteViewBox)adopt();
        else{heldSize=true;wroteViewBox=false;}
        lastBoxWidth=bounds.width;lastBoxHeight=bounds.height;
      }
      svg.setAttribute('viewBox',`0 0 320 ${graphHeight}`);
      grid.setAttribute('d',Array.from({length:5},(_,i)=>`M0 ${graphHeight*i/4}H320 M${80*i} 0V${graphHeight}`).join(' '));
      const range = getRange();
      axisTop.textContent = formatNumber(range.max);
      axisBottom.textContent = formatNumber(range.min);
      const samples = [];
      const first = Math.ceil(domain.min), last = Math.floor(domain.max);
      for (let x = first; x <= last; x += 1) {
        const raw = options.evaluate?.(x);
        const value = Number(raw);
        if (raw == null || !Number.isFinite(value)) continue;
        samples.push({x, value});
      }
      if (!samples.length) {
        line.removeAttribute("d");
        fill.removeAttribute("d");
        bars.replaceChildren();
        rangeLow.textContent = rangeHigh.textContent = "";
        if (mathOverlay) mathOverlay.hidden = true;
        minimum.textContent = maximum.textContent = "—";
        status.textContent = options.invalidText || "INVALID CURVE";
        root.classList.add("invalid");
        return;
      }
      root.classList.remove("invalid");
      if (mathOverlay) mathOverlay.hidden = false;
      status.textContent = "";
      const values = samples.map(sample => sample.value);
      minimum.textContent = formatNumber(Math.min(...values), options.valueFormat || {});
      maximum.textContent = formatNumber(Math.max(...values), options.valueFormat || {});
      hoverExtrema.firstElementChild.textContent = minimum.textContent;
      hoverExtrema.lastElementChild.textContent = maximum.textContent;
      const width = 320, height = graphHeight, spanX = Math.max(1, domain.max - domain.min), spanY = Math.max(1, range.max - range.min);
      const points = samples.map(sample => {
        const x = (sample.x - domain.min) / spanX * width;
        const bounded = Math.max(range.min, Math.min(range.max, sample.value));
        const y = height - (bounded - range.min) / spanY * height;
        return [x, y];
      });
      // Sit the extremes on the ends of the drawn line, in the formula's own
      // style, so the reader gets min - formula - max along the curve.
      if (points.length) {
        const first = points[0], last = points[points.length - 1];
        rangeLow.textContent = formatNumber(samples[0]?.value ?? range.min, {useGrouping: true});
        rangeHigh.textContent = formatNumber(samples[samples.length - 1]?.value ?? range.max, {useGrouping: true});
        // The line's own height at a given x. A number beside the curve has to
        // be placed against the line where the number sits, not against the
        // endpoint it was measured from: the XP curve climbs steeply over its
        // first few levels, so an offset from the first point alone left the
        // minimum sitting on the line a sample later.
        const heightAt = x => {
          if (x <= points[0][0]) return points[0][1];
          for (let index = 1; index < points.length; index += 1) {
            const [x0, y0] = points[index - 1], [x1, y1] = points[index];
            if (x <= x1) return x1 === x0 ? y1 : y0 + (y1 - y0) * (x - x0) / (x1 - x0);
          }
          return points[points.length - 1][1];
        };
        // Sitting AT the ends was not the same as following the line: on a
        // steep curve a level number reads as unrelated to it. Each extreme
        // now takes the slope of the curve at its own end, measured a few
        // samples in so one jagged sample cannot swing it, and clamped so a
        // near-vertical climb never turns the number on its side.
        const slopeAngle = (from, to) => {
          if (!from || !to) return 0;
          const run = to[0] - from[0];
          if (Math.abs(run) < 0.01) return 0;
          const degrees = Math.atan2(to[1] - from[1], run) * 180 / Math.PI;
          return Math.max(-38, Math.min(38, degrees)) * Math.PI / 180;
        };
        const reach = Math.max(1, Math.min(2, points.length - 1));
        const lowAngle = slopeAngle(points[0], points[reach]);
        const highAngle = slopeAngle(points[points.length - 1 - reach], points[points.length - 1]);
        // The number leaves the line along the line's own normal, and the
        // placement is then checked against the line that was actually drawn.
        // A vertical lift drifts back onto a steep curve a few pixels later -
        // that is what put the greatest value on top of the XP curve's own
        // line - and a perpendicular lift alone only answers that for a curve
        // that is roughly straight: at the foot of a near-vertical climb there
        // is no room on either side. So each candidate is measured against the
        // drawn samples, nearest first, and the first one that clears wins.
        const lift = 10, glyph = 9, clearance = 5;
        const offsetFrom = (x, baseY, angle, above, distance) => {
          const side = above ? 1 : -1;
          return {x: x + Math.sin(angle) * side * distance,
                  y: baseY - Math.cos(angle) * side * distance};
        };
        const distanceToSegment = (px, py, ax, ay, bx, by) => {
          const dx = bx - ax, dy = by - ay;
          const lengthSquared = dx * dx + dy * dy;
          const t = lengthSquared ? Math.max(0, Math.min(1,
            ((px - ax) * dx + (py - ay) * dy) / lengthSquared)) : 0;
          return Math.hypot(px - (ax + dx * t), py - (ay + dy * t));
        };
        // How far the turned number's own baseline is from the nearest drawn
        // sample. Text sits on the baseline, so the letters are the segment
        // the value is written along, not the box around them.
        const labelClearance = (point, angle, width, fromEnd) => {
          const direction = fromEnd ? -width : width;
          const endX = point.x + Math.cos(angle) * direction;
          const endY = point.y + Math.sin(angle) * direction;
          let best = Infinity;
          for (const [x, y] of points) {
            const distance = distanceToSegment(x, y, point.x, point.y, endX, endY);
            if (distance < best) best = distance;
          }
          return best;
        };
        const placeLabel = (baseX, baseY, angle, width, fromEnd, limits) => {
          for (const distance of [lift, lift + 7, lift + 14]) {
            for (const above of [true, false]) {
              const point = offsetFrom(baseX, baseY, angle, above,
                                       above ? distance : distance + glyph);
              if (point.y < 9 || point.y > graphHeight - 4) continue;
              if (point.x < limits[0] || point.x > limits[1]) continue;
              if (labelClearance(point, angle, width, fromEnd) >= clearance) return point;
            }
          }
          return offsetFrom(baseX, baseY, angle, true, lift);
        };
        const lowWidth = rangeLow.getComputedTextLength() || 12;
        const highWidth = rangeHigh.getComputedTextLength() || 12;
        const lowBaseX = Math.max(10, first[0] + 2);
        const low = placeLabel(lowBaseX, heightAt(lowBaseX), lowAngle,
                               lowWidth, false, [2, 300]);
        const highBaseX = Math.min(310, last[0] - 2);
        const high = placeLabel(highBaseX, heightAt(highBaseX), highAngle,
                                highWidth, true, [20, 314]);
        const lowX = low.x, lowY = low.y, highX = high.x, highY = high.y;
        rangeLow.setAttribute("x", String(lowX));
        rangeLow.setAttribute("y", String(lowY));
        rangeHigh.setAttribute("x", String(highX));
        rangeHigh.setAttribute("y", String(highY));
        rangeLow.setAttribute("transform",
          `rotate(${(lowAngle * 180 / Math.PI).toFixed(2)} ${lowX} ${lowY})`);
        rangeHigh.setAttribute("transform",
          `rotate(${(highAngle * 180 / Math.PI).toFixed(2)} ${highX} ${highY})`);
      }
      // ONE BAR PER X VALUE. This used to average the samples into 32 fixed
      // buckets, which drew bars of an arbitrary width that lined up with
      // nothing: a bar spanned three levels and its height was the mean of
      // them, so reading a level off the bar view was impossible. Each sample
      // is one level, so each level gets its own bar at its own height.
      const zeroY = height - (Math.max(range.min, Math.min(range.max, 0)) - range.min) / spanY * height;
      const slotWidth = width / points.length;
      bars.replaceChildren(...points.map(([, y], index) => {
        const rect = document.createElementNS(svgNamespace, "rect");
        // A hairline gap only while the bars are wide enough to show one;
        // at 100 levels the bars are thin and a gap would eat them.
        const gap = slotWidth > 2.5 ? slotWidth * .18 : 0;
        rect.setAttribute("x", (index * slotWidth + gap / 2).toFixed(2));
        rect.setAttribute("width", Math.max(.4, slotWidth - gap).toFixed(2));
        rect.setAttribute("y", Math.min(y, zeroY).toFixed(2));
        rect.setAttribute("height", Math.abs(zeroY - y).toFixed(2));
        return rect;
      }));
      const path = curvePath(points);
      line.setAttribute("d", path);
      lineShadow.setAttribute("d", path);
      fill.setAttribute("d", `${path} L${points.at(-1)[0].toFixed(2)} ${zeroY} L${points[0][0].toFixed(2)} ${zeroY} Z`);
      // The formula rides its own guide path, and a glyph on a textPath takes
      // the LOCAL slope of that path. Clamping the guide's steepest ANGLE was
      // not enough on its own: what makes letters collide is how fast the
      // angle CHANGES. Two glyphs sitting above a corner swing toward each
      // other by their own height times the turn between them, so a
      // stairstep curve - MAG and STR are the worst - overlapped its own text
      // at angles that are each individually readable. The guide is therefore
      // built at a chosen gentleness, the real glyph boxes are MEASURED, and
      // the guide is rebuilt gentler until no two letters touch.
      const glyphWidth = width / 44;
      const buckets = [];
      for (const [x, y] of points) {
        const slot = Math.floor(x / glyphWidth);
        const bucket = buckets[slot] || (buckets[slot] = {x: 0, y: 0, n: 0});
        bucket.x += x; bucket.y += y; bucket.n++;
      }
      const sampled = buckets.filter(Boolean).map(b => [b.x / b.n, b.y / b.n]);
      // A polyline through bucket averages is never smooth: neighbouring
      // segments differ by whatever the sampling jitter was, so the baseline
      // wobbles glyph by glyph however hard it is smoothed. A least-squares
      // parabola was smooth but UNFAITHFUL - on a log-shaped stat curve the
      // text drifted up to 28 degrees away from the line it describes, which
      // is the opposite of following the graph. The guide is instead the real
      // curve under a wide Gaussian: faithful to its shape, with the stairstep
      // averaged out over several glyph widths.
      const blur = sigma => {
        const twoSigmaSquared = 2 * sigma * sigma;
        return sampled.map(([x]) => {
          let total = 0, weightSum = 0;
          for (const [sampleX, sampleY] of points) {
            const offset = sampleX - x;
            if (Math.abs(offset) > sigma * 3) continue;
            const weight = Math.exp(-offset * offset / twoSigmaSquared);
            total += weight * sampleY; weightSum += weight;
          }
          return [x, weightSum ? total / weightSum : 0];
        });
      };
      const buildGuide = ({angle, sigma}) => {
        const shape = blur(sigma);
        const zoom = plotScale();
        // The clamp is on the SCREEN angle, converted back into user units by
        // the plot's own stretch, so "no steeper than 46 degrees" means what
        // it looks like rather than what the viewBox says.
        const maxRise = Math.tan(angle * Math.PI / 180) * zoom.x / Math.max(zoom.y, 1e-6);
        const guide = [];
        for (const [x, y] of shape) {
          if (!guide.length) { guide.push([x, y]); continue; }
          const [previousX, previousY] = guide[guide.length - 1];
          const run = Math.max(0.01, x - previousX);
          const limit = run * maxRise;
          const rise = Math.max(-limit, Math.min(limit, y - previousY));
          guide.push([x, previousY + rise]);
        }
        return guide
          .map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`)
          .join(" ");
      };
      if (mathOverlay) {
        positionMath();
        requestAnimationFrame(positionMath);
      } else {
        layoutFormula(buildGuide);
        requestAnimationFrame(() => layoutFormula(buildGuide));
      }
    };
    let pending = false;
    const scheduleDraw = () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; draw(); });
    };
    // Listen in the capture phase. Provenance controls can rebuild their
    // reference rail during the same event. The curve must still redraw from
    // the newly written model value before focus leaves the input.
    root.addEventListener("input", scheduleDraw, true);
    root.addEventListener("change", scheduleDraw, true);
    if(typeof ResizeObserver!=="undefined")new ResizeObserver(scheduleDraw).observe(svg);
    draw();
    root.refreshCurve = draw;
    root.refreshFormula = source => {
      formulaPath.replaceChildren();
      appendFormulaTokens(formulaPath, formulaContent(source));
      if (mathOverlay && source?.classList?.contains("lex-math-formula")) {
        const fresh = source.cloneNode(true);
        const math = fresh.querySelector(":scope > math");
        mathOverlay.replaceChildren();
        mathAtoms.length = 0;
        if (math) {
          math.classList.add("lex-curve-math-source");
          math.setAttribute("aria-hidden", "true");
          mathOverlay.append(math);
          mathSource = math;
          [...math.children].forEach(addAtom);
        } else mathSource = null;
      }
      formulaBlock.replaceChildren(formulaContent(source));
      linkFormulaTokens();
      draw();
    };
    return root;
  };

  const closeButton = (attrs = {}) => {
    const {class: className = "", title = "Close", "aria-label": ariaLabel = title, ...rest} = attrs;
    return element("button", {
      type: "button", ...rest,
      class: ["lex-close-button lex-ui-symbol", className].filter(Boolean).join(" "),
      title, "aria-label": ariaLabel,
    }, element("span", {class: "lex-close-icon", "aria-hidden": "true"}));
  };

  const clone = value => structuredClone(value);
  const signature = value => JSON.stringify(value, (_key, item) => {
    if (item instanceof Set) return {__lexSet: [...item]};
    if (item instanceof Map) return {__lexMap: [...item.entries()]};
    return item;
  });

  const applyTheme = theme => {
    for (const [name, value] of Object.entries(theme || {})) {
      document.documentElement.style.setProperty(`--lex-${name}`, value);
    }
  };

  class EditHistory {
    constructor(options) {
      this.capture = options.capture;
      this.restore = options.restore;
      this.render = options.render || (() => {});
      this.enabled = options.enabled || (() => true);
      this.changed = options.changed || (() => {});
      this.limit = options.limit || 50;
      this.undoStack = [];
      this.redoStack = [];
      this.applying = false;
      this.pending = null;
      // The last snapshot known to match the data, and its signature. A copy
      // of a large plugin's data takes a few hundred milliseconds, and every
      // click and every slider step asks for a "before"; when nothing has
      // changed since the last snapshot, that snapshot is the before.
      this.known = null;
    }

    get canUndo() { return this.undoStack.length > 0; }
    get canRedo() { return this.redoStack.length > 0; }

    clear() {
      this.undoStack = [];
      this.redoStack = [];
      this.pending = null;
      this.changed(this);
    }

    begin(label = "Edit", source = "") {
      if (this.applying || this.pending || !this.enabled()) return;
      const current = this.capture();
      const beforeSignature = signature(current);
      const before = this.known?.signature === beforeSignature ? this.known.snapshot : clone(current);
      this.known = {signature: beforeSignature, snapshot: before};
      this.pending = {label, source, before, beforeSignature};
      setTimeout(() => this.finish(), 0);
    }

    finish() {
      const pending = this.pending;
      this.pending = null;
      if (!pending || this.applying) return;
      const current = this.capture();
      const afterSignature = signature(current);
      if (afterSignature === pending.beforeSignature) return;
      const after = clone(current);
      this.known = {signature: afterSignature, snapshot: after};
      const now = Date.now();
      const last = this.undoStack.at(-1);
      if (last && pending.source && last.source === pending.source && now - last.time < 700 &&
          last.afterSignature === pending.beforeSignature) {
        last.after = after;
        last.afterSignature = afterSignature;
        last.time = now;
        last.at = nextHistoryTick();
      } else {
        this.undoStack.push({...pending, after, afterSignature, time: now, at: nextHistoryTick()});
        if (this.undoStack.length > this.limit) this.undoStack.shift();
      }
      this.redoStack = [];
      this.changed(this);
    }

    async apply(snapshot) {
      this.applying = true;
      this.known = null;
      try {
        await this.restore(clone(snapshot));
        await this.render();
      } finally {
        this.applying = false;
        this.changed(this);
      }
    }

    async undo() {
      this.finish();
      const command = this.undoStack.pop();
      if (!command) return false;
      this.redoStack.push(command);
      await this.apply(command.before);
      return true;
    }

    async redo() {
      this.finish();
      const command = this.redoStack.pop();
      if (!command) return false;
      this.undoStack.push(command);
      await this.apply(command.after);
      return true;
    }

    observe(root = document) {
      const begin = event => {
        // Moving between tabs, subtabs and pages edits nothing.
        if (event.target.closest?.("[data-lex-history-control],nav [data-tab],.lex-subtab-button,.lex-pager")) return;
        const control = event.target.closest?.("input,select,textarea,button,[role=button]");
        const source = control ? [
          document.body.dataset.lexPlugin || "plugin",
          control.id || control.name || control.getAttribute("aria-label") || control.title || control.placeholder || control.textContent?.trim().slice(0, 40),
        ].join(":") : event.type;
        this.begin(control?.title || control?.getAttribute("aria-label") || "Edit", source);
      };
      for (const eventName of ["input", "change", "click"]) {
        root.addEventListener(eventName, begin, true);
      }
      // No key binding here: the shell's shortcut dispatcher is the only
      // Ctrl+Z handler, and a second one undid twice per press.
    }
  }

  class NavigationHistory {
    constructor(options) {
      this.apply = options.apply;
      this.changed = options.changed || (() => {});
      this.limit = Math.max(2, Number(options.limit) || 100);
      this.entries = [];
      this.index = -1;
      this.applying = false;
      if (options.initial) this.visit(options.initial);
    }

    get canBack() { return this.index > 0; }
    get canForward() { return this.index >= 0 && this.index + 1 < this.entries.length; }
    get current() { return this.entries[this.index] || null; }

    visit(destination) {
      const normalized = String(destination || "");
      if (!normalized || this.applying || normalized === this.current) return false;
      this.entries.splice(this.index + 1);
      this.entries.push(normalized);
      if (this.entries.length > this.limit) this.entries.shift();
      this.index = this.entries.length - 1;
      this.changed(this);
      return true;
    }

    async go(direction) {
      const step = Number(direction) < 0 ? -1 : Number(direction) > 0 ? 1 : 0;
      const target = this.index + step;
      if (!step || target < 0 || target >= this.entries.length || this.applying) return false;
      const previous = this.index;
      this.index = target;
      this.applying = true;
      try {
        if (await this.apply(this.entries[target]) === false) {
          this.index = previous;
          return false;
        }
        return true;
      } catch (error) {
        // A failed destination must not move the history cursor away from the
        // page that is still visible. Cancellation already returns false above.
        this.index = previous;
        throw error;
      } finally {
        this.applying = false;
        this.changed(this);
      }
    }
  }

  const installBrowserHistoryGuard = navigateBack => {
    const token = `lexeditor:${location.pathname}:${Date.now()}`;
    const base = {...(history.state || {}), lexeditorDocument: token};
    const guard = {...base, lexeditorHistoryGuard: true};
    history.replaceState(base, "", location.href);
    history.pushState(guard, "", location.href);
    const onPopState = () => {
      if (window.__lexeditorNavigating) return;
      history.pushState(guard, "", location.href);
      Promise.resolve(navigateBack?.()).catch(() => {});
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  };

  const installExtendedMouseHistory = navigationHistory => {
    const onMouseUp = event => {
      if (event.button !== 3 && event.button !== 4) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      Promise.resolve(navigationHistory.go(event.button === 3 ? -1 : 1)).catch(() => {});
    };
    window.addEventListener("mouseup", onMouseUp, true);
    return () => window.removeEventListener("mouseup", onMouseUp, true);
  };

  const settingDependencyMemory = new Map();
  const bindSettingDependencies = (root, relations = []) => {
    const normalized = relations.filter(row => row?.dependency && row?.dependent);
    const overlay = element("svg", {
      class: "lex-setting-dependency-arrows", "aria-hidden": "true",
    });
    root.append(overlay);
    const apply = relation => {
      const owner = normalized.find(row => row.dependent === relation.dependent);
      const relationKey = owner.key || [
        owner.dependency.id || owner.dependency.getAttribute("aria-label") || "dependency",
        relation.dependent.id || relation.dependent.getAttribute("aria-label") || "dependent",
      ].join("->");
      const enabled = normalized.filter(row => row.dependent === relation.dependent).every(row =>
        row.dependency.type === "checkbox" ? row.dependency.checked : !row.dependency.disabled);
      const target = relation.dependent;
      if (!enabled) {
        if (target.type === "checkbox") {
          if (!settingDependencyMemory.has(relationKey)) {
            settingDependencyMemory.set(relationKey, target.checked);
          }
          target.dataset.lexDependencyRestore = String(settingDependencyMemory.get(relationKey));
          if (target.checked) {
            target.checked = false;
            target.dispatchEvent(new Event("change", {bubbles: true}));
          }
        }
        target.disabled = true;
      } else {
        target.disabled = false;
        if (target.type === "checkbox" && settingDependencyMemory.get(relationKey) === true) {
          delete target.dataset.lexDependencyRestore;
          settingDependencyMemory.delete(relationKey);
          target.checked = true;
          target.dispatchEvent(new Event("change", {bubbles: true}));
        } else {
          settingDependencyMemory.delete(relationKey);
          delete target.dataset.lexDependencyRestore;
        }
      }
    };
    const draw = relation => {
      if (!relation.dependency.isConnected || !relation.dependent.isConnected) return;
      const rootBox = root.getBoundingClientRect();
      const from = relation.dependency.getBoundingClientRect();
      const to = relation.dependent.getBoundingClientRect();
      const x1 = from.left + from.width / 2 - rootBox.left + root.scrollLeft;
      const y1 = from.top + from.height / 2 - rootBox.top + root.scrollTop;
      const x2 = to.left + to.width / 2 - rootBox.left + root.scrollLeft;
      const y2 = to.top + to.height / 2 - rootBox.top + root.scrollTop;
      const namespace = "http://www.w3.org/2000/svg";
      const marker = document.createElementNS(namespace, "marker");
      marker.id = `lex-setting-arrow-${Math.random().toString(36).slice(2)}`;
      marker.setAttribute("viewBox", "0 0 10 10"); marker.setAttribute("refX", "9");
      marker.setAttribute("refY", "5"); marker.setAttribute("markerWidth", "7");
      marker.setAttribute("markerHeight", "7"); marker.setAttribute("orient", "auto-start-reverse");
      const tip = document.createElementNS(namespace, "path");
      tip.setAttribute("d", "M 0 0 L 10 5 L 0 10 z"); marker.append(tip);
      const defs = document.createElementNS(namespace, "defs"); defs.append(marker);
      const path = document.createElementNS(namespace, "path");
      const bend = Math.max(28, Math.abs(x2 - x1) * .38);
      path.setAttribute("d", `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`);
      path.setAttribute("marker-end", `url(#${marker.id})`);
      overlay.replaceChildren(defs, path);
      overlay.classList.add("visible");
    };
    const hide = () => overlay.classList.remove("visible");
    for (const relation of normalized) {
      relation.dependency.addEventListener("change", () => apply(relation));
      for (const control of [relation.dependency, relation.dependent]) {
        const hover = control.closest(".setting-row,.lex-global-setting") || control;
        hover.addEventListener("pointerenter", () => draw(relation));
        hover.addEventListener("pointerleave", hide);
      }
      apply(relation);
    }
    return {refresh: () => normalized.forEach(apply), overlay};
  };

  // A yes/no question with a plain explanation. showAlert only ever had one
  // button, so anything needing consent grew its own dialog; this is the shared
  // one. Resolves true only when the confirming button is pressed.
  const confirmAction = options => new Promise(resolve => {
    const previousFocus = document.activeElement;
    const backdrop = element("div", {class: "lex-dialog-backdrop lex-important-backdrop", "data-lex-history-control": true});
    const cancel = element("button", {class: "lex-dialog-action", text: String(options?.cancelLabel || "Cancel")});
    const confirm = element("button", {class: "lex-dialog-action primary", text: String(options?.confirmLabel || "Continue")});
    const body = element("p", {class: "lex-important-message"});
    // The explanation is the point of the dialog, so its line breaks are kept.
    body.style.whiteSpace = "pre-line";
    body.textContent = String(options?.message || "");
    const dialog = element("section", {
      class: "lex-dialog lex-important-dialog", role: "alertdialog", "aria-modal": "true",
    }, element("h2", {text: String(options?.title || "Are you sure?")}), body,
      element("div", {class: "lex-dialog-actions"}, cancel, confirm));
    const finish = answer => {
      backdrop.remove();
      document.removeEventListener("keydown", onKey);
      previousFocus?.focus?.();
      resolve(answer);
    };
    const onKey = event => { if (event.key === "Escape") finish(false); };
    cancel.onclick = () => finish(false);
    confirm.onclick = () => finish(true);
    backdrop.onclick = event => { if (event.target === backdrop) finish(false); };
    document.addEventListener("keydown", onKey);
    backdrop.append(dialog);
    document.body.append(backdrop);
    confirm.focus();
  });

  // A dialog that asks for a name. Resolves the trimmed answer, or null
  // when dismissed.
  const promptText = (options = {}) => new Promise(resolve => {
    const previousFocus = document.activeElement;
    const backdrop = element("div", {class: "lex-dialog-backdrop", "data-lex-history-control": true});
    const input = element("input", {type: "text", class: "lex-dialog-input",
      value: String(options.value ?? ""), "aria-label": String(options.label || options.title || "Name")});
    const cancel = element("button", {class: "lex-dialog-action", text: String(options.cancelLabel || "Cancel")});
    const confirm = element("button", {class: "lex-dialog-action primary",
      text: String(options.confirmLabel || "Create")});
    const dialog = element("section", {class: "lex-dialog lex-prompt-dialog", role: "dialog", "aria-modal": "true"},
      element("h2", {text: String(options.title || "Name")}),
      options.message ? element("p", {class: "lex-important-message"}, String(options.message)) : null,
      element("div", {class: "lex-dialog-field"}, input),
      element("div", {class: "lex-dialog-actions"}, cancel, confirm));
    const finish = answer => {
      backdrop.remove();
      document.removeEventListener("keydown", onKey);
      previousFocus?.focus?.();
      resolve(answer);
    };
    const onKey = event => {
      if (event.key === "Escape") finish(null);
      else if (event.key === "Enter") finish(input.value.trim() || null);
    };
    cancel.onclick = () => finish(null);
    confirm.onclick = () => finish(input.value.trim() || null);
    backdrop.onclick = event => { if (event.target === backdrop) finish(null); };
    document.addEventListener("keydown", onKey);
    backdrop.append(dialog);
    document.body.append(backdrop);
    input.focus();
    input.select();
  });

  // One ReShade, managed by Lexeditor; one preset per mod, carried by the mod.
  // The section is deliberately honest about the three ways this does nothing:
  // ReShade is not installed, the mod ships no preset, or the manifest names a
  // preset file that is not there. Each of those used to look identical to a
  // working setup right up until the game launched unchanged.
  // Settings are read, not searched. A game's whole tweak surface belongs on
  // one scrolling page in as many columns as the window allows, the shape RDR2
  // established: no subtabs to click through, no dropdown to pick a group from,
  // nothing loaded on demand. Sections keep their own order and never split
  // across a column boundary.
  // The shared Tweaks layout, taken from the shape RDR2 uses: one scrolling
  // page of cards dealt into as many real columns as the width allows, rather
  // than CSS columns that cut a card in half across a column break. The card
  // count per column is re-dealt only when the column COUNT changes, so a drag
  // that does not cross a breakpoint costs nothing.
  //
  // A page may also divide itself with subtabs. A bar with fewer than two tabs
  // is not drawn, which is the same rule every other subtab bar follows.
  // Keep controls mounted so dependencies and unsaved values span pages.
  // A page of tweaks is as many cards as the window can actually show. A fixed
  // count cannot be right at two window sizes, and the one that was here put
  // six cards on a screen with room for thirty - so a page of twenty-nine
  // tweaks became five pages with the bottom half of the panel empty, which
  // reads as most of the tweaks having gone missing.
  //
  // The fit is measured the way the row fitter measures a table: lay the cards
  // out, read the grid, take as many whole grid rows as the box holds. A caller
  // that genuinely wants a fixed count still passes pageSize.
  // A paged surface with nothing to scroll turns its pages with the wheel.
  // High-resolution wheels emit many small events for one gesture, so the
  // first page turn locks until that event stream is quiet. A surface that
  // can still scroll keeps the wheel for scrolling (canScroll).
  const wheelPages = (node, step, canScroll = () => false) => {
    let wheelDelta = 0;
    let wheelLocked = false;
    let wheelQuietTimer = 0;
    node.addEventListener("wheel", event => {
      // Only a control being used keeps the wheel (a focused number box, an
      // open list). Excluding every input under the pointer meant a page whose
      // middle was a read-only field could not be turned at all.
      const control = event.target.closest?.("input,select,textarea,[contenteditable=true]");
      const using = control && control === document.activeElement && !control.readOnly && !control.disabled;
      if (event.ctrlKey || event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY) ||
          using || canScroll()) return;
      const scale = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16
        : event.deltaMode === WheelEvent.DOM_DELTA_PAGE ? Math.max(1, node.clientHeight) : 1;
      const delta = event.deltaY * scale;
      if (!delta) return;
      event.preventDefault();
      clearTimeout(wheelQuietTimer);
      wheelQuietTimer = setTimeout(() => {
        wheelDelta = 0;
        wheelLocked = false;
      }, 180);
      if (wheelLocked) return;
      wheelDelta += delta;
      if (Math.abs(wheelDelta) < 24) return;
      wheelLocked = true;
      step(wheelDelta > 0 ? 1 : -1);
    }, {passive:false});
  };

  const labelMeasure = document.createElement('canvas').getContext('2d');
  const labelWidths = new Map();
  const readablePropertyWidth = (cards, fontSize=12) => {
    let minimum=0;
    for(const card of cards){
      for(const label of card.querySelectorAll('.lex-detail-field:not(.lex-detail-field-stacked) > .lex-detail-field-label')){
        const text=label.querySelector(':scope > .lex-detail-field-label-text');
        if(!text?.textContent.trim())continue;
        const css=getComputedStyle(label),lane=css.getPropertyValue('--lex-detail-label-width').trim();
        if(!lane.endsWith('%'))continue;
        const share=parseFloat(lane)/100;
        if(!(share>0&&share<=1))continue;
        // Give the percentage lane room for a readable word before fitting.
        // Longer names can wrap between words without changing that percentage.
        const font=`${css.fontStyle} ${css.fontWeight} ${fontSize}px ${css.fontFamily}`;
        labelMeasure.font=font;
        let wordWidth=0;
        for(const original of text.textContent.trim().split(/\s+/)){
          const word=css.textTransform==='uppercase'?original.toUpperCase():css.textTransform==='lowercase'?original.toLowerCase():original;
          const spacing=parseFloat(css.letterSpacing)||0;
          const key=font+'|'+spacing+'|'+word;
          if(!labelWidths.has(key)){
            if(labelWidths.size>=8192)labelWidths.delete(labelWidths.keys().next().value);
            labelWidths.set(key,labelMeasure.measureText(word).width+Math.max(0,word.length-1)*spacing);
          }
          wordWidth=Math.max(wordWidth,labelWidths.get(key));
        }
        const help=label.querySelector(':scope > .lex-field-help');
        const helpWidth=help?parseFloat(getComputedStyle(help).width)+(parseFloat(css.columnGap)||0):0;
        const inset=(parseFloat(css.paddingLeft)||0)+(parseFloat(css.paddingRight)||0);
        minimum=Math.max(minimum,(wordWidth+helpWidth+inset+2)/share+32);
      }
    }
    return minimum;
  };

  const pagedSectionMemory = new Map();
  const paginateSettings = (content, options = {}) => {
    content.classList.add("lex-tweak-card-grid");
    const cards = [...content.children];
    if(options.columnMajor)cards.sort((a,b)=>(a.querySelector(".lex-detail-panel-title,.lex-detail-section-title")?.textContent||a.textContent).localeCompare(b.querySelector(".lex-detail-panel-title,.lex-detail-section-title")?.textContent||b.textContent,undefined,{sensitivity:"base"}));
    const size = options.pageSize || 0;
    // A record pane's sections remember their page: editing a property on
    // page 2 re-renders the pane, and it came back on page 1. The page is
    // kept per screen and set of sections, so the next record of the same
    // kind opens on it too.
    const titleOf = card => (card.querySelector(".lex-detail-section-title,.lex-detail-panel-title")?.textContent || "").trim();
    const memoryKey = options.inline ? `${shellPluginId()}-${activePageTab()}:${cards.map(titleOf).join("|")}` : null;
    let restore = memoryKey ? pagedSectionMemory.get(memoryKey) || null : null;
    let page = 0;
    // Where each page starts, as an index into the visible cards. Cards differ
    // in height, so one count per page was only ever right for the page it was
    // measured on: a page of tall cards ran under the pager.
    let starts = [0];
    let pagedCount = -1;
    // The box size the pages were last fitted to; a refit at the same size,
    // with the same cards, would only repeat the same work.
    let fittedSize = "";
    const footer = element("div", {class:"lex-tweaks-pages"});
    const scroll = element("div", {class:"lex-tweaks-scroll", tabindex:"-1"}, content);
    const sizeKey = () => scroll.isConnected ? `${scroll.clientWidth}x${scroll.clientHeight}` : "";
    const refitIfChanged = () => {
      const visible = cards.filter(card => !card.hidden).length;
      if (fittedSize && fittedSize === sizeKey() && visible === pagedCount) return;
      refit();
    };
    const root = element("div", {class:"lex-tweaks-paged"}, scroll, footer);

    // Fill each page until one more card would overflow the box. A caller
    // that genuinely wants a fixed count passes pageSize.
    const overflows = () => scroll.scrollHeight > scroll.clientHeight + 1;
    let cardHeights = new WeakMap();
    // Section->column pins from the stored arrangement; the deal honors
    // them instead of re-flowing by height. Null until one is stored.
    let laneMap = null;
    const columnCount = length => {
      // The reader's own count, from the COLUMNS control on the divider.
      const chosen=Number(content.closest('[data-lex-detail-columns]')?.dataset.lexDetailColumns)||0;
      const width=content.clientWidth||scroll.clientWidth;
      const gap=parseFloat(getComputedStyle(content).columnGap)||12;
      // Allow room for the shared name, copy button, value and help lanes.
      // Narrower cards clipped flag names and could abort strict pagination.
      // A caller can supply a measured minimum for a simpler card.
      const asked=parseFloat(getComputedStyle(content).getPropertyValue("--lex-tweak-card-width"));
      // Columns are at least 400px. Names no longer decide it: in a paged
      // flow their lane is a share of the whole panel (framework.css), so a
      // narrower column does not shrink it.
      const target=asked||400;
      const fit=Math.max(1,Math.min(length,Math.floor((width+gap)/(target+gap))||1));
      root.lexFittedColumns=fit;
      // A chosen count is honored past the fit: the fit guards the
      // default, never the maximum. Columns squeeze (flex, min-width 0),
      // so the panel still grows no horizontal scrollbar. Unpaged detail
      // flows honor it as well; only pages without the divider control
      // (tweaks, settings) never set one.
      if(chosen>0)return Math.max(1,Math.min(length,chosen));
      // `columns` is a ceiling, not a count: six fixed columns made three
      // cards a sixth of the window each, truncating every value in them,
      // beside three empty columns. A page never has more columns than cards.
      if(Number.isInteger(options.columns)&&options.columns>0)return Math.max(1,Math.min(options.columns,fit));
      return fit;
    };
    // A section taller than a page goes on in the next column, its title
    // repeated. Each fit starts from the whole sections again, so a larger
    // window joins them back up.
    let pieces = [];
    const joinSections = () => {
      // Every piece goes straight back into the section it was first cut
      // from, in reading order, so each row moves once. Handing each piece to
      // the one before it, newest first, moved a row as many times as there
      // were pieces after it: a 168-record group's thirty pieces meant tens of
      // thousands of moves and twenty seconds of frozen window.
      const cutFrom = new Map(pieces.map(entry => [entry.piece, entry.source]));
      const original = card => { let at = card; while (cutFrom.has(at)) at = cutFrom.get(at); return at; };
      const inOrder = [...pieces].sort((left, right) => cards.indexOf(left.piece) - cards.indexOf(right.piece));
      const originalSubs = new Map();
      for (const {piece, subSplit} of inOrder) {
        const body = original(piece).querySelector(":scope > :is(.lex-detail-section-content,.lex-detail-panel-body,.settings-subs)");
        const rest = piece.querySelector(":scope > :is(.lex-detail-section-content,.lex-detail-panel-body,.settings-subs)");
        if (subSplit && body && rest) {
          const continued = rest.querySelector(':scope > [data-lex-continued="true"]');
          // A long sub can span several pieces. Earlier continuations have
          // already been removed, so later fields must return to the live sub.
          const targetSub = originalSubs.get(subSplit) || subSplit;
          const fields = targetSub.querySelector(":scope > .settings-fields");
          const moved = continued?.querySelector(":scope > .settings-fields");
          if (fields && moved) fields.append(...moved.children);
          if (continued) originalSubs.set(continued, targetSub);
          continued?.remove();
        }
        if (body && rest) body.append(...rest.children);
        piece.remove();
        const at = cards.indexOf(piece);
        if (at >= 0) cards.splice(at, 1);
      }
      pieces = [];
    };
    // A continued piece inherits its card's accessible name; point it at the
    // continued title instead so no two sections announce alike.
    const continuedLabel = (piece, name) => {
      const label = piece.getAttribute("aria-label");
      if (label === null) return;
      piece.setAttribute("aria-label", `${(name || label).replace(/ \(continued\)$/, "")} (continued)`);
    };
    // A section splits between its rows; a panel between its sections; a
    // settings card between its subs.
    const splitSection = (card, available) => {
      const panel = card.matches(".lex-detail-panel");
      const settings = !panel && card.matches(".settings-section");
      if (!panel && !settings && !card.matches(".lex-detail-section")) return false;
      const title = panel ? card.querySelector(":scope > .lex-detail-panel-heading") : settings ? card.querySelector(":scope > h2") : card.querySelector(":scope > .lex-detail-section-title");
      const body = card.querySelector(panel ? ":scope > .lex-detail-panel-body" : settings ? ":scope > .settings-subs" : ":scope > .lex-detail-section-content");
      const rows = body ? [...body.children] : [];
      if (rows.length < 2) {
        // A settings section that a previous split left holding one long sub
        // is still splittable: that single sub is exactly what splitSettingsSub
        // takes apart. Returning early here left the piece taller than the page
        // with nothing left to split, so the strict guard below threw and the
        // tab was left mid-layout - one page of cards with the "(continued)"
        // pieces still in it.
        if (!settings || !body || rows.length !== 1) return false;
        const frame = card.getBoundingClientRect(), content = body.getBoundingClientRect();
        const ratio = frame.height / Math.max(1, card.offsetHeight) || 1;
        return splitSettingsSub(card, body, rows[0], available,
          (content.top - frame.top) / ratio, (frame.bottom - content.bottom) / ratio,
          ratio, content.top);
      }
      const outer = card.getBoundingClientRect(), inner = body.getBoundingClientRect();
      const scale = outer.height / Math.max(1, card.offsetHeight) || 1;
      const above = (inner.top - outer.top) / scale, below = (outer.bottom - inner.bottom) / scale;
      // Every row is read once, and every cut is decided from those numbers:
      // rows keep their height when they move to a piece at the same width.
      // Cutting one piece at a time re-laid-out the whole page per cut.
      const rects = rows.map(row => row.getBoundingClientRect());
      const lead = rects.length ? rects[0].top - inner.top : 0;
      const fitFrom = start => {
        let end = start;
        for (let index = start; index < rows.length; index++) {
          const through = (rects[index].bottom - rects[start].top + lead) / scale;
          if (above + through + below > available - 1) break;
          end = index + 1;
        }
        return end;
      };
      const keep = fitFrom(0);
      // One row taller than the page cannot be helped by splitting between
      // rows. A settings sub taller than the page splits between its own
      // fields instead, so one long sub never fails a small window.
      if (keep >= rows.length) return false;
      if (keep < 1) {
        if (!settings) return false;
        return splitSettingsSub(card, body, rows[0], available, above, below, scale, inner.top);
      }
      const named = panel ? title?.querySelector(".lex-detail-panel-title") : title;
      const name = (panel ? named?.textContent || "" : [...(title?.childNodes || [])].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent).join(""))
        .trim().replace(/ \(continued\)$/, "");
      const segments = [];
      for (let start = keep; start < rows.length;) {
        // A row taller than a whole page gets a piece of its own; the strict
        // guard reports it when that piece is measured.
        const end = Math.max(start + 1, fitFrom(start));
        segments.push(rows.slice(start, end));
        start = end;
      }
      const made = [];
      let previous = card;
      for (const segment of segments) {
        const piece = card.cloneNode(false);
        piece.classList.add("lex-detail-section-continued");
        continuedLabel(piece, name);
        const rest = body.cloneNode(false);
        rest.append(...segment);
        let head = null;
        if (panel && title) {
          head = title.cloneNode(true);
          const copy = head.querySelector(".lex-detail-panel-title");
          if (copy) copy.textContent = `${name} (continued)`;
          head.querySelectorAll(".lex-detail-panel-icon,.lex-detail-panel-actions,.lex-detail-panel-id,.lex-detail-panel-meta").forEach(node => node.remove());
        } else if (title) {
          head = element(title.tagName.toLowerCase(), {class: title.className}, `${name} (continued)`);
        }
        piece.append(...(head ? [head] : []), rest);
        previous.after(piece);
        cards.splice(cards.indexOf(previous) + 1, 0, piece);
        // Each piece is recorded as cut from the one before it, so joining
        // them back newest first returns every row to its place in order.
        pieces.push({source: previous, piece});
        made.push(piece);
        previous = piece;
      }
      return made;
    };
    // A settings sub taller than the page keeps its first fields and hands
    // the rest to a continued sub on the next column, repeating both titles.
    const splitSettingsSub = (card, body, sub, available, above, below, scale, innerTop) => {
      const fieldsBox = sub.querySelector(":scope > .settings-fields");
      const fields = fieldsBox ? [...fieldsBox.children] : [];
      if (fields.length < 2) return false;
      const base = (fieldsBox.getBoundingClientRect().top - innerTop) / scale;
      let keep = 0;
      for (let index = 0; index < fields.length; index++) {
        const through = (fields[index].getBoundingClientRect().bottom - fieldsBox.getBoundingClientRect().top) / scale;
        if (above + base + through + below > available - 1) break;
        keep = index + 1;
      }
      if (keep < 1 || keep >= fields.length) return false;
      const plain = node => [...(node?.childNodes || [])].filter(entry => entry.nodeType === Node.TEXT_NODE)
        .map(entry => entry.textContent).join("").trim().replace(/ \(continued\)$/, "");
      const piece = card.cloneNode(false);
      piece.classList.add("lex-detail-section-continued");
      const rest = body.cloneNode(false);
      const continued = sub.cloneNode(false);
      continued.dataset.lexContinued = "true";
      const subHead = sub.querySelector(":scope > h3");
      if (subHead) continued.append(element(subHead.tagName.toLowerCase(), {class: subHead.className},
        `${plain(subHead)} (continued)`));
      const restFields = fieldsBox.cloneNode(false);
      restFields.append(...fields.slice(keep));
      continued.append(restFields);
      rest.append(continued, ...[...body.children].slice(1));
      const title = card.querySelector(":scope > h2");
      const head = title ? element(title.tagName.toLowerCase(), {class: title.className},
        `${plain(title)} (continued)`) : null;
      continuedLabel(piece, title ? plain(title) : "");
      piece.append(...(head ? [head] : []), rest);
      card.after(piece);
      cards.splice(cards.indexOf(card) + 1, 0, piece);
      pieces.push({source: card, piece, subSplit: sub});
      return true;
    };
    const paginate = (visible, keepPieces = false) => {
      if (pieces.length && !keepPieces) {
        joinSections();
        visible = cards.filter(card => !card.hidden);
      }
      pagedCount = visible.length;
      fittedSize = "";
      if (size || !scroll.isConnected || scroll.clientHeight <= 0) {
        const per = size || visible.length || 1;
        starts = Array.from({length: Math.max(1, Math.ceil(visible.length / per))}, (_, index) => index * per);
        return;
      }
      // Measure each card once at its final column width. No repeated DOM
      // rebuilds to try every possible page size.
      cardHeights=new WeakMap();
      deal(visible);
      // A section too tall for the page is split where it stands, and its new
      // piece - placed right after it, in the same column, at the same width -
      // is measured next. Starting the whole pass over after every split
      // re-dealt and re-measured every card on the page each time: one FF7R
      // group of 168 records took 30-odd splits and froze the window for
      // 14-26 seconds.
      visible=[...visible];
      let split=null;
      for(let index=0;index<visible.length;index++){
        const card=visible[index];
        // Integer offsetHeight rounds down fractional font and border sizes.
        // Round upward before packing a tall column so the error cannot add
        // up into an extra scroll row on later pages.
        const box=card.getBoundingClientRect();
        const scale=box.width/Math.max(1,card.offsetWidth);
        cardHeights.set(card,Math.ceil(box.height/scale)+1);
        // A page never scrolls: a section too tall for it is split where it
        // stands, in strict and inline flows alike. Only strict flows throw
        // when a card cannot be made to fit; an inline flow leaves that one
        // card scrolling so every property stays reachable.
        if(options.strictColumns||options.inline){
          // Say which way it does not fit: a section too tall for the page
          // is split by its game; one too wide has a control that will not
          // shrink.
          const why=card.scrollWidth>card.clientWidth+1?`its content is ${card.scrollWidth}px wide in ${card.clientWidth}px`
            :card.offsetWidth>card.parentElement.clientWidth+1?`it is ${card.offsetWidth}px wide in a ${card.parentElement.clientWidth}px column`
            :card.offsetHeight>scroll.clientHeight+1?`it is ${card.offsetHeight}px tall on a ${scroll.clientHeight}px page`:"";
          // Too tall is fixed here: the section goes on in the next column.
          if(why&&options.splitOversized!==false&&card.offsetHeight>scroll.clientHeight+1&&card.scrollWidth<=card.clientWidth+1&&(split=splitSection(card,scroll.clientHeight))){
            visible.splice(index+1,0,...(Array.isArray(split)?split:[pieces[pieces.length-1].piece]));
            index--;
            continue;
          }
          // A failed fit must still leave every setting reachable: the page
          // falls back to one scrolling column behind the thrown guard.
          if(why&&options.strictColumns){scroll.style.overflowY="auto";throw new RangeError(`Tweak cannot fit one column: ${card.querySelector('.lex-detail-panel-title,.lex-detail-section-title,h2')?.textContent||card.textContent.slice(0,80)} - ${why}`);}
        }
      }
    // An unpaged flow deals every card into columns on one scrolling
    // page: the page-break pass below is skipped and no footer renders.
    if (options.unpaged) { starts = [0]; fittedSize = sizeKey(); return; }
    const count=columnCount(visible.length),gap=parseFloat(getComputedStyle(content.querySelector('.lex-tweak-column') || content).rowGap)||12;
      const available=scroll.clientHeight,loads=Array(count).fill(0),next=[0];
      let orderedLane=0;
      for(let index=0;index<visible.length;index++){
        const height=cardHeights.get(visible[index])||0;
        let lane=orderedLane;
        if(loads[lane]>0&&loads[lane]+gap+height>available+1){
          if(lane<count-1)lane=++orderedLane;
          else {next.push(index);loads.fill(0);lane=0;orderedLane=0;}
        }
        loads[lane]+=(loads[lane]?gap:0)+height;
      }
      starts=next;
      fittedSize=sizeKey();
    };

    // Measure at the final width, then fill ordered columns from top to bottom.
    const deal = onPage => {
      // Stranded cards rejoin instead of dying: anything the grid still
      // holds directly (a custom section placed between deals, a tab shell
      // re-attached elsewhere) enters this dealing, or the replaceChildren
      // below would silently destroy it with its fields inside. The grid
      // is pager-owned, so anything grid-direct is a card-in-waiting; a
      // stray decoration landing in a column is a loud failure, while a
      // destroyed section is silent data loss.
      for (const orphan of [...content.children])
        if (orphan instanceof Element && !orphan.classList.contains("lex-tweak-column") &&
            !orphan.classList.contains("lex-tweak-off-page") && !cards.includes(orphan) &&
            orphan.isConnected) {
          cards.push(orphan);
          onPage.push(orphan);
        }
      const count=columnCount(onPage.length),gap=parseFloat(getComputedStyle(content.querySelector('.lex-tweak-column') || content).rowGap)||12;
      const columns=Array.from({length:count},()=>element("div",{class:"lex-tweak-column"})),loads=Array(count).fill(0);
      let orderedLane=0;
      // Column-major order used to fill the first column to the foot of the
      // page before starting the next, so a page of three cards was one
      // column beside empty ones. The cards are spread instead: each column
      // holds about its share of the page's total height, in reading order,
      // unless that share would run past the foot.
      const heights=onPage.map(card=>cardHeights.get(card));
      let lanesFor=null;
      if(heights.every(height=>height!==undefined)&&count>1){
        const total=heights.reduce((sum,height)=>sum+height,0)+gap*Math.max(0,onPage.length-count);
        const share=Math.max(Math.max(...heights),total/count);
        const lanes=[],sums=Array(count).fill(0);
        let at=0;
        heights.forEach((height,index)=>{
          const left=onPage.length-index;
          if(sums[at]>0&&at<count-1&&(sums[at]+gap+height>share+1||left<=count-1-at))at++;
          lanes.push(at);sums[at]+=(sums[at]?gap:0)+height;
        });
        if(options.unpaged||sums.every(sum=>sum<=scroll.clientHeight+1))lanesFor=lanes;
      }
      onPage.forEach((card,index)=>{
        const measured=cardHeights.get(card);
        let lane=index%count;
        if(lanesFor)lane=lanesFor[index];
        else if(measured!==undefined){
          if(loads[orderedLane]>0&&loads[orderedLane]+gap+measured>scroll.clientHeight+1)orderedLane=Math.min(count-1,orderedLane+1);
          lane=orderedLane;
        }
        // A stored arrangement pins sections to columns: the deal honors
        // the pins instead of re-flowing by height, so adding a column
        // leaves every section where it was and a drop lands where its
        // preview line showed. Pins past the count join the last lane, as
        // do cards the stored arrangement never saw.
        if(options.unpaged&&laneMap?.size){
          const pinned=laneMap.get(card.dataset.lexLayoutSection
            ||(card.dataset.lexLayoutField?`field:${card.dataset.lexLayoutField}`:"properties"));
          lane=pinned===undefined?loads.indexOf(Math.min(...loads)):Math.min(Math.max(0,pinned),count-1);
        }
        columns[lane].append(card);loads[lane]+=(loads[lane]?gap:0)+(measured||0);
      });
      const shown=new Set(onPage);
      const off=element("div",{class:"lex-tweak-off-page",hidden:true},...cards.filter(card=>!shown.has(card)));
      content.replaceChildren(...columns,off);
    };

    const retainContentFocus = action => {
      const focused = content.contains(document.activeElement) ? document.activeElement : null;
      const selection = focused && [focused.selectionStart, focused.selectionEnd];
      action();
      if (focused?.isConnected && !focused.closest("[hidden]") && focused.getClientRects().length) {
        focused.lexRestoringFocus = true;
        try { focused.focus({preventScroll: true}); }
        finally { delete focused.lexRestoringFocus; }
        if (selection?.[0] != null && typeof focused.setSelectionRange === "function")
          focused.setSelectionRange(...selection);
      }
    };
    const render = () => retainContentFocus(() => {
      let visible = cards.filter(card => !card.hidden);
      // Paginating can split a tall section into pieces, so read the cards
      // again afterwards.
      if (visible.length !== pagedCount) { paginate(visible); visible = cards.filter(card => !card.hidden); }
      const pages = starts.length;
      if (restore !== null && pages > 1) { page = restore; restore = null; }
      page = Math.max(0, Math.min(page, pages - 1));
      const from = starts[page], to = starts[page + 1] ?? visible.length;
      deal(visible.slice(from, to));
      const focused = footer.contains(document.activeElement) ? document.activeElement : null;
      const selection = focused && [focused.selectionStart, focused.selectionEnd];
      const label = focused?.getAttribute("aria-label");
      // Embedded property panes need their own footer, not the window's list pager.
      // Unpaged flows render no footer: every card is on the one page. A single
      // page without a search needs none either: its footer would carry only
      // a summary, the stray block from FF8's item details.
      if (options.unpaged || (pages <= 1 && !options.search)) footer.replaceChildren();
      else footer.replaceChildren(pager({inline:options.inline === true,page, pages, total:visible.length, range:[from + 1, to],
        search:options.search, change:turn}));
      if (label && focused?.matches("input")) {
        const replacement = [...footer.querySelectorAll("input")].find(input=>input.getAttribute("aria-label")===label);
        replacement?.focus();
        if (selection && selection[0] !== null) replacement?.setSelectionRange(...selection);
      }
      scroll.style.overflowY = overflows() ? "auto" : "hidden";
    });

    const turn = value => {
      page = value; restore = null;
      if (memoryKey) pagedSectionMemory.set(memoryKey, value);
      render(); scroll.scrollTop = 0;
    };
    // Re-break the pages for the box as it is now, keeping the first card on
    // screen on screen.
    const refit = () => retainContentFocus(() => {
      let visible = cards.filter(card => !card.hidden);
      const anchor = visible[starts[page]] || null;
      paginate(visible);
      visible = cards.filter(card => !card.hidden);
      const at = anchor ? Math.max(0, visible.indexOf(anchor)) : 0;
      page = Math.max(0, starts.findLastIndex(start => start <= at));
      // The first fit, once there are pages, opens the remembered one.
      if (restore !== null && starts.length > 1) { page = restore; restore = null; }
      render();
    });
    wheelPages(scroll, direction => {
      const target = page + direction;
      if (target >= 0 && target < starts.length) turn(target);
    }, overflows);
    root.refreshPages = () => {page=0;pagedCount=-1;refit();};
    root.lexAppendCards = (...added) => {
      const fresh = added.filter(card => !cards.includes(card));
      if (!fresh.length) return;
      cards.push(...fresh);
      content.append(...fresh);
      pagedCount = -1;
      refit();
    };
    // What the pager decided, for checks and for debugging a page break.
    root.lexPaging = () => ({starts:[...starts],page,
      cards:cards.filter(card=>!card.hidden).map(card=>({title:(card.querySelector(".lex-detail-panel-title,.lex-detail-section-title")?.textContent||"").trim(),height:cardHeights.get(card)??null}))});
    root.lexFitPage = refit;
    // The pager deals its cards into columns from this list on every render,
    // so a developer's section order is set here, not by moving nodes. The
    // listed cards fill the places they hold now, in the order given; one the
    // list has not seen (a section the developer added) goes after the card
    // before it in the order.
    root.lexCards = () => [...cards];
    root.lexUnpaged = options.unpaged === true;
    // Setting pins never re-deals by itself: callers refit through
    // their own path (a drop refits once, through orderSections).
    root.lexSetLanes = map => { laneMap = map instanceof Map ? map : asLaneMap(map); };
    // Cards the layout moved out of the columns leave the dealing: dealt
    // again, the pager would otherwise pull a property back out of the
    // custom section it was dropped into.
    root.lexRemoveCards = (...gone) => {
      if (!gone.length) return;
      const drop = new Set(gone);
      const before = cards.length;
      for (let index = cards.length - 1; index >= 0; index--)
        if (drop.has(cards[index])) cards.splice(index, 1);
      if (cards.length !== before) pagedCount = -1;
    };
    root.lexOrderCards = (wanted, quiet = false) => {
      if (!quiet) joinSections();
      const was = [...cards];
      const known = wanted.filter(card => cards.includes(card));
      const slots = known.map(card => cards.indexOf(card)).sort((a, b) => a - b);
      known.forEach((card, index) => { cards[slots[index]] = card; });
      wanted.forEach((card, index) => {
        if (cards.includes(card) || !card.isConnected) return;
        // A card new to the deal slots where the live order puts it:
        // after the nearest known card before it, else before the
        // nearest known card after it. Appending unconditionally put a
        // property dragged above every section below them on refit.
        const previous = wanted.slice(0, index).reverse().find(other => cards.includes(other));
        const next = previous ? null : wanted.slice(index + 1).find(other => cards.includes(other));
        if (previous) cards.splice(cards.indexOf(previous) + 1, 0, card);
        else if (next) cards.splice(cards.indexOf(next), 0, card);
        else cards.push(card);
      });
      if (cards.length === was.length && cards.every((card, index) => card === was[index])) return;
      // A quiet re-sequence only retires the shipped order: the live DOM
      // already shows it, and redealing now would churn the columns that
      // the property schema keys on.
      if (quiet) return;
      pagedCount = -1;
      refit();
    };
    // A rebuild deals the stored arrangement first, not shipped order:
    // with bare field cards the dealing decides the parents, so dealing
    // shipped would key a stranger schema and orphan the layout.
    try {
      const probe = buildPropertyState(content, layoutFields(content));
      const stored = readStoredLayout(probe);
      if (stored) {
        const byBase = new Map();
        for (const card of cards) {
          const id = probe.fields.get(card);
          if (id === undefined) continue;
          const base = propertyOf(id);
          if (!byBase.has(base)) byBase.set(base, []);
          byBase.get(base).push(card);
        }
        const wanted = [];
        for (const key of Object.keys(stored).sort((a, b) => a.localeCompare(b, undefined, {numeric: true}))) {
          if (key === "sections" || key === "removed" || key === "order" || key === "lanes") continue;
          const list = stored[key];
          if (!Array.isArray(list)) continue;
          for (const id of list) {
            if (typeof id !== "string" || !id.includes("/")) continue;
            const queue = byBase.get(propertyOf(id));
            if (queue?.length) wanted.push(queue.shift());
          }
        }
        if (wanted.length) root.lexOrderCards(wanted, true);
        if (stored.lanes && typeof stored.lanes === "object") laneMap = asLaneMap(stored.lanes);
      }
    } catch (_error) {}
    render();
    if (options.notice) root.prepend(options.notice);
    if ((options.tabs || []).length > 1) root.prepend(subtabBar({
      tabs: options.tabs, active: options.activeTab,
      label: options.tabsLabel || "Tweak groups", change: options.changeTab}));
    if (typeof ResizeObserver === "function") {
      let frame = 0;
      const observer = new ResizeObserver(() => {
        if (frame) return;
        frame = requestAnimationFrame(() => {frame = 0; refitIfChanged();});
      });
      observer.observe(scroll);
      // Fonts still loading change every measurement once they arrive.
      if (document.fonts && document.fonts.status !== "loaded")
        document.fonts.ready.then(() => { labelWidths.clear(); if (root.isConnected) refit(); });
      root.lexPageObserver = observer;
    }
    requestAnimationFrame(refitIfChanged);
    return root;
  };
  const settingsColumns = (sections, options = {}) => {
    const content = element("div", {class:"lex-tweak-card-grid"}, ...(sections || []).filter(Boolean));
    const root = paginateSettings(content, {columnMajor:true,strictColumns:true,...options,
      columns:sharedSettings()?.tweakColumnsPerPage||options.columns||6});
    root.classList.add("lex-settings-columns");
    if(options.className) root.classList.add(...options.className.split(/\s+/));
    if(options.columnWidth) content.style.setProperty("--lex-tweak-card-width",options.columnWidth);
    return root;
  };

  // Every game's Tweaks page. A plugin hands over its own pages (its tweak
  // mods first) and how to redraw; the page adds ReShade on a subtab of its
  // own when the game has it, and owns ReShade's loading and actions. Each
  // plugin used to build this by hand, with its own copy of the ReShade
  // calls, and one put ReShade in among the tweak mods (Lexer: "WHY AM I
  // SEEING RESHADE IN THE MAIN TWEAKS TAB").
  //   pages: [{id, label, help?, body: () => [sections], bind?: view => void,
  //            whole?: node}] - `whole` owns the screen when it is the only
  //            page, as a lone status panel would look lost in a column.
  //   notice: a step the reader must take, above every page
  //   columnWidth: the cards' width, for pages of wide cards
  //   active, change: a plugin that keeps the open page in its own state
  // A page that draws its own view (a config list with its own search) gives
  // `view: tabProps => node` instead of `body`, and puts the shared subtab
  // props on its own component.
  //   render: () => void, called when the page must be drawn again
  const tweaksPageMemory = new Map();
  const tweaksPage = (options = {}) => {
    const plugin = options.plugin || shellPluginId();
    const memory = tweaksPageMemory.get(plugin) || {tab: "", reshade: null, loading: null};
    tweaksPageMemory.set(plugin, memory);
    const redraw = () => options.render?.();
    if (options.reshade !== false && !memory.reshade && !memory.loading) {
      memory.loading = Promise.resolve(callWindow("mod_reshade", plugin))
        .then(value => { memory.reshade = value || {}; })
        .catch(() => { memory.reshade = {}; })
        .finally(() => { memory.loading = null; if (memory.reshade?.available) redraw(); });
    }
    const act = async (method, ...args) => {
      try { memory.reshade = await callWindow(method, plugin, ...args) || memory.reshade; }
      catch (error) { showAlert({title: "ReShade could not do that", message: error.message || String(error)}); }
      redraw();
    };
    const pages = (options.pages || []).filter(Boolean);
    const reshade = options.reshade === false ? null : reshadeSection({snapshot: memory.reshade, act});
    if (reshade) pages.push({id: "reshade", label: "ReShade", help: "Effects over the finished frame.", body: () => [reshade]});
    const active = pages.find(page => page.id === (options.active ?? memory.tab)) || pages[0];
    if (!active) return notice({message: "This game has no tweaks yet."});
    if (pages.length === 1 && active.whole) return active.whole;
    const tabProps = {tabs: pages.map(({id, label, help}) => ({id, label, help})), activeTab: active.id,
      tabsLabel: options.tabsLabel || "Tweak pages",
      changeTab: id => { memory.tab = id; if (options.change) options.change(id); else redraw(); }};
    if (typeof active.view === "function") {
      const own = active.view(tabProps);
      if (typeof active.bind === "function" && own) requestAnimationFrame(() => active.bind(own));
      return own;
    }
    const body = typeof active.body === "function" ? active.body() : active.body;
    const view = settingsColumns([body].flat(), {columnWidth: options.columnWidth, notice: options.notice,
      className: ["lex-tweaks-page", options.className || ""].filter(Boolean).join(" "),
      tabs: pages.map(({id, label, help}) => ({id, label, help})), activeTab: active.id,
      tabsLabel: options.tabsLabel || "Tweak pages",
      changeTab: id => { memory.tab = id; if (options.change) options.change(id); else redraw(); }});
    if (typeof active.bind === "function") requestAnimationFrame(() => active.bind(view));
    return view;
  };

  // One game's ReShade: a switch for the whole thing, then each of Lexeditor's
  // effects with its own switch and its controls, read from the shader itself.
  // A game with no defaults set has no ReShade for players, so nothing renders.
  const reshadeSection = spec => {
    const data = spec?.snapshot || {};
    if (!data.available) return null;
    const act = (method, ...args) => spec.act?.(method, ...args);
    const ready = data.gameFound !== false;
    const master = element("label", {class: "lex-reshade-master"},
      element("input", {type: "checkbox", role: "switch", checked: !!data.installed, disabled: !ready,
        "aria-label": "ReShade on or off",
        onchange: event => act("set_reshade_enabled", event.target.checked)}),
      element("span", {class: "lex-reshade-master-label"}, data.installed ? "ReShade is on" : "ReShade is off"));
    const buttons = element("div", {class: "lex-reshade-actions"},
      element("button", {type: "button", class: "lex-dialog-action", disabled: !ready,
        onclick: () => act("reset_reshade_defaults")}, "Back to defaults"),
      data.developerMode ? element("button", {type: "button", class: "lex-dialog-action primary", disabled: !ready,
        onclick: () => act("save_reshade_defaults")}, "Save as defaults") : null);
    const head = element("div", {class: "lex-reshade-head"}, master, buttons);
    const notes = [];
    if (data.error) notes.push(element("p", {class: "lex-reshade-error"}, data.error));
    if (data.developerMode && !data.hasDefaults) {
      notes.push(element("p", {class: "lex-reshade-note"}, "No defaults for this game yet. Players will not see ReShade until you save some."));
    }
    const control = (effect, row) => {
      const value = effect.values?.[row.name];
      const set = next => act("set_reshade_value", effect.file, row.name, next);
      if (row.widget === "checkbox") {
        return element("input", {type: "checkbox", checked: !!value, disabled: !ready, "aria-label": row.label,
          onchange: event => set(event.target.checked)});
      }
      if (row.widget === "combo") {
        const select = element("select", {disabled: !ready, "aria-label": row.label,
          onchange: event => set(Number(event.target.value))});
        row.items.forEach((item, index) => {
          const option = element("option", {value: String(index)}, item);
          option.selected = index === Number(value);
          select.append(option);
        });
        return select;
      }
      const step = row.step ?? (row.type === "int" ? 1 : 0.01);
      const digits = String(step).includes(".") ? String(step).split(".")[1].length : 0;
      const number = element("input", {type: "number", min: row.min, max: row.max, step, value: Number(value).toFixed(digits),
        disabled: !ready, "aria-label": `${row.label} value`, onchange: event => set(Number(event.target.value))});
      const slider = element("input", {type: "range", min: row.min, max: row.max, step, value, disabled: !ready,
        "aria-label": row.label,
        oninput: event => { number.value = Number(event.target.value).toFixed(digits); },
        onchange: event => set(Number(event.target.value))});
      return element("div", {class: "lex-reshade-slider"}, slider, number);
    };
    const effects = (data.effects || []).map(effect => {
      const toggle = element("label", {class: "lex-reshade-effect-toggle"},
        element("input", {type: "checkbox", checked: !!effect.enabled, disabled: !ready,
          "aria-label": `${effect.label} on or off`,
          onchange: event => act("set_reshade_effect", effect.file, event.target.checked)}),
        element("span", {}, effect.label));
      return detailSection({
        title: toggle,
        help: effect.tooltip ? infoHelp(effect.tooltip) : null,
        className: `lex-reshade-effect${effect.enabled ? "" : " off"}`,
        body: effect.controls.map(row => detailField({label: row.label, control: control(effect, row),
          help: row.tooltip ? infoHelp(row.tooltip) : null})),
      });
    });
    return detailSection({title: "RESHADE", className: "lex-reshade", body: [head, ...notes, ...effects]});
  };

  const showAlert = options => {
    const title = String(options?.title || "Lexeditor message");
    const message = String(options?.message || "An important event needs your attention.");
    const items = Array.isArray(options?.items) ? options.items : [];
    const fill = dialog => {
      dialog.querySelector("h2").textContent = title;
      const messageNode = dialog.querySelector(".lex-important-message");
      messageNode.textContent = items.length ? "" : message;
      messageNode.hidden = Boolean(items.length);
      const list = dialog.querySelector(".lex-important-list");
      list.replaceChildren(...items.map(entry => {
        const item = entry.activate
          ? element("button", {type: "button", class: "lex-important-item-link", text: String(entry.item || "Item")})
          : element("strong", {class: "lex-important-item", text: String(entry.item || "Item")});
        if (entry.activate) item.onclick = () => { dialog.closest(".lex-dialog-backdrop")?.remove(); entry.activate(); };
        return element("li", {}, item, element("span", {text: ": "}), element("span", {text: String(entry.issue || message)}));
      }));
      list.hidden = !items.length;
      dialog.querySelector(".lex-dialog-action").textContent = options.closeLabel || "Close";
    };
    const existing = document.querySelector(".lex-important-dialog");
    if (existing) {
      fill(existing);
      existing.querySelector(".lex-dialog-action")?.focus();
      return existing.closest(".lex-dialog-backdrop");
    }
    const previousFocus = document.activeElement;
    const backdrop = element("div", {class: "lex-dialog-backdrop lex-important-backdrop", "data-lex-history-control": true});
    const close = element("button", {class: "lex-dialog-action primary", text: options.closeLabel || "Close"});
    const dialog = element("section", {
      class: "lex-dialog lex-important-dialog", role: "alertdialog", "aria-modal": "true",
      "aria-labelledby": "lex-important-title", "aria-describedby": "lex-important-message",
    },
      element("h2", {id: "lex-important-title", text: title}),
      element("div", {id: "lex-important-message", class: "lex-important-message", text: message}),
      element("ul", {class: "lex-important-list", hidden: true}),
      element("div", {class: "lex-dialog-actions"}, close));
    fill(dialog);
    close.onclick = () => {
      backdrop.remove();
      if (previousFocus?.isConnected) previousFocus.focus();
    };
    backdrop.append(dialog);
    document.body.append(backdrop);
    // An alert can be dismissed from the keyboard too: it is the one dialog
    // with a single action, and a reader who opened it by accident should not
    // have to hunt for the pointer.
    backdrop.addEventListener("keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); close.click(); }
    });
    close.focus();
    return backdrop;
  };

  const confirmUnsavedExit = (options, exit, copy = {}) => {
    const dirty = options.dirtyCount?.() || 0;
    if (!dirty) return Promise.resolve().then(exit).catch(error => {
      showAlert({title: copy.exitError || "Could not exit", message: error.message || String(error)});
      return false;
    });
    const existing = document.querySelector(".lex-exit-dialog");
    if (existing) {
      existing.querySelector(".lex-dialog-action")?.focus();
      return existing.closest(".lex-dialog-backdrop");
    }
    const backdrop = element("div", {class: "lex-dialog-backdrop"});
    const status = element("p", {class: "lex-dialog-status", "aria-live": "polite"});
    const cancel = element("button", {class: "lex-dialog-action", text: "Cancel"});
    const discard = element("button", {class: "lex-dialog-action", text: copy.discardLabel || "Exit Without Saving"});
    const save = element("button", {class: "lex-dialog-action primary", text: copy.saveLabel || "Save and Exit"});
    const buttons = [cancel, discard, save];
    let busy = false;
    const setBusy = value => { busy = value; buttons.forEach(button => { button.disabled = value; }); };
    const dismiss = () => { if (!busy) backdrop.remove(); };
    cancel.onclick = dismiss;
    discard.onclick = async () => {
      setBusy(true);
      // "Without saving" still discards first: guarded exits refuse to
      // run while changes are unsent, so abandoning them is part of the
      // button, not a skip. A page with no discard hook keeps the old
      // direct exit.
      const canDiscard = typeof options.discard === "function";
      status.replaceChildren(loadingStatus(canDiscard ? "Discarding changes…" : (copy.pendingLabel || "Please wait…")));
      let discarded = false;
      try {
        if (canDiscard) {
          await options.discard();
          const remaining = options.dirtyCount?.() || 0;
          if (remaining) {
            status.textContent = `${remaining} change${remaining === 1 ? "" : "s"} could not be discarded. Lexeditor stayed open.`;
            setBusy(false);
            return;
          }
          discarded = true;
          status.replaceChildren(loadingStatus(copy.pendingLabel || "Please wait…"));
          // The host guards restart and close on its own dirty count, synced
          // fire-and-forget while editing. A discard that just reached zero
          // has not been reported yet, so report it now and wait for the
          // round trip: exiting first refuses to leave.
          await callWindow("set_dirty_count", 0).catch(() => {});
        }
        if (await exit()) backdrop.remove();
        else if (discarded) status.textContent = "Discarded, but the action did not complete. Try again or cancel.";
        else status.textContent = "The action did not complete. Try again or cancel.";
      } catch (error) {
        const failed = canDiscard && !discarded ? "Could not discard changes" : (copy.exitError || "Could not exit");
        status.textContent = `${failed}: ${error.message || error}`;
      } finally {
        setBusy(false);
      }
    };
    save.onclick = async () => {
      setBusy(true);
      status.replaceChildren(loadingStatus("Saving changes…"));
      let saved = false;
      try {
        await options.save?.();
        const remaining = options.dirtyCount?.() || 0;
        if (remaining) {
          status.textContent = `${remaining} change${remaining === 1 ? "" : "s"} could not be saved. Lexeditor stayed open.`;
          setBusy(false);
          return;
        }
        saved = true;
        status.replaceChildren(loadingStatus(copy.pendingLabel || "Please wait…"));
        await callWindow("set_dirty_count", 0).catch(() => {});
        if (await exit()) backdrop.remove();
        else status.textContent = "Saved, but the action did not complete. Try again or cancel.";
      } catch (error) {
        status.textContent = `${saved ? (copy.exitError || "Could not exit") : "Save failed"}: ${error.message || error}`;
      } finally {
        setBusy(false);
      }
    };
    const panel = element("div", {
      class: "lex-dialog lex-return-dialog lex-exit-dialog", role: "dialog", "aria-modal": "true",
      "aria-labelledby": "lex-exit-title",
    },
      element("h2", {id: "lex-exit-title", text: copy.title || "Unsaved changes"}),
      element("p", {text: `You have ${dirty} unsaved change${dirty === 1 ? "" : "s"}. ${copy.question || "Save before exiting Lexeditor?"}`}),
      status,
      element("div", {class: "lex-dialog-actions"}, cancel, discard, save))
    backdrop.append(panel);
    backdrop.addEventListener("click", event => { if (event.target === backdrop) dismiss(); });
    backdrop.addEventListener("keydown", event => { if (event.key === "Escape") dismiss(); });
    document.body.append(backdrop);
    cancel.focus();
    return backdrop;
  };

  const confirmDiscardChanges = options => {
    const dirty = options.dirtyCount?.() || 0;
    if (!dirty || typeof options.discard !== "function") return null;
    const existing = document.querySelector(".lex-discard-dialog");
    if (existing) {
      existing.querySelector(".lex-dialog-action")?.focus();
      return existing.closest(".lex-dialog-backdrop");
    }
    const backdrop = element("div", {class: "lex-dialog-backdrop"});
    const status = element("p", {class: "lex-dialog-status", "aria-live": "polite"});
    const cancel = element("button", {class: "lex-dialog-action", text: "Cancel"});
    const discard = element("button", {class: "lex-dialog-action primary", text: "Discard Changes"});
    const dismiss = () => backdrop.remove();
    cancel.onclick = dismiss;
    discard.onclick = async () => {
      cancel.disabled = true;
      discard.disabled = true;
      status.replaceChildren(loadingStatus("Restoring the saved state…"));
      try {
        await options.discard();
        dismiss();
      } catch (error) {
        status.textContent = `Could not discard changes: ${error.message || error}`;
        cancel.disabled = false;
        discard.disabled = false;
      }
    };
    backdrop.append(element("section", {
      class: "lex-dialog lex-discard-dialog", role: "alertdialog", "aria-modal": "true",
      "aria-labelledby": "lex-discard-title",
    },
      element("h2", {id: "lex-discard-title", text: "Discard unsaved changes?"}),
      element("p", {text: `This will restore the last saved state and discard ${dirty} unsaved change${dirty === 1 ? "" : "s"}.`}),
      status,
      element("div", {class: "lex-dialog-actions"}, cancel, discard)));
    backdrop.addEventListener("click", event => { if (event.target === backdrop) dismiss(); });
    backdrop.addEventListener("keydown", event => { if (event.key === "Escape") dismiss(); });
    document.body.append(backdrop);
    cancel.focus();
    return backdrop;
  };

  const returnToMainMenu = (options, leave) => confirmUnsavedExit(options, leave, {
    question: "Save before exiting to the main menu?",
    exitError: "Could not open the main menu",
  });

  const callWindow = async (method, ...args) => {
    const api = window.pywebview?.api;
    if (typeof api?.[method] !== "function") return null;
    return api[method](...args);
  };
  const openGameFolder = pluginId => callWindow("open_game_folder", pluginId);

  let sharedSettingsSnapshot = null;
  const rememberSharedSettings = settings => {
    if (!settings) return null;
    sharedSettingsSnapshot = settings;
    // Freshly synced preferences can carry per-subtab counts a shared key
    // already migrated past, so migration re-arms and re-reads them.
    migratedColumnKeys.clear();
    if (settings.soundEnabled === false || themeSoundGain(settings.soundVolumePercent) <= 0) stopThemeSounds();
    document.documentElement.dataset.lexHoverableAltClick = settings.hoverableAltClick ? "true" : "false";
    document.documentElement.dataset.lexDeveloperMode = settings.developerMode ? "true" : "false";
    // Lexer liked a boolean drawn as one wide box and asked for it as the
    // default, with the arrow-and-checkbox layout as the alternative.
    document.documentElement.dataset.lexBooleanStyle = settings.booleanBoxStyle === false ? "arrow" : "box";
    document.documentElement.dataset.lexShowHidden = settings.showHiddenProperties === true ? "true" : "false";
    document.documentElement.style.setProperty("--lex-panel-gap", `${Number(settings.panelGapPercent || 1)}vw`);
    // The pagination bar is one height on every page, and that height is a
    // setting rather than a number buried in the stylesheet.
    document.documentElement.style.setProperty("--lex-pager-bar-height",
      `${Math.max(3, Math.min(12, Number(settings.pagerBarHeightPercent) || 6))}vh`);
    document.documentElement.style.setProperty("--lex-command-row-height", `${Math.max(3, Math.min(20, Number(settings.mainMenuHeightPercent) || 9))}vh`);
    window.dispatchEvent(new CustomEvent("lexeditor-view-preferences-ready", {detail: settings.viewPreferences || {}}));
    window.dispatchEvent(new CustomEvent("lexeditor-settings-ready", {detail: settings}));
    return settings;
  };

  const hoverableAltClickEnabled = () => sharedSettingsSnapshot?.hoverableAltClick === true;
  const sharedSettings = () => sharedSettingsSnapshot ? clone(sharedSettingsSnapshot) : null;
  // Enabling a mod runs its scripts, so the first time each mod is enabled
  // the reader confirms they trust it (Lexer: "the first time you enable a
  // mod"). The Trust Warning setting switches the warning off entirely. `mod`
  // is the mod's folder, or its key where a list has no folder.
  const confirmFirstModEnable = async mod => {
    let settings = sharedSettingsSnapshot;
    if (!settings) {
      try { settings = rememberSharedSettings(await callWindow("lexeditor_settings")); }
      catch (_error) { settings = null; }
    }
    const seen = new Set((Array.isArray(settings?.trustWarningSeen) ? settings.trustWarningSeen : []).map(String));
    const id = String(mod || "").trim().toLocaleLowerCase();
    if (!settings || settings.trustWarning === false || (id && seen.has(id))) return true;
    const agreed = await confirmAction({title: "Enable this mod?",
      message: "Are you sure you want to enable this mod? Only enable mods you trust.\n\nThis warning shows up the first time you enable a mod because it's important. You can disable this in the settings under \"Trust Warning\".",
      confirmLabel: "Enable", cancelLabel: "Cancel"});
    if (!agreed) return false;
    if (id) {
      const updated = await callWindow("acknowledge_trust_warning", id);
      if (updated) rememberSharedSettings(updated);
    }
    return true;
  };
  const soundCoverageTable = rows => element("table", {class:"lex-theme-sound-table"},
    element("thead", {}, element("tr", {},
      element("th", {}, "Action"), element("th", {}, "Plugin sound"), element("th", {}, "Source"))),
    element("tbody", {}, ...(rows || []).map(row => element("tr", {},
      element("td", {}, String(row.slot || "").replace(/(^|-)\w/g, value => value.toLocaleUpperCase())),
      element("td", {class:row.available ? "available" : "missing"}, row.available ? "✓ Available" : "× Missing"),
      element("td", {}, row.message || "")))));
  const hoverable = options => {
    const target = String(options.targetLabel || options.label || "linked record");
    // A link may carry its target's picture before its name: an item link
    // shows the item's icon. A picture that fails to load leaves no placeholder.
    const hoverIcon = options.icon instanceof Element ? options.icon
      : options.icon ? element("img", {class: "lex-hoverable-icon", src: String(options.icon),
        "data-lex-no-image": "off",
        alt: "", draggable: "false"}) : null;
    if (hoverIcon?.tagName === "IMG") hoverIcon.addEventListener("error", () => hoverIcon.remove(), {once: true});
    // A link that is also editable waits out a second click before it follows:
    // one click opens the record, two clicks rename it. Every other link keeps
    // its instant click, because waiting is only worth paying where a double
    // click means something else.
    let waiting = null;
    const activate = event => {
      const keyboard = event.detail === 0;
      if (hoverableAltClickEnabled() && !event.altKey && !keyboard) return;
      event.preventDefault();
      event.stopPropagation();
      if (options.edit && !keyboard) {
        if (waiting) return;
        waiting = setTimeout(() => { waiting = null; options.activate?.(); }, 240);
        return;
      }
      options.activate?.();
    };
    const button = element("button", {
      type: "button",
      class: ["lex-hoverable", options.class || ""].filter(Boolean).join(" "),
      "data-hover-target-type": options.targetType,
      "data-hover-target-id": options.targetId,
      "aria-label": options["aria-label"] || `Open ${target}`,
      title: `Open ${target}`,
      onclick: activate,
      ondblclick: options.edit ? event => {
        event.preventDefault();
        event.stopPropagation();
        if (waiting) { clearTimeout(waiting); waiting = null; }
        options.edit(button);
      } : undefined,
    }, hoverIcon, options.content ?? options.label ?? target);
    // Flex buttons cannot ellipsize anonymous text nodes.
    [...button.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).forEach(node => {
      const label = element("span", {class: "lex-hoverable-label"}, node.textContent);
      node.replaceWith(label);
    });
    // A link may preview its target on hover, so a reader can compare several
    // linked records without leaving the one they are on.
    if (options.preview) {
      button.removeAttribute("title");
      hoverPreview(button, options.preview, "lex-hover-preview");
    }
    return button;
  };

  const keyboardIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const body = document.createElementNS(namespace, "rect");
    body.setAttribute("x", "3.5"); body.setAttribute("y", "7.5");
    body.setAttribute("width", "17"); body.setAttribute("height", "9");
    body.setAttribute("rx", "1.6");
    body.setAttribute("fill", "none");
    body.setAttribute("stroke", "currentColor");
    body.setAttribute("stroke-width", "1.6");
    svg.append(body);
    const bar = document.createElementNS(namespace, "path");
    bar.setAttribute("d", "M9 13.6h6");
    bar.setAttribute("stroke", "currentColor");
    bar.setAttribute("stroke-width", "1.6");
    bar.setAttribute("stroke-linecap", "round");
    svg.append(bar);
    for (const x of [7, 10, 13, 16]) {
      const key = document.createElementNS(namespace, "path");
      key.setAttribute("d", `M${x} 10.6h.01`);
      key.setAttribute("stroke", "currentColor");
      key.setAttribute("stroke-width", "1.8");
      key.setAttribute("stroke-linecap", "round");
      svg.append(key);
    }
    return svg;
  };

  // One animation viewer is live at a time: the mounted one. The shell's
  // key handler and shortcuts panel read this slot, so animation keys only
  // work - and are only listed - while an animations view is on screen.
  let activeAnimationViewer = null;

  // The animation bindings, in transport order. Entries here are listed in
  // the shortcuts panel only while a viewer is mounted; the shell handler
  // reads the same table, so the two cannot drift apart.
  const ANIMATION_SHORTCUTS = [
    {id: "anim-start", keys: ["Shift", "\u2190"], label: "Go to animation start"},
    {id: "anim-prev", keys: ["\u2190"], label: "Back one frame"},
    {id: "anim-play", keys: ["Space"], label: "Play or pause the animation"},
    {id: "anim-next", keys: ["\u2192"], label: "Forward one frame"},
    {id: "anim-end", keys: ["Shift", "\u2192"], label: "Go to animation end"},
  ];
  const matchAnimationShortcut = event => {
    if (!activeAnimationViewer) return "";
    if (event.ctrlKey || event.metaKey || event.altKey) return "";
    if (event.key === "ArrowLeft" || event.code === "ArrowLeft") return event.shiftKey ? "anim-start" : "anim-prev";
    if (event.key === "ArrowRight" || event.code === "ArrowRight") return event.shiftKey ? "anim-end" : "anim-next";
    if ((event.key === " " || event.key === "Spacebar" || event.code === "Space") && !event.shiftKey) return "anim-play";
    return "";
  };

  // A reusable animation viewer: scrub bar with its event markers overlaid
  // on it, a transport row and a playback loop. The caller draws the
  // pictures: render() gets the current
  // frame (fractional, for blending) and the playback state every animation
  // frame. DS1 poses its skeleton there; a fixture page draws synthetic
  // frames on a plain canvas. Stepping pauses, as on an editing bench: the
  // reader asked to look at one frame, not to keep playing past it.
  const animationViewer = (options = {}) => {
    const host = options.host, timeline = options.timeline, status = options.status;
    const frames = options.frames || {};
    const count = Math.max(1, Math.trunc(Number(frames.count) || 1));
    const duration = Number(frames.duration) > 0 ? Number(frames.duration) : count / 30;
    const frameDur = Number(frames.frameDuration) > 0 ? Number(frames.frameDuration)
      : duration / Math.max(count - 1, 1);
    const state = {time: 0, playing: options.playing !== false, follow: false, live: true};
    timeline.replaceChildren();
    timeline.classList.add("lex-anim-timeline");
    const slider = element("input", {type: "range", min: "0", max: String(count - 1),
      step: "0.01", value: "0", "aria-label": "Frame"});
    const readout = element("span", {class: "lex-anim-readout", "data-anim-readout": "true"});
    const markers = element("div", {class: "lex-anim-markers"});
    const sliderWrap = element("div", {class: "lex-anim-slider"}, slider, markers);
    const scrub = element("div", {class: "lex-anim-scrub"}, sliderWrap, readout);
    for (const cue of frames.events || []) {
      const at = Number(cue.start) || 0;
      const tick = element("button", {type: "button", class: "lex-anim-marker",
        title: `${cue.label} (${at.toFixed(2)}s)`,
        style: `left:${Math.min(at / duration, 1) * 100}%`,
        "aria-label": `${cue.label} (${at.toFixed(2)}s)`,
        onclick: () => { state.time = at % duration; options.onEvent?.(cue); }});
      markers.append(tick);
    }
    const transport = element("div", {class: "lex-anim-transport",
      "data-anim-transport": "true", role: "group", "aria-label": "Animation transport"});
    const glyph = playing => playing ? "\u23F8" : "\u25B6";
    const setPlaying = playing => {
      state.playing = playing;
      playButton.textContent = glyph(playing);
    };
    const sync = () => {
      const shown = (((state.time / frameDur) % count) + count) % count;
      if (document.activeElement !== slider) slider.value = String(shown);
      readout.textContent = `${Math.floor(shown)} / ${count - 1} \u{1D453} \u00B7 ${state.time.toFixed(2)}s`;
      return shown;
    };
    const goToFrame = frame => {
      const clamped = Math.max(0, Math.min(count - 1, Math.round(frame)));
      state.time = clamped * frameDur;
      setPlaying(false);
      sync();
    };
    const buttons = [
      {label: "Go to animation start", glyph: "\u23EE", run: () => goToFrame(0)},
      {label: "Back one frame", glyph: "\u25C1", run: () => goToFrame(Math.round(state.time / frameDur) - 1)},
      {label: "Play or pause", glyph: glyph(state.playing), run: () => setPlaying(!state.playing)},
      {label: "Forward one frame", glyph: "\u25B7", run: () => goToFrame(Math.round(state.time / frameDur) + 1)},
      {label: "Go to animation end", glyph: "\u23ED", run: () => goToFrame(count - 1)},
    ].map(spec => element("button", {type: "button", class: "lex-anim-transport-button",
      "aria-label": spec.label, title: spec.label, onclick: spec.run}, spec.glyph));
    const playButton = buttons[2];
    // The shell lets Space through to this button only, so its native
    // click stays the one and only toggle.
    playButton.dataset.animPlayButton = "";
    transport.append(...buttons);
    // The follow switch sits with the view-mode buttons, styled like
    // one: no extra control crowds the transport row. A host without a
    // view-mode bar keeps the old transport toggle instead, so bar-less
    // callers still get their switch.
    if (options.follow) {
      const followLabel = options.follow.label || "Follow";
      const modeBar = host.querySelector(":scope > .lex-model-view-modes");
      const followButton = element("button", {type: "button",
        class: modeBar ? "lex-model-view-mode" : "lex-anim-transport-button lex-anim-follow-button",
        "data-anim-follow": "",
        "aria-label": followLabel, title: followLabel, "aria-pressed": "false",
        onclick: () => {
          state.follow = !state.follow;
          followButton.setAttribute("aria-pressed", String(state.follow));
          if (modeBar) followButton.classList.toggle("active", state.follow);
          options.follow.change?.(state.follow);
        }}, modeBar ? modelViewModeIcon("follow") : followLabel);
      if (modeBar) {
        // Remounts re-attach the cached bar with its stale toggle, so
        // the old switch goes before the fresh one takes its place.
        modeBar.querySelectorAll("[data-anim-follow]").forEach(node => node.remove());
        modeBar.append(followButton);
      } else transport.append(followButton);
    }
    timeline.append(scrub, transport);
    slider.oninput = () => { state.time = parseFloat(slider.value) * frameDur; };
    if (status) status.textContent = options.statusText ?? "";
    const controller = {
      play: () => setPlaying(true),
      pause: () => setPlaying(false),
      toggle: () => setPlaying(!state.playing),
      step: delta => goToFrame(Math.round(state.time / frameDur) + delta),
      toStart: () => goToFrame(0),
      toEnd: () => goToFrame(count - 1),
      // Selecting an event seeks the playhead to it, the way clicking
      // its marker does: same cues, same playing state. Unknown ids
      // (a viewer behind the list) report false and move nothing.
      toEvent: id => {
        const cue = (frames.events || []).find(event => event.id === id);
        if (!cue) return false;
        state.time = (Number(cue.start) || 0) % duration;
        sync();
        return true;
      },
      get playing() { return state.playing; },
      get follow() { return state.follow; },
      get frame() { return Math.round(state.time / frameDur); },
      get count() { return count; },
      get duration() { return duration; },
      stop: () => {
        if (!state.live) return;
        state.live = false;
        if (activeAnimationViewer === controller) activeAnimationViewer = null;
        try { options.dispose?.(); } finally {
          host.replaceChildren();
          delete host.dataset.ready;
        }
      },
    };
    if (host.isConnected) activeAnimationViewer = controller;
    let rendered = 0, last = performance.now();
    const loop = now => {
      if (!state.live || !host.isConnected) { controller.stop(); return; }
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      if (state.playing) state.time = (state.time + dt) % duration;
      options.render?.(sync(), state);
      if (++rendered === 2) {
        host.dataset.ready = "true";
        options.onReady?.();
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
    return controller;
  };

  // Every binding the shell owns, in one place: the panel lists them and the
  // key handler reads the same table, so the two cannot drift apart.
  const SHORTCUTS = [
    {id: "undo", keys: ["Ctrl", "Z"], label: "Undo"},
    {id: "redo", keys: ["Ctrl", "Shift", "Z"], label: "Redo"},
    {id: "save", keys: ["Ctrl", "S"], label: "Save"},
    {id: "tab", keys: ["Ctrl", "1-9"], label: "Jump to that numbered tab"},
    {id: "subtab", keys: ["Ctrl", "Shift", "1-9"], label: "Jump to that numbered subtab"},
    {id: "settings", keys: ["Ctrl", ","], label: "Open Lexeditor settings"},
    {id: "search", keys: ["Ctrl", "F"], label: "Focus the search bar"},
    {id: "info", keys: ["F1"], label: "Open or close the information page"},
    {id: "datamap", keys: ["Ctrl", "M"], label: "Open or close the Data Map"},
    {id: "launch", keys: ["Ctrl", "Enter"], label: "Launch the game"},
    {id: "restart", keys: ["Ctrl", "Shift", "R"], label: "Restart Lexeditor", developer: true},
  ];

  // Matched on event.code, the physical key, so a Dvorak or AZERTY layout gets
  // the same chords in the same places. event.key alone reports the remapped
  // letter and silently breaks every binding on a non-QWERTY layout.
  // Tab shortcuts run past nine: 1-9, then 0 for the tenth, then - and = for
  // the eleventh and twelfth. This returns the 1-based POSITION, not the
  // character, so a caller can index straight into the tab list.
  const SHORTCUT_ORDINALS = {
    Digit0: 10, Numpad0: 10,
    Minus: 11, NumpadSubtract: 11,
    Equal: 12, NumpadAdd: 12,
  };
  const SHORTCUT_ORDINAL_KEYS = {"0": 10, "-": 11, "=": 12};
  const shortcutDigit = event => {
    const fromCode = /^(?:Digit|Numpad)([1-9])$/.exec(event.code || "");
    if (fromCode) return fromCode[1];
    const byCode = SHORTCUT_ORDINALS[event.code || ""];
    if (byCode) return String(byCode);
    if (/^[1-9]$/.test(event.key)) return event.key;
    const byKey = SHORTCUT_ORDINAL_KEYS[event.key];
    return byKey ? String(byKey) : "";
  };
  const shortcutLetter = event => {
    const fromCode = /^Key([A-Z])$/.exec(event.code || "");
    if (fromCode) return fromCode[1].toLocaleLowerCase();
    return event.key.length === 1 ? event.key.toLocaleLowerCase() : "";
  };
  const matchShortcut = (event, developerMode) => {
    if (event.key === "F1" || event.code === "F1") return "info";
    if (!event.ctrlKey && !event.metaKey) return "";
    if (event.code === "Comma" || event.key === ",") return "settings";
    if (event.code === "Enter" || event.code === "NumpadEnter" || event.key === "Enter") return "launch";
    const digit = shortcutDigit(event);
    if (digit) return event.shiftKey ? "subtab" : "tab";
    const letter = shortcutLetter(event);
    if (letter === "z") return event.shiftKey ? "redo" : "undo";
    if (letter === "s") return "save";
    if (letter === "m") return "datamap";
    if (letter === "f") return "search";
    if (letter === "r" && event.shiftKey) return developerMode ? "restart" : "";
    return "";
  };

  let shortcutPanel = null;
  const flashShortcut = id => {
    const row = shortcutPanel?.querySelector(`[data-lex-shortcut="${id}"]`);
    if (!row) return;
    row.classList.remove("lex-shortcut-fired");
    void row.offsetWidth;
    row.classList.add("lex-shortcut-fired");
    setTimeout(() => row.classList.remove("lex-shortcut-fired"), 600);
  };
  const closeShortcutPanel = () => {
    shortcutPanel?.remove();
    shortcutPanel = null;
  };
  // What Developer Mode adds with the mouse. Every change here is shipped
  // to everyone, and Ctrl+Z takes it back. Right-click the shortcuts button
  // for this list.
  const DEVELOPER_GESTURES = [
    {id: "rename-property", keys: ["Double-click", "property name"], label: "Rename the property"},
    {id: "rename-section", keys: ["Double-click", "section heading"], label: "Rename the section"},
    {id: "edit-help", keys: ["Double-click", "?"], label: "Edit the help bubble's text"},
    {id: "move-property", keys: ["Drag", "property row"], label: "Move the property, within or between sections"},
    {id: "hide-property", keys: ["Hold right", "property"], label: "Hide it for readers without Show hidden properties; again to show it"},
    {id: "add-section", keys: ["Hold right", "section heading"], label: "Add a new section below it; on an empty section, remove it"},
    {id: "fill-tab", keys: ["Hold right", "panel tab"], label: "Add a section to it; on an empty tab, remove it"},
    {id: "save-view", keys: ["Hold right", "page tab or subtab"], label: "Save the page's view as the shipped default"},
    {id: "undo-layout", keys: ["Ctrl", "Z"], label: "Undo any of these"},
  ];
  const openShortcutPanel = (developerMode, gestures = false) => {
    if (shortcutPanel) { closeShortcutPanel(); return; }
    // The panel lists only what is available now: the animation bindings
    // join the shell's own while a viewer is mounted, and vanish with it.
    const available = SHORTCUTS.filter(entry => !entry.developer || developerMode);
    if (activeAnimationViewer) available.push(...ANIMATION_SHORTCUTS);
    const list = gestures ? DEVELOPER_GESTURES : available;
    const title = gestures ? "Developer Mode gestures" : "Keyboard shortcuts";
    const rows = list.map(entry =>
      element("div", {class: "lex-shortcut-row", "data-lex-shortcut": entry.id},
        element("span", {class: "lex-shortcut-keys"},
          ...entry.keys.map(key => element("kbd", {}, key))),
        element("span", {class: "lex-shortcut-label"}, entry.label)));
    const dialog = element("section", {
      class: "lex-dialog lex-shortcut-panel", role: "dialog", "aria-modal": "false",
      "aria-label": title,
    }, element("h2", {}, title), ...rows);
    shortcutPanel = element("div", {
      class: "lex-dialog-backdrop lex-shortcut-backdrop",
      onclick: closeShortcutPanel,
    }, dialog);
    dialog.addEventListener("click", event => event.stopPropagation());
    document.body.append(shortcutPanel);
    return shortcutPanel;
  };

  const createWindowActions = () => {
    const minimize = element("button", {
      id: "window-minimize", class: "lex-window-button", title: "Minimize",
      "aria-label": "Minimize window", "data-window-action": "minimize",
    }, element("span", {class: "lex-window-icon", "aria-hidden": "true"}));
    const maximize = element("button", {
      id: "window-maximize", class: "lex-window-button", title: "Maximize",
      "aria-label": "Maximize window", "data-window-action": "maximize",
    }, element("span", {class: "lex-window-icon", "aria-hidden": "true"}));
    const close = element("button", {
      id: "window-close", class: "lex-window-button lex-window-close", title: "Close",
      "aria-label": "Close window", "data-window-action": "close",
    }, element("span", {class: "lex-window-icon", "aria-hidden": "true"}));
    return {
      root: element("div", {class: "lex-window-actions"}, minimize, maximize, close),
      minimize, maximize, close,
    };
  };

  const githubLogo = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 16 16");
    svg.setAttribute("width", "20");
    svg.setAttribute("height", "20");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("d", "M8 0C3.58 0 0 3.64 0 8.13c0 3.59 2.29 6.64 5.47 7.72.4.08.55-.18.55-.39 0-.19-.01-.83-.01-1.5-2.01.38-2.53-.5-2.69-.96-.09-.23-.48-.96-.82-1.15-.28-.15-.68-.53-.01-.54.63-.01 1.08.59 1.23.83.72 1.23 1.87.88 2.33.67.07-.53.28-.88.51-1.08-1.78-.21-3.64-.91-3.64-4.02 0-.89.31-1.62.82-2.19-.08-.2-.36-1.04.08-2.16 0 0 .67-.22 2.2.84A7.45 7.45 0 0 1 8 3.93c.68 0 1.36.09 2 .27 1.53-1.06 2.2-.84 2.2-.84.44 1.12.16 1.96.08 2.16.51.57.82 1.3.82 2.19 0 3.12-1.87 3.81-3.65 4.02.29.25.54.74.54 1.5 0 1.08-.01 1.95-.01 2.22 0 .22.15.47.55.39A8.13 8.13 0 0 0 16 8.13C16 3.64 12.42 0 8 0Z");
    svg.append(path);
    return svg;
  };

  const settingsIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "19");
    svg.setAttribute("height", "19");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("fill", "currentColor");
    path.setAttribute("d", "M19.43 12.98c.04-.32.07-.65.07-.98s-.03-.66-.08-.98l2.11-1.65a.5.5 0 0 0 .12-.64l-2-3.46a.5.5 0 0 0-.61-.22l-2.49 1a7.3 7.3 0 0 0-1.69-.98L14.5 2.42A.49.49 0 0 0 14 2h-4a.49.49 0 0 0-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1a.49.49 0 0 0-.61.22l-2 3.46a.49.49 0 0 0 .12.64l2.11 1.65c-.04.32-.08.66-.08.98s.03.66.08.98l-2.11 1.65a.5.5 0 0 0-.12.64l2 3.46a.5.5 0 0 0 .61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.04.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.58 1.69-.98l2.49 1c.23.08.49 0 .61-.22l2-3.46a.5.5 0 0 0-.12-.64l-2.11-1.65ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z");
    svg.append(path);
    return svg;
  };

  const mapIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.8");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("d", "M3 5.5 9 3l6 2.5L21 3v15.5L15 21l-6-2.5L3 21V5.5Zm6-2.5v15.5m6-13V21");
    svg.append(path);
    return svg;
  };

  const infoIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const circle = document.createElementNS(namespace, "circle");
    circle.setAttribute("cx", "12"); circle.setAttribute("cy", "12"); circle.setAttribute("r", "9");
    circle.setAttribute("fill", "none"); circle.setAttribute("stroke", "currentColor"); circle.setAttribute("stroke-width", "1.8");
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("fill", "currentColor");
    path.setAttribute("d", "M11 10h2v7h-2zm0-4h2v2h-2z");
    svg.append(circle, path);
    return svg;
  };

  const saveIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const body = document.createElementNS(namespace, "path");
    body.setAttribute("fill", "#8177b8");
    body.setAttribute("stroke", "currentColor");
    body.setAttribute("stroke-width", "1.4");
    body.setAttribute("d", "M4 3h14l2 2v16H4V3Z");
    const label = document.createElementNS(namespace, "path");
    label.setAttribute("fill", "#e6e6ed");
    label.setAttribute("d", "M7 4h8v6H7V4Zm0 10h10v6H7v-6Z");
    const slot = document.createElementNS(namespace, "path");
    slot.setAttribute("fill", "#393653");
    slot.setAttribute("d", "M13 5h2v4h-2V5Z");
    svg.append(body, label, slot);
    return svg;
  };

  const gameProcessIcon = running => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const body = document.createElementNS(namespace, running ? "rect" : "path");
    if (running) {
      body.setAttribute("x", "6"); body.setAttribute("y", "6");
      body.setAttribute("width", "12"); body.setAttribute("height", "12");
      body.setAttribute("rx", "1");
    } else {
      body.setAttribute("d", "M8 5v14l11-7z");
    }
    body.setAttribute("fill", "currentColor");
    svg.append(body);
    return svg;
  };
  const playIcon = () => gameProcessIcon(false);
  const stopIcon = () => gameProcessIcon(true);

  // Settings use the same visual and interaction contract as the command-row
  // save control, but their dirty count and restore operation stay scoped to
  // the settings surface that owns the button.
  const pendingChangeList = (before, after, path = "", result = []) => {
    if (Object.is(before,after)) return result;
    if (before && after && typeof before === "object" && typeof after === "object") {
      const identity = after.label || after.name || after.key;
      const prefix = identity ? `${path} · ${identity}` : path;
      for (const key of new Set([...Object.keys(before),...Object.keys(after)]))
        pendingChangeList(before[key],after[key],`${prefix}${prefix?" / ":""}${key}`,result);
    } else result.push({label:path || "Value",before,after});
    return result;
  };
  // A popup whose anchor left the document is stranded: removing an element
  // fires no mouseleave, so tab switches, record selects and re-renders all
  // orphaned their cards until Escape. Open popups register here; one
  // observer closes any whose anchor is removed, at any depth. It costs
  // nothing while no popup is open.
  const liveHoverPopups = new Set();
  new MutationObserver(records => {
    if (!liveHoverPopups.size) return;
    for (const record of records) {
      for (const node of record.removedNodes) {
        if (!(node instanceof Element)) continue;
        for (const entry of [...liveHoverPopups]) {
          if (entry.anchor === node || node.contains(entry.anchor)) entry.close();
        }
      }
    }
  }).observe(document.documentElement, {childList: true, subtree: true});
  // One hover card for anything that previews what it points at: the save
  // button's pending changes, or a linked record. `build` returns the card's
  // contents, or a promise of them; a card whose anchor was left before the
  // contents arrived is never shown.
  const hoverPreview = (anchor, build, className = "") => {
    let popup, timer, request = 0, entry = null;
    const close=()=>{clearTimeout(timer);request++;popup?.remove();popup=null;anchor.removeAttribute('aria-describedby');if(entry)liveHoverPopups.delete(entry);};
    const leave=()=>{timer=setTimeout(close,180)};
    const show=async()=>{
      clearTimeout(timer);if(popup||anchor.disabled)return;
      const token=++request;
      let contents;
      try{contents=await build();}catch(error){contents=element('p',{},error?.message||String(error));}
      if(token!==request||popup||!anchor.isConnected||!contents)return;
      popup=element('div',{class:['lex-help-popover',className].filter(Boolean).join(' '),role:'tooltip',id:`hover-preview-${Math.random().toString(36).slice(2)}`},contents);
      document.body.append(popup);anchor.setAttribute('aria-describedby',popup.id);
      entry={anchor,close};liveHoverPopups.add(entry);
      const r=anchor.getBoundingClientRect(),box=popup.getBoundingClientRect();
      popup.style.left=`${Math.max(8,Math.min(r.left+r.width/2-box.width/2,innerWidth-box.width-8))}px`;
      const below=innerHeight-r.bottom-16,above=r.top-16;
      const useBelow=box.height<=below || below>=above;
      popup.style.maxHeight=`${Math.max(0,useBelow?below:above)}px`;
      popup.style.top=`${useBelow?r.bottom+8:Math.max(8,r.top-popup.getBoundingClientRect().height-8)}px`;
      popup.addEventListener('mouseenter',()=>clearTimeout(timer));popup.addEventListener('mouseleave',leave);
    };
    anchor.addEventListener('mouseenter',show);anchor.addEventListener('mouseleave',leave);
    anchor.addEventListener('focus',show);anchor.addEventListener('blur',leave);anchor.addEventListener('click',close);
    document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
    new MutationObserver(()=>{if(anchor.disabled)close()}).observe(anchor,{attributes:true,attributeFilter:['disabled']});
    return close;
  };
  // The save button's list reads newest first (Lexer: "new things get placed
  // on the top of the list"). A plugin's list is in its data's order, so each
  // change is stamped when it first appears or its value changes; the shell
  // looks after every edit, and the hover sorts by the stamps. A list given
  // newest first already keeps its order.
  const saveChangePreview = (button, changes, count) => {
    const value=x=>x===undefined?"Not set":x===null?"None":typeof x==='boolean'?(x?'On':'Off'):typeof x==='object'?JSON.stringify(x):String(x);
    const stamps=new Map();let clock=0;
    const order=rows=>{
      const present=new Set();
      for(const row of [...rows].reverse()){
        const label=String(row.label),seen=stamps.get(label),signature=JSON.stringify([row.before,row.after]);
        present.add(label);
        if(!seen||seen.signature!==signature)stamps.set(label,{stamp:++clock,signature});
      }
      for(const label of [...stamps.keys()])if(!present.has(label))stamps.delete(label);
      return rows.map((row,index)=>({row,index,stamp:stamps.get(String(row.label)).stamp}))
        .sort((a,b)=>b.stamp-a.stamp||a.index-b.index).map(entry=>entry.row);
    };
    button.lexNoteChanges=()=>{try{order(count?.()?changes?.()||[]:[]);}catch(_error){}};
    hoverPreview(button,()=>{
      const rows=order(count?.()?changes?.() || []:[]);
      return rows.length?element('ul',{},...rows.map(row=>element('li',{},element('strong',{},row.label),element('div',{},element('span',{},value(row.before)), ' → ',element('span',{},value(row.after)))))):element('p',{},count?.()?'Change details are unavailable.':'No pending changes.');
    },'lex-save-preview');
  };

  const settingsSaveControl = (options = {}) => {
    const count = element("span", {class: "lex-save-count", hidden: true, "aria-hidden": "true"});
    const button = element("button", {
      type: "button", class: "save lex-save-icon lex-settings-save-control",
      title: "No unsaved settings changes", "aria-label": "Save settings", disabled: true,
    }, saveIcon(), count);
    saveChangePreview(button,options.pendingChanges,options.dirtyCount);
    let busy = false;
    const dirtyCount = () => Math.max(0, Math.trunc(Number(options.dirtyCount?.()) || 0));
    const renderContents = () => {
      button.replaceChildren(busy
        ? element("span", {class: "lex-save-throbber", "aria-hidden": "true"})
        : saveIcon(), count);
    };
    const refresh = () => {
      const dirty = dirtyCount();
      button.disabled = busy || !!options.readonly?.() || !dirty;
      button.title = busy ? "Saving settings" : (dirty
        ? `Save ${dirty} unsaved setting change${dirty === 1 ? "" : "s"}`
        : "No unsaved settings changes");
      button.setAttribute("aria-label", button.title);
      count.textContent = String(dirty);
      count.hidden = !dirty;
      options.changed?.(dirty);
    };
    const setBusy = value => {
      busy = !!value;
      document.body.classList.toggle("lex-save-busy", busy);
      document.body.inert = busy;
      button.classList.toggle("saving", busy);
      button.setAttribute("aria-busy", String(busy));
      renderContents();
      refresh();
    };
    button.onclick = async () => {
      if (busy || button.disabled) return;
      setBusy(true);
      let failure = null;
      try { await options.save?.(); playThemeSound("save"); }
      catch (error) { failure = error; }
      finally { setBusy(false); }
      if (failure) showAlert({title: "Settings save failed",
        message: String(failure.message || failure)});
    };
    button.oncontextmenu = event => {
      event.preventDefault();
      if (busy || button.disabled || typeof options.discard !== "function") return;
      confirmDiscardChanges({
        dirtyCount,
        discard: async () => { await options.discard(); refresh(); },
      });
    };
    const editRefresh = () => {
      if (!button.isConnected) {
        document.removeEventListener("input", editRefresh, true);
        document.removeEventListener("change", editRefresh, true);
        return;
      }
      queueMicrotask(refresh);
    };
    document.addEventListener("input", editRefresh, true);
    document.addEventListener("change", editRefresh, true);
    button.refresh = refresh;
    queueMicrotask(refresh);
    return button;
  };

  const folderIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.8");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("d", "M3 6.5h7l2 2h9v10H3v-12Zm0 2h18");
    svg.append(path);
    return svg;
  };

  // The file-location button: one folder glyph in a detail header that opens
  // the record's file in Explorer. A mod replacement wins over the shipped
  // file; with neither, the button sits disabled. Both paths stay on the
  // desktop side of `callWindow`, so the browser never sees them.
  const fileLocationButton = ({plugin, modFile = null, gameFile = null} = {}) => {
    const label = modFile && gameFile ? "Show this record's file in Explorer (mod copy first)"
      : modFile ? "Show the mod replacement in Explorer"
      : gameFile ? "Show the shipped file in Explorer"
      : "No file to reveal";
    return element("button", {type: "button", class: "lex-header-icon lex-file-location-button",
      title: label, "aria-label": label, disabled: !(modFile || gameFile),
      onclick: event => { event.stopPropagation(); callWindow("open_mod_file_location", plugin, modFile, gameFile); }},
      folderIcon());
  };

  const restartIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    // One sweep with a solid head, instead of two arcs ending in bare ticks.
    for (const [d, filled] of [["M16.59 5.45 A8 8 0 1 1 9.26 4.48", false], ["M12.46 3.32 L10.05 6.64 L8.48 2.32 Z", true]]) {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("fill", filled ? "currentColor" : "none");
      path.setAttribute("stroke", filled ? "none" : "currentColor");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  };

  const historyIcon = direction => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("d", direction === "redo"
      ? "M15.5 7 20 11.5 15.5 16M19.5 11.5H11a6 6 0 0 0-6 6"
      : "M8.5 7 4 11.5 8.5 16M4.5 11.5H13a6 6 0 0 1 6 6");
    svg.append(path);
    return svg;
  };

  const askProjectName = async (pluginName, options = {}) => {
    let suggestions = [];
    try {
      const response = await fetch("/shared/assets/mod_names.json", {cache: "no-store"});
      if (response.ok) suggestions = await response.json();
    } catch (_error) {}
    const suggested = options.value || suggestions[Math.floor(Math.random() * suggestions.length)] || "My Mod";
    return new Promise(resolve => {
    const backdrop = element("div", {class: "lex-dialog-backdrop", "data-lex-history-control": true});
    const input = element("input", {type: "text", maxlength: "80", value: suggested, placeholder: `${pluginName} mod name`, "aria-label": options.rename ? "Mod name" : "New mod name"});
    const message = element("div", {class: "lex-dialog-status", "aria-live": "polite"});
    let parent = "";
    const cancel = element("button", {class: "lex-dialog-action"}, "Cancel");
    const create = element("button", {class: "lex-dialog-action primary"}, options.rename ? "Rename" : (options.createLabel || "Create"));
    // Every mod carries a name, and optionally an author and a description,
    // in its mod.json (core/mod_metadata.py). Creating one asks for them here.
    const author = options.details ? element("input", {type: "text", maxlength: "200", value: options.author || "",
      placeholder: "Author (optional)", "aria-label": "Author"}) : null;
    const about = options.details ? element("textarea", {maxlength: "4000", rows: "5",
      placeholder: "Description (optional)", "aria-label": "Description"}, options.about || "") : null;
    const close = value => { backdrop.remove(); resolve(value); };
    cancel.onclick = () => close(null);
    create.onclick = () => {
      const value = input.value.trim();
      if (!value) { message.textContent = "Enter a mod name."; input.focus(); return; }
      close(options.rename ? value : {name: value, parent,
        details: options.details ? {author: author.value.trim(), description: about.value.trim()} : undefined});
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") create.click();
      if (event.key === "Escape") close(null);
    });
    // Creating only asks for a name: the mod lands in this game's own
    // folder in the mod library shown in Settings. Choosing a different
    // location is a separate, explicit action, so naming a mod never
    // requires picking through a folder tree first.
    const location = !options.rename && typeof options.chooseLocation === "function"
      ? element("button", {type: "button", class: "lex-dialog-link", onclick: async () => {
          const chosen = await options.chooseLocation();
          if (chosen?.cancelled || !chosen?.parent) return;
          parent = chosen.parent;
          message.textContent = `Will be created in: ${parent}`;
        }}, "Choose a different location…")
      : null;
    backdrop.append(element("section", {class: "lex-dialog lex-project-dialog", role: "dialog", "aria-modal": "true"},
      element("h2", {}, options.rename ? "Rename Mod" : "Create New Mod"),
      element("p", {}, options.rename ? "Change the mod project folder name." : (options.description || "Lexeditor will create a new editable project from this game's working template.")),
      input, ...(options.details ? [author, about] : []), message,
      element("div", {class: "lex-dialog-actions"}, location, cancel, create)));
    document.body.append(backdrop); input.focus(); input.select();
    });
  };

  // "Did it actually pick anything up?" is the first thing a player wants to
  // know after pointing Lexeditor at a mod folder, and the answer used to be
  // silence. This turns one scan into a plain report: what the loader
  // recognised, and how much it will ignore.
  const modContentsReport = (contents, title) => {
    if (!contents) return;
    if (!contents.exists) {
      showAlert({title, message: `Nothing is there to read yet:
${contents.path}`});
      return;
    }
    if (!contents.declared) {
      showAlert({title, message:
        `${contents.files} file${contents.files === 1 ? "" : "s"} in ${contents.path}.

`
        + "This game's plugin has not declared which file types its loader recognises, "
        + "so Lexeditor cannot break that down yet."});
      return;
    }
    const found = contents.categories.filter(row => row.count > 0);
    const items = found.map(row => ({
      item: row.label,
      issue: `${row.count} file${row.count === 1 ? "" : "s"} (${row.suffixes.join(", ")})`,
    }));
    if (!items.length) {
      showAlert({title, message:
        `Lexeditor recognised none of the ${contents.files} file`
        + `${contents.files === 1 ? "" : "s"} in ${contents.path}.

`
        + "This mod will load nothing. Check that you pointed at the mod's own folder "
        + "rather than a folder above it."});
      return;
    }
    if (contents.unrecognized) {
      items.push({item: "Not recognised",
        issue: `${contents.unrecognized} file${contents.unrecognized === 1 ? "" : "s"} `
          + "this game's loader will ignore"});
    }
    showAlert({title, items, message: contents.path});
  };

  // One call that turns "this game has no mod" into a mod: name it, create it,
  // and let the host restart the plugin on the new project. The mod menu and a
  // game's own page both need it, and a page that is showing the game's own
  // read-only data needs it most.
  const createModProject = async (pluginId, options = {}) => {
    const named = await askProjectName(options.pluginName || pluginId,
      {...options, details: true, chooseLocation: () => callWindow("choose_mod_project_location", pluginId)});
    if (!named) return null;
    const result = await callWindow("create_mod_project", pluginId, named.name, named.parent || "", named.details || {});
    // The host restarted the editor on the new mod; the old page's service
    // is gone, so every caller follows it there.
    if (result?.url) { window.__lexeditorNavigating = true; location.href = result.url; }
    return result;
  };

  const mountProjectControl = (options, host) => {
    const mode = element("span", {class: "lex-project-source-mode", hidden: true});
    const name = element("span", {class: "lex-project-name"}, "Loading mod…");
    const path = element("span", {class: "lex-project-path"});
    const status = element("span", {class: "lex-project-source-status", hidden: true});
    const trigger = element("button", {
      class: "lex-project-select", type: "button", "aria-label": "Active mod project",
      title: "Choose a mod project", "aria-haspopup": "menu", "aria-expanded": "false",
    }, mode, name, path, status);
    const menu = element("div", {class: "lex-project-menu", role: "menu", hidden: true});
    const box = element("div", {class: "lex-project-control", hidden: true}, trigger, menu);
    host.append(box);
    let snapshot = null;
    let modSupport = null;
    const closeMenu = () => { menu.hidden = true; trigger.setAttribute("aria-expanded", "false"); };
    // One name column for the whole menu, taken from the longest name in it, so
    // every row's description starts on the same edge. Measured rather than
    // guessed: a mod is named by the person using it, and "Vanilla" is not the
    // longest thing this list ever holds. A hidden menu measures as nothing, so
    // this runs once it is actually on screen as well as on every render.
    const measureNameColumn = () => {
      if (menu.hidden) return;
      menu.style.removeProperty("--lex-project-name-width");
      const names = [...menu.querySelectorAll(".lex-project-menu-name")];
      if (!names.length) return;
      const widest = Math.ceil(Math.max(...names.map(node => node.getBoundingClientRect().width)));
      if (widest > 0) menu.style.setProperty("--lex-project-name-width", `${widest}px`);
    };
    // The menu opens on its cached snapshot, then refreshes it: switches
    // flipped in the Mods tab and new loader flags must show up without a
    // page reload. A failed refresh keeps the cache; it never hides the menu.
    const refreshSnapshot = async () => {
      try {
        const value = options.projectSnapshot
          ? await options.projectSnapshot()
          : await callWindow("mod_projects", options.plugin.id);
        if (value) render(value);
      } catch (_error) { /* keep the cached menu for this open */ }
    };
    // A mod package dropped anywhere on the program lands in the Mods
    // tab's import flow: the Mods tab stays the single place that
    // uploads and inspects packages, but nobody should have to hunt for
    // it first. Text and in-page drags are untouched, as are drops onto
    // fields or onto a dialog (an open import never stacks another).
    const globalDropFiles = event => {
      if (![...(event.dataTransfer?.types || [])].includes("Files")) return false;
      if (event.target.closest?.(".lex-dialog, input, textarea, select, [contenteditable=true]")) return false;
      return true;
    };
    document.addEventListener("dragover", event => {
      if (globalDropFiles(event)) event.preventDefault();
    });
    document.addEventListener("drop", async event => {
      if (!globalDropFiles(event)) return;
      event.preventDefault();
      if (modSupport && !modSupport.canManage) return;
      // The Mods tab only accepts the drop once its first load sets its
      // switches, so it must finish opening first.
      if (options.activeTab?.() !== "mods") options.navigate?.("mods");
      await options.importModDrop?.(event.dataTransfer).catch(() => {});
    });
    const toggleMenu = () => {
      const open = menu.hidden;
      if (open && snapshot) render(snapshot);
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      if (open) { measureNameColumn(); refreshSnapshot(); }
    };
    const openResult = result => {
      if (!result || result.cancelled) { render(snapshot); return false; }
      if (result.url) {
        window.__lexeditorNavigating = true;
        location.href = result.url;
        return true;
      }
      snapshot = result; render(snapshot); return true;
    };
    const guarded = operation => confirmUnsavedExit(options, async () => {
      try { return openResult(await operation()); }
      // A browser alert is an OS dialog wearing the WebView's clothes. Every
      // message Lexeditor shows is its own.
      catch (error) { showAlert({title: "Could not switch mod project", message: String(error?.message || error)}); return false; }
    }, {question: "Save before switching mod projects?", exitError: "Could not switch mod projects"});
    const render = value => {
      snapshot = value;
      const rows = value?.projects || [];
      const current = rows.find(row => row.current);
      const sources = options.projectSources?.() || [];
      const vanillaSource = sources.find(row => String(row.key) === "vanilla") || null;
      const activeSource = String(options.projectActiveSource?.() || "mine");
      const selectedReference = sources.find(row => String(row.key) === activeSource);
      const selectedSource = activeSource === "mine" && current ? {
        key:"mine", label:current.name, path:current.path || "", readOnly:current.readOnly === true,
        enabled:current.enabled !== false,
      } : selectedReference;
      const canChoose = Boolean(value);
      box.hidden = !current && !selectedSource && !canChoose;
      if (!current && !selectedSource && !canChoose) return;
      // A game nobody has modded yet: the folder this game would use is a
      // plan, not a mod, so the control says what is true and the menu offers
      // to add or find one.
      const noMod = Boolean(current?.noMod);
      // A game with no mod yet is showing the game's own data, so the control
      // names that source. It used to read "No mod" over the folder a mod would
      // USE, which reads as a mod that exists and is empty, and sent readers
      // looking in tModLoader's ModSources for something that was never created.
      const vanilla = vanillaSource || {label: "Vanilla", path: "The game's own data", readOnly: true};
      const readOnly = noMod ? true : selectedSource?.readOnly !== false;
      mode.hidden = !selectedSource && !noMod;
      mode.textContent = readOnly ? "🔒" : "📝";
      mode.setAttribute("aria-label", readOnly ? "Read only" : "Editable");
      name.textContent = noMod ? vanilla.label
        : selectedSource?.label || current?.name || "Select a mod";
      status.hidden = true;
      status.textContent = selectedSource?.enabled === false ? "×" : "✓";
      status.className = `lex-project-source-status ${selectedSource?.enabled === false ? "disabled" : "enabled"}`;
      status.setAttribute("aria-label", selectedSource?.enabled === false ? "Disabled" : "Enabled");
      // The header shows the state, not the game's install path: a long path
      // squeezed the source's own name down to one letter. The menu keeps the
      // path, where there is room for it.
      path.textContent = noMod ? "The game's own data" : (selectedSource?.path || (selectedSource
        ? (selectedSource.readOnly === false ? "Editable mod" : "Read-only reference")
        : current?.path || "New Mod or Find a Mod"));
      box.title = noMod
        ? `This game has no mod yet, so ${vanilla.label} is shown read-only: it is the `
          + "game's own data and there is no mod folder to write into. Add a Mod creates "
          + "an editable mod; Find a Mod opens one you already have."
          + (vanilla.path ? `\n\n${vanilla.path}` : "")
        : path.textContent;
      const projects = (options.sourcesReplaceProjects ? [] : rows.filter(row => (row.valid || row.notEditable) && !row.noMod)).map(row => {
        // The Mods tab's list: a mod the editor cannot open is shown, greyed,
        // with the reason, rather than missing from one list and not the other.
        // Same five columns as an editable row: the select's mode, name and
        // path, then the actions lane (warning flags, if any), then the
        // on/off mark. Without the actions lane the mark lands a column
        // early, and a flag pushes the path out of its column.
        const folder = element("button", {
          class: "lex-project-folder", type: "button",
          title: `Open the ${row.name} folder`, "aria-label": `Open the ${row.name} folder`,
          onclick: async event => {
            event.preventDefault();
            event.stopPropagation();
            closeMenu();
            try { await callWindow("open_mod_folder", options.plugin.id, row.path); }
            catch (error) { showAlert({title: "Could not open the mod folder", message: error.message || String(error)}); }
          },
        }, folderIcon());
        // "What did Lexeditor find in this mod?" belongs to a mod, so it is a
        // button on that mod's row beside its pencil and its folder. It used
        // to be a lone circle crammed in beside the mod name in the command
        // row, where it annotated whichever mod happened to be loaded.
        const about = element("button", {
          class: "lex-project-about", type: "button",
          title: `What did Lexeditor find in ${row.name}?`,
          "aria-label": `What did Lexeditor find in ${row.name}?`,
          onclick: async event => {
            event.preventDefault();
            event.stopPropagation();
            closeMenu();
            try {
              const contents = await callWindow("mod_project_contents", options.plugin.id, row.path);
              modContentsReport(contents, `${row.name} contents`);
            } catch (error) {
              showAlert({title: "Could not read the mod folder",
                         message: error.message || String(error)});
            }
          },
        }, infoIcon());
        if (row.notEditable) return element("div", {class: "lex-project-menu-item lex-project-menu-item-unavailable", title: row.notEditable},
          element("span", {class: "lex-project-menu-item-select", "aria-disabled": "true", role: "menuitem", "aria-label": `${row.name}: ${row.notEditable}`},
            element("span", {class: "lex-project-source-mode", "aria-hidden": "true"}, "🔒"),
            element("span", {class: "lex-project-menu-name"}, row.name, row.version ? ` · ${row.version}` : ""),
            element("span", {class: "lex-project-menu-path"}, row.path)),
          element("span", {class: "lex-project-menu-item-actions"},
            folder, about, modFlagsMark(row.conflicts, row.alerts)),
          element("span", {class: `lex-project-source-status ${row.enabled === false ? "disabled" : "enabled"}`,
              "aria-label": row.enabled === false ? "Disabled" : "Enabled"}, row.enabled === false ? "×" : "✓"));
        const select = element("button", {
        class: `lex-project-menu-item-select${row.current && activeSource === "mine" ? " active" : ""}`,
        type: "button", role: "menuitem", title: row.path,
        onclick: () => {
          closeMenu();
          if (row.current && activeSource !== "mine") guarded(async () => {
            await options.selectProjectSource?.("mine");
            render(snapshot);
          });
          else if (!row.current) guarded(() => callWindow("select_mod_project", options.plugin.id, row.path));
        },
      }, element("span", {class: "lex-project-source-mode", "aria-label":"Editable"}, "📝"),
      element("span", {class: "lex-project-menu-name"}, row.name, row.version ? ` · ${row.version}` : ""),
      element("span", {class: "lex-project-menu-path"}, row.path),
      element("span", {class:`lex-project-source-status ${row.enabled === false ? "disabled" : "enabled"}`,
        "aria-label":row.enabled === false ? "Disabled" : "Enabled"}, row.enabled === false ? "×" : "✓"));
        const rename = element("button", {class:"lex-project-rename",type:"button",title:`Rename ${row.name}`,"aria-label":`Rename ${row.name}`,onclick:async()=>{closeMenu();const next=await askProjectName(options.plugin.name||options.plugin.id,{rename:true,value:row.name});if(next&&next!==row.name)guarded(()=>callWindow("rename_mod_project",options.plugin.id,row.path,next))}}, "✎");
        return element("div", {class:`lex-project-menu-item${row.current&&activeSource==="mine"?" active":""}`},
          select,
          element("span", {class: "lex-project-menu-item-actions"}, rename, folder, about,
            modFlagsMark(row.conflicts, row.alerts)),
          select.querySelector(".lex-project-source-status"));
      });
      const sourceRows = sources.map((row,index) => {
        const select=element("button", {
          class:`lex-project-menu-item-select${String(row.key)===activeSource?" active":""}`,
          type:"button",role:"menuitem","aria-label":row.label,
          onclick:()=>{closeMenu();if(String(row.key)!==activeSource)guarded(async()=>{
            await options.selectProjectSource?.(row.key);render(snapshot);
          });}
        },element("span",{class:"lex-project-source-mode"},row.readOnly===false?"📝":"🔒"),
          element("span",{class:"lex-project-menu-name"},row.label),
          element("span",{class:"lex-project-menu-path"},row.path||"Read-only reference"));
        const actions=element("span",{class:"lex-project-menu-item-actions"});
        const dragAttrs={};
        const run=async operation=>{try{await operation();render(snapshot)}catch(error){showAlert({title:"Could not update mods",message:error.message})}};
        const sourceStatus=row.managed && options.changeProjectSource
          ? element("input",{type:"checkbox",checked:row.enabled!==false,
            class:"lex-project-source-status",
            "aria-label":`Enable ${row.label}`,onchange:event=>run(async()=>{
              if(event.target.checked && !(await confirmFirstModEnable(row.path||row.key)))return;
              await options.changeProjectSource(row.key,{enabled:event.target.checked})})})
          : null;
        if(row.managed && options.changeProjectSource){
          Object.assign(dragAttrs,modOrderGestures({index,controls:"input,.lex-project-menu-item-actions",
            movable:at=>!!sources[at]?.managed,
            move:(from,by)=>run(()=>options.changeProjectSource(sources[from].key,{move:by}))}));
          if(row.removable)actions.append(element("button",{type:"button","aria-label":`Remove ${row.label}`,
            onclick:async()=>{if(await confirmAction({title:`Remove ${row.label}?`,message:"Remove this managed mod from the library?",confirmLabel:"Remove"}))run(()=>options.changeProjectSource(row.key,{remove:true}))}},"×"));
          if(row.settings?.length || row.notes?.length)actions.append(element("button",{
            type:"button","aria-label":`Options for ${row.label}`,onclick:()=>{
              closeMenu();
              const backdrop=element("div",{class:"lex-dialog-backdrop"});
              const close=()=>backdrop.remove();
              const body=(row.settings||[]).map(setting=>detailField({label:setting.name,
                control:element("select",{"aria-label":setting.name,onchange:event=>run(()=>
                  options.changeProjectSource(row.key,{option:setting.id,value:Number(event.target.value)}))},
                  ...setting.values.map(value=>element("option",{value:value.value,
                    selected:value.value===setting.value},value.name)))}));
              body.push(...(row.notes||[]).map(detailText));
              backdrop.append(element("section",{class:"lex-dialog",role:"dialog","aria-modal":"true","aria-label":`${row.label} options`},
                detailPanel({title:row.label,body}),element("div",{class:"lex-dialog-actions"},
                  element("button",{type:"button",onclick:close},"Close"))));
              backdrop.addEventListener("keydown",event=>{if(event.key==="Escape")close()});
              document.body.append(backdrop);backdrop.querySelector("select,button")?.focus();
            }},"⚙"));
        }
        return element("div",{class:`lex-project-menu-item lex-project-reference${String(row.key)===activeSource?" active":""}`,...dragAttrs},
          select,actions,sourceStatus);
      });
      const create = element("button", {
        class: "lex-project-menu-action", type: "button", role: "menuitem",
        // Adding or finding a project is not mod-library work and never was:
        // a plugin says whether it can create one through canCreate. Gating
        // these on a mod adapter took the action away from every game that
        // does not have one, Blank included.
        hidden: !value.canCreate, onclick: async () => {
          closeMenu();
          // Choosing a different location only makes sense for a game whose
          // mods are files on disk; a plugin with its own createProject
          // (Blank's in-browser samples) has no folder to offer one for.
          const named = await askProjectName(options.plugin.name || options.plugin.id, {
            details: !options.createProject,
            ...(options.projectCreatePrompt || {}),
            chooseLocation: options.createProject ? undefined
              : () => callWindow("choose_mod_project_location", options.plugin.id),
          });
          if (named) guarded(async () => {
            const result = options.createProject
              ? await options.createProject(named.name)
              : await callWindow("create_mod_project", options.plugin.id, named.name, named.parent || "", named.details || {});
            if (result?.contents && !result.cancelled) modContentsReport(result.contents, `Added ${named.name}`);
            return result;
          });
        },
      }, "➕ Add a Mod");
      const browse = element("button", {
        class: "lex-project-menu-action", type: "button", role: "menuitem",
        onclick: () => { closeMenu(); guarded(async () => {
          const result = options.browseProject
            ? await options.browseProject()
            : await callWindow("browse_mod_project", options.plugin.id);
          if (result?.contents && !result.cancelled) modContentsReport(result.contents, "Added mod");
          return result;
        }); },
      }, "🔍 Find a Mod");
      const addSource=options.addProjectSource?element("button",{
        class:"lex-project-menu-action",type:"button",role:"menuitem",
        onclick:async()=>{closeMenu();try{await options.addProjectSource();render(snapshot)}catch(error){showAlert({title:"Could not add mod",message:error.message})}}
      },"➕ Add a Mod"):null;
        // A game without mod management says so in the actions row. Adding
        // and finding a mod stay: they are project work, they work without
        // a mod adapter, and they are how a reader gets out of the
        // unmodded state.
        const modLibraryNote = modSupport && !modSupport.canManage
          ? element("p", {class:"lex-dialog-status"},
              modSupport.message || "Mod management is not supported for this game yet.")
          : null;
        // A game with no mod yet still has one thing to show: the game's own
        // read-only data. It belongs in the menu beside the actions that get
        // the reader out of that state, so the list does not read as empty.
        const vanillaMenuItem = noMod && !vanillaSource
          ? element("div", {class: "lex-project-menu-item lex-project-reference active"},
              element("span", {class: "lex-project-source-mode", "aria-label": "Read only"}, "🔒"),
              element("span", {class: "lex-project-menu-name"}, vanilla.label),
              element("span", {class: "lex-project-menu-path"}, vanilla.path))
          : null;
        // Every spread here must be a node or the argument list builds one:
        // replaceChildren turns a bare null into the text "null". This note is
        // for games that cannot manage mods, so on every game that can it was
        // passed as null and printed the word in the middle of the menu.
        menu.replaceChildren(...(vanillaMenuItem?[vanillaMenuItem]:[]), ...sourceRows, ...projects,
          element("div", {class: "lex-project-menu-actions", role: "group", "aria-label": "Mod project actions"}, addSource || create, browse,
            modLibraryNote));
      measureNameColumn();
    };
    trigger.onclick = event => { event.stopPropagation(); toggleMenu(); };
    let copyPromptOpen = false;
    // Clicking a property, or typing into a control, is an edit attempt. A
    // button inside one is not: pins, copy buttons and question marks stay
    // usable while the page is read-only.
    const isEditAttempt = (target, event) => {
      if (!target?.closest?.("main") || target.closest?.("button") ||
          target.closest?.(READONLY_EXEMPT)) return false;
      // A developer's double-click on a property name, a section heading or
      // a help bubble rewords Lexeditor's own shipped text, not the record's
      // data, so it is never gated behind having a mod open. The in-place
      // editor it opens is covered by READONLY_EXEMPT above. Developer Mode
      // is Lexer's own authenticated identity (lexeditor_settings), so
      // nobody else ever sees this exemption; the record's own input,
      // select or textarea is untouched by it and still asks to create a
      // mod.
      if (sharedSettingsSnapshot?.developerMode &&
          target.closest?.(".lex-detail-field-label-text,.lex-detail-section-title,.lex-info-help"))
        return false;
      // Clicking into a text box, selecting in it or dragging its resize
      // grip reads the value; only typing into it would change it. A switch,
      // a list or a number's spin arrows change it on the click itself.
      if (event.type === "keydown") return Boolean(target.matches?.("input,select,textarea,[contenteditable='true']"));
      return Boolean(target.closest?.(".lex-toggle")) || changesOnPointer(target, event);
    };
    requestModForEdit = () => protectManagedEdit({type: "request", target: document.querySelector("main") || document.body,
      preventDefault() {}, stopImmediatePropagation() {}});
    const protectManagedEdit = async event => {
      const current = snapshot?.projects?.find(row => row.current);
      if (event.type === "keydown" && !typesIntoValue(event)) return;
      if (copyPromptOpen || (event.type !== "request" && !isEditAttempt(event.target, event))) return;
      // A game with no mod has nothing to write into, so the attempt to edit
      // the game's own data is the moment to offer the way out of it.
      if (current?.noMod || current?.vanilla || sessionHasNoMod() ||
          String(options.projectActiveSource?.() || "") === "vanilla") {
        event.preventDefault(); event.stopImmediatePropagation();
        copyPromptOpen = true;
        try {
          const agreed = await confirmAction({
            title: "Create a mod to edit?",
            message: "This is the game's own data, so Lexeditor shows it read-only. "
              + "Create a mod to make your own editable version.",
            confirmLabel: "Create a mod"});
          if (!agreed) return;
          await createModProject(options.plugin.id, {pluginName: options.plugin.name});
        } finally { copyPromptOpen = false; }
        return;
      }
      if (!current?.readOnly || current.vanilla) return;
      event.preventDefault(); event.stopImmediatePropagation();
      copyPromptOpen = true;
      try {
        const agreed = await confirmAction({title:"Make an editable copy?",
          message:"This mod updates automatically, so direct edits would be lost. Make a copy with a new name to create your own version. You have my blessing.", confirmLabel:"Make a copy"});
        if (!agreed) return;
        const copyNamed = await askProjectName(options.plugin.name, {value:`${current.name} Copy`,
          createLabel:"Create copy", description:"Choose a name for your independent editable copy. It will be stored in the mod library."});
        if (copyNamed) await guarded(() => callWindow("copy_library_mod", options.plugin.id, current.path, copyNamed.name));
      } finally { copyPromptOpen = false; }
    };
    document.addEventListener("pointerdown", protectManagedEdit, true);
    document.addEventListener("keydown", protectManagedEdit, true);
    menu.onclick = event => event.stopPropagation();
    document.addEventListener("click", closeMenu);
    document.addEventListener("keydown", event => { if (event.key === "Escape") closeMenu(); });
    let loadAttempts = 0;
    const load = async () => {
      try {
        modSupport = await callWindow("mod_library_status", options.plugin.id);
        const value = options.projectSnapshot
          ? await options.projectSnapshot()
          : await callWindow("mod_projects", options.plugin.id);
        if (value) {
          render(value);
          // A selected mod deleted outside Lexeditor: the game opened on
          // Vanilla instead. Said once per session, not on every reload.
          const missing = value.missingProject;
          if (missing) {
            const key = `lex-missing-mod:${options.plugin.id}:${missing}`;
            let told = false;
            try { told = sessionStorage.getItem(key) === "1"; sessionStorage.setItem(key, "1"); } catch (_error) {}
            if (!told) showToast(`${missing} was not found, so ${options.plugin.name} opened on Vanilla. Choose or create a mod to edit again.`, {tone: "warning"});
          }
          return;
        }
        // WebView2 can expose window.pywebview before its API methods are
        // callable. Retry instead of permanently hiding the shared selector.
        if (!options.projectSnapshot && loadAttempts++ < 40) {
          setTimeout(load, 50);
          return;
        }
        box.hidden = true;
      } catch (_error) {
        // A game with no mod projects at all is simply the unmodded game.
        if (modSupport && !modSupport.canManage) render({projects:[{name:"Vanilla", path:"Unmodded game", valid:true, current:true, readOnly:true, vanilla:true}]});
        else box.hidden = true;
      }
    };
    if (options.projectSnapshot) load();
    else if (window.pywebview?.api) load();
    else window.addEventListener("pywebviewready", load, {once: true});
    box.refresh = () => { if (options.projectSnapshot) load(); else if (snapshot) render(snapshot); };
    return box;
  };

  const openSettings = async () => {
    document.querySelector(".lex-global-settings-backdrop")?.remove();
    const backdrop = element("div", {class: "lex-dialog-backdrop lex-global-settings-backdrop", "data-lex-history-control": true});
    const dialog = element("section", {class: "lex-dialog lex-global-settings", role: "dialog", "aria-modal": "true", "aria-label": "Lexeditor settings"});
    const plugin = document.querySelector("[data-lex-plugin-name]")?.dataset.lexPluginName
      || document.title.replace(/^Lexeditor\s*[-–]\s*/, "").trim();
    const heading = element("div", {class: "lex-global-settings-head"},
      element("h2", {}, "LEXEDITOR Settings"));
    const message = element("div", {class: "lex-dialog-status", "aria-live": "polite"}, "Loading settings…");
    let keyHandler = null;
    let settingsDirtyCount = () => 0;
    let libraryMoveActive = false;
    let restoreSettings = () => {};
    const fitDialog = () => {
      dialog.classList.remove("lex-settings-must-scroll");
      dialog.classList.remove("lex-settings-wide");
      if (dialog.scrollHeight > window.innerHeight - 24) dialog.classList.add("lex-settings-wide");
      dialog.classList.toggle("lex-settings-must-scroll",
        dialog.scrollHeight > Math.max(320, window.innerHeight - 24));
    };
    const close = () => {
      if (libraryMoveActive) return;
      if (keyHandler) document.removeEventListener("keydown", keyHandler);
      window.removeEventListener("resize", fitDialog);
      backdrop.remove();
    };
    const requestClose = () => {
      if (!settingsDirtyCount()) { close(); return; }
      confirmDiscardChanges({
        dirtyCount: settingsDirtyCount,
        discard: async () => { restoreSettings(); close(); },
      });
    };
    heading.append(closeButton({onclick: requestClose}));
    dialog.append(heading, message);
    backdrop.append(dialog); document.body.append(backdrop);
    backdrop.addEventListener("click", event => {
      if (event.target === backdrop && !settingsDirtyCount()) close();
      else if (event.target === backdrop) dialog.querySelector(".lex-close-button")?.focus();
    });
    keyHandler = event => { if (event.key === "Escape") requestClose(); };
    document.addEventListener("keydown", keyHandler);
    window.addEventListener("resize", fitDialog);
    try {
      let settings = rememberSharedSettings(await callWindow("lexeditor_settings"));
      if (!settings) throw new Error("The shared settings bridge is unavailable");
      const definitions = [
        {key:"updateCheckFrequency", scope:"user", title:"Update check frequency", description:"Used by LEXEDITOR and managed helpers such as FFNx.", type:"select", choices:settings.updateCheckChoices || []},
        {key:"hoverableAltClick", scope:"user", title:"Alt + Click hoverable linking", description:"When enabled, ordinary clicks do not follow linked record mentions. Alt+Click opens them.", type:"checkbox"},
        {key:"showHoverTooltips", scope:"user", title:"Show hover tooltips", type:"checkbox"},
        {key:"showHiddenProperties", scope:"user", title:"Show hidden properties", description:"Shows the properties Lexeditor hides as not worth editing, dimmed.", type:"checkbox"},
        {key:"selectionHoldMs", scope:"user", title:"Searcher hold time", description:"How long a record must be held before a Searcher selects it.", type:"number", min:150, max:2000, step:50, unit:"ms"},
        {key:"booleanBoxStyle", scope:"user", title:"Wide boolean boxes", description:"An on/off property is one wide box that fills its row, ticked when on. Off draws a small checkbox at the end of an arrow from the property name.", type:"checkbox"},
        {key:"pageWrapAround", scope:"user", title:"Wrap around at the ends", description:"Paging past the last page returns to the first, and paging back from the first goes to the last.", type:"checkbox"},
        {key:"trustWarning", scope:"user", title:"Trust Warning", description:"Warn the first time a mod is enabled. Only enable mods you trust.", type:"checkbox"},
        {key:"panelTabTarget", scope:"user", title:"Tab key panel", description:"Tab opens the next panel tab. Shift+Tab opens the previous tab. Choose the panel under the mouse or the panel with keyboard focus.", type:"select", choices:[{value:"hover",label:"Hovered panel"},{value:"focus",label:"Focused panel"}]},
        {key:"tableRowsPerPage", scope:"user", title:"Table rows per page", description:"A full table page stretches this many rows to use the exact available panel height.", type:"number", min:5, max:40, step:1},
        {key:"panelGapPercent", scope:"user", title:"Panel spacing", description:"The same responsive gap surrounds panels and separates adjacent panels.", type:"number", min:.25, max:4, step:.05, unit:"%"},
        {key:"pagerBarHeightPercent", scope:"user", title:"Pagination bar height", description:"Height of the bottom table bar as a percentage of screen height at 100% UI scale. UI zoom scales this bar with the editor. All table pages use this height.", type:"number", min:3, max:12, step:.5, unit:"%"},
        {key:"mainMenuHeightPercent", scope:"user", title:"Menu bar height", description:"Menu bar height as a percentage of screen height at 100% UI scale. UI zoom scales this bar on Home and in every game plugin.", type:"number", min:3, max:20, step:.25, unit:"%"},
        {key:"soundEnabled", scope:"user", title:"Sound", description:"Play game-themed interface sounds when the active plugin supplies them.", type:"checkbox"},
        {key:"soundVolumePercent", scope:"packaged", title:"Volume level", description:"Attenuates all menu sound effects for every user.", type:"number", min:0, max:100, step:1, unit:"%"},
        {key:"residentHandleWidthPercent", scope:"packaged", title:"Home editor handle width", description:"Width of the Back to Editor handle as a percentage of the main-menu window.", type:"number", min:2.5, max:12, step:.25, unit:"%"},
        {key:"residentCoverBlurPixels", scope:"packaged", title:"Home handle cover blur", description:"How far the game cover behind the Home screen's Back to Editor handle is blurred, in pixels. The handle keeps its own arrow and save mark above the art.", type:"number", min:0, max:24, step:.5, unit:"px"},
        {key:"residentCoverDarkenPercent", scope:"packaged", title:"Home handle cover darkening", description:"How much the game cover behind the Home screen's Back to Editor handle is darkened. This sets both the brightness of the art and the dark film over it.", type:"number", min:0, max:100, step:2, unit:"%"},
        {key:"absentGameDesaturationPercent", scope:"packaged", title:"Absent game desaturation", description:"Amount of color removed from Absent game cover art on the Home screen.", type:"number", min:0, max:100, step:5, unit:"%"},
        {key:"globalMessageRarity", scope:"packaged", title:"Global message rarity", description:"Makes each global loading message this many times less likely than each game-specific message.", type:"number", min:1, max:100, step:1, unit:"× rarer"},
        {key:"loadingTransitionMinimumSeconds", scope:"packaged", title:"Loading screen transition", type:"number", min:0, max:10, step:.25, unit:"s", fallback:1.5},
        {key:"tweakColumnsPerPage", scope:"packaged", title:"Tweak columns per page", description:"Maximum columns on one Tweaks page. Each tweak stays in one column.", type:"number", min:1, max:12, step:1, fallback:6},
      ];
      const ordinaryDefinitions = definitions.filter(definition => definition.scope !== "packaged");
      const supportsCurrent = definition => Object.prototype.hasOwnProperty.call(settings, definition.key);
      const supportsDefault = definition => Object.prototype.hasOwnProperty.call(settings.defaultValues || {}, definition.key);
      const supportedOrdinaryDefinitions = ordinaryDefinitions.filter(supportsCurrent);
      const supportedDefaultDefinitions = definitions.filter(supportsDefault);
      const unsupportedDefinitions = definitions.filter(definition =>
        (definition.scope !== "packaged" && !supportsCurrent(definition)) || !supportsDefault(definition));
      const initialValue = (definition, defaults = false) => {
        const source = defaults ? settings.defaultValues : settings;
        return source?.[definition.key] ?? settings[definition.key] ??
          settings.defaultValues?.[definition.key] ?? definition.fallback ??
          (definition.type === "checkbox" ? false : definition.choices?.[0]?.value ?? definition.min ?? "");
      };
      // The host clamps every numeric setting on save. Clamp here too, so the
      // dialog never shows a value that would be silently changed underneath it.
      const clampSetting = (definition, raw) => {
        const numeric = Number(raw);
        if (!Number.isFinite(numeric)) return definition.min ?? 0;
        const low = definition.min ?? -Infinity, high = definition.max ?? Infinity;
        return Math.min(high, Math.max(low, numeric));
      };
      const makeControl = (definition, value, id) => {
        let control;
        if (definition.type === "select") control = element("select", {id, "aria-label":definition.title},
          ...definition.choices.map(choice => {
            const option = element("option", {value:choice.value}, choice.label);
            option.selected = choice.value === value; return option;
          }));
        else control = element("input", {
          id, type:definition.type, min:definition.min, max:definition.max, step:definition.step,
          checked:definition.type === "checkbox" && !!value,
          value:definition.type === "checkbox" ? undefined : value,
          "aria-label":definition.title,
        });
        if (definition.type === "number") control.addEventListener("change", () => {
          const clamped = clampSetting(definition, control.value);
          if (String(clamped) !== control.value) {
            control.value = clamped;
            message.textContent =
              `${definition.title} accepts ${definition.min} to ${definition.max}. Corrected to ${clamped}.`;
          }
          control.dispatchEvent(new Event("input", {bubbles:true}));
        });
        return definition.unit ? unitField(control, definition.unit) : control;
      };
      const controlNode = value => value.matches?.("input,select") ? value : value.querySelector("input,select");
      const readControl = (definition, wrapped) => {
        const control = controlNode(wrapped);
        if (definition.type === "checkbox") return control.checked;
        if (definition.type === "number") return clampSetting(definition, control.value);
        return control.value;
      };
      const writeControl = (definition, wrapped, value) => {
        const control = controlNode(wrapped);
        if (definition.type === "checkbox") control.checked = !!value;
        else control.value = value;
      };
      const currentControls = new Map(), defaultControls = new Map(), defaultCards = [];
      const lane = (scope, title) => element("section", {class:`lex-settings-lane lex-settings-lane-${scope}`},
        element("h3", {}, title));
      const userLane = lane("user", "GLOBAL SETTINGS");
      const developerLane = lane("developer", `${plugin || "PLUGIN"} DEVELOPER SETTINGS`.toLocaleUpperCase());
      const developerActive = !!settings.developerMode;
      developerLane.append(element("section", {class:"lex-global-setting lex-developer-identity"},
        element("strong", {}, developerActive ? "DEVELOPER MODE ACTIVE" : "DEVELOPER MODE UNAVAILABLE"),
        element("p", {}, developerActive
          ? `Authenticated GitHub account: ${settings.developerLogin}. Distributable authoring controls are enabled.`
          : "Sign in to GitHub as the authorized developer to expose authoring controls.")));
      const setDefaultVisibility = () => {
        defaultCards.forEach(control => {
          control.hidden = !developerActive;
          const supported = control.dataset.lexSettingSupported !== "false";
          control.setAttribute("aria-disabled", String(!supported));
          control.querySelectorAll?.("input,select").forEach(input => { input.disabled = !developerActive || !supported; });
        });
        developerLane.classList.toggle("active", developerActive);
      };
      const copyToDefault = (definition, defaultControl) => {
        if (!developerActive) {
          message.textContent = "Developer Mode requires the authorized GitHub account."; return;
        }
        if (!supportsDefault(definition)) {
          message.textContent = "Restart LEXEDITOR to enable this newly added setting."; return;
        }
        const source = controlNode(currentControls.get(definition.key));
        const target = controlNode(defaultControls.get(definition.key));
        if (definition.type === "checkbox") target.checked = source.checked;
        else target.value = source.value;
        defaultControl.hidden = false; defaultControl.classList.remove("copied"); void defaultControl.offsetWidth; defaultControl.classList.add("copied");
        message.textContent = `${definition.title} will become the packaged default when you save.`;
      };
      for (const definition of definitions) {
        if (definition.scope === "packaged") {
          const supported = supportsDefault(definition);
          const wrapped = makeControl(definition, initialValue(definition, true),
            `lex-default-${definition.key}`);
          defaultControls.set(definition.key, wrapped);
          const card = element("section", {
            class:"lex-global-setting lex-developer-setting lex-packaged-setting", hidden:true,
          }, element("div", {class:"lex-setting-copy"},
            element("label", {for:`lex-default-${definition.key}`}, definition.title),
            definition.description ? element("p", {}, definition.description) : null), wrapped);
          if(!supported)controlNode(wrapped).title="Restart Lexeditor to make this setting available.";
          card.dataset.lexSettingSupported = String(supported);
          developerLane.append(card);
          defaultCards.push(card);
          continue;
        }
        const currentSupported = supportsCurrent(definition);
        const defaultSupported = supportsDefault(definition);
        const wrapped = makeControl(definition, initialValue(definition), `lex-${definition.key}`);
        controlNode(wrapped).disabled = !currentSupported;
        if(!currentSupported)controlNode(wrapped).title="Restart Lexeditor to make this setting available.";
        currentControls.set(definition.key, wrapped);
        const copy = element("div", {class:"lex-setting-copy"},
          element("label", {for:`lex-${definition.key}`}, definition.title),
          definition.description ? element("p", {}, definition.description) : null);
        const defaultWrapped = makeControl(definition, initialValue(definition, true), `lex-default-${definition.key}`);
        defaultControls.set(definition.key, defaultWrapped);
        const defaultControl = element("label", {
          class:"lex-setting-default-control lex-developer-setting", hidden:true,
          for:`lex-default-${definition.key}`, title:"Default for every user",
        }, element("span", {}, "DEFAULT"), defaultWrapped);
        defaultControl.dataset.lexSettingSupported = String(defaultSupported);
        const controls = element("div", {class:"lex-setting-control-pair"}, wrapped, defaultControl);
        const card = element("section", {class:`lex-global-setting lex-${definition.scope}-setting`}, copy, controls);
        (definition.scope === "developer" ? developerLane : userLane).append(card);
        defaultCards.push(defaultControl);
        copy.addEventListener("dblclick", event => { event.preventDefault(); copyToDefault(definition, defaultControl); });
      }
      setDefaultVisibility();
      let savedSettings = clone(settings);
      settingsDirtyCount = () => {
        let dirty = supportedOrdinaryDefinitions.reduce((total, definition) => total + Number(
          readControl(definition, currentControls.get(definition.key)) !== savedSettings[definition.key]), 0);
        if (developerActive) {
          dirty += supportedDefaultDefinitions.reduce((total, definition) => total + Number(
            readControl(definition, defaultControls.get(definition.key)) !== savedSettings.defaultValues?.[definition.key]), 0);
        }
        return dirty;
      };
      restoreSettings = () => {
        supportedOrdinaryDefinitions.forEach(definition => writeControl(definition,
          currentControls.get(definition.key), savedSettings[definition.key]));
        supportedDefaultDefinitions.forEach(definition => writeControl(definition,
          defaultControls.get(definition.key), savedSettings.defaultValues?.[definition.key]));
        setDefaultVisibility();
        message.textContent = "Restored the last saved settings.";
      };
      const save = settingsSaveControl({
        dirtyCount: settingsDirtyCount,
        pendingChanges:()=>[...supportedOrdinaryDefinitions.flatMap(definition=>{
          const before=savedSettings[definition.key],after=readControl(definition,currentControls.get(definition.key));
          return Object.is(before,after)?[]:[{label:definition.title,before,after}];
        }),...(developerActive?supportedDefaultDefinitions.flatMap(definition=>{
          const before=savedSettings.defaultValues?.[definition.key],after=readControl(definition,defaultControls.get(definition.key));
          return Object.is(before,after)?[]:[{label:`Default: ${definition.title}`,before,after}];
        }):[])],
        save: async () => {
          message.textContent = "Saving settings…";
          try {
            const values = Object.fromEntries(supportedOrdinaryDefinitions.map(definition =>
              [definition.key, readControl(definition, currentControls.get(definition.key))]));
            settings = rememberSharedSettings(await callWindow("save_lexeditor_settings", values));
            if (developerActive) {
              const defaults = Object.fromEntries(supportedDefaultDefinitions.map(definition =>
                [definition.key, readControl(definition, defaultControls.get(definition.key))]));
              settings = rememberSharedSettings(await callWindow("save_developer_setting_defaults", defaults));
            }
            savedSettings = clone(settings);
            window.dispatchEvent(new CustomEvent("lexeditor-settings-changed", {detail: settings}));
            message.textContent = unsupportedDefinitions.length
              ? "Settings saved. Restart LEXEDITOR to enable newly added settings."
              : "Settings saved.";
            close();
          }
          catch (error) { message.textContent = String(error?.message || error); throw error; }
        },
        discard: restoreSettings,
      });
      const dialogChildren = [
        heading,
        element("div", {class:"lex-settings-columns"}, userLane, developerLane),
      ];
      const libraryPath = element("output", {class:"lex-readonly-field","aria-label":"Mod library location"}, "Loading library location…");
      let libraryStatus = null;
      const libraryRecover = element("button", {type:"button", hidden:true, onclick:async () => {
        try {
          const recovered = await callWindow("recover_mod_library_move");
          if (recovered?.url) { window.location.href = recovered.url; return; }
          await refreshLibraryLocation();
        } catch (error) { libraryPath.textContent = String(error?.message || error); }
      }}, "Recover move");
      const libraryCleanup = element("button", {type:"button", hidden:true, onclick:async () => {
        const approved = await confirmAction({title:"Remove the old library copy?",
          message:`Remove the verified recovery copy at ${libraryStatus?.move?.source}? The active library at ${libraryStatus?.root} will stay. Cleanup will stop if either copy has changed.`,
          confirmLabel:"Remove recovery copy"});
        if (!approved) return;
        try { await callWindow("remove_mod_library_recovery"); await refreshLibraryLocation(); }
        catch (error) { libraryPath.textContent = String(error?.message || error); }
      }}, "Remove recovery copy…");
      const libraryMove = element("button", {type:"button", onclick:async () => {
        let progressTimer = null;
        try {
          if (settingsDirtyCount()) throw Error("Save your settings before moving the mod library.");
          const plan = await callWindow("choose_mod_library_location");
          if (!plan || plan.cancelled) return;
          const approved = await confirmAction({title:"Move mod library?",
            message:`Move all managed mods from ${plan.source} to ${plan.destination}? This may take a while. An editor using that library will restart. The old folder will stay as a recovery copy. External projects will stay where they are.`,
            confirmLabel:"Move"});
          if (!approved) return;
          libraryMove.disabled = true;
          libraryMoveActive = true;
          libraryPath.textContent = "Copying and checking mod files…";
          progressTimer = setInterval(async () => {
            try {
              const progress = await callWindow("mod_library_move_progress");
              if (progress?.running) libraryPath.textContent = `${progress.completed} / ${progress.total} files — ${progress.file}`;
            } catch (_) {}
          }, 750);
          const result = await callWindow("move_mod_library", plan.source, plan.destination);
          clearInterval(progressTimer); progressTimer = null;
          if (result?.url) { window.__lexeditorNavigating = true; location.href = result.url; return; }
          libraryPath.textContent = `${result.root} — recovery copy: ${result.recovery}`;
          await refreshLibraryLocation();
        } catch (error) { libraryPath.textContent = String(error?.message || error); }
        finally { libraryMoveActive = false; if (progressTimer) clearInterval(progressTimer); libraryMove.disabled = false; }
      }}, "Move…");
      userLane.append(element("section", {class:"lex-global-setting lex-library-setting"},
        element("div", {class:"lex-setting-copy"},element("strong", {}, "Mod library")),
        libraryPath,actionRow(libraryMove,libraryRecover,libraryCleanup)));
      const refreshLibraryLocation = async () => {
        const value = await callWindow("mod_library_location");
        libraryStatus = value;
        libraryPath.textContent = value?.root || "Restart Lexeditor to use the mod library.";
        libraryMove.disabled = !value?.root;
        libraryRecover.hidden = !value?.move || ["committed", "retry"].includes(value.move.phase);
        libraryCleanup.hidden = value?.move?.phase !== "committed";
        if (value?.move) libraryPath.textContent += ` — ${value.move.phase === "committed" ? "Recovery copy" : "Move recovery"}: ${value.move.source}`;
        fitDialog();
      };
      refreshLibraryLocation().catch(error => { libraryPath.textContent = String(error?.message || error); libraryMove.disabled = true; });
      dialogChildren.push(message, element("div", {class: "lex-dialog-actions"}, save));
      dialog.replaceChildren(...dialogChildren);
      // Editing any control has to re-arm the save button. Without this the
      // dialog opens with save disabled and never enables, so a changed
      // setting cannot be saved at all.
      dialog.addEventListener("input", () => save.refresh?.());
      dialog.addEventListener("change", () => save.refresh?.());
      message.textContent = "";
      fitDialog();
      controlNode(currentControls.get("updateCheckFrequency")).focus();
    } catch (error) {
      message.textContent = String(error?.message || error);
    }
  };

  const githubDate = value => {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  };

  const githubError = error => String(error?.message || error || "Unknown GitHub error")
    .replace(/^Error:\s*/i, "");

  const mountGitHubWorkspace = (options, button, header, repository, navigationChanged = () => {}) => {
    const workflows = ["actionable", "untested", "waiting", "unfeasible"];
    const workflowNames={actionable:"Actionable",untested:"Needs Testing",waiting:"Waiting",unfeasible:"Unfeasible"};
    const state = {
      open: false, loaded: false, busy: false, filter: "actionable", query: "",
      issues: [], labels: [], selected: null, issue: null, page:0,
    };
    const hasLabel = (issue, name) => (issue?.labels || []).some(label => label.name === name);
    const status = element("div", {class: "lex-github-status", "aria-live": "polite"});
    const refresh = element("button", {class:"lex-github-refresh", "aria-label":"Refresh GitHub issues",onclick:()=>loadIssues()},"↻");
    const subtabs=subtabBar({label:"Issue workflow",tabs:workflows.map(id=>({id,label:workflowNames[id]})),active:state.filter,change:selectWorkflow});
    const workflowButtons=[...subtabs.querySelectorAll('[role=tab]')];
    workflowButtons.forEach((control,index)=>control.dataset.workflow=workflows[index]);
    // Each workflow tab is named by one of the repository's own labels, and
    // those labels carry a colour. The tab wears that colour, taken from the
    // loaded labels rather than copied here, so recolouring a label on GitHub
    // recolours its tab. The map below is only the fallback for a label the
    // loaded pages have not mentioned yet.
    const workflowFallbackColors={actionable:"#0e8a16",untested:"#fbca04",waiting:"#e87924",unfeasible:"#b60205"};
    const workflowColor=workflow=>{
      const named=row=>String(row?.name||"").toLowerCase()===workflow;
      const label=(state.labels||[]).find(named)
        || (state.issues||[]).flatMap(issue=>issue.labels||[]).find(named);
      const hex=String(label?.color||"").replace("#","").trim();
      return /^[0-9a-f]{6}$/i.test(hex)?`#${hex}`:workflowFallbackColors[workflow];
    };
    const paintWorkflow=control=>control.style.setProperty("--lex-workflow-color",workflowColor(control.dataset.workflow));
    workflowButtons.forEach(paintWorkflow);
    const footer=element("div",{class:"lex-github-footer"});
    const stateIcon=issue=>{
      const closed=String(issue.state).toLowerCase()==='closed';
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
      svg.setAttribute('viewBox','0 0 16 16');svg.setAttribute('class',`lex-github-state-icon ${closed?'closed':'open'}`);
      svg.setAttribute('role','img');svg.setAttribute('aria-label',closed?'Closed issue':'Open issue');
      svg.innerHTML='<circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/>'+(closed?'<path d="m4.5 8 2.3 2.3 4.7-4.7" fill="none" stroke="currentColor" stroke-width="1.5"/>':'<circle cx="8" cy="8" r="1.5" fill="currentColor"/>');
      return svg;
    };
    const issueList = element("div", {class: "lex-list lex-github-issue-list", role: "list"});
    const editor = element("section", {class: "lex-detail lex-github-editor"},
      element("div", {class: "lex-github-empty"}, "Select an issue."));
    const commentsPanel = element("section", {class: "lex-detail lex-github-comments-panel"},
      element("div", {class: "lex-github-empty"}, "Select an issue."));
    const layout = panelLayout([issueList, editor, commentsPanel], "lex-github-layout", {
      defaultSizes: [28, 38, 34], minSizes: [260, 320, 300],
    });
    const root = element("section", {
      class: "lex-github-workspace", hidden: true, "data-lex-history-control": true,
      "aria-label": `${repository.repository} GitHub issues`,
    },subtabs,status,layout,footer);
    header.after(root);
    new ResizeObserver(()=>{if(state.open)root.style.top=`${header.getBoundingClientRect().bottom}px`;}).observe(header);

    const setStatus = (message, error = false) => {
      status.textContent = message || "";
      status.hidden=!message;
      status.classList.toggle("error", error);
    };
    const setBusy = busy => {
      state.busy = busy;
      refresh.disabled = busy;
      workflowButtons.forEach(control => { control.disabled = busy; });
      root.classList.toggle("busy", busy);
    };
    const workflowRows = () => state.issues.filter(issue => hasLabel(issue, state.filter));
    const visibleRows = () => {
      const query = state.query.trim().toLowerCase();
      return workflowRows().filter(issue => !query ||
        `${issue.number} ${issue.title} ${(issue.labels || []).map(label => label.name).join(" ")}`
          .toLowerCase().includes(query));
    };
    const renderSubtabs = () => {
      for (const control of workflowButtons) {
        const workflow = control.dataset.workflow;
        const count = state.issues.filter(issue => hasLabel(issue, workflow)).length;
        paintWorkflow(control);
        control.querySelector(".lex-tab-label-text").textContent = workflowNames[workflow];
        control.classList.toggle("active", workflow === state.filter);
        control.setAttribute("aria-selected", String(workflow === state.filter));
      }
    };
    const updateSummary = issue => {
      const index = state.issues.findIndex(row => row.number === issue.number);
      if (index >= 0) state.issues[index] = {
        ...state.issues[index], title: issue.title, state: issue.state,
        labels: issue.labels, updatedAt: issue.updatedAt,
      };
      renderSubtabs();
      renderList();
    };

    function renderList() {
      const rows = visibleRows(),pageSize=15,pages=Math.max(1,Math.ceil(rows.length/pageSize));
      state.page=Math.min(state.page,pages-1);
      footer.replaceChildren(pager({inline:true,page:state.page,pages,pageSize,total:rows.length,change:value=>{state.page=value;renderList()},filters:[refresh],search:{key:"github-issues",label:"Search GitHub issues",value:state.query,change:value=>{state.query=value;state.page=0;renderList()}}}));
      issueList.replaceChildren(...rows.slice(state.page*pageSize,(state.page+1)*pageSize).map(issue => element("button", {
        class: `lex-list-row lex-github-issue-row${state.selected === issue.number ? " selected" : ""}`,
        role: "listitem", onclick: () => loadIssue(issue.number),
        "aria-label": `Issue ${issue.number}: ${issue.title}`,
      },
        element("span", {class: "lex-github-issue-number"}, `#${issue.number}`),
        element("span", {class: "lex-github-issue-title"}, issue.title),
        element("span", {
          class: `lex-github-priority-mark${hasLabel(issue, "high priority") ? " active" : ""}`,
          title: hasLabel(issue, "high priority") ? "High priority" : "",
          "aria-label": hasLabel(issue, "high priority") ? "High priority" : "",
        }, hasLabel(issue, "high priority") ? "!" : ""),
        stateIcon(issue))));
      if (!rows.length) issueList.append(element("div", {class: "lex-github-empty"},
        workflowRows().length ? "No issues match this search." : `No ${state.filter} issues.`));
    }

    const finishUpdatedIssue = async (updated, message) => {
      state.issue = updated;
      updateSummary(updated);
      if (!hasLabel(updated, state.filter)) {
        const next = visibleRows()[0];
        if (next) await loadIssue(next.number);
        else {
          state.selected = null;
          state.issue = null;
          renderList();
          renderIssue();
        }
      } else {
        renderIssue();
      }
      setStatus(message);
    };

    function renderIssue() {
      const issue = state.issue;
      if (!issue) {
        const empty = () => element("div", {class: "lex-github-empty"}, "Select an issue.");
        editor.replaceChildren(empty());
        commentsPanel.replaceChildren(empty());
        return;
      }
      const title = element("input", {
        class: "lex-github-title-input", value: issue.title,
        "aria-label": `Title for issue ${issue.number}`,
      });
      autoFitControlText(title);
      const body = element("textarea", {
        class: "lex-github-body-input", "aria-label": `Body for issue ${issue.number}`,
      }, issue.body || "");
      const save = element("button", {class: "lex-github-save"}, "SAVE");
      const editStatus = element("span", {class: "lex-github-edit-status", "aria-live": "polite"});
      save.onclick = async () => {
        save.disabled = true;
        editStatus.textContent = "Saving…";
        try {
          const updated = await callWindow(
            "github_edit_issue", options.plugin.id, issue.number, title.value, body.value,
          );
          if (!updated) throw new Error("The GitHub bridge is unavailable");
          await finishUpdatedIssue(updated, `Saved #${issue.number}.`);
        } catch (error) {
          editStatus.textContent = `Save failed: ${githubError(error)}`;
          save.disabled = false;
        }
      };

      const selectedLabels = new Set((issue.labels || []).map(label => label.name));
      const labelEditor=element("div",{class:"lex-github-workflow-actions","aria-label":"Issue workflow"},...workflows.map(workflow=>{
        const control=element("button",{class:"lex-github-workflow-state","data-workflow":workflow,"aria-pressed":String(selectedLabels.has(workflow))},workflowNames[workflow]);
        control.onclick=async()=>{
          const desired=[...selectedLabels].filter(name=>!workflows.includes(name));desired.push(workflow);
          labelEditor.querySelectorAll('button').forEach(button=>button.disabled=true);
          try {const updated=await callWindow("github_set_issue_labels",options.plugin.id,issue.number,desired);
            if(!updated)throw new Error("The GitHub bridge is unavailable");
            await finishUpdatedIssue(updated,`Updated workflow on #${issue.number}.`);
          }catch(error){setStatus(`Workflow update failed: ${githubError(error)}`,true);renderIssue();}
        };return control;
      }));
      const priorityActive = selectedLabels.has("high priority");
      const priority = element("button", {
        class: `lex-github-priority-toggle${priorityActive ? " active" : ""}`,
        title: priorityActive ? "Remove high priority" : "Mark high priority",
        "aria-label": priorityActive ? "Remove high priority" : "Mark high priority",
        "aria-pressed": String(priorityActive),
      }, "!");
      priority.onclick = async () => {
        priority.disabled = true;
        const desired = [...selectedLabels];
        if (priorityActive) desired.splice(desired.indexOf("high priority"), 1);
        else desired.push("high priority");
        setStatus(`${priorityActive ? "Removing" : "Adding"} high priority on #${issue.number}…`);
        try {
          const updated = await callWindow(
            "github_set_issue_labels", options.plugin.id, issue.number, desired,
          );
          if (!updated) throw new Error("The GitHub bridge is unavailable");
          await finishUpdatedIssue(updated, `Updated priority on #${issue.number}.`);
        } catch (error) {
          setStatus(`Priority update failed: ${githubError(error)}`, true);
          renderIssue();
        }
      };
      editor.replaceChildren(detailPanel({titleControl:title,identity:recordId(issue.number),icon:priority,actions:stateIcon(issue),body:[body,
        element("div",{class:"lex-github-edit-actions"},save,editStatus),labelEditor]}));
      const commentsFeed = element("div", {class: "lex-github-comments-feed"});
      if (!(issue.comments || []).length) {
        commentsFeed.append(element("div", {class: "lex-github-empty"}, "No comments."));
      } else {
        for (const comment of issue.comments) commentsFeed.append(element("article", {class: "lex-github-comment"},
          element("div", {class: "lex-github-comment-meta"},
            element("strong", {}, comment.author || "Unknown"), githubDate(comment.createdAt)),
          element("div", {class: "lex-github-comment-body"}, comment.body || "")));
      }
      const commentBody = element("textarea", {
        class: "lex-github-comment-input", placeholder: "Leave a comment…",
        "aria-label": `New comment on issue ${issue.number}`,
      });
      const post = element("button", {class: "lex-github-comment-post"}, "COMMENT");
      const postComment = async () => {
        if (!commentBody.value.trim()) return;
        post.disabled = true;
        commentBody.disabled = true;
        setStatus(`Posting comment on #${issue.number}…`);
        try {
          const updated = await callWindow(
            "github_comment_issue", options.plugin.id, issue.number, commentBody.value,
          );
          if (!updated) throw new Error("The GitHub bridge is unavailable");
          await finishUpdatedIssue(updated, `Commented on #${issue.number}.`);
        } catch (error) {
          setStatus(`Comment failed: ${githubError(error)}`, true);
          post.disabled = false;
          commentBody.disabled = false;
        }
      };
      post.onclick = postComment;
      commentBody.addEventListener("keydown", event => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          postComment();
        }
      });
      commentsPanel.replaceChildren(
        element("div", {class: "lex-github-comments-head"},
          element("h3", {}, `COMMENTS ${(issue.comments || []).length}`)),
        commentsFeed,
        element("div", {class: "lex-github-comment-composer"}, commentBody, post));
      requestAnimationFrame(() => { commentsFeed.scrollTop = commentsFeed.scrollHeight; });
    }

    async function ensureLabels() {
      if (state.labels.length) return;
      const payload = await callWindow("github_labels", options.plugin.id);
      if (!payload) throw new Error("The GitHub bridge is unavailable");
      state.labels = payload.labels || [];
    }

    async function loadIssue(number) {
      state.selected = Number(number);
      renderList();
      editor.replaceChildren(element("div", {class: "lex-github-empty"}, `Loading #${number}…`));
      commentsPanel.replaceChildren(element("div", {class: "lex-github-empty"}, "Loading comments…"));
      try {
        const [issue] = await Promise.all([
          callWindow("github_issue", options.plugin.id, Number(number)), ensureLabels(),
        ]);
        if (!issue) throw new Error("The GitHub bridge is unavailable");
        state.issue = issue;
        renderIssue();
      } catch (error) {
        setStatus(`Could not load #${number}: ${githubError(error)}`, true);
        const failed = () => element("div", {class: "lex-github-empty error"}, githubError(error));
        editor.replaceChildren(failed());
        commentsPanel.replaceChildren(failed());
      }
    }

    async function selectWorkflow(workflow) {
      if (!workflows.includes(workflow)) return;
      state.filter = workflow;
      state.page=0;
      renderSubtabs();
      renderList();
      const current = visibleRows().find(issue => issue.number === state.selected);
      const next = current || visibleRows()[0];
      if (next) await loadIssue(next.number);
      else {
        state.selected = null;
        state.issue = null;
        renderList();
        renderIssue();
      }
    }

    async function loadIssues() {
      if (state.busy) return;
      setBusy(true);
      setStatus("Loading issues…");
      try {
        const payload = await callWindow("github_issues", options.plugin.id, "all");
        if (!payload) throw new Error("The GitHub bridge is unavailable");
        state.issues = payload.issues || [];
        state.loaded = true;
        renderSubtabs();
        const next = visibleRows().find(issue => issue.number === state.selected) || visibleRows()[0];
        state.selected = next?.number || null;
        state.issue = null;
        renderList();
        setStatus("");
        if (state.selected) await loadIssue(state.selected);
        else renderIssue();
      } catch (error) {
        state.issues = [];
        renderSubtabs();
        renderList();
        setStatus(`GitHub failed: ${githubError(error)}`, true);
      } finally {
        setBusy(false);
      }
    }

    const show = () => {
      state.open = true;
      root.hidden = false;
      root.style.top=`${header.getBoundingClientRect().bottom}px`;
      document.body.dataset.lexGithubOpen = "true";
      header.classList.add("lex-github-open");
      header.querySelectorAll("nav button").forEach(control => control.classList.toggle("active", control === button));
      button.classList.add("active");
      button.setAttribute("aria-pressed", "true");
      navigationChanged();
      if (!state.loaded) loadIssues();
      else root.querySelector('input[type="search"]')?.focus();
      // The repository's labels carry the workflow colours. Fetching them is
      // one call, and when it lands the tabs repaint; without it they keep the
      // standard colours of these labels.
      ensureLabels().then(() => workflowButtons.forEach(paintWorkflow)).catch(() => {});
    };
    const hide = () => {
      state.open = false;
      root.hidden = true;
      document.body.dataset.lexGithubOpen = "false";
      header.classList.remove("lex-github-open");
      button.classList.remove("active");
      button.setAttribute("aria-pressed", "false");
      header.querySelectorAll("nav button[data-tab]").forEach(control =>
        control.classList.toggle("active", control.dataset.tab === options.activeTab()));
      navigationChanged();
    };
    button.onclick = () => state.open ? hide() : show();
    renderSubtabs();
    return {root, state, show, hide, loadIssues, loadIssue};
  };

  // The same GitHub issues workspace, opened without a game's editor behind it -
  // from Home, for a game that is not installed ("right click on a game's
  // cover on the main menu to just go straight to its github page/tab thing
  // in the app"). It gets a slim bar of its own with the game's name and a
  // close button, in place of the editor's header.
  const openGitHubIssues = async (pluginId, pluginName = "") => {
    const repository = await callWindow("github_repository", pluginId);
    if (!repository?.repository) {
      showToast(`No GitHub repository is set for ${pluginName || pluginId}.`, true);
      return null;
    }
    document.querySelectorAll(".lex-github-standalone").forEach(node => node.remove());
    const button = element("button", {type: "button", hidden: true});
    let workspace = null;
    const close = () => {
      workspace?.hide();
      workspace?.root.remove();
      header.remove();
    };
    const header = element("header", {class: "lex-shell-header lex-github-standalone"},
      element("strong", {class: "lex-github-standalone-title"}, `${pluginName || pluginId} issues`),
      closeButton({title: "Close the issues", onclick: close}));
    document.body.append(header);
    workspace = mountGitHubWorkspace({plugin: {id: pluginId, name: pluginName}, activeTab: () => ""},
      button, header, repository);
    workspace.root.classList.add("lex-github-standalone");
    workspace.show();
    return {...workspace, close};
  };

  const installWindowFrame = options => {
    const controls = options.controls || createWindowActions();
    const {minimize, maximize, close} = controls;
    const dragRegions = (options.regions || []).filter(Boolean);
    const showMaximized = state => {
      const maximized = !!state?.maximized;
      document.body.dataset.windowMaximized = String(maximized);
      maximize.title = maximized ? "Restore" : "Maximize";
      maximize.setAttribute("aria-label", maximized ? "Restore window" : "Maximize window");
      for (const region of dragRegions) {
        region.classList.toggle("pywebview-drag-region", !maximized);
      }
    };
    minimize.onclick = () => callWindow("window_minimize");
    maximize.onclick = async () => showMaximized(await callWindow("window_toggle_maximize"));
    close.onclick = options.close || (() => callWindow("window_close"));

    const interactive = target => target instanceof Element &&
      !!target.closest("button,input,select,textarea,a,[role=button],[contenteditable=true]");
    const toggleFromTitleBar = async event => {
      if (event.button !== 0 || interactive(event.target)) return;
      event.preventDefault();
      showMaximized(await callWindow("window_toggle_maximize"));
    };
    for (const region of dragRegions) {
      region.classList.add("lex-window-drag-region");
      region.addEventListener("dblclick", toggleFromTitleBar);
    }

    document.querySelectorAll(".lex-window-resize-handle").forEach(handle => handle.remove());
    const resizeHandles = ["top", "right", "bottom", "left", "top-left", "top-right", "bottom-right", "bottom-left"]
      .map(edge => element("div", {
        class: `lex-window-resize-handle ${edge}`,
        "data-window-edge": edge,
        "aria-hidden": "true",
        onmousedown: event => {
          if (event.button !== 0) return;
          event.preventDefault();
          event.stopPropagation();
          callWindow("window_begin_resize", edge);
        },
      }));
    document.body.append(...resizeHandles);
    window.__lexeditorApplyWindowState = showMaximized;
    const syncState = () => callWindow("window_state").then(showMaximized);
    if (window.pywebview?.api) syncState();
    else window.addEventListener("pywebviewready", syncState, {once: true});
    return {...controls, resizeHandles, showMaximized};
  };

  // A table cell opens its editor straight from a dblclick, far from the
  // shell that knows whether the project is read-only. Without this the
  // Vanilla source handed out a fully enabled editor and packaged reference
  // data could be typed over, while every other control on the page was
  // correctly disabled. The shell records its accessor here on mount.
 let activeShellReadonly = null;
  const shellIsReadonly = () => {
    try { return !!activeShellReadonly?.(); } catch { return false; }
  };
  // A game opened with no mod is read-only whatever the plugin believes: the
  // page is showing the game's own data and there is no mod to write into, so
  // the host marks the frame's own URL. A locked save button is better than a
  // save that cannot work, and the header says why.
  const sessionHasNoMod = () => loadingParameters.get("lexNoMod") === "1";

  // A developer renames a tab, a subtab or a field label in place: double-click
  // it, type, press Enter. The name is stored with that tab's view defaults, so
  // it ships to everyone the way a held tab's layout does. Escape keeps the old
  // name, and an empty name restores the shipped one, because a thing nobody
  // can name is a thing nobody can find.
  const shellPluginId = () => document.body.dataset.lexPlugin || "";
  const activePageTab = () =>
    document.querySelector(".lex-shell-header nav button.active")?.dataset.tab || "";
  const savedLabel = (key, fallback) => {
    try {
      const stored = localStorage.getItem(key);
      if (stored === null) return fallback;
      if (stored === "" && !String(key).includes(".help.")) return fallback;
      return stored;
    } catch (_error) { return fallback; }
  };
  // The name a subtab shows under: the developer's rename when there is
  // one, else the shipped label. Panel tabs share this namespace (the bar
  // builds them the same way). Build-time sorts use the shown name, so a
  // renamed tab keeps its alphabetical seat on every render, not just in
  // the re-sort that follows the rename.
  const shownSubtabName = tab => savedLabel(
    `${shellPluginId()}-${activePageTab()}.sub.${tab.id}.label`,
    String(tab.label instanceof Node ? tab.label.textContent : tab.label ?? tab.id));
  // The help text a developer rewords. A bubble has no name of its own and its
  // text is far too long for a key, so the key is a short digest of the shipped
  // text. A string rewritten in a plugin's code simply stops matching, and the
  // reader then sees the new shipped text rather than an orphaned override.
  const textDigest = value => {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
  };
  const helpKey = shipped =>
    `${shellPluginId()}-${activePageTab()}.help.${textDigest(shipped)}.text`;
  // A name a developer changed is an override, not record data, so the
  // plugin's own history never sees it. The shell keeps the last few renames
  // itself and its undo takes them back, newest first.
  const labelUndo = [];
  const labelRedo = [];
  let labelHistoryChanged = () => {};
  // One undo order across kinds: every entry on either stack carries a tick
  // from this shared clock, and the newest change wins, whether it renamed
  // a tab or edited a value. (Lexer: a pile of layout undos used to swallow
  // the button, so value edits never came back.)
  let historyTick = 0;
  const nextHistoryTick = () => ++historyTick;
  const pushLabelUndo = entry => {
    if (entry && !Number.isFinite(entry.at)) entry.at = nextHistoryTick();
    labelUndo.push(entry);
  };
  const stackTopAt = entry => entry && Number.isFinite(entry.at) ? entry.at : -1;
  const pluginStackTop = (history, redo) => {
    if (!history) return undefined;
    const stack = redo ? history.redoStack : history.undoStack;
    return Array.isArray(stack) ? stack[stack.length - 1] : undefined;
  };
  const undoNewest = async pluginHistory => {
    const mine = labelUndo[labelUndo.length - 1];
    const theirs = pluginStackTop(pluginHistory, false);
    if (theirs !== undefined && (mine === undefined || stackTopAt(theirs) > stackTopAt(mine)))
      return pluginHistory.undo();
    return undoLabel();
  };
  const redoNewest = async pluginHistory => {
    const mine = labelRedo[labelRedo.length - 1];
    const theirs = pluginStackTop(pluginHistory, true);
    if (theirs !== undefined && (mine === undefined || stackTopAt(theirs) > stackTopAt(mine)))
      return pluginHistory.redo();
    return redoLabel();
  };
  // A table's column header shows the same property as the field, so a rename
  // reaches the headers already drawn too (Lexer: "i renamed a property but its
  // name in the table column header remained the same?").
  const relabelHeaders = (key, text) => {
    for (const label of document.querySelectorAll(".header-label[data-lex-label-key], .lex-pinned-header-label[data-lex-label-key]")) {
      if (label.dataset.lexLabelKey !== key) continue;
      const name = label.lastChild;
      if (name?.nodeType === Node.TEXT_NODE) name.data = text;
    }
    // A section split across paginated columns draws its heading once per
    // column; every copy follows the one that was renamed.
    for (const title of document.querySelectorAll(".lex-detail-section-title-text[data-lex-label-key]"))
      if (title.dataset.lexLabelKey === key) title.textContent = text;
  };
  // True when the host kept the value, so the toast can say so honestly.
  const storeLabel = async (key, tabId, value, shipped) => {
    const cleared = value !== shipped;
    const next = cleared ? value : "";
    try {
      if (cleared) localStorage.setItem(key, next);
      else localStorage.removeItem(key);
    } catch (_error) {}
    try {
      const result = await callWindow("save_default_view", shellPluginId(), tabId, {[key]: next});
      return !!result?.saved;
    } catch (_error) {}
    return false;
  };
  const undoLabel = async () => {
    const entry = labelUndo.pop();
    if (!entry) return false;
    if (entry.apply) {
      await entry.apply(entry.before);
      labelRedo.push(entry);
      labelHistoryChanged();
      return true;
    }
    if (entry.node?.isConnected) entry.node.textContent = entry.before;
    relabelHeaders(entry.key, entry.before);
    resortSubtabOf(entry.node);
    await storeLabel(entry.key, entry.tabId, entry.before, entry.shipped);
    labelRedo.push(entry);
    labelHistoryChanged();
    return true;
  };
  const redoLabel = async () => {
    const entry = labelRedo.pop();
    if (!entry) return false;
    if (entry.apply) {
      await entry.apply(entry.after);
      pushLabelUndo(entry);
      labelHistoryChanged();
      return true;
    }
    if (entry.node?.isConnected) entry.node.textContent = entry.after;
    relabelHeaders(entry.key, entry.after);
    resortSubtabOf(entry.node);
    await storeLabel(entry.key, entry.tabId, entry.after, entry.shipped);
    pushLabelUndo(entry);
    labelHistoryChanged();
    return true;
  };
  // A property's name as the developer last named it. The shipped name is the
  // key, so an override never orphans itself: the same property, drawn on any
  // screen, reads the same. A label that is a node rather than a name (a chip
  // with an icon in it) is left alone.
  // Keep layout separate from record data. IDs describe the original shared
  // field/section structure, never the selected record's name or number.
  const propertyLayouts = new WeakMap();
  // The live-root lookup beside it: a WeakMap cannot list its keys, so
  // the set carries the roots and drops them as they disconnect.
  const propertyLayoutRoots = new Set();
  const propertyRoot = field => field.closest(".lex-detail-panel") || field.closest(".lex-detail-section");
  // A body box mid-render has no panel ancestor yet: its fields and
  // sections answer to the box itself until it joins its panel. Nested
  // panels still keep their own fields.
  const isDetachedBody = root => !root.isConnected && !root.classList.contains("lex-detail-panel") &&
    !root.classList.contains("lex-detail-section");
  const layoutFields = root => {
    const boxed = isDetachedBody(root);
    return [...root.querySelectorAll(".lex-detail-field[data-lex-layout-field]")].filter(field =>
      (boxed ? !field.closest(".lex-detail-panel") : propertyRoot(field) === root) &&
      !field.parentElement.closest(".lex-detail-field"));
  };
  const hiddenKey = (plugin, tab) => `${plugin}-${tab}.hidden-properties`;
  // The section order is kept per page by section name too: a layout is keyed
  // by its record's exact fields, so an order set on one armor piece did not
  // reach a piece with one field more.
  const orderKey = (plugin, tab) => `${plugin}-${tab}.section-order`;
  const sectionNameOf = id => String(id).replace(/:\d+$/, "");
  const readSectionOrder = (plugin, tab) => {
    try {
      const stored = JSON.parse(localStorage.getItem(orderKey(plugin, tab)) || "null");
      return Array.isArray(stored) ? stored.map(String) : null;
    } catch (_error) { return null; }
  };
  const propertyOf = id => String(id).split("/").pop().replace(/:\d+$/, "");
  const readHiddenProperties = (plugin, tab) => {
    const key = hiddenKey(plugin, tab);
    try {
      const stored = JSON.parse(localStorage.getItem(key) || "null");
      if (Array.isArray(stored)) return new Set(stored.map(String));
    } catch (_error) {}
    // First time: gather what every earlier layout of this page hid.
    const gathered = new Set();
    const prefix = `${plugin}-${tab}.property-layout.`;
    try {
      for (let index = 0; index < localStorage.length; index++) {
        const name = localStorage.key(index);
        if (!name?.startsWith(prefix)) continue;
        const layout = JSON.parse(localStorage.getItem(name) || "null");
        for (const id of Array.isArray(layout?.hidden) ? layout.hidden : []) gathered.add(propertyOf(id));
      }
      localStorage.setItem(key, JSON.stringify([...gathered]));
    } catch (_error) {}
    return gathered;
  };
  // The hidden list rides along with the layout's own save: one host call
  // per change.
  const writeHiddenProperties = (plugin, tab, hidden) => {
    const key = hiddenKey(plugin, tab), value = JSON.stringify([...hidden].sort());
    try { localStorage.setItem(key, value); } catch (_error) {}
    return {[key]: value};
  };
  // Scan only: no restore. Detail tabs probe a mid-render box with this
  // to learn its stored custom sections; the probe shares the exact key.
  // Any parent of properties is a group: a section's content, a dealt
  // column, or the panel body itself for properties dragged out of every
  // section. Shared with the drop handler, which groups a parent that
  // holds no property yet.
  const addPropertyGroup = (groups, node) => {
    if (groups.has(node)) return groups.get(node);
    const section = node.closest(".lex-detail-section");
    const name = section?.dataset.lexLayoutSection || "properties";
    const index = [...groups.values()].filter(group => group.name === name).length;
    const group = {id: `${name}:${index}`, name, node, anchors: [], custom: section?.dataset.lexCustomSection === "true"};
    groups.set(node, group);
    return group;
  };
  const buildPropertyState = (root, fields) => {
    const groups = new Map(), fieldMap = new Map(), identities = new Map();
    const boxed = isDetachedBody(root);
    for (const section of root.querySelectorAll(".lex-detail-section-content")) {
      if (section.closest(".lex-detail-field")) continue;
      const home = section.closest(".lex-detail-panel") || section.closest(".lex-detail-section");
      if (home === root || (boxed && !section.closest(".lex-detail-panel"))) addPropertyGroup(groups, section);
    }
    // Every live lane column is a group, empty or not, in lane order: an
    // emptied lane would otherwise vanish from the numbering, and a field
    // dropped into it would file under the next index - which a fresh
    // build, seeing it occupied, gives to another node instead. Occupied
    // lanes keep the exact indices the fields loop always gave them (field
    // order is lane order), so only empty lanes gain entries, with empty
    // lists. Scoped like the fields themselves: a nested pager's columns
    // belong to its own panel, never to this one.
    if (root.querySelectorAll) for (const pager of root.querySelectorAll(".lex-tweaks-paged")) {
      const home = pager.closest(".lex-detail-panel") || pager.closest(".lex-detail-section");
      if (home !== root && !(boxed && !pager.closest(".lex-detail-panel"))) continue;
      for (const column of pager.querySelectorAll(".lex-tweak-column")) {
        if (column.closest(".lex-tweaks-paged") !== pager) continue;
        addPropertyGroup(groups, column);
      }
    }
    for (const field of fields) {
      const group = addPropertyGroup(groups, field.parentElement);
      const base = `${group.id}/${field.dataset.lexLayoutField}`;
      const index = identities.get(base) || 0;
      identities.set(base, index + 1);
      fieldMap.set(field, `${base}:${index}`);
    }
    // The panel body itself is a group too, made last after the
    // sections: properties live loose in it when the developer drags
    // them out of every section, and it must exist before a stored
    // loose arrangement applies.
    const looseHome = root.querySelector?.(".lex-detail-panel-body .lex-tweak-card-grid, .lex-detail-panel-body");
    if (looseHome) addPropertyGroup(groups, looseHome);
    for (const group of groups.values()) {
      group.anchors = [...group.node.children].filter(node => fieldMap.has(node)).map(field => {
        let next = field.nextSibling;
        while (next && fieldMap.has(next)) next = next.nextSibling;
        return next;
      });
    }
    // The schema is the sorted field-name multiset, never positions:
    // column dealing shifts parents on every refit, and the key must
    // survive it.
    const schema = JSON.stringify([...fieldMap.values()].map(propertyOf).sort());
    return {root, fields: fieldMap, groups,
      tab: activePageTab(), plugin: shellPluginId(),
      key: `${shellPluginId()}-${activePageTab()}.property-layout.${textDigest(schema)}`};
  };
  // Stored layouts outlive their schemas: a layout whose exact key is gone
  // is adopted by field set (one transparent re-key), so shipped and older
  // arrangements survive key changes instead of silently dropping.
  // The tab a moved field left still finds its stored arrangement by
  // counting the ghost, and the tab it joined finds its own by
  // discounting the arrival. Both adoptions write their migrated layout
  // for the next build; the override alone ships, and every reader
  // derives the same layouts from it.
  const adoptFieldTabLayout = state => {
    const bar = [...(state.root.querySelectorAll?.(".lex-tabbed-panel-tabs[data-lex-fieldtabs]") || [])]
      .find(candidate => (candidate.closest(".lex-detail-panel") || candidate.closest(".lex-detail-section")) === state.root);
    if (!bar) return null;
    const shape = bar.dataset.lexFieldtabs;
    const tabId = bar.querySelector(":scope > .lex-subtab-button.active")?.dataset.subtab;
    const entries = Object.entries(readFieldTabOverrides(shape));
    if (!tabId || !entries.length) return null;
    const present = [...state.fields.values()].map(propertyOf);
    const names = new Set(present);
    const ghosts = entries.filter(([field, rule]) => rule?.from === tabId && !names.has(field)).map(([field]) => field);
    const arrivals = entries.filter(([field, rule]) => rule?.to === tabId && names.has(field)).map(([field]) => field);
    if (!ghosts.length && !arrivals.length) return null;
    const keyNames = [...present];
    for (const ghost of ghosts) keyNames.push(ghost);
    for (const arrival of arrivals) keyNames.splice(keyNames.indexOf(arrival), 1);
    const key = `${state.plugin}-${state.tab}.property-layout.${textDigest(JSON.stringify(keyNames.sort()))}`;
    let stored = null;
    try { stored = JSON.parse(localStorage.getItem(key) || "null"); } catch (_error) {}
    if (!stored || typeof stored !== "object") return null;
    const meta = new Set(["hidden", "sections", "removed", "order"]);
    const migrated = {};
    for (const [listKey, list] of Object.entries(stored)) {
      if (!Array.isArray(list) || meta.has(listKey)) { migrated[listKey] = list; continue; }
      migrated[listKey] = list.filter(id => !ghosts.includes(propertyOf(id)));
    }
    const used = new Set();
    for (const arrival of arrivals) {
      const current = [...state.fields.values()].find(id => propertyOf(id) === arrival && !used.has(id));
      if (!current) continue;
      used.add(current);
      const want = sectionNameOf(String(current).split("/")[0]);
      const listKey = Object.keys(migrated).find(candidate =>
        Array.isArray(migrated[candidate]) && !meta.has(candidate) && sectionNameOf(candidate) === want);
      if (!listKey || migrated[listKey].some(id => propertyOf(id) === arrival)) continue;
      migrated[listKey].push(current);
    }
    try { localStorage.setItem(state.key, JSON.stringify(migrated)); } catch (_error) {}
    return migrated;
  };
  // Records a drop onto another tab's button: the override names both
  // tabs, the undo restores the map and returns to the source tab, and the
  // caller re-renders through the clicked button. The bar is found by its
  // shape each time, never by a node a rebuild may have discarded.
  const moveDetailFieldToTab = targetTab => {
    const {field, sourceTab} = propertyDrag || {};
    const fieldKey = field?.dataset?.lexLayoutField;
    const bar = propertyDrag?.panel?.isConnected
      ? propertyDrag.panel.querySelector(":scope > .lex-tabbed-panel-tabs[data-lex-fieldtabs]")
      : null;
    const shape = bar?.dataset.lexFieldtabs;
    if (!shape || !fieldKey || !sourceTab || sourceTab === targetTab) return;
    const beforeMap = readFieldTabOverrides(shape);
    const afterMap = {...beforeMap, [fieldKey]: {from: sourceTab, to: targetTab}};
    const barOf = () => document.querySelector(
      `.lex-tabbed-panel-tabs[data-lex-fieldtabs="${shape}"]`);
    const clickTab = id => barOf()?.querySelector(
      `.lex-subtab-button[data-subtab="${id}"]`)?.click();
    const activeTab = () => barOf()?.querySelector(
      ".lex-subtab-button.active")?.dataset.subtab;
    // The bar is stale the moment the overrides change: a target the move
    // revives still wears its gray, and a tab the reader hid has no button
    // at all. Unhide first (a tab with members is alive again), then land
    // through the gray once so the caller re-renders onto the move.
    const landOn = showId => {
      let at = barOf();
      if (at && !at.querySelector(`.lex-subtab-button[data-subtab="${showId}"]`)) {
        const hiddenNow = readFieldTabHidden(shape);
        if (hiddenNow.includes(showId))
          writeFieldTabHidden(shape, hiddenNow.filter(kept => kept !== showId));
        refreshSubtabBar(at);
        at = barOf();
      }
      const button = at?.querySelector(`.lex-subtab-button[data-subtab="${showId}"]`);
      if (button && (button.disabled || button.getAttribute("aria-disabled") === "true"))
        button.dataset.lexReviveClick = "true";
      button?.click();
    };
    writeFieldTabOverrides(shape, afterMap);
    pushLabelUndo({before: beforeMap, after: afterMap, apply: layout => {
      writeFieldTabOverrides(shape, layout);
      const showId = layout === afterMap ? targetTab : sourceTab;
      // Clicking the active tab rebuilds nothing, so bounce through the
      // other one: the caller re-renders twice and lands on the move.
      if (activeTab() === showId) clickTab(showId === targetTab ? sourceTab : targetTab);
      landOn(showId);
    }});
    labelRedo.length = 0;
    labelHistoryChanged();
    landOn(targetTab);
  };
  const readStoredLayout = state => {
    const parse = text => { try { return JSON.parse(text || "null"); } catch (_error) { return null; } };
    const direct = parse(localStorage.getItem(state.key));
    if (direct) return direct;
    if (!state.plugin || !state.tab) return null;
    const fingerprint = [...state.fields.values()].map(propertyOf).sort().join("\n");
    const prefix = `${state.plugin}-${state.tab}.property-layout.`;
    for (let index = 0; index < localStorage.length; index++) {
      const candidate = localStorage.key(index);
      if (!candidate || !candidate.startsWith(prefix) || candidate === state.key) continue;
      const layout = parse(localStorage.getItem(candidate));
      if (!layout || typeof layout !== "object") continue;
      const names = [];
      for (const [key, list] of Object.entries(layout)) {
        if (key === "hidden" || key === "sections" || key === "removed" || key === "order") continue;
        if (!Array.isArray(list)) continue;
        for (const id of list) if (typeof id === "string" && id.includes("/")) names.push(propertyOf(id));
      }
      if (names.length === state.fields.size && names.sort().join("\n") === fingerprint) {
        try { localStorage.setItem(state.key, JSON.stringify(layout)); } catch (_error) {}
        return layout;
      }
    }
    return adoptFieldTabLayout(state);
  };
  const preparePropertyLayout = root => {
    const fields = layoutFields(root);
    const previous = propertyLayouts.get(root);
    // Only reuse the state while its group nodes are still in the
    // document: a refit rebuilds the columns, and capturing against
    // detached columns would see empty groups and skip the store.
    if (previous && fields.length === previous.fields.size && fields.every(field => previous.fields.has(field)) &&
        [...previous.groups.keys()].every(node => node.isConnected)) return previous;
    const state = buildPropertyState(root, fields);
    propertyLayouts.set(root, state);
    propertyLayoutRoots.add(root);
    try { applyPropertyLayout(state, readStoredLayout(state)); } catch (_error) {}
    return state;
  };
  // A layout is each group's property order, plus the properties the
  // developer hid. Group ids always hold a colon, so "hidden" never clashes.
  const layoutSectionOf = group => group.node.closest(".lex-detail-section");
  // Sections in a flowing pane are dealt into columns, so their reading
  // order is the pager's list, not where they sit in the document.
  const byReadingOrder = (a, b) => {
    if (a === b) return 0;
    const pager = a.closest(".lex-tweaks-paged");
    const list = pager && pager === b.closest(".lex-tweaks-paged") ? pager.lexCards?.() : null;
    if (list?.includes(a) && list.includes(b)) return list.indexOf(a) - list.indexOf(b);
    return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  };
  const sectionOrder = state => [...state.groups.values()].filter(group => layoutSectionOf(group))
    .sort((a, b) => byReadingOrder(layoutSectionOf(a), layoutSectionOf(b))).map(group => group.id);
  // The listed sections keep the places they hold now and fill them in the
  // saved order, so a page that flows sections into columns keeps its flow.
  const orderSections = (state, order) => {
    if (!Array.isArray(order)) return;
    const byId = new Map([...state.groups.values()].map(group => [group.id, layoutSectionOf(group)]));
    const listed = [...new Set(order.map(id => byId.get(id)).filter(section => section?.parentNode))];
    // A custom section belongs to the layout even when the wanted order does
    // not name it: the page-level order is shared across record shapes, so it
    // can name another shape's customs. One left out never joins the pager's
    // cards, and the next deal drops it from the page. Each rejoins after the
    // section it was added below.
    for (const group of state.groups.values()) {
      if (!group.custom) continue;
      const section = layoutSectionOf(group);
      if (!section?.parentNode || listed.includes(section)) continue;
      const spec = (state.custom || []).find(item => item.id === group.name) || {};
      const anchor = byId.get(spec.after);
      const at = anchor ? listed.indexOf(anchor) : -1;
      listed.splice(at < 0 ? listed.length : at + 1, 0, section);
    }
    const movable = listed.filter(section => !listed.some(other => other !== section && other.contains(section)));
    // Sections dealt into detail panes keep their pane: order within
    // each container, never across them, and never into the leftover
    // pager (its refits were disconnected for the same reason).
    if (movable.some(section => section.closest(".lex-detail-tabpane"))) {
      const groups = new Map();
      for (const section of movable) {
        const parent = section.parentElement;
        if (!groups.has(parent)) groups.set(parent, []);
        groups.get(parent).push(section);
      }
      for (const siblings of groups.values()) {
        if (siblings.length < 2) continue;
        const slots = [...siblings].sort(byReadingOrder).map(section => {
          const mark = document.createComment("");
          section.before(mark);
          return mark;
        });
        siblings.forEach((section, index) => slots[index].replaceWith(section));
      }
      return;
    }
    const pager = movable.map(section => section.closest(".lex-tweaks-paged")).find(node => node?.lexOrderCards);
    if (pager) {
      // Every section in the pager joins the deal, customs in tab content
      // included: a new header belongs in one column like every shipped
      // one, not full-width below the columns.
      pager.lexOrderCards(movable.filter(section => section.closest(".lex-tweaks-paged") === pager));
      return;
    }
    if (movable.length < 2) return;
    const slots = [...movable].sort(byReadingOrder).map(section => {
      const mark = document.createComment("");
      section.before(mark);
      return mark;
    });
    movable.forEach((section, index) => slots[index].replaceWith(section));
  };
  const asLaneMap = lanes => new Map(Object.entries(lanes && typeof lanes === "object" ? lanes : {})
    .filter(([, lane]) => Number.isInteger(lane) && lane >= 0)
    .map(([name, lane]) => [String(name), lane]));
  const liveSectionLanes = state => {
    const live = new Map();
    for (const group of state.groups.values()) {
      const section = layoutSectionOf(group);
      const pager = section?.closest(".lex-tweaks-paged");
      if (!pager || pager.lexUnpaged !== true) continue;
      const columns = [...pager.querySelectorAll(".lex-tweak-column")]
        .filter(column => column.closest(".lex-tweaks-paged") === pager);
      if (columns.length < 2) continue;
      const lane = columns.indexOf(section.closest(".lex-tweak-column"));
      if (lane >= 0) live.set(group.name, lane);
    }
    return live;
  };
  // A property loose in the panel body (or a dealt column) records the
  // section after it, so a fresh render puts it back beside that
  // section instead of appending it after every section. Columns
  // rebuild on every refit, so the section - a stable node - is the
  // anchor, not the column. Trailing properties record nothing: the
  // normal passes append them.
  const looseAnchors = state => {
    const anchors = {};
    const contentOf = new Map([...state.groups.values()].map(group => [group.node, group]));
    for (const group of state.groups.values()) {
      if (layoutSectionOf(group)) continue;
      const kids = [...group.node.children];
      kids.forEach((field, at) => {
        if (!state.fields.has(field)) return;
        const following = kids.slice(at + 1).find(node => node.classList?.contains("lex-detail-section"));
        if (!following) return;
        const content = following.querySelector(":scope > .lex-detail-section-content");
        const anchor = content && contentOf.get(content);
        if (anchor) anchors[state.fields.get(field)] = anchor.id;
      });
    }
    return anchors;
  };
  const capturePropertyLayout = state => ({
    ...Object.fromEntries([...state.groups.values()].map(group =>
      [group.id, [...group.node.children].filter(field => state.fields.has(field)).map(field => state.fields.get(field))])),
    hidden: [...state.fields].filter(([field]) => field.classList.contains("lex-property-hidden")).map(([, id]) => id),
    sections: (state.custom || []).map(spec => ({...spec})),
    removed: [...(state.removed || [])],
    order: sectionOrder(state),
    lanes: {...readStoredLayout(state)?.lanes, ...Object.fromEntries(liveSectionLanes(state))},
    loose: looseAnchors(state)});
  // A page's own section the developer removed. It is hidden only while it
  // holds no properties, so a property moved back into it (or one the page
  // gains later) is never lost behind a removed heading.
  // Returns whether any section flipped: callers refit the pager then, so
  // an unhidden section is dealt back into view instead of stranded.
  const hideRemovedSections = state => {
    const removed = new Set(state.removed || []);
    let flipped = false;
    for (const group of state.groups.values()) {
      if (group.custom) continue;
      const section = group.node.closest(".lex-detail-section");
      if (!section) continue;
      // Empty means nothing rendered, the same rule as the hold-right
      // gesture: a removed section holding a graph shows again instead
      // of staying hidden behind a stale removed entry.
      const empty = group.node.childElementCount === 0;
      const hide = removed.has(group.id) && empty;
      if (section.hidden !== hide) { section.hidden = hide; flipped = true; }
    }
    return flipped;
  };
  // A section the developer added: a heading and an empty body that
  // properties are dragged into. It belongs to the layout, after the section
  // it was added below, and its title is the layout's, not a shipped label.
  const customSectionNode = (spec) => {
    const text = element("span", {class: "lex-detail-section-title-text"}, spec.title);
    text.addEventListener("dblclick", event => {
      if (!sharedSettingsSnapshot?.developerMode) return;
      event.preventDefault();
      event.stopPropagation();
      renameValue(text, {value: spec.title, label: "this section", commit: typed => {
        // The building state may be a discarded probe: rename against
        // the live layout and the spec object it owns, found by id.
        const live = preparePropertyLayout(section.closest(".lex-detail-panel") || section);
        const target = (live.custom || []).find(item => item.id === spec.id) || spec;
        const before = capturePropertyLayout(live);
        target.title = typed;
        const after = capturePropertyLayout(live);
        const apply = layout => storePropertyLayout(live, layout);
        pushLabelUndo({before, after, apply}); labelRedo.length = 0; labelHistoryChanged();
        void apply(after);
      }});
    });
    const section = detailSection({title: text, body: []});
    section.dataset.lexLayoutSection = spec.id;
    section.dataset.lexCustomSection = "true";
    return section;
  };
  // A body holding one tabbed panel carries that panel's bar along the
  // panel's top edge (the :only-child rules), so a custom section belongs
  // inside the tab's own content: in its scroll box below the dealt grid
  // when paged (never in the grid, whose deals detach a non-card), else at
  // the content end. Beside the panel it would drop the bar below the
  // heading and collapse the tab content to nothing.
  const tabbedCustomHome = root => {
    const body = root.classList?.contains("lex-detail-panel-body") ? root
      : root.querySelector(".lex-detail-panel-body .lex-tweak-card-grid, .lex-detail-panel-body");
    const tabbed = body?.querySelector(":scope > .lex-tabbed-panel");
    if (!tabbed || [...body.children].some(kid => kid !== tabbed &&
        !kid.classList.contains("lex-multi-edit-notice") && kid.dataset?.lexCustomSection !== "true")) return null;
    const content = tabbed.querySelector(":scope > .lex-tabbed-panel-content");
    if (!content) return null;
    return {body, home: content.querySelector(":scope > .lex-tweaks-paged > .lex-tweaks-scroll") || content};
  };
  const placeCustomSections = (state, specs) => {
    state.custom = (Array.isArray(specs) ? specs : []).filter(spec => spec && typeof spec.id === "string")
      .map(spec => ({id: spec.id, title: String(spec.title || "New section"), after: String(spec.after || "")}));
    const wanted = new Set(state.custom.map(spec => `${spec.id}:0`));
    for (const [node, group] of [...state.groups]) {
      if (!group.custom || wanted.has(group.id)) continue;
      // A removed section gives its properties back to where they came from.
      const home = [...state.groups.values()].find(other => !other.custom);
      for (const field of [...node.children]) if (state.fields.has(field)) home?.node.append(field);
      node.closest(".lex-detail-section")?.remove();
      state.groups.delete(node);
    }
    const tabbed = tabbedCustomHome(state.root);
    for (const spec of state.custom) {
      const id = `${spec.id}:0`;
      const existing = [...state.groups.values()].find(group => group.id === id);
      if (existing) {
        const section = existing.node.closest(".lex-detail-section");
        const text = section?.querySelector(".lex-detail-section-title-text");
        if (text && text.textContent !== spec.title) text.textContent = spec.title;
        // A section an earlier build left beside the tabbed panel rejoins
        // the tab content, restoring the bar and the tab's height at once.
        if (tabbed && section?.parentElement === tabbed.body) tabbed.home.append(section);
        continue;
      }
      const section = customSectionNode(spec);
      const anchor = [...state.groups.values()].find(group => group.id === spec.after)?.node.closest(".lex-detail-section");
      if (anchor) anchor.after(section);
      else if (tabbed) tabbed.home.append(section);
      else (state.root.querySelector(".lex-detail-panel-body .lex-tweak-card-grid, .lex-detail-panel-body") || state.root).append(section);
      const node = section.querySelector(".lex-detail-section-content") || section;
      state.groups.set(node, {id, name: spec.id, node, anchors: [], custom: true});
    }
  };
  // Field drags sequence the pager cards to the live DOM order: deal()
  // fills lanes in card order, so unsynced cards would put every refit
  // back to shipped order and silently drop the developer arrangement.
  const syncPagerCards = pager => {
    if (!pager?.lexOrderCards) return;
    let live = [...pager.querySelectorAll(".lex-tweak-column > *, .lex-tweak-off-page > *")];
    if (!live.length) {
      const grid = pager.querySelector(".lex-tweak-card-grid");
      live = grid ? [...grid.children].filter(node => node instanceof Element &&
        !node.classList.contains("lex-tweak-column") && !node.classList.contains("lex-tweak-off-page")) : [];
    }
    if (live.length) pager.lexOrderCards(live, true);
  };
  const applyPropertyLayout = (state, layout) => {
    // No saved layout for this exact page still gets the page's hidden properties.
    if (!layout || typeof layout !== "object") layout = {};
    const byId = new Map([...state.fields].map(([field, id]) => [id, field]));
    placeCustomSections(state, layout.sections);
    state.removed = Array.isArray(layout.removed) ? layout.removed.filter(id => typeof id === "string") : [];
    const hidden = new Set(Array.isArray(layout.hidden) ? layout.hidden : []);
    const byName = readHiddenProperties(state.plugin, state.tab);
    for (const [field, id] of state.fields)
      field.classList.toggle("lex-property-hidden", hidden.has(id) || byName.has(propertyOf(id)));
    const used = new Set();
    // A refit re-deals columns, so a stored id's group prefix shifts with
    // the window: the same property resolves by name when it misses exactly.
    const byProp = new Map();
    for (const [field, id] of state.fields) {
      const prop = propertyOf(id);
      if (!byProp.has(prop)) byProp.set(prop, []);
      byProp.get(prop).push(field);
    }
    const resolveField = id => {
      const exact = byId.get(id);
      if (exact && !used.has(exact)) return exact;
      const queue = byProp.get(propertyOf(id));
      while (queue?.length) {
        const field = queue.shift();
        if (!used.has(field)) return field;
      }
      return null;
    };
    const layoutKeys = new Set(["hidden", "sections", "removed", "order", "lanes", "loose"]);
    // Bare fields dealt into columns name their group after the column, so
    // the group count IS the column count: a layout stored with one column
    // cannot apply by group id to a two-column dealing. That pulled every
    // property into the first column and left the rest empty, with no
    // property to drag onto. When the counts differ, the stored columns
    // become one reading order, dealt across the live columns the way the
    // pager dealt them.
    {
      const liveBySection = new Map();
      for (const group of state.groups.values()) {
        if (layoutSectionOf(group)) continue;
        const name = sectionNameOf(group.id);
        if (!liveBySection.has(name)) liveBySection.set(name, []);
        liveBySection.get(name).push(group);
      }
      const byIdText = (a, b) => a.localeCompare(b, undefined, {numeric: true});
      let migrated = null;
      for (const live of liveBySection.values()) {
        live.sort((a, b) => byIdText(a.id, b.id));
        const name = sectionNameOf(live[0].id);
        const storedKeys = Object.keys(layout).filter(key =>
          !layoutKeys.has(key) && Array.isArray(layout[key]) && sectionNameOf(key) === name)
          .sort(byIdText);
        if (!storedKeys.length || storedKeys.length === live.length) continue;
        const reading = [];
        for (const key of storedKeys) for (const id of layout[key]) if (typeof id === "string") reading.push(id);
        if (!reading.length) continue;
        const sizes = live.map(group => [...group.node.children].filter(field => state.fields.has(field)).length);
        const total = sizes.reduce((sum, size) => sum + size, 0);
        migrated = migrated || {...layout};
        for (const key of storedKeys) delete migrated[key];
        let at = 0, run = 0;
        live.forEach((group, index) => {
          run += sizes[index];
          const end = index === live.length - 1 ? reading.length
            : total ? Math.round(reading.length * run / total)
            : Math.round(reading.length * (index + 1) / live.length);
          migrated[group.id] = reading.slice(at, Math.max(at, Math.min(reading.length, end)));
          at += migrated[group.id].length;
        });
      }
      if (migrated) layout = migrated;
    }
    // A field pinned to a lane belongs loose in that lane's column, never
    // in a section: the pin is the source of truth the dealing honors,
    // while a stored column group is a node a refit already rebuilt. This
    // runs before the group passes and marks its fields used, so the
    // passes below never file them under a swapped column index or drag
    // them back into their template section.
    for (const [key, lane] of Object.entries(layout.lanes || {})) {
      if (!key.startsWith("field:")) continue;
      const prop = key.slice("field:".length);
      const found = [...state.fields].find(([candidate]) =>
        candidate.dataset.lexLayoutField === prop);
      const pinned = found?.[0];
      const pager = pinned?.closest(".lex-tweaks-paged");
      if (!pinned || pager?.lexUnpaged !== true) continue;
      const lanes = [...pager.querySelectorAll(".lex-tweak-column")]
        .filter(column => column.closest(".lex-tweaks-paged") === pager);
      const home = lanes[Math.max(0, Math.min(lanes.length - 1, Number(lane) || 0))];
      if (!home) continue;
      used.add(pinned);
      if (pinned.parentElement !== home) home.append(pinned);
    }
    // Loose properties rejoin their anchor section first, in stored
    // order: the section is a stable node, while the column they were
    // dropped in rebuilds on every refit. The normal passes skip them
    // once placed.
    const loose = layout.loose && typeof layout.loose === "object" ? layout.loose : null;
    if (loose) {
      const sectionById = new Map([...state.groups.values()].map(group => [group.id, layoutSectionOf(group)]));
      for (const ids of Object.values(layout)) {
        if (!Array.isArray(ids)) continue;
        for (const id of ids) {
          if (typeof id !== "string") continue;
          const anchor = sectionById.get(loose[id] ?? loose[propertyOf(id)]);
          if (!anchor?.parentElement) continue;
          const field = resolveField(id);
          if (!field || used.has(field) || field.contains(anchor)) continue;
          used.add(field);
          // The anchor's parent is a group the fresh page never built (the
          // drop registered it, the template has no such node): without it
          // the restored field is no group's child, and the next capture
          // stores it nowhere - the undo of a drop back inside then lost it.
          addPropertyGroup(state.groups, anchor.parentElement);
          anchor.parentElement.insertBefore(field, anchor);
        }
      }
    }
    for (const group of state.groups.values()) {
      const ids = layout[group.id];
      if (!Array.isArray(ids)) continue;
      for (const [index, id] of ids.entries()) {
        const field = resolveField(id);
        if (!field || used.has(field) || field.contains(group.node)) continue;
        used.add(field);
        const anchor = group.anchors[index] || group.anchors.at(-1);
        group.node.insertBefore(field, anchor?.parentNode === group.node ? anchor : null);
      }
    }
    // Stored columns with no live group (the refit dealt a different count),
    // and stored fields whose column moved, land by name in stored reading
    // order: each slots before the next stored neighbor already home.
    const groupById = new Map([...state.groups.values()].map(group => [group.id, group]));
    for (const [key, ids] of Object.entries(layout)) {
      if (layoutKeys.has(key) || !Array.isArray(ids)) continue;
      const target = groupById.get(key) ||
        [...state.groups.values()].filter(group => sectionNameOf(group.id) === sectionNameOf(key)).at(-1);
      if (!target) continue;
      // Every stored field lands in stored order, moving when the live
      // dealing already holds it somewhere else: a partial exact pass
      // scatters worse than nothing, so this pass enforces the order.
      let before = null;
      for (let index = ids.length - 1; index >= 0; index--) {
        const id = ids[index];
        if (typeof id !== "string") continue;
        const field = resolveField(id);
        if (!field || used.has(field) || field.contains(target.node)) {
          const home = byId.get(id);
          if (home && home.parentNode === target.node) before = home;
          continue;
        }
        used.add(field);
        target.node.insertBefore(field, before);
        before = field;
      }
    }
    const pageOrder = readSectionOrder(state.plugin, state.tab);
    // The page's order is the latest one set on any record of the page (every
    // save, undo included, writes it), so it wins over an older layout's.
    const pagers = new Set();
    for (const group of state.groups.values()) {
      const pager = group.node.closest?.(".lex-tweaks-paged");
      if (pager) pagers.add(pager);
    }
    // Pins land before the ordering refit, or the refit deals stale lanes.
    if (layout.lanes && typeof layout.lanes === "object")
      for (const pager of pagers) pager.lexSetLanes?.(layout.lanes);
    // Cards sync before the ordering refit too: a field the passes just
    // placed loose in a column joins the dealing first, or the refit the
    // ordering triggers deals it away with its column.
    pagers.forEach(syncPagerCards);
    orderSections(state, pageOrder ? pageOrder.map(name => `${name}:0`) : layout.order);
    // A hidden flip changes the dealt set, so the pager refits: without
    // this an undo that unhides a section left it stranded outside the deal.
    if (hideRemovedSections(state)) pagers.forEach(pager => pager.lexFitPage?.());
    // A card the layout moved out of its pager's columns (a property now
    // living in a custom section) leaves that pager's dealing, or the next
    // refit pulls it back out. Cards merely unlisted by the stored layout
    // stay exactly where they are.
    for (const pager of state.root.querySelectorAll(".lex-tweaks-paged")) {
      const gone = (pager.lexCards?.() || []).filter(card => card.isConnected &&
        card.parentElement?.closest(".lex-tweaks-paged") === pager &&
        !card.parentElement.classList.contains("lex-tweak-column") &&
        !card.parentElement.classList.contains("lex-tweak-off-page"));
      if (gone.length) pager.lexRemoveCards?.(...gone);
    }
  };
  const storePropertyLayout = async (state, layout) => {
    const value = JSON.stringify(layout);
    localStorage.setItem(state.key, value);
    // This page's properties take their hidden state from this layout; ones
    // only other record shapes have keep theirs.
    const byName = readHiddenProperties(state.plugin, state.tab);
    const hiddenNow = new Set((layout.hidden || []).map(propertyOf));
    for (const id of state.fields.values()) byName.delete(propertyOf(id));
    for (const name of hiddenNow) byName.add(name);
    const hiddenEntry = writeHiddenProperties(state.plugin, state.tab, byName);
    if (Array.isArray(layout.order)) {
      const names = JSON.stringify([...new Set(layout.order.map(sectionNameOf))]);
      try { localStorage.setItem(orderKey(state.plugin, state.tab), names); } catch (_error) {}
      hiddenEntry[orderKey(state.plugin, state.tab)] = names;
    }
    for (const root of document.querySelectorAll(".lex-detail-panel, .lex-detail-section")) {
      const current = propertyLayouts.get(root);
      if (current?.key === state.key) applyPropertyLayout(current, layout);
    }
    try { await callWindow("save_default_view", state.plugin, state.tab, {[state.key]: value, ...hiddenEntry}); }
    catch (_error) { showToast("Layout saved on this device; the shared default could not be saved."); }
  };
  // Developer Mode: holding the right button on a property hides it for
  // everyone, or shows it again. It is a layout change like a drag, so it is
  // saved and undone the same way. A plain right-click still restores the
  // vanilla value; the hold swallows the right-click it ends with.
  let hideTimer = 0, hideHeld = false;
  document.addEventListener("pointerdown", event => {
    clearTimeout(hideTimer);
    hideHeld = false;
    if (event.button !== 2 || !sharedSettingsSnapshot?.developerMode) return;
    const field = event.target.closest?.(".lex-detail-field[data-lex-layout-field]");
    const root = field && propertyRoot(field);
    if (!root) return;
    field.classList.add("lex-property-holding");
    hideTimer = setTimeout(() => {
      field.classList.remove("lex-property-holding");
      const state = preparePropertyLayout(root);
      if (!state.fields.has(field)) return;
      hideHeld = true;
      const before = capturePropertyLayout(state);
      field.classList.toggle("lex-property-hidden");
      const after = capturePropertyLayout(state);
      const apply = layout => { storePropertyLayout(state, layout); reapplyStoredLayout(state); };
      pushLabelUndo({before, after, apply});
      labelRedo.length = 0;
      labelHistoryChanged();
      void apply(after);
      const name = field.querySelector(".lex-detail-field-label-text")?.textContent || "This property";
      showToast(field.classList.contains("lex-property-hidden")
        ? `${name} is hidden for everyone without Show hidden properties.` : `${name} is shown again.`);
    }, 700);
  }, true);
  document.addEventListener("pointerdown", event => {
    if (event.button !== 2 || !sharedSettingsSnapshot?.developerMode) return;
    const heading = event.target.closest?.(".lex-detail-section-title");
    const section = heading?.closest(".lex-detail-section");
    const root = section && (section.closest(".lex-detail-panel") || section);
    if (!root || event.target.closest(".lex-detail-field")) return;
    clearTimeout(hideTimer);
    heading.classList.add("lex-property-holding");
    hideTimer = setTimeout(() => {
      heading.classList.remove("lex-property-holding");
      const fieldInside = root.querySelector(".lex-detail-field[data-lex-layout-field]");
      // A section with no property rows (a table, a graph, a note) still
      // answers the header gesture: its panel, or itself, is the layout
      // root, so holding removes it and dragging moves it.
      const state = preparePropertyLayout(fieldInside ? propertyRoot(fieldInside) : root);
      hideHeld = true;
      const before = capturePropertyLayout(state);
      const group = [...state.groups.values()].find(entry => entry.node.closest(".lex-detail-section") === section);
      const holdsFields = group && [...group.node.children].some(node => state.fields.has(node));
      // Empty means nothing rendered at all: a section holding a graph, a
      // table or a note is not empty just because it holds no properties.
      // Removing one of those destroyed its content beyond undo.
      const holdsContent = group && group.node.childElementCount > 0;
      // An empty section, the page's own or an added one, is removed; one
      // that still holds anything gets a new section added below it.
      let specs = [...(state.custom || [])];
      const removing = group && !holdsContent;
      let added = null;
      if (removing && group.custom) {
        specs = specs.filter(spec => `${spec.id}:0` !== group.id);
        root._DetailTabs?.forgetShell?.(layoutSectionOf(group));
      }
      else if (removing) state.removed = [...new Set([...(state.removed || []), group.id])];
      else { added = {id: `custom-${Date.now().toString(36)}`, title: "New section", after: group?.id || ""}; specs.push(added); }
      placeCustomSections(state, specs);
      if (added) adoptCustomIntoActivePane(root, added.id, section);
      hideRemovedSections(state);
      const after = capturePropertyLayout(state);
      const apply = layout => { storePropertyLayout(state, layout); reapplyStoredLayout(state); };
      pushLabelUndo({before, after, apply}); labelRedo.length = 0; labelHistoryChanged();
      void apply(after);
      const holdsNonField = group && [...group.node.children].some(child => !state.fields.has(child));
      showToast(removing ? "Removed the empty section. Undo brings it back."
        : holdsNonField ? "That section holds something that is not a property, so it stays. Added a section below it instead."
        : "Added a section. Double-click its heading to name it, and drag properties into it. "
          + "To remove a section, drag its properties out, then hold right on its heading.");
    }, 700);
  }, true);
  for (const type of ["pointerup", "pointercancel"]) document.addEventListener(type, () => {
    clearTimeout(hideTimer);
    document.querySelectorAll(".lex-property-holding").forEach(node => node.classList.remove("lex-property-holding"));
  }, true);
  document.addEventListener("contextmenu", event => {
    if (!hideHeld) return;
    hideHeld = false;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
  let propertyDrag = null, propertyDrop = null;
  const clearPropertyDrop = () => {
    propertyDrop?.marker.classList.remove("lex-property-drop-before", "lex-property-drop-after", "lex-drop-target", "lex-property-drop-target");
    propertyDrop = null;
  };
  // During a section or property drag, holding the pointer near the top or
  // bottom edge of the details panel scrolls it, the way other programs do.
  // The loop runs on animation frames, not drag events, so it keeps scrolling
  // while the pointer sits still at the edge. It only moves scrollTop: the
  // panel's own scrollbar stays as usable as it was before the drag.
  let dragScroll = null;
  let dragScrollRaf = 0;
  const dragScrollContainer = target => {
    for (let node = target instanceof Element ? target : null; node; node = node.parentElement) {
      if (node.scrollHeight > node.clientHeight + 1) {
        const vertical = getComputedStyle(node).overflowY;
        if (vertical === "auto" || vertical === "scroll") return node;
      }
    }
    return null;
  };
  const dragScrollTick = () => {
    dragScrollRaf = 0;
    if (!dragScroll || (!sectionDrag && !propertyDrag)) { dragScroll = null; return; }
    const {container, y} = dragScroll;
    if (container.isConnected) {
      const box = container.getBoundingClientRect();
      const zone = 56;
      const fromTop = y - box.top, fromBottom = box.bottom - y;
      let delta = 0;
      if (fromTop >= 0 && fromTop < zone) delta = -Math.ceil((zone - fromTop) / zone * 14);
      else if (fromBottom >= 0 && fromBottom < zone) delta = Math.ceil((zone - fromBottom) / zone * 14);
      if (delta) container.scrollTop += delta;
    }
    if (sectionDrag || propertyDrag) dragScrollRaf = requestAnimationFrame(dragScrollTick);
    else dragScroll = null;
  };
  const dragScrollNote = event => {
    if (!sectionDrag && !propertyDrag) return;
    const container = dragScrollContainer(event.target);
    if (!container) { dragScroll = null; return; }
    dragScroll = {container, y: event.clientY};
    if (!dragScrollRaf) dragScrollRaf = requestAnimationFrame(dragScrollTick);
  };
  // In Developer Mode a property is dragged by its whole row - anywhere but
  // its value box, which still selects text and edits as usual.
  document.addEventListener("pointerover", event => {
    const heading = event.target.closest?.(".lex-detail-section-title");
    if (heading && !event.target.closest(".lex-detail-field,.lex-label-rename,input"))
      heading.draggable = !!sharedSettingsSnapshot?.developerMode;
    const field = event.target.closest?.(".lex-detail-field[data-lex-layout-field]");
    if (!field) return;
    field.draggable = !!sharedSettingsSnapshot?.developerMode &&
      !event.target.closest(".lex-detail-field-control,.lex-label-rename,.lex-help-edit");
  });
  // A heading drags its whole section before or after another section's.
  let sectionDrag = null;
  document.addEventListener("dragstart", event => {
    const heading = event.target.closest?.(".lex-detail-section-title");
    const section = heading && !event.target.closest(".lex-detail-field") && heading.closest(".lex-detail-section");
    if (!section || !sharedSettingsSnapshot?.developerMode) return;
    const panel = section.closest(".lex-detail-panel") || section;
    const fieldInside = panel.querySelector(".lex-detail-field[data-lex-layout-field]");
    const state = preparePropertyLayout(fieldInside ? propertyRoot(fieldInside) : panel);
    if (![...state.groups.values()].some(group => layoutSectionOf(group) === section)) { event.preventDefault(); return; }
    sectionDrag = {state, section, before: capturePropertyLayout(state)};
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", heading.textContent || "");
    section.classList.add("lex-property-dragging");
  });
  document.addEventListener("dragover", event => {
    if (!sectionDrag) return;
    dragScrollNote(event);
    clearPropertyDrop();
    const {state, section} = sectionDrag;
    const target = [...state.groups.values()].map(layoutSectionOf)
      .find(node => node && node !== section && node.contains(event.target) && !node.contains(section) && !section.contains(node)
        && ![...node.querySelectorAll(".lex-detail-section")].some(inner => inner.contains(event.target) && inner !== section));
    if (!target) {
      const column = event.target.closest?.(".lex-tweak-column");
      const pager = column?.closest(".lex-tweaks-paged");
      if (!column || !pager || pager.lexUnpaged !== true
        || pager !== section.closest(".lex-tweaks-paged")
        || column.querySelector(".lex-detail-section")) return;
      propertyDrop = {target: column, marker: column, after: true, lane: true};
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      column.classList.add("lex-property-drop-target");
      return;
    }
    const after = event.clientY >= target.getBoundingClientRect().top + target.offsetHeight / 2;
    propertyDrop = {target, marker: target, after};
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    target.classList.add(after ? "lex-property-drop-after" : "lex-property-drop-before");
  });
  const pinDropLanes = (state, moving, target) => {
    const pager = target.closest(".lex-tweaks-paged");
    if (!pager || pager.lexUnpaged !== true || typeof pager.lexSetLanes !== "function") return;
    const columns = [...pager.querySelectorAll(".lex-tweak-column")]
      .filter(column => column.closest(".lex-tweaks-paged") === pager);
    if (columns.length < 2) return;
    const laneOf = node => columns.indexOf(node.closest(".lex-tweak-column"));
    const targetLane = laneOf(target);
    if (targetLane < 0) return;
    const map = new Map();
    for (const group of state.groups.values()) {
      const node = layoutSectionOf(group);
      if (!node || node.closest(".lex-tweaks-paged") !== pager) continue;
      const lane = node === moving ? targetLane : laneOf(node);
      if (lane >= 0) map.set(group.name, lane);
    }
    if (map.size) { pager.lexSetLanes(map); return true; }
    return false;
  };
  // Undoing a layout change restores the stored arrangement to the live
  // panel, not just to storage: the state is rebuilt (a refit may have
  // replaced the columns since) and the stored layout applies onto it.
  // When the panel rebuilt since, the live root with the same key takes it.
  const reapplyStoredLayout = state => {
    const live = state.root.isConnected ? state.root
      : [...propertyLayoutRoots].find(root => {
          if (!root.isConnected) { propertyLayoutRoots.delete(root); return false; }
          return propertyLayouts.get(root)?.key === state.key;
        });
    if (!live) return;
    propertyLayouts.delete(live);
    preparePropertyLayout(live);
  };
  document.addEventListener("drop", event => {
    if (!sectionDrag || !propertyDrop?.target || !sharedSettingsSnapshot?.developerMode) return;
    event.preventDefault();
    const {state, section, before} = sectionDrag;
    const idOf = node => [...state.groups.values()].find(group => layoutSectionOf(group) === node)?.id;
    const moving = idOf(section), target = idOf(propertyDrop.target);
    const order = target === undefined ? sectionOrder(state)
      : sectionOrder(state).filter(id => id !== moving);
    if (target !== undefined) order.splice(order.indexOf(target) + (propertyDrop.after ? 1 : 0), 0, moving);
    const dropTarget = propertyDrop.target;
    const pinned = pinDropLanes(state, section, dropTarget);
    clearPropertyDrop();
    orderSections(state, order);
    // A lane-only drop re-sequences nothing, so the ordering above deals
    // nothing: refit for the new pins explicitly.
    if (pinned) for (const pager of state.root.querySelectorAll(".lex-tweaks-paged")) pager.lexFitPage?.();
    const after = capturePropertyLayout(state);
    if (JSON.stringify(before) === JSON.stringify(after)) return;
    const apply = layout => { storePropertyLayout(state, layout); reapplyStoredLayout(state); };
    pushLabelUndo({before, after, apply}); labelRedo.length = 0; labelHistoryChanged();
    void apply(after);
  });
  document.addEventListener("dragend", () => {
    sectionDrag?.section.classList.remove("lex-property-dragging");
    sectionDrag = null;
  });
  document.addEventListener("dragstart", event => {
    const field = event.target.closest?.(".lex-detail-field[data-lex-layout-field]");
    if (!field || event.target.closest(".lex-detail-field-control")) return;
    const root = propertyRoot(field);
    if (!sharedSettingsSnapshot?.developerMode || !root || field.querySelector(".lex-detail-field-label input")) { event.preventDefault(); return; }
    const state = preparePropertyLayout(root);
    if (!state.fields.has(field)) { event.preventDefault(); return; }
    // A cross-tab move records where the field came from: the override
    // names both tabs, and the undo returns to the source one.
    const panel = field.closest(".lex-tabbed-panel");
    const sourceTab = panel?.querySelector(".lex-tabbed-panel-tabs .lex-subtab-button.active")?.dataset.subtab || null;
    propertyDrag = {state, field, before: capturePropertyLayout(state), panel, sourceTab};
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", field.dataset.lexLayoutField);
    field.classList.add("lex-property-dragging");
  });
  document.addEventListener("dragover", event => {
    if (!propertyDrag) return;
    dragScrollNote(event);
    clearPropertyDrop();
    if (!sharedSettingsSnapshot?.developerMode) return;
    const {state, field} = propertyDrag;
    // Onto another accepting tab of the same panel: the field moves there
    // when dropped. Bespoke tabs, and tabs of another panel, refuse it.
    const button = event.target.closest?.(".lex-tabbed-panel-tabs .lex-subtab-button[data-lex-accept-fields]");
    if (button && propertyDrag.panel?.isConnected && propertyDrag.panel.contains(button) &&
        button.dataset.subtab !== propertyDrag.sourceTab &&
        propertyDrag.panel.querySelector(`.lex-tabbed-panel-tabs .lex-subtab-button[data-subtab="${propertyDrag.sourceTab}"]`)?.dataset.lexAcceptFields) {
      propertyDrop = {crossTab: button.dataset.subtab, marker: button, after: true};
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      button.classList.add("lex-drop-target");
      return;
    }
    const target = event.target.closest?.(".lex-detail-field");
    if (target === field) return;
    if (state.fields.has(target)) {
      const after = event.clientY >= target.getBoundingClientRect().top + target.offsetHeight / 2;
      propertyDrop = {node: target.parentElement, before: after ? target.nextSibling : target, marker: target, after};
    } else {
      const section = event.target.closest?.(".lex-detail-section");
      const title = event.target.closest?.(".lex-detail-section-title");
      const sectionNode = section?.querySelector(":scope > .lex-detail-section-content");
      // A title drop lands beside the section instead of inside it,
      // above or below by pointer half. That is how a property leaves
      // every section for the bare panel. The section must belong to
      // the dragged field's own panel, like the content drop below:
      // without the membership check a title drop stole the property
      // into another panel instead of refusing it. An empty section has
      // nothing to leave, so its title takes the drop inside: without
      // that an empty section could never be filled by dragging, since
      // its content has no box to aim at.
      if (title && section && section.parentElement && !title.closest(".lex-detail-field")
          && state.groups.has(sectionNode)
          && sectionNode.querySelector(".lex-detail-field")) {
        const after = event.clientY >= section.getBoundingClientRect().top + section.offsetHeight / 2;
        propertyDrop = {node: section.parentElement, before: after ? section.nextSibling : section, marker: section, after};
      } else {
        if (state.groups.has(sectionNode)) {
          propertyDrop = {node: sectionNode, before: null, marker: section, after: true};
        } else {
          // An emptied column holds no property to land before or after, so
          // the column itself is the target. Non-empty columns still take
          // drops on their properties, never here, so aiming between two
          // rows keeps landing between them.
          const column = event.target.closest?.(".lex-tweak-column");
          const empty = column && state.groups.has(column) &&
            ![...column.children].some(child => state.fields.has(child));
          if (empty) propertyDrop = {node: column, before: null, marker: column, after: true};
          const looseColumn = !empty && column && !state.groups.has(column)
            && !column.querySelector(".lex-detail-section,.lex-detail-field")
            && column.closest(".lex-tweaks-paged")?.lexUnpaged === true
            && column.closest(".lex-tweaks-paged") === field.closest(".lex-tweaks-paged");
          if (looseColumn) propertyDrop = {node: column, before: null, marker: column, after: true, looseLane: true};
        }
      }
    }
    if (!propertyDrop) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    if (propertyDrop.marker.classList.contains("lex-tweak-column")) propertyDrop.marker.classList.add("lex-property-drop-target");
    else propertyDrop.marker.classList.add(propertyDrop.after ? "lex-property-drop-after" : "lex-property-drop-before");
  });
  document.addEventListener("drop", event => {
    if (!propertyDrag || !propertyDrop || !sharedSettingsSnapshot?.developerMode) return;
    event.preventDefault();
    if (propertyDrop.crossTab) {
      moveDetailFieldToTab(propertyDrop.crossTab);
      clearPropertyDrop();
      return;
    }
    const {state, field, before} = propertyDrag;
    const nodeExisted = state.groups.has(propertyDrop.node);
    addPropertyGroup(state.groups, propertyDrop.node);
    propertyDrop.node.insertBefore(field, propertyDrop.before);
    syncPagerCards(field.closest(".lex-tweaks-paged"));
    const after = capturePropertyLayout(state);
    // Lane pins follow looseness, never history: a field loose in a column
    // pins its lane, and one back inside a section drops its pin, or the
    // restore below would rip it back out. Bare flows (no section in the
    // pager) never pin: their columns are the groups, and pins would lock
    // a redeal that must stay fluid.
    {
      const pager = propertyDrop.node.closest?.(".lex-tweaks-paged");
      if (pager?.lexUnpaged === true && pager.querySelector(".lex-detail-section")) {
        const lanes = [...pager.querySelectorAll(".lex-tweak-column")]
          .filter(column => column.closest(".lex-tweaks-paged") === pager);
        if (!nodeExisted || propertyDrop.looseLane) {
          const at = lanes.indexOf(propertyDrop.node);
          if (at >= 0) for (const [candidate] of state.fields) {
            if (candidate.closest(".lex-tweak-column") !== propertyDrop.node) continue;
            const prop = candidate.dataset.lexLayoutField;
            if (prop) after.lanes[`field:${prop}`] = at;
          }
        } else {
          const prop = field.dataset.lexLayoutField;
          if (field.closest(".lex-detail-section")) delete after.lanes[`field:${prop}`];
          else if (prop) {
            const at = lanes.indexOf(field.closest(".lex-tweak-column"));
            if (at >= 0) after.lanes[`field:${prop}`] = at;
          }
        }
      }
    }
    clearPropertyDrop();
    if (JSON.stringify(before) === JSON.stringify(after)) return;
    const apply = layout => { storePropertyLayout(state, layout); reapplyStoredLayout(state); };
    pushLabelUndo({before, after, apply});
    labelRedo.length = 0;
    labelHistoryChanged();
    void apply(after);
  });
  document.addEventListener("dragend", () => {
    propertyDrag?.field.classList.remove("lex-property-dragging");
    propertyDrag = null;
    clearPropertyDrop();
  });
  let layoutPending = false;
  const changedLayoutRoots = new Set();
  new MutationObserver(records => {
    for (const record of records) {
      const target = record.target instanceof Element ? record.target : record.target.parentElement;
      if (!target || target.closest('.lex-detail-field')) continue;
      const changed = [...record.addedNodes, ...record.removedNodes].filter(node => node instanceof Element &&
        (node.matches('.lex-detail-field[data-lex-layout-field],.lex-detail-section,.lex-detail-section-content') ||
         node.querySelector('.lex-detail-field[data-lex-layout-field],.lex-detail-section')));
      if (!changed.length) continue;
      const existing = target.closest('.lex-detail-panel') || target.closest('.lex-detail-section');
      if (existing) changedLayoutRoots.add(existing);
      for (const node of changed) {
        if (!node.isConnected) continue;
        const fields = node.matches('.lex-detail-field[data-lex-layout-field]') ? [node] :
          [...node.querySelectorAll('.lex-detail-field[data-lex-layout-field]')];
        for (const field of fields) {
          const root = propertyRoot(field);
          if (root) changedLayoutRoots.add(root);
        }
      }
    }
    if (!changedLayoutRoots.size) return;
    if (layoutPending) return;
    layoutPending = true;
    requestAnimationFrame(() => {
      layoutPending = false;
      const roots = [...changedLayoutRoots];
      changedLayoutRoots.clear();
      roots.filter(root=>root.isConnected).forEach(preparePropertyLayout);
    });
  }).observe(document.documentElement, {childList: true, subtree: true});

  const fieldLabelKey = label =>
    `${shellPluginId()}-${activePageTab()}.field.${label}.label`;
  const labelNode = options => {
    const shipped = typeof options.label === "string" ? options.label : "";
    const node = element("span", {class: "lex-detail-field-label-text"},
      shipped ? savedLabel(fieldLabelKey(shipped), shipped) : options.label);
    if (!shipped) return node;
    node.addEventListener("dblclick", event => {
      if (!sharedSettingsSnapshot?.developerMode) return;
      event.preventDefault();
      event.stopPropagation();
      renameInPlace(fieldLabelKey(shipped), activePageTab(), shipped, node);
    });
    return node;
  };
  // Rename a value in place: the text is swapped for an input, and Enter hands
  // the new text to the caller, which owns where that text is stored. Escape,
  // or a click somewhere else, leaves the value as it was. This is the same
  // edit a UI label gets from renameInPlace; what differs is only what happens
  // to the text afterwards, which is why the caller is handed it.
  const renameValue = (node, options = {}) => {
    const before = String(options.value ?? node.textContent ?? "");
    const input = element("input", {type: "text", class: "lex-label-rename",
      value: before, "aria-label": `Rename ${options.label || "this value"}`});
    copyRenameFace(node, input);
    node.replaceWith(input);
    input.focus();
    input.select();
    let finished = false;
    const finish = accept => {
      if (finished) return;
      finished = true;
      const typed = input.value.trim();
      input.replaceWith(node);
      // Clearing the name puts the shipped one back: a record is never
      // left nameless. Without a shipped name a blank keeps the old one.
      const final = !typed && accept && options.shipped ? options.shipped : typed;
      if (!accept || !final || final === before) return;
      node.textContent = final;
      options.commit?.(final);
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); finish(true); }
      else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(false));
    return input;
  };
  // An in-place rename swaps text for an input; the typed text keeps the
  // fitted size and face of the text it replaces instead of jumping to
  // the container's inherited font.
  const copyRenameFace = (node, input) => {
    const face = getComputedStyle(node);
    input.style.fontSize = face.fontSize;
    input.style.fontFamily = face.fontFamily;
    input.style.fontWeight = face.fontWeight;
    input.style.lineHeight = face.lineHeight;
    input.style.letterSpacing = face.letterSpacing;
  };
  const renameInPlace = (key, tabId, fallback, text) => {
    const before = text.textContent;
    const input = element("input", {type: "text", class: "lex-label-rename",
      value: before, "aria-label": `Rename ${fallback}`});
    copyRenameFace(text, input);
    text.replaceWith(input);
    input.focus();
    input.select();
    let finished = false;
    const finish = async commit => {
      if (finished) return;
      finished = true;
      const typed = input.value.trim();
      const label = typed && typed !== fallback ? typed : fallback;
      // Escape, or a click somewhere else, keeps the name that was there.
      if (!commit) { text.textContent = before; input.replaceWith(text); return; }
          text.textContent = label;
          input.replaceWith(text);
          relabelHeaders(key, label);
          resortSubtabOf(text);
          // Remember it, so the shell's undo can take the name back: the
          // plugin's record history has no idea this happened.
          pushLabelUndo({key, tabId, before, after: label, shipped: fallback, node: text});
          labelRedo.length = 0;
          const saved = await storeLabel(key, tabId, label, fallback);
          labelHistoryChanged();
          try {
            // "Shipped" only when the shared default kept the name.
            if (saved) {
              showToast(label === fallback ? `${fallback} is back to its shipped name.`
                                           : `${label} is now the shipped name.`);
            } else {
              showToast(label === fallback ? `${fallback} is back on this device.`
                                           : `${label} is saved on this device.`);
            }
          } catch (_error) {}
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); finish(true); }
      else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(false));
  };

  const mountShell = options => {
    // Every game has the shared Mods tab, always leftmost. The shell draws it
    // itself; every other tab still belongs to the plugin.
    const pluginNavigate = options.navigate, pluginActiveTab = options.activeTab;
    const mods = modsPage(options.plugin.id, options.plugin.name);
    let shellPage = null;
    options = {...options,
      importModDrop: transfer => mods.importDrop(transfer),
      tabs: [{id: "mods", label: "Mods", help: "Every mod in this game's library: switch them on or off, edit their details and settings, or add new ones."},
        ...(options.tabs || []).filter(tab => tab.id !== "mods")],
      activeTab: () => shellPage || pluginActiveTab(),
      navigate: tab => {
        if (tab === "mods") {
          shellPage = "mods";
          const toolbar = document.querySelector("#toolbar");
          if (toolbar) toolbar.hidden = true;
          mods.show(document.querySelector("#main"));
          refreshShellTabs();
          return;
        }
        shellPage = null;
        mods.hide();
        // The new tab announces itself at once: the old content is replaced
        // with a throbber synchronously, so a slow load never looks dead
        // and the old tab is never shown as the new one. A plugin that
        // renders synchronously replaces this before paint; no flash.
        document.querySelector("#main")?.replaceChildren(loadingPanel({label: `Loading ${tab}`}));
        // The tab marks itself before the plugin renders: every label and
        // layout key is read from the marked tab, so marking after the
        // render would build the new page under the old tab's keys and drop
        // every rename on the floor.
        for (const button of tabButtons.values())
          button.classList.toggle("active", button.dataset.tab === tab);

        return pluginNavigate(tab);
      }};
    let refreshShellTabs = () => {};
    activeShellReadonly = sessionHasNoMod() ? () => true
      : typeof options.readonly === "function" ? options.readonly : null;
    const host = typeof options.host === "string" ? document.querySelector(options.host) : options.host;
    if (!host) throw new Error("Lexeditor shell host is missing");
    document.body.dataset.lexPlugin = options.plugin.id;
    document.body.dataset.lexTheme = options.plugin.themeName || options.plugin.id;
    applyTheme(options.plugin.theme);
    const quoteScreen = pluginLoadingScreen;
    if (quoteScreen && !loadingParameters.get("lexQuote")) callWindow("loading_quote", options.plugin.id).then(result => {
      if (!result?.quote) return;
      sessionQuote.set(result.quote);
      const quote = quoteScreen.querySelector(".lex-plugin-loading-quote");
      // Keep one quote for the entire transition. A late response may seed
      // the next load, but must not replace text already being read or fading.
      if (pluginLoadingScreen === quoteScreen && quote?.textContent === "Loading editor…") quote.textContent = result.quote;
    }).catch(() => {});

    const brand = element("button", {
      class: "lex-brand-button",
      onmousedown:event=>event.preventDefault(),
      onselectstart:event=>event.preventDefault(),
      title: "Return to main menu",
      "aria-label": "Return to main menu",
      "data-lex-history-control": true,
    }, element("h1", {"data-lex-brand-label":options.brand || "LEXEDITOR",
      "aria-label":options.brand || "LEXEDITOR"}));
    const nav = element("nav", {"aria-label": `${options.plugin.name || options.plugin.id} sections`});
    const navFrame = element("div", {class: "lex-nav-frame"}, nav);
    // A strip that scrolls (--lex-nav-overflow-x) keeps its active tab in
    // view: when the tab changes, and when fonts or the window resize it.
    // Between those, the reader's own scrolling is left alone.
    let shownNavTab = null;
    const revealActiveTab = () => {
      const activeNavTab = nav.querySelector("button.active");
      shownNavTab = activeNavTab;
      if (!activeNavTab || navFrame.scrollWidth <= navFrame.clientWidth + 1) return;
      const frameBox = navFrame.getBoundingClientRect(), tabBox = activeNavTab.getBoundingClientRect();
      if (tabBox.left < frameBox.left) navFrame.scrollLeft -= frameBox.left - tabBox.left;
      else if (tabBox.right > frameBox.right) navFrame.scrollLeft += tabBox.right - frameBox.right;
    };
    window.addEventListener("resize", revealActiveTab);
    document.fonts?.addEventListener?.("loadingdone", revealActiveTab);
    let githubWorkspace = null;
    let navigationHistory = null;
    let developerMode = false;
    const installPackagedDefaults = async () => {
      const result = await callWindow("default_views", options.plugin.id);
      let changed = false;
      for (const values of Object.values(result?.views || {})) {
        for (const [key, value] of Object.entries(values || {})) {
          if (localStorage.getItem(key) !== null) continue;
          localStorage.setItem(key, String(value));
          changed = true;
        }
      }
      if (changed) { relabelTabBar(); options.navigate(options.activeTab()); }
    };
    if (window.pywebview?.api) installPackagedDefaults().catch(() => {});
    else window.addEventListener("pywebviewready", () => installPackagedDefaults().catch(() => {}), {once:true});
    // Tweaks is an ordinary page. It was grouped with Settings, which pushed it
    // out of the run of tabs and gave it a paler fill, so a page the reader
    // uses constantly read as chrome. Settings is the only tab that sits apart.
    const isSpecialTab = tab => tab.special === true || tab.id === "settings" || tab.id === "tweaks";
    // Pages are alphabetical by name. Lexer asked for that and asked again when
    // it was swapped for each plugin's declared order ("the tabs aren't
    // alphabetically sorted anymore. wtf?"): a reader finds a page by name,
    // and every game's bar then reads the same way. A page whose order carries
    // meaning still states `order`.
    const tabName = tab => savedLabel(`${options.plugin.id}-${tab.id}.label`,
      String(tab.label instanceof Node ? tab.label.textContent : tab.label ?? tab.id));
    const orderedTabs = [...options.tabs].sort((left, right) => {
      const leftSettings = isSpecialTab(left);
      const rightSettings = isSpecialTab(right);
      if ((left.id === "mods") !== (right.id === "mods")) return left.id === "mods" ? -1 : 1;
      if (leftSettings !== rightSettings) return leftSettings ? 1 : -1;
      const rank = tab => tab.id === "tweaks" ? 2 : (tab.id === "misc" || /^misc\.?$/i.test(String(tab.label))) ? 1 : 0;
      // A page whose order carries meaning - Blank's component levels run from
      // whole pages down to single controls - says so with `order`.
      const stated = tab => Number.isFinite(tab.order) ? tab.order : null;
      if (stated(left) !== null && stated(right) !== null && stated(left) !== stated(right)) return stated(left) - stated(right);
      return rank(left) - rank(right)
        || tabName(left).localeCompare(tabName(right), undefined, {numeric: true, sensitivity: "base"});
    });
    const tabButtons = new Map();
    // Tabs the reader never opened carry a dot until first viewed. The set
    // persists per plugin; a first mount seeds it with the tabs at hand, so
    // a fresh install shows no dots and only a tab that appears later (a new
    // page) is dotted. Stale ids prune on the way in.
    const viewedTabsKey = `lexeditor:viewed-tabs:${options.plugin.id}`;
    let viewedTabs = null;
    try {
      const stored = localStorage.getItem(viewedTabsKey);
      viewedTabs = stored === null ? null : new Set(JSON.parse(stored));
    } catch (_error) { viewedTabs = new Set(); }
    if (viewedTabs === null) {
      viewedTabs = new Set(orderedTabs.map(tab => tab.id));
    } else {
      for (const id of [...viewedTabs]) {
        if (!orderedTabs.some(tab => tab.id === id)) viewedTabs.delete(id);
      }
    }
    const saveViewedTabs = () => {
      try { localStorage.setItem(viewedTabsKey, JSON.stringify([...viewedTabs])); }
      catch (_error) {}
    };
    saveViewedTabs();
    // A shipped rename reaches an already-built bar: the packaged
    // defaults arrive after the buttons are drawn, so seeding (and a
    // view reset, which wipes the tab's own keys) re-applies the
    // stored names. Only an override rewrites a label, so a drawn
    // game font never becomes plain text.
    const relabelTabBar = () => {
      for (const [id, button] of tabButtons) {
        let stored = null;
        try { stored = localStorage.getItem(`${options.plugin.id}-${id}.label`); }
        catch (_error) {}
        if (stored === null || stored === "") continue;
        const labelText = button.querySelector(".lex-tab-label-text");
        if (labelText && labelText.textContent !== stored) labelText.textContent = stored;
      }
    };
    for (const [tabIndex, tab] of orderedTabs.entries()) {
      let defaultHoldTimer = 0;
      let savedDefault = false;
      const saveDefault = async () => {
        const token = `${options.plugin.id}-${tab.id}`;
        const preferences = {};
        for (let index = 0; index < localStorage.length; index += 1) {
          const key = localStorage.key(index);
          if (key && key.includes(token)) preferences[key] = localStorage.getItem(key);
        }
        if (!Object.keys(preferences).length) {
          showToast(`${tab.label} has no view settings to save.`);
          return;
        }
        const result = await callWindow("save_default_view", options.plugin.id, tab.id, preferences);
        savedDefault = !!result?.saved;
        if (savedDefault) {
          showToast(`${tab.label} is now the shipped default view.`);
          refreshMissingDefaultViews(options.plugin.id, tab.id);
        }
      };
      const button = element("button", {
        "data-tab": tab.id,
        class: [tab.id === options.activeTab() ? "active" : "",
        isSpecialTab(tab) ? "lex-settings-tab" : "",
        isSpecialTab(tab) || tab.id === "tweaks" || tab.id === "mods" ? "lex-tweaks-tab" : "",
        // Mods wears the same special fill as Tweaks; the sort puts it first.
        tab.id === "mods" ? "lex-settings-tab lex-mods-tab" : ""].filter(Boolean).join(" "),
        onclick: () => {
          playThemeSound("confirm");
          githubWorkspace?.hide();
          options.navigate(tab.id);
        },
        // The move sound belongs to actually MOVING between tabs, not to
        // pointing at one. Firing it on pointerenter meant dragging the
        // cursor across the bar machine-gunned the sound. Keyboard tab
        // changes still play it, because those really are moves.
        onfocus: event => { if (event.target.matches(":focus-visible")) playThemeSound("move"); },
        onpointerdown: event => {
          if (event.button !== 2 || !developerMode) return;
          savedDefault = false;
          clearTimeout(defaultHoldTimer);
          defaultHoldTimer = setTimeout(() => {
            savedDefault = true;
            saveDefault().catch(error => {
              savedDefault = false;
              showAlert({title: "Could not save the default view", message: error.message || String(error)});
            });
          }, 700);
        },
        onpointerup: () => clearTimeout(defaultHoldTimer),
        onpointercancel: () => clearTimeout(defaultHoldTimer),
        oncontextmenu: async event => {
          event.preventDefault();
          clearTimeout(defaultHoldTimer);
          if (savedDefault) { savedDefault = false; return; }
          const token = `${options.plugin.id}-${tab.id}`;
          await resetStoredView(options.plugin.id, tab.id, token);
          relabelTabBar();
          options.resetView?.(tab.id);
          window.dispatchEvent(new CustomEvent("lexeditor-view-reset", {detail: {plugin: options.plugin.id, tab: tab.id}}));
          options.navigate(tab.id);
        },
      }, element("span", {class: "lex-tab-label"},
          element("span", {class: "lex-tab-label-text"},
            savedLabel(`${options.plugin.id}-${tab.id}.label`, tab.label)),
          viewedTabs.has(tab.id) ? "" : element("span",
            {class: "lex-tab-unviewed", "aria-hidden": "true", title: "Not opened yet"})),
        (key => key ? element("span", {
          class: "lex-tab-shortcut", "aria-hidden": "true",
        }, key) : "")(shortcutKeyFor(tabIndex + 1)));
      nav.append(button);
      tabButtons.set(tab.id, button);
      markMissingDefaultView(button, options.plugin.id, tab.id, "");
      // The handler is always attached and the mode is read when it fires:
      // settings arrive after the bar is built, so a developer-mode test at
      // build time would leave every tab unrenamable.
      const labelText = button.querySelector(".lex-tab-label-text");
      labelText.addEventListener("dblclick", event => {
        if (!developerMode) return;
        event.preventDefault();
        event.stopPropagation();
        renameInPlace(`${options.plugin.id}-${tab.id}.label`, tab.id, tab.label, labelText);
      });
    }
    const context = element("div", {class: "lex-plugin-context"});
    const undo = element("button", {
      id: "global-undo", class: "lex-history-button", title: "Undo (Ctrl+Z)",
      "aria-label": "Undo", "data-lex-history-control": true, disabled: true,
    }, historyIcon("undo"));
    const redo = element("button", {
      id: "global-redo", class: "lex-history-button", title: "Redo (Ctrl+Y)",
      "aria-label": "Redo", "data-lex-history-control": true, disabled: true,
    }, historyIcon("redo"));
    const save = element("button", {
      id: "global-save", class: "save lex-save-icon lex-command-primary", title: "No unsaved changes",
      "aria-label": "Save changes", "data-lex-history-control": true, disabled: true,
    }, saveIcon(), element("span", {class: "lex-save-count", hidden: true, "aria-hidden": "true"}));
    const game = element("button", {
      id: "global-game-process", class: "lex-game-process lex-command-primary", title: "Launch game",
      "aria-label": "Launch game", "data-lex-history-control": true,
    }, playIcon());
    const shortcuts = element("button", {
      id: "lexeditor-shortcuts", class: "lex-settings-button", title: "Keyboard shortcuts",
      "aria-label": "Show keyboard shortcuts", "data-lex-history-control": true,
      onclick: () => openShortcutPanel(!!sharedSettingsSnapshot?.developerMode),
      oncontextmenu: event => {
        if (!sharedSettingsSnapshot?.developerMode) return;
        event.preventDefault();
        openShortcutPanel(true, true);
      },
    }, keyboardIcon());
    const settings = element("button", {
      id: "lexeditor-settings", class: "lex-settings-button", title: "Lexeditor settings",
      "aria-label": "Open Lexeditor settings", "data-lex-history-control": true,
      onclick: options.settings || openSettings,
    }, settingsIcon());
    const windowControls = createWindowActions();
    const {minimize, maximize, close} = windowControls;
    const help = options.help ? element("button", {
      id: "plugin-data-map", class: "lex-help-button lex-ui-symbol", title: options.helpTitle || `Open ${options.plugin.id} Data Map`,
      "aria-label": options.helpTitle || `Open ${options.plugin.id} Data Map`,
      "data-lex-history-control": true,
      // Tab buttons hide the GitHub workspace before navigating; without
      // the same step these two navigated underneath a workspace that
      // stayed open, so they lit up and nothing happened.
      onclick: () => { githubWorkspace?.hide(); options.help(); },
    }, mapIcon()) : null;
    const info = options.info ? element("button", {
      id: "plugin-info", class: "lex-help-button", title: options.infoTitle || `Open ${options.plugin.id} information`,
      "aria-label": options.infoTitle || `Open ${options.plugin.id} information`,
      "data-lex-history-control": true,
      onclick: () => { githubWorkspace?.hide(); options.info(); },
    }, infoIcon()) : null;
    const github = element("button", {
      id: "plugin-github", class: "lex-developer-button lex-github-tab", hidden: true,
      title: "Open GitHub issues inside Lexeditor", "aria-label": "Open GitHub issues inside Lexeditor",
      "aria-pressed": "false", "data-lex-history-control": true,
    }, githubLogo());
    const restart = element("button", {
      id: "plugin-restart", class: "lex-window-button",
      title: "Restart Lexeditor", "aria-label": "Restart Lexeditor",
      "data-lex-history-control": true,
    }, restartIcon());
    const projectControl = mountProjectControl(options, context);
    // A session with no mod says so once, in the mod selector ("Vanilla",
    // locked), and the disabled save button's tooltip says why. A no-mod
    // badge between Play and redo was a third copy of the same fact, and
    // Lexer kept seeing it: "dude i can clearly still see this 'No mod' thing".
    const brandSlot = element("div", {class: "lex-brand-slot"}, brand);
    const leftActions = element("div", {class: "lex-shell-left-actions"}, context);
    const centerActions = element("div", {class: "lex-shell-center-actions"},
      undo, save, game, redo);
    const rightActions = element("div", {class: "lex-shell-right-actions"}, uiScaleControl(), settings, shortcuts, help, info);
    // Restart acts on the window, so it sits with the window controls and is
    // shaped like them. Parked at the end of the developer group it read as a
    // developer toggle with a gap between it and the controls it belongs to.
    restart.classList.remove("lex-developer-button");
    restart.classList.add("lex-window-button", "lex-window-restart");
    const developerActions = element("div", {class: "lex-developer-actions"}, github);
    windowControls.root?.prepend?.(restart);
    // Three cells: the two sides share the leftover width equally, so the
    // centre group sits in the middle of the window, and neither side can be
    // squeezed below its controls, so the centre group moves over instead of
    // being drawn on top of them (it used to be positioned outside the row's
    // layout and covered the zoom slider in small windows).
    const startSide = element("div", {class: "lex-shell-start"}, brandSlot, leftActions);
    const endSide = element("div", {class: "lex-shell-end"}, rightActions, developerActions, windowControls.root);
    const commandRow = element("div", {class: "lex-shell-command-row"},
      startSide, centerActions, endSide);
    const header = element("header", {class: "lex-shell-header"}, commandRow, navFrame);
    host.replaceWith(header);
    // The row keeps every control until it cannot hold them. In a window too
    // narrow for the whole rail, the scale slider is the one whose job can
    // wait - it is a preference, not an edit - and it comes back the moment
    // there is room. Anything else would either overflow the window or take a
    // control away in a window that has space for it.
    const fitCommandRow = () => {
      const scale = commandRow.querySelector(".lex-ui-scale");
      if (!scale) return;
      scale.hidden = false;
      if (commandRow.scrollWidth > commandRow.clientWidth + 1) scale.hidden = true;
    };
    fitCommandRow();
    window.addEventListener("resize", fitCommandRow);
    document.fonts?.ready?.then(fitCommandRow).catch(() => {});

    const initializeGitHub = async () => {
      if (!developerMode) return;
      if (githubWorkspace) {
        github.hidden = false;
        return;
      }
      try {
        const repository = await callWindow("github_repository", options.plugin.id);
        if (!repository?.repository) return;
        github.title = `Open ${repository.repository} issues inside Lexeditor`;
        github.setAttribute("aria-label", github.title);
        github.hidden = false;
        githubWorkspace = mountGitHubWorkspace(options, github, header, repository, () => refresh());
        github.oncontextmenu=event=>{event.preventDefault();callWindow("open_plugin_repository",options.plugin.id).catch(error=>showToast(String(error.message||error),true));};
      } catch (_error) {
        github.hidden = true;
      }
    };
    const setDeveloperMode = enabled => {
      developerMode = !!enabled;
      // Restarting the plugin is a developer action (issue #29), the same as
      // the GitHub workspace beside it and the Ctrl+Shift+R that reaches it.
      restart.hidden = !developerMode;
      if (!developerMode) {
        githubWorkspace?.hide();
        github.hidden = true;
      } else {
        initializeGitHub();
      }
    };
    // Hidden until the first answer arrives, rather than visible until it is
    // taken away.
    restart.hidden = true;
    const initializeDeveloperMode = async () => {
      try {
        const value = rememberSharedSettings(await callWindow("lexeditor_settings"));
        setDeveloperMode(value?.developerMode);
      }
      catch (_error) { setDeveloperMode(false); }
    };
    window.addEventListener("lexeditor-settings-changed", event => {
      rememberSharedSettings(event.detail);
      setDeveloperMode(event.detail?.developerMode);
    });
    if (window.pywebview?.api) initializeDeveloperMode();
    else window.addEventListener("pywebviewready", initializeDeveloperMode, {once: true});

    const leaveForMainMenu = async () => {
      window.__lexeditorNavigating = true;
      await panDocument("0", "100vw");
      try {
        const returned = await callWindow("return_to_main_menu");
        if (!returned) { window.__lexeditorNavigating = false; return false; }
        if (returned.url && !returned.hostNavigates) {
          location.href = returned.url;
        }
        return true;
      } catch (error) {
        window.__lexeditorNavigating = false;
        await panDocument("100vw", "0");
        throw error;
      }
    };
    brand.onclick = () => { playThemeSound("exit"); return returnToMainMenu(options, leaveForMainMenu); };
    const restartLexeditor = async () => {
      const started = await callWindow("restart_lexeditor");
      if (!started?.restarting) throw new Error("The desktop host did not restart. Close and reopen Lexeditor if this continues.");
      // The window is closing and a fresh process is starting; stay marked
      // navigating so the button never re-arms under the old page.
      window.__lexeditorNavigating = true;
      return true;
    };
    // One restart at a time. A second click while the window is closing is
    // ignored; the host also refuses a second restart once one is underway.
    let restarting = false;
    restart.onclick = async () => {
      if (restarting) return;
      restarting = true;
      restart.disabled = true;
      restart.classList.add("busy");
      try {
        await confirmUnsavedExit(options, restartLexeditor, {
          title: "Unsaved changes",
          question: "Save before restarting Lexeditor?",
          discardLabel: "Restart Without Saving",
          saveLabel: "Save and Restart",
          exitError: "Could not restart Lexeditor",
          pendingLabel: "Restarting Lexeditor…",
        });
      } finally {
        if (!window.__lexeditorNavigating) {
          restarting = false;
          restart.disabled = false;
          restart.classList.remove("busy");
        }
      }
    };
    const closeLexeditor = () => callWindow("window_close");
    const requestWindowClose = () => confirmUnsavedExit(options, closeLexeditor);
    window.__lexeditorRequestWindowClose = requestWindowClose;
    installWindowFrame({
      controls: windowControls,
      regions: [header],
      close: requestWindowClose,
    });

    if (options.context) {
      const content = options.context();
      context.append(...(Array.isArray(content) ? content : [content]));
    }

    // A plugin whose data lives in the browser hands over capture and restore
    // and gets snapshot history. One whose edits live on its server (DS1)
    // hands over its own history, with undo and redo, and keeps it as given.
    const ownHistory = typeof options.history?.undo === "function";
    const history = !options.history ? null
      : ownHistory ? options.history : new EditHistory({...options.history, changed: refresh});
    if (history && !ownHistory) history.observe(document);
  // A name the developer changed and a record the plugin changed undo
  // newest first, through one shared order instead of draining either
  // stack first.
  undo.onclick = () => undoNewest(history);
  redo.onclick = () => redoNewest(history);
    let saveBusy = false;
    const renderSaveContents = () => {
      const count = element("span", {class: "lex-save-count", hidden: true, "aria-hidden": "true"});
      save.replaceChildren(saveBusy
        ? element("span", {class: "lex-save-throbber", "aria-hidden": "true"})
        : saveIcon(), count);
    };
    const setSaveBusy = busy => {
      saveBusy = !!busy;
      document.body.classList.toggle("lex-save-busy", saveBusy);
      document.body.inert = saveBusy;
      save.classList.toggle("saving", saveBusy);
      save.setAttribute("aria-busy", String(saveBusy));
      renderSaveContents();
      refresh();
    };
    save.onclick = async () => {
      if (saveBusy || save.disabled) return;
      setSaveBusy(true);
      // Saving rebuilds the installed tweaks, which is what the Mods tab
      // alert marks describe: re-read them so a rebuilt mod clears its
      // mark at once instead of waiting for Play.
      try { await options.save?.(); playThemeSound("save"); await mods.refresh(); }
      catch (error) { showToast(error?.message || "Save failed.", true); }
      finally { setSaveBusy(false); }
    };
    save.oncontextmenu = event => {
      event.preventDefault();
      if (saveBusy || save.disabled) return;
      confirmDiscardChanges(options);
    };
    let gameRunning = false, gameCanLaunch = true, gameBusy = false;
    const renderGameProcess = (running, canLaunch = gameCanLaunch) => {
      const nextRunning = !!running;
      const nextCanLaunch = canLaunch !== false;
      if (nextRunning === gameRunning && nextCanLaunch === gameCanLaunch && game.childElementCount)
        return;
      gameRunning = nextRunning;
      gameCanLaunch = nextCanLaunch;
      game.replaceChildren(gameRunning ? stopIcon() : playIcon());
      game.title = gameRunning ? "Stop game" : gameCanLaunch ? "Launch game" : "Start this game from Steam";
      game.setAttribute("aria-label", game.title);
      game.classList.toggle("running", gameRunning);
      // Play is greyed out for a game Lexeditor cannot start; Stop always works.
      if (!gameBusy) game.disabled = !gameRunning && !gameCanLaunch;
    };
    const refreshGameProcess = async () => {
      try {
        const status = await callWindow("game_process_status", options.plugin.id);
        renderGameProcess(status?.running, status?.canLaunch);
      }
      catch (_error) { game.hidden = true; }
    };
    game.onclick = async () => {
      if (!gameRunning && !gameCanLaunch) return;
      gameBusy = true;
      game.disabled = true;
      try {
        const launching = !gameRunning;
        if (launching) await options.beforeLaunch?.();
        const result = await callWindow(launching ? "launch_game" : "stop_game", options.plugin.id);
        renderGameProcess(result?.running);
        if (launching && result?.running) options.afterLaunch?.(result);
      } catch (error) {
        showAlert({title: gameRunning ? "Could not stop the game" : "Could not launch the game", message: error.message || String(error)});
      } finally { gameBusy = false; game.disabled = !gameRunning && !gameCanLaunch; }
    };
    if (window.pywebview?.api) refreshGameProcess();
    else window.addEventListener("pywebviewready", refreshGameProcess, {once: true});
    const gameProcessTimer = setInterval(refreshGameProcess, 2000);
    window.addEventListener("pagehide", () => clearInterval(gameProcessTimer), {once: true});

    const applyDestination = async destination => {
      if (destination === "github") {
        if (!githubWorkspace) return false;
        githubWorkspace.show();
        return true;
      }
      if (!destination.startsWith("tab:")) return false;
      githubWorkspace?.hide();
      options.navigate(destination.slice(4));
      return true;
    };
    navigationHistory = new NavigationHistory({
      initial: `tab:${options.activeTab()}`,
      apply: applyDestination,
      changed: () => {},
    });
    window.__lexeditorNavigateHistory = direction => navigationHistory.go(direction);
    const removeBrowserHistoryGuard = installBrowserHistoryGuard(() => {
      playThemeSound("back");
      return navigationHistory.go(-1);
    });
    const removeExtendedMouseHistory = installExtendedMouseHistory(navigationHistory);
    window.addEventListener("pagehide", () => {
      removeBrowserHistoryGuard();
      removeExtendedMouseHistory();
    }, {once: true});

    let savedPreviewState;
    saveChangePreview(save,()=>options.pendingChanges?.() || pendingChangeList(savedPreviewState,options.history?.capture?.()),options.dirtyCount);
    let lastReportedDirty = null, noticedDirty = 0;
  function refresh() {
    // A rename outside a render - the shell's own undo - still has to move the
    // history buttons.
    labelHistoryChanged = refresh;
      refreshReferences();
      projectControl.refresh?.();
      const dirty = options.dirtyCount?.() || 0;
      if (dirty !== noticedDirty) { noticedDirty = dirty; save.lexNoteChanges?.(); }
      // Only the built-in change list reads this copy; a plugin with its own
      // pendingChanges would pay for a full copy of its data on every refresh.
      if (!dirty && options.history?.capture && !options.pendingChanges) savedPreviewState=clone(options.history.capture());
      navigationHistory?.visit(githubWorkspace?.state.open ? "github" : `tab:${options.activeTab()}`);
      undo.disabled = !(labelUndo.length || history?.canUndo);
      redo.disabled = !(labelRedo.length || history?.canRedo);
      // The shell's own accessor, not the plugin's, so a session the host
      // opened without a mod locks every edit even when the plugin never grew
      // a read-only notion of its own.
      const projectReadonly = shellIsReadonly();
      // Published so CSS can drop edit affordances that would be refused.
      document.documentElement.setAttribute(
        "data-lex-project-readonly", String(projectReadonly));
      save.disabled = saveBusy || projectReadonly || !dirty;
      save.title = saveBusy ? "Saving and building"
        : projectReadonly ? "Nothing can be saved: this is the game's own data, shown read-only. Create a mod from the mod menu to change anything."
        : (dirty ? `Save all ${dirty} unsaved change${dirty === 1 ? "" : "s"}` : "No unsaved changes");
      const saveCount = save.querySelector(".lex-save-count");
      if (saveCount) {
        saveCount.textContent = String(dirty);
        saveCount.hidden = !dirty;
      }
      nav.querySelectorAll("button").forEach(button => button.classList.toggle("active",
        !githubWorkspace?.state.open && button.dataset.tab === options.activeTab()));
      // Opening a tab marks it viewed wherever the navigation came from: a
      // click, a record link, or the tab the plugin opened itself with.
      const activeButton = tabButtons.get(options.activeTab());
      if (activeButton?.querySelector(".lex-tab-unviewed")) {
        viewedTabs.add(options.activeTab());
        saveViewedTabs();
        activeButton.querySelector(".lex-tab-unviewed").remove();
      }
      if (nav.querySelector("button.active") !== shownNavTab) revealActiveTab();
      github.classList.toggle("active", !!githubWorkspace?.state.open);
      help?.classList.toggle("active", !!options.helpActive?.());
      info?.classList.toggle("active", !!options.infoActive?.());
      syncInfoPanels(options.plugin?.id, !!options.infoActive?.());
      if (dirty !== lastReportedDirty) {
        lastReportedDirty = dirty;
        callWindow("set_dirty_count", dirty).catch(() => {});
      }
    }
    refresh();
    // Shortcut handling. Every branch flashes its own row in the panel when
    // the panel happens to be open, so the panel doubles as a live legend.
    const focusableSearch = () => document.querySelector(
      ".lex-pager-search input, input[type='search']:not([disabled])");
    const shortcutHandler = event => {
      if (event.key === "Escape" && shortcutPanel) { closeShortcutPanel(); return; }
      const developerMode = !!sharedSettingsSnapshot?.developerMode;
      const animAction = matchAnimationShortcut(event);
      if (animAction) {
        // With the panel open the shortcuts are a legend, not live controls.
        if (shortcutPanel) {
          event.preventDefault();
          event.stopPropagation();
          flashShortcut(animAction);
          return;
        }
        // A modal dialog keeps every key, Space included.
        if (document.querySelector("dialog[open]")) return;
        const target = event.target;
        const typing = target instanceof HTMLElement &&
          target.matches("input:not([type='checkbox']):not([type='range']),textarea,select,[contenteditable='true']");
        if (typing) return;
        // Only the transport's own play button owns Space: it toggles
        // through its native click, and nothing double-fires. Every
        // other button - tabs, steppers, markers - yields Space to
        // play/pause instead of re-firing itself.
        if ((event.key === " " || event.code === "Space") &&
            target instanceof HTMLElement && target.matches("button[data-anim-play-button]")) return;
        event.preventDefault();
        flashShortcut(animAction);
        ({ "anim-start": () => activeAnimationViewer.toStart(),
           "anim-prev": () => activeAnimationViewer.step(-1),
           "anim-play": () => activeAnimationViewer.toggle(),
           "anim-next": () => activeAnimationViewer.step(1),
           "anim-end": () => activeAnimationViewer.toEnd(),
        }[animAction]?.());
        return;
      }
      const action = matchShortcut(event, developerMode);
      if (!action) return;
      // With the panel open the shortcuts are a legend, not live controls.
      if (shortcutPanel) {
        event.preventDefault();
        event.stopPropagation();
        flashShortcut(action);
        return;
      }
      if (action === "undo" || action === "redo") {
        // Free text keeps native typing undo, and an open dialog keeps
        // every key; anything else undoes the app, blurring first so a
        // focused managed field commits what it holds.
        if (document.querySelector(".lex-dialog-backdrop,dialog[open]")) return;
        if (event.target.closest?.("textarea,input[type=text]:not([data-field-key]),input[type=search]")) return;
        document.activeElement?.blur?.();
      }
      const run = {
        undo: () => undo.click(),
        redo: () => redo.click(),
        save: () => save.click(),
        settings: () => settings.click(),
        datamap: () => help?.click(),
        info: () => info?.click(),
        launch: () => game.click(),
        restart: () => restart.click(),
        search: () => {
          const field = document.querySelector(
            ".lex-pager-search input, input[type='search']:not([disabled])");
          if (!field) return false;
          field.focus();
          field.select?.();
          return true;
        },
        tab: () => document.querySelectorAll("nav button[data-tab]")[
          Number(shortcutDigit(event)) - 1]?.click(),
        subtab: () => {
          const bar = [...document.querySelectorAll('.lex-subtab-bar[data-lex-subtab-shortcuts="true"]:not(.lex-tabbed-panel-tabs)')]
            .find(node => node.checkVisibility() && !node.closest('[hidden]'));
          bar?.querySelectorAll(':scope > .lex-subtab-button')[Number(shortcutDigit(event)) - 1]?.click();
        },
      }[action];
      if (!run) return;
      event.preventDefault();
      flashShortcut(action);
      run();
    };
    const shortcutButtons={undo,redo,save,settings,datamap:help,info,launch:game,restart};
    for(const [action,button] of Object.entries(shortcutButtons)){
      if(!button)continue;
      button.dataset.shortcutKey=SHORTCUTS.find(row=>row.id===action)?.keys.filter(key=>key!=="Ctrl").join("+").replace("Shift+","⇧").replace("Enter","↵")||"";
    }
    const showShortcutKeys=event=>document.documentElement.classList.toggle("lex-control-held",!!event.ctrlKey);
    document.addEventListener("keydown",showShortcutKeys);
    document.addEventListener("keyup",showShortcutKeys);
    window.addEventListener("blur",()=>document.documentElement.classList.remove("lex-control-held"));
    header.addEventListener("click",event=>{
      const button=event.target.closest("button");if(!button||button.disabled)return;
      button.classList.add("lex-command-pressed");setTimeout(()=>button.classList.remove("lex-command-pressed"),180);
    },true);
    document.addEventListener("keydown", shortcutHandler);

    // Hovering a tab reveals the number that jumps to it.
    nav.addEventListener("pointerover", event => {
      const button = event.target.closest?.("button[data-tab]");
      if (!button || button.querySelector(".lex-tab-ordinal,.lex-tab-shortcut")) return;
      const index = [...nav.querySelectorAll("button[data-tab]")].indexOf(button);
      if (index < 0 || index > 8) return;
      button.append(element("span", {class: "lex-tab-ordinal", "aria-hidden": "true"}, String(index + 1)));
    });
    nav.addEventListener("pointerout", event => {
      const button = event.target.closest?.("button[data-tab]");
      if (button && !button.contains(event.relatedTarget)) {
        button.querySelector(".lex-tab-ordinal")?.remove();
      }
    });

    const removeControlHelp = installControlHelp(document.body);
    window.addEventListener("pagehide", removeControlHelp, {once:true});

    refreshShellTabs = refresh;
    // The first time a game opens, offer Lexer's Mod and show where things are.
    // Downloaded Lexer's Mod modules stay up to date: checked as the game
    // opens (at most hourly, in the background) as well as on the Mods tab.
    const startFirstRun = () => {
      callWindow("lexmod_update", options.plugin.id).catch(() => {});
      return firstRun(options.plugin.id, options.plugin.name).catch(() => {});
    };
    if (window.pywebview?.api) startFirstRun();
    else window.addEventListener("pywebviewready", startFirstRun, {once: true});
    return {
      header, nav, context, settings, help, info, github, restart, githubWorkspace: () => githubWorkspace,
      save, game, undo, redo, minimize, maximize, close, history, navigationHistory, refresh,
    };
  };

  const list = options => {
    const root = element("div", {
      class: `lex-list ${options.class || ""}`.trim(),
      role: options.role,
      style: options.style,
      "aria-label": options["aria-label"],
      "aria-rowcount": options["aria-rowcount"],
    });
    if (options.header) root.append(typeof options.header === "function" ? options.header() : options.header);
    for (const row of options.rows) {
      const key = options.key(row);
      const selected = key === options.selected;
      const rowClass = typeof options.rowClass === "function" ? options.rowClass(row) : options.rowClass;
      const rowStyle = typeof options.rowStyle === "function" ? options.rowStyle(row) : options.rowStyle;
      const rowNode = element("div", {
        class: ["lex-list-row", rowClass || "", selected ? (options.selectedClass || "selected") : ""].filter(Boolean).join(" "),
        "data-key": key,
        role: options.rowRole,
        style: rowStyle,
        title: typeof options.rowTitle === "function" ? options.rowTitle(row) : options.rowTitle,
        "aria-selected": options.select ? String(selected) : null,
        // A shift-click ranges the selection: swallow the press so the
        // browser does not also stretch a text selection across the rows.
        onmousedown: options.select ? event => { if (event.shiftKey) event.preventDefault(); } : null,
        // The clicked row is marked at once, so a caller that keeps the table
        // and only updates what it drives does not have to reach into the
        // list's rows to move the selection itself.
        onclick: options.select ? event => {
          const marked = options.selectedClass || "selected";
          // Clicking the row that is already the only selection changes
          // nothing, so it re-selects nothing: re-rendering for it threw away
          // a name being double-clicked for editing in that row.
          const only = root.querySelectorAll(':scope > .lex-list-row[aria-selected="true"]');
          if (event.currentTarget.getAttribute("aria-selected") === "true" && only.length === 1 &&
              !event.shiftKey && !event.ctrlKey && !event.metaKey) return;
          for (const sibling of root.querySelectorAll(":scope > .lex-list-row")) {
            sibling.classList.toggle(marked, sibling === event.currentTarget);
            sibling.setAttribute("aria-selected", String(sibling === event.currentTarget));
          }
          options.select(row,event);
        } : null,
      }, options.render(row));
      options.decorateRow?.(rowNode, row, key);
      root.append(rowNode);
    }
    return root;
  };

  // A sortable column list is still the standard list. It adds table-like
  // headers and cells without creating a second record-view system.
  const dynamicColumnTemplate = columns => {
    const declaredGrow = columns.some(column => Number(column.grow) > 0);
    const nameIndex = columns.findIndex(column => column.key === "name");
    // Never hand the growth column to a generated fixture like the enabled
    // switch: unpinning the name column would otherwise leave every real
    // column at max-content and the table wider than its panel.
    const firstDescription = columns.findIndex(column => !column.generated && !column.width && !column.numberedId && !column.numeric);
    // If every field is numeric, keep every track at its content width.
    // Giving the first coordinate the unused width makes X look like a
    // description column while Y and Z stay compact.
    const automaticGrow = nameIndex >= 0 ? nameIndex : firstDescription;
    return columns.map((column, index) => {
      if (column.width) return column.width;
      const grow = Number(column.grow)
        || (!declaredGrow && automaticGrow >= 0 && index === automaticGrow ? 1 : 0);
      if (grow > 0) return `minmax(0, ${grow}fr)`;
      // Content maximums never yield: beside wider columns the track
      // overflows instead of shrinking, and the header cannot wrap into the
      // room there is. A flexible maximum sizes past content when room
      // suffices and shrinks toward min-content when it does not, so the
      // header wraps and the column sizes toward its values. Numbers never
      // wrap, so their min-content is the whole number: "5,000" is never
      // cut to "5,00".
      return "minmax(min-content, 1fr)";
    }).join(" ");
  };

  const isNumberedIdColumn = (column, rows) => {
    if (column.numberedId === true) return true;
    if (column.key !== "id") return false;
    const values = rows.map(row => row?.[column.key])
      .filter(value => value !== null && value !== undefined && value !== "");
    return values.length > 0 && values.every(value => /^#?\d+$/.test(String(value).trim()));
  };

  // Numeric record identity is shown immediately before the record name.
  // This visual rule does not change the caller-owned sort state.
  const numberedIdColumns = (columns, rows) => {
    const ordered = [...columns];
    const enabledIndex = ordered.findIndex(column => String(column.key).toLocaleLowerCase() === "enabled");
    if (enabledIndex > 0) {
      const [enabled] = ordered.splice(enabledIndex, 1);
      ordered.unshift(enabled);
    }
    const idIndex = ordered.findIndex(column => isNumberedIdColumn(column, rows));
    const nameIndex = ordered.findIndex(column => column.key === "name");
    if (idIndex < 0 || nameIndex < 0 || idIndex + 1 === nameIndex) return ordered;
    const [idColumn] = ordered.splice(idIndex, 1);
    ordered.splice(ordered.findIndex(column => column.key === "name"), 0, idColumn);
    return ordered;
  };

  // `enabled` is a generic record property, handled the same way as record id
  // and icon: any row set that carries it gets the column without the plugin
  // declaring one. The column is always leftmost, its rows draw greyed, and
  // the switch itself stays live so a disabled record can be switched back on.
  const ENABLED_KEY = "enabled";
  const hasEnabledProperty = rows => Array.isArray(rows) && rows.length > 0 &&
    rows.every(row => typeof row?.[ENABLED_KEY] === "boolean");
  // The mixed check/cross mark the Data Map already uses for yes/no.
  const enabledMark = () => element("span", {
    class: "lex-enabled-mark lex-ui-symbol", "aria-hidden": "true", title: "Enabled",
  }, element("span", {class: "lex-enabled-mark-yes"}, "\u2713"),
     element("span", {class: "lex-enabled-mark-no"}, "\u00d7"));
  const enabledColumn = change => ({
    key: ENABLED_KEY,
    // The factory, not one node: a single node cannot head two tables, and a
    // header rebuilt after the fact would be left with nothing.
    label: enabledMark,
    headerTitle: "Enabled",
    width: "max-content",
    align: "center",
    generated: true,
    sortValue: row => (row?.[ENABLED_KEY] ? 0 : 1),
    render: row => {
      if (typeof change !== "function") return booleanMark(row?.[ENABLED_KEY]);
      const input = element("input", {
        type: "checkbox",
        checked: !!row?.[ENABLED_KEY],
        "aria-label": "Enabled",
        onclick: event => event.stopPropagation(),
        onchange: event => change(row, event.target.checked, event),
      });
      return element("span", {class: "lex-enabled-toggle"}, input);
    },
  });
  const withEnabledColumn = (declared, rows, change, autoAdd = true) => {
    const columns = declared || [];
    const enabledIndex = columns.findIndex(
      column => String(column.key).toLocaleLowerCase() === ENABLED_KEY);
    if (!hasEnabledProperty(rows)) {
      return columns.filter((column, index) =>
        index !== enabledIndex || !column.generated);
    }
    if (enabledIndex >= 0) {
      return columns.map((column, index) =>
        index === enabledIndex && column.generated ? enabledColumn(change) : column);
    }
    return autoAdd ? [enabledColumn(change), ...columns] : columns;
  };

  // One pin, two positions: an unpinned pin hovers up and to the right and
  // drops into the page when it is stuck in. No crossed-out variant.
  const pinIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const icon = document.createElementNS(namespace, "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-hidden", "true");
    const pin = document.createElementNS(namespace, "path");
    pin.classList.add("lex-column-pin-on");
    pin.setAttribute("d", "M3.71 21.71L9 16.42l2.29 2.29c.2.2.45.29.71.29s.51-.1.71-.29l2-2a.996.996 0 0 0 0-1.41l-.79-.79l3.59-3.59l.79.79c.39.39 1.02.39 1.41 0l2-2a.996.996 0 0 0 0-1.41l-6-6a.996.996 0 0 0-1.41 0l-2 2a.996.996 0 0 0 0 1.41l.79.79l-3.59 3.59l-.79-.79a.996.996 0 0 0-1.41 0l-2 2a.996.996 0 0 0 0 1.41L7.59 15L2.3 20.29l1.41 1.41Z");
    icon.append(pin);
    return icon;
  };

  // Every property in a list-and-detail page can be pinned as a table column,
  // in every game. Pins used to exist only where a plugin wired its own
  // column preferences, so most games had none. The paged list now gives
  // each property without a pin of its own one, and its table shows the
  // pinned properties as columns. A row supplies a pinned value as
  // row.values[key] (or row[key]), and may give row.display[key] to show.
  let pagedPinOwner = null;
  // A list whose records' names the game stores renames them in its table's
  // Name column and in the detail heading, by double-click, through one
  // option: pagedListDetail({rename(row, name), renamable(row)}).
  let pagedRenameOwner = null;
  // Set by the shell's mod control: what an edit attempt on a locked project
  // does (offer to create a mod).
  let requestModForEdit = null;
  const renameColumn = (column, owner) => owner && column.key === "name" && !column.edit && !column.editor ? {
    ...column,
    edit: (row, value) => {
      const name = String(value ?? "").trim();
      if (name && name !== String(row.name ?? "") && owner.renamable(row)) owner.rename(row, name);
      else if (!name && owner.renamable(row) && typeof owner.shippedName === "function") {
        const shipped = owner.shippedName(row);
        if (shipped && shipped !== String(row.name ?? "")) owner.rename(row, shipped);
      }
    },
    editValue: row => row.name ?? "",
    cellClass: row => [typeof column.cellClass === "function" ? column.cellClass(row) : column.cellClass || "",
      owner.renamable(row) ? "" : "lex-cell-fixed"].filter(Boolean).join(" "),
  } : column;
  // The shipped label a pin was taken from: a pin taken after a rename
  // holds the renamed text, so match a stored rename by value first.
  const pinShipped = label => {
    const text = String(label ?? "");
    try {
      const prefix = `${shellPluginId()}-${activePageTab()}.field.`;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key?.startsWith(prefix) && key.endsWith(".label") && localStorage.getItem(key) === text)
          return key.slice(prefix.length, -".label".length);
      }
    } catch (_error) {}
    return text;
  };
  const autoPinStores = new Map();
  const autoPins = viewKey => {
    if (!autoPinStores.has(viewKey)) {
      const key = `lexeditor:pins:${viewKey}`;
      let pinned = [];
      try { pinned = JSON.parse(localStorage.getItem(key) || "[]"); } catch (_error) {}
      autoPinStores.set(viewKey, {key, pinned: (Array.isArray(pinned) ? pinned : [])
        .filter(entry => entry && typeof entry.key === "string")
        .map(entry => ({...entry, shipped: entry.shipped || pinShipped(entry.label)}))});
    }
    return autoPinStores.get(viewKey);
  };
  const pinnedValue = (row, key) => row?.values?.[key] ?? row?.[key];
  // The value a list sorts a record by: a pinned property (key "pin:<name>")
  // from the row's values, anything else from the row itself.
  const sortValueOf = (row, key) => {
    const name = String(key ?? "");
    return name.startsWith("pin:") ? pinnedValue(row, name.slice(4)) : (row?.[name] ?? row?.values?.[name]);
  };
  // Compare two records for a {key, dir} sort. Blanks go last whichever way.
  const compareRecords = (left, right, sort = {}) => {
    const a = sortValueOf(left, sort.key), b = sortValueOf(right, sort.key);
    const blank = value => value === undefined || value === null || value === "" || value === "\u2014";
    if (blank(a) || blank(b)) return blank(a) === blank(b) ? 0 : blank(a) ? 1 : -1;
    const result = typeof a === "number" && typeof b === "number" ? a - b
      : typeof a === "boolean" && typeof b === "boolean" ? Number(a) - Number(b)
      : String(a).localeCompare(String(b), undefined, {numeric: true, sensitivity: "base"});
    return result * (sort.dir || 1);
  };
  const pinnedColumns = owner => owner.store.pinned.map(entry => {
    const described = typeof owner.describe === "function" ? owner.describe(entry.key) : null;
    const editable = !!described?.editable && typeof owner.commitCell === "function";
    // A pin header reads as the developer last named it, here as in
    // the record's field: the rename store keys by shipped label.
    const shipped = described?.label ?? entry.shipped ?? entry.label ?? entry.key;
    const labelKey = fieldLabelKey(shipped);
    const shown = () => savedLabel(labelKey, shipped);
    return {
      key: `pin:${entry.key}`, label: entry.icon ? () => element("span", {class: "lex-pinned-header-label", "data-lex-label-key": labelKey,
        // The kind rides along so a game can swap the generic glyph for
        // its own art, the way DS1 label art replaces field glyphs.
        "data-lex-icon": entry.icon}, typeGlyph(entry.icon), shown()) : shipped, sortable: described?.sortable !== false,
      ...(described?.width ? {width: described.width} : {}), pinnedProperty: entry.key,
      sortValue: row => pinnedValue(row, entry.key) ?? "",
      numeric: described?.numeric === true,
      min: described?.minimum, max: described?.maximum, step: described?.step,
      choices: described?.choices || null,
      editValue: row => row?.values?.[entry.key] ?? "",
      edit: editable ? ((row, value) => owner.commitCell(row, entry.key, value)) : null,
      render: described?.render || (row => {
        const shown = row?.display?.[entry.key] ?? pinnedValue(row, entry.key);
        return shown === undefined || shown === null ? "" : typeof shown === "number" ? formatNumber(shown) : String(shown);
      })};
  });
  const autoPinButton = (owner, key, label, icon) => {
    const pinned = owner.store.pinned.some(entry => entry.key === key);
    return element("button", {
      type: "button", class: `lex-column-pin${pinned ? " pinned" : ""}`, "data-lex-control": "pin", "data-lex-auto-pin": "",
      "data-lex-pin-column": key, "aria-pressed": String(pinned),
      title: pinned ? `Hide ${label} in the table` : `Show ${label} in the table`,
      "aria-label": pinned ? `Unpin ${label} column` : `Pin ${label} column`,
      onclick: event => {
        event.preventDefault(); event.stopPropagation();
        const inserting = !owner.store.pinned.some(entry => entry.key === key);
        owner.toggle(key, label, icon);
        const button = event.currentTarget;
        button.classList.toggle("pinned", inserting);
        button.setAttribute("aria-pressed", String(inserting));
        button.title = inserting ? `Hide ${label} in the table` : `Show ${label} in the table`;
        button.setAttribute("aria-label", inserting ? `Unpin ${label} column` : `Pin ${label} column`);
        if (inserting) refusePinWhenCrowded(button, () => {
          owner.toggle(key, label, icon);
          button.classList.toggle("pinned", false);
          button.setAttribute("aria-pressed", "false");
          button.title = `Show ${label} in the table`;
          button.setAttribute("aria-label", `Pin ${label} column`);
        });
      },
    }, pinIcon());
  };
  // A record's own picture pins as a table column through the same
  // toggle as any property: the pin sits on the thumbnail's corner,
  // and a right-click on the thumbnail places or removes it. The
  // right-click stops here, so Developer Mode does not also add a
  // section from the heading behind it.
  const attachPreviewPin = (iconBox, owner, key, label) => {
    if (!(iconBox instanceof Element) || !owner || !key) return null;
    if (iconBox.querySelector(":scope > .lex-column-pin")) return iconBox.querySelector(":scope > .lex-column-pin");
    const button = autoPinButton(owner, key, label || "Icon", "");
    iconBox.append(button);
    iconBox.addEventListener("contextmenu", event => {
      event.preventDefault(); event.stopPropagation(); button.click();
    });
    return button;
  };
  const autoPinDetail = (node, owner) => {
    for (const field of node.querySelectorAll(".lex-detail-field[data-lex-layout-field]")) {
      if (field.querySelector(".lex-column-pin")) continue;
      const box = field.querySelector(":scope > .lex-detail-field-control");
      if (!box) continue;
      const key = field.dataset.lexLayoutField;
      const label = field.querySelector(".lex-detail-field-label-text")?.textContent?.trim() || key;
      box.append(autoPinButton(owner, key, label, field.dataset.lexIcon || ""));
    }
    const preview = node.querySelector?.(":scope > .lex-detail-panel-heading > .lex-detail-panel-icon[data-lex-preview-pin]");
    if (preview) attachPreviewPin(preview, owner, preview.dataset.lexPreviewPin, preview.dataset.lexPreviewPinLabel || "Icon");
  };

  const columnPreferences = (viewKey, definitions, changed = () => {}) => {
    const key = `lexeditor:columns:${String(viewKey || "view")}`;
    const declared = numberedIdColumns(definitions || [], []);
    const source = declared.some(column => String(column.key).toLocaleLowerCase() === ENABLED_KEY)
      ? declared : [enabledColumn(null), ...declared];
    const byKey = new Map(source.map(column => [column.key, column]));
    const defaults = source.filter(column => column.pinned !== false).map(column => column.key);
    let order = [...defaults];
    try {
      const stored = JSON.parse(localStorage.getItem(key) || "null");
      if (Array.isArray(stored)) {
        order = stored.filter(value => byKey.has(value));
      }
    } catch (_error) {}
    const save = () => {
      try { localStorage.setItem(key, JSON.stringify(order)); } catch (_error) {}
      // Preserve the divider while pinning. Clearing it made the detail pane
      // flash to the default width on every pin click.
      changed([...order]);
      window.dispatchEvent(new CustomEvent("lexeditor-columns-changed", {
        detail: {viewKey, columns: [...order]},
      }));
    };
    const api = {
      key,
      all: () => [...source],
      active: () => order.map(value => byKey.get(value)).filter(Boolean),
      isPinned: value => order.includes(value),
      toggle: value => {
        if (!byKey.has(value)) return;
        order = order.includes(value) ? order.filter(item => item !== value) : [...order, value];
        save();
      },
      move: (value, before) => {
        if (!order.includes(value) || value === before) return;
        const from = order.indexOf(value);
        const to = order.indexOf(before);
        order = order.filter(item => item !== value);
        let index = order.indexOf(before);
        // Dropped on a column it takes that slot: dragged rightward it
        // lands after the target, dragged leftward before it. Always
        // inserting before made a rightward drop a no-op.
        if (from >= 0 && to >= 0 && from < to) index = index < 0 ? order.length : index + 1;
        order.splice(index < 0 ? order.length : index, 0, value);
        save();
      },
      reset: () => { order = [...defaults]; save(); },
      pinButton: (value, label = byKey.get(value)?.label || value) => {
        const pinned = order.includes(value);
        const icon = pinIcon();
        return element("button", {
          type: "button", class: `lex-column-pin${pinned ? " pinned" : ""}`,
          "data-lex-control": "pin",
          "data-lex-pin-column": value,
          title: pinned ? `Hide ${label} in the table` : `Show ${label} in the table`,
          "aria-label": pinned ? `Unpin ${label} column` : `Pin ${label} column`,
          "aria-pressed": String(pinned),
          onpointerenter: () => setColumnLit(value, true),
          onpointerleave: () => setColumnLit(value, false),
          onclick: async event => {
            event.preventDefault();
            event.stopPropagation();
            const button=event.currentTarget;
            if(button.dataset.pinMoving)return;
            button.dataset.pinMoving="true";
            const inserting=!api.isPinned(value);
            try {
              if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
                const animation=icon.animate([
                  {translate:inserting?'6px -6px':'0px 0px'},
                  {translate:inserting?'0px 0px':'6px -6px'},
                ],{duration:220,easing:inserting?'cubic-bezier(.4,0,.7,1)':'cubic-bezier(.2,.7,.3,1)',fill:'forwards'});
                await animation.finished.catch(()=>{});
                animation.cancel();
              }
              // Commit only after the movement: callers can replace the whole
              // detail panel when the visible columns change.
              button.classList.toggle('pinned',inserting);
              button.setAttribute('aria-pressed',String(inserting));
              button.setAttribute('aria-label',inserting?`Unpin ${label} column`:`Pin ${label} column`);
              button.title=inserting?`Hide ${label} in the table`:`Show ${label} in the table`;
              api.toggle(value);
              if(inserting)refusePinWhenCrowded(button,()=>{
                api.toggle(value);
                button.classList.toggle('pinned',false);
                button.setAttribute('aria-pressed','false');
                button.setAttribute('aria-label',`Pin ${label} column`);
                button.title=`Show ${label} in the table`;
              });
              markArrivingColumn(document, value);
            } finally { delete button.dataset.pinMoving; }
          },
        }, icon);
      },
    };
    return api;
  };

  // Hovering a column header (or the pin that owns that column) lights the
  // whole column and the matching property in the detail pane, so the reader
  // can see what a table column and a detail row have to do with each other.
  const litColumns = new Set();
  // A column that has just been pinned or unpinned announces itself once, so
  // the table does not simply have a different shape the next time you look
  // at it.
  // Pinning refuses when the table has no horizontal room: the insert is
  // rolled back after layout proves the table overflows, and the reader is
  // told why, instead of growing the page sideways.
  const refusePinWhenCrowded = (button, rollback) => {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const root = button.closest(".lex-paged-list-detail");
      const list = root?.querySelector(".lex-barrelled-master .lex-column-list")
        ?? root?.querySelector(".lex-column-list")
        ?? document.querySelector(".lex-barrelled-master .lex-column-list");
      if (!list || !list.isConnected) return;
      if (list.scrollWidth <= list.clientWidth + 1) return;
      rollback();
      // Dividers are static: nothing the reader can do widens the table,
      // so the only way out is named.
      showToast("No room for another column. Unpin a column first.", true);
    }));
  };

  const markArrivingColumn = (root, key) => {
    if (!root || !key) return;
    requestAnimationFrame(() => {
      root.querySelectorAll?.(`[data-column-key="${CSS.escape(String(key))}"]`)
        .forEach(node => {
          node.classList.add("lex-column-arriving");
          node.addEventListener("animationend",
            () => node.classList.remove("lex-column-arriving"), {once: true});
        });
    });
  };

  const setColumnLit = (key, lit) => {
    if (!key) return;
    if (lit) litColumns.add(key); else litColumns.delete(key);
    for (const node of document.querySelectorAll(glowSelector(key))) {
      node.classList.toggle("lex-column-lit", lit);
    }
  };
  // Only tabs inside a detail panel belong at its bottom. Page-level dataset
  // and language bars must keep their place above the complete list/detail view.
  const bottomPanelTabs = () => {
    for (const bar of document.querySelectorAll('.lex-subtab-bar:not([hidden])')) {
      const parent = bar.parentElement;
      if (!parent || parent.children.length < 2 || parent.closest('.lex-shell-header,[role="dialog"]')) continue;
      if (parent.matches('.lex-tabbed-panel,.lex-settings-columns')) continue;
      if (!parent.closest('.lex-detail-panel')) {
        parent.classList.remove('lex-bottom-tab-panel');
        continue;
      }
      parent.classList.add('lex-bottom-tab-panel');
    }
  };
  new MutationObserver(bottomPanelTabs).observe(document.documentElement,{childList:true,subtree:true});
  let panelTabTarget = sharedSettings()?.panelTabTarget || "hover";
  window.addEventListener("lexeditor-settings-ready",event=>{panelTabTarget=event.detail?.panelTabTarget||"hover"});
  let panelPointer = null;
  document.addEventListener("pointermove", event => { panelPointer = {x:event.clientX,y:event.clientY}; }, true);
  const panelTabNavigation = event => {
    if (event.key !== "Tab" || event.altKey || event.ctrlKey || event.metaKey) return;
    // Dialog controls retain normal keyboard navigation.
    if (event.target?.closest?.('[role="dialog"],.lex-dialog-backdrop')) return;
    // So does a field being typed in: Tab there finishes the entry and moves
    // to the next field. Cycling tabs from it flipped the page after an edit
    // (Lexer: "Tab after editing unexpectedly switching to Field-to-World").
    const typing = event.target?.closest?.('textarea,select,[contenteditable=""],[contenteditable="true"]')
      || (event.target?.matches?.('input') && !/^(checkbox|radio|button|submit|reset|range|color|file|image)$/i.test(event.target.type || "text"));
    if (typing) return;
    event.preventDefault();
    event.stopPropagation();
    let node = panelTabTarget === "focus" ? document.activeElement
      : panelPointer ? document.elementFromPoint(panelPointer.x,panelPointer.y) : null;
    for (; node && node !== document.body; node = node.parentElement) {
      const bar = node.matches?.('.lex-subtab-bar') ? node : node.querySelector?.(':scope > .lex-subtab-bar:not([hidden])');
      if (!bar) continue;
      const tabs = [...bar.querySelectorAll(':scope > [role="tab"]:not([disabled]):not([aria-disabled="true"])')];
      if (tabs.length < 2) continue;
      const index = Math.max(0,tabs.findIndex(tab=>tab.getAttribute('aria-selected')==='true'));
      const label = bar.getAttribute("aria-label");
      const next = (index + (event.shiftKey ? -1 : 1) + tabs.length) % tabs.length;
      tabs[next].click();
      if (panelTabTarget === "focus") requestAnimationFrame(()=>{
        const replacement=[...document.querySelectorAll('.lex-subtab-bar')].find(value=>value.getAttribute('aria-label')===label);
        replacement?.querySelector('[aria-selected="true"]')?.focus({preventScroll:true});
      });
      return;
    }
  };
  document.addEventListener("keydown", panelTabNavigation, true);

  // The rail doubles as the sort indicator when its row is not hovered.
  const setColumnSort = (key, direction) => {
    for (const node of document.querySelectorAll("[data-lex-property]")) {
      const rail = node.querySelector(":scope > .lex-field-type-rail");
      if (node.dataset.lexProperty === String(key) && direction) {
        node.dataset.lexSort = direction > 0 ? "asc" : "desc";
        // The arrow replaces the type marker, so it has to say what it means.
        if (rail) rail.title = `The list is sorted by this property, ${direction > 0 ? "smallest first" : "largest first"}.`;
      } else {
        delete node.dataset.lexSort;
        if (rail && rail.title.startsWith("The list is sorted")) rail.removeAttribute("title");
      }
    }
  };

  // Only a column's own header lights it. Binding this to a cell lit the whole
  // column whenever the pointer crossed any row of it, so simply reading down
  // a table flashed columns on and off.
  const bindColumnHighlight = (node, key) => {
    if (!node || !key) return node;
    if (!node.classList?.contains("lex-column-list-head-cell") &&
        !node.classList?.contains("lex-column-heading")) return node;
    node.addEventListener("pointerenter", () => setColumnLit(key, true));
    node.addEventListener("pointerleave", () => setColumnLit(key, false));
    return node;
  };

  // A paged list hands each table one page of records. A table that sorted
  // itself would reorder the fourteen rows on screen and leave the rest of the
  // list in its old order, which reads as "sorting sorts the page". So the
  // paged list owns the order: it sorts the whole record set with the table's
  // own comparison and re-renders, the table draws the mark, and this map
  // remembers the choice across the re-render the click causes.
  const pagedSortStates = new Map();
  let pagedSortOwner = null;

  // Editing is a per-cell action, not a table mode: double-click a value and
  // the column's own editor takes over that cell until it is committed or
  // dismissed. Tables that never declare an editor stay read-only.
  // A double-click on an editable cell, counted by hand: when the first
  // click selects the row and the list re-renders, the second click lands on
  // a new cell and the browser sends no dblclick at all. Two clicks on the
  // same row's same column within the double-click time are one.
  let lastCellClick = null;
  document.addEventListener("click", event => {
    const cell = event.target.closest?.(".lex-column-list-cell");
    if (!cell) { lastCellClick = null; return; }
    const row = cell.closest("[data-key]");
    const identity = row ? `${row.dataset.key}|${cell.dataset.columnKey}` : null;
    const now = performance.now();
    const again = lastCellClick && now - lastCellClick.at < 500;
    // The same cell still on the page gets the browser's own double-click.
    if (again && lastCellClick.cell !== cell && identity && lastCellClick.identity === identity) {
      lastCellClick = null;
      // This click may re-render the list too, so the editor opens after it,
      // in whichever cell is there by then.
      const rowKey = row.dataset.key, columnKey = cell.dataset.columnKey;
      setTimeout(() => {
        if (document.querySelector(".lex-cell-editing")) return;
        const current = [...document.querySelectorAll(`[data-key="${CSS.escape(rowKey)}"] .lex-column-list-cell[data-column-key="${CSS.escape(columnKey)}"]`)]
          .find(node => node.isConnected && node.lexBeginEdit);
        current?.lexBeginEdit();
      }, 0);
      return;
    }
    lastCellClick = {identity, cell, at: now};
  }, true);
  const beginCellEdit = (cell, column, row, refresh) => {
    if (!column?.edit || cell.classList.contains("lex-cell-editing") || cell.classList.contains("lex-cell-fixed")) return;
    if (shellIsReadonly()) { requestModForEdit?.(); return; }
    const content = cell.querySelector(".lex-column-cell-content");
    if (!content) return;
    const original = [...content.childNodes];
    let committed=false;
    const commit = value => {
      if(committed)return;committed=true;
      cell.classList.remove("lex-cell-editing");
      content.replaceChildren(...original);
      if (value !== undefined) column.edit(row, value);
      refresh?.();
    };
    const editor = column.editor
      ? column.editor(row, commit)
      : (() => {
        const current=column.editValue ? column.editValue(row) : (row?.[column.key] ?? "");
        const input = column.choices ? element("select", {}, ...column.choices.map(entry => {
          const [value, label] = Array.isArray(entry) ? entry : [entry, entry];
          return element("option", {value: String(value)}, String(label));
        }))
          : element("input", {type:column.numeric?"number":"text",min:column.min,max:column.max,step:column.step,value:current});
        input.value=String(current);
        if(column.choices)input.addEventListener("change",()=>commit(input.value));
        input.addEventListener("keydown", event => {
          if (event.key === "Enter") { event.preventDefault(); commit(input.value); }
          if (event.key === "Escape") { event.preventDefault(); commit(undefined); }
        });
        input.addEventListener("blur", () => commit(input.value));
        return input;
      })();
    cell.classList.add("lex-cell-editing");
    content.replaceChildren(editor);
    editor.focus?.();
    editor.select?.();
  };

  // Column minima include the rendered heading, not only the body values.
  const columnHeadingWidths = new Map();
  // Measuring is split from writing so that every list waiting for a fit is
  // probed in one layout: prepare() adds a list's probes, finish() reads them
  // after all of them are in.
  const prepareHeadingFit = root => {
    if (!root.isConnected) return null;
    const base = root.lexHeadingTemplate || root.style.getPropertyValue("--lex-column-list-template");
    root.lexHeadingTemplate = base;
    const tracks = splitTemplateTracks(base);
    const heads = [...root.querySelectorAll(":scope > .lex-column-list-header:not(.lex-matrix-column-axis) > .lex-column-list-head-cell")];
    if (!heads.length || tracks.length !== heads.length) return null;
    // Probing one column at a time cost a full page layout per column, and a
    // panel holding a dozen tables spent over a second doing it.
    // Headers wrap: the floor is the longest word, not the whole line,
    // so a long name wraps instead of widening its column past the values.
    const probes = heads.map(head => {
      const probe = head.cloneNode(true);
      probe.removeAttribute("id");
      probe.style.cssText = "position:fixed;visibility:hidden;width:min-content;min-width:min-content;max-width:none;";
      probe.querySelectorAll("*").forEach(node => {
        node.style.whiteSpace = "normal";
        node.style.maxWidth = "none";
        node.style.flexShrink = "";
      });
      return probe;
    });
    heads[0].parentElement.append(...probes);
    return () => {
      const widths = probes.map(probe => Math.ceil(probe.offsetWidth + 2));
      probes.forEach(probe => probe.remove());

      const fitted = heads.map((head, index) => {
        const width = widths[index];
        const track = tracks[index], range = /^minmax\((.*),\s*([^,]+)\)$/.exec(track);
        // Intrinsic sizes are valid grid bounds, but are not CSS math values.
        // Their natural size already includes the unwrapped heading.
        if (range) {
          if (/^(?:min-content|max-content|auto)$/.test(range[1].trim())) {
            // A flexible maximum still needs a definite floor: an intrinsic
            // minimum resolves the base to max-content and the track never
            // shrinks, so the header cannot wrap. The longest word floors it.
            if (!/fr\b/.test(range[2])) return track;
            const floored = `minmax(${width}px, ${range[2].trim()})`;
            return CSS.supports('grid-template-columns', floored) ? floored : track;
          }
          // Grid accepts unitless zero, but CSS math requires a length when
          // comparing against pixels. Otherwise minmax(0,1fr) loses its floor.
          const minimum = /^[-+]?0(?:\.0+)?$/.test(range[1].trim()) ? "0px" : range[1];
          const candidate = `minmax(max(${width}px, ${minimum}), ${range[2]})`;
          return CSS.supports('grid-template-columns', candidate) ? candidate : track;
        }
        // A numbered-id column never goes below its widest id with the cell's
        // padding, measured by the grid itself: the table resizes its text
        // after this pass, and a first column that keeps room for the sort
        // mark cut its ids short (FF8 Weapons "#1").
        if (head.dataset.lexIdColumn === "true" && /^[\d.]+(?:px|em|rem|ch|%)$/.test(track))
          return `minmax(max-content, max(${width}px, ${track}))`;
        if (/^[\d.]+(?:px|em|rem|ch|%)$/.test(track)) return `max(${width}px, ${track})`;
        if (/^[\d.]+fr$/.test(track)) return `minmax(${width}px, ${track})`;
        return track;
      }).join(" ");
      if (!CSS.supports('grid-template-columns', fitted)) return () => {};
      columnHeadingWidths.set(root.lexHeadingKey, fitted);
      // The barrel unify floors the same tracks at the shared body width
      // after this pass. Writing here unconditionally would strip its floor
      // straight back off, and the two passes would trade templates for ever
      // on the observers between them. A template already covering this one -
      // same tracks, every minimum at least this minimum - is left alone.
      const trackMin = track => {
        const range = /^minmax\((.*),\s*([^,]+)\)$/.exec(track.trim());
        const part = range ? range[1] : track;
        const px = [...part.matchAll(/([\d.]+)px/g)].map(match => parseFloat(match[1]));
        if (px.length) return Math.max(...px);
        if (/^[-+]?0(?:\.0+)?$/.test(part.trim())) return 0;
        if (/^[\d.]+fr$/.test(part.trim())) return 0;
        return -1;
      };
      const trackMax = track => {
        const range = /^minmax\((.*),\s*([^,]+)\)$/.exec(track.trim());
        return (range ? range[2] : track).trim();
      };
      const covers = current => {
        const mine = splitTemplateTracks(current);
        const want = splitTemplateTracks(fitted);
        return mine.length === want.length && mine.every((track, index) =>
          trackMax(track) === trackMax(want[index]) && trackMin(track) >= trackMin(want[index]));
      };
      return () => {
        const current = root.style.getPropertyValue("--lex-column-list-template");
        if (current !== fitted && !covers(current))
          root.style.setProperty("--lex-column-list-template", fitted);
      };
    };
  };
  const pendingHeadingFits = new Set();
  const fitColumnHeadings = root => {
    if (pendingHeadingFits.size === 0) requestAnimationFrame(() => {
      const roots = [...pendingHeadingFits];
      pendingHeadingFits.clear();
      const reads = roots.map(prepareHeadingFit).filter(Boolean);
      const writes = reads.map(read => read());
      writes.forEach(write => write());
    });
    pendingHeadingFits.add(root);
  };

  // A font may start loading only after the first table uses it. The ready
  // promise taken while building that detached table can already be resolved.
  document.fonts?.addEventListener("loadingdone", () => {
    document.querySelectorAll(".lex-column-list").forEach(fitColumnHeadings);
  });

  const columnList = options => {
    const preferredColumns = options.columnPreferences?.active?.();
    // The generic enabled column is not a user-choosable column, so it is
    // added after saved preferences rather than being subject to them.
    // A table with its own column preferences wires its own pins; the paged
    // list then adds none, so no pin is ever dead.
    if (options.columnPreferences && pagedPinOwner) pagedPinOwner.declined = true;
    const pinOwner = options.columnPreferences ? null : pagedPinOwner;
    const renameOwner = pagedRenameOwner;
    const ownColumns = (pinOwner ? [...(options.columns || []), ...pinnedColumns(pinOwner)
      .filter(column => !(options.columns || []).some(own =>
        String(own.key ?? "").toLowerCase() === String(column.pinnedProperty ?? "").toLowerCase()))] : options.columns || [])
      .map(column => renameColumn(column, renameOwner));
    const columns = preferredColumns
      ? withEnabledColumn(preferredColumns, options.rows, options.enabledChange, false)
      : numberedIdColumns(
          withEnabledColumn(ownColumns, options.rows, options.enabledChange),
          options.rows || []);
    if (columns.some(column => isNumberedIdColumn(column, options.rows || []))) {
      setRecordIdWidth(options.rows, {floor: options.idFloor});
    }
    // A table inside a paged list does not own its order. The paged list sorts
    // the whole record set and tells the table which column to mark, so a page
    // is never sorted on its own.
    const pagedOwner = typeof options.sort === "function" ? null : pagedSortOwner;
    const sortState = pagedOwner?.state
      || (Array.isArray(options.sortState)
        ? {key: options.sortState[0], dir: options.sortState[1]}
        : (options.sortState || {}));
    requestAnimationFrame(() => setColumnSort(sortState.key, sortState.dir));
    const template = options.template || dynamicColumnTemplate(columns);
    const numberedColumn = column => isNumberedIdColumn(column, options.rows || []);
    const alignmentClass = column => `lex-column-align-${column.align || (numberedColumn(column) ? "start" : options.align) || "center"}`;
    // A numbered-id column's values sit at the start of the cell, so its
    // header does too; centred over them it read as misaligned (FF8 GF
    // ability Slot column).
    const headerAlignmentClass = column => `lex-column-align-${column.headerAlign
      || (numberedColumn(column) ? (column.align || "start") : null) || options.headerAlign || "center"}`;
    const canSort = column => column.sortable !== false && options.localSort !== false;
    const valueForSort = (row, column) => {
      const value = typeof column.sortValue === "function" ? column.sortValue(row) : row?.[column.key];
      if (value instanceof Node) return value.textContent || "";
      return value ?? "";
    };
    const magnitudeMetrics = new Map(columns.map(column => {
      if (column.numeric !== true) return [column.key, null];
      let integerDigits = 1, fractionDigits = 0;
      for (const row of options.rows || []) {
        const value = Number(valueForSort(row, column));
        if (!Number.isFinite(value)) continue;
        // Count what the cell shows, sign and thousands separators included:
        // counting bare digits left "-29,406" a character short, and its last
        // digit was cut off (FF8 > World > Field Returns, Z).
        const [integer, fraction = ""] = formatNumber(value).split(".");
        integerDigits = Math.max(integerDigits, integer.length);
        fractionDigits = Math.max(fractionDigits, fraction.length);
      }
      return [column.key, {integerDigits, fractionDigits}];
    }));
    const compareFor = column => (left, right) => {
      const first = valueForSort(left, column);
      const second = valueForSort(right, column);
      return typeof first === "number" && typeof second === "number"
        ? first - second
        : String(first).localeCompare(String(second), undefined, {numeric:true, sensitivity:"base"});
    };
    const localSort = column => {
      const nextDirection = sortState.key === column.key ? -(Number(sortState.dir) || 1) : 1;
      // The order belongs to the whole list, not to this table's page.
      if (pagedOwner) {
        pagedOwner.sort(column, nextDirection, compareFor(column));
        return;
      }
      const compare = compareFor(column);
      const indexed = (options.rows || []).map((row, index) => ({row, index}));
      indexed.sort((left, right) => {
        const result = compare(left.row, right.row);
        return result ? result * nextDirection : left.index - right.index;
      });
      const replacement = columnList({
        ...options,
        rows: indexed.map(entry => entry.row),
        sortState: {key: column.key, dir: nextDirection},
        idFloor: recordIdWidth,
      });
      // The page fitter measured the list this replaces and set its row height
      // on that node. Sorting swapped in a fresh one, which kept none of it, so
      // the table shrank to its natural height and lost its last row.
      if (root) {
        for (const name of ["--lex-fitted-row-height", "--lex-page-row-count", "--lex-page-font-row-count"]) {
          const value = root.style.getPropertyValue(name);
          if (value) replacement.style.setProperty(name, value);
        }
        for (const key of ["lexFixedRows", "lexFittedPageSize"]) {
          if (root.dataset[key]) replacement.dataset[key] = root.dataset[key];
        }
        if (root.classList.contains("lex-fitted-page")) replacement.classList.add("lex-fitted-page");
        if (root.style.height) replacement.style.height = root.style.height;
      }
      if (root?.parentElement?.lexReplacePanel) root.parentElement.lexReplacePanel(root, replacement);
      else root?.replaceWith(replacement);
      // A local sort replaces the table in place, so anything outside it - the
      // pager summary - only learns of the new order from this event.
      replacement.dispatchEvent(new CustomEvent("lex-column-sorted",
        {bubbles: true, detail: {key: column.key, dir: nextDirection, previous:root}}));
    };
    let suppressSortUntil = 0;
    const pointerColumn = options.pointerColumn ||
      columns.find(column => ["name", "title", "item", "ability", "gf", "enemy", "shop", "weapon", "magic"]
        .includes(String(column.key).toLowerCase()))?.key ||
      columns.find(column => String(column.key).toLowerCase() !== "id")?.key || columns[0]?.key;
    // Origin belongs to the record, so every table paints its pen without a
    // game-specific name renderer. Keep existing source icons supplied by
    // callers, and require the explicit boolean rather than a field's value.
    const sourceColumn = columns.find(column => ["name", "title"].includes(String(column.key).toLowerCase()))?.key
      || columns.find(column => !["enabled", "status"].includes(String(column.key).toLowerCase()))?.key;
    // A list whose rows cannot carry flags - FF8's signature compares the
    // whole row object, so stamping one would mark everything - answers
    // the same question with a predicate instead.
    const rowCreated = row => typeof options.created === "function" ? !!options.created(row) : row?.created === true;
    const rowModified = row => typeof options.modified === "function" ? !!options.modified(row) : row?.modified === true;
    const header = element("div", {
      class: ["lex-column-list-header", options.headerClass || ""].filter(Boolean).join(" "),
      role: "row",
    }, ...columns.map(column => {
      const sortable = canSort(column);
      const active = sortable && sortState.key === column.key;
      // A plain name is the property's name, and reads as the developer last
      // named it, here as in the record's field.
      const labelKey = typeof column.label === "string" && column.label ? fieldLabelKey(column.label) : null;
      const label = element("span", {class: "header-label", ...(labelKey ? {"data-lex-label-key": labelKey} : {})},
        active ? element("span", {
          class: `lex-sort-indicator ${sortState.dir > 0 ? "ascending" : "descending"}`,
          "aria-hidden": "true",
        }, sortState.dir > 0 ? "▲" : "▼") : "",
        // A label may be a factory. One DOM node cannot be in two places, so a
        // node reused across renders or across barrelled tables lands in the
        // last one and leaves the others blank; a factory builds a fresh one.
        typeof column.label === "function" ? column.label()
          : labelKey ? document.createTextNode(savedLabel(labelKey, column.label)) : column.label);  // ascending points up
      const sortControl = sortable
        ? element("button", {
            type: "button", "data-lex-control": "sort",
        class: ["lex-column-sort", active ? "sorted" : ""].filter(Boolean).join(" "),
            title: `Sort by ${typeof column.label === "string" ? column.label : column.key}`,
          }, label)
        : label;
      const help = column.help ? infoHelp(column.help) : null;
      const content = help
        ? element("span", {class: "lex-column-heading"}, sortControl, help)
        : sortControl;
      return bindColumnHighlight(element("div", {
        class: ["lex-column-list-head-cell", sortable ? "lex-column-sortable" : "", active ? "sorted" : "", headerAlignmentClass(column), column.class || ""].filter(Boolean).join(" "),
        role: "columnheader",
        title: column.headerTitle || null,
        draggable: false,
        "data-column-key": column.key,
        "data-lex-id-column": numberedColumn(column) ? "true" : false,
        "aria-sort": active ? (sortState.dir > 0 ? "ascending" : "descending") : "none",
        onclick: event => {
          if (!sortable || event.target.closest(".lex-info-help,.lex-column-pin")) return;
          if (performance.now() < suppressSortUntil) return;
          listResortedAt = performance.now();
          if (typeof options.sort === "function") options.sort(column.key);
          else localSort(column);
        },
        ondragstart: event => {
          event.dataTransfer?.setData("text/plain", column.key);
          if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        },
        ondragover: event => { if (options.columnPreferences) event.preventDefault(); },
        ondrop: event => {
          if (!options.columnPreferences) return;
          event.preventDefault();
          options.columnPreferences.move(event.dataTransfer?.getData("text/plain"), column.key);
        },
      }, content), column.key);
    }));
    if (options.columnPreferences || pinOwner?.move) {
      let drag = null;
      const clearTargets = () => header.querySelectorAll(".drag-target,.dragging")
        .forEach(node => node.classList.remove("drag-target", "dragging"));
      header.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        const cell = event.target.closest(".lex-column-list-head-cell");
        if (!cell || !header.contains(cell)) return;
        drag = {cell, key: cell.dataset.columnKey, startX: event.clientX, startY: event.clientY, moved: false, target: cell};
      });
      header.addEventListener("pointermove", event => {
        if (!drag) return;
        if (!drag.moved && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 7) return;
        if (!drag.moved) {
          try { drag.cell.setPointerCapture?.(event.pointerId); } catch (_error) {}
        }
        drag.moved = true;
        drag.cell.classList.add("dragging");
        const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".lex-column-list-head-cell");
        if (!target || !header.contains(target)) return;
        header.querySelectorAll(".drag-target").forEach(node => node.classList.remove("drag-target"));
        target.classList.add("drag-target");
        drag.target = target;
        event.preventDefault();
      });
      const finishDrag = event => {
        if (!drag) return;
        if (drag.moved) {
          event.preventDefault();
          event.stopPropagation();
          suppressSortUntil = performance.now() + 250;
          if (options.columnPreferences) options.columnPreferences.move(drag.key, drag.target?.dataset.columnKey);
          else if (pinOwner?.move) {
            const strip = key => String(key || "").startsWith("pin:") ? String(key).slice(4) : null;
            const value = strip(drag.key);
            if (value) {
              let before = strip(drag.target?.dataset.columnKey);
              if (before === null) {
                // Dropped on a fixed column: the dragged pin goes to the
                // near end of the pinned run, ahead of it when dropped left.
                const headCells = [...header.querySelectorAll(".lex-column-list-head-cell")];
                const firstPin = headCells.find(cell => String(cell.dataset.columnKey).startsWith("pin:"));
                if (firstPin && headCells.indexOf(drag.target) < headCells.indexOf(drag.cell)) before = strip(firstPin.dataset.columnKey);
              } else {
                // Dropped on a pin it takes that slot: dragged rightward
                // it lands after the target, dragged leftward before it.
                // Always inserting before made a rightward drop a no-op.
                const order = pinOwner.store?.pinned || [];
                const from = order.findIndex(entry => entry.key === value);
                const to = order.findIndex(entry => entry.key === before);
                if (from >= 0 && to >= 0 && from < to) before = (order[to + 1] || {}).key ?? null;
              }
              pinOwner.move(value, before);
            }
          }
        }
        clearTargets();
        drag = null;
      };
      header.addEventListener("pointerup", finishDrag);
      header.addEventListener("pointercancel", finishDrag);
    }
    const root = list({
      rows: options.rows,
      key: options.key || ((row, index) => row.id ?? row.key ?? index),
      selected: options.selected,
      selectedClass: options.selectedClass,
      select: options.select,
      class: ["lex-column-list", options.fill ? "lex-table-fill" : "", options.class || ""].filter(Boolean).join(" "),
      role: "table",
      style: `--lex-column-list-template:${template};--lex-table-row-count:${Math.max(1,options.rows.length)};grid-template-columns:var(--lex-column-list-template)`,
      "aria-label": options["aria-label"],
      "aria-rowcount": options.rows.length + 1,
      // A tiny table whose columns are named by the row beside them - FF8's
      // draw tiers - reads better without a header row.
      header: options.showHeader === false ? undefined : header,
      rowRole: "row",
      rowClass: row => ["lex-column-list-row",
        rowModified(row) ? "lex-record-modified" : "",
        columns.some(column => String(column.key).toLocaleLowerCase() === "enabled") && row?.enabled === false ? "lex-row-disabled" : "",
        typeof options.rowClass === "function" ? options.rowClass(row) : options.rowClass || ""].filter(Boolean).join(" "),
      rowTitle: options.rowTitle,
      decorateRow: options.decorateRow,
      render: row => columns.map(column => {
        const rendered = column.render ? column.render(row) : row[column.key];
        const isNumbered = numberedColumn(column);
        const content = isNumbered
          ? recordId(rendered)
          : (!column.render && typeof rendered === "number"
            ? (column.numeric === true ? magnitudeValue(rendered, magnitudeMetrics.get(column.key) || {}) : numberValue(rendered))
            : rendered);
        const ownClass = typeof column.cellClass === "function" ? column.cellClass(row) : column.cellClass || "";
        const cell = element("div", {
          class: ["lex-column-list-cell",
            // A record that cannot be renamed keeps a plain name cell.
            column.edit && !String(ownClass).split(" ").includes("lex-cell-fixed") ? "lex-cell-editable" : "",
            column.key === pointerColumn ? "lex-column-pointer-cell" : "",
            isNumbered ? "lex-numbered-id-cell" : "",
            column.numeric === true ? "lex-numeric-cell" : "",
            alignmentClass(column),
            ownClass].filter(Boolean).join(" "),
          role: "cell",
          "data-column-key": column.key,
        // A bare string handed straight to the flex content span cannot be
        // ellipsised: text-overflow does nothing on a flex container, so a long
        // value was hard-cut mid-character. Wrapping plain text in its own
        // block gives the existing single-line truncation something to act on,
        // and the title keeps the full value reachable.
        }, element("span", {class: "lex-column-cell-content"},
          (typeof content === "string" || typeof content === "number")
            ? element("span", {class: "lex-column-cell-text", title: String(content)}, String(content))
            : content));
        if (rowCreated(row) && column.key === sourceColumn &&
            !cell.querySelector(".lex-record-source")) {
          const value = cell.querySelector(".lex-column-cell-content");
          value.replaceChildren(inlineLabel(recordSource({created:true}), ...value.childNodes));
        }
        if (rowModified(row) && !rowCreated(row) && column.key === sourceColumn &&
            !cell.querySelector(".lex-record-source")) {
          const value = cell.querySelector(".lex-column-cell-content");
          value.replaceChildren(inlineLabel(recordSource({modified:true}), ...value.childNodes));
        }
        // The double-click is caught once, at the document: a list whose
        // click selects the row re-renders between the two clicks, so the
        // cell the double-click lands on is a new one, not the first.
        if (column.edit) {
          cell.lexBeginEdit = () => beginCellEdit(cell, column, row, options.refresh);
          // A table that stays put between clicks gets the browser's own
          // double-click; the counted one covers a table that re-rendered.
          cell.addEventListener("dblclick", event => {
            event.preventDefault();
            if (!document.querySelector(".lex-cell-editing")) cell.lexBeginEdit();
          });
        }
        return cell;
      }),
    });
    root.lexHeadingTemplate = template;
    root.lexHeadingKey = JSON.stringify([template, options.class, header.textContent]);
    const cachedHeadingTemplate = columnHeadingWidths.get(root.lexHeadingKey);
    if (cachedHeadingTemplate) root.style.setProperty("--lex-column-list-template", cachedHeadingTemplate);
    // An edit repaints its pinned cells in place. The rows array is shared
    // with the plugin, so patched values show without rebuilding the table,
    // which would steal focus from whatever is edited next.
    const pinnedRefresh = new Map(columns
      .filter(column => typeof column?.pinnedProperty === "string" && typeof column?.render === "function")
      .map(column => [column.key, column]));
    root.refreshValues = () => {
      if (!pinnedRefresh.size) return;
      const listKeyOf = options.key || ((row, index) => row.id ?? row.key ?? index);
      const records = new Map((options.rows || []).map((row, index) => [String(listKeyOf(row, index)), row]));
      for (const row of root.querySelectorAll(".lex-column-list-row[data-key]")) {
        const record = records.get(row.dataset.key);
        if (!record) continue;
        for (const cell of row.querySelectorAll(':scope > .lex-column-list-cell[data-column-key^="pin:"]')) {
          const column = pinnedRefresh.get(cell.dataset.columnKey);
          const text = cell.querySelector(":scope > .lex-column-cell-content > .lex-column-cell-text");
          if (!column || !text || cell.classList.contains("lex-cell-editing")) continue;
          const shown = column.render(record);
          text.textContent = shown;
          text.title = String(shown);
        }
      }
    };
    fitColumnHeadings(root);
    document.fonts?.ready.then(() => fitColumnHeadings(root));
    return root;
  };

  // A matrix keeps the column-list controls and sizing, with one name/help
  // for each axis. The first column identifies rows; remaining columns are
  // values of the column axis. Axis order is fixed rather than locally sorted.
  const matrixTable = options => {
    const {rowAxis, columnAxis} = options;
    const root = columnList({...options, fill: options.fill !== false, localSort:false,
      class: ["lex-matrix-table", options.class || ""].join(" "),
      columns:[{...rowAxis, label:"", help:null}, ...options.columns]
        .map(column => ({...column, sortable:false}))});
    root.style.gridTemplateColumns = "max-content var(--lex-column-list-template)";
    root.setAttribute("aria-rowcount", options.rows.length + 2);
    const axisLabel = axis => element("span", {class:"lex-matrix-axis-label"},
      element("span", {class:"lex-matrix-axis-text"}, axis.label),
      axis.help ? infoHelp(axis.help) : null);
    const columnHeading = element("div", {
      class:"lex-matrix-column-axis lex-column-list-header", role:"row",
    }, element("div", {class:"lex-column-list-head-cell", role:"columnheader",
      "aria-colindex":2, "aria-colspan":options.columns.length}, axisLabel(columnAxis)));
    const rowHeading = element("div", {
      class:"lex-matrix-row-axis", role:"presentation",
    }, axisLabel(rowAxis));
    const header = root.querySelector(".lex-column-list-header");
    header.firstElementChild.setAttribute("aria-label", rowAxis.label);
    root.querySelectorAll(".lex-column-list-row").forEach((row, index) => {
      row.style.gridRow = String(index + 3);
      row.firstElementChild.setAttribute("role", "rowheader");
      row.firstElementChild.setAttribute("aria-label", `${rowAxis.label} ${row.firstElementChild.textContent.trim()}`);
    });
    root.prepend(columnHeading, rowHeading);
    return root;
  };

  const normalizedPanelSizes = (values, count) => {
    const sizes = Array.from({length: count}, (_, index) => {
      const value = Number(values?.[index]);
      return Number.isFinite(value) && value > 0 ? value : 1;
    });
    const total = sizes.reduce((sum, value) => sum + value, 0) || count;
    return sizes.map(value => value / total * 100);
  };

  // A layout composes panel archetypes. Every pair of sibling panels receives
  // the same resize controller; games never create divider markup or behavior.
  const panelLayout = (panels, className = "", layoutOptions = {}) => {
    if (className && typeof className === "object") {
      layoutOptions = className;
      className = "";
    }
    const options = layoutOptions || {};
    const nodes = (Array.isArray(panels) ? panels : [panels]).filter(Boolean);
    const vertical = String(options.orientation || "").toLowerCase() === "vertical";
    const root = element("div", {
      class: `lex-panel-layout ${vertical ? "lex-panel-layout-vertical " : ""}${className}`.trim(),
    });
    const stackAt = [700, 850, 1000, 1100].includes(Number(options.stackAt))
      ? Number(options.stackAt) : 850;
    root.classList.add(`lex-panel-layout-stack-${stackAt}`);
    nodes.forEach(node => {
      node.classList?.add("lex-panel-layout-pane");
      if (options.paneClass) node.classList?.add(options.paneClass);
    });
    // Selection replaces a detail pane without rebuilding its layout. Keep
    // the resize controller pointed at the mounted replacement, not the old
    // detached node (whose measured width and height are both zero).
    root.lexReplacePanel = (current, replacement) => {
      const index = nodes.indexOf(current);
      if (index < 0) throw new Error("The replaced panel does not belong to this layout.");
      replacement.classList.add("lex-panel-layout-pane");
      if (options.paneClass) replacement.classList.add(options.paneClass);
      nodes[index] = replacement;
      current.replaceWith(replacement);
    };
    let minimumFractions = Array.from({length: nodes.length}, (_, index) =>
      Math.max(0, Math.min(.95, Number(options.minimumFractions?.[index]) || 0)));
    const minimumTotal = minimumFractions.reduce((sum, value) => sum + value, 0);
    if (minimumTotal > .95) {
      minimumFractions = minimumFractions.map(value => value / minimumTotal * .95);
    }
    const sizesWithMinimums = values => {
      const normalized = normalizedPanelSizes(values, nodes.length);
      const minimums = minimumFractions.map(value => value * 100);
      const available = Math.max(0, 100 - minimums.reduce((sum, value) => sum + value, 0));
      const weights = normalized.map((value, index) => Math.max(0, value - minimums[index]));
      const weightTotal = weights.reduce((sum, value) => sum + value, 0);
      if (!weightTotal) return minimums.map((value, index) =>
        value + available / Math.max(1, minimums.length));
      return minimums.map((value, index) => value + available * weights[index] / weightTotal);
    };
    const defaults = sizesWithMinimums(options.defaultSizes);
    let sizes = [...defaults];
    const template = (current, dividers = true) => current.flatMap((value, index) =>
      index < current.length - 1 && dividers
        ? [`minmax(${minSizes[index]}px, ${value}fr)`, "var(--lex-panel-gap, 14px)"]
        : [`minmax(${minSizes[index]}px, ${value}fr)`]).join(" ");
    const minSizes = Array.from({length: nodes.length}, (_, index) =>
      Math.max(80, Number(options.minSizes?.[index]) || 240));
    const configuredMinSizes=[...minSizes];
    if (!vertical) root.style.setProperty('--lex-panel-stack-min', `${Math.max(0, ...minSizes)}px`);
    let belowMinimum = false, measuredGap = 14;
    // Every side-by-side layout keeps its panes at their minimum widths, from
    // the first draw on, not only the ones that stack when room runs out: a
    // three-pane page at 1100px squeezed its detail to 350px of a 430px
    // minimum while its other panes kept more than theirs (Enemies > Loot).
    // A pane holding a table is at least as wide as the table's own columns
    // at their minimum, so a header is never cut off by its pane. The width
    // is the table's real minimum, not its current width, so the pane can
    // always shrink back to it; side-by-side barrels add up.
    const tableMinimum = node => {
      let widest = 0;
      const grids = new Map();
      for (const list of node.querySelectorAll(".lex-column-list")) {
        if (list.closest(".lex-detail-panel") || !list.offsetParent) continue;
        const grid = list.closest(".lex-barrel-grid") || list;
        if (!grids.has(grid)) grids.set(grid, []);
        grids.get(grid).push(list);
      }
      for (const [grid, lists] of grids) {
        const chrome = node.getBoundingClientRect().width - grid.getBoundingClientRect().width;
        let need = 0;
        for (const list of lists) {
          const before = list.style.width;
          list.style.width = "min-content";
          need += list.getBoundingClientRect().width;
          list.style.width = before;
        }
        need += 7 * (lists.length - 1);
        widest = Math.max(widest, Math.ceil(need + Math.max(0, chrome)));
      }
      return widest;
    };
    // Barrels ask for their content width from the spare room: the floor
    // above keeps headers readable, but names truncated while the detail
    // pane sat empty (Textures at two barrels) need the full width asked,
    // not floored. Summed from the measured columns: a max-content probe of
    // the whole list under-measures once three tracks share it.
    const barrelContentWant = node => {
      const grids = [...node.querySelectorAll(".lex-barrel-grid")]
        .filter(grid => !grid.closest(".lex-detail-panel") && grid.offsetParent);
      if (!grids.length) return 0;
      let want = 0;
      for (const grid of grids) {
        const chrome = Math.max(0,
          node.getBoundingClientRect().width - grid.getBoundingClientRect().width);
        // Measured fresh: a cached width goes stale the moment an edit or
        // a pin changes what the cells hold. Reads only, no probing writes.
        const measured = measureBarrelColumnWidths(grid);
        if (!measured) continue;
        want = Math.max(want, chrome
          + measured.lists.length * (measured.widths.reduce((sum, width) => sum + width, 0) + measured.pad)
          + 7 * (measured.lists.length - 1));
      }
      return Math.ceil(want);
    };
    const updateResponsive = () => {
      const extent = vertical ? root.clientHeight : root.clientWidth;
      const css = getComputedStyle(root);
      const divider = root.querySelector(':scope > .lex-panel-layout-divider');
      const dividerSize = vertical ? divider?.offsetHeight : divider?.offsetWidth;
      if (dividerSize) measuredGap = dividerSize;
      const available = extent - (parseFloat(vertical ? css.paddingTop : css.paddingLeft) || 0)
        - (parseFloat(vertical ? css.paddingBottom : css.paddingRight) || 0) - measuredGap * (nodes.length - 1);
      if(!vertical&&root.isConnected){
        // A table's columns and the configured minimum are hard floors. Room
        // for a whole word in the label lane is only asked for from the space
        // that is left: at 1280px a detail pane wanting 1020px for "Dependent"
        // pushed the page into a sideways scroll (Bannerlord > Dependencies),
        // where the label fit already shrinks a long name instead.
        const hard=nodes.map((node,index)=>Math.max(configuredMinSizes[index],tableMinimum(node)));
        const wanted=nodes.map((node,index)=>Math.max(0,Math.max(readablePropertyWidth([node],9),barrelContentWant(node))-hard[index]));
        const asked=wanted.reduce((sum,value)=>sum+value,0);
        const spare=Math.max(0,(extent?available:Infinity)-hard.reduce((sum,value)=>sum+value,0));
        // A layout that stacks below its minimum stacks instead of squeezing.
        const granted=options.stackBelowMinimum||asked<=spare?1:spare/asked;
        nodes.forEach((_node,index)=>minSizes[index]=Math.floor(hard[index]+wanted[index]*granted));
        root.style.setProperty('--lex-panel-stack-min',`${Math.max(...minSizes)}px`);
      }
      if (!extent) return 0;
      const least = minSizes.reduce((sum, value) => sum + value, 0);
      root.classList.toggle('lex-panel-layout-overflow', available <
        (!vertical && options.stackBelowMinimum ? Math.max(...minSizes) : least));
      if (vertical || !options.stackBelowMinimum) return available;
      belowMinimum = available < minSizes.reduce((sum, value) => sum + value, 0);
      root.classList.toggle('lex-panel-layout-below-minimum', belowMinimum);
      root.style.setProperty('--lex-panel-count', nodes.length);
      return belowMinimum ? 0 : available;
    };
    const fitResponsiveSizes = available => {
      const least=minSizes.reduce((sum,value)=>sum+value,0);
      // The grid keeps its declared track minima when they cannot fit. The
      // container scrolls (or stacks), rather than quietly reducing the floor.
      if (available && available < least) return null;
      if (!available || !sizes.some((value,index)=>value*available/100<minSizes[index]-.5)) return null;
      const spare=available-minSizes.reduce((sum,value)=>sum+value,0);
      const weights=sizes.map((value,index)=>Math.max(0,value*available/100-minSizes[index]));
      const total=weights.reduce((sum,value)=>sum+value,0);
      return minSizes.map((value,index)=>value+spare*(total?weights[index]/total:1/nodes.length));
    };

    // Divider positions are never dragged or saved: every layout takes its
    // configured shares clamped to measured minimums, refit as room changes.
    // The strips between panes only anchor divider accessories (the shared
    // Barrels and Columns buttons). They take no input.
    root.classList.add("lex-panel-layout-static");
    root.style.setProperty("--lex-panel-layout-template", template(sizes));
    const accessories = options.dividerAccessories || [];
    const strips = Array.from({length: Math.max(0, nodes.length - 1)}, (_, index) => {
      const strip = element("div", {class: "lex-panel-layout-divider"});
      if (options.dividerClass) strip.classList.add(options.dividerClass);
      [accessories[index]].flat().filter(Boolean).forEach(node => strip.append(node));
      // The Barrels/Columns gizmos meet the cursor where it hovers instead of
      // waiting at the divider's middle: every summoning puts them under the
      // eye that asked. Centered on the cursor, clamped to the strip so they
      // never hang past its ends. (Horizontal dividers keep centered gizmos.)
      // A gizmo hangs rotated a quarter turn, so its visual height is its
      // layout width.
      if (!vertical) strip.addEventListener("pointermove", event => {
        // Under the cursor it holds still: moving while hovered would slide
        // its buttons out from under the click that summoned them.
        if (event.target.closest?.(".lex-barrel-control")) return;
        const gizmos = strip.querySelectorAll(":scope > .lex-barrel-control");
        if (!gizmos.length || !strip.clientHeight) return;
        const at = event.clientY - strip.getBoundingClientRect().top;
        for (const gizmo of gizmos) {
          const half = gizmo.offsetWidth / 2;
          const top = half * 2 >= strip.clientHeight ? strip.clientHeight / 2
            : Math.min(strip.clientHeight - half, Math.max(half, at));
          const was = parseFloat(gizmo.style.top);
          if (!Number.isFinite(was) || Math.abs(was - top) > 0.5) gizmo.style.top = `${top}px`;
        }
      });
      return strip;
    });
    nodes.forEach((node, index) => {
      root.append(node);
      if (index < strips.length) root.append(strips[index]);
    });
    const refreshResponsive = () => {
      const fitted = fitResponsiveSizes(updateResponsive());
      // The fitted pixel shares render but never persist: persisting them
      // rewrote the configured split (32/68 narrowed to 44/56), and the
      // widened window never violated a minimum again, so panes froze
      // narrow with their labels shrunk for the narrow room.
      root.style.setProperty('--lex-panel-layout-template',
        template(fitted ? sizesWithMinimums(fitted) : sizes));
    };
    refreshResponsive();
    if (typeof ResizeObserver !== "undefined") {
      let pending = 0;
      const observer = new ResizeObserver(() => {
        if (pending) cancelAnimationFrame(pending);
        pending = requestAnimationFrame(() => {
          pending = 0;
          refreshResponsive();
        });
      });
      observer.observe(root);
      root.__lexPanelLayoutObserver = observer;
    }
    requestAnimationFrame(() => {
      refreshResponsive();
      document.fonts?.ready.then(() => {labelWidths.clear();if(root.isConnected)refreshResponsive();});
    });
    root.refreshLayout = () => { if (root.isConnected) refreshResponsive(); };
    // Pins change what the master must hold: re-derive the shares from the
    // defaults instead of keeping shares the old columns needed, or the
    // master keeps room its columns no longer fill after an unpin.
    root.lexResetSizes = () => { sizes = [...defaults]; if (root.isConnected) refreshResponsive(); };
    return root;
  };

  // Compatibility wrapper for older callers. Sizes always come from panelLayout.
  const listDetail = (listNode, detail, className = "", splitOptions = {}) => {
    if (className && typeof className === "object") {
      splitOptions = className;
      className = "";
    }
    const options = splitOptions || {};
    const defaultSplit = Math.max(20, Math.min(80, Number(options.defaultSplit) || 42));
    const minimumSplit = Math.max(0, Math.min(90, Number(options.minimumSplit) || 0));
    const root = panelLayout([listNode, detail],
      `lex-list-detail lex-master-detail ${className}`.trim(), {
        defaultSizes: [defaultSplit, 100 - defaultSplit],
        minSizes: [Math.max(160, Number(options.minLeft) || 280),
          Math.max(240, Number(options.minRight) || 360)],
        minimumFractions: [minimumSplit / 100, 0],
        dividerClass: "lex-list-detail-divider",
        dividerAccessories: options.dividerAccessories,
        paneClass: options.paneClass,
      });
    root.__lexListDetailObserver = root.__lexPanelLayoutObserver;
    return root;
  };
  const masterDetail = listDetail;

  // Fit a paged list to complete rendered rows. The caller owns the records and
  // pagination state; this shared measurement owns only visible capacity.
  const fittedPageGeometry = new Map();
  const fitListPage = options => {
    const listNode = options.list;
    if (!listNode) return null;
    const availableNode = options.available || listNode;
    listNode.classList.add("lex-fitted-page");
    let frame = 0;
    const fixedRows = Math.max(0, Number(options.fixedRows) || 0);
    const fittedLists = (options.lists || [listNode]).filter(Boolean);
    let lastSize = Math.max(1, Number(options.pageSize) || 1);
    let waitingForDrag = false;
    const geometryKey = options.cacheKey ? `${options.cacheKey}:${innerWidth}:${innerHeight}:${fixedRows}:${options.minRowHeight||0}` : null;
    const cachedGeometry = geometryKey && fittedPageGeometry.get(geometryKey);
    if (cachedGeometry) {
      fittedLists.forEach(node => {
        node.style.setProperty("--lex-fitted-row-height", `${cachedGeometry.rowHeight}px`);
        node.dataset.lexFixedRows = String(cachedGeometry.pageSize);
      });
      options.resize?.(cachedGeometry.height, cachedGeometry);
    }
    let lastStability = "", lastStableGeometry = null;
    const measure = () => {
      frame = 0;
      if (!listNode.isConnected) return;
      if (document.body.classList.contains("lex-panel-layout-dragging")) {
        if (!waitingForDrag) {
          waitingForDrag = true;
          document.addEventListener("lex-panel-drag-ended", () => {waitingForDrag=false;schedule();}, {once:true});
        }
        return;
      }
      const header = listNode.querySelector(options.headerSelector || ".lex-column-list-header, .loot-listhead, .rdr-listhead") ||
        (listNode.firstElementChild?.classList.contains("lex-list-row") ? null : listNode.firstElementChild);
      const rows = [...listNode.querySelectorAll(options.rowSelector || ".lex-list-row")];
      if (!rows.length) return;
      // Same rows, same space, same answer. Re-sorting a column rebuilds the
      // rows, and measuring the rebuilt ones handed back a different row height
      // each time, so the table changed size when you sorted it.
      const ownerRect = availableNode.getBoundingClientRect();
      const scale = ownerRect.height / availableNode.offsetHeight || 1;
      const pagerNode = availableNode.querySelector?.(":scope > .lex-pager");
      const pagerInFlow = pagerNode && getComputedStyle(pagerNode).position !== "fixed";
      const visibleBottom = Math.min(ownerRect.bottom, innerHeight,
        pagerNode && !pagerInFlow ? pagerNode.getBoundingClientRect().top : Infinity);
      const availableHeight = Math.max(0, Math.min(availableNode.clientHeight,
        (visibleBottom - ownerRect.top) / scale) -
        (pagerInFlow ? pagerNode.getBoundingClientRect().height / scale : 0));
      const stability = `${rows.length}:${availableHeight.toFixed(2)}:${Math.round(listNode.clientWidth)}`;
      if (lastStability === stability && lastStableGeometry) {
        options.resize?.(lastStableGeometry.height, lastStableGeometry);
        return;
      }
      // A paged view can set one real CSS row height for content whose icons or
      // glyphs otherwise alter the line box. That keeps capacity independent
      // of the page being displayed. Measuring only the current page can make
      // two pages choose different sizes and repeatedly navigate into each
      // other. Views without a fixed row contract still use the rendered row.
      const configuredRowHeight = parseFloat(
        getComputedStyle(listNode).getPropertyValue("--lex-fitted-row-height")
      );
      const measuredRowHeight = rows[0].getBoundingClientRect().height / scale;
      const naturalRowHeight = configuredRowHeight > 0 ? configuredRowHeight : measuredRowHeight;
      if (!(naturalRowHeight > 0) || !(availableNode.clientHeight > 0)) return;
      const headerHeight = (header?.getBoundingClientRect().height || 0) / scale;
      const listStyle = getComputedStyle(listNode);
      const borderHeight = (parseFloat(listStyle.borderTopWidth) || 0) +
        (parseFloat(listStyle.borderBottomWidth) || 0);
      // Fit to the visible intersection. Some callers reserve fixed-pager
      // space already; others do not. Never assume either layout.
      const available = Math.max(0, availableHeight - borderHeight - headerHeight);
      const minimumRowHeight = Math.max(0, Number(options.minRowHeight) || 0);
      const capacity = minimumRowHeight > 0 ? Math.max(1, Math.floor((available - 0.5) / minimumRowHeight)) : Infinity;
      // Stretched rows report the track height, which shrinks as the count
      // grows: fitting from it counts down to one row. A fixed row contract
      // fits from the assumed height instead, which depends only on space.
      const assumedRowHeight = Math.max(0, Number(options.fixedRowHeight) || 0);
      const measuredCapacity = assumedRowHeight > 0
        ? Math.max(1, Math.floor((available - 0.5) / assumedRowHeight))
        : Math.max(1, Math.floor((available - 0.5) / naturalRowHeight));
      const pageSize = fixedRows || Math.min(measuredCapacity, capacity);
      // An explicit row count squeezes rows to fit: paginated content never
      // scrolls, so a high count shrinks rows instead of adding a scrollbar.
      const rowHeight = fixedRows ? available / pageSize : naturalRowHeight;
      if (!(rowHeight > 0)) return;
      if (fixedRows) fittedLists.forEach(node => {
        node.style.setProperty("--lex-fitted-row-height", `${rowHeight}px`);
        node.dataset.lexFixedRows = String(pageSize);
        node.style.overflowY = "";
      });
      listNode.dataset.lexFittedPageSize = String(pageSize);
      const requestedVisibleRows = typeof options.visibleRows === "function"
        ? options.visibleRows() : options.visibleRows;
      const visibleRows = Math.max(1, Math.min(pageSize,
        Number(requestedVisibleRows) || pageSize));
      const full = visibleRows >= pageSize;
      const fittedHeight = full ? availableHeight :
        Math.ceil(borderHeight + headerHeight + visibleRows * rowHeight);
      const geometry = {full, pageSize, visibleRows, rowHeight, height:fittedHeight};
      lastStability = stability;
      lastStableGeometry = geometry;
      if (geometryKey && fixedRows) fittedPageGeometry.set(geometryKey, geometry);
      options.resize?.(fittedHeight, geometry);
      if ((!fixedRows || minimumRowHeight > 0) && pageSize !== lastSize) {
        lastSize = pageSize;
        options.change?.(pageSize);
      }
    };
    const schedule = () => {
      // The pager is already in the DOM when fitListPage is called. Measure on
      // the next quiet pair of frames immediately, then measure once more when
      // web fonts settle. Waiting for fonts before the FIRST fit left some
      // pages scrollable or at the wrong row count during normal startup.
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(measure);
      });
    };
    schedule();
    document.fonts?.ready?.then(schedule).catch(() => {});
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(schedule);
      observer.observe(availableNode);
      const firstRow = listNode.querySelector(options.rowSelector || ".lex-list-row");
      if (firstRow) observer.observe(firstRow);
      listNode.__lexFitListObserver = observer;
    } else {
      window.addEventListener("resize", schedule);
    }
    return listNode;
  };

  const selectionIcon = () => {
    const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");
    for(const [key,value] of Object.entries({viewBox:"0 0 24 24","aria-hidden":"true",fill:"none",stroke:"currentColor","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round"}))svg.setAttribute(key,value);
    const path=document.createElementNS(ns,"path");
    path.setAttribute("d","M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4");
    svg.append(path);return svg;
  };
  const searchIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    const circle = document.createElementNS(namespace, "circle");
    circle.setAttribute("cx", "10.5"); circle.setAttribute("cy", "10.5"); circle.setAttribute("r", "6.5");
    const handle = document.createElementNS(namespace, "path");
    handle.setAttribute("d", "m15.5 15.5 5 5");
    svg.append(circle, handle);
    return svg;
  };

  // A magnifier with a plus: the control that opens a map at full size.
  const magnifyIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    const circle = document.createElementNS(namespace, "circle");
    circle.setAttribute("cx", "10.5"); circle.setAttribute("cy", "10.5"); circle.setAttribute("r", "6.5");
    const handle = document.createElementNS(namespace, "path");
    handle.setAttribute("d", "m15.5 15.5 5 5");
    const plus = document.createElementNS(namespace, "path");
    plus.setAttribute("d", "M10.5 7.5v6M7.5 10.5h6");
    svg.append(circle, handle, plus);
    return svg;
  };

  let activeSearcher = null;
  const lockSearcherTarget = searcher => {
    searcher.targetLocks ||= new Map();
    if (activeSearcher !== searcher || !searcher.atTarget) {
      for (const [node, inert] of searcher.targetLocks) node.inert = inert;
      searcher.targetLocks.clear();
      return;
    }
    // Browsing and filtering candidates stays live; their editable details
    // and record actions must not change data during replacement selection.
    for (const node of document.querySelectorAll(
      "#main .lex-detail-field,#main .lex-detail-panel-actions,#main .lex-table-add," +
      "#main input,#main select,#main textarea,#main [contenteditable='true'],#global-save,#global-undo,#global-redo")) {
      if (node.matches("input,select,textarea,[contenteditable='true']") &&
          (node.matches("input[type='search']") || node.closest(READONLY_EXEMPT))) continue;
      if (!searcher.targetLocks.has(node)) searcher.targetLocks.set(node, node.inert);
      node.inert = true;
    }
    for (const [node, inert] of searcher.targetLocks) if (!node.isConnected) {
      node.inert = inert;
      searcher.targetLocks.delete(node);
    }
  };
  document.addEventListener("keydown", event => {
    if (activeSearcher && (event.ctrlKey || event.metaKey) && ["s","z","y"].includes(event.key.toLowerCase())) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  const lockSearcherSource = (searcher, locked) => {
    for (const [node, inert] of searcher.sourceLocks || []) node.inert = inert;
    searcher.sourceLocks = [];
    document.body.classList.toggle("lex-searcher-source", locked);
    if (locked) for (const node of document.querySelectorAll("#main,#toolbar,.lex-shell-left-actions,.lex-shell-center-actions")) {
      searcher.sourceLocks.push([node, node.inert]);
      node.inert = true;
    }
  };
  const finishSearcher = (navigateOrigin = true) => {
    if (!activeSearcher) return;
    const searcher = activeSearcher;
    activeSearcher = null;
    searcher.targetObserver?.disconnect();
    searcher.layoutObserver?.disconnect();
    cancelAnimationFrame(searcher.layoutFrame);
    window.removeEventListener("resize", searcher.scheduleLayout);
    for (const [node, inert] of searcher.tabLocks || []) node.inert = inert;
    lockSearcherTarget(searcher);
    lockSearcherSource(searcher, false);
    searcher.header?.classList.remove("lex-searcher-active");
    searcher.bar?.remove();
    if (navigateOrigin) searcher.origin?.();
    window.dispatchEvent(new CustomEvent("lexeditor-searcher-changed", {detail: {active: false}}));
  };
  const selectionBar = (options = {}) => {
    const context=element("button",{type:"button",class:"lex-searcher-context",title:options.contextLabel||"Show the source record",
      "aria-label":options.contextLabel||null},searchIcon());
    const prompt=element("strong",{class:"lex-searcher-prompt"},options.prompt||"Select a record");
    const cancel=element("button",{type:"button",class:"lex-searcher-cancel",title:options.closeLabel||"Cancel selection",
      "aria-label":options.closeLabel||"Cancel selection"},"×");
    const clear=options.clearValue === undefined ? null : element("button",{type:"button",class:"lex-searcher-clear",
      title:options.clearTitle||`Clear the selection (${options.clearLabel||"None"})`,
      "aria-label":options.clearLabel||"None"},options.clearLabel||"None");
    const bar=element("div",{class:"lex-searcher-bar",role:"status","aria-live":"polite"},context,prompt,clear,cancel);
    return {context,prompt,cancel,clear,bar};
  };
  const beginSearcher = options => {
    finishSearcher(false);
    const header = document.querySelector(".lex-shell-header");
    if (!header?.querySelector(".lex-nav-frame")) throw new Error("The shared Searcher needs the Lexeditor shell");
    const {context,prompt,cancel,clear,bar}=selectionBar(options);
    const searcher = {
      type: String(options.type || "record"), accept: options.accept, origin: options.origin,
      target: options.target, bar, header, atTarget: true,
      holdMs: Math.max(150, Math.min(2000, Number(options.holdMs || sharedSettingsSnapshot?.selectionHoldMs || 650))),
    };
    activeSearcher = searcher;
    searcher.tabLocks = new Map();
    const fitBar = () => {
      if (activeSearcher !== searcher) return;
      const nav = header.querySelector(".lex-nav-frame");
      const bounds = nav.getBoundingClientRect();
      const scale = bounds.height / nav.offsetHeight || 1;
      let bottom = bounds.bottom;
      const tabs = [...document.querySelectorAll("#toolbar .lex-subtab-bar,#main .lex-subtab-bar")]
        .filter(node => !node.closest(".lex-detail-panel,.lex-tabbed-panel") && !node.querySelector('.lex-search-candidate') && node.getClientRects().length)
        .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      const covered = new Set();
      for (const node of tabs) {
        const box = node.getBoundingClientRect();
        // Only page navigation directly below the header, never panel tabs.
        if (box.height && box.top >= bounds.bottom - 1 && box.top <= bottom + 32 * scale &&
            box.width >= bounds.width * .8) {
          bottom = Math.max(bottom, box.bottom);
          covered.add(node);
          if (!searcher.tabLocks.has(node)) {
            searcher.tabLocks.set(node, node.inert);
            searcher.layoutObserver.observe(node);
          }
          node.inert = true;
        }
      }
      for (const [node, inert] of searcher.tabLocks) if (!covered.has(node)) {
        node.inert = inert;
        searcher.tabLocks.delete(node);
        searcher.layoutObserver.unobserve(node);
      }
      bar.style.setProperty("--lex-searcher-height", `${(bottom - bounds.top) / scale}px`);
    };
    searcher.scheduleLayout = () => {
      cancelAnimationFrame(searcher.layoutFrame);
      searcher.layoutFrame = requestAnimationFrame(fitBar);
    };
    searcher.layoutObserver = new ResizeObserver(searcher.scheduleLayout);
    searcher.layoutObserver.observe(header);
    window.addEventListener("resize", searcher.scheduleLayout);
    searcher.targetObserver = new MutationObserver(() => {
      lockSearcherTarget(searcher);
      searcher.scheduleLayout();
    });
    searcher.targetObserver.observe(document.body, {childList:true, subtree:true});
    context.onclick = () => {
      if (searcher.atTarget) {
        searcher.atTarget = false;
        lockSearcherTarget(searcher);
        context.replaceChildren(element("span", {class: "lex-searcher-return lex-ui-symbol", "aria-hidden": "true"}, "↩"));
        context.title = "Return to selection results";
        context.classList.add("returning");
        prompt.replaceChildren("Click the ", element("span", {class:"lex-searcher-return-prompt"}, "blue return button"),
          ` to ${options.prompt || "select a record"}`);
        lockSearcherSource(searcher, true);
        Promise.resolve(searcher.origin?.()).then(() => {
          if (activeSearcher === searcher && !searcher.atTarget) lockSearcherSource(searcher, true);
        });
      } else {
        searcher.atTarget = true;
        lockSearcherSource(searcher, false);
        context.classList.remove("returning");
        prompt.textContent = options.prompt || "Select a record";
        context.replaceChildren(searchIcon());
        context.title = "Show the source record";
        searcher.target?.();
        lockSearcherTarget(searcher);
      }
    };
    cancel.onclick = () => finishSearcher(true);
    if (clear) clear.onclick = () => {
      const accept = searcher.accept;
      finishSearcher(false);
      accept?.(options.clearValue, options.clearLabel || "None");
      searcher.origin?.();
    };
    header.classList.add("lex-searcher-active");
    header.append(bar);
    searcher.target?.();
    lockSearcherTarget(searcher);
    fitBar();
    window.dispatchEvent(new CustomEvent("lexeditor-searcher-changed", {detail: {active: true, type: searcher.type}}));
    return searcher;
  };
  const decorateSearchCandidate = (node, options) => {
    const searcher = activeSearcher;
    if (!searcher || searcher.type !== String(options.type || "record")) return node;
    node.classList.add("lex-search-candidate");
    node.style.setProperty("--lex-search-hold", `${searcher.holdMs}ms`);
    // A hold picks the candidate; a plain click does what it always does -
    // select the row and show it in the detail panel - so the player can look
    // inside a candidate before choosing it (Lexer, FF8 encounter groups).
    let timer = 0, held = false;
    const cancel = () => {
      clearTimeout(timer); timer = 0; node.classList.remove("selecting");
    };
    node.addEventListener("pointerdown", event => {
      if (event.button !== 0 || !searcher.atTarget || activeSearcher !== searcher) return;
      event.preventDefault();
      node.setPointerCapture?.(event.pointerId);
      node.classList.add("selecting");
      timer = setTimeout(() => {
        timer = 0;
        held = true;
        node.classList.remove("selecting");
        if (activeSearcher !== searcher || !searcher.atTarget) return;
        const accept = searcher.accept;
        finishSearcher(false);
        accept?.(options.value, options.label);
        searcher.origin?.();
      }, searcher.holdMs);
    });
    for (const type of ["pointerup", "pointercancel", "pointerleave"]) node.addEventListener(type, cancel);
    node.addEventListener("click", event => {
      if (!held) return;
      held = false;
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);
    return node;
  };

  // THE thing finder: FF8's hold-to-choose record picker, shared by every
  // game. The button opens the shared Searcher: the prompt reads up top in
  // the menu bar's place (which goes inert behind it), the magnifier goes
  // back to the source record, and holding a candidate chooses it while a
  // plain click only looks inside it. thingFinderField pairs the button
  // with the linked value it changes: a hoverable plus this button is the
  // standard linked-record control.
  const thingFinderButton = (options = {}) => element("button", {
    type: "button",
    class: ["lex-thing-finder", options.content ? "lex-thing-finder-custom" : "", options.class || ""].filter(Boolean).join(" "),
    title: options.title || options.label || "Choose a record",
    "aria-label": options.label || options.title || "Choose a record",
    disabled: options.disabled === true,
    onclick: event => { event.preventDefault(); event.stopPropagation();
      beginSearcher({type: options.type, prompt: options.prompt, target: options.target,
        origin: options.origin, accept: options.accept, holdMs: options.holdMs,
        clearValue: options.clearValue, clearLabel: options.clearLabel,
        clearTitle: options.clearTitle}); },
  }, options.content || selectionIcon());
  const thingFinderField = (content, options = {}) => choiceField(content, thingFinderButton(options), options);

  const bottomSearchChangeTimers = new Map();
  let typingSearch = null;
  // Keystrokes stay adoptable for a second: a delayed search (FF8's 110ms)
  // races its rebuilds within milliseconds, while a query carried from
  // another tab under a reused key is long stale. Without this, navigating
  // away leaked the old tab's query into the new tab's box and filtered
  // its list to nothing.
  const BOTTOM_SEARCH_ADOPT_MS = 1000;
  const bottomSearch = options => {
    const key = String(options.key || options.label || "records");
    let composing = false;
    const control = element("input", {
      type: "search", value: options.value || "", placeholder: "",
      "aria-label": options.label || options.placeholder || "Search records",
      "data-lex-bottom-search": key,
    });
    const change = event => {
      clearTimeout(bottomSearchChangeTimers.get(key));
      bottomSearchChangeTimers.delete(key);
      // Replacing an input in the middle of an IME composition discards text.
      if (composing || event?.isComposing) return;
      const apply = () => {
        bottomSearchChangeTimers.delete(key);
        // A delayed filter must not render an old page after navigation.
        if (composing || !control.isConnected) return;
        const focused = document.activeElement === control;
        const start = control.selectionStart;
        const end = control.selectionEnd;
        const direction = control.selectionDirection;
        options.change?.(control.value);
        // Most list views rebuild their pager when filtering. Restore focus
        // before this input event returns, not two animation frames later:
        // keystrokes arriving between frames would otherwise go to <body>.
        if (!focused || control.isConnected) return;
        const active = document.activeElement;
        if (active && active !== document.body && active !== document.documentElement) return;
        const next = [...document.querySelectorAll("[data-lex-bottom-search]")]
          .find(node => node.dataset.lexBottomSearch === key);
        if (!next) return;
        next.focus({preventScroll: true});
        if (Number.isInteger(start)) next.setSelectionRange(
          start, Number.isInteger(end) ? end : start, direction || "none");
        typingSearch = {key, control: next, start, end, direction, at: typingSearch?.at};
      };
      const delay = Math.max(0, Number(options.delay) || 0);
      if (delay) bottomSearchChangeTimers.set(key, setTimeout(apply, delay));
      else apply();
    };
    // A page may rebuild its search box again later than the keystroke - DS1
    // loads the newly selected record and renders once more - and the restore
    // above only covers a rebuild inside the keystroke. So the box being typed
    // in is remembered, and a box built under the same key while that one
    // has left the page (taking focus with it, to <body>) takes over.
    const remember = typed => { typingSearch = {key, control, start: control.selectionStart,
      end: control.selectionEnd, direction: control.selectionDirection,
      at: typed ? performance.now()
        : (typingSearch?.control === control ? typingSearch.at : undefined)}; };
    // The caret is read before the keystroke's own rebuild: read after it, the
    // box had left the page and reported 0, and the next rebuild put the
    // caret at the front ("travelling" came out "ingtravell").
    for (const type of ["input", "keyup"]) control.addEventListener(type, () => {
      if (control.isConnected) remember(true);
    });
    for (const type of ["focus", "select"]) control.addEventListener(type, () => {
      if (control.isConnected) remember(false);
    });
    control.addEventListener("input", change);
    control.addEventListener("blur", () => {
      // A blur while the box sits on the page is the reader leaving it, so
      // the box is forgotten: a box built under this key afterwards must
      // not adopt a value the reader already walked away from. The check
      // lands deferred because yanking the box fires blur while the node
      // still reports connected, and the yanked box keeps its keystrokes
      // adoptable. (A swap in the same task as the blur still adopts;
      // renders land on a later task.)
      setTimeout(() => { if (typingSearch?.control === control && control.isConnected) typingSearch = null; }, 0);
    });
    queueMicrotask(() => {
      const last = typingSearch;
      if (!last || last.key !== key || last.control === control || last.control.isConnected || !control.isConnected) return;
      // The keystrokes that landed in the dead box come along: without this,
      // a record that finishes loading mid-word eats what was typed into the
      // box it replaced, and the search never hears about it. A box the
      // reader left deliberately was already forgotten by its blur, so
      // its render's fresh value stands instead.
      const adopted = last.control.value !== control.value &&
        performance.now() - (last.at || 0) < BOTTOM_SEARCH_ADOPT_MS;
      if (adopted) {
        control.value = last.control.value;
        if (Number.isInteger(last.control.selectionStart)) control.setSelectionRange(
          last.control.selectionStart, Number.isInteger(last.control.selectionEnd)
            ? last.control.selectionEnd : last.control.selectionStart,
          last.control.selectionDirection || "none");
      } else if (Number.isInteger(last.start)) control.setSelectionRange(last.start,
        Number.isInteger(last.end) ? last.end : last.start, last.direction || "none");
      const active = document.activeElement;
      if (!active || active === document.body || active === document.documentElement)
        control.focus({preventScroll: true});
      typingSearch = {key, control, start: control.selectionStart,
        end: control.selectionEnd, direction: control.selectionDirection,
        at: adopted ? last.at : undefined};
      // Last: if this render replaces the box again, the next box takes over
      // from the remembered one with an equal value and only restores focus.
      if (adopted) options.change?.(control.value);
    });
    control.addEventListener("compositionstart", () => {
      composing = true;
      clearTimeout(bottomSearchChangeTimers.get(key));
      bottomSearchChangeTimers.delete(key);
    });
    control.addEventListener("compositionend", () => { composing = false; change(); });
    return element("label", {class: "lex-pager-search"}, searchIcon(), control);
  };

  // The pager's right-hand side is where filters live. These are the two shapes
  // a plugin needs, so every game's filters look and behave the same instead of
  // each one growing its own strip above the table.
  const pagerToggle = spec => {
    const input = element("input", {
      type: "checkbox", checked: spec.checked === true, disabled: spec.disabled === true,
      "aria-label": String(spec.label || "Filter"),
      onchange: event => spec.change?.(event.target.checked),
    });
    return element("label", {
      class: `lex-pager-filter lex-pager-toggle${spec.disabled ? " disabled" : ""}${spec.lines ? " multiline" : ""}`,
      title: String(spec.title || spec.label || ""),
    }, input, element("span", {}, spec.lines ? spec.lines.join("\n") : String(spec.label || "Filter")));
  };

  const pagerSelect = spec => {
    const select = element("select", {
      disabled: spec.disabled === true,
      "aria-label": String(spec.label || "Filter"),
      onchange: event => spec.change?.(event.target.value),
    });
    for (const option of spec.options || []) {
      const node = element("option", {value: String(option.id)}, String(option.label));
      node.selected = String(option.id) === String(spec.value);
      select.append(node);
    }
    return element("label", {
      class: "lex-pager-filter lex-pager-select",
      title: String(spec.title || spec.label || ""),
    }, spec.label ? element("span", {}, String(spec.label)) : null, select);
  };

  const pager = options => {
    const inline = options.inline === true;
    const pages = Math.max(1, Number(options.pages) || 1);
    const page = Math.max(0, Math.min(Number(options.page) || 0, pages - 1));
    // Paging past either end wraps to the other, like the master list: a
    // wheel at the last page turns to the first instead of dying there.
    const wraps = sharedSettingsSnapshot?.pageWrapAround !== false && pages > 1;
    const change = target => options.change?.(Math.max(0, Math.min(target, pages - 1)));
    const pageInput = element("input", {
      class: "lex-page-number", type: "text", inputmode: "numeric", value: page + 1,
      size: String(pages).length, "aria-label": `Current page, ${page + 1} of ${pages}`,
      style: `--lex-page-digits:${String(pages).length}`,
      title: "Click and enter a page number",
      onfocus: event => event.target.select(),
      oninput: event => { event.target.value = event.target.value.replace(/[^0-9]/g, ""); },
    });
    const applyInput = () => {
      const requested = Number.parseInt(pageInput.value, 10);
      const target = Number.isFinite(requested) ? Math.max(1, Math.min(requested, pages)) - 1 : page;
      pageInput.value = target + 1;
      if (target !== page) change(target);
    };
    pageInput.addEventListener("change", applyInput);
    pageInput.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyInput();
      } else if (event.key === "Escape") {
        pageInput.value = page + 1;
        pageInput.blur();
      }
    });
    const button = (text, target, disabled, label) => element("button", {
      disabled, title: label, "aria-label": label, onclick: () => change(target),
    }, text);
    const total = Math.max(0, Number(options.total) || 0);
    const pageSize = Math.max(1, Number(options.pageSize) || 1);
    const first = !total ? 0 : options.range ? options.range[0] : page * pageSize + 1;
    const last = !total ? 0 : options.range ? options.range[1] : Math.min(total, first + pageSize - 1);
    const controls = element("div", {class: "lex-pager-controls"},
      button("<<", 0, page <= 0, "First page"),
      button("<", wraps && page <= 0 ? pages - 1 : page - 1, !wraps && page <= 0, "Previous page"),
      element("span", {class: "lex-page-position"},
        pageInput, element("span", {"aria-hidden": "true"}, "/"),
        element("span", {class: "lex-page-total", text: pages})),
      button(">", wraps && page + 1 >= pages ? 0 : page + 1, !wraps && page + 1 >= pages, "Next page"),
      button(">>", pages - 1, page + 1 >= pages, "Last page"));
    const filters=options.filters || [];
    const createControls=filters.filter(control=>control?.matches?.('.lex-new-button'));
    const left = element("div", {class: "lex-pager-left"},
      ...createControls,
      options.search ? bottomSearch(options.search) : null);
    let rowControl = null;
    if (options.rowControl) {
      // Rows per page runs 5 to 80. The fit used to cap it to what the
      // panel holds at a readable height, so a reader who set 40 got 27.
      const rowMax = 80;
      const commitRows = input => {
        // A box replaced by the render its own Enter caused still blurs; that
        // second commit re-rendered the table again for nothing.
        if (input.dataset.lexCommitted === input.value) return;
        input.dataset.lexCommitted = input.value;
        const requested = Number.parseInt(input.value, 10);
        if (Number.isFinite(requested) && requested > rowMax) {
          input.value = rowMax;
          showToast(`At most ${rowMax} rows on a page.`);
        }
        options.rowControl.change?.(input.value);
      };
      const rowInput = element("input", {
        type: "number", min: "5", max: String(rowMax), step: "1", value: options.rowControl.value,
        // This box is sized for two digits. Fitting its font to its own ch
        // width creates a feedback loop that keeps shrinking both.
        "data-lex-autofit": "false",
        "aria-label": "Rows on this page",
        onblur: event => commitRows(event.target),
        onkeydown: event => {
          if (event.key === "Enter") { event.preventDefault(); commitRows(event.target); }
          else if (event.key === "Escape") {
            event.preventDefault();
            event.target.value = options.rowControl.value;
            event.target.blur();
          }
        },
      });
      rowControl = element("label", {
        class: `lex-page-row-override${options.rowControl.overridden ? "" : " inherited"}`,
        title: options.rowControl.overridden
          ? "Rows on this page. Right-click to use the global setting."
          : `Using the global setting (${options.rowControl.defaultValue}). Change this value to override it on this page.`,
        oncontextmenu: event => {
          event.preventDefault();
          if (options.rowControl.overridden) options.rowControl.clear?.();
        },
      }, element("span", {}, "ROWS"), rowInput);
    }
    const right = element("div", {class: "lex-pager-right"},
      rowControl,
      ...filters.filter(control=>!createControls.includes(control)),
      element("span", {class: "lex-page-summary", text: first === last
        ? `${formatNumber(first)}/${formatNumber(total)}`
        : `${formatNumber(first)}-${formatNumber(last)}/${formatNumber(total)}`}));
    if (options.compact === true) {
      // Narrow panels (the maps directory): the search box takes its own
      // row up top, the X-Y/Z position count is dropped, and everything
      // left shares one bottom row - pager controls, filters and the
      // remaining counts - instead of stacking.
      const bottom = element("div", {class: "lex-compact-pager-bottom"},
        ...createControls,
        pages === 1 ? null : controls,
        ...filters.filter(control => !createControls.includes(control)),
        rowControl);
      return element("div", {
        class: `lex-pager lex-pager-inline lex-compact-pager${pages === 1 ? " single-page" : ""}`,
        "aria-label": "Search and pagination",
      },
        options.search ? element("div", {class: "lex-compact-pager-search"},
          bottomSearch(options.search)) : null,
        bottom);
    }
    return element("div", {
      class: `lex-pager${pages === 1 ? " single-page" : ""}${inline ? " lex-pager-inline" : ""}${options.stacked === true ? " lex-pager-stacked" : ""}`,
      "aria-label": "Search and pagination",
    }, left, pages === 1 ? null : controls, right);
  };

  // The compact pagination bar: pager's narrow-panel variant, with the
  // search box on its own row and one shared bottom row. Same options
  // as pager (page, pages, total, pageSize, search, filters, change).
  const compactPager = options => pager({...options, compact: true});

  // Editing chrome that stays live in a read-only project: none of it changes
  // record data. The in-place rename input and the help-bubble editor only
  // ever exist while Developer Mode is on (their own dblclick handlers check
  // it before creating them), so exempting them here never opens an edit a
  // reader without that identity could reach.
  const READONLY_EXEMPT = [".lex-pager", ".lex-searcher", ".lex-search", ".lex-dialog",
    ".lex-dialog-backdrop", ".lex-modal", ".lex-global-settings", ".lex-project-control",
    ".lex-shortcut-panel", ".lex-github-workspace", ".lex-toast-stack", ".lex-data-map",
    ".lex-label-rename", ".lex-help-edit",
    // View filters narrow a list; they edit no record.
    "[data-lex-view-filter]",
    // Switching, configuring and downloading mods manages the mod library,
    // which exists whether or not a mod is open for editing.
    ".lex-mods-page", ".lex-first-run", ".lex-tweak-panel",
    "header", "nav"].join(",");
  // A control whose value a click changes, as opposed to one a click only
  // focuses. A number box changes on a click only on its spin arrows.
  const changesOnPointer = (target, event) => {
    // Only the value box is reaching for the value. The property's name and
    // the rest of its row are for reading it, and in Developer Mode for
    // dragging it; a click there edits nothing, so it asks nothing. A
    // disabled control takes no pointer events, so a click on it lands on its
    // box. A switch row is one control from end to end.
    const own = target?.closest?.("input,select,textarea");
    const field = own || target?.closest?.(".lex-detail-field-control,.lex-toggle")
      ?.querySelector("input,select,textarea");
    if (!field || field.matches(".lex-readonly-field,[type='search']")) return false;
    // A locked value cannot be typed into, so the click is the only way to
    // reach for it - except a text area's resize grip, which only reads.
    if (field.disabled || field.readOnly) {
      if (!field.matches("textarea") || !event || own !== field) return true;
      const box = field.getBoundingClientRect();
      return !(event.clientX > box.right - 18 && event.clientY > box.bottom - 18);
    }
    // A switch, a list or a number's spin arrows change on the click itself;
    // clicking into a live text or number box only focuses it.
    if (field.matches("select,[type='checkbox'],[type='radio'],[type='range'],[type='color'],[type='file']")) return true;
    if (!field.matches("[type='number']") || !event || own !== field) return false;
    const box = field.getBoundingClientRect();
    return event.clientX > box.right - 20;
  };
  // A key that would change a text value: a character, deleting, or a
  // cut or paste shortcut. Moving the caret, selecting and copying read.
  const typesIntoValue = event => {
    if (event.ctrlKey || event.metaKey) return ["v", "x", "z", "y"].includes(String(event.key).toLowerCase());
    return event.key.length === 1 || ["Backspace", "Delete", "Enter"].includes(event.key);
  };
  const readonlyProject = () =>
    document.documentElement.getAttribute("data-lex-project-readonly") === "true";
  const refusesEdit = (target, event) => {
    if (!readonlyProject()) return false;
    if (!(target instanceof HTMLElement)) return false;
    const control = target.closest("input,select,textarea,[contenteditable='true']");
    if (!control) return false;
    if (control.matches("[type='search'],[type='button'],[type='submit'],[type='reset']")) return false;
    if (control.closest(READONLY_EXEMPT)) return false;
    // Clicking only focuses a text box: the caret, selection and resize grip
    // stay usable, and beforeinput refuses the typing itself.
    if (event?.type === "mousedown" || event?.type === "click") return changesOnPointer(target, event);
    return true;
  };
  // A locked project refuses every record edit, not only the ones a plugin
  // remembered to disable. Capture phase, so it survives every re-render.
  for (const kind of ["beforeinput", "paste", "drop", "keydown", "mousedown", "click", "change"]) {
    document.addEventListener(kind, event => {
      if (!refusesEdit(event.target, event)) return;
      // Reading a locked project still means moving through it, so navigation
      // keys and copying are left alone.
      if (kind === "keydown" && (event.ctrlKey || event.metaKey || event.key.length > 1)) return;
      event.preventDefault();
      event.stopPropagation();
    }, true);
  }

  const barrelPreferenceKey = options => `barrels:${String(
    options.barrelKey || options.splitKey || options.noun || "records")}`;
  const boundedBarrelCount = (value, maximum = 6) => Math.max(1, Math.min(
    Math.max(1, Number(maximum) || 6), Number.parseInt(value, 10) || 1));
  const readBarrelCount = (key, fallback = 1, maximum = 6) => {
    const managed = sharedSettingsSnapshot?.viewPreferences?.[key];
    if (managed !== undefined) return boundedBarrelCount(managed, maximum);
    try {
      const local = localStorage.getItem(`lexeditor:${key}`);
      if (local !== null) return boundedBarrelCount(local, maximum);
    } catch (_error) {}
    return boundedBarrelCount(fallback, maximum);
  };
  // How many columns a page's details use: 1-6, or none saved for "fit".
  // Shared-key migration runs once per base key per session; every path
  // either marks (adopted, purged, or nothing dead) or retries later.
  const migratedColumnKeys = new Set();
  const detailColumnsKey = options => `columns:${String(
    options.columnsKey || options.barrelKey || options.splitKey || options.noun || "records").replace(/[^A-Za-z0-9:_-]/g, "_")}`;
  const readDetailColumns = key => {
    const managed = sharedSettingsSnapshot?.viewPreferences?.[key];
    let value = managed;
    if (value === undefined) {
      try { value = localStorage.getItem(`lexeditor:${key}`); } catch (_error) {}
    }
    const count = Number.parseInt(value, 10);
    return count >= 1 && count <= 6 ? count : 0;
  };
  const saveDetailColumns = (key, value) => {
    if (!value) {
      try { localStorage.removeItem(`lexeditor:${key}`); } catch (_error) {}
      if (sharedSettingsSnapshot?.viewPreferences) delete sharedSettingsSnapshot.viewPreferences[key];
      if (window.pywebview?.api) callWindow("clear_lexeditor_view_preference", key).then(rememberSharedSettings).catch(() => {});
      return;
    }
    saveBarrelCount(key, value, 6);
  };
  const saveBarrelCount = (key, value, maximum = 6) => {
    const count = boundedBarrelCount(value, maximum);
    try { localStorage.setItem(`lexeditor:${key}`, String(count)); } catch (_error) {}
    if (!sharedSettingsSnapshot) sharedSettingsSnapshot = {viewPreferences: {}};
    if (!sharedSettingsSnapshot.viewPreferences) sharedSettingsSnapshot.viewPreferences = {};
    sharedSettingsSnapshot.viewPreferences[key] = count;
    if (window.pywebview?.api) {
      callWindow("save_lexeditor_view_preference", key, count)
        .then(rememberSharedSettings).catch(() => {});
    }
    return count;
  };
  const tableRowPreferenceKey = options => `rows:${String(
    options.rowsKey || options.splitKey || options.noun || "records")}`;
  const boundedTableRows = value => Math.max(5, Math.min(80, Number.parseInt(value, 10) || 15));
  const hasTableRowsOverride = key => {
    if (sharedSettingsSnapshot?.viewPreferences &&
        Object.prototype.hasOwnProperty.call(sharedSettingsSnapshot.viewPreferences, key)) return true;
    try { return localStorage.getItem(`lexeditor:${key}`) !== null; }
    catch (_error) { return false; }
  };
  const readTableRows = (key, fallback) => {
    const managed = sharedSettingsSnapshot?.viewPreferences?.[key];
    if (managed !== undefined) return boundedTableRows(managed);
    try {
      const local = localStorage.getItem(`lexeditor:${key}`);
      if (local !== null) return boundedTableRows(local);
    } catch (_error) {}
    return boundedTableRows(fallback);
  };
  const saveTableRows = (key, value) => {
    const count = boundedTableRows(value);
    try { localStorage.setItem(`lexeditor:${key}`, String(count)); } catch (_error) {}
    if (!sharedSettingsSnapshot) sharedSettingsSnapshot = {viewPreferences: {}};
    if (!sharedSettingsSnapshot.viewPreferences) sharedSettingsSnapshot.viewPreferences = {};
    sharedSettingsSnapshot.viewPreferences[key] = count;
    if (window.pywebview?.api) {
      callWindow("save_lexeditor_view_preference", key, count)
        .then(rememberSharedSettings).catch(() => {});
    }
    return count;
  };
  const clearTableRows = key => {
    try { localStorage.removeItem(`lexeditor:${key}`); } catch (_error) {}
    if (sharedSettingsSnapshot?.viewPreferences) delete sharedSettingsSnapshot.viewPreferences[key];
    if (window.pywebview?.api) {
      callWindow("clear_lexeditor_view_preference", key)
        .then(rememberSharedSettings).catch(() => {});
    }
  };
  const tableFitCapacityCache = new Map();
  // The table whose row count the reader just typed, so a fit that caps it
  // says why instead of quietly showing fewer rows than asked for.
  let typedRowsKey = null;
  // Which page each table last drew, so a page the reader asked for can be
  // told apart from the page a stale selection would pull it back to.
  const lastRenderedPage = new Map();
  let openBarrelControlKey = "";
  let pendingBarrelSettle = null;
  const fitBarrelTableColumns = node => {
    const template = node?.style?.getPropertyValue("--lex-column-list-template");
    if (!template) return node;
    const fitted = template.replace(/minmax\(\s*[\d.]+px\s*,/gi, "minmax(0,");
    if (fitted !== template) node.style.setProperty("--lex-column-list-template", fitted);
    return node;
  };

  // Split a grid template into top-level tracks, keeping minmax()/max()
  // argument lists whole. Shared by the heading fit and the barrel fit.
  const splitTemplateTracks = base => {
    const tracks = [];
    let depth = 0, start = 0;
    for (let index = 0; index <= base.length; index++) {
      const character = base[index];
      if (character === "(") depth++;
      if (character === ")") depth--;
      if (index === base.length || (!depth && /\s/.test(character))) {
        if (index > start) tracks.push(base.slice(start, index));
        start = index + 1;
      }
    }
    return tracks;
  };

  // The content width of each barrel column, maxed across the barrels of
  // one grid. No box here reports its content: the cell stretches to its
  // track, the content box stretches to the cell, and even the truncating
  // text span stretches past its text, so every scroll width reports the
  // track back and any floor built on one ratchets to whatever width the
  // barrel happened to have. A range over the span's text reports the text
  // itself, clipped or not, plus the cell's padding. Fixed tracks report
  // their used width from the header, which stretches to a constant.
  // Content-sized tracks report the header at its min-content: headings wrap,
  // so a long name holds its longest word, not the whole line.
  const measureBarrelColumnWidths = grid => {
    const lists = [...(grid?.querySelectorAll?.(":scope > .lex-column-list") || [])]
      .filter(node => node.offsetParent);
    if (!lists.length) return null;
    const keys = lists.map(node =>
      [...node.querySelectorAll(":scope > .lex-column-list-header:not(.lex-matrix-column-axis)"
        + " > .lex-column-list-head-cell")].map(cell => cell.dataset.columnKey));
    if (!keys[0].length || keys.some(sequence => sequence.join("\n") !== keys[0].join("\n"))) return null;
    const templates = lists.map(node => splitTemplateTracks(
      node.style.getPropertyValue("--lex-column-list-template")));
    if (templates.some(tracks => tracks.length !== keys[0].length)) return null;
    const contentSized = track => !/fr\b/.test(track)
      && /\b(max-content|min-content|auto)\b/.test(track);
    // Heads of content-sized tracks read at min-content (their longest word),
    // not at the track they stretch to: the track holds the whole header line
    // when room suffices, and reading it would size every column to its name
    // instead of its values. One write batch, one read layout, one restore.
    const minContentHeads = [];
    lists.forEach((node, listIndex) => {
      node.querySelectorAll(":scope > .lex-column-list-header:not(.lex-matrix-column-axis)"
        + " > .lex-column-list-head-cell").forEach((head, index) => {
        if (contentSized(templates[listIndex][index]) || /fr\b/.test(templates[listIndex][index])) {
          minContentHeads.push([head, head.style.width]);
          head.style.width = "min-content";
        }
      });
    });
    const range = document.createRange();
    const cellPad = index => {
      const cell = lists[0].querySelectorAll(":scope > .lex-column-list-row"
        + " > .lex-column-list-cell")[index];
      if (!cell) return 0;
      const style = getComputedStyle(cell);
      return (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
    };
    const widths = keys[0].map((_key, index) => {
      let need = 0;
      for (const node of lists) {
        const track = templates[lists.indexOf(node)][index];
        const head = node.querySelectorAll(":scope > .lex-column-list-header"
          + " > .lex-column-list-head-cell")[index];
        if (contentSized(track)) {
          // A content-sized track is already as wide as its widest content,
          // header included, so the header box reports it directly. Body
          // ranges alone undercount columns whose heading outruns their
          // values, and the floor then says "fits" while the boxes overflow.
          if (head) need = Math.max(need, head.getBoundingClientRect().width);
        } else if (!/fr\b/.test(track)) {
          // A grow track absorbs, so it wants its content like any other;
          // only a truly fixed track reports its used width.
          if (head) need = Math.max(need, head.getBoundingClientRect().width);
          continue;
        }
        // This track is flexible: the heading fit floors it at the header's
        // longest word, so the want includes the header (read at min-content
        // above) alongside the body text scanned below.
        if (head) need = Math.max(need, head.getBoundingClientRect().width);
        // Filler rows draw the grid below a short barrel; they hold no
        // values, only a zero-width space outside any text span, so the
        // fallback below would read their stretched box - the track width
        // itself - and every refit would feed the last width back as content.
        node.querySelectorAll(":scope > .lex-column-list-row:not(.lex-filler-row)").forEach(row => {
          const cell = row.querySelectorAll(":scope > .lex-column-list-cell")[index];
          if (!cell) return;
          const spans = cell.querySelectorAll(":scope .lex-column-cell-text");
          if (spans.length) {
            spans.forEach(span => {
              range.selectNodeContents(span);
              need = Math.max(need, range.getBoundingClientRect().width);
            });
          } else {
            const inner = cell.firstElementChild;
            if (inner) {
              // A block or flex child stretches to its track, so its box -
              // and a range over the element, which covers the stretched box
              // - reports the track back, and any floor built on it ratchets
              // a little wider every refit. Text nodes do not stretch: union
              // the rendered text with any replaced content. Only a child
              // with neither (a fixed icon) reports its box.
              let left = Infinity, right = -Infinity;
              const walker = document.createTreeWalker(inner, NodeFilter.SHOW_TEXT);
              let textNode = walker.nextNode();
              while (textNode) {
                if (textNode.textContent.trim()) {
                  range.selectNodeContents(textNode);
                  const box = range.getBoundingClientRect();
                  if (box.width > 0) {
                    left = Math.min(left, box.left);
                    right = Math.max(right, box.right);
                  }
                }
                textNode = walker.nextNode();
              }
              for (const replaced of inner.querySelectorAll("img,svg,canvas,video")) {
                const box = replaced.getBoundingClientRect();
                if (box.width > 0) {
                  left = Math.min(left, box.left);
                  right = Math.max(right, box.right);
                }
              }
              need = Math.max(need, right > left ? right - left : inner.getBoundingClientRect().width);
            }
          }
        });
      }
      // Two pixels of slack, the way the heading fit adds two: ranges,
      // padding and grid shares all round, and a single sub-pixel of
      // overflow still draws an ellipsis.
      return Math.ceil(need + (need > 0 ? cellPad(index) + 2 : 0));
    });
    for (const [head, width] of minContentHeads) head.style.width = width;
    const style = getComputedStyle(lists[0]);
    const pad = ["paddingLeft", "paddingRight", "borderLeftWidth", "borderRightWidth"]
      .reduce((sum, prop) => sum + (parseFloat(style[prop]) || 0), 0);
    return {lists, keys: keys[0], templates, widths, pad};
  };

  // Barrels of one table share their columns, so they share their column
  // widths: each barrel used to fit its own rows, and one barrel holding a
  // long value ("Split archive" in Kind) squeezed its other columns while
  // its neighbours stayed wide. Every content-sized track takes the widest
  // body content found in ANY barrel, so the columns line up across barrels.
  // Fixed and grow tracks are untouched: the grow column still absorbs.
  // A font that lands late re-metrics every column: re-fit all barrels
  // after each font batch, not only the first. Ready fires once no matter
  // how many batches arrive after it; without this a late swap leaves
  // floors measured in the fallback font behind.
  let barrelFontWatcher = false;
  const watchBarrelFonts = () => {
    if (barrelFontWatcher || !document.fonts?.addEventListener) return;
    barrelFontWatcher = true;
    document.fonts.addEventListener("loadingdone", () => {
      requestAnimationFrame(() => {
        for (const grid of document.querySelectorAll(".lex-barrel-grid")) {
          if (!grid.isConnected) continue;
          unifyBarrelTemplates(grid);
          grid.closest(".lex-panel-layout")?.refreshLayout?.();
        }
      });
    });
  };

  const unifyBarrelTemplates = grid => {
    watchBarrelFonts();
    const measured = measureBarrelColumnWidths(grid);
    if (!measured || measured.lists.length < 2) return;
    const contentSized = track => !/fr\b/.test(track)
      && /\b(max-content|min-content|auto)\b/.test(track);
    if (!measured.templates[0].some(contentSized)) return;
    measured.lists.forEach((node, listIndex) => {
      const original = splitTemplateTracks(node.lexHeadingTemplate || "");
      const next = measured.templates[listIndex].map((track, index) => {
        // Flexible tracks align like content ones, floored at the shared body
        // width, except the absorbent grow track (a zero minimum in the
        // original template), which keeps truncating into the slack.
        const frRange = /^minmax\((.*),\s*([\d.]+fr)\)$/.exec(track);
        if (frRange) {
          const originalMin = /^minmax\((.*),\s*[\d.]+fr\)$/.exec(original[index] || "")?.[1].trim();
          if (originalMin === "0" || originalMin === "0px") return track;
          const fittedMin = Math.max(0, ...[...frRange[1].matchAll(/([\d.]+)px/g)]
            .map(match => parseFloat(match[1])));
          return `minmax(${Math.max(measured.widths[index], Math.ceil(fittedMin))}px, ${frRange[2].trim()})`;
        }
        // The shared body width floors the track; the track's own maximum is
        // kept, so an auto maximum keeps yielding (and its header wrapping)
        // where max-content would overflow instead.
        if (!contentSized(track)) return track;
        const range = /^minmax\((.*),\s*([^,]+)\)$/.exec(track);
        const maximum = range ? range[2].trim() : track.trim();
        return `minmax(${measured.widths[index]}px, ${maximum})`;
      }).join(" ");
      if (node.style.getPropertyValue("--lex-column-list-template") !== next)
        node.style.setProperty("--lex-column-list-template", next);
    });
  };

  // A short final barrel used to simply stop, leaving its background drawn but
  // its rules missing. Pad it out with empty rows so the table keeps its grid
  // to the bottom of the panel, the way a spreadsheet does.
  const padBarrelTable = (node, target) => {
    if (!node?.classList?.contains("lex-column-list")) return node;
    const header = node.querySelector(".lex-column-list-header");
    if (!header) return node;
    const cells = header.querySelectorAll(".lex-column-list-head-cell").length;
    if (!cells) return node;
    const present = node.querySelectorAll(".lex-column-list-row").length;
    for (let index = present; index < target; index++) {
      const filler = element("div", {
        class: "lex-list-row lex-column-list-row lex-filler-row", role: "row", "aria-hidden": "true",
      });
      const keys = [...header.querySelectorAll(".lex-column-list-head-cell")]
        .map(cell => cell.dataset.columnKey || null);
      for (let column = 0; column < cells; column++) {
        // Mirror a real cell's structure, including its content span, so the
        // filler rows line up exactly with the barrel beside them. The key
        // rides along so a lit column glows to the bottom of the panel
        // instead of stopping at the last real row.
        filler.append(element("div", {class: "lex-column-list-cell", role: "cell",
          "data-column-key": keys[column] || null},
          element("span", {class: "lex-column-cell-content"}, "​")));
      }
      node.append(filler);
    }
    return node;
  };

  // One preset owns the complete paged list-detail behavior. Games provide
  // records and view-specific renderers; they do not assemble their own page
  // slice, selection fallback, fitted master, detail, and bottom pager.
  // Every Table declares whether its records are fixed SLOTS or a growable
  // list, because the two behave differently in three visible ways: a growable
  // list offers Add, a slot table never does; a slot table can hide its
  // empty slots; and once a slot table is sorted by anything but its ID, a
  // first-to-last range no longer describes what is on screen. Both pad a
  // short page with empty rows so the grid reaches the panel bottom.
  const slotTablePreferenceKey = options =>
    `hide-empty:${String(options.rowsKey || options.splitKey || options.noun || "records")}`;
  const readHideEmpty = key => {
    try { return localStorage.getItem(key) === "1"; } catch (_error) { return false; }
  };
  const saveHideEmpty = (key, value) => {
    try {
      if (value) localStorage.setItem(key, "1");
      else localStorage.removeItem(key);
    } catch (_error) {}
  };

  const tableSelections = new Map();
  const applyRecordDelta = (before,after,target) => {
    if(Array.isArray(after)&&after.some(value=>value?.field)) {
      for(const value of after){
        const old=before?.find(entry=>entry.field===value.field),next=target.find(entry=>entry.field===value.field);
        if(old&&next)applyRecordDelta(old,value,next);
      }
      return;
    }
    for (const key of Object.keys(after||{})) {
      if (!(key in target)) continue;
      const a=before?.[key],b=after[key];
      if (JSON.stringify(a)===JSON.stringify(b)) continue;
      if(a&&b&&typeof a==='object'&&typeof b==='object'&&target[key]&&typeof target[key]==='object')
        applyRecordDelta(a,b,target[key]);
      else target[key]=clone(b);
    }
  };
  let listResortedAt = -Infinity;
  const pagedListDetail = options => {
    const slotBased = options.slots !== false;
    if (options.slots === undefined && sharedSettingsSnapshot?.developerMode) {
      console.warn(`Table "${options.splitKey || options.noun || "records"}" does not declare slots:`
        + " true for fixed slots, false for a growable list.");
    }
    const emptyRow = slotBased && typeof options.empty === "function" ? options.empty : null;
    const hideEmptyKey = slotTablePreferenceKey(options);
    const hideEmpty = Boolean(emptyRow) && readHideEmpty(hideEmptyKey);
    const allRows = Array.isArray(options.rows) ? options.rows : [];
    // "Mod contents only" belongs to the shared table, not to each plugin.
    // A plugin says whether it can tell (it needs a vanilla baseline loaded)
    // and how to tell for one record; the toggle, its placement on the
    // pagination bar, the filtering and the page reset are handled here, so
    // adopting it is one option rather than a reimplementation per game.
    const modOnly = options.modOnly && typeof options.modOnly.changed === "function"
      ? options.modOnly : null;
    const modOnlyOn = Boolean(modOnly && modOnly.value && modOnly.available !== false);
    const suppliedRows = modOnlyOn
      ? allRows.filter(row => modOnly.changed(row)) : allRows;
    let records = hideEmpty ? suppliedRows.filter(record => !emptyRow(record)) : suppliedRows;
    const emptyCount = emptyRow ? suppliedRows.reduce(
      (count, record) => count + (emptyRow(record) ? 1 : 0), 0) : 0;
    // A column sort belongs to the list, not to the page: a table that holds
    // one page asked for this order, so apply it before the page is cut.
    const rowPreferenceKey = tableRowPreferenceKey(options);
    let keptSort = pagedSortStates.get(rowPreferenceKey);
    // Every record list sorts by name, A to Z, until the reader picks
    // a column: the shipped default. A click still wins for that table,
    // and a page whose order is data (load order, time order, fixed
    // slots) passes order "given" to keep it. Stored like a click, so
    // the first click on Name flips to Z to A instead of re-sorting
    // to the order already shown.
    // Nameless rows have nothing to sort by: stamping the default
    // anyway would be a no-op today that silently starts sorting the
    // day a name field appears. Those tables keep their given order.
    const hasNames = records.some(record => {
      const name = sortValueOf(record, "name");
      return name !== undefined && name !== null && name !== "" && name !== "\u2014";
    });
    if (!keptSort && options.order !== "given" && hasNames) {
      keptSort = {key: "name", dir: 1,
        compare: (left, right) => compareRecords(left, right, {key: "name"})};
      pagedSortStates.set(rowPreferenceKey, keptSort);
    }
    if (keptSort && typeof keptSort.compare === "function") {
      records = [...records].sort((left, right) => keptSort.compare(left, right) * keptSort.dir);
    }
    // Set the id width before either pane renders so the detail heading and
    // the table agree on padding.
    setRecordIdWidth(records, {wholeSet: true});
    const keyOf = options.key;
    // A Table page uses one global row target. Plugin-local page sizes are only
    // compatibility state until the shared settings snapshot arrives.
    // Pagination must leave enough height for readable text and controls.
    // The requested row count is a ceiling, not permission to crush rows.
    const fitMinimum = options.fit === false ? 0 : Math.max(32, Number(options.fit?.minRowHeight) || 0);
    const fitCapacity = fitMinimum ? tableFitCapacityCache.get(rowPreferenceKey) : null;
    const globalPageSize = boundedTableRows(sharedSettingsSnapshot?.tableRowsPerPage || fitCapacity?.requested || options.pageSize || 15);
    const hasRowOverride = hasTableRowsOverride(rowPreferenceKey);
    const requestedPageSize = readTableRows(rowPreferenceKey, globalPageSize);
    const pageSize = requestedPageSize;
    // The page always declares a full page of tracks: sizing the tracks to a
    // short table's own row count stretched its rows to fill the panel.
    const rowCapacity = Math.max(1, pageSize);
    const maximumBarrels = boundedBarrelCount(options.maxBarrels || 6, 6);
    const preferenceKey = barrelPreferenceKey(options);
    const oldPages = Math.max(1, Math.ceil(records.length / pageSize));
    const barrels = Math.min(oldPages, readBarrelCount(
      preferenceKey, options.defaultBarrels || 1, maximumBarrels));
    const barrelSize = pageSize * barrels;
    const requestedSelection = options.selected;
    const pages = Math.max(1, Math.ceil(records.length / barrelSize));
    let page = Math.max(0, Math.min(Number(options.page) || 0, pages - 1));
    const requestedIndex = records.findIndex(record => keyOf(record) === requestedSelection);
    // The reveal exists for a selection that arrived from somewhere else - a
    // search hit, a link followed - and it must not fight the reader. Paging
    // forward leaves the selection on the page you left, so the reveal dragged
    // the table straight back to it and pagination looked dead: every press of
    // Next re-rendered page one. A page the reader asked for wins; the reveal
    // applies when the PAGE did not change and the selection did.
    // A null page is a link asking for its record, not a page choice: several
    // lists can share one key (FF8's World subtabs), and a link from one to
    // another must still reveal its record.
    // A new sort starts at the top (Lexer: sorting "didn't sort", because the
    // list stayed on the page that held the selected record, mid-order). The
    // header click is read by the list it re-renders, even one that fetches
    // first, and by no other.
    const resorted = performance.now() - listResortedAt < 2000;
    listResortedAt = -Infinity;
    if (resorted) page = 0;
    const pagedDeliberately = resorted || options.page !== null && options.page !== undefined &&
      lastRenderedPage.get(rowPreferenceKey) !== undefined &&
      lastRenderedPage.get(rowPreferenceKey) !== page;
    lastRenderedPage.set(rowPreferenceKey, page);
    if (options.revealSelected !== false && !pagedDeliberately && requestedIndex >= 0 &&
        (requestedIndex < page * barrelSize || requestedIndex >= (page + 1) * barrelSize)) {
      page = Math.floor(requestedIndex / barrelSize);
      lastRenderedPage.set(rowPreferenceKey, page);
    }
    const groupStart = page * barrelSize;
    const barrelRows = records.length ? Array.from({length: barrels}, (_unused, index) =>
      records.slice(groupStart + index * pageSize, groupStart + (index + 1) * pageSize)) : [[]];
    const shown = barrelRows.flat();
    const picked = shown.find(record => keyOf(record) === requestedSelection) || shown[0] || null;
    let selected = picked ? keyOf(picked) : null;
    const change = (reason, patch = {}) => options.change?.({
      page, pageSize, selected, reason, ...patch,
    });
    const changePage = target => {
      const requested = Number(target) || 0;
      // Paging past either end wraps to the other, so a wheel at the last page
      // does something instead of silently re-rendering the same page.
      const wraps = sharedSettingsSnapshot?.pageWrapAround !== false;
      const targetPage = wraps && pages > 1
        ? ((requested % pages) + pages) % pages
        : Math.max(0, Math.min(requested, pages - 1));
      if (targetPage === page) return false;
      const first = records[targetPage * barrelSize] || null;
      change("page", {page: targetPage, selected: first ? keyOf(first) : null});
      return true;
    };
    const changeBarrels = requested => {
      const next = Math.max(1, Math.min(oldPages, maximumBarrels, Number(requested) || 1));
      if (next === barrels) return false;
      openBarrelControlKey = preferenceKey;
      saveBarrelCount(preferenceKey, next, maximumBarrels);
      const anchor = requestedIndex >= 0 ? requestedIndex : groupStart;
      const nextPage = Math.max(0, Math.floor(anchor / (pageSize * next)));
      change("barrels", {page: nextPage});
      return true;
    };

    // Synchronize clamped pages and selection fallback without causing a
    // second render. Interactive changes go through the one change callback.
    const selectionKey=options.splitKey || rowPreferenceKey;
    const selection=tableSelections.get(selectionKey)||{keys:new Set([selected]),anchor:selected};
    selection.keys=new Set([...selection.keys].filter(key=>records.some(row=>keyOf(row)===key)));
    if(!selection.keys.size)selection.keys.add(selected);
    tableSelections.set(selectionKey,selection);
    options.sync?.({page, pageSize, selected, selection: [...selection.keys]});
    const pinOwner={store:autoPins(options.rowsKey||rowPreferenceKey),
      describe:options.describePinnedCell||null,commitCell:options.commitPinnedCell||null,
      move:(value,before)=>{
      const pinned=pinOwner.store.pinned,moving=pinned.find(entry=>entry.key===value);
      if(!moving||value===before)return;
      const rest=pinned.filter(entry=>entry.key!==value);
      const index=rest.findIndex(entry=>entry.key===before);
      if(index<0)rest.push(moving);else rest.splice(index,0,moving);
      pinOwner.store.pinned=rest;
      try{localStorage.setItem(pinOwner.store.key,JSON.stringify(rest));}catch(_error){}
      change("pins",{});
    },toggle:(key,label,icon)=>{
      const store=pinOwner.store;
      store.pinned=store.pinned.some(entry=>entry.key===key)?store.pinned.filter(entry=>entry.key!==key):[...store.pinned,{key,label,icon:icon||"",shipped:pinShipped(label)}];
      try{localStorage.setItem(store.key,JSON.stringify(store.pinned));}catch(_error){}
      change("pins",{});
    }};
    const renameOwner=typeof options.rename==="function"
      ?{rename:options.rename,shippedName:options.shippedName,renamable:row=>typeof options.renamable==="function"?options.renamable(row)!==false:true}:null;
    const makeDetail=record=>{
      const node=options.detail(record);
      // The heading's name renames the record too, by double-click.
      const heading=renameOwner&&renameOwner.renamable(record)?node.querySelector?.(".lex-detail-panel-name"):null;
      if(heading){
        heading.title="Double-click to rename";
        heading.addEventListener("dblclick",event=>{
          event.preventDefault();event.stopPropagation();
          if(shellIsReadonly()){requestModForEdit?.();return;}
          renameValue(heading,{value:String(record.name??heading.textContent),label:"this record",
            shipped:typeof renameOwner.shippedName==="function"?renameOwner.shippedName(record):undefined,
            commit:name=>renameOwner.rename(record,name)});
        });
      }
      if(typeof options.change==="function"&&!pinOwner.declined)autoPinDetail(node,pinOwner);
      const chosen=records.filter(row=>selection.keys.has(keyOf(row)));
      if(chosen.length>1){
        const banner=element('div',{class:'lex-multi-edit-notice'},`${chosen.length} records selected. Edits apply to all selected records. Values shown are from ${record.name||keyOf(record)}; other records may differ.`);
        // The notice heads the panel's body. Prepended to the panel itself it
        // took the heading's grid row, the heading took the body's, and the
        // body was left with no height: a giant name over an empty pane
        // (Lexer: multi-select "literally doesn't work").
        const body=node.querySelector?.(":scope > .lex-tweaks-paged, :scope > .lex-detail-panel-body");
        if(body)body.prepend(banner);else node.prepend(banner);
        let editBefore;
        const beginEdit=event=>{
          if(!event.target.matches('input,select,textarea'))return;
          editBefore=clone(record);
          // An explicit value also applies when it equals the primary value.
          const label=event.target.getAttribute('aria-label')||'';
          const index=record.fields?.findIndex(field=>field.label===label);
          if(index>=0)editBefore.fields[index].value={bulkEdit:true};
          else {
            const normalize=value=>String(value).replace(/[^a-z0-9]/gi,'').toLowerCase();
            const key=Object.keys(record).find(key=>normalize(key)===normalize(label));
            if(key&&typeof record[key]!=='object')editBefore[key]={bulkEdit:true};
          }
        };
        const finishEdit=()=>{
          if(!editBefore)return;
          for(const target of chosen)if(target!==record)applyRecordDelta(editBefore,record,target);
          editBefore=null;options.bulkChanged?.();
        };
        for(const event of ['input','change']){
          node.addEventListener(event,beginEdit,true);node.addEventListener(event,finishEdit);
        }
      }
      return node;
    };
    let detailNode = picked
      ? makeDetail(picked)
      : (typeof options.emptyDetail === "function" ? options.emptyDetail() : options.emptyDetail || element("div", {class: "lex-detail"}));
    let leadingNode = typeof options.leadingPanel === "function" && picked ? options.leadingPanel(picked) : null;
    let trailingNode = typeof options.trailingPanel === "function" && picked ? options.trailingPanel(picked) : null;
    let masterNodes = [];
    const select = (record,event={}) => {
      const nextSelected = keyOf(record);
      if(event.shiftKey){
        const start=records.findIndex(row=>keyOf(row)===selection.anchor),end=records.indexOf(record);
        if(!event.ctrlKey&&!event.metaKey)selection.keys.clear();
        for(const row of records.slice(Math.max(0,Math.min(start,end)),Math.max(start,end)+1))selection.keys.add(keyOf(row));
      }else if(event.ctrlKey||event.metaKey){
        if(selection.keys.has(nextSelected)&&selection.keys.size>1)selection.keys.delete(nextSelected);else selection.keys.add(nextSelected);
        selection.anchor=nextSelected;
      }else {selection.keys=new Set([nextSelected]);selection.anchor=nextSelected;}
      selected = selection.keys.has(nextSelected)?nextSelected:[...selection.keys].at(-1);
      record=records.find(row=>keyOf(row)===selected)||record;
      options.sync?.({page, pageSize, selected, selection: [...selection.keys], reason:"select"});
      for (const node of masterNodes) {
        node.querySelectorAll(".lex-list-row[data-key]").forEach(row => {
          const active = [...selection.keys].some(key=>String(key)===String(row.dataset.key));
          row.classList.toggle("selected", active);
          row.classList.remove("sel");
          row.setAttribute("aria-selected", String(active));
        });
      }
      const replacement = makeDetail(record);
      if (detailNode.classList.contains("lex-panel-layout-pane")) replacement.classList.add("lex-panel-layout-pane");
      const fixedHeight = detailNode.style.height;
      if (fixedHeight) replacement.style.height = fixedHeight;
      root.lexReplacePanel(detailNode, replacement);
      detailNode = replacement;
      if (leadingNode) {
        const nextLeading = options.leadingPanel(record);
        nextLeading.classList.add("lex-panel-layout-pane");
        root.lexReplacePanel(leadingNode, nextLeading);
        leadingNode = nextLeading;
        refreshReferences(nextLeading);
      }
      if (trailingNode) {
        const nextTrailing = options.trailingPanel(record);
        root.lexReplacePanel(trailingNode, nextTrailing);
        trailingNode = nextTrailing;
        refreshReferences(nextTrailing);
      }
      refreshReferences(replacement);
      return true;
    };
    // While the master builds its tables, tell them that this list owns the
    // order: a click on one of their headers re-sorts the list, then the list
    // re-renders through the plugin's own change callback.
    const buildMasters = () => {
      const outerSortOwner = pagedSortOwner, outerPinOwner = pagedPinOwner, outerRenameOwner = pagedRenameOwner;
      pagedPinOwner = typeof options.change === "function" ? pinOwner : null;
      pagedRenameOwner = renameOwner;
      pagedSortOwner = typeof options.change === "function" ? {
        state: keptSort ? {key: keptSort.key, dir: keptSort.dir} : null,
        sort: (column, direction, compare) => {
          pagedSortStates.set(rowPreferenceKey, {key: column.key, dir: direction, compare});
          change("sort", {});
        },
      } : null;
      try {
        return barrelRows.map((rows, index) => {
          const node = typeof options.master === "function"
            ? options.master({rows, selected, select, barrel: index, barrels})
            : list({...options.list, rows, key: keyOf, selected, select});
          node.querySelectorAll('.lex-list-row[data-key]').forEach(row=>{
            const active=[...selection.keys].some(key=>String(key)===row.dataset.key);
            row.classList.toggle('selected',active);row.setAttribute('aria-selected',String(active));
            if(modOnly){
              const record=rows.find(record=>String(keyOf(record))===row.dataset.key);
              row.dataset.lexRecordProvenance='';
              row.refreshRecordProvenance=()=>row.classList.toggle('lex-record-modified',
                record!==undefined&&modOnly.available!==false&&Boolean(modOnly.changed(record)));
              row.refreshRecordProvenance();
            }
          });
          node.setAttribute('aria-multiselectable','true');
          fitBarrelTableColumns(node);
          // Filler rows square off a short page the way a spreadsheet does,
          // slot table or growable list alike: the grid keeps its rules to the
          // bottom of the panel instead of ending in flat gray.
          // Pad to the track count this table actually declares. Padding to the
          // page size instead put forty rows into a ten-track grid whenever a
          // table held less than one page: the ten declared tracks collapsed to
          // zero and every real record painted on top of the others in one band.
          padBarrelTable(node, rowCapacity);
          node.classList.add("lex-page-sized-table");
          // The track count never drops below the page's row target: a short
          // page keeps fitted-height rows with empty tracks below it instead
          // of stretching its rows to fill the panel. It never drops below
          // the rows really there either, so padding and capacity cannot
          // disagree and paint records on top of each other again.
          node.style.setProperty("--lex-page-row-count",
            String(Math.max(rowCapacity, node.querySelectorAll(":scope > .lex-column-list-row").length)));
          node.style.setProperty("--lex-page-font-row-count", String(rowCapacity));
          node.dataset.lexBarrel = String(index + 1);
          if (index) node.classList.add("lex-fitted-page");
          return node;
        });
      } finally {
        pagedSortOwner = outerSortOwner;
        pagedPinOwner = outerPinOwner;
        pagedRenameOwner = outerRenameOwner;
        if (pinOwner.declined) detailNode?.querySelectorAll?.("[data-lex-auto-pin]").forEach(node => node.remove());
      }
    };
    masterNodes = buildMasters();
    // The floor belongs to THIS table's record set. Leaving it set made an
    // unrelated table rendered afterwards inherit the padding.
    recordIdFloor = 1;
    const decrease = element("button", {
      class: "lex-barrel-decrease",
      type: "button", disabled: barrels <= 1, title: "Show one fewer table",
      "aria-label": "Decrease table barrels", onclick: () => changeBarrels(barrels - 1),
    });
    const increase = element("button", {
      class: "lex-barrel-increase",
      type: "button", disabled: barrels >= Math.min(oldPages, maximumBarrels),
      title: "Show the next page beside this table",
      "aria-label": "Increase table barrels", onclick: () => changeBarrels(barrels + 1),
    });
    const barrelControl = element("div", {
      class: `lex-barrel-control${openBarrelControlKey === preferenceKey ? " open" : ""}`, hidden: oldPages <= 1,
      title: "Tables shown side by side",
      onmouseleave: () => {
        if (openBarrelControlKey !== preferenceKey) return;
        openBarrelControlKey = "";
        barrelControl.classList.remove("open");
      },
    }, element("span", {class: "lex-barrel-label"}, "BARRELS"),
    element("span", {class: "lex-barrel-buttons"}, decrease,
      element("output", {class: "lex-barrel-count", "aria-live": "polite"}, String(barrels)), increase));
    if (pendingBarrelSettle) {
      document.removeEventListener("pointermove", pendingBarrelSettle.move);
      document.removeEventListener("pointerdown", pendingBarrelSettle.down);
      pendingBarrelSettle = null;
    }
    // A re-rendered control appears under a stationary cursor the browser
    // never tracked as hovered, so its own mouseleave may never fire and
    // the sticky open state would survive mouse-away. The next pointer
    // movement or press anywhere settles it: still over a gizmo means
    // hover tracking works from here, otherwise the stickiness clears.
    if (openBarrelControlKey === preferenceKey) {
      const settle = event => {
        if (event.target.closest?.(".lex-barrel-control")
          || openBarrelControlKey !== preferenceKey) return;
        openBarrelControlKey = "";
        barrelControl.classList.remove("open");
      };
      const done = () => {
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerdown", down);
        if (pendingBarrelSettle?.move === move) pendingBarrelSettle = null;
      };
      const move = event => { settle(event); done(); };
      const down = event => { settle(event); done(); };
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerdown", down);
      pendingBarrelSettle = {move, down};
    }
    // COLUMNS mirrors BARRELS on the other side of the same divider: how many
    // columns the selected record's details flow into. Right-click: fit again.
    // Without an explicit columnsKey each panel tab keeps its own column
    // count: the key extends with the active tabs in the detail, outer to
    // inner, so one item section and the next (or the GF's HP tab and its
    // XP tab) can differ. Callers that show the same fields under several
    // subtabs pass columnsKey to share one count across them, the way the
    // property layout already does; the subtab path stays off that key.
    const columnsBaseKey = detailColumnsKey(options);
    const sharedColumnsKey = Boolean(options.columnsKey);
    const columnsPathNow = () => [...(detailNode?.querySelectorAll?.(".lex-subtab-bar") || [])]
      .map(bar => bar.querySelector(":scope > .lex-subtab-button.active")?.dataset.subtab?.replace(/[^A-Za-z0-9_-]/g, "_"))
      .filter(Boolean);
    const columnsKeyNow = () => {
      if (sharedColumnsKey) return columnsBaseKey;
      const path = columnsPathNow();
      return path.length ? `${columnsBaseKey}:${path.join(":")}` : columnsBaseKey;
    };
    // A count saved under an older per-subtab key moves up to the shared
    // key once: the current subtab's wins, else the largest dead one (a
    // real count beats a fitted guess), and the dead per-subtab keys go
    // away from every store. Fresh readers with no saved count keep the
    // fitted default: nothing is written for them.
    const migrateSharedColumns = () => {
      if (!sharedColumnsKey || migratedColumnKeys.has(columnsBaseKey))
        return readDetailColumns(columnsBaseKey);
      const prefix = `${columnsBaseKey}:`;
      const dead = new Set();
      try {
        for (let index = 0; index < localStorage.length; index++) {
          const candidate = localStorage.key(index);
          if (candidate?.startsWith(`lexeditor:${prefix}`))
            dead.add(candidate.slice("lexeditor:".length));
        }
      } catch (_error) {}
      for (const candidate of Object.keys(sharedSettingsSnapshot?.viewPreferences || {}))
        if (candidate.startsWith(prefix)) dead.add(candidate);
      if (!dead.size) {
        migratedColumnKeys.add(columnsBaseKey);
        return readDetailColumns(columnsBaseKey);
      }
      const shared = readDetailColumns(columnsBaseKey);
      if (shared) {
        for (const key of dead) saveDetailColumns(key, 0);
        migratedColumnKeys.add(columnsBaseKey);
        return shared;
      }
      const path = columnsPathNow();
      if (!path.length) return 0;
      let adopted = readDetailColumns(`${columnsBaseKey}:${path.join(":")}`);
      if (!adopted) for (const key of dead)
        adopted = Math.max(adopted, readDetailColumns(key));
      if (adopted) saveDetailColumns(columnsBaseKey, adopted);
      for (const key of dead) saveDetailColumns(key, 0);
      migratedColumnKeys.add(columnsBaseKey);
      return adopted;
    };
    let columnsKey = columnsKeyNow();
    migrateSharedColumns();
    let chosenColumns = readDetailColumns(columnsKey);
    const shownColumns = () => {
      // Every visible column counts, empty ones included: they still take
      // their share of the row (the blank right side), and the deal still
      // honors them. Counting only non-empty columns read "1" on a fitted
      // three-column deal whose stored layout stacks everything left, while
      // drops landed in the "missing" columns and minus sat disabled.
      const columns = [...(detailNode?.querySelectorAll?.(".lex-tweaks-paged .lex-tweak-column") || [])]
        .filter(column => column.offsetParent);
      return chosenColumns || Math.max(1, columns.length);
    };
    const columnTally = element("output", {class: "lex-barrel-count", "aria-live": "polite"}, String(chosenColumns || ""));
    const fewerColumns = element("button", {
      class: "lex-barrel-decrease", type: "button", title: "One fewer column of details",
      "aria-label": "Decrease detail columns", onclick: () => changeColumns(shownColumns() - 1),
    });
    const moreColumns = element("button", {
      class: "lex-barrel-increase", type: "button", title: "One more column of details",
      "aria-label": "Increase detail columns", onclick: () => changeColumns(shownColumns() + 1),
    });
    const showColumnCount = () => {
      columnsKey = columnsKeyNow();
      migrateSharedColumns();
      chosenColumns = readDetailColumns(columnsKey);
      const count = shownColumns();
      columnTally.textContent = String(count);
      columnTally.title = chosenColumns ? "Your column count. Right-click to fit to width again." : "Fitted to width";
      fewerColumns.disabled = count <= 1;
      moreColumns.disabled = count >= 6;
    };
    const changeColumns = requested => {
      columnsKey = columnsKeyNow();
      chosenColumns = Math.max(0, Math.min(6, Number(requested) || 0));
      saveDetailColumns(columnsKey, chosenColumns);
      if (chosenColumns) root.dataset.lexDetailColumns = String(chosenColumns);
      else delete root.dataset.lexDetailColumns;
      detailNode?.querySelectorAll?.(".lex-tweaks-paged").forEach(paged => paged.lexFitPage?.());
      requestAnimationFrame(showColumnCount);
    };
    const columnControl = element("div", {
      class: "lex-barrel-control lex-detail-column-control",
      title: "Columns of details",
      onmouseenter: showColumnCount,
      oncontextmenu: event => { event.preventDefault(); event.stopPropagation(); changeColumns(0); },
    }, element("span", {class: "lex-barrel-label"}, "COLUMNS"),
    element("span", {class: "lex-barrel-buttons"}, fewerColumns, columnTally, moreColumns));
    const barrelGrid = element("div", {
      class: "lex-barrel-grid", style: `--lex-barrels:${masterNodes.length}`,
    }, ...masterNodes);
    const masterNode = element("div", {class: "lex-barrelled-master"}, barrelGrid);
    // A fitted master has no vertical scroll range, so its wheel turns pages.
    wheelPages(masterNode, direction => changePage(page + direction));
    const barrelPanelMinimum = Math.max(160, Number(options.minLeft) || 280) * barrels +
      7 * (barrels - 1);
    const root = leadingNode ? panelLayout([leadingNode, masterNode, detailNode],
      `lex-list-detail lex-master-detail lex-leading-list-detail ${options.className || ""}`, {
        defaultSizes: options.panelSizes || [options.defaultLeadingWidth || 25, 30, 45],
        minSizes: [Math.max(220, Number(options.minLeading) || 300), barrelPanelMinimum, Math.max(240, Number(options.minRight) || 360)],
        dividerClass: "lex-list-detail-divider",
        dividerAccessories: [null, [barrelControl, columnControl]],
      }) : trailingNode ? panelLayout([masterNode, detailNode, trailingNode],
      `lex-list-detail lex-master-detail ${options.className || ""}`, {
        defaultSizes:options.panelSizes || [30,30,40],
        minSizes:[barrelPanelMinimum, Math.max(240, Number(options.minRight) || 300), Math.max(240, Number(options.minTrailing) || 360)],
        dividerClass:"lex-list-detail-divider",
        dividerAccessories:[[barrelControl, columnControl],null],
      }) : listDetail(masterNode, detailNode, options.className || "", {
      splitKey: options.splitKey,
      defaultSplit: options.defaultSplit,
      minLeft: barrelPanelMinimum,
      minRight: options.minRight,
      // No fraction floor: barrels stand on the pixel minimum plus the
      // tables' measured widths. A share of the window only stopped the
      // panel shrinking on wide screens.
      dividerAccessories: [[barrelControl, columnControl]],
      paneClass: options.paneClass,
    });
    root.classList.add("lex-paged-list-detail");
    if (chosenColumns) root.dataset.lexDetailColumns = String(chosenColumns);
    // The count is current when the control appears, not only once touched.
    columnControl.closest(".lex-panel-layout-divider")?.addEventListener("mouseenter", showColumnCount);
    root.addEventListener("lex-column-sorted", event => {
      const index = masterNodes.indexOf(event.detail.previous);
      if (index >= 0) masterNodes[index] = event.target;
    });
    // A pin changes columns, not records: rebuild the master barrels in
    // place instead of the whole page, leaving the detail pane, its focus
    // and scroll, and its giant dropdowns, alone.
    root.refreshMaster = () => {
      masterNodes[0]?.__lexFitListObserver?.disconnect?.();
      const scrollers = [masterNode, barrelGrid, ...masterNodes];
      const scroll = scrollers.map(node => [node.scrollTop, node.scrollLeft]);
      masterNodes = buildMasters();
      barrelGrid.replaceChildren(...masterNodes);
      [masterNode, barrelGrid, ...masterNodes].forEach((node, index) => {
        if (node && scroll[index]) { node.scrollTop = scroll[index][0]; node.scrollLeft = scroll[index][1]; }
      });
      fitMasters();
      // The new columns unify across barrels and the layout refits around
      // them; heading fits registered during the build run first in the frame.
      // Shares re-derive from the defaults, so unpinning releases the room
      // pinning took instead of leaving the master stretched.
      requestAnimationFrame(() => {
        unifyBarrelTemplates(barrelGrid);
        if (root.lexResetSizes) root.lexResetSizes();
        else root.refreshLayout?.();
      });
    };
    root.refreshValues = () => { for (const node of masterNodes) node.refreshValues?.(); };
    root.pinOwner = options.columnPreferences ? null : pinOwner;
    root.dataset.lexPage = String(page);
    root.dataset.lexPageSize = String(pageSize);
    const bottomTools = [...(options.filters || [])];
    if (modOnly) {
      bottomTools.unshift(pagerToggle({
        label: modOnly.label || "Mod contents only",
        lines: modOnly.label ? undefined : ["Mod", "contents", "only"],
        title: modOnly.available === false
          ? (modOnly.unavailableTitle
            || "Available once an editable mod and its vanilla baseline are both loaded.")
          : (modOnly.title || "Show only the records this mod changes."),
        checked: modOnlyOn,
        disabled: modOnly.available === false,
        change: value => modOnly.change?.(value),
      }));
    }
    // Creation lives in the detail header: a list whose plugin owns
    // creation there passes tableAdd:false and shows no button here.
    // Lists still migrating keep the old bottom-right button meanwhile.
    if (options.tableAdd !== false) {
      // Every table has one add button, round, in its own bottom-right corner
      // and faint until pointed at. Where a record cannot be added it stays
      // there, marked unavailable, and says why when pointed at or pressed:
      // "every game, every list should have it... if disabled, it says why".
      // A plugin that builds its own add button and hands it over with the
      // pager's filters gets that button moved here, not a second one.
      const suppliedAdd = bottomTools.find(control => control?.matches?.(".lex-new-button"));
      if (suppliedAdd) bottomTools.splice(bottomTools.indexOf(suppliedAdd), 1);
      const readonlySource = document.documentElement.dataset.lexProjectReadonly === "true";
      // A slot table cannot grow, but one that knows its empty slots fills the
      // next one: Add hands the plugin that slot (Lexer: "i distinctly remember
      // you saying that there were empty slots for things").
      const claimsEmpty = slotBased && Boolean(emptyRow) && typeof options.add === "function"
        && options.addDisabled !== true;
      const pluginAdd = suppliedAdd ? !suppliedAdd.disabled
        : claimsEmpty ? emptyCount > 0
        : !slotBased && typeof options.add === "function" && options.addDisabled !== true;
      const canAdd = pluginAdd && !readonlySource;
      const addWhy = canAdd ? "" : readonlySource
        ? "This is the game's own data, shown read-only. Create a mod to add records to it."
        : options.addDisabledReason || (suppliedAdd || options.addDisabled === true
          ? "Adding is unavailable right now."
          : claimsEmpty
            ? `Every slot in this table is in use, so there is no room to add ${options.noun || "records"}.`
          : slotBased
            ? `This table is a fixed set of slots in the game's data, so there is no room to add ${options.noun || "records"}.`
            : `Adding ${options.noun || "records"} to this table is not supported yet.`);
      const tableAdd = suppliedAdd || newButton({title: options.addTitle || `Add ${options.noun || "record"}`,
        onclick: event => {
          event.stopPropagation();
          if (!canAdd) return;
          if (!claimsEmpty) { options.add(); return; }
          // The slot being filled must be on screen, so Hide empty lets go.
          if (hideEmpty) saveHideEmpty(hideEmptyKey, false);
          options.add(allRows.find(record => emptyRow(record)));
        }});
      tableAdd.disabled = false;
      tableAdd.classList.add("lex-table-add");
      tableAdd.classList.toggle("unavailable", !canAdd);
      if (canAdd) tableAdd.removeAttribute("aria-disabled");
      else {
        tableAdd.setAttribute("aria-disabled", "true");
        tableAdd.title = addWhy;
        tableAdd.setAttribute("aria-label", addWhy);
      }
      // Capturing on the button itself runs before the handler it was built
      // with, so an unavailable button explains itself instead of acting.
      tableAdd.addEventListener("click", event => {
        if (canAdd) return;
        event.stopImmediatePropagation();
        event.preventDefault();
        showToast(addWhy);
      }, {capture: true});
      hoverActions(masterNode, {label: "Table actions", align: "bottom-right", actions: [{node: tableAdd}]});
    }
    if (emptyRow) {
      const toggle = element("input", {
        type: "checkbox", checked: hideEmpty, "aria-label": "Hide empty slots",
        onchange: event => {
          saveHideEmpty(hideEmptyKey, event.target.checked);
          change("hide-empty", {page: 0});
        },
      });
      bottomTools.push(element("label", {
        class: `lex-hide-empty${hideEmpty ? " active" : ""}`,
        title: emptyCount
          ? `${formatNumber(emptyCount)} of these ${formatNumber(suppliedRows.length)} slots are empty.`
          : "No slot in this table is empty.",
      }, toggle, element("span", {}, "HIDE EMPTY")));
    }
    const hasBottomTools = Boolean(options.search || bottomTools.length);
    if (pages > 1 || hasBottomTools) {
      const setPageSize = requested => {
        const nextSize = saveTableRows(rowPreferenceKey, requested);
        if (nextSize === pageSize) return;
        typedRowsKey = rowPreferenceKey;
        const selectedIndex = records.findIndex(record => keyOf(record) === selected);
        const anchor = selectedIndex >= 0 ? selectedIndex : groupStart;
        const nextBarrelSize = nextSize * barrels;
        const nextPages = Math.max(1, Math.ceil(records.length / nextBarrelSize));
        const nextPage = Math.max(0, Math.min(Math.floor(anchor / nextBarrelSize), nextPages - 1));
        change("table-rows", {page: nextPage, pageSize: nextSize});
      };
      const rowControl = sharedSettingsSnapshot?.developerMode ? {
        value: pageSize,
        max: 80,
        defaultValue: globalPageSize,
        overridden: hasRowOverride,
        change: setPageSize,
        clear: () => {
          if (!hasTableRowsOverride(rowPreferenceKey)) return;
          clearTableRows(rowPreferenceKey);
          const selectedIndex = records.findIndex(record => keyOf(record) === selected);
          const anchor = selectedIndex >= 0 ? selectedIndex : groupStart;
          const nextBarrelSize = globalPageSize * barrels;
          const nextPages = Math.max(1, Math.ceil(records.length / nextBarrelSize));
          const nextPage = Math.max(0, Math.min(Math.floor(anchor / nextBarrelSize), nextPages - 1));
          change("table-rows-clear", {page: nextPage, pageSize: globalPageSize});
        },
      } : null;
      const pagerNode = pager({inline:options.inlinePager===true,page, pages, total: records.length, pageSize: barrelSize,
        noun: options.noun, change: changePage, search: options.search, filters: bottomTools,
        rowControl});
      root.classList.add("lex-paged-list-detail", "has-pager");
      root.append(pagerNode);
      // "41-80/144" describes a contiguous run of records, which is true only
      // while a slot table is in ID order. Sorted by anything else, the two
      // ends of the range mean nothing, so state how many of the total are on
      // screen instead.
      const summary = pagerNode.querySelector(".lex-page-summary");
      if (summary && slotBased) {
        const range = summary.textContent;
        const restate = () => {
          const sorted = masterNode.querySelector(".lex-column-list-head-cell.sorted");
          const byRecordId = !sorted || sorted.dataset.lexIdColumn === "true";
          summary.textContent = byRecordId
            ? range
            : `${formatNumber(shown.length)}/${formatNumber(records.length)}`;
        };
        requestAnimationFrame(restate);
        root.addEventListener("lex-column-sorted", restate);
      }
      const measurePager = () => {
        const height = Math.ceil(pagerNode.getBoundingClientRect().height);
        const value = `${height}px`;
        if (height && root.style.getPropertyValue("--lex-pager-height") !== value) {
          root.style.setProperty("--lex-pager-height", value);
          if(options.inlinePager!==true)document.documentElement.style.setProperty("--lex-pager-height", value);
        }
      };
      requestAnimationFrame(() => requestAnimationFrame(measurePager));
      document.fonts?.ready?.then(measurePager).catch(() => {});
      // The reserved space is a measured number, and the bar can change height
      // at any time: the reader picks the pagination bar height in Settings,
      // long after a page was built. Watching the bar for its whole life - not
      // for its first ten seconds - keeps the reserved space equal to the bar,
      // so lowering the height resizes the page instead of leaving a band of
      // empty space above the bar until the page is rebuilt.
      if (window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          if (!root.isConnected) { observer.disconnect(); return; }
          measurePager();
        });
        observer.observe(pagerNode);
      }
      const remeasureOnSettings = () => {
        if (!root.isConnected) {
          window.removeEventListener("lexeditor-settings-changed", remeasureOnSettings);
          return;
        }
        measurePager();
      };
      window.addEventListener("lexeditor-settings-changed", remeasureOnSettings);
    }

    if (sharedSettingsSnapshot === null) {
      window.addEventListener("lexeditor-view-preferences-ready", () => {
        if (!root.isConnected) return;
        const saved = Math.min(oldPages, readBarrelCount(preferenceKey, barrels, maximumBarrels));
        if (saved !== barrels) changeBarrels(saved);
      }, {once: true});
    }

    const useSavedTableRows = settings => {
      if (!root.isConnected) return;
      const nextSize = readTableRows(rowPreferenceKey,
        boundedTableRows(settings?.tableRowsPerPage || pageSize));
      if (nextSize === pageSize) return;
      const selectedIndex = records.findIndex(record => keyOf(record) === selected);
      const anchor = selectedIndex >= 0 ? selectedIndex : groupStart;
      const nextBarrelSize = nextSize * barrels;
      const nextPages = Math.max(1, Math.ceil(records.length / nextBarrelSize));
      const nextPage = Math.max(0, Math.min(Math.floor(anchor / nextBarrelSize), nextPages - 1));
      change("table-rows", {page: nextPage, pageSize: nextSize});
    };
    window.addEventListener("lexeditor-view-preferences-ready", () =>
      useSavedTableRows(sharedSettingsSnapshot), {once: true});
    window.addEventListener("lexeditor-settings-changed", event =>
      useSavedTableRows(event.detail), {once: true});

    // New barrels start without fitted rows, and their text falls back to
    // the default size; a pin rebuild re-fits them from the cached geometry.
    const fitMasters = () => {
      if (options.fit === false || !masterNodes[0]) return;
      const fit = options.fit || {};
      const searchActive = Boolean(String(options.search?.value ?? options.search?.query ?? "").trim());
      fitListPage({
        cacheKey:rowPreferenceKey,
        list: masterNodes[0],
        lists: masterNodes,
        available: root,
        pageSize,
        // A short table still declares a full page of fixed rows: capping the
        // count at its own records stretched its rows to fill the panel.
        fixedRows: fitMinimum ? requestedPageSize :
          searchActive ? pageSize : (pages === 1 ? Math.max(1, ...barrelRows.map(rows => rows.length)) : pageSize),
        minRowHeight: fitMinimum,
        visibleRows: () => searchActive ? pageSize : Math.max(1, ...barrelRows.map(rows => rows.length)),
        rowSelector: fit.rowSelector,
        headerSelector: fit.headerSelector,
        resize: (height, measurement) => {
          // A stacked (single-column) page must not pin both panes to the
          // fitted table height: the grid rows already bound master and
          // detail, and equal inline heights overlap them.
          const tracks = getComputedStyle(root).gridTemplateColumns.split(" ");
          const stacked = tracks.length < 2 && tracks[0] !== "none";
          const fittedHeight = measurement?.full && !stacked ? `${height}px` : "";
          masterNode.style.height = fittedHeight;
          // The class stops the panes stretching to their row, so it goes on
          // only with the heights that replace the stretch. A fit that ran
          // before the page was attached read the grid as stacked, pinned
          // nothing and still set it, and the detail panel shrank to its
          // content - most of it blank - until the next fit: the flash on
          // clicking a tab that is already open.
          root.classList.toggle("lex-full-table-page", Boolean(fittedHeight));
          detailNode.style.height = fittedHeight;
        },
        change: nextSize => {
          if (fitMinimum) tableFitCapacityCache.set(rowPreferenceKey, {capacity: nextSize, requested: requestedPageSize});
          typedRowsKey = null;
          const selectedIndex = records.findIndex(record => keyOf(record) === selected);
          const anchor = selectedIndex >= 0 ? selectedIndex : groupStart;
          const nextBarrelSize = nextSize * barrels;
          const nextPages = Math.max(1, Math.ceil(records.length / nextBarrelSize));
          const nextPage = Math.max(0, Math.min(Math.floor(anchor / nextBarrelSize), nextPages - 1));
          const applyResize = () => {
            if (!root.isConnected) return;
            if (detailNode.contains(document.activeElement)) {
              detailNode.addEventListener("focusout", () => setTimeout(applyResize, 0), {once:true});
              return;
            }
            change("resize", {page: nextPage, pageSize: nextSize});
          };
          applyResize();
        },
      });
    };
    fitMasters();
    // Barrels line up their columns and ask for content width once laid
    // out; heading fits registered during the build run first in the frame.
    requestAnimationFrame(() => {
      if (!barrelGrid.isConnected) return;
      unifyBarrelTemplates(barrelGrid);
      root.refreshLayout?.();
    });
    document.fonts?.ready.then(() => {
      if (!barrelGrid.isConnected) return;
      unifyBarrelTemplates(barrelGrid);
      root.refreshLayout?.();
    });
    return root;
  };

  const shortReferenceName = source => {
    if (source.shortName) return source.shortName;
    const normalized = String(source.name || "").trim().toLocaleLowerCase();
    if (normalized === "vanilla") return "V";
    if (["lexer", "lexer lux", "lexer-lux", "lexer's mod", "lexers mod", "lexers-mod"].includes(normalized)) return "LL";
    const words = String(source.name || "").trim().split(/\s+/).filter(Boolean);
    if (words.length > 1) return words.map(word => word[0]).join("").slice(0, 3).toLocaleUpperCase();
    return String(source.name || "").slice(0, 5).toLocaleUpperCase();
  };

  // A reference rail is a narrow, fixed lane. A value that does not fit it is
  // shortened rather than allowed to widen the lane, because the lane widening
  // moves every value box on the panel. Thousands become 12K, millions 3.4M,
  // billions 1.2B; the exact number stays on the entry's tooltip.
  const REFERENCE_VALUE_CHARACTERS = 6;
  // Words get more room than digits: a number past six digits says as much
  // shortened to 1.2M, while "default" cut to "defau…" says nothing.
  const REFERENCE_WORD_CHARACTERS = 10;
  const compactReferenceNumber = value => {
    const numeric = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(numeric)) return String(value);
    const plain = formatNumber(numeric);
    if (plain.replace("-", "").length <= REFERENCE_VALUE_CHARACTERS) return plain;
    const sign = numeric < 0 ? "-" : "";
    const size = Math.abs(numeric);
    for (const [limit, suffix] of [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]]) {
      if (size < limit) continue;
      const scaled = size / limit;
      // One decimal while it earns its place: 1.2M says more than 1M, 340M
      // needs no decimal and has no room for one.
      const text = scaled < 10 ? scaled.toFixed(1).replace(/\.0$/, "") : String(Math.round(scaled));
      return `${sign}${text}${suffix}`;
    }
    // A long decimal is trimmed from the right, where the least of it lives.
    return plain.slice(0, REFERENCE_VALUE_CHARACTERS + sign.length);
  };
  const compactReferenceText = value => {
    const text = String(value);
    return text.length <= REFERENCE_WORD_CHARACTERS
      ? text : `${text.slice(0, REFERENCE_WORD_CHARACTERS - 1)}…`;
  };

  const booleanMark = value => element("span", {
    class: `lex-boolean-mark ${value ? "true" : "false"}`,
    "aria-label": value ? "Yes" : "No",
  }, value ? "✓" : "×");

  // One compact comparison display for every plugin. Matching sources carry no
  // information, so only differing values are rendered. If all available
  // sources match, the complete display disappears.
  const referenceDisplay = options => {
    const format = options.format || (value => {
      if (typeof value === "boolean") return booleanMark(value);
      if (typeof value === "number") return compactReferenceNumber(value);
      if (typeof value === "string" && /^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value.trim())) return compactReferenceNumber(value);
      return compactReferenceText(value);
    });
    const same = options.same || ((left, right) => JSON.stringify(left) === JSON.stringify(right));
    const configuredSources = options.sources || [];
    if (configuredSources.length > 3) {
      throw new RangeError("Reference stacks support Vanilla plus at most two reference mods.");
    }
    const hasCurrent = options.current !== undefined;
    const sources = configuredSources.map((source, referenceIndex) => ({...source, referenceIndex})).filter(source =>
      source.value !== undefined && (!hasCurrent || !same(options.current, source.value)));
    if (!sources.length) return null;
    return element("div", {
      class: ["lex-source-strip", "lex-reference-values", options.className || ""].filter(Boolean).join(" "),
      "aria-label": "Reference values",
      style: `--lex-reference-count:${sources.length}`,
      "data-reference-count": String(sources.length),
    }, ...sources.map(source => {
      const formatted = format(source.value, source);
      // The rail may have shortened what it paints; the tooltip says the whole
      // value, because that is what pressing the entry writes into the box.
      const exact = typeof source.value === "boolean"
        ? (source.value ? "Yes" : "No")
        : typeof source.value === "number" ? formatNumber(source.value) : String(source.value);
      return element("button", {
        type: "button",
        class: ["lex-reference-value", `lex-reference-slot-${source.referenceIndex}`, source.className || ""].filter(Boolean).join(" "),
        "data-reference-index": String(source.referenceIndex),
        disabled: !!options.readOnly,
        title: `Use ${source.name}: ${exact}`,
        onclick: event => options.apply?.(clone(source.value), event, source),
      },
      element("span", {class: `lex-reference-tag${shortReferenceName(source) === "LL" ? " lex-reference-ll" : ""}`}, shortReferenceName(source)),
      element("span", {class: "lex-reference-text"}, formatted));
    }));
  };

  // Games supply values and the apply callback; the shared framework owns the
  // source labels, comparison, compact layout, and restore interaction.
  const provenanceControl = options => {
    // A value with a unit shows its references with that unit too ("V 16%"),
    // whichever plugin built it: the unit comes from the unitField.
    const unitHost = options.control instanceof Element
      ? (options.control.matches("[data-lex-unit]") ? options.control : options.control.querySelector("[data-lex-unit]")) : null;
    const unit = unitHost?.dataset.lexUnit || "";
    if (unit && !options.format) {
      const tight = /^[%×°'"]$/.test(unit);
      options = {...options, format: value => {
        if (typeof value !== "number") return typeof value === "boolean" ? booleanMark(value) : compactReferenceText(value ?? "");
        const number = compactReferenceNumber(value);
        if (unitHost.dataset.lexUnitPosition === "prefix") return `${unit}${number}`;
        return tight ? `${number}${unit}` : `${number} ${unit}`;
      }};
    }
    // A checkbox paints its references as ticks, whatever type the game
    // stores: "V 0" on a boolean reads as a value, not as off.
    const checkHost = options.control instanceof Element
      ? (options.control.matches("input[type=checkbox]") ? options.control : options.control.querySelector("input[type=checkbox]")) : null;
    if (checkHost && !options.format) {
      options = {...options, format: value => booleanMark(
        !(value === false || value === 0 || value === "0" || value === "" || value === null || value === undefined))};
    }
    const sources = [
      {name: options.vanillaName || "Vanilla", shortName: options.vanillaShortName || "V", value: options.vanilla},
      ...(options.references || []),
    ];
    // References live INSIDE the value box by default. An outside pillar
    // reserves a lane on the right of every box on the panel, which is a band
    // of empty ground on every property that has nothing to compare. A caller
    // that wants the outside pillar asks for it with internal:false; a control
    // with no box to put a reference in - a checkbox - never gets one.
    const boxed = options.control instanceof Element &&
      options.control.matches?.("input:not([type=checkbox]):not([type=range]),select,textarea,output,.lex-unit-field,.lex-readonly-field,.lex-inline-label:has(> select)");
    const multiline = options.control?.matches?.('textarea:not(.lex-code-field)');
    const internal = !multiline && (options.internal === undefined ? boxed : options.internal !== false);
    const stacked = !internal && options.control?.matches?.("textarea,.lex-choice-field,.lex-stack");
    const root = element("div", {
      class: ["lex-source-control", internal ? "lex-source-control-internal" : "", stacked ? "lex-source-control-stacked" : ""].filter(Boolean).join(" "),
    }, options.control);
    const readOnly = () => (typeof options.readOnly === "function" ? options.readOnly() : options.readOnly === true)
      || !!options.control?.matches?.(":disabled,[readonly]");
    // A number sharing its box with a reference gets its own up and down at
    // the box's right edge. The browser's arrows sit at the end of the text,
    // so the space kept for the reference showed as an empty band to the
    // right of them, and the arrows jumped left whenever a reference appeared.
    const numberBox = internal && options.control instanceof Element
      ? (options.control.matches("input[type=number]") ? options.control : options.control.querySelector(":scope > input[type=number]"))
      : null;
    if (numberBox) {
      root.classList.add("lex-has-stepper");
      const step = direction => event => {
        event.preventDefault();
        if (numberBox.disabled || numberBox.readOnly) return;
        try { direction > 0 ? numberBox.stepUp() : numberBox.stepDown(); }
        catch (_error) { numberBox.value = String((Number(numberBox.value) || 0) + direction); }
        numberBox.dispatchEvent(new Event("input", {bubbles: true}));
        numberBox.dispatchEvent(new Event("change", {bubbles: true}));
      };
      const arrow = (direction, label) => element("button", {type: "button", tabindex: "-1", "aria-hidden": "true",
        class: direction > 0 ? "lex-stepper-up" : "lex-stepper-down", title: label,
        onpointerdown: event => event.preventDefault(), onclick: step(direction)});
      root.append(element("span", {class: "lex-stepper"}, arrow(1, "Increase"), arrow(-1, "Decrease")));
    }
    // What the rail must hold is decided by the sources, which do not change
    // while a value is edited - not by which of them happen to differ from the
    // value right now. Measuring the visible entries instead made the rail
    // breathe every time an edit matched or stopped matching vanilla, and the
    // whole column of value boxes moved with it.
    const painted = source => {
      // What the entry PAINTS, which for a boolean is one tick rather than
      // the word "true". Reserving for the word made every rail on a panel
      // holding one boolean four characters wider than anything in it.
      const formatted = (options.format || (value => typeof value === "boolean"
        ? booleanMark(value)
        : typeof value === "number" ? compactReferenceNumber(value)
        : compactReferenceText(value ?? "")))(source.value, source);
      return formatted instanceof Node ? formatted.textContent : String(formatted);
    };
    const widestOf = pick => sources.map(pick).reduce((longest, text) =>
      text.length > longest.length ? text : longest, "");
    const canReference = sources.some(source => source.value !== undefined);
    const widestTag = widestOf(shortReferenceName);
    const widestValue = widestOf(painted);
    const referenceCharacters = Math.max(1, widestTag.length + widestValue.length + 1);
    if (internal) {
      // Internal references share the live control's box. Size the reserved
      // lane from the actual tag+value character count with enough average
      // glyph width for game fonts; the old .38em estimate clipped values such
      // as "V DEFAULT" and two-digit numbers against native select chrome.
      // The lane is measured from what this rail can paint, once the control is
      // in the document and its font has resolved; the alignment pass does that
      // and needs the longest entry this control can ever show.
      root.dataset.lexInsideTag = widestTag;
      root.dataset.lexInsideValue = widestValue;
      // Marked so the alignment pass measures this rail against the box it
      // shares rather than against a property row it has nothing to do with.
      root.dataset.lexInsideRail = widestTag;
    } else {
      // Sizing the rail per control makes value boxes on the same panel end at
      // different edges, because one reference reading "V 25" needs less room
      // than one reading "R1 130". The requirement is recorded here as the
      // longest tag and the longest value this control can ever show, and the
      // panel-wide pass below turns the widest of those into one rail.
      root.dataset.lexRailTag = widestTag;
      root.dataset.lexRailValue = widestValue;
    }
    const currentValue = () => typeof options.current === "function" ? options.current() : options.current;
    root.lexVanillaValue = () => options.vanilla;
    root.lexRevert = event => {
      // A right-click reset must not move the reader: route through the
      // vanilla rail entry when one is painted, so the same scroll-preserving
      // apply runs as for a rail click. The old selector looked for a button
      // inside the entry, but the entry IS the button, so it never matched
      // and every reset rebuilt without restoring the reader's place.
      const same = options.same || ((left, right) => JSON.stringify(left) === JSON.stringify(right));
      if (options.vanilla !== undefined && same(currentValue(), options.vanilla)) {
        refresh();
        return true;
      }
      const vanillaEntry = root.querySelector('.lex-reference-values .lex-reference-value[data-reference-index="0"]');
      if (vanillaEntry instanceof HTMLElement) { vanillaEntry.click(); return true; }
      if (!readOnly()) options.apply?.(options.vanilla, event, sources[0]);
      refresh();
      return true;
    };
    let lastReferenceState;
    const refresh = () => {
      const value = currentValue(), locked = readOnly();
      const same = options.same || ((a,b)=>JSON.stringify(a)===JSON.stringify(b));
      const referenceState = JSON.stringify([value, locked, sources,
        sources.map(source => [painted(source), same(value, source.value)])]);
      // Shell refreshes visit every control. Preserve unchanged strips so one
      // edit does not replace hundreds of nodes and invalidate their layout.
      if (referenceState === lastReferenceState && root.querySelector(
          ":scope > :is(.lex-reference-values,.lex-reference-placeholder)")) return;
      lastReferenceState = referenceState;
      root.classList.toggle("lex-value-modified", options.vanilla !== undefined && !same(value,options.vanilla));
      root.querySelector(":scope > :is(.lex-reference-values,.lex-reference-placeholder)")?.remove();
      const reference = referenceDisplay({
        current: value, sources, format: options.format, same: options.same, readOnly: locked,
        apply: (value, event, source) => {
          if (readOnly()) return;
          const selector = "main,.lex-shell-main,.lex-panel-layout-pane,.lex-detail,.lex-barrelled-master,.lex-column-list,.lex-data-map-view";
          const ordinals = new Map();
          const scroll = [...document.querySelectorAll(selector)].map(node => {
            const identity = node.id
              ? `#${CSS.escape(node.id)}`
              : `${node.tagName.toLocaleLowerCase()}${[...node.classList].map(name => `.${CSS.escape(name)}`).join("")}`;
            const ordinal = ordinals.get(identity) || 0;
            ordinals.set(identity, ordinal + 1);
            return {identity, ordinal, top: node.scrollTop, left: node.scrollLeft};
          });
          const windowScroll = {x: window.scrollX, y: window.scrollY};
          options.apply?.(value, event, source);
          refresh();
          const restoreScroll = () => {
            for (const entry of scroll) {
              const node = document.querySelectorAll(entry.identity)[entry.ordinal];
              if (!node) continue;
              node.scrollTop = entry.top;
              node.scrollLeft = entry.left;
            }
            window.scrollTo(windowScroll.x, windowScroll.y);
          };
          const scrollObservers = [];
          if (typeof ResizeObserver !== "undefined") {
            for (const entry of scroll.filter(value => value.top > 0 || value.left > 0)) {
              const node = document.querySelectorAll(entry.identity)[entry.ordinal];
              if (!node) continue;
              const observer = new ResizeObserver(() => {
                node.scrollTop = entry.top;
                node.scrollLeft = entry.left;
                const maxTop = Math.max(0, node.scrollHeight - node.clientHeight);
                const maxLeft = Math.max(0, node.scrollWidth - node.clientWidth);
                const topReady = entry.top <= 0 || (maxTop > 0 && Math.abs(node.scrollTop - Math.min(entry.top, maxTop)) <= 1);
                const leftReady = entry.left <= 0 || (maxLeft > 0 && Math.abs(node.scrollLeft - Math.min(entry.left, maxLeft)) <= 1);
                if (topReady && leftReady) observer.disconnect();
              });
              observer.observe(node);
              scrollObservers.push(observer);
            }
            setTimeout(() => scrollObservers.forEach(observer => observer.disconnect()), 2000);
          }
          // A game-owned apply handler can replace the panel synchronously,
          // while fitted-table layout can settle over the next two frames.
          // Restore at all three points so neither rebuild resets the reader.
          restoreScroll();
          requestAnimationFrame(() => {
            restoreScroll();
            requestAnimationFrame(restoreScroll);
          });
        },
      });
      root.style.setProperty("--lex-reference-count", reference?.dataset.referenceCount || "1");
      // Keep the reference rail in the grid even while all values match. A
      // reference that appears after an edit must not resize or shift the live
      // control beside it.
      root.append(reference || element("span", {
        class: "lex-source-strip lex-reference-placeholder",
        "aria-hidden": "true",
      }));
      // The rail belongs to the control, not to today's values. Dropping the
      // column the moment every reference matched was what made a value box
      // jump wider the instant an edit landed on vanilla and snap back on the
      // next keystroke. A control with nothing to compare against still
      // collapses, because it has no rail to hold.
      root.classList.toggle("no-reference", !canReference);
    };
    // Run after the game-owned listener has updated its model, but do not wait
    // for a new frame or a tab rebuild. Waiting caused editable tables to show
    // stale Vanilla/reference values until the player left the tab.
    options.control?.addEventListener?.("input", refresh);
    options.control?.addEventListener?.("change", refresh);
    refresh();
    // A box too narrow to read a reference beside its value keeps the
    // value: the rail and stepper hide until the box has room again.
    // Unit boxes already compact through followUnit; every other
    // internal box compacts here, by the same width.
    if (internal && !unitHost && options.control instanceof Element
        && typeof ResizeObserver !== "undefined") {
      const box = options.control;
      const place = () => placeCompactBox(root, box);
      new ResizeObserver(place).observe(box);
      requestAnimationFrame(place);
    }
    root.refreshReference = refresh;
    return root;
  };

  const integrationStatus = status => {
    const normalized = status === "integrated" || status === "partial" ? status : "not-integrated";
    const labels = {integrated: "Integrated", partial: "Partial", "not-integrated": "Not integrated"};
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("width", "20");
    icon.setAttribute("height", "20");
    icon.setAttribute("aria-hidden", "true");
    icon.classList.add("lex-status-mark");
    icon.innerHTML = normalized === "integrated"
      ? '<path d="m4 12 5 5L20 6" fill="none" stroke="currentColor" stroke-width="3"/>'
      : normalized === "partial"
        ? '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4a8 8 0 0 1 0 16Z" fill="currentColor"/>'
        : '<path d="m6 6 12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="3"/>';
    return element("span", {
      class: `lex-integration-status ${normalized}`,
      title: labels[normalized],
      "aria-label": labels[normalized],
    }, icon);
  };

  // One fitted Table + Detail map for every plugin. Coverage is an explicit
  // user-interface claim, never inferred from a parser or a legacy green badge.
  // Every plugin states the same five things about its mod loader, in the same
  // order, in the same words. Left to each plugin these went missing entirely:
  // five of eight editors said nothing at all about how their output is loaded.
  const MOD_LOADER_FIELDS = [
    ["LOADER", "loader", "Which loader or mechanism the game uses to read this plugin's output."],
    ["OUTPUT", "output", "Where Lexeditor writes, and what the game reads."],
    ["LOAD ORDER", "order", "How this output orders against other mods."],
    ["SAFETY", "safety", "What Lexeditor never modifies in the installed game."],
    ["REMOVING", "removal", "How to take the changes back out."],
  ];
  const modLoaderSection = (spec = {}) => detailSection({
    title: "MOD LOADER",
    body: MOD_LOADER_FIELDS.map(([label, key, fallback]) => detailField({
      label,
      control: readonlyField(String(spec[key] || "").trim() || fallback),
      help: infoHelp(fallback),
    })),
  });

  const dataMapState = new Map();
  const dataMap = options => {
    const plugin = document.body.dataset.lexPlugin || "plugin";
    const stateKey = options.searchKey || `${plugin}-data-map`;
    const saved = dataMapState.get(stateKey) || {pageSize:15, selected:null};
    dataMapState.set(stateKey, saved);
    const labels = {integrated:"Integrated", partial:"Partial", "not-integrated":"Not integrated"};
        const status = row => Object.hasOwn(labels,row.status) ? row.status : "not-integrated";
        const label = row => labels[status(row)];
        const coverage = row => row.coverage;
        // The file is the row's identity, so it is the key for the two prose
        // lines a developer can reword. The handler is delegated: the detail
        // pane is rebuilt whenever a row is clicked, and a listener on the line
        // itself would be thrown away between the two clicks of a double-click.
        const proseKey = (row, field) =>
          `${plugin}-${activePageTab()}.datamap.${row.filename}.${field}`;
    const keyOf = row => row.id || `${row.filename}\u001f${row.controls || ""}`;
    const query = String(options.query || "").trim().toLocaleLowerCase();
    const wanted = options.status || "";
    const [sortKey, direction] = options.sort || ["filename", 1];
    const filtered = (options.rows || []).filter(row => (!wanted ||
      status(row)===wanted) &&
      (!query || [row.filename,row.controls,row.notes,label(row)].some(value=>String(value||"").toLocaleLowerCase().includes(query))))
      .sort((a,b)=>direction*String(sortKey==="status"?label(a):a[sortKey]||"").localeCompare(
        String(sortKey==="status"?label(b):b[sortKey]||""),undefined,{numeric:true}));
    const statusFilter = element("select", {"aria-label":"Filter files by integration",
      onchange:event=>options.changeStatus?.(event.target.value)},
      ...[["","All integration states"],...Object.entries(labels)].map(([value,text])=>{
        const option=element("option",{value},text);option.selected=value===wanted;return option;
      }));
    const detail = row => {
      // Both prose lines carry the sentence they shipped with, so a reworded
      // line can be traced back to it: clearing the line restores the shipped
      // sentence rather than leaving an empty paragraph.
      const shippedControls = row.controls || "No mapped interface";
      const shippedNotes = row.notes || "No further notes.";
      const prose = (className, field, shipped) => element("p",
        {class: className, "data-lex-shipped": shipped, "data-lex-prose": field},
        element("span", {class: "lex-data-map-prose"},
          savedLabel(proseKey(row, field), shipped)));
      const body = [prose("lex-data-map-scope", "controls", shippedControls),
        prose("lex-data-map-notes", "notes", shippedNotes)];
      const actions=[];
      const targets = row.targets || (row.target || row.view ? [{id:row.target || row.view,label:row.target || row.view}] : []);
      if (["structured","view"].includes(coverage(row)) && options.open) {
        for (const target of targets) {
          const id=typeof target==="string"?target:target.id;
          const text=typeof target==="string"?target:target.label || target.id;
          actions.push(element("button",{type:"button",class:"lex-data-map-open",onclick:()=>options.open({...row,target:id,view:id})},`Open ${text}`));
        }
      }
      if (options.openSource && (row.sourceOpenable || (coverage(row)==="source" && row.openable)))
        actions.push(element("button",{type:"button",class:"lex-data-map-source",onclick:()=>options.openSource(row)},"Edit source only"));
      const path=element("span",{class:"lex-data-map-path"},row.path || row.sourcePath || row.filename);
      const folder=element("button",{type:"button",class:"lex-data-map-location","aria-label":"Open file location",
        onclick:async()=>{try{const opened=await callWindow("open_game_data_location",plugin,row.filename);
          if(opened===false)throw new Error("Open this page in the desktop editor to reveal original files.");
        }catch(error){showToast(error.message || String(error),true)}}},folderIcon());
      callWindow("game_data_location",plugin,row.filename).then(result=>{
        if(result?.path){path.textContent=result.path;path.title=result.path;}
      }).catch(()=>{});
      body.push(element("div",{class:"lex-data-map-actions"},...actions));
      return detailPanel({className:"lex-data-map-detail",title:row.filename,meta:element('div',{class:'lex-data-map-file'},folder,path),identity:integrationStatus(status(row)),body});
    };
    let page = Number(options.page)||0;
    const content = pagedListDetail({
      rows:filtered,key:keyOf,slots:true,noun:"files",page,pageSize:saved.pageSize,
      selected:saved.selected,revealSelected:false,fit:{minRowHeight:34},maxBarrels:1,
      className:"lex-data-map lex-data-map-view",splitKey:`${stateKey}-split`,rowsKey:`${stateKey}-rows`,
      defaultSplit:54,minLeft:280,minRight:240,
      search:{key:stateKey,value:options.query || "",label:"Search the data map",
        placeholder:"Search filenames, systems, or notes…",change:options.changeQuery},filters:[statusFilter],
      sync:next=>{Object.assign(saved,next);page=next.page},
      change:next=>{Object.assign(saved,next);options.changePage?.(next.page)},
      emptyDetail:()=>detailPanel({className:"lex-data-map-detail",title:"Data Map",body:[element("p",{},"No files match this filter.")]}),
      master:({rows,selected,select})=>columnList({rows,key:keyOf,selected,select,
        class:`lex-data-map-table ${options.tableClass || ""}`,
        template:"max-content minmax(100px,1.2fr) minmax(80px,1fr)",
        sortState:{key:sortKey,dir:direction},sort:options.changeSort,
        columns:[{key:"status",label:enabledMark,headerTitle:"Integration",width:"max-content",
            sortable:true,align:"center",render:row=>integrationStatus(status(row))},
          {key:"filename",label:"Filename",sortable:true,align:"start"},
          {key:"controls",label:"What it controls",sortable:true,align:"start"}]}),
      detail,
    });
    // A delegated listener on the whole view: the detail pane's lines are
    // rebuilt whenever a row is clicked, so the handler has to live above them.
    content.addEventListener("dblclick", event => {
      if (!sharedSettingsSnapshot?.developerMode) return;
      const line = event.target?.closest?.("[data-lex-prose]");
      if (!line || !content.contains(line)) return;
      const row = (options.rows || []).find(candidate => keyOf(candidate) === saved.selected);
      const text = line.querySelector(":scope > .lex-data-map-prose");
      if (!row || !text) return;
      event.preventDefault();
      event.stopPropagation();
      renameInPlace(proseKey(row, line.dataset.lexProse), activePageTab(),
        line.dataset.lexShipped || text.textContent, text);
    });
    return {controls:[],content,page,pages:Math.max(1,Math.ceil(filtered.length/saved.pageSize)),filtered};
  };

  const platformConfigView = options => {
    const config = options.config || {};
    if (!config.available) return element("section", {class: "lex-platform-config-unavailable"},
      element("h2", {}, `${config.runtime || "Mod platform"} settings`),
      element("p", {}, config.message || "The mod platform configuration is not available."),
      element("code", {}, config.path || "Configuration path unavailable"));
    const query = String(options.query || "").trim().toLocaleLowerCase();
    const controlFor = field => {
      const common = {disabled: !!options.disabled, "aria-label": field.label};
      if (field.kind === "boolean") return element("input", {...common, type: "checkbox", checked: !!field.value,
        onchange: event => options.change(field.id, event.target.checked)});
      if (field.kind === "enum") {
        const select = element("select", {...common, onchange: event => options.change(field.id, Number(event.target.value))},
          ...field.choices.map(choice => element("option", {value: choice.value}, `${choice.value} — ${choice.label}`)));
        select.value = String(field.value);
        return select;
      }
      if (field.kind === "integer" || field.kind === "number") return element("input", {...common, type: "number",
        min: field.minimum, max: field.maximum, step: field.step || (field.kind === "integer" ? 1 : "any"), value: field.value,
        oninput: event => { if (event.target.value !== "") options.change(field.id, field.kind === "integer" ? Number.parseInt(event.target.value, 10) : Number(event.target.value)); }});
      const shown = field.kind === "list" ? field.value.join(", ") : field.value;
      return element("input", {...common, type: "text", value: shown,
        oninput: event => options.change(field.id, field.kind === "list" ? event.target.value.split(",").map(value => value.trim()).filter(Boolean) : event.target.value)});
    };
    const sections = config.sections.flatMap(section => {
      const fields = section.fields.map(field => {
        const searchText = `${section.label} ${field.label} ${field.key} ${field.description}`.toLocaleLowerCase();
        const control = controlFor(field);
        const node = detailPanel({
          className: "lex-platform-config-field lex-platform-config-section", title: field.label,
          help: field.description || null,
          actions: field.kind === "boolean" ? control : null,
          body: field.kind === "boolean" ? [] : control,
        });
        node.dataset.platformSearch = searchText;
        node.hidden = !!query && !searchText.includes(query);
        return node;
      });
      return fields;
    });
    let paged;
    const searchOptions={key:`platform-${config.runtime || "settings"}`,value:options.query || "",label:`Search ${config.runtime} settings`};
    const applySearch = value => {
      // Page rebuilding must keep the current input, including its caret.
      searchOptions.value=value;
      options.search(value);
      const normalized = String(value).toLocaleLowerCase();
      const root = document.querySelector(".lex-platform-config");
      if (!root) return;
      for (const field of sections) {
        field.hidden = !!normalized && !field.dataset.platformSearch.includes(normalized);
      }
      paged.refreshPages();
    };
    paged = paginateSettings(element("div", {class:"lex-platform-config-sections"}, ...sections), {
      columns: 6, columnMajor: true, strictColumns: true,
      // A plugin whose Tweaks page divides into groups hands the bar down
      // rather than drawing a second one above this view.
      tabs: options.tabs, activeTab: options.activeTab,
      tabsLabel: options.tabsLabel, changeTab: options.changeTab,
      search:Object.assign(searchOptions,{change:applySearch}),
    });
    return element("section", {class: "lex-platform-config"},
      options.showHeader === false ? null : element("header", {class: "lex-platform-config-head"},
        element("div", {}, element("h2", {}, `${config.runtime} settings`), element("p", {}, config.message), element("code", {}, config.path))),
      paged)
  };

  /* ------------------------------------------------------------------
     Game controller navigation (issue 566)

     A Steam Deck has no mouse and no keyboard. Its controls arrive inside
     the embedded page as one standard-mapped gamepad, so a page that only
     answers clicks cannot be used there at all, and every plugin would
     otherwise grow its own version of this. The translation from pad to
     interface lives here once, in the shared UI, and every plugin gets it
     without writing a line.

     The pad drives the two things the interface already has: DOM focus,
     which every shared control already draws, and the ordinary click,
     Escape and input events those controls already answer. Nothing here
     knows about a particular game.

     It stays quiet when no pad is attached: the loop only ticks while one
     is, and a pad that throws cannot take the editor with it. The loop also
     stops while another app has the focus, so polling never holds the pad
     away from a game started behind the editor. `tick` and
     `setPadSource` are the seam a check drives without hardware.
  ------------------------------------------------------------------ */
  const gamepadNavigation = (() => {
    const FOCUSABLE = [
      "button", "a[href]", "input", "select", "textarea",
      "[contenteditable='true']", "[tabindex]",
    ].join(",");
    // Things the pad must never land on: the hidden shims a plugin keeps
    // behind its own controls, and values that only look like controls.
    const UNREACHABLE = "input[type='hidden'],[disabled],[aria-disabled='true'],[tabindex='-1'],output";
    const DEADZONE = 0.5;
    // A held direction walks the interface. The first step is immediate, then
    // the pad repeats: fast enough to cross a long list, slow enough not to
    // overshoot the row the player meant.
    const REPEAT_FIRST_MS = 340;
    const REPEAT_MS = 95;
    // Standard mapping, which is what Steam Deck and every modern pad send.
    const BUTTON = {a: 0, b: 1, x: 2, y: 3, lb: 4, rb: 5, lt: 6, rt: 7,
                    select: 8, start: 9, ls: 10, rs: 11, up: 12, down: 13, left: 14, right: 15};
    const DIRECTIONS = ["up", "down", "left", "right"];
    const SIGN = {up: -1, down: 1, left: -1, right: 1};

    let source = () => (typeof navigator !== "undefined" && navigator.getGamepads
      ? navigator.getGamepads() : []);
    let installed = false;
    let running = false;
    let padFocus = null;
    const heldSince = new Map();
    const lastRepeat = new Map();
    const discreteDown = new Set();
    let awaitingNeutral = false;
    const acceptsPadInput = () => document.hasFocus() && !document.hidden;
    const suspendPadInput = () => {
      awaitingNeutral = true;
      adjusting = null;
      heldSince.clear();
      discreteDown.clear();
      lastRepeat.clear();
      clearPadFocus();
    };

    const shown = node => {
      if (!(node instanceof HTMLElement)) return false;
      if (node.closest("[hidden],[inert]")) return false;
      if (typeof node.checkVisibility === "function" && !node.checkVisibility()) return false;
      const box = node.getBoundingClientRect();
      return box.width > 1 && box.height > 1;
    };

    // While a dialog is open the pad stays inside it: a direction that
    // wandered back into the page behind would look like the dialog losing
    // the player's input.
    const openDialog = () => {
      const dialogs = [...document.querySelectorAll(
        ".lex-dialog, .lex-modal, .lex-global-settings, .modal-backdrop, [role='dialog']")]
        .filter(shown);
      return dialogs.length ? dialogs[dialogs.length - 1] : null;
    };

    const focusPool = () => {
      const root = openDialog() || document;
      return [...root.querySelectorAll(FOCUSABLE)]
        .filter(node => shown(node) && !node.matches(UNREACHABLE));
    };

    /* The screen is read as regions, not as one field of dots: the menu bar,
       the tab strip, each panel and the pagination bar. The left stick and
       the d-pad stay inside the region they are in, so "right" never drops
       out of a panel into a column header somewhere else. The right stick,
       L3 and R3 are how the pad crosses between regions. A page with no
       panels, such as Home, keeps one walk over the whole page. */
    const MENU_BAR = ".lex-shell-command-row";
    const TAB_STRIP = ".lex-shell-header nav";
    const PANE = ".lex-panel-layout-pane";
    const lastInRegion = new WeakMap();

    // The page's own pagination bar is the lowest one outside the panels; a
    // panel's inner pager (enemy AI steps) belongs to that panel.
    const pagerBar = () => {
      const bars = [...document.querySelectorAll(".lex-pager")].filter(shown);
      const outside = bars.filter(bar => !bar.closest(PANE));
      return (outside.length ? outside : bars)
        .sort((a, b) => b.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom)[0] || null;
    };

    // The bars have controls of their own (LB/RB tabs, LT/RT subtabs, L3 the
    // menu bar, R3 the pagination bar), so the sticks never walk onto them:
    // the pool inside a panel leaves its subtab buttons out, and the right
    // stick moves between panels only.
    const BAR_CONTROL = ".lex-subtab-bar *";
    const panels = () => openDialog() ? [] : [...document.querySelectorAll(PANE)]
      .filter(pane => shown(pane) && !pane.querySelector(PANE));
    const bars = () => [document.querySelector(MENU_BAR), pagerBar()].filter(node => node && shown(node));
    const regions = () => {
      const list = panels();
      return list.length ? [...bars(), ...list] : [];
    };
    const regionOf = (node, list = regions()) => list.find(region => region.contains(node)) || null;
    const reachable = (pool, region) => pool.filter(node => region.contains(node)
      && !(region.matches(PANE) && node.matches(BAR_CONTROL)));

    // The panel the player is in is outlined, so the right stick has a
    // visible starting point.
    let markedRegion = null;
    const markRegion = region => {
      if (markedRegion === region) return;
      markedRegion?.classList.remove("lex-pad-region");
      markedRegion = region;
      region?.classList.add("lex-pad-region");
    };

    const topLeft = pool => pool.reduce((best, node) => {
      const a = node.getBoundingClientRect(), b = best.getBoundingClientRect();
      return a.top < b.top - 4 || (Math.abs(a.top - b.top) <= 4 && a.left < b.left) ? node : best;
    });

    // Entering a region returns to where the player last was in it, else to
    // its selected tab or row, else to its first control.
    const enterRegion = region => {
      const pool = reachable(focusPool(), region);
      if (!pool.length) return false;
      const remembered = lastInRegion.get(region);
      if (remembered && pool.includes(remembered)) return setPadFocus(remembered);
      const selected = pool.find(node => node.matches(".active,[aria-selected='true']"));
      return setPadFocus(selected || topLeft(pool));
    };

    // With nothing focused yet, the pad starts in the first panel that has
    // something to reach, reading the panels top to bottom, left to right.
    const enterFirstPanel = list => list.filter(region => region.matches(PANE))
      .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top
        || a.getBoundingClientRect().left - b.getBoundingClientRect().left)
      .some(region => enterRegion(region));

    const clearPadFocus = () => {
      padFocus?.classList.remove("lex-pad-focus");
      padFocus = null;
      markRegion(null);
    };

    // A programmatic focus() does not always light :focus-visible, so the
    // highlight the pad needs is a class of its own. It goes away the moment
    // the reader takes over with a mouse, the keyboard or a scroll.
    const setPadFocus = node => {
      if (!(node instanceof HTMLElement)) return false;
      if (padFocus && padFocus !== node) padFocus.classList.remove("lex-pad-focus");
      padFocus = node;
      node.classList.add("lex-pad-focus");
      const region = regionOf(node);
      if (region) lastInRegion.set(region, node);
      markRegion(region);
      try { node.focus({preventScroll: true}); } catch (_error) { node.focus?.(); }
      node.scrollIntoView?.({block: "nearest", inline: "nearest", behavior: "auto"});
      return true;
    };

    const focused = pool => {
      const active = document.activeElement;
      if (active instanceof HTMLElement && pool.includes(active)) return active;
      if (padFocus && pool.includes(padFocus)) return padFocus;
      return null;
    };

    const numberish = node => node.matches?.("input[type='number'],input[type='range']");
    const textEntry = node => node.matches?.(
      "textarea,input:not([type]),input[type='text'],input[type='search'],"
      + "input[type='number'],input[type='tel'],input[type='url'],input[type='email'],"
      + "input[type='password'],[contenteditable='true']");

    // The Deck's own keyboard is asked for by focusing a real text field and
    // calling the virtual-keyboard API where the page has it. Steam's own
    // keyboard follows that focus on hardware that does not.
    const requestOnScreenKeyboard = node => {
      node.setAttribute("enterkeyhint", node.getAttribute("enterkeyhint") || "done");
      try { navigator.virtualKeyboard?.show?.(); } catch (_error) { /* not available */ }
      return true;
    };

    /* The d-pad walks; the left stick changes the value the ring is on, as
       far and as fast as it is pushed. A light touch moves a step or two a
       second, for exact values; full tilt crosses the whole range in about
       two seconds. The rate climbs between the two on a log curve, so a
       range of a million is as easy to steer as one of ten. While the stick
       is held only input events go out, so the value, its fill and its
       reference rail follow live; the change - the commit and the one undo
       step - goes out when the stick comes back to the middle. On anything
       that is not a value the stick walks like the d-pad. */
    const ADJUST_DEADZONE = 0.2;
    const valueControl = node => node instanceof HTMLElement && !node.disabled && !node.readOnly
      && (numberish(node) || (node instanceof HTMLSelectElement && node.options.length > 1)) ? node : null;
    let adjusting = null;
    const finishAdjust = () => {
      const done = adjusting;
      adjusting = null;
      if (done?.changed && done.node.isConnected) done.node.dispatchEvent(new Event("change", {bubbles: true}));
    };
    const stepsOf = node => {
      if (node instanceof HTMLSelectElement) return {step: 1, min: 0, max: node.options.length - 1, current: node.selectedIndex};
      const step = Math.abs(Number(node.step)) || 1;
      const min = node.min !== "" && Number.isFinite(Number(node.min)) ? Number(node.min) : -Infinity;
      const max = node.max !== "" && Number.isFinite(Number(node.max)) ? Number(node.max) : Infinity;
      return {step, min, max, current: Number(node.value)};
    };
    const setStepped = (node, value) => {
      if (node instanceof HTMLSelectElement) { node.selectedIndex = value; return; }
      const decimals = (String(node.step).split(".")[1] || "").length;
      node.value = decimals ? value.toFixed(decimals) : String(Math.round(value));
    };
    const adjustWithStick = (pad, now) => {
      const node = valueControl(padFocus?.isConnected ? padFocus : document.activeElement);
      if (adjusting && adjusting.node !== node) finishAdjust();
      if (!node) return false;
      const [x = 0, y = 0] = pad.axes || [];
      const push = Math.abs(x) >= Math.abs(y) ? x : -y;
      if (Math.abs(push) < ADJUST_DEADZONE) { finishAdjust(); return true; }
      const {step, min, max, current} = stepsOf(node);
      if (!Number.isFinite(current)) return true;
      const sign = Math.sign(push);
      if (!adjusting || adjusting.sign !== sign) {
        // The first step is immediate, so a flick moves the value by one.
        adjusting = {node, sign, carry: sign * step, last: now, changed: adjusting?.changed || false};
      } else {
        const strength = (Math.abs(push) - ADJUST_DEADZONE) / (1 - ADJUST_DEADZONE);
        const range = Number.isFinite(max - min) ? max - min : step * 400;
        const slow = step * 2, fast = Math.max(range / 2, step * 4);
        const rate = slow * Math.pow(fast / slow, strength);
        adjusting.carry += sign * rate * Math.min(100, now - adjusting.last) / 1000;
        adjusting.last = now;
      }
      const steps = Math.trunc(adjusting.carry / step);
      if (!steps) return true;
      adjusting.carry -= steps * step;
      const next = Math.max(min, Math.min(max, current + steps * step));
      if (next === current) return true;
      setStepped(node, next);
      adjusting.changed = true;
      node.dispatchEvent(new Event("input", {bubbles: true}));
      return true;
    };

    const nearest = (pool, from, direction) => {
      const box = from.getBoundingClientRect();
      const fromX = box.left + box.width / 2;
      const fromY = box.top + box.height / 2;
      const horizontal = direction === "left" || direction === "right";
      const sign = SIGN[direction];
      let best = null, bestCost = Infinity;
      for (const node of pool) {
        if (node === from) continue;
        const other = node.getBoundingClientRect();
        const x = other.left + other.width / 2;
        const y = other.top + other.height / 2;
        const primary = (horizontal ? x - fromX : y - fromY) * sign;
        if (primary < 4) continue;
        const cross = Math.abs(horizontal ? y - fromY : x - fromX);
        // A control beside this one wins over a far one that happens to sit
        // closer along the straight line the cost alone would measure.
        const beside = horizontal
          ? other.bottom > box.top - 6 && other.top < box.bottom + 6
          : other.right > box.left - 6 && other.left < box.right + 6;
        const cost = primary + cross * (beside ? 1.5 : 4);
        if (cost < bestCost) { bestCost = cost; best = node; }
      }
      return best;
    };

    const move = direction => {
      const pool = focusPool();
      if (!pool.length) return false;
      const list = regions();
      const from = focused(pool);
      if (!from) return enterFirstPanel(list) || setPadFocus(pool[0]);
      const region = regionOf(from, list);
      // Focus that reached a bar by other means (a click, a tab switch) is
      // not somewhere the stick walks from; it goes back into a panel.
      if (list.length && (!region || (region.matches(PANE) && from.matches(BAR_CONTROL)))) {
        return (region && enterRegion(region)) || enterFirstPanel(list);
      }
      const next = nearest(region ? reachable(pool, region) : pool, from, direction);
      return next ? setPadFocus(next) : false;
    };

    // The right stick: the nearest region that way, entered where it was left.
    const movePanel = direction => {
      const list = regions();
      if (!list.length) return move(direction);
      const pool = focusPool();
      const from = focused(pool);
      const current = from ? regionOf(from, list) : null;
      // From a bar, the right stick goes back to the panel the player left.
      if (!current || !current.matches(PANE)) return returnFromBar() || enterFirstPanel(list);
      const candidates = panels().filter(region => region !== current && reachable(pool, region).length);
      const next = nearest(candidates, current, direction);
      return next ? enterRegion(next) : false;
    };

    // L3 is the menu bar, R3 the pagination bar. Each is a toggle: the same
    // click again returns to the control the player was on in a panel.
    let returnTo = null;
    const returnFromBar = () => {
      const node = returnTo;
      returnTo = null;
      if (node?.isConnected && focusPool().includes(node)) return setPadFocus(node);
      return enterFirstPanel(regions());
    };
    const focusBar = which => {
      if (openDialog()) return false;
      const bar = which === "menu" ? document.querySelector(MENU_BAR) : pagerBar();
      if (!bar || !shown(bar)) return false;
      const from = focused(focusPool());
      if (from && bar.contains(from)) return returnFromBar();
      if (from && regionOf(from)?.matches(PANE)) returnTo = from;
      return enterRegion(bar);
    };

    // The triggers step the subtabs of the panel the player is in, or the
    // page's first subtab row when that panel has none.
    const subtabBars = () => [...document.querySelectorAll(".lex-subtab-bar")].filter(shown);
    const switchSubtab = step => {
      if (openDialog()) return false;
      const bars = subtabBars();
      if (!bars.length) return false;
      const from = focused(focusPool());
      const region = from ? regionOf(from) : null;
      const bar = (from && bars.find(node => node.contains(from)))
        || (region && bars.find(node => region.contains(node))) || bars[0];
      const buttons = [...bar.querySelectorAll(".lex-subtab-button")]
        .filter(node => shown(node) && !node.disabled && node.getAttribute("aria-disabled") !== "true");
      if (buttons.length < 2) return false;
      const index = buttons.findIndex(node => node.classList.contains("active"));
      const next = buttons[(Math.max(0, index) + step + buttons.length) % buttons.length];
      const position = bars.indexOf(bar);
      next.click();
      // The click may redraw the bar, at once or after a plugin's own check
      // (enemy AI asks about unsaved steps first); the ring follows the new
      // selection whenever it lands.
      const label = next.textContent;
      // In a page of panels the ring stays in the panel, on its new content;
      // a page without panels has nowhere else, so it marks the subtab.
      const follow = () => {
        const redrawn = subtabBars()[position]?.querySelector(".lex-subtab-button.active");
        if (!redrawn || redrawn.textContent !== label) return;
        const pane = panels().find(node => node.contains(redrawn));
        if (pane) {
          if (!(padFocus?.isConnected && pane.contains(padFocus) && !padFocus.matches(BAR_CONTROL))) {
            lastInRegion.delete(pane);
            enterRegion(pane);
          }
        } else if (redrawn !== padFocus) setPadFocus(redrawn);
      };
      follow();
      setTimeout(follow, 0);
      setTimeout(follow, 200);
      return true;
    };

    const activate = () => {
      const pool = focusPool();
      const node = focused(pool);
      if (!node) return pool.length ? setPadFocus(pool[0]) : false;
      if (textEntry(node)) {
        setPadFocus(node);
        node.select?.();
        return requestOnScreenKeyboard(node);
      }
      if (typeof node.click === "function") { node.click(); return true; }
      return false;
    };

    // Anything that owns the screen on its own: a dialog, a menu, a rename
    // editor, the shortcut legend. While one is open, B means "close this".
    const POPUPS = ".lex-dialog,.lex-modal,.lex-global-settings,.modal-backdrop,[role='dialog'],"
      + ".lex-label-rename,.lex-shortcut-panel,.lex-project-menu,.lex-github-workspace,"
      + ".lex-map-magnifier-backdrop";
    // A dialog a page built by hand may not answer Escape at all - Home's own
    // modal only offers a button. These are the labels that mean "leave without
    // changing anything", and only they are ever clicked for the player.
    const DISMISS = /^(close|cancel|back|dismiss|not now|later|no)$/i;
    const dismissButton = root => [...root.querySelectorAll("button")]
      .find(node => !node.disabled && DISMISS.test(String(node.textContent).trim()));

    const escape = dialog => {
      const active = document.activeElement;
      // Aim the one Escape where the interface is looking. A dialog that
      // listens on its own backdrop only hears an event from inside it, and
      // a control with its own Escape handling still has to see it first.
      const target = dialog && !(active instanceof HTMLElement && dialog.contains(active))
        ? dialog
        : (active instanceof HTMLElement ? active : document.body);
      // One Escape on that control still travels the whole capture and bubble
      // path to the document, where the other shared dialogs listen.
      target.dispatchEvent(new KeyboardEvent("keydown",
        {key: "Escape", bubbles: true, cancelable: true}));
    };

    const cancel = () => {
      const dialog = openDialog();
      if (dialog) {
        escape(dialog);
        if (dialog.isConnected && shown(dialog)) dismissButton(dialog)?.click();
        return true;
      }
      const popup = [...document.querySelectorAll(POPUPS)].find(shown);
      if (popup) { escape(null); return true; }
      // Nothing to close. A field being edited is left first, so B never
      // throws away the value the player was working on.
      const active = document.activeElement;
      if (active instanceof HTMLElement
          && active.matches("input,select,textarea,[contenteditable='true']")) {
        escape(null);
        if (document.activeElement === active) { active.blur(); clearPadFocus(); }
        return true;
      }
      escape(null);
      // B is the console's Back, the same step the shell's own navigation
      // history makes when the browser's Back button is pressed.
      window.__lexeditorNavigateHistory?.(-1);
      return true;
    };

    const tabs = () => [...document.querySelectorAll("nav button[data-tab]")]
      .filter(node => shown(node) && !node.disabled);

    const switchTab = step => {
      const buttons = tabs();
      if (buttons.length < 2) return false;
      const index = buttons.findIndex(node => node.classList.contains("active"));
      const next = buttons[(Math.max(0, index) + step + buttons.length) % buttons.length];
      if (!next) return false;
      next.click();
      // The bumpers own the tab strip; with panels on the page, the ring
      // lands in the new page's first panel once it has drawn.
      if (!panels().length) return setPadFocus(next);
      clearPadFocus();
      const land = () => { if (!padFocus?.isConnected) enterFirstPanel(regions()); };
      setTimeout(land, 0);
      setTimeout(land, 250);
      return true;
    };

    const pagerButton = step => {
      const title = step < 0 ? "Previous page" : "Next page";
      const owner = document.activeElement?.closest?.(".lex-pager") || null;
      const buttons = [...document.querySelectorAll(`.lex-pager button[title="${title}"]`)]
        .filter(node => shown(node) && !node.disabled);
      const button = (owner && buttons.find(node => owner.contains(node)))
        || buttons[buttons.length - 1];
      if (!button) return false;
      button.click();
      return true;
    };

    const press = action => {
      if (!acceptsPadInput()) { suspendPadInput(); return false; }
      switch (action) {
        case "up": case "down": case "left": case "right": return move(action);
        case "a": return activate();
        case "b": return cancel();
        case "previousTab": return switchTab(-1);
        case "nextTab": return switchTab(1);
        case "previousSubtab": return switchSubtab(-1);
        case "nextSubtab": return switchSubtab(1);
        case "menuBar": return focusBar("menu");
        case "pagerBar": return focusBar("pager");
        case "previousPage": return pagerButton(-1);
        case "nextPage": return pagerButton(1);
        default:
          return action.startsWith("panel:") ? movePanel(action.slice(6)) : false;
      }
    };

    const held = (pad, index) => {
      const button = pad.buttons?.[index];
      if (!button) return false;
      return button.pressed === true || Number(button.value) > 0.5;
    };

    const directionState = (pad, stick = true) => {
      const down = new Set();
      if (held(pad, BUTTON.up)) down.add("up");
      if (held(pad, BUTTON.down)) down.add("down");
      if (held(pad, BUTTON.left)) down.add("left");
      if (held(pad, BUTTON.right)) down.add("right");
      const [x = 0, y = 0] = stick ? pad.axes || [] : [];
      if (x <= -DEADZONE) down.add("left");
      if (x >= DEADZONE) down.add("right");
      if (y <= -DEADZONE) down.add("up");
      if (y >= DEADZONE) down.add("down");
      return down;
    };

    const panelDirectionState = pad => {
      const down = new Set();
      const [, , x = 0, y = 0] = pad.axes || [];
      if (x <= -DEADZONE) down.add("left");
      if (x >= DEADZONE) down.add("right");
      if (y <= -DEADZONE) down.add("up");
      if (y >= DEADZONE) down.add("down");
      return down;
    };

    const DISCRETE = [
      [BUTTON.a, "a"], [BUTTON.b, "b"],
      [BUTTON.lb, "previousTab"], [BUTTON.rb, "nextTab"],
      [BUTTON.lt, "previousSubtab"], [BUTTON.rt, "nextSubtab"],
      [BUTTON.ls, "menuBar"], [BUTTON.rs, "pagerBar"],
    ];

    // One frame of pad input. `now` is a parameter so a check can drive the
    // repeat timing instead of waiting for real frames.
    const tick = (now = performance.now()) => {
      // The loop only runs while this page can take pad input; a direct call
      // still refuses, so background gameplay inputs never become edits here.
      if (!acceptsPadInput()) { suspendPadInput(); return false; }
      let pads = [];
      try { pads = source() || []; } catch (_error) { pads = []; }
      const pad = [...pads].find(entry => entry && entry.connected !== false);
      if (!pad) { heldSince.clear(); discreteDown.clear(); return false; }
      // A button/stick held while returning from the game must be released
      // before it can activate a control or resume directional repeats.
      if (awaitingNeutral) {
        if ([...pad.buttons || []].some((_, index) => held(pad, index)) ||
            [...pad.axes || []].some(value => Math.abs(value) >= DEADZONE)) return false;
        awaitingNeutral = false;
      }

      for (const [index, action] of DISCRETE) {
        const down = held(pad, index);
        if (down && !discreteDown.has(index)) { discreteDown.add(index); press(action); }
        else if (!down) discreteDown.delete(index);
      }

      // The d-pad (and the left stick, off a value) moves within a region,
      // the right stick between regions; each repeats on its own clock.
      const steer = (down, prefix) => {
        for (const direction of DIRECTIONS) {
          const key = prefix + direction;
          if (!down.has(direction)) { heldSince.delete(key); continue; }
          const since = heldSince.get(key);
          if (since === undefined) {
            heldSince.set(key, now);
            lastRepeat.set(prefix, now);
            press(key);
          } else if (now - since >= REPEAT_FIRST_MS && now - (lastRepeat.get(prefix) ?? 0) >= REPEAT_MS) {
            lastRepeat.set(prefix, now);
            press(key);
          }
        }
      };
      const stickOnValue = adjustWithStick(pad, now);
      steer(directionState(pad, !stickOnValue), "");
      steer(panelDirectionState(pad), "panel:");
      return true;
    };

    const attached = () => {
      try { return (source() || []).some(pad => pad && pad.connected !== false); }
      catch (_error) { return false; }
    };

    let frameHandle = 0;
    let pollHandle = 0;
    const frame = () => {
      if (!running) return;
      // The pad belongs to the focused app: while this page cannot take pad
      // input it must not poll at all. Polling keeps the browser's
      // DirectInput acquire alive, which blocks a game started behind it
      // (Dark Souls loses its gamepad for the session). The loop resumes on
      // the next focus or gesture.
      if (!acceptsPadInput()) { running = false; suspendPadInput(); return; }
      if (!attached()) { running = false; clearPadFocus(); return; }
      try { tick(); } catch (_error) { /* a broken pad must not break the page */ }
      frameHandle = requestAnimationFrame(frame);
    };

    const connect = () => {
      if (running || !acceptsPadInput() || !attached()) return false;
      running = true;
      frameHandle = requestAnimationFrame(frame);
      return true;
    };

    const onDisconnect = () => { if (!attached()) running = false; };
    // A page can load with the pad already attached, which fires no connection
    // event, so the loop is also asked for on the reader's first gesture and
    // once a second while nothing is running. Both are removed with the rest:
    // a page that switched the pad path off must really be off.
    const CONNECT_EVENTS = ["pointerdown", "keydown", "focusin"];
    const CLEAR_EVENTS = ["pointerdown", "keydown", "wheel"];

    const uninstall = () => {
      if (!installed) return;
      installed = false;
      running = false;
      cancelAnimationFrame(frameHandle);
      clearInterval(pollHandle);
      pollHandle = 0;
      window.removeEventListener("gamepadconnected", connect);
      window.removeEventListener("gamepaddisconnected", onDisconnect);
      window.removeEventListener("blur", suspendPadInput);
      document.removeEventListener("visibilitychange", suspendPadInput);
      for (const type of CONNECT_EVENTS) document.removeEventListener(type, connect, true);
      for (const type of CLEAR_EVENTS) window.removeEventListener(type, clearPadFocus, true);
      heldSince.clear();
      discreteDown.clear();
      clearPadFocus();
    };

    const install = () => {
      if (installed || typeof requestAnimationFrame !== "function") return api;
      installed = true;
      window.addEventListener("gamepadconnected", connect);
      window.addEventListener("gamepaddisconnected", onDisconnect);
      window.addEventListener("blur", suspendPadInput);
      document.addEventListener("visibilitychange", suspendPadInput);
      for (const type of CONNECT_EVENTS) document.addEventListener(type, connect, true);
      for (const type of CLEAR_EVENTS) window.addEventListener(type, clearPadFocus, true);
      if (!pollHandle) pollHandle = setInterval(connect, 1000);
      connect();
      return api;
    };

    const api = {
      install, uninstall, tick, press, move, movePanel, focusBar, switchSubtab,
      activate, cancel, switchTab, pagerButton,
      setPadFocus,
      state: () => ({installed, running, focus: padFocus}),
      setPadSource: next => { source = typeof next === "function" ? next : source; return api; },
    };
    return api;
  })();

  // One panel per tweak mod, drawn from its settings schema. Every game's
  // Tweaks page uses this: the fields and the "not available yet" badge
  // look and behave the same everywhere. There is no switch: a tweak is a
  // mod, and the Mods tab enables it.
  const tweakPanel = (title, help, toggle, body = [], blocker = "") => {
    // A tweak that cannot be switched on yet says so where it stands: what it
    // does in the help bubble, why it is unavailable in the body.
    const heading = blocker
      ? inlineLabel(element("span", {}, title), badge("NOT AVAILABLE YET", {tone: "warning", title: blocker}))
      : title;
    const panel = detailPanel({title: heading, help, actions: toggle,
      body: [...(blocker ? [detailNote(blocker)] : []), ...body]});
    panel.classList?.add("lex-tweak-panel");
    return panel;
  };
  const tweakModPanels = (options = {}) => {
    const changed = row => options.change?.(row);
    const number = options.number || ((value, min, max, step, onchange, attrs) => element("input", {
      ...attrs, type: "number", value, min, max, step,
      onchange: event => { if (event.target.checkValidity()) onchange(Number(event.target.value)); else event.target.reportValidity(); },
    }));
    const select = options.select || ((value, entries, onchange) => {
      const control = element("select", {onchange: event => onchange(event.target.value)},
        ...entries.map(entry => element("option", {value: entry.id}, entry.name)));
      control.value = String(value);
      return control;
    });
    const field = (row, item) => {
      const values = row.values, label = item.label || item.key;
      const set = value => { values[item.key] = value; changed(row); };
      let control;
      if (item.type === "bool") control = element("input", {type: "checkbox", checked: values[item.key] === true,
        "aria-label": label, disabled: !!options.readOnly, onchange: event => set(event.target.checked)});
      else if (item.type === "enum") control = select(values[item.key],
        item.choices.map(choice => ({id: choice.value, name: choice.label || String(choice.value)})), set);
      else if (item.type === "sound" && options.sounds?.().length) control = select(values[item.key], options.sounds(), value => set(Number(value)));
      else {
        const input = number(values[item.key], item.min, item.max, item.step || (item.type === "number" ? 0.1 : 1), set, {"aria-label": label});
        control = item.unit ? unitField(input, item.unit) : input;
      }
      return detailField({label, help: item.help ? infoHelp(item.help) : null, control});
    };
    const toggles = new Map();
    const rows = [...(options.rows || [])].sort((a, b) =>
      (a.schema?.title || a.name).localeCompare(b.schema?.title || b.name));
    // A Tweaks page shows only switched-on mods with something to change:
    // the Mods tab switches them, and a mod without settings has no panel.
    // A mod whose settings failed to load still shows its error. The Mods
    // tab's own settings section keeps every field, on or off, but a mod
    // with nothing to show has no panel either, so the header never sits
    // over blank space.
    const hasContent = row => row.error || row.schema?.blocker
      || (row.schema?.fields || []).some(item => !item.hidden);
    const shown = options.fieldsOnly ? rows.filter(hasContent)
      : rows.filter(row => row.enabled && hasContent(row));
    const panels = shown.map(row => {
      const schema = row.schema || {fields: []}, blocker = schema.blocker || "";
      const body = [];
      if (row.error) body.push(detailNote(row.error));
      body.push(...(schema.fields || []).filter(item => !item.hidden).map(item => field(row, item)));
      // A mod's own details pane already names the mod and has its switch.
      if (options.fieldsOnly) return element("div", {class: "lex-tweak-fields"}, ...(blocker ? [detailNote(blocker)] : []), ...body);
      // The heading is the mod’s own name, as in the Mods tab: a second
      // title in the schema always drifts from it.
      return tweakPanel(row.name, schema.help, null, body, blocker);
    });
    // A tweak another one requires greys out the dependent while it is off.
    const bind = root => bindSettingDependencies(root, shown.flatMap(row =>
      (row.schema?.requires || []).filter(need => toggles.has(need))
        .map(need => ({key: `${need}->${row.id}`, dependency: toggles.get(need), dependent: toggles.get(row.id)}))));
    return {panels, toggles, bind};
  };

  // --- Mods tab and first run -------------------------------------------
  // Every game gets the same Mods tab, always leftmost: its library's mods
  // in a table, the selected one's details and settings beside it, and
  // Lexer's Mod modules the reader has not downloaded, greyed, at the end.
  const modsDialog = (title, build) => new Promise(resolve => {
    const backdrop = element("div", {class: "lex-dialog-backdrop", "data-lex-history-control": true});
    const dialog = element("section", {class: "lex-dialog lex-mods-dialog", role: "dialog", "aria-modal": "true", "aria-label": title});
    const close = value => { backdrop.remove(); resolve(value); };
    dialog.append(element("h2", {}, title), ...build(close));
    backdrop.append(dialog);
    document.body.append(backdrop);
  });
  const watchDownload = async (pluginId, onProgress) => {
    for (;;) {
      const progress = await callWindow("lexmod_download_progress", pluginId);
      onProgress?.(progress);
      if (progress.state !== "running") return progress;
      await new Promise(resolve => setTimeout(resolve, 400));
    }
  };
  const progressText = progress => progress.state === "failed" ? progress.error
    : progress.phase === "install" ? `Installing ${progress.done} of ${progress.total} modules…`
    : progress.total ? `Downloading… ${Math.round(progress.done / progress.total * 100)}%`
    : `Downloading… ${(progress.done / 1048576).toFixed(1)} MB`;

  // A mod whose changes another switched-on mod overrides, or that overrides
  // another's: a red "!" on its row, the list in its bubble. Every game's
  // loader reports these the same way (core/mod_conflicts.py).
  const conflictMark = lines => infoHelp(
    element("ul", {class: "lex-conflict-list"}, ...lines.map(line => element("li", {}, line))),
    {class: "lex-conflict-mark", symbol: "!", title: "",
     "aria-label": `Conflicts with other mods: ${lines.join("; ")}`});
  // One red "!" on a mod's row lists every flag on it: conflicts with other
  // mods, then loader alerts (a mod changed since its last build). Hovering
  // shows all of them. A conflicts-only row keeps its old label.
  const modFlagsMark = (conflicts, alerts) => {
    const lines = [...(conflicts || []), ...(alerts || [])];
    if (!lines.length) return null;
    if (!(alerts || []).length) return conflictMark(lines);
    return infoHelp(
      element("ul", {class: "lex-conflict-list"}, ...lines.map(line => element("li", {}, line))),
      {class: "lex-conflict-mark", symbol: "!", title: "",
       "aria-label": `Mod warnings: ${lines.join("; ")}`});
  };

  const modsPage = (pluginId, pluginName) => {
    let data = null, selected = null, page = 0, pageSize = 20, query = "", main = null;
    let modDetailTab = "details", contentsMod = null, contentsResult = null, contentsFailed = false;
    const contentsWraps = {files: null, records: null};
    const contentsQuery = {records: "", files: ""}, contentsPage = {records: 0, files: 0};
    const contentsFitted = {records: 10, files: 10};
    const failure = (title, error) => showAlert({title, message: error?.message || String(error)});
    const load = async () => { data = await callWindow("mods_overview", pluginId); };
    const rows = () => [...(data?.rows || []), ...(data?.remote || []).map(row => ({...row, path: `remote:${row.folder}`}))];
    const keyOf = row => row.path;
    const replaceRow = fresh => { data.rows = data.rows.map(row => row.path === fresh.path ? fresh : row); };
    // The Mods tab and the mod selector show one order: the library's load
    // order, lowest first. A row moves within the full order, not the page,
    // so a move stays correct while the list is searched, sorted or paged.
    // A downloadable module is not in the library and cannot move.
    const localPaths = () => (data?.rows || []).map(row => row.path);
    const moveMod = async (path, delta) => {
      try { await callWindow("move_mod", pluginId, path, delta); await load(); draw(); }
      catch (error) { failure("Could not reorder the mods", error); }
    };
    const decorateModRow = (node, row) => {
      if (row.remote) return;
      const paths = localPaths();
      // An existing row: handlers become properties, the rest attributes.
      for (const [key, value] of Object.entries(modOrderGestures({
        index: paths.indexOf(row.path),
        movable: at => at >= 0 && at < paths.length,
        move: (from, by) => moveMod(paths[from], by),
      }))) {
        if (key.startsWith("on")) node[key] = value;
        else node.setAttribute(key, value);
      }
    };
    const add = () => modsDialog("Add a mod", close => [
      element("p", {}, "Create a new mod from this game's starter, or add one you already have."),
      element("div", {class: "lex-dialog-actions"},
        element("button", {type: "button", class: "lex-dialog-action", onclick: () => close(null)}, "Cancel"),
        element("button", {type: "button", class: "lex-dialog-action", disabled: !data?.canManage,
          title: data?.canManage ? "" : (data?.message || "This game's mod loader cannot add mods yet."),
          onclick: () => close("folder")}, "Add a folder…"),
        element("button", {type: "button", class: "lex-dialog-action", disabled: !data?.canManage,
          onclick: () => close("zip")}, "Add a ZIP…"),
        element("button", {type: "button", class: "lex-dialog-action primary", onclick: () => close("create")}, "Create a new mod"))
    ]).then(async choice => {
      if (!choice) return;
      try {
        if (choice === "create") { await createModProject(pluginId, {pluginName}); return; }
        const picked = await callWindow("choose_mod_package", pluginId, choice);
        if (!picked || picked.cancelled) return;
        const inspected = await callWindow("inspect_mod_package", pluginId, picked.source, "", null);
        const known = inspected.metadata || {};
        // A mod is stored with its name, author and description; ask for
        // whatever the package did not say about itself.
        const named = await askProjectName(pluginName, {details: true, value: known.missing?.length ? "" : known.name,
          author: known.author, about: known.description, createLabel: "Add",
          description: "Name the mod. The author and description may stay blank."});
        if (!named) return;
        await callWindow("import_mod_package", pluginId, picked.source, named.name, "", null,
          {...named.details, credits: known.credits || ""});
        await load(); selected = data.rows.find(row => row.name === named.name)?.path || selected; draw();
      } catch (error) { failure("Could not add the mod", error); }
    });
    const textControl = (row, key, label, multiline) => {
      const control = (multiline ? textArea : options => element("input", {type: "text", ...options}))({
        "aria-label": label, value: row[key] || "", placeholder: key === "name" ? "Required" : "Optional",
        onchange: async event => {
          const details = {name: row.name, author: row.author, description: row.description, credits: row.credits,
            [key]: event.target.value};
          try { replaceRow(await callWindow("save_mod_details", pluginId, row.path, details)); draw(); }
          catch (error) { event.target.value = row[key] || ""; failure("Could not save the mod's details", error); }
        }});
      if (multiline) control.value = row[key] || "";
      return control;
    };
    const download = async (row, button, note) => {
      button.disabled = true;
      try {
        await callWindow("lexmod_download", pluginId, [row.folder]);
        const result = await watchDownload(pluginId, progress => { note.textContent = progressText(progress); });
        if (result.state === "failed") throw new Error(result.error);
        await load(); selected = data.rows.find(item => item.folder === row.folder)?.path || null; draw();
      } catch (error) { button.disabled = false; failure("Could not download the module", error); }
    };
    const detail = () => {
      const row = rows().find(item => keyOf(item) === selected);
      // Creation lives in the detail header: one add button opening the
      // add/import dialog, in every detail state.
      const addButton = element("button", {type: "button", class: "lex-header-icon",
        title: "Add a mod", "aria-label": "Add a mod", onclick: add}, addIcon());
      if (!row) return detailPanel({title: "Mods", actions: [addButton], body: [detailNote(rows().length
        ? "Select a mod." : "This game has no mods yet. Press + in the header to create one or add one you already have.")]});
      if (row.remote) {
        const note = detailNote("");
        const button = element("button", {type: "button", class: "lex-mods-detail-download", onclick: () => download(row, button, note)}, "Download");
        return detailPanel({title: row.name, actions: [addButton],
          help: "A module of Lexer's Mod that is not in your library yet. Once downloaded it stays up to date.",
          body: [detailSection({title: "DETAILS", body: [
            detailField({label: "AUTHOR", control: readonlyField(row.author || "—")}),
            detailField({label: "DESCRIPTION", control: readonlyField(row.description || "—")})]}),
            actionRow(button), note]});
      }
      const toggle = element("input", {type: "checkbox", checked: row.enabled, "aria-label": `${row.name} enabled`,
        onchange: async event => {
          if (event.target.checked && !(await confirmFirstModEnable(row.path))) { event.target.checked = false; return; }
          try { await callWindow("set_mod_enabled", pluginId, row.path, event.target.checked); await load(); draw(); }
          catch (error) { event.target.checked = !event.target.checked; failure("Could not switch the mod", error); }
        }});
      const copyMod = async () => {
        const agreed = await confirmAction({title: "Create an editable copy?",
          message: "Managed mods update automatically. Your named copy will be independent, so updates cannot replace your edits. You have my blessing.", confirmLabel: "Make a copy"});
        if (!agreed) return;
        const named = await askProjectName(pluginName, {value: `${row.name} Copy`,
          createLabel: "Create copy", description: "Choose a name for your independent editable copy. It will be stored in the mod library."});
        if (!named) return;
        try {
          const result = await callWindow("copy_library_mod", pluginId, row.path, named.name);
          if (result?.url) { window.__lexeditorNavigating = true; location.href = result.url; }
        } catch (error) { failure("Could not copy the mod", error); }
      };
      const removeMod = async () => {
        const agreed = await confirmAction({title: `Remove "${row.name}" from the library?`,
          message: "Its files stay on disk; only the library entry goes. Import it again any time to bring it back.", confirmLabel: "Remove"});
        if (!agreed) return;
        try { await callWindow("remove_mod_project", pluginId, row.path); await load(); draw(); }
        catch (error) { failure("Could not remove the mod", error); }
      };
      const duplicateTitle = `Make an editable copy of ${row.name}`;
      const removeTitle = row.lexmod ? "This mod updates automatically, so it cannot be removed from here"
        : `Remove ${row.name} from the library`;
      const openTitle = `Open ${row.name}'s folder`;
      // The switch closes the header row, always the rightmost record control.
      const actions = [addButton,
        element("button", {type: "button", class: "lex-header-icon", title: duplicateTitle,
          "aria-label": duplicateTitle, onclick: copyMod}, copyIcon()),
        element("button", {type: "button", class: "lex-header-icon", title: removeTitle,
          "aria-label": removeTitle, disabled: !!row.lexmod, onclick: removeMod}, removeIcon()),
        element("button", {type: "button", class: "lex-header-icon", title: openTitle,
          "aria-label": openTitle,
          onclick: () => callWindow("open_mod_folder", pluginId, row.path)
            .catch(error => failure("Could not open the folder", error))}, folderIcon()),
        toggle];

      const sections = [];
      const settingsPanels = [];
      if (row.script) {
        const {panels} = tweakModPanels({rows: [{id: row.folder, name: row.name, enabled: row.enabled, ...row.script}],
          toggle: false, fieldsOnly: true,
          change: async () => {
            try { await callWindow("save_mod_settings", pluginId, row.path, row.script.values); await load(); draw(); }
            catch (error) { failure("Could not save the mod's settings", error); await load(); draw(); }
          }});
        settingsPanels.push(...panels);
      }
      // A bundle's components are ordinary on/off settings from its schema,
      // saved through the same call as a tweak mod's settings.
      if (row.components) {
        const {panels} = tweakModPanels({rows: [{id: row.folder, name: row.name, enabled: row.enabled, ...row.components}],
          toggle: false, fieldsOnly: true,
          change: async () => {
            try { await callWindow("save_mod_settings", pluginId, row.path, row.components.values); await load(); draw(); }
            catch (error) { failure("Could not save the mod's settings", error); await load(); draw(); }
          }});
        settingsPanels.push(...panels);
      }
      if (settingsPanels.length) sections.push(detailSection({title: "SETTINGS", body: settingsPanels}));
      sections.push(
        detailSection({title: "DETAILS", body: [
          detailField({label: "NAME", property: "name", control: textControl(row, "name", "Name")}),
          detailField({label: "AUTHOR", property: "author", control: textControl(row, "author", "Author")}),
          detailField({label: "DESCRIPTION", control: textControl(row, "description", "Description", true)}),
          detailField({label: "CREDITS", control: textControl(row, "credits", "Credits", true)})]}),
        ...((row.requirements?.length || row.requirementsError) ? [detailSection({title: "REQUIRES", body: [
          ...(row.requirementsError ? [detailNote(row.requirementsError)] : []),
          ...(row.requirements || []).map(need => detailField({label: need.name || need.id,
            control: readonlyField(!need.installed ? "Not installed"
              : need.enabled ? "Switched on" : "Switched off")}))]})] : []),
        detailSection({title: "SOURCE", body: [
          detailField({label: "FROM", control: readonlyField(row.lexmod ? `Lexer's Mod ${row.lexmod.version || ""}`.trim() : "Your library")}),
          ...(row.version ? [detailField({label: "VERSION", property: "version", control: readonlyField(row.version)})] : []),
        ]}));
      if (selected !== contentsMod) {
        contentsMod = selected;
        contentsQuery.records = "";
        contentsQuery.files = "";
        contentsPage.records = 0;
        contentsPage.files = 0;
        contentsResult = null;
        contentsFailed = false;
        // One fetch per selected mod: tab switches redraw from the cache,
        // so they never flash the loading line or refetch.
        const fetched = selected;
        callWindow("mod_contents", pluginId, row.path).then(result => {
          if (selected !== fetched) return;
          contentsResult = result || {};
          paintWraps();
        }).catch(() => {
          if (selected !== fetched) return;
          contentsFailed = true;
          paintWraps();
        });
      }
      const modChangeText = entry => (entry.fields || []).length ? entry.fields.join(", ")
        : entry.before != null || entry.after != null
          ? `${entry.before ?? "(nothing)"} \u2192 ${entry.after ?? "(nothing)"}` : "";
      const modContentsTable = (tab, rows, columns, searchLabel, emptyNote, notes, rowClass, rowTitle) => {
        const needle = String(contentsQuery[tab] || "").toLowerCase();
        const filtered = needle ? rows.filter(row => JSON.stringify(row).toLowerCase().includes(needle)) : rows;
        const size = Math.max(1, contentsFitted[tab] || 10);
        const pages = Math.max(1, Math.ceil(filtered.length / size));
        contentsPage[tab] = Math.max(0, Math.min(contentsPage[tab] || 0, pages - 1));
        const slice = filtered.slice(contentsPage[tab] * size, (contentsPage[tab] + 1) * size);
        const pagerNode = pager({inline: true, page: contentsPage[tab], pages, total: filtered.length, pageSize: size,
          change: next => { contentsPage[tab] = next; draw(); },
          search: {key: `${pluginId}-mod-${tab}`, value: contentsQuery[tab] || "", label: searchLabel,
            change: value => { contentsQuery[tab] = value; contentsPage[tab] = 0; draw(); }}});
        const foot = notes.map(line => detailNote(line));
        if (!rows.length) return element("div", {class: "lex-mod-contents"}, detailNote(emptyNote), ...foot);
        if (!filtered.length) return element("div", {class: "lex-mod-contents"},
          detailNote(`No ${tab === "records" ? "changes" : "files"} match this search.`), pagerNode, ...foot);
        // The list owns the tab below its header: it fills the space,
        // takes as many rows as fit, and the wheel turns its pages.
        const list = columnList({rows: slice, key: (row, index) => index,
          columns, rowClass, rowTitle, class: "lex-list-fill"});
        const box = element("div", {class: "lex-mod-contents"},
          list, pagerNode, ...foot);
        fitListPage({list, pageSize: size, change: next => {
          if (next === contentsFitted[tab]) return;
          contentsFitted[tab] = next;
          contentsPage[tab] = Math.max(0, Math.min(contentsPage[tab],
            Math.max(1, Math.ceil(filtered.length / next)) - 1));
          draw();
        }});
        wheelPages(box, direction => {
          const target = contentsPage[tab] + direction;
          if (target < 0 || target >= pages) return;
          contentsPage[tab] = target;
          draw();
        });
        return box;
      };
      const modRecordsTable = result => {
        const changes = result.changes || [];
        if (result.note && !changes.length) return element("div", {class: "lex-mod-contents"}, detailNote(result.note));
        const notes = [];
        if (result.changesTruncated) notes.push(result.totalChanges > changes.length
          ? `Showing the first ${changes.length} of ${result.totalChanges} changes.`
          : `Showing the first ${changes.length} changes.`);
        if (result.note) notes.push(result.note);
        return modContentsTable("records", changes, [
          {key: "label", label: "Record", grow: 1},
          {key: "location", label: "Table", sortValue: row => `${row.table} ${row.id}`,
            render: row => `${row.table} ${row.id}`},
          {key: "change", label: "Change", grow: 1, sortValue: modChangeText, render: modChangeText},
          {key: "state", label: "State", width: "max-content",
            sortValue: row => row.added ? "New" : row.removed ? "Removed" : "",
            render: row => row.added ? "New" : row.removed ? "Removed" : ""},
        ], "Search changed records", "No record changes compared to vanilla.", notes, null, null);
      };
      const modFilesTable = result => {
        const files = result.files || [];
        const notes = [];
        if (result.truncated) notes.push(`Showing the first ${files.length} files.`);
        if (!result.canDescribe) notes.push("Which files the loader reads is not known for this game.");
        return modContentsTable("files", files, [
          {key: "relative", label: "File", grow: 1},
          {key: "sizeLabel", label: "Size", width: "max-content", align: "end", sortValue: row => row.size},
          {key: "loaded", label: "Read", width: "max-content", align: "center",
            sortValue: row => row.loaded ? 1 : 0, render: row => booleanMark(row.loaded)},
        ], "Search files", "This mod has no files.", notes,
          row => row.loaded ? "lex-mod-file-loaded" : "",
          row => row.loaded ? "The mod loader reads this file when the mod is on" : null);
      };
      const contentsNode = tab => {
        if (contentsFailed) return detailNote("Could not read the mod's contents.");
        if (!contentsResult) return loadingStatus("Reading mod contents");
        return tab === "files" ? modFilesTable(contentsResult) : modRecordsTable(contentsResult);
      };
      const recordsEmptyNow = () => !!contentsResult && !contentsFailed
        && !(contentsResult.changes || []).length && !contentsResult.note;
      const paintWraps = () => {
        if (contentsWraps.files) contentsWraps.files.replaceChildren(contentsNode("files"));
        if (contentsWraps.records) contentsWraps.records.replaceChildren(contentsNode("records"));
        // The strip was built before the contents arrived, and only
        // the showing tab is mounted, so an emptiness change redraws
        // from cache: the Records tab grays with its reason there,
        // and a showing Records tab falls back to Details.
        const empty = recordsEmptyNow();
        const button = main?.querySelector(
          '.lex-tabbed-panel-tabs [data-subtab="records"]');
        const grayed = button?.getAttribute("aria-disabled") === "true"
          || button?.disabled === true;
        if (button && empty !== grayed) draw();
      };
      const filesWrap = element("div", {class: "lex-mod-contents-tab"}, contentsNode("files"));
      const recordsWrap = element("div", {class: "lex-mod-contents-tab"}, contentsNode("records"));
      contentsWraps.files = filesWrap;
      contentsWraps.records = recordsWrap;
      const notes = [row.error ? detailNote(row.error) : null,
        row.enabled && row.conflicts?.length ? detailNote(element("span", {class: "lex-mods-name"},
          conflictMark(row.conflicts), "Another switched-on mod changes the same things.")) : null,
        ...(row.alerts || []).map(line => detailNote(line)),
        row.missing?.length ? detailNote("This mod has no name yet. Name it to store it properly.") : null].filter(Boolean);
      // Panel tabs, not sections with a tab strip inside: Details, Files and
      // Records work the way every other detail panel's tabs do. Each table
      // carries its own inline pager, so no panel paging.
      // A mod with no record changes offers no Records tab: the tab
      // grays out with its reason instead of opening an empty table.
      // A loader note still counts as content, so it stays enabled.
      const recordsEmpty = recordsEmptyNow();
      if (modDetailTab === "records" && recordsEmpty) modDetailTab = "details";
      return detailPanel({title: row.name, actions, body: [...notes, tabbedPanel({
        label: "Mod details",
        active: modDetailTab,
        paginate: false,
        tabs: [
          {id: "details", label: "Details"},
          {id: "files", label: "Files",
            help: "Every file in the mod folder. The lit ones are the files the mod loader reads when the mod is on."},
          {id: "records", label: "Records",
            ...(recordsEmpty ? {disabled: true,
              disabledReason: "This mod changes no rows or text entries."} : {}),
            help: "Every row and text entry this mod changes compared to the game's own files. Maps, models and other files show under Files instead."},
        ],
        change: id => { modDetailTab = id; draw(); },
        content: modDetailTab === "details" ? sections : modDetailTab === "files" ? filesWrap : recordsWrap,
      })], paginate: false});
    };
    const draw = () => {
      if (!main) return;
      if (!data) { main.replaceChildren(loadingPanel({label: "Loading mods"})); return; }
      const filtered = rows().filter(row => `${row.name} ${row.author || ""}`.toLowerCase().includes(query.toLowerCase()));
      if (!filtered.some(row => keyOf(row) === selected)) selected = filtered[0] ? keyOf(filtered[0]) : null;
      const view = pagedListDetail({className: "lex-mods-page", rows: filtered, key: keyOf, selected, slots: false, noun: "mods",
        order: "given",
        page, pageSize, defaultSplit: 40, minLeft: 260, minRight: 360, splitKey: `${pluginId}-mods`, rowsKey: `${pluginId}-mods`,
        search: {key: `${pluginId}-mods-search`, value: query, label: "Search mods", change: value => { query = value; page = 0; draw(); }},
        sync: next => { page = next.page; pageSize = next.pageSize; if (next.selected !== selected) { selected = next.selected; draw(); } },
        change: next => { page = next.page; pageSize = next.pageSize; draw(); },
        // Creation lives in the detail header: the add button there opens
        // the add/import dialog, so the list keeps no add button.
        tableAdd: false,
        master: ({rows: listed, selected: current, select}) => columnList({
          // The switch column below replaces the automatic on/off mark.
          rows: listed.map(({enabled, ...row}) => ({...row, on: enabled})), key: keyOf, selected: current,
          select: row => { select(row); selected = keyOf(row); draw(); },
          decorateRow: decorateModRow,
          // Load order, lowest first: the server returns it and the page
          // keeps it (order "given"). The number makes the order visible;
          // downloadable modules have none until imported.
          columns: [
            {key: "priority", label: "Priority", width: "max-content", align: "center", numeric: true,
              help: "Load order: when two switched-on mods change the same thing, the higher number wins. Drag a row to move it.",
              sortValue: row => row.remote ? Number.MAX_SAFE_INTEGER : localPaths().indexOf(row.path),
              render: row => element("span", {class: row.remote ? "lex-mods-remote" : ""},
                row.remote ? "\u2014" : String(localPaths().indexOf(row.path) + 1))},
            {key: "name", label: "Name", grow: 1, render: row => element("span", {class: row.remote ? "lex-mods-remote" : "lex-mods-name"},
              element("span", {class: "lex-mods-name-text"}, row.name), modFlagsMark(row.on ? row.conflicts : null, row.alerts))},
            {key: "author", label: "Author", render: row => element("span", {class: row.remote ? "lex-mods-remote" : ""}, row.author || "—")},
            {key: "version", label: "Version", width: "max-content", align: "center",
              help: "The version the mod gives itself. A module you have not downloaded yet shows none.",
              render: row => element("span", {class: row.remote ? "lex-mods-remote" : ""}, row.version || "—")},
            {key: "on", label: "On", sortable: false, render: row => row.remote
              ? element("button", {type: "button", class: "lex-mods-download", "aria-label": `Download ${row.name}`,
                  onclick: event => { event.stopPropagation(); selected = keyOf(row); draw();
                    const button = document.querySelector(".lex-mods-page .lex-detail-panel .lex-mods-detail-download");
                    button?.click(); }}, "Download")
              : element("input", {type: "checkbox", checked: row.on, "aria-label": `Switch ${row.name}`,
                  onclick: event => event.stopPropagation(),
                  onchange: async event => {
                    if (event.target.checked && !(await confirmFirstModEnable(row.path))) { event.target.checked = false; return; }
                    try { await callWindow("set_mod_enabled", pluginId, row.path, event.target.checked); await load(); draw(); }
                    catch (error) { event.target.checked = !event.target.checked; failure("Could not switch the mod", error); }
                  }})}]}),
        detail, emptyDetail: () => detail()});
      main.replaceChildren(view);
    };
    let importing = false;
    // A package dropped anywhere on the program lands here: the shell
    // navigates to the Mods tab first, then hands over the drop. The
    // bytes upload in chunks, the package is inspected with the same
    // data-folder and file choice as any other import, and Import stores
    // it. One import at a time: a second drop while this one is open is
    // ignored rather than stacked.
    const importDrop = async transfer => {
      if (importing) return;
      importing = true;
      try {
        try { if (!data) await load(); }
        catch (error) { failure("Could not add the mod", error); return; }
        if (!data?.canManage) {
          failure("Could not add the mod", new Error(data?.message || "This game's mod loader cannot add mods yet."));
          return;
        }
        let uploadToken = null, cancelled = false;
        const status = element("p", {role: "status"}, "Reading dropped files…");
        const preview = element("div");
        const inspect = async (finish, actions, source) => {
          let selectedFiles = null, rootValue = "", revision = 0;
          const root = element("select", {"aria-label": "Package data folder"});
          const name = element("input", {type: "text", "aria-label": "Mod name"});
          const files = element("div", {style: "max-height:30vh;overflow:auto"});
          const result = element("p", {role: "status"});
          const importButton = element("button", {type: "button", class: "lex-dialog-action", disabled: true}, "Import mod");
          const refresh = async (rebuild = false) => {
            const request = ++revision;
            importButton.disabled = true; result.textContent = "Checking package…";
            try {
              const report = await callWindow("inspect_mod_package", pluginId, source, rootValue, selectedFiles);
              if (request !== revision) return;
              if (!root.options.length) {
                const folders = new Set([""]);
                for (const path of report.files) {
                  const parts = path.split("/"); parts.pop();
                  while (parts.length) { folders.add(parts.join("/")); parts.pop(); }
                }
                root.replaceChildren(...[...folders].sort().map(value => element("option", {value}, value || "Package root")));
              }
              if (!name.value) name.value = report.metadata.name;
              if (rebuild) {
                files.replaceChildren(...report.rootFiles.map(path => {
                  const box = element("input", {type: "checkbox", checked: true, value: path});
                  box.onchange = () => {
                    selectedFiles = [...files.querySelectorAll("input:checked")].map(node => node.value);
                    refresh();
                  };
                  return element("label", {style: "display:block"}, box, path);
                }));
              }
              result.textContent = report.valid
                ? `${report.packages.length} PAK package(s) checked. Import does not activate the mod.`
                : report.problems.join("\n");
              result.style.whiteSpace = "pre-line";
              importButton.disabled = !report.valid;
            } catch (error) { if (request === revision) result.textContent = String(error?.message || error); }
          };
          root.onchange = () => { rootValue = root.value; selectedFiles = null; refresh(true); };
          importButton.onclick = async () => {
            importButton.disabled = true;
            try {
              await callWindow("import_mod_package", pluginId, source, name.value, rootValue, selectedFiles);
              finish({imported: name.value});
            } catch (error) { status.textContent = String(error?.message || error); importButton.disabled = false; }
          };
          preview.replaceChildren(element("p", {}, source), element("label", {}, "Data folder", root),
            element("label", {}, "Name", name), files, result);
          actions.append(importButton);
          await refresh(true);
        };
        const upload = async (finish, actions) => {
          const started = await callWindow("begin_mod_upload", pluginId);
          uploadToken = started.token;
          const items = [...transfer.items];
          const dropped = [];
          const visit = async (entry, parent = "") => {
            if (entry.isFile) {
              const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
              dropped.push({file, path: parent + file.name});
            } else if (entry.isDirectory) {
              const reader = entry.createReader();
              for (;;) {
                const children = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
                if (!children.length) break;
                for (const child of children) await visit(child, parent + entry.name + "/");
              }
            }
          };
          for (const item of items) {
            const entry = item.webkitGetAsEntry?.();
            if (entry) await visit(entry);
            else { const file = item.getAsFile(); if (file) dropped.push({file, path: file.name}); }
          }
          if (!dropped.length) throw Error("Drop a folder or ZIP archive.");
          for (const {file, path} of dropped) {
            for (let offset = 0; offset < file.size || offset === 0; offset += 3 * 1024 * 1024) {
              if (cancelled) return;
              status.textContent = `Reading ${path}: ${Math.min(offset, file.size).toLocaleString()} / ${file.size.toLocaleString()} bytes`;
              const chunk = await new Promise((resolve, reject) => {
                const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]);
                reader.onerror = () => reject(reader.error); reader.readAsDataURL(file.slice(offset, offset + 3 * 1024 * 1024));
              });
              await callWindow("upload_mod_chunk", uploadToken, path, offset, chunk);
            }
          }
          if (cancelled) return;
          const source = dropped.length === 1 && dropped[0].path.toLowerCase().endsWith(".zip")
            ? `${started.root}/${dropped[0].path}` : started.root;
          status.textContent = "";
          await inspect(finish, actions, source);
        };
        const done = await modsDialog("Add a mod", close => {
          const finish = value => { cancelled = true; close(value); };
          const actions = element("div", {class: "lex-dialog-actions"},
            element("button", {type: "button", class: "lex-dialog-action", onclick: () => finish(null)}, "Cancel"));
          upload(finish, actions).catch(error => { status.textContent = String(error?.message || error); });
          return [status, preview, actions];
        });
        if (uploadToken) await callWindow("end_mod_upload", uploadToken).catch(() => {});
        if (done?.imported) {
          await load();
          selected = data.rows.find(row => row.name === done.imported)?.path || selected;
          draw();
        }
      } finally { importing = false; }
    };
    return {
      async refresh() {
        // A save rebuilds what the marks describe; a showing tab re-reads
        // them so a rebuilt mod clears its alert without reopening.
        // A failed re-read keeps the old rows: the save still succeeded.
        if (!main?.isConnected) return;
        try { await load(); } catch (_error) { return; }
        if (main?.isConnected) draw();
      },
      async show(target) {
        main = target;
        draw();
        try { await load(); } catch (error) { main.replaceChildren(notice({tone: "warning", message: error.message || String(error)})); return; }
        if (data?.conflictError) showToast?.(`Could not check the mods for conflicts: ${data.conflictError}`, {tone: "warning"});
        draw();
        // Downloaded Lexer's Mod modules stay up to date.
        callWindow("lexmod_update", pluginId).then(async result => {
          if (result?.updated && main?.isConnected) { await load(); draw(); }
        }).catch(() => {});
      },
      hide() { main = null; },
      importDrop: transfer => importDrop(transfer),
    };
  };

  const firstRun = async (pluginId, pluginName) => {
    let status;
    try { status = await callWindow("onboarding_status", pluginId); } catch (_error) { return; }
    if (!status?.show) return;
    const info = await callWindow("lexmod_info", pluginId).catch(() => ({available: false}));
    const game = status.game || pluginName;
    const backdrop = element("div", {class: "lex-dialog-backdrop lex-important-backdrop", "data-lex-history-control": true});
    const dialog = element("section", {class: "lex-dialog lex-first-run", role: "dialog", "aria-modal": "true", "aria-label": `Welcome to ${game}`});
    backdrop.append(dialog);
    document.body.append(backdrop);
    const link = (text, action) => element("button", {type: "button", class: "lex-dialog-link lex-inline-link", onclick: action}, text);
    const step = (title, body, actions) => dialog.replaceChildren(element("h2", {}, title), ...body,
      element("div", {class: "lex-dialog-actions"}, ...actions));
    const next = (label, action) => element("button", {type: "button", class: "lex-dialog-action primary", onclick: action}, label);
    const finish = async () => { backdrop.remove(); await callWindow("finish_onboarding", pluginId).catch(() => {}); };
    const enjoy = () => step("Please enjoy!", [], [next("Done", finish)]);
    const tweaks = () => step("Tweaks", [element("p", {}, "You can configure all your mod settings at a glance from the Tweaks tab on the right.")], [next("Next", enjoy)]);
    const mods = () => step("Mods", [element("p", {}, "You can enable or disable mods from the Mods tab, or add your own from there.")], [next("Next", tweaks)]);
    const ready = () => step(`Lexer's Mod for ${game} is ready to play!`, [element("p", {},
      "I hope you enjoy it, and please ", link("contact me", () => callWindow("open_home_link", "twitter")),
      " with any suggestions you have or bugs you may find!")], [next("Next", mods)]);
    const downloading = async () => {
      const bar = element("progress", {max: 1, value: 0, "aria-label": "Download progress"});
      const text = element("p", {class: "lex-dialog-status", "aria-live": "polite"}, "Starting…");
      const forward = next("Next", async () => {
        try { await callWindow("activate_enabled_mods", pluginId); } catch (_error) { /* the Mods tab can still apply them */ }
        ready();
      });
      forward.disabled = true;
      const back = element("button", {type: "button", class: "lex-dialog-action", onclick: async () => {
        back.disabled = true;
        await callWindow("lexmod_download_cancel", pluginId).catch(() => {});
        decide();
      }}, "Back");
      step(`Downloading Lexer's Mod for ${game}`, [bar, text], [back, forward]);
      try {
        await callWindow("lexmod_download", pluginId, null);
        const result = await watchDownload(pluginId, progress => {
          text.textContent = progressText(progress);
          if (progress.total) { bar.max = progress.total; bar.value = progress.done; } else bar.removeAttribute("value");
        });
        if (result.state === "done") {
          bar.max = 1; bar.value = 1;
          text.textContent = `Installed ${result.installed.length} modules.`;
          forward.disabled = false;
        } else if (result.state === "failed") text.textContent = result.error;
      } catch (error) { text.textContent = error.message || String(error); }
    };
    const decide = () => step(`Lexer's Mod for ${game}`, [
      element("p", {}, "Download ", link("my mod", () => callWindow("open_lexmod", pluginId)), " for this game? It has:"),
      element("ul", {class: "lex-first-run-features"}, ...(info.features || []).map(item => element("li", {}, item)))],
      [element("button", {type: "button", class: "lex-dialog-action", onclick: mods}, "No thanks"), next("Download", downloading)]);
    if (info.available && (info.features || []).length) decide(); else mods();
  };

window.LexeditorUI = {compareRecords, sortValueOf, tweaksPage, tweakPanel, tweakModPanels, panelIcon, noImage, noThumbnail, registerNoThumbnail, openGitHubIssues, shellTextNodes, dismissDialogs, sectionParts, pendingChangeList,uiScaleControl, element, el: element, confirmAction, paginateSettings, settingsColumns, pagerToggle, pagerSelect, instructionList, reshadeSection, callWindow, newButton, modLoaderSection, infoHelp, conflictMark, controlHelp, installControlHelp, creditsPanel, unitField, readonlyField, formatNumber, numberValue, magnitudeValue, recordId, detailPanel, tabbedPanel, applyFieldTabOverrides, detailSection, detailNote, detailField, detailGroup, detailRow, multiNumberRow, subtabBar, toggleRow, autoFitControlText, lazyOptions, notice, actionRow, pagedPane, tileGrid, curveGrid, gameCard, recordCard, componentSample, toolbar, inlineLabel, recordSource, choiceField, quantityChoice, iconValue, textArea, tagBar, controlGroup, stack, bitmapText, modelStage, modelViewModes, modelViewModeIcon, iconSlot, figureGrid, imageMap, mapMagnifier, statCard, choicePopover, treeGraph, codeField, logView, detailText, loadingPanel, loadingStatus, badge, showToast, copyText, copyIcon, removeIcon, addIcon, mathFormula, curveEditor, refreshReferences, closeButton, hoverable, renameValue, settingsIcon, infoIcon, folderIcon, fileLocationButton, searchIcon, magnifyIcon, selectionIcon, saveIcon, settingsSaveControl, bottomSearch, beginSearcher, finishSearcher, decorateSearchCandidate, thingFinderButton, thingFinderField, openGameFolder, finishPluginLoading, configureThemeSounds, playThemeSound, sharedSettings, soundCoverageTable, soundPreview, audioColumn, clone, applyTheme, EditHistory, NavigationHistory, nextHistoryTick, undoNewest, redoNewest, createModProject, installBrowserHistoryGuard, installExtendedMouseHistory, bindSettingDependencies, showAlert, confirmUnsavedExit, confirmDiscardChanges, createWindowActions, installWindowFrame, openSettings, mountShell, list, columnList, matrixTable, columnPreferences, hasEnabledProperty, panelLayout, listDetail, masterDetail, fitListPage, pagedListDetail, pager, compactPager, referenceDisplay, provenanceControl, booleanMark, enabledMark, integrationStatus, dataMap, platformConfigView, gamepadNavigation, hoverActions, collapsiblePanel, padBarrelTable, promptText, tabStrip, typeGlyph, animationViewer};
window.LexeditorUI.exactIntegerInput = exactIntegerInput;
window.LexeditorUI.attachPreviewPin = attachPreviewPin;
// The pad path is on for every page that mounts the shared UI, so a plugin
// becomes usable with a controller without doing anything itself. A page with
// no pad attached pays one idle check a second and changes nothing on screen.
if (typeof window !== "undefined" && typeof requestAnimationFrame === "function") {
  gamepadNavigation.install();
}
})();


/* LEXEDITOR_SHARED_UI_STANDARDIZATION_20260906 */
(() => {
  const ui = window.LexeditorUI;
  if (!ui || ui.__sharedStandardization20260906) return;
  ui.__sharedStandardization20260906 = true;

  const attachModelPreview = (panel, spec) => {
    if (!(panel instanceof Element) || !spec) return panel;
    const heading = panel.querySelector(':scope > .lex-detail-panel-heading');
    let icon = heading?.querySelector('.lex-detail-panel-icon');
    if (!heading) return panel;
    if (panel.lexModelPreview) return panel;
    if (!icon) {
      const art = ui.noThumbnail(spec && spec.plugin, spec && spec.thumbnailLabel);
      icon = ui.element('div',{class:'lex-detail-panel-icon'},ui.iconSlot({content:art}));
      heading.prepend(icon);
    }
    heading.classList.remove('no-icon');
    heading.classList.add('lex-model-preview-heading');
    // The content may be a node or a factory. A preview that has to read a
    // mesh out of a game archive should not pay for that until someone opens
    // the drawer, and a factory is how a plugin says so.
    const getContent = typeof spec === 'function' ? spec
      : typeof spec.content === 'function' ? spec.content
      : () => spec.content;
    const onOpen = typeof spec === 'object' ? spec.onOpen : null;
    const onClose = typeof spec === 'object' ? spec.onClose : null;
    const openLabel = typeof spec === 'object' && spec.openLabel ? spec.openLabel : 'Open model preview';
    const closeLabel = typeof spec === 'object' && spec.closeLabel ? spec.closeLabel : 'Close model preview';

    const iconContent = document.createElement('span');
    iconContent.className = 'lex-model-preview-icon-content';
    while (icon.firstChild) iconContent.append(icon.firstChild);
    const closeMark = document.createElement('span');
    closeMark.className = 'lex-model-preview-close';
    closeMark.setAttribute('aria-hidden', 'true');
    closeMark.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg>';
    icon.append(iconContent, closeMark);

    const drawer = document.createElement('section');
    drawer.className = 'lex-model-preview-drawer';
    drawer.hidden = true;
    drawer.setAttribute('aria-label', typeof spec === 'object' && spec.label ? spec.label : 'Model preview');
    heading.after(drawer);
    // The drawer covers the editing surface below the heading. Its grid
    // row does that on grid panels, but a tabbed panel is flex, where
    // the grid row means nothing and the drawer would cover the whole
    // panel with the heading floating over its top rows. Pinning its top
    // edge to the heading's measured bottom edge fits both.
    const fitDrawer = () => {
      if (!panel.classList.contains('lex-model-preview-open')) return;
      const panelBox = panel.getBoundingClientRect();
      const headBox = heading.getBoundingClientRect();
      drawer.style.top = `${Math.max(0, headBox.bottom - panelBox.top)}px`;
    };
    if (typeof ResizeObserver === 'function') {
      const headingWatch = new ResizeObserver(() => fitDrawer());
      headingWatch.observe(heading);
    }

    const snapshotSlot = () => {
      const box = icon.getBoundingClientRect();
      return {left:box.left, top:box.top, width:box.width, height:box.height};
    };
    let activationSlot = null;
    let frozenSlot = null;
    let slotLockGeneration = 0;
    const releaseIconSlot = () => {
      icon.style.left = '';
      icon.style.top = '';
    };
    const lockIconSlot = target => {
      if (!target || !panel.classList.contains('lex-model-preview-open')) return;
      releaseIconSlot();
      const current = icon.getBoundingClientRect();
      icon.style.left = `${target.left - current.left}px`;
      icon.style.top = `${target.top - current.top}px`;
    };
    const holdIconSlot = target => {
      const generation = ++slotLockGeneration;
      const started = performance.now();
      const tick = now => {
        if (generation !== slotLockGeneration || !panel.classList.contains('lex-model-preview-open')) return;
        lockIconSlot(target);
        if (now - started < 360) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    let busy = false;
    const open = async () => {
      if (busy || panel.classList.contains('lex-model-preview-open')) return;
      busy = true;
      try {
        // pointerdown is captured before the browser focuses the role=button.
        // Use that box so changing focus state cannot make the magnifier
        // jump before the click handler even starts.
        frozenSlot = activationSlot || snapshotSlot();
        activationSlot = null;
        if (!drawer.childNodes.length) {
          const pending = getContent?.();
          const content = pending instanceof Promise ? await pending : pending;
          if (content instanceof Node) drawer.append(content);
        }
        drawer.hidden = false;
        panel.classList.add('lex-model-preview-open');
        fitDrawer();
        lockIconSlot(frozenSlot);
        holdIconSlot(frozenSlot);
        icon.setAttribute('aria-expanded', 'true');
        icon.setAttribute('aria-label', closeLabel);
        icon.title = closeLabel;
        await onOpen?.(drawer);
      } finally { busy = false; }
    };
    const shut = async () => {
      if (busy || !panel.classList.contains('lex-model-preview-open')) return;
      busy = true;
      try {
        ++slotLockGeneration;
        panel.classList.remove('lex-model-preview-open');
        await new Promise(resolve => setTimeout(resolve, 150));
        await onClose?.(drawer);
        drawer.hidden = true;
        releaseIconSlot();
        activationSlot = null;
        frozenSlot = null;
        icon.setAttribute('aria-expanded', 'false');
        icon.setAttribute('aria-label', openLabel);
        icon.title = openLabel;
      } finally { busy = false; }
    };
    const toggle = () => panel.classList.contains('lex-model-preview-open') ? shut() : open();

    icon.classList.add('lex-model-preview-trigger');
    icon.tabIndex = 0;
    icon.setAttribute('role', 'button');
    icon.setAttribute('aria-label', openLabel);
    icon.setAttribute('aria-expanded', 'false');
    icon.title = openLabel;
    icon.addEventListener('pointerdown', () => {
      if (!panel.classList.contains('lex-model-preview-open')) activationSlot = snapshotSlot();
    });
    icon.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      toggle();
    });
    icon.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        if (!panel.classList.contains('lex-model-preview-open')) activationSlot = snapshotSlot();
        event.preventDefault();
        toggle();
      }
    });
    window.addEventListener('resize', () => {
      if (!panel.classList.contains('lex-model-preview-open')) return;
      fitDrawer();
      if (!frozenSlot) return;
      releaseIconSlot();
      frozenSlot = snapshotSlot();
      lockIconSlot(frozenSlot);
      holdIconSlot(frozenSlot);
    });
    panel.lexModelPreview = {open, close: shut, drawer};
    return panel;
  };
  ui.attachModelPreview = attachModelPreview;
  const originalDetailPanel = ui.detailPanel;
  ui.detailPanel = options => {
    const panel = originalDetailPanel(options);
    return options?.modelPreview ? attachModelPreview(panel, options.modelPreview) : panel;
  };

  // A header thumbnail that does not open the model viewer shows a floating
  // enlargement on hover, so the record art can be previewed at a readable
  // size. Thumbnails that open the viewer keep their magnifier instead: a
  // zoom beside the drawer they open would fight it. The enlargement is a
  // fixed overlay, never an in-place scale, so hovering changes no layout.
  let headerZoom = null;
  const closeHeaderZoom = () => {
    headerZoom?.lexSource?.classList.remove('lex-thumb-zoomed');
    headerZoom?.remove();
    headerZoom = null;
  };
  const headerZoomArt = icon => {
    const canvas = icon.querySelector('canvas');
    if (canvas instanceof HTMLCanvasElement && canvas.width > 0 && canvas.height > 0) {
      // A canvas clone paints blank: its bitmap lives outside the DOM.
      const copy = document.createElement('canvas');
      copy.width = canvas.width;
      copy.height = canvas.height;
      copy.getContext('2d')?.drawImage(canvas, 0, 0);
      return copy;
    }
    // The picture, not the pin on its corner, a sound's play button, or
    // a no-thumbnail placeholder: an empty preview has nothing to enlarge.
    const art = [...icon.querySelectorAll('img,svg,picture')]
      .find(node => !node.hidden && !node.closest('.lex-column-pin,.lex-audio-play,.lex-no-image,.lex-no-thumbnail'));
    return art instanceof Element ? art.cloneNode(true) : null;
  };
  document.addEventListener('pointerover', event => {
    if (headerZoom) return;
    const icon = event.target.closest?.('.lex-detail-panel-icon');
    if (!icon || !icon.isConnected || icon.classList.contains('lex-model-preview-trigger')) return;
    // A preview the game cannot supply states so on its icon; the mark
    // stays unzoomable even when an inventory picture stands beside it.
    if (icon.hasAttribute('data-lex-preview-state')) return;
    const art = headerZoomArt(icon);
    if (!art) return;
    const box = icon.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) return;
    // The thumbnail itself grows: the enlargement starts exactly over it and
    // swells outward from its centre, and the original is hidden meanwhile.
    // Lexer: "i didn't say that hovering a thumbnail should make a second
    // thumbnail appear lol. it should expand so you can see it better."
    const zoom = document.createElement('div');
    zoom.className = 'lex-header-thumb-zoom';
    zoom.setAttribute('aria-hidden', 'true');
    zoom.append(art);
    const place = (left, top, width, height) => Object.assign(zoom.style, {
      left: `${Math.round(left)}px`, top: `${Math.round(top)}px`,
      width: `${Math.round(width)}px`, height: `${Math.round(height)}px`});
    place(box.left, box.top, box.width, box.height);
    document.body.append(zoom);
    icon.classList.add('lex-thumb-zoomed');
    zoom.lexSource = icon;
    headerZoom = zoom;
    const pad = 12, scale = Math.min(320 / box.width, 320 / box.height, 3);
    const width = box.width * Math.max(1, scale), height = box.height * Math.max(1, scale);
    const left = Math.max(pad, Math.min(box.left + box.width / 2 - width / 2, window.innerWidth - width - pad));
    const top = Math.max(pad, Math.min(box.top + box.height / 2 - height / 2, window.innerHeight - height - pad));
    requestAnimationFrame(() => { if (headerZoom === zoom) place(left, top, width, height); });
  });
  document.addEventListener('pointerout', event => {
    if (!headerZoom) return;
    const icon = event.target.closest?.('.lex-detail-panel-icon');
    if (icon && !icon.contains(event.relatedTarget)) closeHeaderZoom();
  });
  document.addEventListener('pointerdown', closeHeaderZoom, true);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeHeaderZoom(); });
  window.addEventListener('scroll', closeHeaderZoom, true);

  // Local mirror of the glow matcher: this block keeps its own scope.
  // It matches the canonical one above, both directions included.
  const stripPinPrefix = key => String(key ?? "").replace(/^pin:/, "");
  const glowSelector = key => {
    const raw = String(key ?? "");
    const base = stripPinPrefix(raw);
    // The match runs both ways: a header carries its pin: prefix while
    // its property does not, so an unprefixed key also matches the
    // pinned column, and hovering the field lights its header back.
    const columns = raw === base
      ? [`[data-column-key="${CSS.escape(raw)}"]`, `[data-column-key="pin:${CSS.escape(raw)}"]`]
      : [`[data-column-key="${CSS.escape(raw)}"]`, `[data-column-key="${CSS.escape(base)}"]`];
    return [...columns, `[data-lex-property="${CSS.escape(base)}"]`].join(",");
  };
  // A header whose property sits on another panel tab glows that tab's
  // button instead of its hidden field. Only bars that name their
  // members answer; only the hovered table's own panel is asked.
  const litHolderTabs = (key, scope, lit) => {
    if (!key || !scope?.querySelectorAll) return;
    for (const bar of scope.querySelectorAll(".lex-tabbed-panel-tabs")) {
      const tabId = bar.lexTabMembers?.get?.(stripPinPrefix(key));
      if (!tabId) continue;
      bar.querySelector(`:scope > .lex-subtab-button[data-subtab="${CSS.escape(String(tabId))}"]`)
        ?.classList.toggle("lex-column-lit", lit);
    }
  };
  const hoverKey = node => node?.dataset?.lexProperty || node?.dataset?.columnKey || '';
  // One hovered key at a time: a new hover drops the last key's
  // glow outright, so nothing sticks when its pointerout goes
  // missing (a drag swallowing boundary events, a node replaced
  // mid-hover). Blur, gesture cancel and native drags clear
  // everything: no pointerout follows any of them.
  let glowKey = '';
  const clearGlow = () => {
    glowKey = '';
    document.querySelectorAll('.lex-self-hover').forEach(node => node.classList.remove('lex-self-hover'));
    document.querySelectorAll('.lex-column-lit').forEach(node => node.classList.remove('lex-column-lit'));
  };
  window.addEventListener('blur', clearGlow);
  document.addEventListener('pointercancel', clearGlow, true);
  document.addEventListener('dragstart', clearGlow, true);
  document.addEventListener('pointerover', event => {
    const node = event.target.closest?.('.lex-detail-field,[data-column-key]');
    const overKey = node ? hoverKey(node) : '';
    if (overKey !== glowKey) clearGlow();
    glowKey = overKey;
    if (!node) return;
    node.classList.add('lex-self-hover');
    // A column lights from its HEADER, not from anywhere inside it. Lighting
    // it from any cell meant reading down a table lit and unlit whole columns
    // under the pointer, which is motion the reader did not ask for.
    const fromHeader = node.classList.contains('lex-column-list-head-cell') ||
      node.classList.contains('lex-detail-field') ||
      Boolean(event.target.closest?.('.lex-column-pin,.lex-column-list-head-cell'));
    if (!fromHeader) return;
    const key = hoverKey(node);
    if (!key) return;
    const peers = document.querySelectorAll(glowSelector(key));
    peers.forEach(peer => peer.classList.add('lex-column-lit'));
    const fieldShown = [...peers].some(peer =>
      peer.hasAttribute('data-lex-property') && peer.getClientRects().length > 0);
    if (!fieldShown) litHolderTabs(key, node.closest?.('.lex-paged-list-detail') || document, true);
  });
  document.addEventListener('pointerout', event => {
    const node = event.target.closest?.('.lex-detail-field,[data-column-key]');
    if (!node || node.contains(event.relatedTarget)) return;
    node.classList.remove('lex-self-hover');
    const key = hoverKey(node);
    if (!key) return;
    if (key === glowKey) glowKey = '';
    document.querySelectorAll(glowSelector(key))
      .forEach(peer => peer.classList.remove('lex-column-lit'));
    litHolderTabs(key, node.closest?.('.lex-paged-list-detail') || document, false);
  });

  document.addEventListener('click', event => {
    const field = event.target.closest?.('.lex-boolean-field');
    if (!field || event.target.closest?.('input,button,a,select,textarea,.lex-info-help,.lex-reference-values,.lex-column-pin')) return;
    // The label is its own control (double-click renames it in developer
    // mode); only the value side of the row toggles the box.
    if (!event.target.closest?.('.lex-detail-field-control,.lex-field-boolean-arrow')) return;
    const input = field.querySelector('.lex-detail-field-control input[type="checkbox"]');
    if (!input || input.disabled) return;
    event.preventDefault();
    input.click();
  });

  let textDragSource = null;
  document.addEventListener("dragstart", event => {
    textDragSource = event.target?.matches?.("input,textarea") ? event.target : null;
  }, true);
  document.addEventListener("dragend", () => { textDragSource = null; }, true);
  const otherTextBox = event => {
    const box = event.target?.closest?.("input,textarea");
    return box && textDragSource && box !== textDragSource;
  };
  document.addEventListener("dragover", event => {
    if (!otherTextBox(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "none";
  }, true);
  document.addEventListener("drop", event => {
    if (!otherTextBox(event)) return;
    event.preventDefault();
    event.stopPropagation();
  }, true);

  const syncRange = field => {
    if (!field) return;
    const number = field.querySelector('input[type="number"]');
    const range = field.querySelector('input[type="range"]');
    if (number && range && range.value !== number.value) {
      range.value = number.value;
      range.dispatchEvent(new Event('input', {bubbles: true}));
    }
  };
  document.addEventListener('contextmenu', event => {
    const field = event.target.closest?.('.lex-detail-field');
    if (!field) return;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      syncRange(field);
      const target = getComputedStyle(field).backgroundColor;
      const accent = getComputedStyle(document.documentElement).getPropertyValue('--lex-accent').trim() || target;
      field.animate(
        [{backgroundColor: accent}, {backgroundColor: target}],
        {duration: 420, easing: 'cubic-bezier(.2,.75,.2,1)'},
      );
    }));
  }, true);

  const dedupeShortcuts = root => root.querySelectorAll?.('nav button[data-tab]').forEach(button => {
    if (button.querySelector('.lex-tab-shortcut')) {
      button.querySelectorAll('.lex-tab-ordinal').forEach(node => node.remove());
    }
  });
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node instanceof Element) dedupeShortcuts(node.closest('header') || node);
  }))).observe(document.documentElement, {childList: true, subtree: true});
  dedupeShortcuts(document);

  // Fitting a label is a read, a write and a read again, which forces the
  // browser to re-lay-out the page between every pair. Doing that to every
  // label in the document on every DOM change cost a third of a second per
  // keystroke on a panel of four hundred properties - the reported lag between
  // ticking a box and seeing it tick. A label whose box and text have not
  // moved since it was last fitted is already fitted, and the check for that
  // reads without writing, so nothing is invalidated and the browser answers
  // the whole sweep from one layout.
  const fitted = new WeakMap();
  const LABEL_MIN_PX = 9;
  const labelLeftOverflow = label => {
    const left=label.getBoundingClientRect().left;
    // A child with no box (a <wbr> break point) reports x=0, which read as
    // text far off the label's left edge and shrank the name to the floor.
    return Math.max(0,...[...label.children].map(child=>child.getBoundingClientRect())
      .filter(box=>box.width||box.height).map(box=>left-box.left));
  };
  const fitKey = label => `${label.clientWidth}x${label.clientHeight}|${label.textContent}`;
  const labelTextOutside = label => {
    const text=label.querySelector(':scope > .lex-detail-field-label-text');
    if(!text)return false;
    const range=document.createRange();range.selectNodeContents(text);
    const ink=range.getBoundingClientRect(),room=text.getBoundingClientRect();
    return ink.right>room.right+1||ink.left<room.left-1;
  };
  const placeBooleanHelp = label => {
    if(!label.parentElement?.classList.contains('lex-boolean-field'))return;
    const text=label.querySelector(':scope > .lex-detail-field-label-text');
    const wrapper=label.querySelector(':scope > .lex-field-help');
    const help=wrapper?.querySelector(':scope > .lex-info-help');
    if(!text||!help)return;
    const range=document.createRange();range.selectNodeContents(text);
    const line=[...range.getClientRects()].filter(box=>box.width&&box.height).at(-1);
    const box=wrapper.getBoundingClientRect();
    if(!line||!box.width||!box.height)return;
    // Keep the reserved help lane, but put the circle beside the final word
    // rather than beside the centre of a wrapped name's whole rectangle.
    const scaleX=box.width/(wrapper.offsetWidth||box.width);
    const scaleY=box.height/(wrapper.offsetHeight||box.height);
    const x=(line.right+4*scaleX-box.left)/scaleX;
    const y=(line.top+line.height/2-box.top-box.height/2)/scaleY;
    const transform=`translate(${x}px,${y}px)`;
    if(help.style.transform!==transform)help.style.transform=transform;
  };
  // Field labels in one pane take one size, the way one sub-tab bar's names
  // and one list's row text already do: every label is only as small as the
  // longest needs. Fitted one at a time, a renamed label kept the size its
  // old text needed while its neighbours kept full size (DS1 Items > Ammo >
  // Standard Arrow > Defense showed "Strike" at 10px beside 15px neighbours
  // after "Strike Guard Cut Rate" was shortened). The entry carries the base
  // font beside the box and text, so a later base change refits instead of
  // leaving stale sizes behind. A stacked field's label spans the whole row
  // instead of the shared lane, so it keeps its own size and fits alone.
  const FIELD_LABEL_SELECTOR = '.lex-detail-field-label';
  const fieldLabelScope = label =>
    label.closest('.lex-detail-panel') ||
    label.closest('.lex-dialog') ||
    label.closest('.lex-tweak-card-grid') ||
    label.closest('.lex-detail-section') ||
    label.closest('main') ||
    document.body;
  const scopeFieldLabels = scope => [...scope.querySelectorAll(FIELD_LABEL_SELECTOR)]
    .filter(label => fieldLabelScope(label) === scope &&
      !label.parentElement?.classList.contains('lex-detail-field-stacked') &&
      label.getClientRects().length);
  // A label's base size is what it inherits: no rule sets a field label's
  // own font size, so the field it sits in reads the same without clearing
  // the fitted size first.
  const fieldLabelBase = label => parseFloat(getComputedStyle(label.parentElement).fontSize) || 12;
  const scopedFieldKey = (label, base) => `${fitKey(label)}|${base}`;
  // Width gets no slack: a word may no longer wrap mid-way, so a name one
  // pixel too wide pokes past the label edge every other name ends on.
  // A name is never shrunk past what can be read. The floor was one pixel,
  // and a long property name in a narrow lane came out as a smear. A name
  // that still does not fit at the floor keeps the percentage lane.
  const labelFits = label => {
    // A label being renamed fits whatever its editor does: the input is
    // an overlay, not the label's text, and the committed text refits
    // when it swaps back in.
    if (label.querySelector(':scope > .lex-label-rename')) return true;
    const box=label.getBoundingClientRect(),css=getComputedStyle(label);
    const top=box.top+parseFloat(css.paddingTop),bottom=box.bottom-parseFloat(css.paddingBottom);
    if(labelTextOutside(label))return false;
    const outsidePadding=[...label.children].some(child=>{
      const bounds=child.getBoundingClientRect();
      return bounds.height>0&&(bounds.top<top-1||bounds.bottom>bottom+1);
    });
    return !outsidePadding && label.scrollHeight <= label.clientHeight + 1 && label.scrollWidth <= label.clientWidth && labelLeftOverflow(label)<=1;
  };
  // The lane width that lays this name out on at most two lines at its
  // size now: the narrowest width its words split into two lines on, plus
  // the help mark and padding. Each candidate line is measured as one range
  // so the spaces between its words count; a range per word left them out
  // (a trailing space has no box) and the lane came out four pixels short.
  // A name that is not plain words (a chip with an icon in it) asks for
  // nothing.
  const needTwoLines = label => {
    const nameText = label.querySelector(':scope > .lex-detail-field-label-text');
    const node = nameText?.childNodes.length === 1 && nameText.firstChild.nodeType === Node.TEXT_NODE
      ? nameText.firstChild : null;
    if (!node) return 0;
    const words = [...node.data.matchAll(/\S+/g)].map(match => ({at: match.index, to: match.index + match[0].length}));
    if (!words.length) return 0;
    const range = document.createRange();
    const ink = (from, to) => {
      range.setStart(node, from);
      range.setEnd(node, to);
      return range.getBoundingClientRect().width;
    };
    let best = ink(words[0].at, words[words.length - 1].to);
    for (let split = 0; split + 1 < words.length; split++) {
      best = Math.min(best, Math.max(ink(words[0].at, words[split].to), ink(words[split + 1].at, words[words.length - 1].to)));
    }
    const css = getComputedStyle(label);
    const help = label.querySelector(':scope > .lex-field-help');
    const mark = help ? help.getBoundingClientRect().width + (parseFloat(css.columnGap) || 0) : 0;
    return Math.ceil(best + mark + (parseFloat(css.paddingLeft) || 0) + (parseFloat(css.paddingRight) || 0) + 2);
  };
  const fitFieldLabelScope = (scope, hint) => {
    if (!(scope instanceof Element) || !scope.isConnected) return;
    // The common pass: the label that asked still fits at the size it has,
    // for the box, text and base it has now. Reads only, so the whole sweep
    // answers from one layout.
    // A lane that fits its own box can still hog its field: the floor
    // outlives the wide columns it was raised for, and the label's box is
    // the floor, so "fits" never reopens the sweep on its own. Half the row
    // reopens it; the sweep applies the narrowest row in the scope.
    const floorOver = (pane, cap) => pane
      && (parseFloat(pane.style.getPropertyValue('--lex-detail-label-floor')) || 0) > cap;
    // Full size is preferred: a label left shrunk by narrow columns regrows
    // while the floor has room under the cap. Without this the sweep kept a
    // fitted-at-narrow size after widening, a downward ratchet to match the
    // upward one the floor cap fixes.
    const shrunkWithRoom = (label, pane, cap) => label.style.fontSize
      && (parseFloat(pane?.style.getPropertyValue('--lex-detail-label-floor')) || 0) < cap - 1;
    if (hint instanceof HTMLElement && fieldLabelScope(hint) === scope &&
        !hint.parentElement?.classList.contains('lex-detail-field-stacked')) {
      const base = fieldLabelBase(hint);
      const hintPane = hint.closest('.lex-tweak-card-grid') || hint.parentElement?.parentElement;
      const hintCap = (hint.parentElement?.clientWidth || 0) / 2;
      if (!floorOver(hintPane, hintCap) && !shrunkWithRoom(hint, hintPane, hintCap)
        && fitted.get(hint) === scopedFieldKey(hint, base) && labelFits(hint)) return;
    }
    // Narrow columns stack their fields by container query, without the
    // stacked class: the label spans the field instead of sharing the lane.
    // Those labels take no part in the lane fit - an inline label never
    // spans nine tenths of its row (the floor caps the lane at half of it).
    // When every label is stacked the lane is unused and its floor clears.
    const scoped = scopeFieldLabels(scope);
    const labels = scoped.filter(label =>
      label.clientWidth <= label.parentElement.clientWidth * 0.9);
    if (scoped.length && !labels.length) {
      const pane = scoped[0].closest('.lex-tweak-card-grid') || scoped[0].parentElement?.parentElement;
      if (pane?.style.getPropertyValue('--lex-detail-label-floor'))
        pane.style.removeProperty('--lex-detail-label-floor');
      return;
    }
    if (!labels.length) return;
    const base = fieldLabelBase(labels[0]);
    const pane = labels[0].closest('.lex-tweak-card-grid') || labels[0].parentElement?.parentElement;
    const cap = Math.min(...labels.map(label => label.parentElement.clientWidth)) / 2;
    if (!floorOver(pane, cap) && !labels.some(label => shrunkWithRoom(label, pane, cap))
      && labels.every(label => fitted.get(label) === scopedFieldKey(label, base) && labelFits(label))) return;
    labels.forEach(label => {
      label.style.fontSize = '';
      const nameText = label.querySelector(':scope > .lex-detail-field-label-text');
      if (nameText) nameText.style.width = '';
    });
    // Names that all fit at full size keep it. Wrapping comes before
    // shrinking, so a name that fits on two lines never shrinks for it. The
    // floor stays: they may fit thanks to it, and clearing here traded sets
    // with the lane growth below for ever. Past the cap it lowers to the cap
    // and the resize it causes refits from there.
    if (labels.every(labelFits)) {
      const floorNow = parseFloat(pane.style.getPropertyValue('--lex-detail-label-floor')) || 0;
      if (floorNow > cap) pane.style.setProperty('--lex-detail-label-floor', `${Math.ceil(cap)}px`);
      else labels.forEach(label => fitted.set(label, scopedFieldKey(label, base)));
      return;
    }
    // A name that only fits on three lines asks for the room first: the
    // lane grows to lay every name out on at most two lines at full size,
    // capped at half the row. Past the cap the shrink below applies.
    if (pane && cap > 0) {
      // Every label contributes its two-line need, not just the ones
      // failing now: a need drawn from the failing set alone drops the
      // floor out from under the labels that fit, and the floor trades
      // two values for ever (the animations character panel flickered
      // its lane between 71px and 85px this way). The need is now a pure
      // function of the labels, so the floor lands in one step.
      // Line inks must be measured unwrapped: a range over a wrapped line
      // reads its longest line, not the line being asked for, and the lane
      // came out forty pixels short.
      labels.forEach(label => { label.style.whiteSpace = 'nowrap'; });
      let need = 0;
      for (const label of labels) need = Math.max(need, needTwoLines(label));
      labels.forEach(label => { label.style.whiteSpace = ''; });
      // The floor follows the cap down as well as the need up: it was
      // only ever raised, so a lane widened for wide columns kept hogging
      // after the reader narrowed them past it.
      const floor = Math.min(cap, need);
      const floorNow = pane.style.getPropertyValue('--lex-detail-label-floor');
      const floorWant = floor > 0 ? `${Math.ceil(floor)}px` : '';
      if (floorWant !== floorNow) {
        if (floorWant) pane.style.setProperty('--lex-detail-label-floor', floorWant);
        else pane.style.removeProperty('--lex-detail-label-floor');
      }
      if (labels.every(labelFits)) {
        labels.forEach(label => fitted.set(label, scopedFieldKey(label, base)));
        return;
      }
    }
    let size = parseFloat(getComputedStyle(labels[0]).fontSize) || 12;
    // Largest uniform size where every label fits: binary search over the
    // same half-pixel steps the old loop walked one by one, so a sweep
    // costs a few measures instead of a forced layout per step per drop.
    if (!labels.every(labelFits)) {
      const start = size;
      const steps = Math.max(0, Math.round((start - LABEL_MIN_PX) / .5));
      let lo = 0, hi = steps, best = steps;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const candidate = Math.max(LABEL_MIN_PX, start - mid * .5);
        labels.forEach(label => { label.style.fontSize = `${candidate}px`; });
        if (labels.every(labelFits)) { best = mid; hi = mid - 1; }
        else lo = mid + 1;
      }
      size = Math.max(LABEL_MIN_PX, start - best * .5);
      labels.forEach(label => { label.style.fontSize = `${size}px`; });
      while (size > LABEL_MIN_PX && !labels.every(labelFits)) {
        size = Math.max(LABEL_MIN_PX, size - .5);
        labels.forEach(label => { label.style.fontSize = `${size}px`; });
      }
      // Full size leaves no inline style, like the all-fit path above:
      // a stamped "13px" read as shrunk-with-room and churned.
      if (size === start) labels.forEach(label => { label.style.fontSize = ""; });
    }
    for (const label of labels) {
      if (label.scrollWidth > label.clientWidth) {
        // At the font floor a long word and its help mark still overran the
        // lane, and the mark sat on the value ("Requirement: STR" in DS1
        // Stats). The pane's lane grows just enough (framework.css), so every
        // name in it keeps one edge.
        const pane=label.closest('.lex-tweak-card-grid')||label.parentElement?.parentElement;
        // Capped at half the narrowest row like the floor above: an uncapped
        // word here took the whole field in narrow columns. The clipped
        // remainder stays reachable on hover; the title is always true, so it
        // is never cleared.
        const need=Math.min(cap,Math.ceil(label.scrollWidth+1));
        if(pane&&need>(parseFloat(pane.style.getPropertyValue('--lex-detail-label-floor'))||0))
          pane.style.setProperty('--lex-detail-label-floor',`${need}px`);
        const titleText=label.querySelector(':scope > .lex-detail-field-label-text');
        if(titleText&&!label.title)label.title=titleText.textContent.trim();
      }
    }
    // Hugs batched after every floor: a wrapped name's box is as wide as
    // its lane, not its longest line, so in a lane widened for a neighbour
    // the help mark sat far past "Crit / bonus". Measure every name first,
    // then place every mark: one layout for the reads, one for the writes.
    // Each hug only narrows its own name, so measuring them together reads
    // the same lines the old interleaved loop did.
    const hugs = [];
    for (const label of labels) {
      const nameText = label.querySelector(':scope > .lex-detail-field-label-text');
      if (nameText && label.querySelector(':scope > .lex-field-help')) {
        const range = document.createRange(); range.selectNodeContents(nameText);
        const lines = [...range.getClientRects()].filter(box => box.width && box.height);
        const scale = nameText.getBoundingClientRect().width / (nameText.offsetWidth || 1) || 1;
        if (lines.length > 1) hugs.push([nameText, Math.ceil(Math.max(...lines.map(box => box.width)) / scale) + 1]);
      }
    }
    for (const [node, width] of hugs) node.style.width = `${width}px`;
    for (const label of labels) {
      placeBooleanHelp(label);
      fitted.set(label, scopedFieldKey(label, base));
    }
  };
  const fitLabel = label => {
    if (!(label instanceof HTMLElement)) return;
    // A label in the shared lane is fitted with its pane, never alone.
    if (label.classList.contains('lex-detail-field-label') &&
        !label.parentElement?.classList.contains('lex-detail-field-stacked')) {
      fitFieldLabelScope(fieldLabelScope(label), label);
      return;
    }
    // The name lane has a fixed width. Fit the font inside it.
    const key = fitKey(label);
    if (fitted.get(label) === key && label.scrollWidth <= label.clientWidth && label.scrollHeight <= label.clientHeight + 1 && labelLeftOverflow(label)<1 && !labelTextOutside(label)) return;
    label.style.fontSize = '';
    const nameText = label.classList.contains('lex-detail-field-label') ? label.querySelector(':scope > .lex-detail-field-label-text') : null;
    if (nameText) nameText.style.width = '';
    let size = parseFloat(getComputedStyle(label).fontSize) || 12;
    if(label.classList.contains('lex-tab-label-text')) {
      // Main tabs and subtabs fit their labels inside a single row.
      const nav=label.closest('.lex-shell-header nav');
      // A page tab is never narrower than its own name, and its strip is sized
      // as a whole by fitNavStrip. Shrinking one of those labels here would
      // leave one strip's names in different sizes and fight that pass, so the
      // strip owns them. A sub-tab bar shares its row equally and still fits
      // each of its labels here.
      if(nav){fitted.set(label,fitKey(label));return;}
      // A sub-tab bar is fitted as a whole, like the page-tab strip: every
      // name in it takes one size, only as small as the longest needs. Fitted
      // one at a time, a long name shrank to the floor inside its slice while
      // a short neighbour kept full size (Field: "Camera Ranges" at 8px beside
      // a 16px "Tile").
      const bar=label.closest('.lex-subtab-bar:not(.lex-subtab-bar-images)');
      if(bar){fitSubtabBar(bar);return;}
      const range=document.createRange();range.selectNodeContents(label);
      // A tab with a help mark hugs its label to its text, so the label's own
      // width is no measure of the room: text 3px short of a box its own
      // size never fitted, and every such tab shrank to the floor. The room
      // is what the tab leaves once its padding and its other parts are out.
      const button=label.closest('button'),own=label.closest('.lex-tab-label')||label;
      const room=()=>{
        const css=getComputedStyle(label),inset=parseFloat(css.paddingLeft)+parseFloat(css.paddingRight)+3;
        if(!button||!button.querySelector(':scope > .lex-info-help'))return label.clientWidth-inset;
        const box=getComputedStyle(button),gap=parseFloat(box.columnGap)||0;
        let space=button.clientWidth-parseFloat(box.paddingLeft)-parseFloat(box.paddingRight);
        for(const part of button.children){
          if(part===own||part.contains(label)||getComputedStyle(part).position==='absolute')continue;
          space-=part.getBoundingClientRect().width+gap;
        }
        return space-inset;
      };
      const fits=()=>range.getBoundingClientRect().width<=room();
      // Largest size that fits: binary search over the same half-pixel
      // steps instead of a forced layout per step.
      if(!fits()){
        const start=size,steps=Math.max(0,Math.round((start-LABEL_MIN_PX)/.5));
        let lo=0,hi=steps,best=steps;
        while(lo<=hi){
          const mid=(lo+hi)>>1;
          label.style.fontSize=`${Math.max(LABEL_MIN_PX,start-mid*.5)}px`;
          if(fits()){best=mid;hi=mid-1;}
          else lo=mid+1;
        }
        size=Math.max(LABEL_MIN_PX,start-best*.5);
        label.style.fontSize=`${size}px`;
        while(size>LABEL_MIN_PX&&!fits()){size=Math.max(LABEL_MIN_PX,size-.5);label.style.fontSize=`${size}px`;}
      }
      fitted.set(label,fitKey(label));
      return;
    }
    // A record's name stops shrinking at 14px while wrapping can still help;
    // one long word that fits nowhere keeps shrinking to the shared floor
    // rather than being clipped.
    // Largest size that fits: binary search over the same half-pixel
    // steps the phased loop below used to walk. The phases shared one
    // outcome (nothing runs between them), so one search answers both.
    if (!labelFits(label)) {
      const start = size, minimum = LABEL_MIN_PX;
      const steps = Math.max(0, Math.round((start - minimum) / .5));
      let lo = 0, hi = steps, best = steps;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        label.style.fontSize = `${Math.max(minimum, start - mid * .5)}px`;
        if (labelFits(label)) { best = mid; hi = mid - 1; }
        else lo = mid + 1;
      }
      size = Math.max(minimum, start - best * .5);
      label.style.fontSize = `${size}px`;
      while (size > minimum && !labelFits(label)) {
        size = Math.max(minimum, size - .5);
        label.style.fontSize = `${size}px`;
      }
    }
    if (label.classList.contains('lex-detail-field-label') && label.scrollWidth > label.clientWidth) {
      // At the font floor a long word and its help mark still overran the
      // lane, and the mark sat on the value ("Requirement: STR" in DS1
      // Stats). The pane's lane grows just enough (framework.css), so every
      // name in it keeps one edge.
      const pane=label.closest('.lex-tweak-card-grid')||label.parentElement?.parentElement;
      const need=Math.ceil(label.scrollWidth+1);
      if(pane&&need>(parseFloat(pane.style.getPropertyValue('--lex-detail-label-floor'))||0))
        pane.style.setProperty('--lex-detail-label-floor',`${need}px`);
    }
    // A property row never grows for its label. Past the shrinking above,
    // at the readable font floor, the text clips (framework.css) instead
    // of taking extra vertical space.
    // A wrapped name's box is as wide as its lane, not its longest line, so
    // in a lane widened for a neighbour the help mark sat far past "Crit /
    // bonus". The box hugs the longest line and the mark follows the name.
    if (nameText && label.querySelector(':scope > .lex-field-help')) {
      const range=document.createRange();range.selectNodeContents(nameText);
      const lines=[...range.getClientRects()].filter(box=>box.width&&box.height);
      const scale=nameText.getBoundingClientRect().width/(nameText.offsetWidth||1)||1;
      if (lines.length>1) nameText.style.width=`${Math.ceil(Math.max(...lines.map(box=>box.width))/scale)+1}px`;
    }
    placeBooleanHelp(label);

    // `contain:size` keeps the font size out of the box's own measurements, so
    // the key is the same one computed above and the label settles in one pass.
    fitted.set(label, key);
  };
  // The room a sub-tab leaves its name once padding, help mark and badges are
  // out, and whether the name's text fits it.
  const tabLabelFits = label => {
    const range=document.createRange();range.selectNodeContents(label);
    const button=label.closest('button'),own=label.closest('.lex-tab-label')||label;
    const css=getComputedStyle(label),inset=parseFloat(css.paddingLeft)+parseFloat(css.paddingRight)+3;
    let room=label.clientWidth-inset;
    if(button&&button.querySelector(':scope > .lex-info-help')){
      const box=getComputedStyle(button),gap=parseFloat(box.columnGap)||0;
      room=button.clientWidth-parseFloat(box.paddingLeft)-parseFloat(box.paddingRight);
      for(const part of button.children){
        if(part===own||part.contains(label)||getComputedStyle(part).position==='absolute')continue;
        room-=part.getBoundingClientRect().width+gap;
      }
      room-=inset;
    }
    return range.getBoundingClientRect().width<=room;
  };
  const barKey = bar => `${bar.clientWidth}|${[...bar.querySelectorAll('.lex-tab-label-text')].map(label=>label.textContent).join('|')}`;
  const fitSubtabBar = bar => {
    const labels=[...bar.querySelectorAll('.lex-tab-label-text')];
    if(!labels.length)return;
    const key=barKey(bar);
    if(fitted.get(bar)===key&&labels.every(tabLabelFits))return;
    labels.forEach(label=>{label.style.fontSize='';});
    bar.style.gridTemplateColumns='';
    // Names that all fit at full size keep the bar's equal lanes.
    if(labels.every(tabLabelFits)){fitted.set(bar,barKey(bar));labels.forEach(label=>fitted.set(label,fitKey(label)));return;}
    // Otherwise each tab's share of the row follows what it needs at full
    // size - its name, its help mark and its padding - so every name reaches
    // the same size at once instead of short names holding room long ones
    // lack. The bar is a grid, so the shares are its columns.
    const needs=[];
    for(const label of labels){
      const button=label.closest('button');if(!button){needs.push(1);continue;}
      const range=document.createRange();range.selectNodeContents(label);
      const text=range.getBoundingClientRect().width,css=getComputedStyle(label),box=getComputedStyle(button);
      let need=text+parseFloat(css.paddingLeft)+parseFloat(css.paddingRight)+parseFloat(box.paddingLeft)+parseFloat(box.paddingRight)+6;
      for(const part of button.children)if(!part.contains(label)&&getComputedStyle(part).position!=='absolute')
        need+=part.getBoundingClientRect().width+(parseFloat(box.columnGap)||0);
      needs.push(Math.max(1,Math.round(need)));
    }
    if(getComputedStyle(bar).display==='grid'&&needs.length===bar.querySelectorAll(':scope > [role="tab"]').length)
      bar.style.gridTemplateColumns=needs.map(need=>`minmax(0,${need}fr)`).join(' ');
    let size=parseFloat(getComputedStyle(labels[0]).fontSize)||12;
    while(size>LABEL_MIN_PX&&!labels.every(tabLabelFits)){
      size-=.5;
      labels.forEach(label=>{label.style.fontSize=`${size}px`;});
    }
    fitted.set(bar,barKey(bar));
    labels.forEach(label=>fitted.set(label,fitKey(label)));
  };
  // Plain table text is fitted as one size per list, the way a sub-tab bar's
  // names are: every row name in a list takes one size, only as small as the
  // longest needs. Fitted one row at a time, a long name shrank while a short
  // neighbour kept full size - and each row's inline size froze the row font
  // of the moment it was fitted, so when the page geometry settled to a
  // smaller row height the fitted rows stayed larger than their neighbours
  // (DS1 consumables: "Soul of a Nameless Soldier" at 14px beside 11px rows).
  // The scope's key carries the row font it was fitted from, so a row font
  // that changes afterwards refits instead of leaving stale sizes behind.
  const CELL_TEXT_SELECTOR = '.lex-column-cell-text';
  const cellTextScope = label => {
    const list = label.closest('.lex-column-list');
    // Barrels of one master are direct children of their grid, so the whole
    // master shares one size; a table nested anywhere else keeps its own.
    return list?.parentElement?.classList.contains('lex-barrel-grid')
      ? list.parentElement : list;
  };
  const scopeLabels = scope => [...scope.querySelectorAll(CELL_TEXT_SELECTOR)]
    .filter(label => cellTextScope(label) === scope);
  const cellTextFits = label =>
    label.scrollWidth <= label.clientWidth + 1 &&
    label.scrollHeight <= label.clientHeight + 1 &&
    labelLeftOverflow(label) < 1;
  const cellTextBase = scope => {
    const row = scope.querySelector('.lex-column-list-row');
    return parseFloat(row && getComputedStyle(row).fontSize) || 12;
  };
  const scopeLanes = scope => {
    const lists = scope.classList.contains('lex-barrel-grid')
      ? [...scope.querySelectorAll(':scope > .lex-column-list')] : [scope];
    return lists.map(list => {
      for (const row of list.querySelectorAll(':scope > .lex-column-list-row:not(.lex-filler-row)')) {
        const cells = row.querySelectorAll(':scope > .lex-column-list-cell');
        if (cells.length) return [...cells].map(cell => Math.round(cell.clientWidth)).join(',');
      }
      return '';
    }).join(';');
  };
  const cellScopeKey = (scope, labels) =>
    `${cellTextBase(scope)}|${scope.clientWidth}|${scopeLanes(scope)}|${labels.map(label => label.textContent).join('|')}`;
  const fitCellTextScope = scope => {
    if (!(scope instanceof Element) || !scope.isConnected) return;
    const labels = scopeLabels(scope);
    if (!labels.length) return;
    if (fitted.get(scope) === cellScopeKey(scope, labels) && labels.every(cellTextFits)) return;
    labels.forEach(label => { label.style.fontSize = ''; });
    if (labels.every(cellTextFits)) { fitted.set(scope, cellScopeKey(scope, labels)); return; }
    // One ratio round first: a narrow lane can need far less than the base,
    // and half-pixel steps would re-lay-out the list for every one of them.
    const base = cellTextBase(scope);
    let size = base;
    for (const label of labels) {
      if (label.scrollWidth <= label.clientWidth + 1) continue;
      size = Math.min(size, base * label.clientWidth / Math.max(1, label.scrollWidth));
    }
    size = Math.max(LABEL_MIN_PX, Math.floor(size * 2) / 2);
    labels.forEach(label => { label.style.fontSize = `${size}px`; });
    let guard = 0;
    while (size > LABEL_MIN_PX && guard++ < 12 && !labels.every(cellTextFits)) {
      size = Math.max(LABEL_MIN_PX, size - .5);
      labels.forEach(label => { label.style.fontSize = `${size}px`; });
    }
    fitted.set(scope, cellScopeKey(scope, labels));
  };
  const LABEL_SELECTOR = '.lex-detail-field-label,.lex-toggle-label,.lex-flag-label,.lex-tab-label-text,.lex-detail-panel-name';
  const labelSizeObserver = new ResizeObserver(entries => scheduleFit(entries.map(entry=>entry.target)));
  // Within the page-tab strip every tab is at least its own name's width, so a
  // game with twenty tabs wants a strip wider than its window. Shrinking one
  // label at a time cannot fix that - the strip stays too wide, and the names
  // end up in different sizes. The whole strip shrinks together, only as far as
  // it must and only to the readable floor; past that, the frame scrolls. This
  // is the one place that decides the strip's size, for every game.
  const fitNavStrip = (nav, reset) => {
    // A strip the pass has found is watched here as well as where it was built:
    // a page that swaps its header for a fresh one leaves the original strip
    // detached, and this is what picks the replacement up.
    stripObserver.observe(nav);
    const frame = nav.closest('.lex-nav-frame') || nav.parentElement;
    const labels = [...nav.querySelectorAll('.lex-tab-label-text')];
    if (!frame || !labels.length) return;
    // The frame scrolls exactly when the strip is wider than the lane the
    // frame leaves it, and the buttons' own padding does not shrink with the
    // font, so the size is solved against the text room that is left.
    const overflows = () => nav.scrollWidth > nav.clientWidth + 1;
    const apply = size => labels.forEach(label => { label.style.fontSize = `${size}px`; });
    // Only a pass that is allowed to start over may grow the strip back: one
    // that shrinks it fires the strip's own observer, and a pass that cleared
    // its way back to the base size every time would trade those two states
    // for ever. Growing back is the window's business, and that pass resets.
    if (reset) {
      labels.forEach(label => { label.style.fontSize = ''; });
      nav.classList.remove('lex-nav-tight');
    } else {
      // A tab added after the strip was fitted arrives at the theme's base
      // size and would stay larger than its neighbours; it takes the size the
      // rest of the strip already has.
      const sized = labels.map(label => parseFloat(label.style.fontSize)).filter(Number.isFinite);
      if (sized.length && sized.length < labels.length) apply(Math.min(...sized));
    }
    if (!overflows()) return;
    const shrink = () => {
      const fixed = labels.reduce((total, label) => {
        const css = getComputedStyle(label.closest('button') || label);
        return total + parseFloat(css.paddingLeft) + parseFloat(css.paddingRight)
          + parseFloat(css.borderLeftWidth) + parseFloat(css.borderRightWidth);
      }, 0);
      const room = Math.max(1, nav.clientWidth - fixed - 1);
      let size = parseFloat(getComputedStyle(labels[0]).fontSize) || 12;
      // Measuring after each step is what makes this exact: the ratio is taken
      // from the real text width, not from an estimate that ignores padding.
      for (let attempt = 0; attempt < 5 && size > LABEL_MIN_PX && overflows(); attempt += 1) {
        size = Math.max(LABEL_MIN_PX, size * room / Math.max(1, nav.scrollWidth - fixed));
        apply(size);
      }
    };
    shrink();
    // At the readable floor the tabs give up their side padding before the
    // strip scrolls: "horizontal scroll bar -- this should never happen...
    // one row. always. no scrollbar." The names keep their size; only the air
    // around them goes.
    if (overflows()) {
      nav.classList.add('lex-nav-tight');
      shrink();
    }
  };
  // The strip itself is what changes size when a page adds its tabs or when a
  // page that opened hidden becomes visible, and neither of those resizes the
  // window or a label the fit pass already knew about. Watching every strip
  // from the moment it is built is what lets it be measured at the size it
  // really has; nothing else reaches a strip whose page builds it late. It is
  // fitted here rather than batched into the next frame, because a frame that
  // has not painted yet receives no animation frame at all.
  const stripLane = new WeakMap();
  const stripObserver = new ResizeObserver(entries => entries.forEach(entry => {
    const nav = entry.target;
    if (!nav.isConnected) return;
    const width = Math.round(nav.clientWidth);
    const laneChanged = stripLane.get(nav) !== width;
    stripLane.set(nav, width);
    // A lane that changed width is solved again from the base size, so the
    // strip can grow back. One that only changed height is only ever shrunk:
    // clearing it there would trade the two sizes for ever, because the height
    // of a tab follows its own font.
    fitNavStrip(nav, laneChanged);
  }));
  const fitAllLabels = (root, reset, lanes) => {
    // Shared-lane labels fit as one scope: fitting each label alone ran the
    // whole scope sweep per label (quadratic), which made every property
    // drop cost hundreds of milliseconds. Each scope fits once per frame,
    // with its first label as the hint; the frame shares one map across
    // every target so separate roots in one scope still fit but once.
    const laneScopes = lanes || new Map();
    const fit = label => {
      labelSizeObserver.observe(label);
      if (label.classList.contains('lex-detail-field-label') &&
          !label.parentElement?.classList.contains('lex-detail-field-stacked')) {
        const scope = fieldLabelScope(label);
        if (scope) {
          if (!laneScopes.has(scope)) laneScopes.set(scope, label);
          return;
        }
      }
      fitLabel(label);
    };
    if (root instanceof Element && root.matches?.(LABEL_SELECTOR)) fit(root);
    root.querySelectorAll?.(LABEL_SELECTOR).forEach(fit);
    if (!lanes) laneScopes.forEach((hint, scope) => fitFieldLabelScope(scope, hint));
    const scopes = new Set();
    const collect = label => {
      labelSizeObserver.observe(label);
      // Plain cell text hugs its glyphs; after shrinking, its own box does not
      // grow when the column does. Observe the cell so its font can grow back.
      const cell = label.closest('.lex-column-list-cell');
      if (cell) labelSizeObserver.observe(cell);
      const scope = cellTextScope(label);
      if (scope) scopes.add(scope);
    };
    if (root instanceof Element && root.matches?.(CELL_TEXT_SELECTOR)) collect(root);
    root.querySelectorAll?.(CELL_TEXT_SELECTOR).forEach(collect);
    scopes.forEach(fitCellTextScope);
    const strips = new Set();
    const own = root instanceof Element ? root.closest?.('.lex-shell-header nav') : null;
    if (own) strips.add(own);
    root.querySelectorAll?.('.lex-shell-header nav').forEach(nav => strips.add(nav));
    strips.forEach(nav => fitNavStrip(nav, reset));
  };
  // Measuring inside the mutation callback reads a layout that is not final:
  // the label's own height comes from the row, and the row is sized by a
  // control that has not been laid out yet. Every label measured that way keeps
  // its full size and then clips once the row settles, which is where the
  // sweep's list of cut-off property names came from. Batch the pass into the
  // next frame instead, when the row heights are real.
  //
  // Re-fitting cannot feed back into layout: `contain:size` on the label means
  // its font size cannot change the row's height, so this settles in one pass.
  let fitPending = false;
  let fitRoots = null;
  // A window resize must be able to grow the strip back even when a pass that
  // only shrinks it is already queued for the same frame, so the reset sticks
  // to the pass rather than to whoever asked first.
  let fitReset = false;
  // A rebuilt reference stack is not a reason to re-measure the property names
  // three panels away. Only what was just added is fitted; a resize or a font
  // arriving is what re-fits the page.
  const scheduleFit = (roots, reset = roots === undefined) => {
    if (!Array.isArray(roots)) fitRoots = null;
    else if (fitRoots) for (const root of roots) fitRoots.add(root);
    fitReset = fitReset || reset;
    if (fitPending) return;
    fitPending = true;
    requestAnimationFrame(() => {
      fitPending = false;
      const targets = fitRoots, resetNow = fitReset;
      fitRoots = new Set();
      fitReset = false;
      if (targets === null || !targets.size) fitAllLabels(document, resetNow);
      else {
        const lanes = new Map();
        for (const root of targets) if (root.isConnected) fitAllLabels(root, resetNow, lanes);
        lanes.forEach((hint, scope) => fitFieldLabelScope(scope, hint));
      }
    });
  };
  const labelObserver = new MutationObserver(records => {
    const added = [];
    const strips = new Set();
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;
        added.push(node);
        // A node added inside a fitted label is not a label itself and holds
        // none, so the pass below would find nothing in it: an in-place
        // rename swapping its name span back in. The label around it is what
        // must refit.
        const outer = node.closest(LABEL_SELECTOR) || node.closest('.lex-column-cell-text');
        if (outer && outer !== node) added.push(outer);
      }
      // A rename, undo or language swap changes text and adds no element; the
      // label holding that text is what must refit. Plain row text is its own
      // label.
      if (record.type === 'characterData' ||
          [...record.addedNodes, ...record.removedNodes].some(node => !(node instanceof Element))) {
        const host = record.target instanceof Element ? record.target : record.target.parentElement;
        const label = host?.closest?.(LABEL_SELECTOR) || host?.closest?.('.lex-column-cell-text');
        if (label) added.push(label);
      }
      // The strip is fitted here, in the mutation itself, rather than in the
      // next animation frame like the rest of the pass. A frame that has not
      // painted yet never receives one, and FF7's editor page can sit in that
      // state with twenty labels that still have to fit; the strip's own
      // measurement reads the lane the shell has already given it, so it does
      // not need the row heights that the batched pass waits for.
      const nav = record.target instanceof Element
        ? record.target.closest('.lex-shell-header nav') : null;
      if (nav) strips.add(nav);
    }
    strips.forEach(nav => fitNavStrip(nav, true));
    if (added.length) scheduleFit(added);
  });
  labelObserver.observe(document.documentElement, {childList: true, subtree: true, characterData: true});
  window.addEventListener('resize', () => scheduleFit());
  // A panel split drag resizes the lane without adding a node or resizing the
  // window, so watch the region the fields actually live in as well.
  let fitPageWidth = null;
  new ResizeObserver(entries => {
    const width = entries[0]?.contentRect.width;
    if (width === fitPageWidth) return;
    fitPageWidth = width;
    scheduleFit();
  }).observe(document.documentElement);
  // A label measured against the fallback font is re-laid-out when the real
  // face arrives, and the few extra pixels that brings are enough to clip a
  // line that had just fitted. Re-fit once the fonts are actually in.
  document.fonts?.ready?.then(() => scheduleFit());
  document.fonts?.addEventListener?.('loadingdone', () => {
    document.querySelectorAll(LABEL_SELECTOR).forEach(label => fitted.delete(label));
    document.querySelectorAll('.lex-column-list,.lex-barrel-grid').forEach(scope => fitted.delete(scope));
    scheduleFit();
  });
  // A page whose header is written into the served HTML fires no mutation for
  // the observer above to see, so nothing would ever ask its strip to be
  // measured; FF7's editor is built that way. The strip reads the lane the
  // shell has already given it, so it is fitted directly here, once the
  // document is parsed and the game's own stylesheet has been applied.
  const fitStripsNow = () => document.querySelectorAll('.lex-shell-header nav')
    .forEach(nav => fitNavStrip(nav, true));
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fitStripsNow, {once: true});
  else fitStripsNow();
  scheduleFit();
})();

// Selection marks precede the label, including its leading icon.
(() => {
  let pending=false;
  const sizes=new ResizeObserver(()=>schedule());
  const place=()=>{
    pending=false;
    for(const host of document.querySelectorAll('.lex-shell-header nav button.active,.lex-column-list-row.selected .lex-column-pointer-cell > .lex-column-cell-content')){
      const tab=host.matches('button');
      const label=tab?host.querySelector('.lex-tab-label-text'):host;
      if(!label)continue;
      sizes.observe(label);
      const walker=document.createTreeWalker(label,NodeFilter.SHOW_TEXT,{acceptNode:node=>node.textContent.trim()&&!node.parentElement.closest('.lex-reference-values,.lex-tab-shortcut,.lex-info-help,[aria-hidden="true"],select')?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_SKIP});
      let node=tab?label.firstChild:walker.nextNode();
      while(node&&node.nodeType!==Node.TEXT_NODE)node=node.firstChild;
      if(!node||!node.textContent.trim())continue;
      const range=document.createRange();range.selectNodeContents(node);
      const text=range.getBoundingClientRect(),box=host.getBoundingClientRect(),css=getComputedStyle(host);
      if(!text.width)continue;
      let labelLeft=text.left;
      for(const icon of label.querySelectorAll('img,svg,canvas')){
        if(icon.closest('.lex-reference-values,.lex-info-help,.lex-tab-shortcut'))continue;
        const iconStyle=getComputedStyle(icon),bounds=icon.getBoundingClientRect();
        if(iconStyle.visibility==='hidden'||!bounds.width||!bounds.height)continue;
        sizes.observe(icon);
        if(bounds.right<=text.left+1)labelLeft=Math.min(labelLeft,bounds.left);
      }
      const width=parseFloat(css.getPropertyValue(tab?'--lex-tab-marker-width':'--lex-row-marker-width'))||24;
      const gap=6;
      const scale=box.width/host.offsetWidth||1;
      const left=(labelLeft-box.left)/scale-width-gap-(parseFloat(css.borderLeftWidth)||0);
      host.style.setProperty('--lex-marker-left',`${left}px`);
    }
  };
  const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(place);}};
  const markerContext='.lex-shell-header nav,.lex-column-list-row';
  new MutationObserver(records=>{
    for(const record of records){
      const target=record.target instanceof Element?record.target:record.target.parentElement;
      if(target?.closest(markerContext)||(record.type==='attributes'&&target?.querySelector(markerContext))){schedule();return;}
      for(const node of [...record.addedNodes,...record.removedNodes]){
        if(node instanceof Element&&(node.matches(markerContext)||node.querySelector(markerContext))){schedule();return;}
      }
    }
  }).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
  new ResizeObserver(schedule).observe(document.documentElement);
  window.addEventListener('resize',schedule);
  document.addEventListener('pointerup',schedule);
  document.fonts?.ready?.then(schedule);
  schedule();
})();


/* LEXEDITOR_FIELD_METADATA_GEOMETRY_20260906 */
(() => {
  const alignFieldMetadata = root => {
    const fields = root?.matches?.('.lex-detail-field')
      ? [root] : [...(root?.querySelectorAll?.('.lex-detail-field') || [])];
    // Every measurement first, every write afterwards. Interleaving them made
    // each field's style write invalidate the layout that the next field's
    // measurement then had to rebuild, so a panel of four hundred properties
    // spent a third of a second re-laying itself out behind every keystroke.
    const placements = [];
    for (const field of fields) {
      const rail = field.querySelector(':scope > .lex-field-type-rail');
      const label = field.querySelector(':scope > .lex-detail-field-label');
      // Every property's rail sits in the same place beside its name, whether
      // or not the property also carries authored help. Requiring a ? here
      // left every plain property's rail parked in the far-left gutter, so no
      // two rows in a panel annotated their names from the same place.
      if (!rail || !label) continue;
      // The property name is wrapped in its own span so the boolean leader
      // arrow cannot squeeze it, so look inside that wrapper first. Searching
      // only the label's direct children left the rail parked at the far left
      // of the lane, a hundred and eighty pixels from the name it annotates.
      const holder = label.querySelector(":scope > .lex-detail-field-label-text") || label;
      // The label fitter shrinks a long name after this pass has already
      // measured it, which left the rail sitting where the name used to start
      // and, on the longest names, painted over the name itself. Watching the
      // name means the rail follows every re-fit.
      nameObserver?.observe(holder);
      const text = [...holder.childNodes].find(node =>
        node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (!text) continue;
      const range = document.createRange();
      range.selectNodeContents(text);
      const fieldBox = field.getBoundingClientRect();
      const textBox = range.getBoundingClientRect();
      const railBox = rail.getBoundingClientRect();
      if (!fieldBox.width || !textBox.width || !railBox.width) continue;
      // User-facing contract: the info bubble sits JUST LEFT of the property
      // name it annotates, not centred in the empty lane beside it. Centring
      // put it a hundred and eighty pixels away in a wide panel, where it read
      // as belonging to nothing. It stays inside the row when the name runs
      // long enough to leave no room.
      const gap = 8;
      const wanted = textBox.left - gap - railBox.width - fieldBox.left;
      placements.push([rail, `${Math.max(0, wanted)}px`]);
    }
    for (const [rail, left] of placements) {
      if (rail.style.left !== left) rail.style.left = left;
    }
  };
  // Grouping separators in the boxes a reader types into. Everything the
  // framework PAINTS is already grouped - table cells, readonly fields,
  // reference readings - but a plugin's own input[type=number] cannot hold a
  // comma at all: assigning "50,000" to one leaves it empty. So the box is
  // rebuilt as a text box that carries the number, groups it while the reader
  // is looking at it and while they edit it.
  //
  // Two things keep this safe for plugins that never asked for it. Only boxes
  // that can actually hold a big number are touched - a 0-100 percentage gains
  // nothing from a separator. Input and change handlers receive plain digits;
  // grouping returns after dispatch, with the caret in the same digit position.
  const GROUPING_FLOOR = 10000;
  const groupedBoxes = new WeakSet();
  const wantsGrouping = input => {
    const max = Number(input.max);
    if (Number.isFinite(max)) return Math.abs(max) >= GROUPING_FLOOR;
    const value = Number(input.value);
    return Number.isFinite(value) && Math.abs(value) >= GROUPING_FLOOR;
  };
  const fitNewControls = root => {
    const scope = root instanceof Element || root instanceof Document ? root : document;
    const inputs = [...scope.querySelectorAll('input[type="number"]')];
    if (scope instanceof Element && scope.matches?.('input[type="number"]')) inputs.push(scope);
    // A dropdown cannot wrap its face: a long choice in a narrow box clipped
    // to an ellipsis. The fitter scales the face down instead, like numbers.
    const selects = [...scope.querySelectorAll("select")];
    if (scope instanceof Element && scope.matches?.("select")) selects.push(scope);
    // A locked value is sized like an editable one, but only a value: fitted
    // to one line, a sentence shrank to a few pixels high.
    for (const box of scope.querySelectorAll(".lex-detail-field-control .lex-readonly-field")) {
      const text = String(box.value ?? box.textContent ?? "").trim();
      if (!box.__lexAutoFitUpdate && text.length <= 24) window.LexeditorUI.autoFitControlText(box,{minimum:8});
    }
    for (const select of selects) {
      if (!select.__lexAutoFitUpdate) window.LexeditorUI.autoFitControlText(select,{minimum:8});
    }
    for (const input of inputs) {
      if (!input.__lexAutoFitUpdate) window.LexeditorUI.autoFitControlText(input,{minimum:8});
      if (input.dataset.lexExactInteger || input.dataset.lexValidateNumber || groupedBoxes.has(input) || !wantsGrouping(input)) continue;
      groupedBoxes.add(input);
      const plain = () => String(input.value ?? "").replace(/,/g, "");
      // A text box does not enforce min and max the way a number box does, so
      // the bounds the plugin declared are applied here instead of quietly
      // going away with the spinner.
      const floor = input.min === "" ? NaN : Number(input.min);
      const ceiling = input.max === "" ? NaN : Number(input.max);
      const clamp = value => {
        let bounded = value;
        if (Number.isFinite(floor)) bounded = Math.max(floor, bounded);
        if (Number.isFinite(ceiling)) bounded = Math.min(ceiling, bounded);
        return bounded;
      };
      const show = () => {
        if (input === document.activeElement) { groupEditing(); return; }
        const value = Number(plain());
        if (plain() === "" || !Number.isFinite(value)) return;
        const bounded = clamp(value);
        if (bounded !== value) {
          input.value = String(bounded);
          input.dispatchEvent(new Event("input", {bubbles: true}));
        }
        input.value = window.LexeditorUI.formatNumber(bounded);
        window.LexeditorUI.autoFitControlText(input, {minimum:8});
      };
      input.type = "text";
      input.inputMode = "decimal";
      input.autocomplete = "off";
      const groupEditing = () => {
        const value=input.value;
        const start=value.slice(0,input.selectionStart??value.length).replace(/,/g,'').length;
        const end=value.slice(0,input.selectionEnd??value.length).replace(/,/g,'').length;
        const raw=plain();
        if(!/^-?\d+(\.\d*)?$/.test(raw))return;
        const [integer,fraction]=raw.split('.');
        const formatted=integer.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(fraction===undefined?'':'.'+fraction);
        const position=count=>{let i=0,seen=0;while(i<formatted.length&&seen<count){if(formatted[i]!==',')seen++;i++}return i};
        input.value=formatted;
        if(input===document.activeElement)input.setSelectionRange(position(start),position(end));
      };
      // Handlers receive plain numbers; restore grouping after event dispatch.
      const editEvent = () => {
        const start=input.value.slice(0,input.selectionStart??input.value.length).replace(/,/g,'').length;
        const end=input.value.slice(0,input.selectionEnd??input.value.length).replace(/,/g,'').length;
        input.value=plain();input.setSelectionRange(start,end);
        setTimeout(groupEditing,0);
      };
      input.addEventListener('input',editEvent,true);
      input.addEventListener('change',editEvent,true);
      input.addEventListener("focus", () => {
        groupEditing();
        input.select();
      });
      input.addEventListener("blur", show);
      // A plugin that writes a fresh value into the box while it sits unfocused
      // re-groups it; while it is focused the reader's own digits stand.
      input.addEventListener("change", () => setTimeout(show,0));
      show();
    }
  };

  let pending = false;
  const schedule = root => {
    fitNewControls(root && root !== document ? root : document);
    if (root && root !== document) { requestAnimationFrame(() => alignFieldMetadata(root)); return; }
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; alignFieldMetadata(document); });
  };
  // Editing a value re-sizes the row, and a taller row re-sizes the label box
  // inside it, which used to re-run the whole pass twice per keystroke. Only a
  // name that changed WIDTH can have moved where it starts.
  const nameWidths = new WeakMap();
  const nameObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(entries => {
    let moved = false;
    for (const entry of entries) {
      const width = Math.round(entry.contentRect.width);
      if (nameWidths.get(entry.target) === width) continue;
      nameWidths.set(entry.target, width);
      moved = true;
    }
    if (moved) schedule(document);
  });
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node instanceof Element) schedule(node);
  }))).observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener('resize', () => schedule(document));
  // The rail is placed against the measured left edge of the property name, so
  // anything that moves that name has to move the rail with it: a pane drag,
  // the label fitter's own re-wrap, and the real font face arriving after the
  // first measurement was taken against the fallback.
  // Width only: a page that merely got taller moved nothing sideways.
  let pageWidth = 0;
  new ResizeObserver(entries => {
    const width = Math.round(entries[0]?.contentRect.width || 0);
    if (width === pageWidth) return;
    pageWidth = width;
    schedule(document);
  }).observe(document.documentElement);
  document.fonts?.ready?.then(() => schedule(document));
  schedule(document);
})();
