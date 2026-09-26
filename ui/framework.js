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
    const slider = element("input", {type:"range", min:50, max:150, step:1, value:100,
      "aria-label":"UI scale", "aria-valuetext":"100%"});
    let pending = null, running = false;
    const show = percent => { slider.value=percent; value.textContent=`${percent}%`; slider.setAttribute("aria-valuetext",`${percent}%`); };
    const apply = async () => {
      if(running)return;
      running=true;
      try {
        while(pending!==null){const percent=pending;pending=null;await callWindow("ui_scale",percent);}
      } catch(error){showToast(`Could not change UI scale: ${error.message||error}`,true);}
      finally{running=false;}
    };
    slider.addEventListener("input",()=>show(Number(slider.value)));
    slider.addEventListener("change",()=>{pending=Number(slider.value);apply();});
    const initialize=async()=>{try{const result=await callWindow("ui_scale");if(result?.percent&&!running)show(result.percent);}catch(_error){}};
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
  // Toasts never take the pointer, so hovering one is measured, not heard:
  // one under the pointer fades until the pointer moves off it.
  const ghostToasts = event => {
    for (const toast of document.querySelectorAll(".lex-toast")) {
      const box = toast.getBoundingClientRect();
      const over = event.clientX >= box.left && event.clientX <= box.right &&
        event.clientY >= box.top && event.clientY <= box.bottom;
      toast.classList.toggle("lex-toast-ghost", over);
    }
  };
  // Listened for from the start: the window bar's own toast is not made here.
  document.addEventListener("pointermove", ghostToasts, {passive: true});
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
    setTimeout(() => {
      toast.classList.add("leaving");
      setTimeout(() => toast.remove(), 220);
    }, Math.max(900, Number(options.duration) || 2000));
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

  const newButton = (attrs = {}) => {
    const {class: className = "", title = "Add", "aria-label": ariaLabel = title, ...rest} = attrs;
    return element("button", {
      type: "button", ...rest,
      class: ["lex-new-button lex-ui-symbol", className].filter(Boolean).join(" "),
      title, "aria-label": ariaLabel,
    }, element("span", {class: "lex-new-button-plus", "aria-hidden": "true"}, "+"));
  };

  let infoHelpSequence = 0;
  let activeHelpPopup = null;

  const closeHelpPopup = () => {
    if (!activeHelpPopup) return;
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
    return () => observer.disconnect();
  };

  const infoHelp = (text, attrs = {}) => {
    if (text instanceof Element && text.matches('.lex-info-help') && !Object.keys(attrs).length) return text;
    const {
      class: className = "", title = text, "aria-label": ariaLabel = text,
      onclick = null, ...rest
    } = attrs;
    const interactive = typeof onclick === "function";
    const popupId = `lex-help-${++infoHelpSequence}`;
    const marker = element(interactive ? "button" : "span", {
      ...(interactive ? {type: "button", onclick} : {tabindex: "0"}),
      ...rest,
      class: ["lex-info-help", className].filter(Boolean).join(" "),
      "data-lex-control": "help",
      "aria-label": ariaLabel, "aria-describedby": popupId,
    }, element("span", {"aria-hidden": "true"}, "?"));
    let closeTimer = null;
    const cancelClose = () => { clearTimeout(closeTimer); closeTimer = null; };
    const scheduleClose = () => {
      cancelClose();
      closeTimer = setTimeout(() => {
        if (activeHelpPopup?.id === popupId &&
            !marker.matches(":hover,:focus-visible") &&
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
      const shipped = typeof text === "string" ? text : null;
      const shown = () => shipped === null ? text : savedLabel(helpKey(shipped), shipped);
      const popup = element("div", {
        id: popupId, class: "lex-help-popover", role: "tooltip", tabindex: "0",
      }, text instanceof Node ? text.cloneNode(true) : String(shown() ?? title ?? ""));
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
          const finish = async commit => {
            if (finished) return;
            finished = true;
            popup.classList.remove("lex-help-editing");
            const typed = editor.value.trim();
            const next = typed && typed !== shipped ? typed : shipped;
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
            open();
            // A bubble has no lasting node, so undoing a rewording puts the text
            // back for the next time it opens rather than under the pointer.
            labelUndo.push({key: helpKey(shipped), tabId: activePageTab(), before,
              after: next, shipped, node: null});
            labelRedo.length = 0;
            await storeLabel(helpKey(shipped), activePageTab(), next, shipped);
            labelHistoryChanged();
            try {
              // storeLabel already saved it, with the same transport the rest of
              // the renames use.
              showToast(next === shipped ? "The shipped help text is back."
                                         : "The new help text is now the shipped one.");
            } catch (_error) {}
          };
          editor.addEventListener("keydown", keyEvent => {
            keyEvent.stopPropagation();
            if (keyEvent.key === "Escape") { keyEvent.preventDefault(); finish(false); }
            else if (keyEvent.key === "Enter" && (keyEvent.ctrlKey || keyEvent.metaKey)) {
              keyEvent.preventDefault();
              finish(true);
            }
          });
          editor.addEventListener("blur", () => finish(false));
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
        if (marker.matches(":focus-within") || popup.matches(":focus-within")) position();
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
      position();
    };
    marker.addEventListener("pointerenter", open);
    marker.addEventListener("pointerleave", scheduleClose);
    marker.addEventListener("focus", open);
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
      element("p", {role: "alert"}, error.message)));
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
          element("summary", {}, row.name), element("pre", {tabindex: 0}, row.text))))).catch(() => {});
    }).catch(error => section.replaceChildren(element("h2", {}, "Credits"),
      element("p", {role: "alert"}, error.message)));
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
    if (!main.querySelector(".lex-plugin-mod-loading")) parent.append(modLoadingPanel(pluginId));
    if (!main.querySelector(".lex-plugin-credits")) parent.append(creditsPanel(pluginId));
  };

  const unitField = (control, unit, attrs = {}) => {
    const boxed = attrs.boxed ?? (control instanceof Element &&
      control.matches("input,select,textarea,output,.lex-readonly-field"));
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
    }, control, unit ? element("span", {
    class: ["lex-unit", unit === "×" ? "lex-unit-multiplier" : "", attrs.unitClass || ""].filter(Boolean).join(" "),
    "aria-hidden": "true",
    }, unit) : null);
    if (boxed && unit && !prefix) followUnit(field, control);
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
      const reserved = parseFloat(getComputedStyle(field).getPropertyValue("--lex-unit-reserve")) || 0;
      const limit = Math.max(0, field.clientWidth - unitNode.offsetWidth - reserved);
      const left = Math.min(border + start + measured + gap, limit);
      const next = `${Math.round(left)}px`;
      if (unitNode.style.left !== next) unitNode.style.left = next;
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
    const numeric = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(numeric)) return String(value);
    return new Intl.NumberFormat("en-US", {
      useGrouping: true,
      maximumFractionDigits: 20,
      ...options,
    }).format(numeric);
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
  const DETAIL_BODY_LAYOUTS = {stacked: "", beside: "lex-detail-panel-beside"};

  const detailPanel = (options = {}) => {
    const bodyClass = ["lex-detail-panel-body", DETAIL_BODY_LAYOUTS[options.bodyLayout] || ""].filter(Boolean).join(" ");
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
          element("span", {class: "lex-detail-panel-name"}, options.title ?? ""));
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
    if (options.title !== undefined || options.titleControl || options.renameRecord)
      title.append(copyValueButton(titleText, "Copy this name"));
    if (options.help) title.append(infoHelp(options.help));
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
      options.icon ? element("div", {class: "lex-detail-panel-icon"}, options.icon) : null,
      identity,
      options.actions ? element("div", {class: "lex-detail-panel-actions"}, options.actions) : null);
    return element("section", {
      ...(options.attrs || {}),
      class: ["lex-detail-panel", "lex-detail", options.headingOverlay ? "lex-detail-panel-media" : "", options.tone ? `lex-panel-tone-${options.tone}` : "", heading ? "" : "no-heading", options.className || ""].filter(Boolean).join(" "),
    }, heading, options.paginate ? paginateSettings(element("div", {class: bodyClass}, options.body || [])) : element("div", {class: bodyClass}, options.body || []));
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

  const tabbedPanel = (options = {}) => {
    const suppliedTabs = options.tabs || [];
    const title = tab => String(tab.label instanceof Node ? tab.label.textContent : tab.label ?? tab.id);
    // A misc tab is written with its full stop and comes last, after
    // every named area, with a tweaks tab after it when a panel has one.
    const tabRank = tab => {
      const id = String(tab.id).toLocaleLowerCase();
      return id === "tweaks" ? 2 : id === "misc" ? 1 : 0;
    };
    const tabTitle = tab => {
      const name = title(tab);
      return String(tab.id).toLocaleLowerCase() === "misc" && name === "Misc"
        ? "Misc." : name;
    };
    const tabs = [...suppliedTabs].sort((a,b)=>tabRank(a)-tabRank(b)
      ||tabTitle(a).localeCompare(tabTitle(b),undefined,{numeric:true,sensitivity:"base"}));
    const active = tabs.some(tab => tab.id === options.active)
      ? options.active
      : suppliedTabs[0]?.id;
    const selected = tabs.find(tab => tab.id === active);
    const content = typeof options.content === "function"
      ? options.content(active, selected)
      : options.content;
    return guardNestedTabs(element("section", {
      ...(options.attrs || {}),
      class: ["lex-tabbed-panel", options.className || ""].filter(Boolean).join(" "),
    }, subtabBar({
      tabs,
      active,
      label: options.label || "Panel views",
      className: "lex-tabbed-panel-tabs",
      shortcuts: false,
      change: options.change,
    }), element("div", {
      class: ["lex-tabbed-panel-content", options.contentClassName || ""].filter(Boolean).join(" "),
      role: "tabpanel",
      "aria-label": selected?.label || "Panel content",
    }, content || [])));
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
      control.replaceChildren(...list.map(entry => element("option", {value: entry.value}, entry.label)));
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
  const flushAutoFit = () => {
    const controls = [...autoFitQueue].filter(control => control.isConnected);
    autoFitQueue.clear();
    controls.forEach(control => control.__lexAutoFitReset());
    const sizes = controls.map(control => control.__lexAutoFitMeasure());
    controls.forEach((control, index) => control.__lexAutoFitApply(sizes[index]));
  };
  const queueAutoFit = control => {
    if (!autoFitQueue.size) requestAnimationFrame(flushAutoFit);
    autoFitQueue.add(control);
  };
  // One observer for every fitted control, held here for the life of the page.
  const autoFitObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(entries => {
      entries.forEach(entry => autoFitQueue.add(entry.target));
      flushAutoFit();
    })
    : null;
  const autoFitControlText = (control, options = {}) => {
    if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement)) return control;
    if (control.dataset.lexAutofit === "false") return control;
    if (control.__lexAutoFitUpdate) {
      control.__lexAutoFitUpdate();
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
      const maximum = control instanceof HTMLTextAreaElement || control.closest(".lex-column-list")
        ? Number.parseFloat(style.fontSize) || 16
        : Math.max(minimum,Math.min(28,control.clientHeight*.78));
      const horizontal = (Number.parseFloat(style.paddingLeft) || 0) +
        (Number.parseFloat(style.paddingRight) || 0) +
        (Number.parseFloat(style.borderLeftWidth) || 0) +
        (Number.parseFloat(style.borderRightWidth) || 0) +
        (control instanceof HTMLSelectElement ? 22 : 2);
      const available = Math.max(1, control.clientWidth - horizontal);
      const value = control instanceof HTMLSelectElement
        ? control.selectedOptions[0]?.textContent || ""
        : control.value || control.placeholder || "";
      const canvas = autoFitControlText.canvas ||= document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context || !value) return null;
      context.font = `${style.fontStyle} ${style.fontWeight} ${maximum}px ${style.fontFamily}`;
      const measured = context.measureText(value).width;
      const size = Math.max(minimum,Math.min(maximum,maximum*available/Math.max(1,measured)));
      // The ceiling above is read from the box's natural height, and that
      // height comes from the text. Enlarged digits would make the box taller,
      // the next fit would read a taller box, and every numeric property grew
      // instead of filling. Text larger than the natural font therefore keeps
      // the natural box: the digits fill it, the box stays where it was.
      const natural = Number.parseFloat(style.fontSize) || 0;
      return {size, height: size > natural ? control.getBoundingClientRect().height : 0};
    };
    const reset = () => {
      control.style.fontSize = "";
      control.style.height = "";
      control.style.boxSizing = "";
    };
    const apply = fit => {
      if (!fit) return;
      if (fit.height) {
        control.style.boxSizing = "border-box";
        control.style.height = `${fit.height}px`;
      }
      control.style.fontSize = `${fit.size}px`;
    };
    const update = () => {
      reset();
      apply(measure());
    };
    control.addEventListener("input", update);
    control.addEventListener("change", update);
    control.__lexAutoFitUpdate = update;
    control.__lexAutoFitMeasure = measure;
    control.__lexAutoFitReset = reset;
    control.__lexAutoFitApply = apply;
    autoFitObserver?.observe(control);
    document.fonts?.ready?.then(() => queueAutoFit(control));
    queueAutoFit(control);
    return control;
  };

  // Every value box on a panel should end at the same edge, so the reference
  // rail takes the widest requirement in that panel rather than each control
  // keeping its own.
  const alignReferenceRails = (container = document) => {
    const panels = new Set();
    container.querySelectorAll?.(".lex-source-control[data-lex-rail-tag]")
      .forEach(control => panels.add(
        control.closest(".lex-detail-panel-body, .lex-detail-panel, .lex-detail") || container));
    for (const panel of panels) {
      const controls = [...panel.querySelectorAll(".lex-source-control[data-lex-rail-tag]")];
      if (!controls.length) continue;
      // Each entry gets an equal share of the space beside the property it
      // annotates, so a deeper stack is a smaller stack rather than a taller
      // row.
      for (const control of controls) {
        const stack = control.querySelector(":scope > .lex-reference-values");
        const count = stack?.children.length || 0;
        if (!count) {
          control.style.removeProperty("--lex-reference-slot");
          control.style.removeProperty("--lex-reference-cap");
          continue;
        }
        // The share is taken from the PROPERTY ROW, not from the value box
        // inside it. The box is the shorter of the two, and dividing that by
        // three left a three-deep stack at seven pixels - it fitted, and it
        // could not be read. The row is the space actually available beside
        // the box, and staying inside it is what keeps the stack from making
        // the row taller.
        const row = control.closest(".lex-detail-field") || control;
        const cap = Math.max(12, Math.round(row.getBoundingClientRect().height) - 4);
        control.style.setProperty("--lex-reference-cap", `${cap}px`);
        control.style.setProperty("--lex-reference-slot", `${Math.max(6, Math.floor(cap / count))}px`);
      }
      // The rail is reserved in advance from the longest tag and the longest
      // value any control on this panel can ever put in it, measured in a
      // hidden copy of a real entry rather than from the entries on screen.
      // Two earlier attempts both moved the value boxes as values changed: a
      // character count times a guessed em over-reserved by half a rail, and
      // measuring what was displayed re-sized the rail on every edit that
      // matched or stopped matching a reference. The probe is pinned to the
      // largest type a stack ever uses, because a deeper stack only ever
      // draws smaller.
      const longest = (attribute, floor) => controls
        .map(control => control.dataset[attribute] || "")
        .reduce((widest, text) => text.length > widest.length ? text : widest, floor);
      const probe = element("div", {
        class: "lex-source-strip lex-reference-values lex-reference-probe",
        "aria-hidden": "true",
      }, element("span", {class: "lex-reference-value"},
        element("span", {class: "lex-reference-tag"}, longest("lexRailTag", "V")),
        element("span", {class: "lex-reference-text"}, longest("lexRailValue", "000"))));
      (controls[0].parentElement || panel).append(probe);
      const tag = Math.ceil(probe.querySelector(".lex-reference-tag").getBoundingClientRect().width);
      const text = Math.ceil(probe.querySelector(".lex-reference-text").getBoundingClientRect().width);
      probe.remove();
      // tag + the column gap the stack opens between the two + the value, and
      // two pixels so the last glyph is not flush against the panel edge.
      const widest = tag + text + 6;
      panel.style?.setProperty("--lex-panel-reference-rail-width", `${widest}px`);
      panel.style?.setProperty("--lex-reference-tag-width", `${tag}px`);
      for (const control of controls) {
        control.style.setProperty("--lex-reference-requested-width", `${widest}px`);
        control.style.setProperty("--lex-reference-tag-width", `${tag}px`);
      }
    }
    // An inside rail lives in the value box, so its share comes from that box
    // rather than from the property row: it is capped at the box's own height.
    // Uncapped, a drawer's strip was taller than the value it labelled and
    // stood above it, which read as a rail that had left its box. These
    // controls have no outside rail, so their share is measured on its own -
    // a graph card's variable drawer is a panel with nothing else in it.
    container.querySelectorAll?.(".lex-source-control[data-lex-inside-rail]").forEach(control => {
      const stack = control.querySelector(":scope > .lex-reference-values");
      const count = stack?.children.length || 0;
      if (!count) return;
      // The box the rail shares is the control's own input, not the grid cell
      // around it: a drawer's cell is taller than the box inside it, and
      // measuring the cell left the strip taller than the value again.
      const box = control.querySelector("input:not([type=checkbox]), select, output, textarea")
        || control.querySelector(":scope > .lex-unit-field, :scope > .lex-readonly-field") || control;
      const cap = Math.max(12, Math.round(box.getBoundingClientRect().height) - 2);
      control.style.setProperty("--lex-reference-cap", `${cap}px`);
      control.style.setProperty("--lex-reference-slot", `${Math.max(6, Math.floor(cap / count))}px`);
      // The lane is measured from the longest entry this rail can paint, at the
      // size it paints it. The old character-count estimate was tuned for the
      // shared symbol font at an outside rail's small size; an inside rail
      // draws at the value's own size, so "V 255" in a game font came out wider
      // than the lane reserved for it and left the box.
      const probe = element("span", {class: "lex-reference-value lex-reference-probe-value",
        "aria-hidden": "true"},
        element("span", {class: "lex-reference-tag"}, control.dataset.lexInsideTag || "V"),
        element("span", {class: "lex-reference-text"}, control.dataset.lexInsideValue || ""));
      control.append(probe);
      const width = Math.ceil(probe.getBoundingClientRect().width) + 2;
      probe.remove();
      if (width > 2) control.style.setProperty("--lex-internal-reference-requested-width", `${width}px`);
    });
  };

  // Refresh every mounted reference display from its live control value. This
  // is the single update path for all plugins and all control types.
  const refreshReferences = (container = document) => {
    container.querySelectorAll?.(".lex-source-control").forEach(node => node.refreshReference?.());
    alignReferenceRails(container);
  };
  // The first pass measures the rail against whatever face is loaded at the
  // time. A face only starts loading when something asks to paint with it, so
  // a panel that mounts after the document is otherwise ready measures its
  // rail against the fallback and re-reserves it a pixel or two later, on the
  // reader's first edit. Every batch of faces that finishes re-reserves it
  // instead, which is what the rail exists to prevent.
  document.fonts?.addEventListener?.("loadingdone", () => alignReferenceRails(document));
  document.fonts?.ready?.then(() => alignReferenceRails(document));

  // Shared Detail internals. A game supplies its theme and field controls;
  // this component owns the repeated section and field structure.
  const detailSection = (options = {}) => element(options.collapsible ? "details" : "section", {
    ...(options.attrs || {}),
    class: ["lex-detail-section", options.className || ""].filter(Boolean).join(" "),
    "aria-label": options.ariaLabel || (typeof options.title === "string" ? options.title : null),
    ...(options.collapsible && options.open ? {open: true} : {}),
  }, options.title ? element(options.collapsible ? "summary" : "h3", {class: "lex-detail-section-title"},
    options.title, options.help || null) : null,
  element("div", {class: "lex-detail-section-content"}, options.body || []));

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
  const actionRow = (...children) => element("div", {class: "lex-action-row"}, ...children);

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
  const tileGrid = (cards = [], options = {}) => element("div", {
    class:"lex-tile-grid",
    style:`--lex-tile-min-width:${Math.max(80,Number(options.minWidth)||320)}px;${options.columns ? `--lex-tile-columns:repeat(${Math.max(1,Math.floor(options.columns))},minmax(0,1fr))` : ""}`,
  }, ...cards);
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
  const choiceField = (value, action) => element("span", {class:"lex-choice-field"}, value, action);
  const quantityChoice = (choice, quantity) => element("div", {class:"lex-quantity-choice"},
    choice, element("span", {class:"lex-quantity-mark","aria-hidden":"true"}, "×"), quantity);
  const iconValue = ({icon,label,toggle,control}) => element("div",{class:"lex-icon-value"},
    element("label",{class:"lex-icon-value-toggle",title:`${label}: toggle immunity`},toggle,element("span",{class:"lex-icon-value-art"},icon),
      element("span",{},label)),control);
  const textArea = (options = {}) => element("textarea", {rows:4, ...options,
    class:["lex-text-area", options.class || ""].filter(Boolean).join(" ")});

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
  // message says what is happening until it has. `busy` shows a spinner in
  // place of words. The message node is stage.lexMessage.
  const modelStage = (options = {}) => {
    const message = element("div", {class: "lex-model-stage-message"},
      options.busy ? element("div", {class: "lex-model-stage-spin", "aria-hidden": "true"}) : (options.message ?? ""));
    const stage = element("div", {class: ["lex-model-stage", options.className || ""].filter(Boolean).join(" ")}, message);
    stage.lexMessage = message;
    return stage;
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
    const backdrop=element("div",{class:"lex-dialog-backdrop lex-map-magnifier-backdrop","data-lex-history-control":true});
    const note=element("p",{class:"lex-map-magnifier-note"});
    const body=element("div",{class:"lex-map-magnifier-body"});
    const close=()=>{document.removeEventListener("keydown",onKey,true);backdrop.remove();};
    const onKey=event=>{if(event.key==="Escape"){event.preventDefault();close();}};
    const draw=()=>{
      const spec=options.magnify()||{},place=spec.place;
      note.textContent=spec.note||"Point at the map to read the value, then click to place the point.";
      body.replaceChildren(imageMap({...spec,fill:true,magnify:null,crosshair:true,
        place:place?point=>{place(point);draw();}:undefined}));
    };
    const done=element("button",{type:"button",class:"lex-dialog-action primary",onclick:close},"Close");
    backdrop.append(element("section",{class:"lex-dialog lex-map-magnifier-dialog",role:"dialog","aria-modal":"true",
      "aria-label":`${options.label||"Map"}, full size`},
      element("h2",{},options.label||"Map"),note,body,element("div",{class:"lex-dialog-actions"},done)));
    document.body.append(backdrop);
    document.addEventListener("keydown",onKey,true);
    draw();
    done.focus();
    return backdrop;
  };

  // Map coordinates are fractions of the image, independent of UI zoom.
  const imageMap = (options = {}) => {
    const stage=element("div",{class:"lex-image-map-stage",style:`aspect-ratio:${Number(options.ratio)||4/3};--lex-map-columns:${Number(options.columns)||1};--lex-map-rows:${Number(options.rows)||1}`},
      options.media || (options.image?element("img",{src:options.image,alt:options.label||"Map",draggable:false}):null));
    if(options.cells?.length)stage.append(element("div",{class:"lex-image-map-cells"},...options.cells.map(cell=>
      element("button",{type:"button",class:cell.selected?"selected":"",title:cell.title||cell.label,
        "aria-label":cell.label,"aria-pressed":!!cell.selected,onclick:()=>options.select?.(cell.id)}))));
    for(const point of options.points||[])stage.append(element("button",{type:"button",class:`lex-image-map-point${point.selected?" selected":""}${point.className?" "+point.className:""}`,
      style:`left:${point.x*100}%;top:${point.y*100}%`,title:point.label,"aria-label":point.label,
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
      stage.append(readout);
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
    const image=stage.querySelector('img');
    if(image&&!options.ratio){const fit=()=>{if(!image.naturalWidth||!image.naturalHeight)return;const ratio=image.naturalWidth/image.naturalHeight;root.style.setProperty('--lex-map-ratio',String(ratio));stage.style.aspectRatio=String(ratio)};image.addEventListener('load',fit);fit();}
    root.lexStage=stage;
    // A map in a panel is small, and a stored coordinate is not. The magnifier
    // opens the same map at the size of the window, with the same markers and the
    // same click, so a point is placed against the art. `magnify` returns that
    // view's options from the caller's own state, so each placement redraws the
    // markers where the record is now.
    if(typeof options.magnify==="function")
      root.append(element("button",{type:"button",class:"lex-image-map-magnify",
        title:"Open the large map","aria-label":`Open the large map: ${options.label||"map"}`,
        onclick:event=>{event.stopPropagation();mapMagnifier(options);}},magnifyIcon()));
    return root;
  };

  const statCard = (options = {}) => element("div", {class:"lex-stat-card"},
    options.image ? element("img", {src:options.image,alt:options.label || "",
      onerror:event=>{event.target.hidden=true;}}) : null,
    element("div", {class:"lex-stat-card-ranks"}, ...(options.ranks || [])),
    // A game that names the card's type in a word rather than one glyph asks
    // for a corner wide enough to hold the word.
    options.corner ? element("div", {class:["lex-stat-card-corner", options.cornerWord ? "lex-stat-card-corner-word" : ""]
      .filter(Boolean).join(" ")}, options.corner) : null,
    options.footer ? element("div", {class:"lex-stat-card-footer"}, options.footer) : null);

  const choicePopover = (options = {}) => {
    const popup = element("div", {class:"lex-choice-popover",popover:"auto",role:"group",
      "aria-label":options.label || "Choose a value"}, ...(options.choices || []).map(choice =>
      element("button", {type:"button","aria-label":choice.label,onclick:()=>{popup.hidePopover();options.select?.(choice.value);}},
        choice.icon || null, element("span",{},choice.label))));
    popup.addEventListener("keydown", event => {
      if (!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const buttons=[...popup.querySelectorAll("button")], step=["ArrowUp","ArrowLeft"].includes(event.key)?-1:1;
      buttons[(buttons.indexOf(document.activeElement)+step+buttons.length)%buttons.length]?.focus();
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
      popup.querySelector("button")?.focus();
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
      if (input.matches('input[type="checkbox"]')) {
        // Keep the whole icon inside the row, above the leader near the box.
        // Rectangles include UI zoom; positioned offsets use unscaled pixels.
        const scale = owner.width / control.offsetWidth || 1;
        pin.style.setProperty("left", `${(target.left - owner.left - icon.width - 6 * scale) / scale}px`, "important");
        pin.style.setProperty("top", `${(target.top - owner.top - icon.height / 2) / scale}px`, "important");
        pin.style.setProperty("right", "auto", "important");
        return;
      }
      const inset = Math.min(3, target.height * .1);
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
      const targetX = target.right + (outward ? inset : -inset - overhangX);
      const targetY = target.top + (outward ? -inset : inset + dropY);
      const scale = owner.width / control.offsetWidth || 1;
      pin.style.setProperty("left", `${(targetX - owner.left - tipX) / scale}px`, "important");
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
      class: ["lex-detail-parts", switches ? "lex-detail-parts-switches" : "", !switches && list.every(part=>part instanceof Element) ? "lex-detail-parts-bare" : "", options.stacked ? "lex-detail-parts-stacked" : "", options.className || ""]
        .filter(Boolean).join(" "),
      style: `--lex-part-columns:${columns};--lex-multi-number-columns:${columns}`,
      "data-lex-copy-parts": options.copy ? "" : null,
      role: options.role, "aria-label": options.label,
    }, ...list.map(part => detailPart(part, options)));
  };

  const controlGroup = (parts, options = {}) => detailParts(parts, options);

  const detailField = (options = {}) => {
    if (Array.isArray(options.controls)) {
      options = {...options, control: detailParts(options.controls)};
    }
    const control = options.control instanceof Element && options.control.matches('input[type="checkbox"]')
      ? element("div", {class:"lex-source-control no-reference"}, options.control)
      : options.control;
    const pin = options.pin || null;
    const input = control instanceof Element
      ? (control.matches("input,select,textarea,output,.lex-readonly-field")
        ? control : control.querySelector("input,select,textarea,output,.lex-readonly-field"))
      : null;
    const inputType = String(input?.type || "").toLocaleLowerCase();
    const step = input?.getAttribute?.("step") ?? input?.dataset?.step;
    const numericLike = inputType === "number" || (
      ["numeric", "decimal"].includes(String(input?.inputMode || "").toLocaleLowerCase()) &&
      step !== null && step !== undefined && step !== "");
    const readOnly = Boolean(input && (
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
    if (input && !readOnly && dataType === "INT") {
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
        options.tone ? `lex-tone-${options.tone}` : "", options.className || ""].filter(Boolean).join(" "),
      "data-lex-type": dataType,
      "data-lex-property": options.property
        || pin?.getAttribute?.("data-lex-pin-column") || null,
      "data-lex-readonly": String(readOnly),
      // The property name is wrapped so it is a real flex item. Left as a bare
      // text node it was an anonymous item the leader arrow could shrink to
      // nothing, which wrapped "CAN SELL" one letter per line and drove the
      // label fitter down to its six-pixel floor.
      }, element("div", {class: "lex-detail-field-label"},
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
      // Upright, inside the value box, hard against its right edge.
      const host = control instanceof Element && control.matches(".lex-unit-field")
        ? control : (input?.parentElement || node);
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
    // A drag slider is only honest when a pixel of travel is worth a sensible
    // amount. Over a raw INT32 field the whole range is four billion wide, so
    // the pointer lands a hair off centre and writes -24832854 into a price -
    // the control looks broken because it is being asked to resolve four
    // billion values across three hundred pixels. Past this span the value gets
    // a plain number box with no fill and no handle.
    const SLIDER_MAX_STEPS = 100000;
    const boundedSpan = Number.isFinite(lowBound) && Number.isFinite(highBound)
      ? (highBound - lowBound) / (Number(step) || 1) : Infinity;
    if (input && !readOnly && numericLike &&
        Number.isFinite(lowBound) && Number.isFinite(highBound) && highBound > lowBound &&
        boundedSpan <= SLIDER_MAX_STEPS) {
      const fill = element("span", {class: "lex-value-fill", "aria-hidden": "true"});
      const handle = element("span", {class: "lex-value-handle", "aria-hidden": "true"});
      fill.append(handle);
      const ratio = () => {
        const value = readNumeric(input);
        if (!Number.isFinite(value)) return 0;
        return Math.max(0, Math.min(1, (value - lowBound) / (highBound - lowBound)));
      };
      const paint = () => fill.style.setProperty("--lex-value-ratio", String(ratio()));
      input.__lexValueSliderPaint = paint;
      input.addEventListener("input", paint);
      input.addEventListener("change", paint);
      const box = () => (control instanceof Element && control.matches(".lex-unit-field")
        ? control : input);
      const setFromPointer = event => {
        const bounds = box().getBoundingClientRect();
        const share = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
        const step = Number(input.step) || 1;
        const raw = lowBound + share * (highBound - lowBound);
        const snapped = Math.round(raw / step) * step;
        const nextValue = Math.max(lowBound, Math.min(highBound, snapped));
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
        const stop = () => {
          if (stopped) return;
          stopped = true;
          flushPointer();
          handle.removeEventListener("pointermove", move);
          handle.removeEventListener("pointerup", stop);
          handle.removeEventListener("pointercancel", stop);
          node.classList.remove("lex-value-dragging");
          input.lexValueSliderDragging = false;
          input.dispatchEvent(new Event("change", {bubbles: true}));
        };
        handle.addEventListener("pointermove", move);
        handle.addEventListener("pointerup", stop);
        handle.addEventListener("pointercancel", stop);
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
      input.addEventListener("focus", () => requestAnimationFrame(() => input.select?.()));
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
      const label = element("label", {
        class: ["lex-toggle", toggle.className || ""].filter(Boolean).join(" "),
        "data-lex-toggle": toggle.key || toggle.label || "",
      }, rail, toggle.decorateControl ? toggle.decorateControl(input) : input,
      toggle.icon || null, element("span", {class: "lex-toggle-name"}, toggle.label,
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
    {columns: options.columns, stacked: options.stacked, copy: !options.stacked,
     className: ["lex-multi-number", options.className || ""].filter(Boolean).join(" ")});

  // Nested navigation is a shared control. Plugins provide only labels,
  // active state, and the page-owned change callback.
  // A page with one subtab has no choice to offer, so it shows no bar. A bar
  // with a single tab in it reads as a control that does nothing.
  const subtabBar = (options = {}) => (options.tabs || []).length < 2
    ? element("div", {class: "lex-subtab-bar lex-subtab-bar-single", hidden: true})
    : element("div", {
    class: ["lex-subtab-bar", options.flush === true ? "lex-subtab-bar-flush" : "",
      options.images ? "lex-subtab-bar-images" : "",
      options.className || ""].filter(Boolean).join(" "),
    role: "tablist",
    "data-lex-subtab-shortcuts": String(options.shortcuts !== false),
    "aria-label": options.label || "Subsections",
    }, ...(options.tabs || []).map((tab, index) => {
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
      disabled:!!tab.disabled,
      class: ["lex-subtab-button", tab.id === options.active ? "active" : ""].filter(Boolean).join(" "),
      role: "tab",
      "aria-selected": String(tab.id === options.active),
      tabindex: tab.id === options.active ? "0" : "-1",
      onclick: () => options.change?.(tab.id),
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
  }, `⇧${key}`) : "")(shortcutKeyFor(index + 1)));
    }));

  // The key that selects the Nth tab, matching the shortcut sequence:
  // 1-9, then 0 for the tenth, then - and = for the eleventh and twelfth.
  // Positions past that have no key, so they get no badge.
  const shortcutKeyFor = position => (
    position <= 9 ? String(position)
    : position === 10 ? "0"
    : position === 11 ? "-"
    : position === 12 ? "=" : "");

  const mathFormula = (source) => {
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
      if (/^[ABCD]$/.test(token)) name.setAttribute("class", `lex-curve-variable-${token.toLowerCase()}`);
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
    const mathSource = mathOverlay?.querySelector(":scope > math");
    const mathAtoms = [];
    if (mathSource) {
      mathOverlay.classList.add("lex-curve-math-follow");
      mathOverlay.setAttribute("role", "img");
      mathOverlay.setAttribute("aria-label", options.formula.title || mathSource.getAttribute("aria-label") || mathSource.textContent);
      mathSource.classList.add("lex-curve-math-source");
      mathSource.setAttribute("aria-hidden", "true");
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
    const curveVariableKeys = (options.variables || []).map(variable =>
      String(variable.label || "").trim()).filter(Boolean);
    const curveVariableSet = new Set(curveVariableKeys.map(key => key.toLocaleLowerCase()));
    const formulaContent = source => {
      if (source?.cloneNode) return source.cloneNode(true);
      const text = String(source ?? "");
      if (!curveVariableKeys.length) return text;
      const escaped = curveVariableKeys
        .sort((left, right) => right.length - left.length)
        .map(key => key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      const matcher = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");
      const fragment = document.createDocumentFragment();
      let offset = 0;
      for (const match of text.matchAll(matcher)) {
        if (match.index > offset) fragment.append(text.slice(offset, match.index));
        const key = match[0].toLocaleLowerCase();
        fragment.append(element("span", {class: `lex-curve-variable-${key}`}, match[0]));
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
    svg.append(grid, fill, bars, line, formulaGuide, rangeLow, rangeHigh, formulaText, guide, marker);

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
        const key = String(variable.label || "").trim().toLocaleLowerCase();
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
      element("div", {class: "lex-curve-formula"}, formulaContent(options.formula)),
      status);

    const variableKeys = curveVariableSet;
    const formulaTokens = [...root.querySelectorAll(".lex-curve-path-formula [class]")];
    formulaTokens.forEach(token => {
      const match = [...token.classList].find(name => {
        if (!name.startsWith("lex-curve-variable-")) return false;
        const key = name.slice("lex-curve-variable-".length);
        return variableKeys.has(key);
      });
      if (match) token.dataset.curveVariable = match.slice("lex-curve-variable-".length);
    });
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
      const plotBounds = plot.getBoundingClientRect();
      const tooltipBounds = tooltip.getBoundingClientRect();
      const inset = 4;
      const halfWidth = tooltipBounds.width / 2;
      /* Centre the readout on the pointer across neighbouring graph space.
         Clamp only at the real window edge; clamping to each small plot made
         the label drift away from the cursor near every card boundary. */
      const viewportCenter = Math.max(inset + halfWidth,
        Math.min(innerWidth - inset - halfWidth, event.clientX));
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
      } else {
        this.undoStack.push({...pending, after, afterSignature, time: now});
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
      root.addEventListener("keydown", event => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
        const key = event.key.toLowerCase();
        if (key !== "z" && key !== "y") return;
        event.preventDefault();
        const active = document.activeElement;
        if (active?.matches?.("input,textarea,select")) active.blur();
        setTimeout(() => key === "y" || event.shiftKey ? this.redo() : this.undo(), 0);
      }, true);
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

  const paginateSettings = (content, options = {}) => {
    content.classList.add("lex-tweak-card-grid");
    const cards = [...content.children];
    if(options.columnMajor)cards.sort((a,b)=>(a.querySelector(".lex-detail-panel-title,.lex-detail-section-title")?.textContent||a.textContent).localeCompare(b.querySelector(".lex-detail-panel-title,.lex-detail-section-title")?.textContent||b.textContent,undefined,{sensitivity:"base"}));
    const size = options.pageSize || 0;
    let page = 0;
    // Where each page starts, as an index into the visible cards. Cards differ
    // in height, so one count per page was only ever right for the page it was
    // measured on: a page of tall cards ran under the pager.
    let starts = [0];
    let pagedCount = -1;
    const footer = element("div", {class:"lex-tweaks-pages"});
    const scroll = element("div", {class:"lex-tweaks-scroll", tabindex:"-1"}, content);
    const root = element("div", {class:"lex-tweaks-paged"}, scroll, footer);

    // Fill each page until one more card would overflow the box. A caller
    // that genuinely wants a fixed count passes pageSize.
    const overflows = () => scroll.scrollHeight > scroll.clientHeight + 1;
    let cardHeights = new WeakMap();
    const columnCount = length => {
      const width=content.clientWidth||scroll.clientWidth;
      const gap=parseFloat(getComputedStyle(content).columnGap)||12;
      // Allow room for the shared name, copy button, value and help lanes.
      // Narrower cards clipped flag names and could abort strict pagination.
      // A caller can supply a measured minimum for a simpler card.
      const asked=parseFloat(getComputedStyle(content).getPropertyValue("--lex-tweak-card-width"));
      const target=asked||400;
      const fit=Math.max(1,Math.min(length,Math.floor((width+gap)/(target+gap))||1));
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
      for (const {piece, subSplit} of inOrder) {
        const body = original(piece).querySelector(":scope > :is(.lex-detail-section-content,.lex-detail-panel-body,.settings-subs)");
        const rest = piece.querySelector(":scope > :is(.lex-detail-section-content,.lex-detail-panel-body,.settings-subs)");
        if (subSplit && body && rest) {
          const continued = rest.querySelector(':scope > [data-lex-continued="true"]');
          const fields = subSplit.querySelector(":scope > .settings-fields");
          const moved = continued?.querySelector(":scope > .settings-fields");
          if (fields && moved) fields.append(...moved.children);
          continued?.remove();
        }
        if (body && rest) body.append(...rest.children);
        piece.remove();
        const at = cards.indexOf(piece);
        if (at >= 0) cards.splice(at, 1);
      }
      pieces = [];
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
        if(options.strictColumns){
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
          if(why){scroll.style.overflowY="auto";throw new RangeError(`Tweak cannot fit one column: ${card.querySelector('.lex-detail-panel-title,.lex-detail-section-title,h2')?.textContent||card.textContent.slice(0,80)} - ${why}`);}
        }
      }
      const count=columnCount(visible.length),gap=parseFloat(getComputedStyle(content.querySelector('.lex-tweak-column') || content).rowGap)||12;
      const available=scroll.clientHeight,loads=Array(count).fill(0),next=[0];
      let orderedLane=0;
      for(let index=0;index<visible.length;index++){
        const height=cardHeights.get(visible[index])||0;
        let lane=options.columnMajor?orderedLane:loads.indexOf(Math.min(...loads));
        if(loads[lane]>0&&loads[lane]+gap+height>available+1){
          if(options.columnMajor&&lane<count-1)lane=++orderedLane;
          else {next.push(index);loads.fill(0);lane=0;orderedLane=0;}
        }
        loads[lane]+=(loads[lane]?gap:0)+height;
      }
      starts=next;
    };

    // Measure at the final width, then fill ordered columns from top to bottom.
    const deal = onPage => {
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
      if(options.columnMajor&&heights.every(height=>height!==undefined)&&count>1){
        const total=heights.reduce((sum,height)=>sum+height,0)+gap*Math.max(0,onPage.length-count);
        const share=Math.max(Math.max(...heights),total/count);
        const lanes=[],sums=Array(count).fill(0);
        let at=0;
        heights.forEach((height,index)=>{
          const left=onPage.length-index;
          if(sums[at]>0&&at<count-1&&(sums[at]+gap+height>share+1||left<=count-1-at))at++;
          lanes.push(at);sums[at]+=(sums[at]?gap:0)+height;
        });
        if(sums.every(sum=>sum<=scroll.clientHeight+1))lanesFor=lanes;
      }
      onPage.forEach((card,index)=>{
        const measured=cardHeights.get(card);
        let lane=measured===undefined?index%count:loads.indexOf(Math.min(...loads));
        if(lanesFor)lane=lanesFor[index];
        else if(options.columnMajor&&measured!==undefined){
          if(loads[orderedLane]>0&&loads[orderedLane]+gap+measured>scroll.clientHeight+1)orderedLane=Math.min(count-1,orderedLane+1);
          lane=orderedLane;
        }
        columns[lane].append(card);loads[lane]+=(loads[lane]?gap:0)+(measured||0);
      });
      const shown=new Set(onPage);
      const off=element("div",{class:"lex-tweak-off-page",hidden:true},...cards.filter(card=>!shown.has(card)));
      content.replaceChildren(...columns,off);
    };

    const render = () => {
      let visible = cards.filter(card => !card.hidden);
      // Paginating can split a tall section into pieces, so read the cards
      // again afterwards.
      if (visible.length !== pagedCount) { paginate(visible); visible = cards.filter(card => !card.hidden); }
      const pages = starts.length;
      page = Math.max(0, Math.min(page, pages - 1));
      const from = starts[page], to = starts[page + 1] ?? visible.length;
      deal(visible.slice(from, to));
      const focused = footer.contains(document.activeElement) ? document.activeElement : null;
      const selection = focused && [focused.selectionStart, focused.selectionEnd];
      const label = focused?.getAttribute("aria-label");
      footer.replaceChildren(pager({page, pages, total:visible.length, range:[from + 1, to],
        search:options.search, change:turn}));
      if (label && focused?.matches("input")) {
        const replacement = [...footer.querySelectorAll("input")].find(input=>input.getAttribute("aria-label")===label);
        replacement?.focus();
        if (selection && selection[0] !== null) replacement?.setSelectionRange(...selection);
      }
      scroll.style.overflowY = overflows() ? "auto" : "hidden";
    };

    const turn = value => {page = value; render(); scroll.scrollTop = 0;};
    // Re-break the pages for the box as it is now, keeping the first card on
    // screen on screen.
    const refit = () => {
      let visible = cards.filter(card => !card.hidden);
      const anchor = visible[starts[page]] || null;
      paginate(visible);
      visible = cards.filter(card => !card.hidden);
      const at = anchor ? Math.max(0, visible.indexOf(anchor)) : 0;
      page = Math.max(0, starts.findLastIndex(start => start <= at));
      render();
    };
    wheelPages(scroll, direction => {
      const target = page + direction;
      if (target >= 0 && target < starts.length) turn(target);
    }, overflows);
    root.refreshPages = () => {page=0;pagedCount=-1;refit();};
    // What the pager decided, for checks and for debugging a page break.
    root.lexPaging = () => ({starts:[...starts],page,
      cards:cards.filter(card=>!card.hidden).map(card=>({title:(card.querySelector(".lex-detail-panel-title,.lex-detail-section-title")?.textContent||"").trim(),height:cardHeights.get(card)??null}))});
    root.lexFitPage = refit;
    render();
    if (options.notice) root.prepend(options.notice);
    if ((options.tabs || []).length > 1) root.prepend(subtabBar({
      tabs: options.tabs, active: options.activeTab,
      label: options.tabsLabel || "Tweak groups", change: options.changeTab}));
    if (typeof ResizeObserver === "function") {
      let frame = 0;
      const observer = new ResizeObserver(() => {
        if (frame) return;
        frame = requestAnimationFrame(() => {frame = 0; refit();});
      });
      observer.observe(scroll);
      document.fonts?.ready.then(() => { if (root.isConnected) refit(); });
      root.lexPageObserver = observer;
    }
    requestAnimationFrame(refit);
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
      status.textContent = copy.pendingLabel || "Please wait…";
      try {
        if (await exit()) backdrop.remove();
        else status.textContent = "The action did not complete. Try again or cancel.";
      } catch (error) {
        status.textContent = `${copy.exitError || "Could not exit"}: ${error.message || error}`;
      } finally {
        setBusy(false);
      }
    };
    save.onclick = async () => {
      setBusy(true);
      status.textContent = "Saving changes…";
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
        status.textContent = copy.pendingLabel || "Please wait…";
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
      status.textContent = "Restoring the saved state…";
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
    if (settings.soundEnabled === false || themeSoundGain(settings.soundVolumePercent) <= 0) stopThemeSounds();
    document.documentElement.dataset.lexHoverableAltClick = settings.hoverableAltClick ? "true" : "false";
    // Lexer liked a boolean drawn as one wide box and asked for it as the
    // default, with the arrow-and-checkbox layout as the alternative.
    document.documentElement.dataset.lexBooleanStyle = settings.booleanBoxStyle === false ? "arrow" : "box";
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
  const soundCoverageTable = rows => element("table", {class:"lex-theme-sound-table"},
    element("thead", {}, element("tr", {},
      element("th", {}, "Action"), element("th", {}, "Plugin sound"), element("th", {}, "Source"))),
    element("tbody", {}, ...(rows || []).map(row => element("tr", {},
      element("td", {}, String(row.slot || "").replace(/(^|-)\w/g, value => value.toLocaleUpperCase())),
      element("td", {class:row.available ? "available" : "missing"}, row.available ? "✓ Available" : "× Missing"),
      element("td", {}, row.message || "")))));
  const hoverable = options => {
    const target = String(options.targetLabel || options.label || "linked record");
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
    }, options.content ?? options.label ?? target);
    // Flex buttons cannot ellipsize anonymous text nodes.
    [...button.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).forEach(node => {
      const label = element("span", {class: "lex-hoverable-label"}, node.textContent);
      node.replaceWith(label);
    });
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
    {id: "restart", keys: ["Ctrl", "Shift", "R"], label: "Restart the plugin", developer: true},
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
  const openShortcutPanel = developerMode => {
    if (shortcutPanel) { closeShortcutPanel(); return; }
    const rows = SHORTCUTS.filter(entry => !entry.developer || developerMode).map(entry =>
      element("div", {class: "lex-shortcut-row", "data-lex-shortcut": entry.id},
        element("span", {class: "lex-shortcut-keys"},
          ...entry.keys.map(key => element("kbd", {}, key))),
        element("span", {class: "lex-shortcut-label"}, entry.label)));
    const dialog = element("section", {
      class: "lex-dialog lex-shortcut-panel", role: "dialog", "aria-modal": "false",
      "aria-label": "Keyboard shortcuts",
    }, element("h2", {}, "Keyboard shortcuts"), ...rows);
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
  const saveChangePreview = (button, changes, count) => {
    let popup, timer;
    const close=()=>{clearTimeout(timer);popup?.remove();popup=null;button.removeAttribute('aria-describedby')};
    const leave=()=>{timer=setTimeout(close,180)};
    const show=()=>{
      clearTimeout(timer);if(popup||button.disabled)return;
      const rows=count?.()?changes?.() || []:[];
      const value=x=>x===undefined?"Not set":x===null?"None":typeof x==='boolean'?(x?'On':'Off'):typeof x==='object'?JSON.stringify(x):String(x);
      popup=element('div',{class:'lex-help-popover lex-save-preview',role:'tooltip',id:`save-preview-${Math.random().toString(36).slice(2)}`},
        rows.length?element('ul',{},...rows.map(row=>element('li',{},element('strong',{},row.label),element('div',{},element('span',{},value(row.before)), ' → ',element('span',{},value(row.after)))))):element('p',{},count?.()?'Change details are unavailable.':'No pending changes.'));
      document.body.append(popup);button.setAttribute('aria-describedby',popup.id);
      const r=button.getBoundingClientRect(),box=popup.getBoundingClientRect();
      popup.style.left=`${Math.max(8,Math.min(r.left+r.width/2-box.width/2,innerWidth-box.width-8))}px`;
      const below=innerHeight-r.bottom-16,above=r.top-16;
      const useBelow=box.height<=below || below>=above;
      popup.style.maxHeight=`${Math.max(0,useBelow?below:above)}px`;
      popup.style.top=`${useBelow?r.bottom+8:Math.max(8,r.top-popup.getBoundingClientRect().height-8)}px`;
      popup.addEventListener('mouseenter',()=>clearTimeout(timer));popup.addEventListener('mouseleave',leave);
    };
    button.addEventListener('mouseenter',show);button.addEventListener('mouseleave',leave);
    button.addEventListener('focus',show);button.addEventListener('blur',leave);button.addEventListener('click',close);
    document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
    new MutationObserver(()=>{if(button.disabled)close()}).observe(button,{attributes:true,attributeFilter:['disabled']});
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
    const cancel = element("button", {class: "lex-dialog-action"}, "Cancel");
    const create = element("button", {class: "lex-dialog-action primary"}, options.rename ? "Rename" : (options.createLabel || "Choose Location…"));
    const close = value => { backdrop.remove(); resolve(value); };
    cancel.onclick = () => close("");
    create.onclick = () => {
      const value = input.value.trim();
      if (!value) { message.textContent = "Enter a mod name."; input.focus(); return; }
      close(value);
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") create.click();
      if (event.key === "Escape") close("");
    });
    backdrop.append(element("section", {class: "lex-dialog lex-project-dialog", role: "dialog", "aria-modal": "true"},
      element("h2", {}, options.rename ? "Rename Mod" : "Create New Mod"),
      element("p", {}, options.rename ? "Change the mod project folder name." : (options.description || "Lexeditor will create a new editable project from this game's working template.")),
      input, message, element("div", {class: "lex-dialog-actions"}, cancel, create)));
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
    const name = await askProjectName(options.pluginName || pluginId, options);
    if (!name) return null;
    return callWindow("create_mod_project", pluginId, name);
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
    const toggleMenu = () => {
      const open = menu.hidden;
      if (open && snapshot) render(snapshot);
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      if (open) measureNameColumn();
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
      const projects = (options.sourcesReplaceProjects ? [] : rows.filter(row => row.valid)).map(row => {
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
        return element("div", {class:`lex-project-menu-item${row.current&&activeSource==="mine"?" active":""}`},
          select,
          element("span", {class: "lex-project-menu-item-actions"}, rename, folder, about),
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
            "aria-label":`Enable ${row.label}`,onchange:event=>run(()=>options.changeProjectSource(row.key,{enabled:event.target.checked}))})
          : null;
        if(row.managed && options.changeProjectSource){
          let controlGesture=false;
          Object.assign(dragAttrs,{draggable:"true",tabindex:0,
            "aria-description":"Drag onto another mod. Alt+Up or Alt+Down moves one place.",
            onpointerdown:event=>{controlGesture=!!event.target.closest('input,.lex-project-menu-item-actions');},
            ondragstart:event=>{if(controlGesture){event.preventDefault();return;}event.dataTransfer.effectAllowed="move";event.dataTransfer.setData("application/x-lex-mod",String(index));},
            onkeydown:event=>{if(event.target===event.currentTarget&&event.altKey&&["ArrowUp","ArrowDown"].includes(event.key)){
              event.preventDefault();const delta=event.key==="ArrowUp"?-1:1;
              if(sources[index+delta]?.managed)run(()=>options.changeProjectSource(row.key,{move:delta}));
            }}});
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
        return element("div",{class:`lex-project-menu-item lex-project-reference${String(row.key)===activeSource?" active":""}`,...dragAttrs,
          ondragover:event=>{if(row.managed&&event.dataTransfer.types.includes("application/x-lex-mod")){event.preventDefault();event.dataTransfer.dropEffect="move";}},
          ondrop:event=>{const from=Number(event.dataTransfer.getData("application/x-lex-mod"));
            if(!row.managed||!sources[from]?.managed)return;event.preventDefault();
            if(from!==index)run(()=>options.changeProjectSource(sources[from].key,{move:index-from}));
          }},select,actions,sourceStatus);
      });
      const create = element("button", {
        class: "lex-project-menu-action", type: "button", role: "menuitem",
        // Adding or finding a project is not mod-library work and never was:
        // a plugin says whether it can create one through canCreate. Gating
        // these on a mod adapter took the action away from every game that
        // does not have one, Blank included.
        hidden: !value.canCreate, onclick: async () => {
          closeMenu();
          const projectName = await askProjectName(options.plugin.name || options.plugin.id, options.projectCreatePrompt || {});
          if (projectName) guarded(async () => {
            const result = options.createProject
              ? await options.createProject(projectName)
              : await callWindow("create_mod_project", options.plugin.id, projectName);
            if (result?.contents && !result.cancelled) modContentsReport(result.contents, `Added ${projectName}`);
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
        // A game without mod management says so where the Mod library button
        // would be. The button opened a dialog that only repeated that it is
        // not supported. Adding and finding a mod stay: they are project work,
        // they work without a mod adapter, and they are how a reader gets out
        // of the unmodded state.
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
            modLibraryNote || (options.sourcesReplaceProjects ? null
              : element("button", {type:"button", class:"lex-project-menu-action", onclick:() => { closeMenu(); openModLibrary(options.plugin.id); }}, "Mod library…"))));
      measureNameColumn();
    };
    trigger.onclick = event => { event.stopPropagation(); toggleMenu(); };
    let copyPromptOpen = false;
    // Clicking a property, or typing into a control, is an edit attempt. A
    // button inside one is not: pins, copy buttons and question marks stay
    // usable while the page is read-only.
    const isEditAttempt = target => {
      if (!target?.closest?.("main") || target.closest?.("button")) return false;
      return Boolean(target.closest?.(".lex-detail-field"))
        || Boolean(target.matches?.("input,select,textarea,[contenteditable='true']"));
    };
    const protectManagedEdit = async event => {
      const current = snapshot?.projects?.find(row => row.current);
      if (event.type === "keydown" && ["Tab","Escape","Shift","Control","Alt"].includes(event.key)) return;
      if (copyPromptOpen || !isEditAttempt(event.target)) return;
      // A game with no mod has nothing to write into, so the attempt to edit
      // the game's own data is the moment to offer the way out of it.
      if (current?.noMod) {
        event.preventDefault(); event.stopImmediatePropagation();
        copyPromptOpen = true;
        try {
          const agreed = await confirmAction({
            title: "Create a mod to edit?",
            message: "This is the game's own data, so Lexeditor shows it read-only: there is "
              + "no mod to save into yet. Create a mod and this page becomes editable.",
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
        const copyName = await askProjectName(options.plugin.name, {value:`${current.name} Copy`,
          createLabel:"Create copy", description:"Choose a name for your independent editable copy. It will be stored in the mod library."});
        if (copyName) await guarded(() => callWindow("copy_library_mod", options.plugin.id, current.path, copyName));
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
        if (value) { render(value); return; }
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

  const openModLibrary = async pluginId => {
    const backdrop = element("div", {class:"lex-dialog-backdrop"});
    const dialog = element("section", {class:"lex-dialog", role:"dialog", "aria-modal":"true", "aria-label":"Mod library"});
    const message = element("p", {role:"status"}, "Loading mod library…");
    const content = element("div", {style:"max-height:65vh;overflow:auto;min-width:0"});
    let uploadToken = null, uploading = false, canManage = false;
    const close = () => {
      backdrop.remove();
      if (uploadToken) callWindow("end_mod_upload", uploadToken).catch(() => {});
    };
    dialog.append(element("h2", {}, "Mod library"), closeButton({onclick:close}), message, content);
    backdrop.append(dialog); document.body.append(backdrop);
    const failure = error => { message.textContent = String(error?.message || error); };
    dialog.addEventListener("dragover", event => { event.preventDefault(); });
    dialog.addEventListener("drop", async event => {
      event.preventDefault();
      if (!canManage || uploading) return;
      uploading = true;
      try {
        if (uploadToken) await callWindow("end_mod_upload", uploadToken);
        const upload = await callWindow("begin_mod_upload", pluginId);
        uploadToken = upload.token;
        const items = [...event.dataTransfer.items];
        const dropped = [];
        const visit = async (entry, parent = "") => {
          if (entry.isFile) {
            const file = await new Promise((resolve,reject) => entry.file(resolve,reject));
            dropped.push({file, path:parent + file.name});
          } else if (entry.isDirectory) {
            const reader = entry.createReader();
            for (;;) {
              const children = await new Promise((resolve,reject) => reader.readEntries(resolve,reject));
              if (!children.length) break;
              for (const child of children) await visit(child, parent + entry.name + "/");
            }
          }
        };
        for (const item of items) {
          const entry = item.webkitGetAsEntry?.();
          if (entry) await visit(entry);
          else { const file = item.getAsFile(); if (file) dropped.push({file,path:file.name}); }
        }
        if (!dropped.length) throw Error("Drop a folder or ZIP archive.");
        for (const {file,path} of dropped) {
          for (let offset = 0; offset < file.size || offset === 0; offset += 3 * 1024 * 1024) {
            message.textContent = `Reading ${path}: ${Math.min(offset,file.size).toLocaleString()} / ${file.size.toLocaleString()} bytes`;
            const data = await new Promise((resolve,reject) => {
              const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]);
              reader.onerror = () => reject(reader.error); reader.readAsDataURL(file.slice(offset,offset + 3 * 1024 * 1024));
            });
            await callWindow("upload_mod_chunk", uploadToken, path, offset, data);
            if (!backdrop.isConnected) return;
          }
        }
        const source = dropped.length === 1 && dropped[0].path.toLowerCase().endsWith(".zip")
          ? `${upload.root}/${dropped[0].path}` : upload.root;
        await inspect(source);
      } catch (error) { failure(error); }
      finally { uploading = false; }
    });
    const inspect = async source => {
      let selected = null, rootValue = "", revision = 0;
      const root = element("select", {"aria-label":"Package data folder"});
      const name = element("input", {type:"text", "aria-label":"Mod name"});
      const files = element("div", {style:"max-height:30vh;overflow:auto"});
      const result = element("p", {role:"status"});
      const add = element("button", {type:"button", disabled:true}, "Import mod");
      const refresh = async (rebuild = false) => {
        const request = ++revision;
        add.disabled = true; result.textContent = "Checking package…";
        try {
          const report = await callWindow("inspect_mod_package", pluginId, source, rootValue, selected);
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
              const box = element("input", {type:"checkbox", checked:true, value:path});
              box.onchange = () => {
                selected = [...files.querySelectorAll("input:checked")].map(node => node.value);
                refresh();
              };
              return element("label", {style:"display:block"}, box, path);
            }));
          }
          result.textContent = report.valid
            ? `${report.packages.length} PAK package(s) checked. Import does not activate the mod.`
            : report.problems.join("\n");
          result.style.whiteSpace = "pre-line";
          add.disabled = !report.valid;
        } catch (error) { if (request === revision) result.textContent = String(error?.message || error); }
      };
      root.onchange = () => { rootValue = root.value; selected = null; refresh(true); };
      add.onclick = async () => {
        add.disabled = true;
        try {
          await callWindow("import_mod_package", pluginId, source, name.value, rootValue, selected);
          await render();
        } catch (error) { failure(error); add.disabled = false; }
      };
      content.replaceChildren(element("p", {}, source), element("label", {}, "Data folder", root),
        element("label", {}, "Name", name), files, result,
        element("div", {class:"lex-dialog-actions"}, element("button", {type:"button", onclick:render}, "Back"), add));
      await refresh(true);
    };
    const render = async () => {
      try {
        const state = await callWindow("mod_library_entries", pluginId);
        canManage = state.canManage;
        message.textContent = state.authorTest ? "Author test build: game loading has not been verified." : state.message;
        if (state.managedUpdate?.message) message.textContent += ` ${state.managedUpdate.message}`;
        if (state.managedUpdate?.error) message.textContent += ` ${state.managedUpdate.error}`;
        const rows = state.entries.map(row => {
          const box = element("input", {type:"checkbox", checked:row.enabled, disabled:!state.canManage || !!row.error, value:row.path});
          const copy = element("button", {type:"button", disabled:!state.canManage || !!row.error, onclick:async event => {
            event.preventDefault();
            const agreed = await confirmAction({title:"Create an editable copy?",
              message:"Managed mods update automatically. Your named copy will be independent, so updates cannot replace your edits. You have my blessing.", confirmLabel:"Make a copy"});
            if (!agreed) return;
            const name = await askProjectName("mod", {value:`${row.name} Copy`,
              createLabel:"Create copy", description:"Choose a name for your independent editable copy. It will be stored in the mod library."});
            if (!name) return;
            copy.disabled = true;
            try {
              const result = await callWindow("copy_library_mod", pluginId, row.path, name);
              if (result?.url) { window.__lexeditorNavigating = true; location.href = result.url; }
            } catch (error) { failure(error); copy.disabled = false; }
          }}, "Make editable copy…");
          return element("div", {style:"display:flex;gap:8px;align-items:center"},
            element("label", {}, box, `${row.readOnly ? "🔒 " : ""}${row.name}${row.version ? ` · ${row.version}` : ""}${row.error ? ` — ${row.error}` : ""}`), copy);
        });
        const choose = kind => async () => {
          try { const value = await callWindow("choose_mod_package", pluginId, kind); if (value && !value.cancelled) await inspect(value.source); }
          catch (error) { failure(error); }
        };
        const apply = element("button", {type:"button", disabled:!state.canManage, onclick:async () => {
          apply.disabled = true;
          try {
            await callWindow("activate_library_mods", pluginId, rows.flatMap(row => [...row.querySelectorAll("input:checked")].map(box => box.value)));
            await render(); message.textContent = "Active mod files updated. Launch the game to test them.";
          } catch (error) { failure(error); apply.disabled = false; }
        }}, "Apply enabled mods");
        content.replaceChildren(element("p", {}, state.root), element("p", {}, "Drop a folder or ZIP here, or use Import below."), ...rows,
          element("div", {class:"lex-dialog-actions"},
            element("button", {type:"button", disabled:!state.canManage, onclick:choose("folder")}, "Import folder…"),
            element("button", {type:"button", disabled:!state.canManage, onclick:choose("zip")}, "Import ZIP…"), apply));
      } catch (error) { failure(error); }
    };
    await render();
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
        {key:"selectionHoldMs", scope:"user", title:"Searcher hold time", description:"How long a record must be held before a Searcher selects it.", type:"number", min:150, max:2000, step:50, unit:"ms"},
        {key:"booleanBoxStyle", scope:"user", title:"Wide boolean boxes", description:"An on/off property is one wide box that fills its row, ticked when on. Off draws a small checkbox at the end of an arrow from the property name.", type:"checkbox"},
        {key:"pageWrapAround", scope:"user", title:"Wrap around at the ends", description:"Paging past the last page returns to the first, and paging back from the first goes to the last.", type:"checkbox"},
        {key:"panelTabTarget", scope:"user", title:"Tab key panel", description:"Tab opens the next panel tab. Shift+Tab opens the previous tab. Choose the panel under the mouse or the panel with keyboard focus.", type:"select", choices:[{value:"hover",label:"Hovered panel"},{value:"focus",label:"Focused panel"}]},
        {key:"tableRowsPerPage", scope:"user", title:"Table rows per page", description:"A full table page stretches this many rows to use the exact available panel height.", type:"number", min:5, max:40, step:1},
        {key:"panelGapPercent", scope:"user", title:"Panel spacing", description:"The same responsive gap surrounds panels and separates adjacent panels.", type:"number", min:.25, max:4, step:.05, unit:"%"},
        {key:"pagerBarHeightPercent", scope:"user", title:"Pagination bar height", description:"How tall the bar along the bottom of a table page is, as a percentage of the screen height. One height on every page, whether or not that page's bar carries a search box.", type:"number", min:3, max:12, step:.5, unit:"%"},
        {key:"mainMenuHeightPercent", scope:"user", title:"Menu bar height", description:"Height of the menu bar in the Home screen and every game plugin, as a percentage of the screen.", type:"number", min:3, max:20, step:.25, unit:"%"},
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
      layoutKey: `github-${options.plugin.id}`,
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
    try { return localStorage.getItem(key) || fallback; } catch (_error) { return fallback; }
  };
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
  const storeLabel = async (key, tabId, value, shipped) => {
    const next = value && value !== shipped ? value : "";
    try {
      if (next) localStorage.setItem(key, next);
      else localStorage.removeItem(key);
    } catch (_error) {}
    try {
      await callWindow("save_default_view", shellPluginId(), tabId, {[key]: next});
    } catch (_error) {}
  };
  const undoLabel = async () => {
    const entry = labelUndo.pop();
    if (!entry) return false;
    if (entry.node?.isConnected) entry.node.textContent = entry.before;
    await storeLabel(entry.key, entry.tabId, entry.before, entry.shipped);
    labelRedo.push(entry);
    labelHistoryChanged();
    return true;
  };
  const redoLabel = async () => {
    const entry = labelRedo.pop();
    if (!entry) return false;
    if (entry.node?.isConnected) entry.node.textContent = entry.after;
    await storeLabel(entry.key, entry.tabId, entry.after, entry.shipped);
    labelUndo.push(entry);
    labelHistoryChanged();
    return true;
  };
  // A property's name as the developer last named it. The shipped name is the
  // key, so an override never orphans itself: the same property, drawn on any
  // screen, reads the same. A label that is a node rather than a name (a chip
  // with an icon in it) is left alone.
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
    node.replaceWith(input);
    input.focus();
    input.select();
    let finished = false;
    const finish = accept => {
      if (finished) return;
      finished = true;
      const typed = input.value.trim();
      input.replaceWith(node);
      if (!accept || !typed || typed === before) return;
      node.textContent = typed;
      options.commit?.(typed);
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); finish(true); }
      else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(false));
    return input;
  };
  const renameInPlace = (key, tabId, fallback, text) => {
    const before = text.textContent;
    const input = element("input", {type: "text", class: "lex-label-rename",
      value: before, "aria-label": `Rename ${fallback}`});
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
          // Remember it, so the shell's undo can take the name back: the
          // plugin's record history has no idea this happened.
          labelUndo.push({key, tabId, before, after: label, shipped: fallback, node: text});
          labelRedo.length = 0;
          await storeLabel(key, tabId, label, fallback);
          labelHistoryChanged();
          try {
            showToast(label === fallback ? `${fallback} is back to its shipped name.`
                                         : `${label} is now the shipped name.`);
          } catch (_error) {}
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); finish(true); }
      else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(false));
  };

  const mountShell = options => {
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
    const toast = message => {
      const node = element("div", {class: "lex-toast", role: "status"}, message);
      document.body.append(node);
      requestAnimationFrame(() => node.classList.add("visible"));
      setTimeout(() => { node.classList.remove("visible"); setTimeout(() => node.remove(), 180); }, 2200);
    };
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
      if (changed) options.navigate(options.activeTab());
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
    const tabName = tab => String(tab.label instanceof Node ? tab.label.textContent : tab.label ?? tab.id);
    const orderedTabs = [...options.tabs].sort((left, right) => {
      const leftSettings = isSpecialTab(left);
      const rightSettings = isSpecialTab(right);
      if (leftSettings !== rightSettings) return leftSettings ? 1 : -1;
      const rank = tab => tab.id === "tweaks" ? 2 : (tab.id === "misc" || /^misc\.?$/i.test(String(tab.label))) ? 1 : 0;
      // A page whose order carries meaning - Blank's component levels run from
      // whole pages down to single controls - says so with `order`.
      const stated = tab => Number.isFinite(tab.order) ? tab.order : null;
      if (stated(left) !== null && stated(right) !== null && stated(left) !== stated(right)) return stated(left) - stated(right);
      return rank(left) - rank(right)
        || tabName(left).localeCompare(tabName(right), undefined, {numeric: true, sensitivity: "base"});
    });
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
        const result = await callWindow("save_default_view", options.plugin.id, tab.id, preferences);
        savedDefault = !!result?.saved;
        if (savedDefault) toast(`${tab.label} is now the shipped default view.`);
      };
      const button = element("button", {
        "data-tab": tab.id,
        class: [tab.id === options.activeTab() ? "active" : "",
        isSpecialTab(tab) ? "lex-settings-tab" : "",
        isSpecialTab(tab) || tab.id === "tweaks" ? "lex-tweaks-tab" : ""].filter(Boolean).join(" "),
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
        oncontextmenu: event => {
          event.preventDefault();
          clearTimeout(defaultHoldTimer);
          if (savedDefault) { savedDefault = false; return; }
          const token = `${options.plugin.id}-${tab.id}`;
          try {
            for (let index = localStorage.length - 1; index >= 0; index -= 1) {
              const key = localStorage.key(index);
              if (key && key.includes(token)) localStorage.removeItem(key);
            }
          } catch (_error) {}
          options.resetView?.(tab.id);
          window.dispatchEvent(new CustomEvent("lexeditor-view-reset", {detail: {plugin: options.plugin.id, tab: tab.id}}));
          options.navigate(tab.id);
        },
      }, element("span", {class: "lex-tab-label"},
          element("span", {class: "lex-tab-label-text"},
            savedLabel(`${options.plugin.id}-${tab.id}.label`, tab.label))),
        (key => key ? element("span", {
          class: "lex-tab-shortcut", "aria-hidden": "true",
        }, key) : "")(shortcutKeyFor(tabIndex + 1)));
      nav.append(button);
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
      title: "Restart this plugin", "aria-label": "Restart this plugin",
      "data-lex-history-control": true,
    }, restartIcon());
    const projectControl = mountProjectControl(options, context);
    // Why nothing can be saved, in the row where saving happens: a session
    // opened on a game with no mod shows the game's own data and locks every
    // edit, and the reader should not have to guess that from a dead button.
    const noModNote = sessionHasNoMod()
      ? badge("NO MOD", {tone: "warning",
          title: `This game has no mod yet, so the editor shows the game's own data. Create a mod from the project menu to change anything.`})
      : null;
    const brandSlot = element("div", {class: "lex-brand-slot"}, brand);
    const leftActions = element("div", {class: "lex-shell-left-actions"}, context);
    const centerActions = element("div", {class: "lex-shell-center-actions"},
      undo, save, game, noModNote, redo);
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
    const restartPlugin = async () => {
      const opened = await callWindow("restart_plugin", options.plugin.id);
      if (!opened?.url) throw new Error("The desktop host did not return a restart address. Close and reopen Lexeditor if this continues.");
      window.__lexeditorNavigating = true;
      // A restart is still a load, so it gets a real loading message rather
      // than dropping through to the fallback text.
      const destination = new URL(opened.url, location.href);
      // The old service has stopped. Navigate immediately; optional quote
      // retrieval must never keep the discard dialog waiting on another bridge call.
      destination.searchParams.set("lexTransition", "load");
      destination.searchParams.set("lexLoadStarted", String(Date.now()));
      location.href = destination.href;
      return true;
    };
    // One restart at a time. A second click while the first was still starting
    // the new service started a third, which shut down the service the page
    // had just been sent to: "Failed to fetch", and a page left pointing at it.
    let restarting = false;
    restart.onclick = async () => {
      if (restarting) return;
      restarting = true;
      restart.disabled = true;
      restart.classList.add("busy");
      try {
        await confirmUnsavedExit(options, restartPlugin, {
          title: "Unsaved changes",
          question: "Save before restarting this plugin?",
          discardLabel: "Restart Without Saving",
          saveLabel: "Save and Restart",
          exitError: "Could not restart the plugin",
          pendingLabel: "Restarting plugin…",
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

    const history = options.history ? new EditHistory({...options.history, changed: refresh}) : null;
    if (history) history.observe(document);
  // A name the developer changed is undone first, then the record history:
  // the two are different kinds of change and the newest one wins.
  undo.onclick = async () => { if (!(await undoLabel())) history?.undo(); };
  redo.onclick = async () => { if (!(await redoLabel())) history?.redo(); };
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
      try { await options.save?.(); playThemeSound("save"); }
      finally { setSaveBusy(false); }
    };
    save.oncontextmenu = event => {
      event.preventDefault();
      if (saveBusy || save.disabled) return;
      confirmDiscardChanges(options);
    };
    let gameRunning = false, gameCanLaunch = true, gameBusy = false;
    const renderGameProcess = (running, canLaunch = gameCanLaunch) => {
      gameRunning = !!running;
      gameCanLaunch = canLaunch !== false;
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
    let lastReportedDirty = null;
  function refresh() {
    // A rename outside a render - the shell's own undo - still has to move the
    // history buttons.
    labelHistoryChanged = refresh;
      refreshReferences();
      projectControl.refresh?.();
      const dirty = options.dirtyCount?.() || 0;
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
      save.title = saveBusy ? "Saving and building" :
        (dirty ? `Save all ${dirty} unsaved change${dirty === 1 ? "" : "s"}` : "No unsaved changes");
      const saveCount = save.querySelector(".lex-save-count");
      if (saveCount) {
        saveCount.textContent = String(dirty);
        saveCount.hidden = !dirty;
      }
      nav.querySelectorAll("button").forEach(button => button.classList.toggle("active",
        !githubWorkspace?.state.open && button.dataset.tab === options.activeTab()));
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
      const action = matchShortcut(event, developerMode);
      if (!action) return;
      // With the panel open the shortcuts are a legend, not live controls.
      if (shortcutPanel) {
        event.preventDefault();
        event.stopPropagation();
        flashShortcut(action);
        return;
      }
      const editing = event.target instanceof HTMLElement &&
        event.target.matches("input:not([type='checkbox']),textarea,select,[contenteditable='true']");
      if (editing && (action === "undo" || action === "redo")) return;
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
        onclick: options.select ? event => options.select(row,event) : null,
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
    const firstReal = columns.findIndex(column => !column.generated && !column.width);
    const automaticGrow = nameIndex >= 0 ? nameIndex : firstReal;
    return columns.map((column, index) => {
      if (column.width) return column.width;
      const grow = Number(column.grow)
        || (!declaredGrow && automaticGrow >= 0 && index === automaticGrow ? 1 : 0);
      if (grow > 0) return `minmax(0, ${grow}fr)`;
      // A max-content track is still squeezed when the wider columns beside it
      // want the space, and a squeezed number is not a shortened number - it is
      // a different one. "5,000" cut to "5,00" reads as five hundred. Text may
      // truncate; a numeric column is floored at its own content and never
      // does.
      return column.numeric === true ? "minmax(min-content, max-content)" : "max-content";
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
        order = order.filter(item => item !== value);
        const index = order.indexOf(before);
        order.splice(index < 0 ? order.length : index, 0, value);
        save();
      },
      reset: () => { order = [...defaults]; save(); },
      pinButton: (value, label = byKey.get(value)?.label || value) => {
        const pinned = order.includes(value);
        const namespace = "http://www.w3.org/2000/svg";
        const icon = document.createElementNS(namespace, "svg");
        icon.setAttribute("viewBox", "0 0 24 24");
        icon.setAttribute("aria-hidden", "true");
        const pin = document.createElementNS(namespace, "path");
        pin.classList.add("lex-column-pin-on");
        pin.setAttribute("d", "M3.71 21.71L9 16.42l2.29 2.29c.2.2.45.29.71.29s.51-.1.71-.29l2-2a.996.996 0 0 0 0-1.41l-.79-.79l3.59-3.59l.79.79c.39.39 1.02.39 1.41 0l2-2a.996.996 0 0 0 0-1.41l-6-6a.996.996 0 0 0-1.41 0l-2 2a.996.996 0 0 0 0 1.41l.79.79l-3.59 3.59l-.79-.79a.996.996 0 0 0-1.41 0l-2 2a.996.996 0 0 0 0 1.41L7.59 15L2.3 20.29l1.41 1.41Z");
        // One pin, two positions: an unpinned pin hovers up and to the right
        // and drops into the page when it is stuck in. No crossed-out variant.
        icon.append(pin);
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
    const escaped = CSS.escape(String(key));
    for (const node of document.querySelectorAll(`[data-column-key="${escaped}"]`)) {
      node.classList.toggle("lex-column-lit", lit);
    }
    for (const node of document.querySelectorAll(`[data-lex-property="${escaped}"]`)) {
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
    event.preventDefault();
    event.stopPropagation();
    let node = panelTabTarget === "focus" ? document.activeElement
      : panelPointer ? document.elementFromPoint(panelPointer.x,panelPointer.y) : null;
    for (; node && node !== document.body; node = node.parentElement) {
      const bar = node.matches?.('.lex-subtab-bar') ? node : node.querySelector?.(':scope > .lex-subtab-bar:not([hidden])');
      if (!bar) continue;
      const tabs = [...bar.querySelectorAll(':scope > [role="tab"]:not([disabled])')];
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
  const beginCellEdit = (cell, column, row, refresh) => {
    if (!column?.edit || cell.classList.contains("lex-cell-editing")) return;
    if (shellIsReadonly()) return;
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
        const input = column.choices ? element("select", {}, ...column.choices.map(value=>element("option",{value},value)))
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
    const tracks = [];
    let depth = 0, start = 0;
    for (let index = 0; index <= base.length; index++) {
      const character = base[index];
      if (character === '(') depth++;
      if (character === ')') depth--;
      if (index === base.length || (!depth && /\s/.test(character))) {
        if (index > start) tracks.push(base.slice(start, index));
        start = index + 1;
      }
    }
    const heads = [...root.querySelectorAll(":scope > .lex-column-list-header > .lex-column-list-head-cell")];
    if (!heads.length || tracks.length !== heads.length) return null;
    // Probing one column at a time cost a full page layout per column, and a
    // panel holding a dozen tables spent over a second doing it.
    const probes = heads.map(head => {
      const probe = head.cloneNode(true);
      probe.removeAttribute("id");
      probe.style.cssText = "position:fixed;visibility:hidden;width:max-content;min-width:max-content;max-width:none;white-space:nowrap;";
      probe.querySelectorAll("*").forEach(node => {
        node.style.whiteSpace = "nowrap";
        node.style.maxWidth = "none";
        node.style.flexShrink = "0";
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
          if (/^(?:min-content|max-content|auto)$/.test(range[1].trim())) return track;
          const candidate = `minmax(max(${width}px, ${range[1]}), ${range[2]})`;
          return CSS.supports('grid-template-columns', candidate) ? candidate : track;
        }
        if (/^[\d.]+(?:px|em|rem|ch|%)$/.test(track)) return `max(${width}px, ${track})`;
        if (/^[\d.]+fr$/.test(track)) return `minmax(${width}px, ${track})`;
        return track;
      }).join(" ");
      if (!CSS.supports('grid-template-columns', fitted)) return () => {};
      columnHeadingWidths.set(root.lexHeadingKey, fitted);
      return () => {
        if (root.style.getPropertyValue("--lex-column-list-template") !== fitted)
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

  const columnList = options => {
    const preferredColumns = options.columnPreferences?.active?.();
    // The generic enabled column is not a user-choosable column, so it is
    // added after saved preferences rather than being subject to them.
    const columns = preferredColumns
      ? withEnabledColumn(preferredColumns, options.rows, options.enabledChange, false)
      : numberedIdColumns(
          withEnabledColumn(options.columns, options.rows, options.enabledChange),
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
    const headerAlignmentClass = column => `lex-column-align-${column.headerAlign || options.headerAlign || "center"}`;
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
        const [integer, fraction = ""] = String(Math.abs(value)).split(".");
        integerDigits = Math.max(integerDigits, integer.length + (value < 0 ? 1 : 0));
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
    const header = element("div", {
      class: ["lex-column-list-header", options.headerClass || ""].filter(Boolean).join(" "),
      role: "row",
    }, ...columns.map(column => {
      const sortable = canSort(column);
      const active = sortable && sortState.key === column.key;
      const label = element("span", {class: "header-label"},
        active ? element("span", {
          class: `lex-sort-indicator ${sortState.dir > 0 ? "ascending" : "descending"}`,
          "aria-hidden": "true",
        }, sortState.dir > 0 ? "▲" : "▼") : "",
        // A label may be a factory. One DOM node cannot be in two places, so a
        // node reused across renders or across barrelled tables lands in the
        // last one and leaves the others blank; a factory builds a fresh one.
        typeof column.label === "function" ? column.label() : column.label);  // ascending points up
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
    if (options.columnPreferences) {
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
          options.columnPreferences.move(drag.key, drag.target?.dataset.columnKey);
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
        const cell = element("div", {
          class: ["lex-column-list-cell",
            column.edit ? "lex-cell-editable" : "",
            column.key === pointerColumn ? "lex-column-pointer-cell" : "",
            isNumbered ? "lex-numbered-id-cell" : "",
            column.numeric === true ? "lex-numeric-cell" : "",
            alignmentClass(column),
            typeof column.cellClass === "function" ? column.cellClass(row) : column.cellClass || ""].filter(Boolean).join(" "),
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
        if (column.edit) {
          cell.addEventListener("dblclick", event => {
            event.preventDefault();
            beginCellEdit(cell, column, row, options.refresh);
          });
        }
        return cell;
      }),
    });
    root.lexHeadingTemplate = template;
    root.lexHeadingKey = JSON.stringify([template, options.class, header.textContent]);
    const cachedHeadingTemplate = columnHeadingWidths.get(root.lexHeadingKey);
    if (cachedHeadingTemplate) root.style.setProperty("--lex-column-list-template", cachedHeadingTemplate);
    fitColumnHeadings(root);
    document.fonts?.ready.then(() => fitColumnHeadings(root));
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
    const storageKey = options.storageKey ||
      (options.layoutKey ? `lexeditor:panel-layout:${options.layoutKey}` : "");
    if (storageKey) {
      try {
        const stored = localStorage.getItem(storageKey);
        const parsed = JSON.parse(stored || "null");
        if (Array.isArray(parsed) && parsed.length === nodes.length) {
          sizes = sizesWithMinimums(parsed);
        } else if (nodes.length === 2 && Number.isFinite(Number.parseFloat(stored))) {
          const first = Number.parseFloat(stored);
          sizes = sizesWithMinimums([first, 100 - first]);
        }
      } catch (_error) {
        // Storage can be unavailable in a locked-down WebView. Resizing still
        // works for the current layout instance.
      }
    }
    const template = (current, dividers = true) => current.flatMap((value, index) =>
      index < current.length - 1 && dividers
        ? [`minmax(0, ${value}fr)`, "var(--lex-panel-gap, 14px)"]
        : [`minmax(0, ${value}fr)`]).join(" ");

    if (nodes.length < 2 || options.resizable === false) {
      root.style.setProperty("--lex-panel-layout-template", template(sizes, false));
      root.style.setProperty("--lex-panel-layout-gap", Number(options.gap) > 0
        ? `${Number(options.gap)}px` : "var(--lex-panel-gap, 14px)");
      root.classList.add("lex-panel-layout-static");
      root.append(...nodes);
      return root;
    }

    root.classList.add("lex-panel-layout-resizable");
    const minSizes = Array.from({length: nodes.length}, (_, index) =>
      Math.max(80, Number(options.minSizes?.[index]) || 240));
    const dividers = Array.from({length: nodes.length - 1}, (_, index) => {
      const divider = element("div", {
        class: "lex-panel-layout-divider",
        role: "separator",
        tabindex: "0",
        "aria-label": options.dividerLabels?.[index] ||
          `Resize panel ${index + 1} and panel ${index + 2}`,
        "aria-orientation": vertical ? "horizontal" : "vertical",
        title: "Drag to resize panels. Right-click to reset.",
      });
      if (options.dividerClass) divider.classList.add(options.dividerClass);
      divider.dataset.dividerIndex = String(index);
      const accessory = options.dividerAccessories?.[index];
      if (accessory) divider.append(accessory);
      return divider;
    });
    const updateDividerState = () => dividers.forEach((divider, index) => {
      const pair = sizes[index] + sizes[index + 1] || 1;
      const value = sizes[index] / pair * 100;
      divider.setAttribute("aria-valuemin", "0");
      divider.setAttribute("aria-valuemax", "100");
      divider.setAttribute("aria-valuenow", String(Math.round(value)));
      divider.setAttribute("aria-valuetext",
        `Panel ${index + 1} ${Math.round(sizes[index])} percent; panel ${index + 2} ${Math.round(sizes[index + 1])} percent`);
    });
    const setSizes = (requested, persist = false) => {
      sizes = sizesWithMinimums(requested);
      root.style.setProperty("--lex-panel-layout-template", template(sizes));
      updateDividerState();
      const detail = {sizes: [...sizes], split: sizes[0]};
      root.dispatchEvent(new CustomEvent("lex-panel-layout-resize", {detail}));
      if (options.eventName) root.dispatchEvent(new CustomEvent(options.eventName, {detail}));
      if (persist && storageKey) {
        try {
          localStorage.setItem(storageKey, nodes.length === 2 ? String(sizes[0]) : JSON.stringify(sizes));
        } catch (_error) {}
      }
    };
    // A pane is never dragged so small that its text starts to clip: a table
    // name cut to nothing, a choice whose words run under its arrow. The fixed
    // floor above knows nothing of what a pane holds, so the drag also stops
    // at the last width where the shrinking pane's text is clipped by no more
    // pixels than before - so a name already cut short is not cut further.
    const CLIP_CANDIDATES = ".lex-column-cell-content,.lex-column-cell-content *,select,.lex-readonly-field,.lex-toggle-label,.lex-detail-panel-title";
    const clippedIn = node => {
      let hidden = 0;
      for (const item of node.querySelectorAll(CLIP_CANDIDATES))
        if (item.clientWidth && item.scrollWidth > item.clientWidth + 1) hidden += item.scrollWidth - item.clientWidth;
      return hidden;
    };
    const resizePair = (index, delta, persist = false, edge = "", initialWidths = null) => {
      const widths = initialWidths ? [...initialWidths]
        : nodes.map(node => vertical ? node.getBoundingClientRect().height : node.getBoundingClientRect().width);
      if (!root.isConnected || widths.some(value => value <= 0)) return false;
      const total = widths.reduce((sum,value)=>sum+value,0);
      const minimumScale = Math.min(1,total/minSizes.reduce((sum,value)=>sum+value,0));
      const minimums = minSizes.map((value,i)=>Math.max(value*minimumScale,total*minimumFractions[i]));
      if(edge==="home")delta=-total;
      if(edge==="end")delta=total;
      // When the adjacent pane reaches its minimum, use spare room in the
      // next pane too. A narrow centre list must not trap the left divider.
      const donors=delta>0
        ? widths.map((_,i)=>i).filter(i=>i>index)
        : widths.map((_,i)=>i).filter(i=>i<=index).reverse();
      let remaining=Math.abs(delta),applied=0;
      for(const donor of donors){
        const taken=Math.min(remaining,Math.max(0,widths[donor]-minimums[donor]));
        widths[donor]-=taken;remaining-=taken;applied+=taken;
        if(remaining<.25)break;
      }
      // A drag is measured from its starting widths. Returning to the start
      // must restore those widths, even though this move transfers nothing.
      if(applied<.25){if(initialWidths)setSizes(widths,persist);return false;}
      widths[delta>0?index:index+1]+=applied;
      const shrunk=donors.filter(donor=>widths[donor]<nodes[donor].getBoundingClientRect()[vertical?"height":"width"]-.25);
      const before=[...sizes],clipped=shrunk.map(donor=>clippedIn(nodes[donor]));
      setSizes(widths, persist);
      const clips=()=>shrunk.some((donor,i)=>clippedIn(nodes[donor])>clipped[i]+1);
      if(!clips())return true;
      // One fast flick can pass the limit in a single frame. Find the
      // smallest step toward it that still clips nothing, rather than
      // snapping the pane back to where the drag started.
      const sum=before.reduce((a,b)=>a+b,0)||1,from=before.map(value=>value/sum*total);
      const mix=t=>from.map((value,i)=>value+(widths[i]-value)*t);
      let good=0,bad=1;
      for(let step=0;step<7;step++){const t=(good+bad)/2;setSizes(mix(t),false);if(clips())bad=t;else good=t;}
      setSizes(mix(good),persist);
      return good>0;
    };
    let dragFrame = 0, pendingDrag = null, dragStart = null;
    const flushDrag = () => {
      dragFrame = 0;
      const pending = pendingDrag; pendingDrag = null;
      if (!pending || !root.isConnected) return;
      if (!dragStart) return;
      resizePair(pending.index, pending.x - dragStart.x, false, "", dragStart.widths);
    };
    const finishDrag = (divider, event) => {
      if (!divider.classList.contains("dragging")) return;
      if (dragFrame) cancelAnimationFrame(dragFrame);
      flushDrag();
      dragStart = null;
      divider.classList.remove("dragging");
      document.body.classList.remove("lex-panel-layout-dragging");
      try {
        if (divider.hasPointerCapture?.(event.pointerId)) divider.releasePointerCapture(event.pointerId);
      } catch (_error) {}
      setSizes(sizes, true);
      document.dispatchEvent(new Event("lex-panel-drag-ended"));
    };
    dividers.forEach((divider, index) => {
      divider.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        // Divider accessories are controls, not resize handles. Capturing their
        // pointer made the shared Barrels buttons appear live but do nothing.
        if (event.target.closest?.("button,input,select,textarea,[role=button]")) return;
        event.preventDefault();
        dragStart = {x: vertical ? event.clientY : event.clientX,
          widths: nodes.map(node => vertical ? node.getBoundingClientRect().height : node.getBoundingClientRect().width)};
        divider.classList.add("dragging");
        document.body.classList.add("lex-panel-layout-dragging");
        try { divider.setPointerCapture?.(event.pointerId); } catch (_error) {}
      });
      divider.addEventListener("pointermove", event => {
        if (!divider.classList.contains("dragging")) return;
        pendingDrag = {divider, index, x: vertical ? event.clientY : event.clientX};
        if (!dragFrame) dragFrame = requestAnimationFrame(flushDrag);
      });
      divider.addEventListener("pointerup", event => finishDrag(divider, event));
      divider.addEventListener("pointercancel", event => finishDrag(divider, event));
      divider.addEventListener("lostpointercapture", event => finishDrag(divider, event));
      divider.addEventListener("keydown", event => {
        const dimension = vertical ? "height" : "width";
        const pairWidth = nodes[index].getBoundingClientRect()[dimension] +
          nodes[index + 1].getBoundingClientRect()[dimension];
        const step = pairWidth * (event.shiftKey ? .05 : .02);
        if (event.key === (vertical ? "ArrowUp" : "ArrowLeft")) resizePair(index, -step, true);
        else if (event.key === (vertical ? "ArrowDown" : "ArrowRight")) resizePair(index, step, true);
        else if (event.key === "Home") resizePair(index, 0, true, "home");
        else if (event.key === "End") resizePair(index, 0, true, "end");
        else return;
        event.preventDefault();
      });
      const reset = event => {
        if (event.target.closest?.("button,input,select,textarea,[role=button]")) return;
        event.preventDefault();
        setSizes(defaults, true);
      };
      // Right-click resets a split; double-click does not. A divider is
      // dragged, and a drag that starts with two quick presses would otherwise
      // throw the layout away instead of moving it. Two separate contracts
      // record this decision.
      divider.addEventListener("contextmenu", reset);
    });

    nodes.forEach((node, index) => {
      root.append(node);
      if (index < dividers.length) root.append(dividers[index]);
    });
    setSizes(sizes);
    if (typeof ResizeObserver !== "undefined") {
      let pending = 0;
      const observer = new ResizeObserver(() => {
        if (pending) cancelAnimationFrame(pending);
        pending = requestAnimationFrame(() => {
          pending = 0;
          if (nodes.length === 2 && !dividers[0]?.classList.contains("dragging")) {
            resizePair(0, 0);
          }
          updateDividerState();
        });
      });
      observer.observe(root);
      root.__lexPanelLayoutObserver = observer;
    }
    requestAnimationFrame(() => {
      if (root.isConnected && nodes.length === 2) resizePair(0, 0);
    });
    return root;
  };

  // Compatibility wrapper for older callers. Resizing belongs to panelLayout.
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
        storageKey: options.splitKey ? `lexeditor:list-detail:${options.splitKey}` : "",
        resizable: options.resizable,
        dividerClass: "lex-list-detail-divider",
        dividerLabels: ["Resize list and detail panels"],
        dividerAccessories: options.dividerAccessories,
        paneClass: options.paneClass,
        eventName: "lex-list-detail-resize",
      });
    if (options.resizable !== false) root.classList.add("lex-list-detail-resizable");
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
      const pageSize = Math.min(fixedRows || Math.max(1, Math.floor((available - 0.5) / naturalRowHeight)), capacity);
      const rowHeight = fixedRows ? available / pageSize : naturalRowHeight;
      if (!(rowHeight > 0)) return;
      if (fixedRows) fittedLists.forEach(node => {
        node.style.setProperty("--lex-fitted-row-height", `${rowHeight}px`);
        node.dataset.lexFixedRows = String(pageSize);
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
  const finishSearcher = (navigateOrigin = true) => {
    if (!activeSearcher) return;
    const searcher = activeSearcher;
    activeSearcher = null;
    searcher.header?.classList.remove("lex-searcher-active");
    searcher.bar?.remove();
    if (navigateOrigin) searcher.origin?.();
    window.dispatchEvent(new CustomEvent("lexeditor-searcher-changed", {detail: {active: false}}));
  };
  const beginSearcher = options => {
    finishSearcher(false);
    const header = document.querySelector(".lex-shell-header");
    const command = header?.querySelector(".lex-shell-command-row");
    if (!header || !command) throw new Error("The shared Searcher needs the Lexeditor shell");
    const context = element("button", {type: "button", class: "lex-searcher-context", title: "Show the source record"}, searchIcon());
    const prompt = element("strong", {class: "lex-searcher-prompt"}, options.prompt || "Select a record");
    const cancel = element("button", {type: "button", class: "lex-searcher-cancel", title: "Cancel selection", "aria-label": "Cancel selection"}, "×");
    const bar = element("div", {class: "lex-searcher-bar", role: "status", "aria-live": "polite"}, context, prompt, cancel);
    const searcher = {
      type: String(options.type || "record"), accept: options.accept, origin: options.origin,
      target: options.target, bar, header, atTarget: true,
      holdMs: Math.max(150, Math.min(2000, Number(options.holdMs || sharedSettingsSnapshot?.selectionHoldMs || 650))),
    };
    activeSearcher = searcher;
    context.onclick = () => {
      if (searcher.atTarget) {
        searcher.atTarget = false;
        context.replaceChildren(element("span", {class: "lex-searcher-return lex-ui-symbol", "aria-hidden": "true"}, "↩"));
        context.title = "Return to selection results";
        searcher.origin?.();
      } else {
        searcher.atTarget = true;
        context.replaceChildren(searchIcon());
        context.title = "Show the source record";
        searcher.target?.();
      }
    };
    cancel.onclick = () => finishSearcher(true);
    header.classList.add("lex-searcher-active");
    command.append(bar);
    searcher.target?.();
    window.dispatchEvent(new CustomEvent("lexeditor-searcher-changed", {detail: {active: true, type: searcher.type}}));
    return searcher;
  };
  const decorateSearchCandidate = (node, options) => {
    const searcher = activeSearcher;
    if (!searcher || searcher.type !== String(options.type || "record")) return node;
    node.classList.add("lex-search-candidate");
    node.style.setProperty("--lex-search-hold", `${searcher.holdMs}ms`);
    let timer = 0;
    const cancel = () => {
      clearTimeout(timer); timer = 0; node.classList.remove("selecting");
    };
    node.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      event.preventDefault();
      node.setPointerCapture?.(event.pointerId);
      node.classList.add("selecting");
      timer = setTimeout(() => {
        timer = 0;
        node.classList.remove("selecting");
        const accept = searcher.accept;
        activeSearcher = null;
        searcher.header?.classList.remove("lex-searcher-active");
        searcher.bar?.remove();
        accept?.(options.value, options.label);
        searcher.origin?.();
        window.dispatchEvent(new CustomEvent("lexeditor-searcher-changed", {detail: {active: false}}));
      }, searcher.holdMs);
    });
    for (const type of ["pointerup", "pointercancel", "pointerleave"]) node.addEventListener(type, cancel);
    node.addEventListener("click", event => { event.preventDefault(); event.stopImmediatePropagation(); }, true);
    return node;
  };

  const bottomSearchChangeTimers = new Map();
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
      };
      const delay = Math.max(0, Number(options.delay) || 0);
      if (delay) bottomSearchChangeTimers.set(key, setTimeout(apply, delay));
      else apply();
    };
    control.addEventListener("input", change);
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
      button("<", page - 1, page <= 0, "Previous page"),
      element("span", {class: "lex-page-position"},
        pageInput, element("span", {"aria-hidden": "true"}, "/"),
        element("span", {class: "lex-page-total", text: pages})),
      button(">", page + 1, page + 1 >= pages, "Next page"),
      button(">>", pages - 1, page + 1 >= pages, "Last page"));
    const filters=options.filters || [];
    const createControls=filters.filter(control=>control?.matches?.('.lex-new-button'));
    const left = element("div", {class: "lex-pager-left"},
      ...createControls,
      options.search ? bottomSearch(options.search) : null);
    let rowControl = null;
    if (options.rowControl) {
      // The most rows that fit this panel at a readable height. Asking for
      // more used to be saved and then silently capped, so Enter looked dead.
      const rowMax = Math.max(5, Math.min(80, Number(options.rowControl.max) || 80));
      const commitRows = input => {
        // A box replaced by the render its own Enter caused still blurs; that
        // second commit re-rendered the table again for nothing.
        if (input.dataset.lexCommitted === input.value) return;
        input.dataset.lexCommitted = input.value;
        const requested = Number.parseInt(input.value, 10);
        if (Number.isFinite(requested) && requested > rowMax) {
          input.value = rowMax;
          showToast(`Only ${rowMax} rows fit this panel at a readable height.`);
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
      element("span", {class: "lex-page-summary", text: `${formatNumber(first)}-${formatNumber(last)}/${formatNumber(total)}`}));
    return element("div", {
      class: `lex-pager${pages === 1 ? " single-page" : ""}${inline ? " lex-pager-inline" : ""}`,
      "aria-label": "Search and pagination",
    }, left, pages === 1 ? null : controls, right);
  };

  // Editing chrome that stays live in a read-only project: none of it changes
  // record data.
  const READONLY_EXEMPT = [".lex-pager", ".lex-searcher", ".lex-search", ".lex-dialog",
    ".lex-dialog-backdrop", ".lex-modal", ".lex-global-settings", ".lex-project-control",
    ".lex-shortcut-panel", ".lex-github-workspace", ".lex-toast-stack", ".lex-data-map",
    "header", "nav"].join(",");
  const readonlyProject = () =>
    document.documentElement.getAttribute("data-lex-project-readonly") === "true";
  const refusesEdit = target => {
    if (!readonlyProject()) return false;
    if (!(target instanceof HTMLElement)) return false;
    const control = target.closest("input,select,textarea,[contenteditable='true']");
    if (!control) return false;
    if (control.matches("[type='search'],[type='button'],[type='submit'],[type='reset']")) return false;
    return !control.closest(READONLY_EXEMPT);
  };
  // A locked project refuses every record edit, not only the ones a plugin
  // remembered to disable. Capture phase, so it survives every re-render.
  for (const kind of ["beforeinput", "paste", "drop", "keydown", "mousedown", "click", "change"]) {
    document.addEventListener(kind, event => {
      if (!refusesEdit(event.target)) return;
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
  const tableCapacityCache = new Map();
  const tableFitCapacityCache = new Map();
  // The table whose row count the reader just typed, so a fit that caps it
  // says why instead of quietly showing fewer rows than asked for.
  let typedRowsKey = null;
  // Which page each table last drew, so a page the reader asked for can be
  // told apart from the page a stale selection would pull it back to.
  const lastRenderedPage = new Map();
  let openBarrelControlKey = "";
  const fitBarrelTableColumns = node => {
    const template = node?.style?.getPropertyValue("--lex-column-list-template");
    if (!template) return node;
    const fitted = template.replace(/minmax\(\s*[\d.]+px\s*,/gi, "minmax(0,");
    if (fitted !== template) node.style.setProperty("--lex-column-list-template", fitted);
    return node;
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
      for (let column = 0; column < cells; column++) {
        // Mirror a real cell's structure, including its content span, so the
        // filler rows line up exactly with the barrel beside them.
        filler.append(element("div", {class: "lex-column-list-cell", role: "cell"},
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
  // list, because the two behave differently in four visible ways: a growable
  // list offers Add, a slot table never does; a slot table shows only real
  // slots, so it is not padded out to fill the page; a slot table can hide its
  // empty slots; and once a slot table is sorted by anything but its ID, a
  // first-to-last range no longer describes what is on screen.
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
    const keptSort = pagedSortStates.get(rowPreferenceKey);
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
    const pageSize = Math.min(requestedPageSize, fitCapacity?.capacity || requestedPageSize);
    const queryActive = Boolean(String(options.search?.value || "").trim());
    if (!queryActive) tableCapacityCache.set(rowPreferenceKey, records.length);
    const stableRecordCount = queryActive
      ? (tableCapacityCache.get(rowPreferenceKey) ?? pageSize)
      : records.length;
    const rowCapacity = Math.max(1, Math.min(pageSize, stableRecordCount || pageSize));
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
    const pagedDeliberately = lastRenderedPage.get(rowPreferenceKey) !== undefined &&
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
    options.sync?.({page, pageSize, selected});
    const selectionKey=options.splitKey || rowPreferenceKey;
    const selection=tableSelections.get(selectionKey)||{keys:new Set([selected]),anchor:selected};
    selection.keys=new Set([...selection.keys].filter(key=>records.some(row=>keyOf(row)===key)));
    if(!selection.keys.size)selection.keys.add(selected);
    tableSelections.set(selectionKey,selection);
    const makeDetail=record=>{
      const node=options.detail(record);
      const chosen=records.filter(row=>selection.keys.has(keyOf(row)));
      if(chosen.length>1){
        const banner=element('div',{class:'lex-multi-edit-notice'},`${chosen.length} records selected. Edits apply to all selected records. Values shown are from ${record.name||keyOf(record)}; other records may differ.`);
        node.prepend(banner);
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
      options.sync?.({page, pageSize, selected, reason:"select"});
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
    const outerSortOwner = pagedSortOwner;
    pagedSortOwner = typeof options.change === "function" ? {
      state: keptSort ? {key: keptSort.key, dir: keptSort.dir} : null,
      sort: (column, direction, compare) => {
        pagedSortStates.set(rowPreferenceKey, {key: column.key, dir: direction, compare});
        change("sort", {});
      },
    } : null;
    try {
      masterNodes = barrelRows.map((rows, index) => {
        const node = typeof options.master === "function"
          ? options.master({rows, selected, select, barrel: index, barrels})
          : list({...options.list, rows, key: keyOf, selected, select});
        node.querySelectorAll('.lex-list-row[data-key]').forEach(row=>{
          const active=[...selection.keys].some(key=>String(key)===row.dataset.key);
          row.classList.toggle('selected',active);row.setAttribute('aria-selected',String(active));
        });
        node.setAttribute('aria-multiselectable','true');
        fitBarrelTableColumns(node);
        // Filler rows exist to square off a growable list. A slot table shows
        // one row per real slot, so a short last page simply ends.
        // Pad to the track count this table actually declares. Padding to the
        // page size instead put forty rows into a ten-track grid whenever a
        // table held less than one page: the ten declared tracks collapsed to
        // zero and every real record painted on top of the others in one band.
        if (!slotBased) padBarrelTable(node, rowCapacity);
        node.classList.add("lex-page-sized-table");
        // The track count is read back from the rows that are really there, so
        // a padding rule and a capacity rule can never disagree again.
        node.style.setProperty("--lex-page-row-count",
          String(Math.max(1, node.querySelectorAll(":scope > .lex-column-list-row").length || rowCapacity)));
        node.style.setProperty("--lex-page-font-row-count", String(rowCapacity));
        node.dataset.lexBarrel = String(index + 1);
        if (index) node.classList.add("lex-fitted-page");
        return node;
      });
    } finally {
      pagedSortOwner = outerSortOwner;
    }
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
    const barrelGrid = element("div", {
      class: "lex-barrel-grid", style: `--lex-barrels:${masterNodes.length}`,
    }, ...masterNodes);
    const masterNode = element("div", {class: "lex-barrelled-master"}, barrelGrid);
    // A fitted master has no vertical scroll range, so its wheel turns pages.
    wheelPages(masterNode, direction => changePage(page + direction));
    const barrelPanelMinimum = Math.max(160, Number(options.minLeft) || 280) * barrels +
      7 * (barrels - 1);
    const root = leadingNode ? panelLayout([leadingNode, masterNode, detailNode],
      `lex-list-detail lex-master-detail lex-list-detail-resizable lex-leading-list-detail ${options.className || ""}`, {
        defaultSizes: options.panelSizes || [options.defaultLeadingWidth || 25, 30, 45],
        minSizes: [Math.max(220, Number(options.minLeading) || 300), barrelPanelMinimum, Math.max(240, Number(options.minRight) || 360)],
        storageKey: options.splitKey ? `lexeditor:leading-list-detail:${options.splitKey}` : "",
        dividerClass: "lex-list-detail-divider",
        dividerAccessories: [null, barrelControl],
        dividerLabels: ["Resize secondary panel and list", "Resize list and detail panels"],
        eventName: "lex-list-detail-resize",
      }) : trailingNode ? panelLayout([masterNode, detailNode, trailingNode],
      `lex-list-detail lex-master-detail ${options.className || ""}`, {
        defaultSizes:options.panelSizes || [30,30,40],
        minSizes:[barrelPanelMinimum, Math.max(240, Number(options.minRight) || 300), Math.max(240, Number(options.minTrailing) || 360)],
        storageKey:options.splitKey ? `lexeditor:trailing-list-detail:${options.splitKey}` : "",
        dividerClass:"lex-list-detail-divider",
        dividerAccessories:[barrelControl,null],
        dividerLabels:["Resize list and detail panels","Resize detail and related records"],
        eventName:"lex-list-detail-resize",
      }) : listDetail(masterNode, detailNode, options.className || "", {
      splitKey: options.splitKey,
      defaultSplit: options.defaultSplit,
      minLeft: barrelPanelMinimum,
      minRight: options.minRight,
      minimumSplit: Math.min(78, 22 * barrels),
      dividerAccessories: [barrelControl],
      paneClass: options.paneClass,
    });
    root.classList.add("lex-paged-list-detail");
    root.addEventListener("lex-column-sorted", event => {
      const index = masterNodes.indexOf(event.detail.previous);
      if (index >= 0) masterNodes[index] = event.target;
    });
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
    // Every table has one add button, round, in its own bottom-right corner
    // and faint until pointed at. Where a record cannot be added it stays
    // there, marked unavailable, and says why when pointed at or pressed:
    // "every game, every list should have it... if disabled, it says why".
    // A plugin that builds its own add button and hands it over with the
    // pager's filters gets that button moved here, not a second one.
    const suppliedAdd = bottomTools.find(control => control?.matches?.(".lex-new-button"));
    if (suppliedAdd) bottomTools.splice(bottomTools.indexOf(suppliedAdd), 1);
    const readonlySource = document.documentElement.dataset.lexProjectReadonly === "true";
    const pluginAdd = suppliedAdd ? !suppliedAdd.disabled
      : !slotBased && typeof options.add === "function" && options.addDisabled !== true;
    const canAdd = pluginAdd && !readonlySource;
    const addWhy = canAdd ? "" : readonlySource
      ? "This is the game's own data, shown read-only. Create a mod to add records to it."
      : options.addDisabledReason || (suppliedAdd || options.addDisabled === true
        ? "Adding is unavailable right now."
        : slotBased
          ? `This table is a fixed set of slots in the game's data, so there is no room to add ${options.noun || "records"}.`
          : `Adding ${options.noun || "records"} to this table is not supported yet.`);
    const tableAdd = suppliedAdd || newButton({title: options.addTitle || `Add ${options.noun || "record"}`,
      onclick: event => { event.stopPropagation(); if (canAdd) options.add(); }});
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
    masterNode.append(tableAdd);
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
        max: fitCapacity?.capacity || null,
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
      const pagerNode = pager({page, pages, total: records.length, pageSize: barrelSize,
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
          document.documentElement.style.setProperty("--lex-pager-height", value);
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

    if (options.fit !== false && masterNodes[0]) {
      const fit = options.fit || {};
      const searchActive = Boolean(String(options.search?.value ?? options.search?.query ?? "").trim());
      fitListPage({
        cacheKey:rowPreferenceKey,
        list: masterNodes[0],
        lists: masterNodes,
        available: root,
        pageSize,
        fixedRows: fitMinimum ? Math.min(requestedPageSize, Math.max(1, records.length)) :
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
          if (typedRowsKey === rowPreferenceKey && nextSize < requestedPageSize)
            showToast(`Only ${nextSize} rows fit this panel at a readable height.`);
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
    }
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
      options.apply?.(options.vanilla, event, sources[0]);
      refresh();
      return true;
    };
    const refresh = () => {
      root.classList.toggle("lex-value-modified", options.vanilla !== undefined && !(options.same || ((a,b)=>JSON.stringify(a)===JSON.stringify(b)))(currentValue(),options.vanilla));
      root.querySelector(":scope > :is(.lex-reference-values,.lex-reference-placeholder)")?.remove();
      const reference = referenceDisplay({
        current: currentValue(), sources, format: options.format, same: options.same,
        apply: (value, event, source) => {
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
     is, and a pad that throws cannot take the editor with it. `tick` and
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
                    select: 8, start: 9, up: 12, down: 13, left: 14, right: 15};
    const DIRECTIONS = ["up", "down", "left", "right"];
    const SIGN = {up: -1, down: 1, left: -1, right: 1};

    let source = () => (typeof navigator !== "undefined" && navigator.getGamepads
      ? navigator.getGamepads() : []);
    let installed = false;
    let running = false;
    let padFocus = null;
    const heldSince = new Map();
    let lastRepeat = 0;
    const discreteDown = new Set();

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

    const clearPadFocus = () => {
      padFocus?.classList.remove("lex-pad-focus");
      padFocus = null;
    };

    // A programmatic focus() does not always light :focus-visible, so the
    // highlight the pad needs is a class of its own. It goes away the moment
    // the reader takes over with a mouse, the keyboard or a scroll.
    const setPadFocus = node => {
      if (!(node instanceof HTMLElement)) return false;
      if (padFocus && padFocus !== node) padFocus.classList.remove("lex-pad-focus");
      padFocus = node;
      node.classList.add("lex-pad-focus");
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

    // Left and right on a bounded control change it instead of leaving it.
    // A number or a slider with no way to move it is the one thing a pad
    // cannot reach, and every value in this editor is bounded.
    const stepControl = (node, direction) => {
      const delta = direction === "left" ? -1 : 1;
      if (node instanceof HTMLSelectElement) {
        if (node.options.length < 2) return false;
        const index = node.selectedIndex + delta;
        if (index < 0 || index >= node.options.length) return false;
        node.selectedIndex = index;
        node.dispatchEvent(new Event("input", {bubbles: true}));
        node.dispatchEvent(new Event("change", {bubbles: true}));
        return true;
      }
      if (!numberish(node)) return false;
      const step = Math.abs(Number(node.step)) || 1;
      const current = Number(node.value);
      if (!Number.isFinite(current)) return false;
      let next = current + delta * step;
      const min = Number(node.min), max = Number(node.max);
      if (node.min !== "" && Number.isFinite(min)) next = Math.max(min, next);
      if (node.max !== "" && Number.isFinite(max)) next = Math.min(max, next);
      if (next === current) return false;
      // The same two events a typed edit sends, so every plugin's own dirty
      // tracking, clamping and reference rail answer the pad identically.
      node.value = String(next);
      node.dispatchEvent(new Event("input", {bubbles: true}));
      node.dispatchEvent(new Event("change", {bubbles: true}));
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
      const from = focused(pool);
      if (!from) return setPadFocus(pool[0]);
      if ((direction === "left" || direction === "right") && stepControl(from, direction)) return true;
      const next = nearest(pool, from, direction);
      return next ? setPadFocus(next) : false;
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
      setPadFocus(next);
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
      switch (action) {
        case "up": case "down": case "left": case "right": return move(action);
        case "a": return activate();
        case "b": return cancel();
        case "previousTab": return switchTab(-1);
        case "nextTab": return switchTab(1);
        case "previousPage": return pagerButton(-1);
        case "nextPage": return pagerButton(1);
        default: return false;
      }
    };

    const held = (pad, index) => {
      const button = pad.buttons?.[index];
      if (!button) return false;
      return button.pressed === true || Number(button.value) > 0.5;
    };

    const directionState = pad => {
      const down = new Set();
      if (held(pad, BUTTON.up)) down.add("up");
      if (held(pad, BUTTON.down)) down.add("down");
      if (held(pad, BUTTON.left)) down.add("left");
      if (held(pad, BUTTON.right)) down.add("right");
      const [x = 0, y = 0] = pad.axes || [];
      if (x <= -DEADZONE) down.add("left");
      if (x >= DEADZONE) down.add("right");
      if (y <= -DEADZONE) down.add("up");
      if (y >= DEADZONE) down.add("down");
      return down;
    };

    const DISCRETE = [
      [BUTTON.a, "a"], [BUTTON.b, "b"],
      [BUTTON.lb, "previousTab"], [BUTTON.rb, "nextTab"],
      [BUTTON.lt, "previousPage"], [BUTTON.rt, "nextPage"],
    ];

    // One frame of pad input. `now` is a parameter so a check can drive the
    // repeat timing instead of waiting for real frames.
    const tick = (now = performance.now()) => {
      let pads = [];
      try { pads = source() || []; } catch (_error) { pads = []; }
      const pad = [...pads].find(entry => entry && entry.connected !== false);
      if (!pad) { heldSince.clear(); discreteDown.clear(); return false; }

      for (const [index, action] of DISCRETE) {
        const down = held(pad, index);
        if (down && !discreteDown.has(index)) { discreteDown.add(index); press(action); }
        else if (!down) discreteDown.delete(index);
      }

      const down = directionState(pad);
      for (const direction of DIRECTIONS) {
        if (!down.has(direction)) { heldSince.delete(direction); continue; }
        const since = heldSince.get(direction);
        if (since === undefined) {
          heldSince.set(direction, now);
          lastRepeat = now;
          press(direction);
        } else if (now - since >= REPEAT_FIRST_MS && now - lastRepeat >= REPEAT_MS) {
          lastRepeat = now;
          press(direction);
        }
      }
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
      if (!attached()) { running = false; clearPadFocus(); return; }
      try { tick(); } catch (_error) { /* a broken pad must not break the page */ }
      frameHandle = requestAnimationFrame(frame);
    };

    const connect = () => {
      if (running || !attached()) return false;
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
      for (const type of CONNECT_EVENTS) document.addEventListener(type, connect, true);
      for (const type of CLEAR_EVENTS) window.addEventListener(type, clearPadFocus, true);
      if (!pollHandle) pollHandle = setInterval(connect, 1000);
      connect();
      return api;
    };

    const api = {
      install, uninstall, tick, press, move, activate, cancel, switchTab, pagerButton,
      setPadFocus,
      state: () => ({installed, running, focus: padFocus}),
      setPadSource: next => { source = typeof next === "function" ? next : source; return api; },
    };
    return api;
  })();

window.LexeditorUI = {panelIcon, shellTextNodes, dismissDialogs, sectionParts, pendingChangeList,uiScaleControl, element, el: element, confirmAction, paginateSettings, settingsColumns, pagerToggle, pagerSelect, instructionList, reshadeSection, callWindow, newButton, modLoaderSection, infoHelp, controlHelp, installControlHelp, creditsPanel, unitField, readonlyField, formatNumber, numberValue, magnitudeValue, recordId, detailPanel, tabbedPanel, detailSection, detailNote, detailField, detailGroup, detailRow, multiNumberRow, subtabBar, toggleRow, autoFitControlText, lazyOptions, notice, actionRow, pagedPane, tileGrid, curveGrid, gameCard, componentSample, toolbar, inlineLabel, choiceField, quantityChoice, iconValue, textArea, controlGroup, stack, bitmapText, modelStage, iconSlot, figureGrid, imageMap, mapMagnifier, statCard, choicePopover, treeGraph, codeField, logView, detailText, badge, showToast, copyText, mathFormula, curveEditor, refreshReferences, closeButton, hoverable, renameValue, settingsIcon, infoIcon, folderIcon, searchIcon, magnifyIcon, selectionIcon, saveIcon, settingsSaveControl, bottomSearch, beginSearcher, finishSearcher, decorateSearchCandidate, openGameFolder, finishPluginLoading, configureThemeSounds, playThemeSound, sharedSettings, soundCoverageTable, clone, applyTheme, EditHistory, NavigationHistory, createModProject, installBrowserHistoryGuard, installExtendedMouseHistory, bindSettingDependencies, showAlert, confirmUnsavedExit, confirmDiscardChanges, createWindowActions, installWindowFrame, openSettings, mountShell, list, columnList, columnPreferences, hasEnabledProperty, panelLayout, listDetail, masterDetail, fitListPage, pagedListDetail, pager, referenceDisplay, provenanceControl, booleanMark, enabledMark, integrationStatus, dataMap, platformConfigView, gamepadNavigation};
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
      icon = ui.element('div',{class:'lex-detail-panel-icon'},ui.iconSlot({message:'No image'}));
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
      if (!frozenSlot || !panel.classList.contains('lex-model-preview-open')) return;
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
  const closeHeaderZoom = () => { headerZoom?.remove(); headerZoom = null; };
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
    const art = icon.querySelector('img,svg,picture');
    return art instanceof Element ? art.cloneNode(true) : null;
  };
  document.addEventListener('pointerover', event => {
    if (headerZoom) return;
    const icon = event.target.closest?.('.lex-detail-panel-icon');
    if (!icon || !icon.isConnected || icon.classList.contains('lex-model-preview-trigger')) return;
    const art = headerZoomArt(icon);
    if (!art) return;
    const box = icon.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) return;
    const zoom = document.createElement('div');
    zoom.className = 'lex-header-thumb-zoom';
    zoom.setAttribute('aria-hidden', 'true');
    zoom.append(art);
    document.body.append(zoom);
    // Seat the enlargement beside the header icon, inside the viewport.
    const pad = 12, cap = 320;
    const width = Math.min(cap, zoom.offsetWidth || cap);
    const height = Math.min(cap, zoom.offsetHeight || cap);
    zoom.style.left = `${Math.round(Math.max(pad, Math.min(box.right + pad, window.innerWidth - width - pad)))}px`;
    zoom.style.top = `${Math.round(Math.max(pad, Math.min(box.bottom + pad, window.innerHeight - height - pad)))}px`;
    headerZoom = zoom;
  });
  document.addEventListener('pointerout', event => {
    if (!headerZoom) return;
    const icon = event.target.closest?.('.lex-detail-panel-icon');
    if (icon && !icon.contains(event.relatedTarget)) closeHeaderZoom();
  });
  document.addEventListener('pointerdown', closeHeaderZoom, true);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeHeaderZoom(); });
  window.addEventListener('scroll', closeHeaderZoom, true);

  const hoverKey = node => node?.dataset?.lexProperty || node?.dataset?.columnKey || '';
  document.addEventListener('pointerover', event => {
    const node = event.target.closest?.('.lex-detail-field,[data-column-key]');
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
    const escaped = CSS.escape(String(key));
    document.querySelectorAll(`[data-column-key="${escaped}"],[data-lex-property="${escaped}"]`)
      .forEach(peer => peer.classList.add('lex-column-lit'));
  });
  document.addEventListener('pointerout', event => {
    const node = event.target.closest?.('.lex-detail-field,[data-column-key]');
    if (!node || node.contains(event.relatedTarget)) return;
    node.classList.remove('lex-self-hover');
    const key = hoverKey(node);
    if (!key) return;
    const escaped = CSS.escape(String(key));
    document.querySelectorAll(`[data-column-key="${escaped}"],[data-lex-property="${escaped}"]`)
      .forEach(peer => peer.classList.remove('lex-column-lit'));
  });

  document.addEventListener('click', event => {
    const field = event.target.closest?.('.lex-boolean-field');
    if (!field || event.target.closest?.('input,button,a,select,textarea,.lex-info-help,.lex-reference-values,.lex-column-pin')) return;
    const input = field.querySelector('.lex-detail-field-control input[type="checkbox"]');
    if (!input || input.disabled) return;
    event.preventDefault();
    input.click();
  });

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
    return Math.max(0,...[...label.children].map(child=>left-child.getBoundingClientRect().left));
  };
  const widenLabelLane = label => {
    const lane = label.closest('.lex-tweak-card-grid,.lex-detail-panel,.lex-detail,.lex-detail-section') || label.parentElement?.parentElement || label.parentElement;
    if (!lane) return;
    const needed = Math.ceil(label.scrollWidth + labelLeftOverflow(label) + 2);
    const current = parseFloat(lane.style.getPropertyValue('--lex-detail-label-min')) || 0;
    if (needed > current) lane.style.setProperty('--lex-detail-label-min', `${needed}px`);
  };
  const fitKey = label => `${label.clientWidth}x${label.clientHeight}|${label.textContent}`;
  const fitLabel = label => {
    if (!(label instanceof HTMLElement)) return;
    // The name lane has a fixed width. Fit the font inside it.
    const key = fitKey(label);
    if (fitted.get(label) === key && label.scrollWidth <= label.clientWidth && label.scrollHeight <= label.clientHeight + 1 && labelLeftOverflow(label)<1) return;
    label.style.fontSize = '';
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
      const range=document.createRange();range.selectNodeContents(label);
      const fits=()=>{const css=getComputedStyle(label);return range.getBoundingClientRect().width <= label.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight)-3;};
      while(size>LABEL_MIN_PX&&!fits()){size-=.5;label.style.fontSize=`${size}px`;}
      fitted.set(label,fitKey(label));
      return;
    }
    // Width gets no slack: a word may no longer wrap mid-way, so a name one
    // pixel too wide pokes past the label edge every other name ends on.
    // A name is never shrunk past what can be read. The floor was one pixel,
    // and a long property name in a narrow lane came out as a smear. A name
    // that still does not fit at the floor widens the lane instead - for its
    // whole panel, so the names in it keep one edge.
    const overflows = () => {
      const box=label.getBoundingClientRect(),css=getComputedStyle(label);
      const top=box.top+parseFloat(css.paddingTop),bottom=box.bottom-parseFloat(css.paddingBottom);
      const outsidePadding=[...label.children].some(child=>{
        const bounds=child.getBoundingClientRect();
        return bounds.height>0&&(bounds.top<top-1||bounds.bottom>bottom+1);
      });
      return outsidePadding || label.scrollHeight > label.clientHeight + 1 || label.scrollWidth > label.clientWidth || labelLeftOverflow(label)>1;
    };
    // A word wider than the lane widens the lane before anything shrinks, so
    // one long name does not come out smaller than the names around it. The
    // lane settles on the next pass, when the observer sees it resize.
    // A name that only fits by wrapping asks for the room too: measured on one
    // line, it widens the lane (the grid caps the lane at half the row) before
    // it is broken over two lines and shrunk. "MDEF (RIGHT)" came out as two
    // clipped 13px lines beside a value box six times wider than it needed.
    if (label.classList.contains('lex-detail-field-label')) {
      const wrap = label.style.whiteSpace;
      label.style.whiteSpace = 'nowrap';
      if (label.scrollWidth > label.clientWidth || labelLeftOverflow(label)>1) widenLabelLane(label);
      label.style.whiteSpace = wrap;
    }
    while (size > LABEL_MIN_PX && overflows()) {
      size -= .5;
      label.style.fontSize = `${size}px`;
    }
    if (label.classList.contains('lex-detail-field-label') && overflows()) {
      // At the readable font floor, give wrapped labels space rather than
      // letting their text consume the gap between adjacent properties.
      const css=getComputedStyle(label);
      const height=Math.max(0,...[...label.children].map(child=>child.getBoundingClientRect().height));
      label.parentElement.style.minHeight=`${Math.ceil(height+parseFloat(css.paddingTop)+parseFloat(css.paddingBottom))}px`;
    }

    // `contain:size` keeps the font size out of the box's own measurements, so
    // the key is the same one computed above and the label settles in one pass.
    fitted.set(label, key);
  };
  const LABEL_SELECTOR = '.lex-detail-field-label,.lex-toggle-label,.lex-flag-label,.lex-tab-label-text';
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
  const fitAllLabels = (root, reset) => {
    const fit = label => { labelSizeObserver.observe(label); fitLabel(label); };
    if (root instanceof Element && root.matches?.(LABEL_SELECTOR)) fit(root);
    root.querySelectorAll?.(LABEL_SELECTOR).forEach(fit);
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
      else for (const root of targets) if (root.isConnected) fitAllLabels(root, resetNow);
    });
  };
  const labelObserver = new MutationObserver(records => {
    const added = [];
    const strips = new Set();
    for (const record of records) {
      for (const node of record.addedNodes) if (node instanceof Element) added.push(node);
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
  labelObserver.observe(document.documentElement, {childList: true, subtree: true});
  window.addEventListener('resize', () => scheduleFit());
  // A panel split drag resizes the lane without adding a node or resizing the
  // window, so watch the region the fields actually live in as well.
  new ResizeObserver(() => scheduleFit()).observe(document.documentElement);
  // A label measured against the fallback font is re-laid-out when the real
  // face arrives, and the few extra pixels that brings are enough to clip a
  // line that had just fitted. Re-fit once the fonts are actually in.
  document.fonts?.ready?.then(() => scheduleFit());
  document.fonts?.addEventListener?.('loadingdone', () => {
    document.querySelectorAll(LABEL_SELECTOR).forEach(label => fitted.delete(label));
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
  new MutationObserver(schedule).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
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
  const groupNumberBoxes = root => {
    const scope = root instanceof Element || root instanceof Document ? root : document;
    const inputs = [...scope.querySelectorAll('input[type="number"]')];
    if (scope instanceof Element && scope.matches?.('input[type="number"]')) inputs.push(scope);
    for (const input of inputs) {
      window.LexeditorUI.autoFitControlText(input,{minimum:8});
      if (groupedBoxes.has(input) || !wantsGrouping(input)) continue;
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
    groupNumberBoxes(root && root !== document ? root : document);
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
