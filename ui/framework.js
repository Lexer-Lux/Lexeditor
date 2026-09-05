"use strict";

(() => {
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

  const element = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (value === true) node.setAttribute(key, "");
      else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value);
    }
    for (const child of children.flat(Infinity)) {
      if (child !== null && child !== undefined && child !== false) node.append(child);
    }
    return node;
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
  const loadingParameters = new URLSearchParams(location.search);
  const loadingStartedAt = (() => {
    const supplied = Number(loadingParameters.get("lexLoadStarted"));
    return Number.isFinite(supplied) && supplied > 0 ? supplied : Date.now();
  })();
  if (!embeddedEditor && loadingParameters.get("lexTransition") === "load") {
    pluginLoadingScreen = element("div", {
      class: ["lex-plugin-loading-screen",
        loadingParameters.get("lexLoadStarted") ? "continued" : ""].filter(Boolean).join(" "),
      role: "status", "aria-live": "polite",
      "aria-label": "Loading game editor",
    }, element("blockquote", {class: "lex-plugin-loading-quote"},
      loadingParameters.get("lexQuote") || "Loading editor…"),
    element("span", {class: "lex-plugin-loading-pulse", "aria-hidden": "true"}));
    document.body.append(pluginLoadingScreen);
    // The root already painted an identical screen; hand over without a blink.
    document.documentElement.classList.add("lex-loading-live");
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
  const showToast = (message, options = {}) => {
    if (!toastStack || !toastStack.isConnected) {
      toastStack = element("div", {class: "lex-toast-stack", role: "status", "aria-live": "polite"});
      document.body.append(toastStack);
    }
    const toast = element("div", {class: "lex-toast"}, message);
    toastStack.append(toast);
    while (toastStack.children.length > 4) toastStack.firstElementChild.remove();
    setTimeout(() => {
      toast.classList.add("leaving");
      setTimeout(() => toast.remove(), 220);
    }, Math.max(900, Number(options.duration) || 2000));
    return toast;
  };

  const copyText = async text => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
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
      return copied;
    }
  };

  const copyIcon = () => {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
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

  const infoHelp = (text, attrs = {}) => {
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
      "aria-label": ariaLabel, "aria-describedby": popupId,
    }, element("span", {"aria-hidden": "true"}, "?"));
    const open = () => {
      closeHelpPopup();
      const popup = element("div", {
        id: popupId, class: "lex-help-popover", role: "tooltip",
      }, text instanceof Node ? text.cloneNode(true) : String(text ?? title ?? ""));
      document.body.append(popup);
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
      window.addEventListener("resize", close, {once: true});
      window.addEventListener("scroll", close, {once: true, capture: true});
      document.addEventListener("keydown", escape);
      popup.cleanup = () => document.removeEventListener("keydown", escape);
      activeHelpPopup = popup;
      position();
    };
    marker.addEventListener("pointerenter", open);
    marker.addEventListener("pointerleave", closeHelpPopup);
    marker.addEventListener("focus", open);
    marker.addEventListener("blur", closeHelpPopup);
    return marker;
  };

  const unitField = (control, unit, attrs = {}) => {
    const boxed = attrs.boxed ?? (control instanceof Element &&
      control.matches("input,select,textarea,output,.lex-readonly-field"));
    const prefix = attrs.position === "prefix";
    const reserve = Math.max(1.8, String(unit || "").length * .45 + .9);
    return element("span", {
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
    let content = value instanceof Node ? value : String(value ?? "").replace(/^#/, "");
    if (!(value instanceof Node) && /^\d+$/.test(content)) content = content.padStart(recordIdWidth, "0");
    return element("span", {
      ...rest,
      class: ["lex-record-id", className].filter(Boolean).join(" "),
    }, element("span", {class: "lex-record-id-prefix", "aria-hidden": "true"}, "#"), content);
  };

  // One shared Detail heading owns the optional icon or live-preview slot,
  // record identity, metadata, and actions. Games supply themed content.
  const detailPanel = (options = {}) => {
    const title = options.title instanceof Node
      ? options.title
      : element("h2", {class: "lex-detail-panel-title"}, String(options.title ?? ""));
    const identity = element("div", {class: "lex-detail-panel-identity"},
      title,
      options.identity ? element("div", {class: "lex-detail-panel-id"}, options.identity) : null,
      options.meta ? element("div", {class: "lex-detail-panel-meta"}, options.meta) : null);
    const heading = options.heading === false ? null : element("div", {
      class: ["lex-detail-panel-heading", options.icon ? "" : "no-icon", options.actions ? "" : "no-actions"].filter(Boolean).join(" "),
    },
      options.icon ? element("div", {class: "lex-detail-panel-icon"}, options.icon) : null,
      identity,
      options.actions ? element("div", {class: "lex-detail-panel-actions"}, options.actions) : null);
    return element("section", {
      ...(options.attrs || {}),
      class: ["lex-detail-panel", "lex-detail", heading ? "" : "no-heading", options.className || ""].filter(Boolean).join(" "),
    }, heading, element("div", {class: "lex-detail-panel-body"}, options.body || []));
  };

  // A panel can own local navigation without turning those choices into
  // application-level tabs. Plugins provide the active key and content; this
  // shared component owns the tab semantics and stable panel geometry.
  const tabbedPanel = (options = {}) => {
    const tabs = options.tabs || [];
    const active = tabs.some(tab => tab.id === options.active)
      ? options.active
      : tabs[0]?.id;
    const selected = tabs.find(tab => tab.id === active);
    const content = typeof options.content === "function"
      ? options.content(active, selected)
      : options.content;
    return element("section", {
      ...(options.attrs || {}),
      class: ["lex-tabbed-panel", options.className || ""].filter(Boolean).join(" "),
    }, subtabBar({
      tabs,
      active,
      label: options.label || "Panel views",
      className: "lex-tabbed-panel-tabs",
      change: options.change,
    }), element("div", {
      class: ["lex-tabbed-panel-content", options.contentClassName || ""].filter(Boolean).join(" "),
      role: "tabpanel",
      "aria-label": selected?.label || "Panel content",
    }, content || []));
  };

  // Keep the visible value legible when a bounded control contains a long
  // enum label. Width changes and value changes use the same measurement path.
  const autoFitControlText = (control, options = {}) => {
    if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement)) return control;
    if (control.__lexAutoFitUpdate) {
      control.__lexAutoFitUpdate();
      return control;
    }
    const minimum = Math.max(8, Number(options.minimum) || 11);
    const update = () => {
      control.style.fontSize = "";
      const style = getComputedStyle(control);
      const maximum = Number.parseFloat(style.fontSize) || 16;
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
      if (!context || !value) return;
      context.font = `${style.fontStyle} ${style.fontWeight} ${maximum}px ${style.fontFamily}`;
      const measured = context.measureText(value).width;
      if (measured > available) control.style.fontSize = `${Math.max(minimum, maximum * available / measured)}px`;
    };
    control.addEventListener("input", update);
    control.addEventListener("change", update);
    control.__lexAutoFitUpdate = update;
    if (typeof ResizeObserver === "function") {
      // Keep a strong reference. A detached observer can be collected after
      // setup, which made later grid and panel resizes retain the old size.
      control.__lexAutoFitResizeObserver = new ResizeObserver(update);
      control.__lexAutoFitResizeObserver.observe(control);
    }
    document.fonts?.ready?.then(update);
    requestAnimationFrame(update);
    return control;
  };

  // Every value box on a panel should end at the same edge, so the reference
  // rail takes the widest requirement in that panel rather than each control
  // keeping its own.
  const alignReferenceRails = (container = document) => {
    const panels = new Set();
    container.querySelectorAll?.(".lex-source-control[data-lex-rail-width]")
      .forEach(control => panels.add(
        control.closest(".lex-detail-panel-body, .lex-detail-panel, .lex-detail") || container));
    for (const panel of panels) {
      const controls = [...panel.querySelectorAll(".lex-source-control[data-lex-rail-width]")]
        .filter(control => !control.classList.contains("lex-source-control-internal"));
      if (!controls.length) continue;
      const widest = Math.max(...controls.map(control => Number(control.dataset.lexRailWidth) || 0));
      for (const control of controls) {
        control.style.setProperty("--lex-reference-rail-width", `${widest}em`);
      }
    }
  };

  // Refresh every mounted reference display from its live control value. This
  // is the single update path for all plugins and all control types.
  const refreshReferences = (container = document) => {
    container.querySelectorAll?.(".lex-source-control").forEach(node => node.refreshReference?.());
    alignReferenceRails(container);
  };

  // Shared Detail internals. A game supplies its theme and field controls;
  // this component owns the repeated section and field structure.
  const detailSection = (options = {}) => element("section", {
    ...(options.attrs || {}),
    class: ["lex-detail-section", options.className || ""].filter(Boolean).join(" "),
    "aria-label": options.ariaLabel || (typeof options.title === "string" ? options.title : null),
  }, options.title ? element("h3", {class: "lex-detail-section-title"},
    options.title, options.help || null) : null,
  element("div", {class: "lex-detail-section-content"}, options.body || []));

  const anchorDetailPin = (pin, control, input, outward = false) => {
    if (!(pin instanceof Element) || !(control instanceof Element) || !(input instanceof Element)) return;
    const position = () => {
      if (!pin.isConnected || !control.isConnected || !input.isConnected) return;
      const owner = control.getBoundingClientRect();
      const target = input.getBoundingClientRect();
      const icon = pin.getBoundingClientRect();
      if (!owner.width || !target.height || !icon.width) return;
      const inset = target.height * .1;
      // The Boxicons pin tip is at 3.71,21.71 in its 24-by-24 view box.
      const tipX = icon.width * 3.71 / 24;
      const tipY = icon.height * 21.71 / 24;
      const targetX = target.right + (outward ? inset : -inset);
      const targetY = target.top + (outward ? -inset : inset);
      pin.style.left = `${targetX - owner.left - tipX}px`;
      pin.style.top = `${targetY - owner.top - tipY}px`;
      pin.style.right = "auto";
    };
    requestAnimationFrame(position);
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(position);
      observer.observe(control);
      observer.observe(input);
    }
  };

  const detailField = (options = {}) => {
    const control = options.control;
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
    const inferredType = inputType === "checkbox" ? (checkboxCount > 1 ? "FLAGS" : "BOOL")
      : numericLike && (step === null || step === "" || (step !== "any" && Number.isInteger(Number(step)))) ? "INT"
      : numericLike ? "FLOAT"
      : input?.tagName === "SELECT" ? "ENUM"
      : input?.tagName === "TEXTAREA" ? "TEXT"
      // No control to read a type from. "VALUE" said nothing except that the
      // guess failed, so the rail carries no type name instead.
      : input ? "STRING" : "";
    const declaredType = String(options.dataType || "").toLocaleUpperCase();
    const dataType = declaredType && declaredType !== "READ ONLY" ? declaredType : inferredType;
    const min = options.min ?? input?.getAttribute?.("min") ?? input?.dataset?.min;
    const max = options.max ?? input?.getAttribute?.("max") ?? input?.dataset?.max;
    const rangeText = options.range || ((min !== null && min !== undefined && min !== "") ||
      (max !== null && max !== undefined && max !== "")
      ? `(${min ?? "…"}-${max ?? "…"})` : "");
    if (input && dataType === "INT") {
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
    const typeRail = element("div", {class: "lex-field-type-rail", "aria-hidden": "true"},
      typeName, typeRange, options.help || null);
    const directCheckboxes = control instanceof Element
      ? (control.matches('input[type="checkbox"]') ? 1 : control.querySelectorAll('input[type="checkbox"]').length)
      : 0;
    const booleanField = dataType === "BOOL" && directCheckboxes === 1;
    const arrow = booleanField ? element("span", {class: "lex-field-boolean-arrow", "aria-hidden": "true"}) : null;
    const node = element("div", {
      ...(options.attrs || {}),
      class: ["lex-detail-field", "lex-pinnable-property", booleanField ? "lex-boolean-field" : "", options.className || ""].filter(Boolean).join(" "),
      "data-lex-type": dataType,
      "data-lex-property": options.property
        || pin?.getAttribute?.("data-lex-pin-column") || null,
      "data-lex-readonly": String(readOnly),
    }, element("div", {class: "lex-detail-field-label"},
      options.label, arrow),
    element("div", {class: "lex-detail-field-control"}, control,
      pin && pin.parentElement !== control ? pin : null), typeRail);
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
    }
    node.lexRejectValue = rejectValue;

    // A bounded number draws its own value as a fill behind the box, and on
    // hover the fill slides out into a slider for rough adjustment.
    const lowBound = min === null || min === undefined || min === "" ? null : Number(min);
    const highBound = max === null || max === undefined || max === "" ? null : Number(max);
    if (input && !readOnly && numericLike &&
        Number.isFinite(lowBound) && Number.isFinite(highBound) && highBound > lowBound) {
      const fill = element("span", {class: "lex-value-fill", "aria-hidden": "true"});
      const handle = element("span", {class: "lex-value-handle", "aria-hidden": "true"});
      fill.append(handle);
      const ratio = () => {
        const value = Number(input.value);
        if (!Number.isFinite(value)) return 0;
        return Math.max(0, Math.min(1, (value - lowBound) / (highBound - lowBound)));
      };
      const paint = () => fill.style.setProperty("--lex-value-ratio", String(ratio()));
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
        const nextValue = String(Math.max(lowBound, Math.min(highBound, snapped)));
        if (input.value === nextValue) return;
        input.value = nextValue;
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
      (control instanceof Element && control.matches(".lex-unit-field") ? control : input.parentElement)
        ?.prepend(fill);
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
          const value = Number(input.value);
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
      showToast("Restored the vanilla value");
    });

    if (input && inputType !== "checkbox") {
      const copy = element("button", {
        type: "button", class: "lex-copy-value", tabindex: "-1",
        title: "Copy this value", "aria-label": "Copy this value",
        onclick: async event => {
          event.preventDefault();
          event.stopPropagation();
          const text = input.tagName === "SELECT"
            ? (input.selectedOptions[0]?.textContent || input.value)
            : input.value;
          const copied = await copyText(String(text));
          showToast(copied ? `Copied: "${text}"` : "Could not reach the clipboard");
        },
      }, copyIcon());
      node.querySelector(".lex-detail-field-control")?.prepend(copy);
    }
    return node;
  };

  // Public names describe the panel archetype, not one historic view. A Detail
  // panel is made from groups of rows. Every row shares the panel's one label
  // division, while games only supply controls and theme overrides.
  // A row of related on/off switches shown as one property. Multi-toggle rows
  // kept being rebuilt per plugin and kept collapsing into unreadable strips,
  // so this is the one implementation: labels stay full size and the row wraps
  // onto as many lines as it needs instead of shrinking to fit one.
  const toggleRow = (options = {}) => {
    const toggles = (options.toggles || []).map(toggle => {
      const input = element("input", {
        type: "checkbox",
        checked: !!toggle.checked,
        disabled: !!toggle.disabled,
        "aria-label": toggle.label,
        onchange: event => toggle.change?.(event.target.checked, event),
      });
      // Each switch carries its own type rail, matching every other property:
      // BOOL until pointed at, then the help marker for that flag.
      const rail = element("span", {class: "lex-toggle-rail", "aria-hidden": "true"},
        element("span", {class: "lex-toggle-type"}, "BOOL"));
      const label = element("label", {
        class: ["lex-toggle", toggle.className || ""].filter(Boolean).join(" "),
        "data-lex-toggle": toggle.key || toggle.label || "",
      }, rail, input, element("span", {class: "lex-toggle-name"}, toggle.label));
      if (toggle.help) rail.append(infoHelp(toggle.help));
      return label;
    });
    const root = element("div", {
      class: ["lex-toggle-row", options.className || ""].filter(Boolean).join(" "),
      role: "group",
      "aria-label": options.label || "Toggles",
    }, ...toggles);
    if (options.minimum) root.style.setProperty("--lex-toggle-minimum", `${options.minimum}px`);
    if (options.columns) root.style.setProperty("--lex-toggle-columns", String(options.columns));
    return root;
  };

  const detailGroup = detailSection;
  const detailRow = detailField;

  // One property that holds several numbers - a stat block, a set of junction
  // values - laid out as ordinary label-then-box pairs rather than captions
  // stacked over boxes, which is what every other property in the editor does.
  const multiNumberRow = (entries = [], options = {}) => {
    const items = entries.filter(Boolean);
    const columns = Math.max(1, Number(options.columns) || Math.min(3, items.length) || 1);
    return element("div", {
      class: ["lex-multi-number", options.className || ""].filter(Boolean).join(" "),
      style: `--lex-multi-number-columns:${columns}`,
    }, ...items.map(entry => element("label", {
      class: "lex-multi-number-item", title: entry.title || undefined,
    }, element("span", {class: "lex-multi-number-label"}, entry.label),
      element("span", {class: "lex-multi-number-control"}, entry.control))));
  };

  // Nested navigation is a shared control. Plugins provide only labels,
  // active state, and the page-owned change callback.
  const subtabBar = (options = {}) => element("div", {
    class: ["lex-subtab-bar", options.className || ""].filter(Boolean).join(" "),
    role: "tablist",
    "aria-label": options.label || "Subsections",
  }, ...(options.tabs || []).map((tab, index) => element("button", {
    type: "button",
    class: ["lex-subtab-button", tab.id === options.active ? "active" : ""].filter(Boolean).join(" "),
    role: "tab",
    "aria-selected": String(tab.id === options.active),
    tabindex: tab.id === options.active ? "0" : "-1",
    onclick: () => options.change?.(tab.id),
  }, element("span", {class: "lex-tab-label"},
    element("span", {class: "lex-tab-label-text"}, tab.label)),
  (key => key ? element("span", {
    class: "lex-tab-shortcut", "aria-hidden": "true",
  }, key) : "")(shortcutKeyFor(index + 1)))));

  // The key that selects the Nth tab, matching the shortcut sequence:
  // 1-9, then 0 for the tenth, then - and = for the eleventh and twelfth.
  // Positions past that have no key, so they get no badge.
  const shortcutKeyFor = position => (
    position <= 9 ? String(position)
    : position === 10 ? "0"
    : position === 11 ? "-"
    : position === 12 ? "=" : "");

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
    // "meet" letterboxed the 2:1 drawing space inside a taller box, which
    // left a third of every graph empty. The space stretches to fill instead,
    // and stroked paths keep their weight through vector-effect below.
    svg.setAttribute("preserveAspectRatio", "none");
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
    appendFormulaTokens(formulaPath, options.formula?.cloneNode?.(true) || options.formula || "");
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
    const variables = element("div", {class: "lex-curve-variables lex-curve-variable-overlay"},
      ...(options.variables || []).map(variable => {
        const key = String(variable.label || "").trim().toLocaleLowerCase();
        return element("label", {class: "lex-curve-variable", "data-curve-variable": key},
          element("span", {class: `lex-curve-variable-name lex-curve-variable-${key}`}, variable.label), variable.control);
      }));
    const tooltip = element("output", {class:"lex-curve-tooltip", "aria-live":"polite"});
    const hoverExtrema = element("div", {class:"lex-curve-hover-extrema", "aria-hidden":"true"},
      element("output", {class:"lex-curve-hover-minimum", title:"Curve minimum"}, "—"),
      element("output", {class:"lex-curve-hover-maximum", title:"Curve maximum"}, "—"));
    // The stat name sits behind the plot like a watermark: large, centred on
    // both axes, heavy, and faint enough to read the curve through.
    const watermark = element("div", {class: "lex-curve-watermark", "aria-hidden": "true"},
      options.title || "CURVE");
    // Bottom-right switch between the smooth line and a bar reading of the
    // same samples. The mode is a class on the plot, so nothing is redrawn.
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
    const plot = element("div", {class: "lex-curve-plot"},
      watermark,
      svg,
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
      modeToggle,
      variables,
      tooltip);
    const title = element("h4", {},
      element("span", {class: "lex-curve-heading-title"}, options.title || "CURVE"));
    if (options.extremaInTitle) title.append(
      " ", element("span", {class: "lex-curve-heading-extrema"}, "[", minimum, " TO ", maximum, "]"));
    if (options.formulaInTitle && options.formula) title.append(
      " ", element("span", {class: "lex-curve-heading-formula"}, options.formula));
    const root = element("article", {
      class: ["lex-curve-editor", options.className || ""].filter(Boolean).join(" "),
      "data-curve-title": options.title || "CURVE",
      ...(options.attrs || {}),
    },
      element("header", {class: "lex-curve-heading"},
        title,
        options.extremaInTitle || options.overlayExtrema ? null : element("div", {class: "lex-curve-extrema"},
          element("span", {}, "MIN ", minimum),
          element("span", {}, "MAX ", maximum))),
      plot,
      element("div", {class: "lex-curve-formula"}, options.formula || ""),
      status);

    const variableKeys = new Set((options.variables || []).map(variable =>
      String(variable.label || "").trim().toLocaleLowerCase()).filter(Boolean));
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
      const y = Number(options.evaluate?.(x));
      if (!Number.isFinite(y)) { clearProbe(); return; }
      const range = getRange();
      const spanX = Math.max(1, domain.max - domain.min);
      const spanY = Math.max(1, range.max - range.min);
      const graphX = (x - domain.min) / spanX * 320;
      const bounded = Math.max(range.min, Math.min(range.max, y));
      const graphY = 160 - (bounded - range.min) / spanY * 160;
      const cursorY = Math.max(0, Math.min(160, (event.clientY - bounds.top) / bounds.height * 160));
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
      tooltip.style.top = `${Math.max(8, bounds.top - plotBounds.top + graphY / 160 * bounds.height)}px`;
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
    // The plot is 320x160 of user space stretched into whatever box the card
    // gives it, with preserveAspectRatio="none". Angles and overlaps therefore
    // mean nothing in user space - a 20 degree user-space slope can display at
    // 40 - so every angle below is a SCREEN angle and every box is measured
    // after the same stretch the eye sees.
    const plotScale = () => {
      const box = svg.getBoundingClientRect();
      return {x: (box.width || 320) / 320, y: (box.height || 160) / 160};
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

    const draw = () => {
      const range = getRange();
      axisTop.textContent = formatNumber(range.max);
      axisBottom.textContent = formatNumber(range.min);
      const samples = [];
      const first = Math.ceil(domain.min), last = Math.floor(domain.max);
      for (let x = first; x <= last; x += 1) {
        const value = Number(options.evaluate?.(x));
        if (!Number.isFinite(value)) continue;
        samples.push({x, value});
      }
      if (!samples.length) {
        line.removeAttribute("d");
        fill.removeAttribute("d");
        minimum.textContent = maximum.textContent = "—";
        status.textContent = options.invalidText || "INVALID CURVE";
        root.classList.add("invalid");
        return;
      }
      root.classList.remove("invalid");
      status.textContent = "";
      const values = samples.map(sample => sample.value);
      minimum.textContent = formatNumber(Math.min(...values), options.valueFormat || {});
      maximum.textContent = formatNumber(Math.max(...values), options.valueFormat || {});
      hoverExtrema.firstElementChild.textContent = minimum.textContent;
      hoverExtrema.lastElementChild.textContent = maximum.textContent;
      const width = 320, height = 160, spanX = Math.max(1, domain.max - domain.min), spanY = Math.max(1, range.max - range.min);
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
        // Kept clear of the plot edges: at 4 units the first digit sat on the
        // frame and ran into the axis caption beside it.
        const lowX = Math.max(12, first[0] + 4), lowY = Math.max(9, first[1] - 5);
        const highX = Math.min(308, last[0] - 4), highY = Math.max(9, last[1] - 5);
        rangeLow.setAttribute("x", String(lowX));
        rangeLow.setAttribute("y", String(lowY));
        rangeHigh.setAttribute("x", String(highX));
        rangeHigh.setAttribute("y", String(highY));
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
          return Math.max(-38, Math.min(38, degrees));
        };
        const reach = Math.max(1, Math.min(4, points.length - 1));
        const lowAngle = slopeAngle(points[0], points[reach]);
        const highAngle = slopeAngle(points[points.length - 1 - reach], points[points.length - 1]);
        rangeLow.setAttribute("transform", `rotate(${lowAngle.toFixed(2)} ${lowX} ${lowY})`);
        rangeHigh.setAttribute("transform", `rotate(${highAngle.toFixed(2)} ${highX} ${highY})`);
      }
      // ONE BAR PER X VALUE. This used to average the samples into 32 fixed
      // buckets, which drew bars of an arbitrary width that lined up with
      // nothing: a bar spanned three levels and its height was the mean of
      // them, so reading a level off the bar view was impossible. Each sample
      // is one level, so each level gets its own bar at its own height.
      const slotWidth = width / points.length;
      bars.replaceChildren(...points.map(([, y], index) => {
        const rect = document.createElementNS(svgNamespace, "rect");
        // A hairline gap only while the bars are wide enough to show one;
        // at 100 levels the bars are thin and a gap would eat them.
        const gap = slotWidth > 2.5 ? slotWidth * .18 : 0;
        rect.setAttribute("x", (index * slotWidth + gap / 2).toFixed(2));
        rect.setAttribute("width", Math.max(.4, slotWidth - gap).toFixed(2));
        rect.setAttribute("y", y.toFixed(2));
        rect.setAttribute("height", Math.max(0, height - y).toFixed(2));
        return rect;
      }));
      const path = points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
      line.setAttribute("d", path);
      fill.setAttribute("d", `${path} L${points.at(-1)[0].toFixed(2)} ${height} L${points[0][0].toFixed(2)} ${height} Z`);
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
      layoutFormula(buildGuide);
      requestAnimationFrame(() => layoutFormula(buildGuide));
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
      const before = clone(this.capture());
      this.pending = {label, source, before, beforeSignature: signature(before)};
      setTimeout(() => this.finish(), 0);
    }

    finish() {
      const pending = this.pending;
      this.pending = null;
      if (!pending || this.applying) return;
      const after = clone(this.capture());
      const afterSignature = signature(after);
      if (afterSignature === pending.beforeSignature) return;
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
        if (event.target.closest?.("[data-lex-history-control]")) return;
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
      const relationKey = relation.key || [
        relation.dependency.id || relation.dependency.getAttribute("aria-label") || "dependency",
        relation.dependent.id || relation.dependent.getAttribute("aria-label") || "dependent",
      ].join("->");
      const enabled = relation.dependency.type === "checkbox"
        ? relation.dependency.checked : !relation.dependency.disabled;
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
    close.focus();
    return backdrop;
  };

  const confirmUnsavedExit = (options, exit, copy = {}) => {
    const dirty = options.dirtyCount?.() || 0;
    if (!dirty) return exit();
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
    const setBusy = busy => buttons.forEach(button => { button.disabled = busy; });
    const dismiss = () => backdrop.remove();
    cancel.onclick = dismiss;
    discard.onclick = async () => {
      setBusy(true);
      try {
        if (await exit()) dismiss();
      } catch (error) {
        status.textContent = `${copy.exitError || "Could not exit"}: ${error.message || error}`;
        setBusy(false);
      }
    };
    save.onclick = async () => {
      setBusy(true);
      status.textContent = "Saving changes…";
      try {
        await options.save?.();
        const remaining = options.dirtyCount?.() || 0;
        if (remaining) {
          status.textContent = `${remaining} change${remaining === 1 ? "" : "s"} could not be saved. Lexeditor stayed open.`;
          setBusy(false);
          return;
        }
        if (await exit()) dismiss();
      } catch (error) {
        status.textContent = `Save failed: ${error.message || error}`;
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
    document.documentElement.style.setProperty("--lex-panel-gap", `${Number(settings.panelGapPercent || 1)}vw`);
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
    const activate = event => {
      const keyboard = event.detail === 0;
      if (hoverableAltClickEnabled() && !event.altKey && !keyboard) return;
      event.preventDefault();
      event.stopPropagation();
      options.activate?.();
    };
    return element("button", {
      type: "button",
      class: ["lex-hoverable", options.class || ""].filter(Boolean).join(" "),
      "data-hover-target-type": options.targetType,
      "data-hover-target-id": options.targetId,
      "aria-label": options["aria-label"] || `Open ${target}`,
      title: `Open ${target}`,
      onclick: activate,
    }, options.content ?? options.label ?? target);
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
  const settingsSaveControl = (options = {}) => {
    const count = element("span", {class: "lex-save-count", hidden: true, "aria-hidden": "true"});
    const button = element("button", {
      type: "button", class: "save lex-save-icon lex-settings-save-control",
      title: "No unsaved settings changes", "aria-label": "Save settings", disabled: true,
    }, saveIcon(), count);
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
      try { await options.save?.(); playThemeSound("save"); }
      finally { setBusy(false); }
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
    const create = element("button", {class: "lex-dialog-action primary"}, options.rename ? "Rename" : "Choose Location…");
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
      element("p", {}, options.rename ? "Change the mod project folder name." : "Lexeditor will create a new editable project from this game's working template."),
      input, message, element("div", {class: "lex-dialog-actions"}, cancel, create)));
    document.body.append(backdrop); input.focus(); input.select();
    });
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
    const closeMenu = () => { menu.hidden = true; trigger.setAttribute("aria-expanded", "false"); };
    const toggleMenu = () => {
      const open = menu.hidden;
      if (open && snapshot) render(snapshot);
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
    };
    const openResult = result => {
      if (!result || result.cancelled) { render(snapshot); return false; }
      if (result.url) {
        window.__lexeditorNavigating = true;
        location.href = result.url;
        return true;
      }
      snapshot = result; render(snapshot); return false;
    };
    const guarded = operation => confirmUnsavedExit(options, async () => {
      try { return openResult(await operation()); }
      catch (error) { window.alert(String(error?.message || error)); return false; }
    }, {question: "Save before switching mod projects?", exitError: "Could not switch mod projects"});
    const render = value => {
      snapshot = value;
      const rows = value?.projects || [];
      const current = rows.find(row => row.current);
      const sources = options.projectSources?.() || [];
      const activeSource = String(options.projectActiveSource?.() || "mine");
      const selectedSource = sources.find(row => String(row.key) === activeSource);
      const canChoose = Boolean(value);
      box.hidden = !current && !selectedSource && !canChoose;
      if (!current && !selectedSource && !canChoose) return;
      mode.hidden = !selectedSource;
      mode.textContent = selectedSource?.readOnly === false ? "📝" : "🔒";
      mode.setAttribute("aria-label", selectedSource?.readOnly === false ? "Editable" : "Read only");
      name.textContent = selectedSource?.label || current?.name || "Select a mod";
      status.hidden = !selectedSource;
      status.textContent = selectedSource?.enabled === false ? "×" : "✓";
      status.className = `lex-project-source-status ${selectedSource?.enabled === false ? "disabled" : "enabled"}`;
      status.setAttribute("aria-label", selectedSource?.enabled === false ? "Disabled" : "Enabled");
      path.textContent = selectedSource?.path || (selectedSource
        ? "Read-only reference"
        : current?.path || "New Mod or Find a Mod");
      box.title = path.textContent;
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
      }, element("span", {class: "lex-project-menu-name"}, row.name),
      element("span", {class: "lex-project-menu-path"}, row.path));
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
        return element("div", {class:`lex-project-menu-item${row.current&&activeSource==="mine"?" active":""}`}, select, rename, folder);
      });
      const sourceRows = sources.map(row => element("button", {
        class: `lex-project-menu-item-select lex-project-menu-item lex-project-reference${String(row.key) === activeSource ? " active" : ""}`,
        type: "button", role: "menuitem", title: row.path || "Read-only reference",
        onclick: () => {
          closeMenu();
          if (String(row.key) !== activeSource) guarded(async () => {
            await options.selectProjectSource?.(row.key);
            render(snapshot);
          });
        },
      }, element("span", {class: "lex-project-source-mode", "aria-label":row.readOnly === false ? "Editable" : "Read only"}, row.readOnly === false ? "📝" : "🔒"),
      element("span", {class: "lex-project-menu-name"}, row.label),
      element("span", {class: "lex-project-menu-path"}, row.path || "Read-only reference"),
      element("span", {class:`lex-project-source-status ${row.enabled === false ? "disabled" : "enabled"}`, "aria-label":row.enabled === false ? "Disabled" : "Enabled"}, row.enabled === false ? "×" : "✓")));
      const create = element("button", {
        class: "lex-project-menu-action", type: "button", role: "menuitem",
        hidden: !value.canCreate, onclick: async () => {
          closeMenu();
          const projectName = await askProjectName(options.plugin.name || options.plugin.id);
          if (projectName) guarded(() => callWindow("create_mod_project", options.plugin.id, projectName));
        },
      }, "New Mod");
      const browse = element("button", {
        class: "lex-project-menu-action", type: "button", role: "menuitem",
        onclick: () => { closeMenu(); guarded(() => callWindow("browse_mod_project", options.plugin.id)); },
      }, "Find a Mod");
      const manage = element("button", {
        class: "lex-project-menu-action", type: "button", role: "menuitem",
        hidden: !options.manageProjectSources,
        onclick: () => { closeMenu(); options.manageProjectSources?.(); },
      }, "Load Order…");
      menu.replaceChildren(...sourceRows, ...projects,
        element("div", {class: "lex-project-menu-actions", role: "group", "aria-label": "Mod project actions"}, create, browse, manage));
    };
    trigger.onclick = event => { event.stopPropagation(); toggleMenu(); };
    menu.onclick = event => event.stopPropagation();
    document.addEventListener("click", closeMenu);
    document.addEventListener("keydown", event => { if (event.key === "Escape") closeMenu(); });
    let loadAttempts = 0;
    const load = async () => {
      try {
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
      } catch (_error) { box.hidden = true; }
    };
    if (options.projectSnapshot) load();
    else if (window.pywebview?.api) load();
    else window.addEventListener("pywebviewready", load, {once: true});
    box.refresh = () => { if (snapshot) render(snapshot); };
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
    let restoreSettings = () => {};
    const fitDialog = () => {
      dialog.classList.remove("lex-settings-must-scroll");
      dialog.classList.toggle("lex-settings-must-scroll",
        dialog.scrollHeight > Math.max(320, window.innerHeight - 24));
    };
    const close = () => {
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
        {key:"tableRowsPerPage", scope:"user", title:"Table rows per page", description:"A full table page stretches this many rows to use the exact available panel height.", type:"number", min:5, max:40, step:1},
        {key:"panelGapPercent", scope:"user", title:"Panel spacing", description:"The same responsive gap surrounds panels and separates adjacent panels.", type:"number", min:.25, max:4, step:.05, unit:"%"},
        {key:"mainMenuHeightPercent", scope:"user", title:"Menu bar height", description:"Height of the menu bar in the Home screen and every game plugin, as a percentage of the screen.", type:"number", min:3, max:20, step:.25, unit:"%"},
        {key:"soundEnabled", scope:"user", title:"Sound", description:"Play game-themed interface sounds when the active plugin supplies them.", type:"checkbox"},
        {key:"soundVolumePercent", scope:"lexer", title:"Volume level", description:"Attenuates all menu sound effects for every user.", type:"number", min:0, max:100, step:1, unit:"%"},
        {key:"developerMode", scope:"developer", title:"Developer Mode", description:"Shows development tools such as the GitHub workspace and plugin Restart control.", type:"checkbox"},
        {key:"residentHandleWidthPercent", scope:"lexer", title:"Home editor handle width", description:"Width of the Back to Editor handle as a percentage of the main-menu window.", type:"number", min:2.5, max:12, step:.25, unit:"%"},
        {key:"absentGameDesaturationPercent", scope:"lexer", title:"Absent game desaturation", description:"Amount of color removed from Absent game cover art on the Home screen.", type:"number", min:0, max:100, step:5, unit:"%"},
        {key:"globalMessageRarity", scope:"lexer", title:"Global message rarity", description:"Makes each global loading message this many times less likely than each game-specific message.", type:"number", min:1, max:100, step:1, unit:"× rarer"},
        {key:"loadingTransitionMinimumSeconds", scope:"lexer", title:"Loading screen minimum", description:"Keeps the loading screen visible for at least this long. Actual loading can take longer.", type:"number", min:0, max:10, step:.25, unit:"s", fallback:1.5},
      ];
      const ordinaryDefinitions = definitions.filter(definition => definition.scope !== "lexer");
      const supportsCurrent = definition => Object.prototype.hasOwnProperty.call(settings, definition.key);
      const supportsDefault = definition => Object.prototype.hasOwnProperty.call(settings.defaultValues || {}, definition.key);
      const supportedOrdinaryDefinitions = ordinaryDefinitions.filter(supportsCurrent);
      const supportedDefaultDefinitions = definitions.filter(supportsDefault);
      const unsupportedDefinitions = definitions.filter(definition =>
        (definition.scope !== "lexer" && !supportsCurrent(definition)) || !supportsDefault(definition));
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
      const developerLane = lane("developer", `${plugin || "PLUGIN"} EDITOR SETTINGS`.toLocaleUpperCase());
      const lexerLane = lane("lexer", "LEXER");
      const lexerMode = element("input", {
        id:"lex-lexer-mode", type:"checkbox", checked:!!settings.lexerMode,
        disabled:!settings.lexerAuthorized,
      });
      const lexerModeCard = element("section", {class:"lex-global-setting lex-lexer-setting lex-lexer-mode-setting"},
        element("label", {for:"lex-lexer-mode"}, "I am Lexer"),
        element("p", {}, settings.lexerAuthorized
          ? `Verified GitHub account: ${settings.lexerLogin}. Enables distributable defaults.`
          : "Unavailable. Sign in to GitHub as Lexer to enable distributable defaults."), lexerMode);
      lexerLane.append(lexerModeCard);
      const setDefaultVisibility = () => {
        const active = lexerMode.checked && !lexerMode.disabled;
        defaultCards.forEach(control => {
          control.hidden = !active;
          const supported = control.dataset.lexSettingSupported !== "false";
          control.setAttribute("aria-disabled", String(!supported));
          control.querySelectorAll?.("input,select").forEach(input => { input.disabled = !active || !supported; });
        });
        lexerLane.classList.toggle("active", active);
      };
      const copyToDefault = (definition, defaultControl) => {
        if (!lexerMode.checked || lexerMode.disabled) {
          message.textContent = "Enable I am Lexer to change the default for everyone."; return;
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
        if (definition.scope === "lexer") {
          const supported = supportsDefault(definition);
          const wrapped = makeControl(definition, initialValue(definition, true),
            `lex-default-${definition.key}`);
          defaultControls.set(definition.key, wrapped);
          const card = element("section", {
            class:"lex-global-setting lex-lexer-setting lex-lexer-only-setting", hidden:true,
          }, element("div", {class:"lex-setting-copy"},
            element("label", {for:`lex-default-${definition.key}`}, definition.title),
            element("p", {}, `${definition.description}${supported ? "" : " Restart LEXEDITOR to enable this newly added setting."}`)), wrapped);
          card.dataset.lexSettingSupported = String(supported);
          lexerLane.append(card);
          defaultCards.push(card);
          continue;
        }
        const currentSupported = supportsCurrent(definition);
        const defaultSupported = supportsDefault(definition);
        const wrapped = makeControl(definition, initialValue(definition), `lex-${definition.key}`);
        controlNode(wrapped).disabled = !currentSupported;
        currentControls.set(definition.key, wrapped);
        const copy = element("div", {class:"lex-setting-copy"},
          element("label", {for:`lex-${definition.key}`}, definition.title),
          element("p", {}, `${definition.description}${currentSupported ? "" : " Restart LEXEDITOR to enable this newly added setting."}`));
        const defaultWrapped = makeControl(definition, initialValue(definition, true), `lex-default-${definition.key}`);
        defaultControls.set(definition.key, defaultWrapped);
        const defaultControl = element("label", {
          class:"lex-setting-default-control lex-lexer-setting", hidden:true,
          for:`lex-default-${definition.key}`, title:"Default for every user",
        }, element("span", {}, "DEFAULT"), defaultWrapped);
        defaultControl.dataset.lexSettingSupported = String(defaultSupported);
        const controls = element("div", {class:"lex-setting-control-pair"}, wrapped, defaultControl);
        const card = element("section", {class:`lex-global-setting lex-${definition.scope}-setting`}, copy, controls);
        (definition.scope === "developer" ? developerLane : userLane).append(card);
        defaultCards.push(defaultControl);
        copy.addEventListener("dblclick", event => { event.preventDefault(); copyToDefault(definition, defaultControl); });
      }
      lexerMode.addEventListener("change", setDefaultVisibility);
      setDefaultVisibility();
      let savedSettings = clone(settings);
      settingsDirtyCount = () => {
        let dirty = supportedOrdinaryDefinitions.reduce((total, definition) => total + Number(
          readControl(definition, currentControls.get(definition.key)) !== savedSettings[definition.key]), 0);
        dirty += Number(lexerMode.checked !== !!savedSettings.lexerMode);
        if (lexerMode.checked && !lexerMode.disabled) {
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
        lexerMode.checked = !!savedSettings.lexerMode;
        setDefaultVisibility();
        developerSetting.classList.toggle("active-developer-setting", developerMode.checked);
        message.textContent = "Restored the last saved settings.";
      };
      const save = settingsSaveControl({
        dirtyCount: settingsDirtyCount,
        save: async () => {
          message.textContent = "Saving settings…";
          try {
            const values = Object.fromEntries(supportedOrdinaryDefinitions.map(definition =>
              [definition.key, readControl(definition, currentControls.get(definition.key))]));
            settings = rememberSharedSettings(await callWindow("save_lexeditor_settings", {...values, lexerMode: lexerMode.checked}));
            if (lexerMode.checked) {
              const defaults = Object.fromEntries(supportedDefaultDefinitions.map(definition =>
                [definition.key, readControl(definition, defaultControls.get(definition.key))]));
              settings = rememberSharedSettings(await callWindow("save_lexer_setting_defaults", defaults));
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
      const developerMode = controlNode(currentControls.get("developerMode"));
      const developerSetting = developerMode.closest(".lex-global-setting");
      developerSetting.classList.toggle("active-developer-setting", developerMode.checked);
      developerMode.addEventListener("change", () => developerSetting.classList.toggle("active-developer-setting", developerMode.checked));
      const dialogChildren = [
        heading,
        element("div", {class:"lex-settings-columns"}, userLane, developerLane, lexerLane),
      ];
      dialogChildren.push(message, element("div", {class: "lex-dialog-actions"}, save));
      dialog.replaceChildren(...dialogChildren);
      // Editing any control has to re-arm the save button. Without this the
      // dialog opens with save disabled and never enables, so a changed
      // setting cannot be saved at all.
      dialog.addEventListener("input", () => save.refresh?.());
      dialog.addEventListener("change", () => save.refresh?.());
      message.textContent = unsupportedDefinitions.length
        ? "Restart LEXEDITOR to enable newly added settings. Other settings can still be saved."
        : "";
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
    const workflows = ["actionable", "waiting", "unfeasible"];
    const state = {
      open: false, loaded: false, busy: false, filter: "actionable", query: "",
      issues: [], labels: [], selected: null, issue: null,
    };
    const hasLabel = (issue, name) => (issue?.labels || []).some(label => label.name === name);
    const status = element("div", {class: "lex-github-status", "aria-live": "polite"});
    const search = element("input", {
      type: "search", placeholder: "Search issues…", "aria-label": "Search GitHub issues",
      oninput: event => { state.query = event.target.value; renderList(); },
    });
    const refresh = element("button", {
      class: "lex-github-refresh", title: "Refresh issues", "aria-label": "Refresh GitHub issues",
      onclick: () => loadIssues(),
    }, "↻");
    const workflowButtons = workflows.map(workflow => element("button", {
      class: "lex-github-workflow-tab", "data-workflow": workflow,
      onclick: () => selectWorkflow(workflow),
    }, workflow.toUpperCase()));
    const subtabs = element("div", {class: "lex-github-subtabs", role: "tablist"}, ...workflowButtons);
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
    },
      subtabs,
      element("div", {class: "lex-github-toolbar"},
        element("div", {class: "lex-github-repository"}, repository.repository),
        search, status, refresh),
      layout);
    header.after(root);

    const setStatus = (message, error = false) => {
      status.textContent = message || "";
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
        control.textContent = `${workflow.toUpperCase()} ${count}`;
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
      const rows = visibleRows();
      issueList.replaceChildren(...rows.map(issue => element("button", {
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
        element("span", {class: `lex-github-state ${String(issue.state).toLowerCase()}`}, issue.state))));
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
      const labelEditor = element("div", {class: "lex-github-label-editor"});
      for (const label of state.labels.filter(row => row.name !== "high priority")) {
        const checkbox = element("input", {
          type: "checkbox", checked: selectedLabels.has(label.name), "data-label": label.name,
        });
        const control = element("label", {
          class: "lex-github-label-option",
          style: `--github-label:#${label.color || "808080"}`,
          title: label.description || label.name,
        }, checkbox, element("span", {}, label.name));
        checkbox.onchange = async () => {
          if (checkbox.checked && workflows.includes(label.name)) {
            labelEditor.querySelectorAll("input").forEach(input => {
              if (input !== checkbox && workflows.includes(input.dataset.label)) input.checked = false;
            });
          }
          const desired = [...labelEditor.querySelectorAll("input:checked")].map(input => input.dataset.label);
          if (selectedLabels.has("high priority")) desired.push("high priority");
          labelEditor.querySelectorAll("input").forEach(input => { input.disabled = true; });
          setStatus(`Updating labels on #${issue.number}…`);
          try {
            const updated = await callWindow(
              "github_set_issue_labels", options.plugin.id, issue.number, desired,
            );
            if (!updated) throw new Error("The GitHub bridge is unavailable");
            await finishUpdatedIssue(updated, `Updated labels on #${issue.number}.`);
          } catch (error) {
            setStatus(`Label update failed: ${githubError(error)}`, true);
            renderIssue();
          }
        };
        labelEditor.append(control);
      }
      editor.replaceChildren(
        element("div", {class: "lex-github-title-row"},
          element("span", {class: "lex-github-detail-number"}, `#${issue.number}`), title,
          element("span", {class: `lex-github-state ${String(issue.state).toLowerCase()}`}, issue.state)),
        body,
        element("div", {class: "lex-github-edit-actions"}, save, editStatus,
          element("span", {class: "lex-github-updated"}, `Updated ${githubDate(issue.updatedAt)}`)),
        element("section", {class: "lex-github-labels-section"},
          element("h3", {}, "LABELS"), labelEditor));

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
          element("h3", {}, `COMMENTS ${(issue.comments || []).length}`), priority),
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
        setStatus(`${workflowRows().length} ${state.filter} issue${workflowRows().length === 1 ? "" : "s"}.`);
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
      document.body.dataset.lexGithubOpen = "true";
      header.classList.add("lex-github-open");
      header.querySelectorAll("nav button").forEach(control => control.classList.toggle("active", control === button));
      button.classList.add("active");
      button.setAttribute("aria-pressed", "true");
      navigationChanged();
      if (!state.loaded) loadIssues();
      else search.focus();
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

  const mountShell = options => {
    activeShellReadonly = typeof options.readonly === "function" ? options.readonly : null;
    const host = typeof options.host === "string" ? document.querySelector(options.host) : options.host;
    if (!host) throw new Error("Lexeditor shell host is missing");
    document.body.dataset.lexPlugin = options.plugin.id;
    document.body.dataset.lexTheme = options.plugin.themeName || options.plugin.id;
    applyTheme(options.plugin.theme);

    const brand = element("button", {
      class: "lex-brand-button",
      title: "Return to main menu",
      "aria-label": "Return to main menu",
      "data-lex-history-control": true,
    }, element("h1", {text: options.brand || "LEXEDITOR"}));
    const nav = element("nav", {"aria-label": `${options.plugin.name || options.plugin.id} sections`});
    const navFrame = element("div", {class: "lex-nav-frame"}, nav);
    let githubWorkspace = null;
    let navigationHistory = null;
    let developerMode = false;
    let lexerMode = false;
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
    const isSpecialTab = tab => tab.special === true || ["settings", "tweaks"].includes(tab.id);
    const orderedTabs = [...options.tabs].sort((left, right) => {
      const leftSettings = isSpecialTab(left);
      const rightSettings = isSpecialTab(right);
      if (leftSettings !== rightSettings) return leftSettings ? 1 : -1;
      return String(left.label).localeCompare(String(right.label), undefined, {sensitivity: "base"});
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
        class: [tab.id === options.activeTab() ? "active" : "", isSpecialTab(tab) ? "lex-settings-tab" : ""].filter(Boolean).join(" "),
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
          if (event.button !== 2 || !lexerMode) return;
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
          element("span", {class: "lex-tab-label-text"}, tab.label)),
        (key => key ? element("span", {
          class: "lex-tab-shortcut", "aria-hidden": "true",
        }, key) : "")(shortcutKeyFor(tabIndex + 1)));
      nav.append(button);
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
      "data-lex-history-control": true, onclick: options.help,
    }, mapIcon()) : null;
    const info = options.info ? element("button", {
      id: "plugin-info", class: "lex-help-button", title: options.infoTitle || `Open ${options.plugin.id} information`,
      "aria-label": options.infoTitle || `Open ${options.plugin.id} information`,
      "data-lex-history-control": true, onclick: options.info,
    }, infoIcon()) : null;
    const github = element("button", {
      id: "plugin-github", class: "lex-developer-button lex-github-tab", hidden: true,
      title: "Open GitHub issues inside Lexeditor", "aria-label": "Open GitHub issues inside Lexeditor",
      "aria-pressed": "false", "data-lex-history-control": true,
    }, githubLogo());
    const restart = element("button", {
      id: "plugin-restart", class: "lex-developer-button", hidden: true,
      title: "Restart this plugin", "aria-label": "Restart this plugin",
      "data-lex-history-control": true,
    }, restartIcon());
    const projectControl = mountProjectControl(options, context);
    const brandSlot = element("div", {class: "lex-brand-slot"}, brand);
    const leftActions = element("div", {class: "lex-shell-left-actions"}, context);
    const centerActions = element("div", {class: "lex-shell-center-actions"}, undo, save, game, redo);
    const rightActions = element("div", {class: "lex-shell-right-actions"}, settings, shortcuts, help, info);
    const developerActions = element("div", {class: "lex-developer-actions"}, github, restart);
    const commandRow = element("div", {class: "lex-shell-command-row"},
      brandSlot, leftActions, centerActions, rightActions, developerActions, windowControls.root);
    const header = element("header", {class: "lex-shell-header"}, commandRow, navFrame);
    host.replaceWith(header);

    // The centre commands are deliberately pinned to the viewport centre.
    // Bound the project region to their measured left edge so its 100%-wide
    // dropdown cannot continue behind Save and Play toward the right rail.
    const fitProjectRegion = () => {
      const left = leftActions.getBoundingClientRect().left;
      const centre = centerActions.getBoundingClientRect().left;
      leftActions.style.width = `${Math.max(0, Math.floor(centre - left - 7))}px`;
    };
    const projectRegionObserver = new ResizeObserver(fitProjectRegion);
    projectRegionObserver.observe(commandRow);
    projectRegionObserver.observe(centerActions);
    commandRow.lexProjectRegionObserver = projectRegionObserver;
    window.addEventListener("resize", fitProjectRegion);
    requestAnimationFrame(fitProjectRegion);

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
      } catch (_error) {
        github.hidden = true;
      }
    };
    const setDeveloperMode = enabled => {
      developerMode = !!enabled;
      restart.hidden = !developerMode;
      if (!developerMode) {
        githubWorkspace?.hide();
        github.hidden = true;
      } else {
        initializeGitHub();
      }
    };
    const setLexerMode = enabled => { lexerMode = !!enabled; };
    const initializeDeveloperMode = async () => {
      try {
        const value = rememberSharedSettings(await callWindow("lexeditor_settings"));
        setDeveloperMode(value?.developerMode); setLexerMode(value?.lexerMode);
      }
      catch (_error) { setDeveloperMode(false); setLexerMode(false); }
    };
    window.addEventListener("lexeditor-settings-changed", event => {
      rememberSharedSettings(event.detail);
      setDeveloperMode(event.detail?.developerMode);
      setLexerMode(event.detail?.lexerMode);
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
      if (!opened?.url) return false;
      window.__lexeditorNavigating = true;
      // A restart is still a load, so it gets a real loading message rather
      // than dropping through to the fallback text.
      const destination = new URL(opened.url, location.href);
      let quote = "";
      try { quote = (await callWindow("loading_quote", options.plugin.id))?.quote || ""; }
      catch (_error) {}
      destination.searchParams.set("lexTransition", "load");
      if (quote) destination.searchParams.set("lexQuote", quote);
      destination.searchParams.set("lexLoadStarted", String(Date.now()));
      location.href = destination.href;
      return true;
    };
    restart.onclick = () => confirmUnsavedExit(options, restartPlugin, {
      title: "Unsaved changes",
      question: "Save before restarting this plugin?",
      discardLabel: "Restart Without Saving",
      saveLabel: "Save and Restart",
      exitError: "Could not restart the plugin",
    });
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
    undo.onclick = async () => history?.undo();
    redo.onclick = async () => history?.redo();
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
    let gameRunning = false;
    const renderGameProcess = running => {
      gameRunning = !!running;
      game.replaceChildren(gameRunning ? stopIcon() : playIcon());
      game.title = gameRunning ? "Stop game" : "Launch game";
      game.setAttribute("aria-label", game.title);
      game.classList.toggle("running", gameRunning);
    };
    const refreshGameProcess = async () => {
      try { renderGameProcess((await callWindow("game_process_status", options.plugin.id))?.running); }
      catch (_error) { game.hidden = true; }
    };
    game.onclick = async () => {
      game.disabled = true;
      try {
        const launching = !gameRunning;
        if (launching) await options.beforeLaunch?.();
        const result = await callWindow(launching ? "launch_game" : "stop_game", options.plugin.id);
        renderGameProcess(result?.running);
        if (launching && result?.running) options.afterLaunch?.(result);
      } catch (error) {
        showAlert({title: gameRunning ? "Could not stop the game" : "Could not launch the game", message: error.message || String(error)});
      } finally { game.disabled = false; }
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

    let lastReportedDirty = null;
    function refresh() {
      refreshReferences();
      projectControl.refresh?.();
      const dirty = options.dirtyCount?.() || 0;
      navigationHistory?.visit(githubWorkspace?.state.open ? "github" : `tab:${options.activeTab()}`);
      undo.disabled = !history?.canUndo;
      redo.disabled = !history?.canRedo;
      const projectReadonly = !!options.readonly?.();
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
      github.classList.toggle("active", !!githubWorkspace?.state.open);
      help?.classList.toggle("active", !!options.helpActive?.());
      info?.classList.toggle("active", !!options.infoActive?.());
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
        undo: () => history?.undo?.(),
        redo: () => history?.redo?.(),
        save: () => save.click(),
        settings: () => settings.click(),
        datamap: () => options.help?.(),
        info: () => options.info?.(),
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
        subtab: () => document.querySelectorAll(".lex-subtab-button")[
          Number(shortcutDigit(event)) - 1]?.click(),
      }[action];
      if (!run) return;
      event.preventDefault();
      flashShortcut(action);
      run();
    };
    document.addEventListener("keydown", shortcutHandler);

    // Hovering a tab reveals the number that jumps to it.
    nav.addEventListener("pointerover", event => {
      const button = event.target.closest?.("button[data-tab]");
      if (!button || button.querySelector(".lex-tab-ordinal")) return;
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
        onclick: options.select ? () => options.select(row) : null,
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
    const automaticGrow = nameIndex >= 0 ? nameIndex : Math.max(0, firstReal);
    return columns.map((column, index) => {
      if (column.width) return column.width;
      const grow = Number(column.grow) || (!declaredGrow && index === automaticGrow ? 1 : 0);
      return grow > 0 ? `minmax(0, ${grow}fr)` : "max-content";
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
  const withEnabledColumn = (declared, rows, change) => {
    const columns = declared || [];
    if (!hasEnabledProperty(rows)) return columns;
    if (columns.some(column => String(column.key).toLocaleLowerCase() === ENABLED_KEY)) return columns;
    return [enabledColumn(change), ...columns];
  };

  const columnPreferences = (viewKey, definitions, changed = () => {}) => {
    const key = `lexeditor:columns:${String(viewKey || "view")}`;
    const source = numberedIdColumns(definitions || [], []);
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
      // A changed column set changes the table's real minimum width. Discard
      // the old divider size so the shared layout can fit the new table.
      for (const layoutKey of [
        `lexeditor:panel-layout:${viewKey}`,
        `lexeditor:list-detail:${viewKey}`,
      ]) {
        try { localStorage.removeItem(layoutKey); } catch (_error) {}
      }
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
          "data-lex-pin-column": value,
          title: pinned ? `Hide ${label} in the table` : `Show ${label} in the table`,
          "aria-label": pinned ? `Unpin ${label} column` : `Pin ${label} column`,
          "aria-pressed": String(pinned),
          onpointerenter: () => setColumnLit(value, true),
          onpointerleave: () => setColumnLit(value, false),
          onclick: event => { event.preventDefault(); event.stopPropagation(); api.toggle(value); },
        }, icon);
      },
    };
    return api;
  };

  // Hovering a column header (or the pin that owns that column) lights the
  // whole column and the matching property in the detail pane, so the reader
  // can see what a table column and a detail row have to do with each other.
  const litColumns = new Set();
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
  // Tab is a property-level move inside a detail pane. Stepping through every
  // focusable control in a row makes a long pane unusable with the keyboard.
  const propertyTabNavigation = event => {
    if (event.key !== "Tab" || event.altKey || event.ctrlKey || event.metaKey) return;
    const field = event.target?.closest?.(".lex-detail-field");
    if (!field) return;
    const pane = field.closest(".lex-detail-panel-body") || field.closest(".lex-detail");
    if (!pane) return;
    const fields = [...pane.querySelectorAll(".lex-detail-field")];
    const index = fields.indexOf(field);
    const next = fields[index + (event.shiftKey ? -1 : 1)];
    if (!next) return;
    const target = next.querySelector(
      "input:not([type='hidden']):not([disabled]),select:not([disabled]),textarea:not([disabled]),button:not([disabled]):not([tabindex='-1'])");
    if (!target) return;
    event.preventDefault();
    target.focus();
    target.select?.();
  };
  document.addEventListener("keydown", propertyTabNavigation);

  // The rail doubles as the sort indicator when its row is not hovered.
  const setColumnSort = (key, direction) => {
    for (const node of document.querySelectorAll("[data-lex-property]")) {
      if (node.dataset.lexProperty === String(key) && direction) {
        node.dataset.lexSort = direction > 0 ? "asc" : "desc";
      } else {
        delete node.dataset.lexSort;
      }
    }
  };

  const bindColumnHighlight = (node, key) => {
    if (!node || !key) return node;
    node.addEventListener("pointerenter", () => setColumnLit(key, true));
    node.addEventListener("pointerleave", () => setColumnLit(key, false));
    return node;
  };

  // Editing is a per-cell action, not a table mode: double-click a value and
  // the column's own editor takes over that cell until it is committed or
  // dismissed. Tables that never declare an editor stay read-only.
  const beginCellEdit = (cell, column, row, refresh) => {
    if (!column?.edit || cell.classList.contains("lex-cell-editing")) return;
    if (shellIsReadonly()) return;
    const content = cell.querySelector(".lex-column-cell-content");
    if (!content) return;
    const original = [...content.childNodes];
    const commit = value => {
      cell.classList.remove("lex-cell-editing");
      content.replaceChildren(...original);
      if (value !== undefined) column.edit(row, value);
      refresh?.();
    };
    const editor = column.editor
      ? column.editor(row, commit)
      : (() => {
        const input = element("input", {
          type: column.numeric ? "number" : "text",
          value: column.editValue ? column.editValue(row) : (row?.[column.key] ?? ""),
        });
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

  const columnList = options => {
    const preferredColumns = options.columnPreferences?.active?.();
    // The generic enabled column is not a user-choosable column, so it is
    // added after saved preferences rather than being subject to them.
    const columns = preferredColumns
      ? withEnabledColumn(preferredColumns, options.rows, options.enabledChange)
      : numberedIdColumns(
          withEnabledColumn(options.columns, options.rows, options.enabledChange),
          options.rows || []);
    if (columns.some(column => isNumberedIdColumn(column, options.rows || []))) {
      setRecordIdWidth(options.rows, {floor: options.idFloor});
    }
    requestAnimationFrame(() => {
      const active = Array.isArray(options.sortState)
        ? {key: options.sortState[0], dir: options.sortState[1]}
        : (options.sortState || {});
      setColumnSort(active.key, active.dir);
    });
    const sortState = Array.isArray(options.sortState)
      ? {key: options.sortState[0], dir: options.sortState[1]}
      : (options.sortState || {});
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
    const localSort = column => {
      const nextDirection = sortState.key === column.key ? -(Number(sortState.dir) || 1) : 1;
      const indexed = (options.rows || []).map((row, index) => ({row, index}));
      indexed.sort((left, right) => {
        const first = valueForSort(left.row, column);
        const second = valueForSort(right.row, column);
        const result = typeof first === "number" && typeof second === "number"
          ? first - second
          : String(first).localeCompare(String(second), undefined, {numeric:true, sensitivity:"base"});
        return result ? result * nextDirection : left.index - right.index;
      });
      const replacement = columnList({
        ...options,
        rows: indexed.map(entry => entry.row),
        sortState: {key: column.key, dir: nextDirection},
        idFloor: recordIdWidth,
      });
      root?.replaceWith(replacement);
      // A local sort replaces the table in place, so anything outside it - the
      // pager summary - only learns of the new order from this event.
      replacement.dispatchEvent(new CustomEvent("lex-column-sorted",
        {bubbles: true, detail: {key: column.key, dir: nextDirection}}));
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
            type: "button", class: ["lex-column-sort", active ? "sorted" : ""].filter(Boolean).join(" "),
            title: `Sort by ${typeof column.label === "string" ? column.label : column.key}`,
          }, label)
        : label;
      const help = column.help ? infoHelp(column.help) : null;
      const content = help
        ? element("span", {class: "lex-column-heading"}, sortControl, help)
        : sortControl;
      return bindColumnHighlight(element("div", {
        class: ["lex-column-list-head-cell", active ? "sorted" : "", headerAlignmentClass(column), column.class || ""].filter(Boolean).join(" "),
        role: "columnheader",
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
      class: ["lex-column-list", options.editable ? "lex-editable-table" : "", options.class || ""].filter(Boolean).join(" "),
      role: "table",
      style: `--lex-column-list-template:${template};grid-template-columns:var(--lex-column-list-template)`,
      "aria-label": options["aria-label"],
      "aria-rowcount": options.rows.length + 1,
      header,
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
            alignmentClass(column),
            typeof column.cellClass === "function" ? column.cellClass(row) : column.cellClass || ""].filter(Boolean).join(" "),
          role: "cell",
          "data-column-key": column.key,
        }, element("span", {class: "lex-column-cell-content"}, content));
        if (column.edit) {
          cell.addEventListener("dblclick", event => {
            event.preventDefault();
            beginCellEdit(cell, column, row, options.refresh);
          });
        }
        return cell;
      }),
    });
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
    const root = element("div", {
      class: `lex-panel-layout ${className}`.trim(),
    });
    const stackAt = [700, 850, 1000, 1100].includes(Number(options.stackAt))
      ? Number(options.stackAt) : 850;
    root.classList.add(`lex-panel-layout-stack-${stackAt}`);
    nodes.forEach(node => node.classList?.add("lex-panel-layout-pane"));
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
        "aria-orientation": "vertical",
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
    const resizePair = (index, delta, persist = false, edge = "") => {
      const widths = nodes.map(node => node.getBoundingClientRect().width);
      const pairWidth = Math.max(1, widths[index] + widths[index + 1]);
      const requestedMinimum = minSizes[index] + minSizes[index + 1];
      // When the window is narrower than both requested minimums, preserve
      // their ratio instead of abandoning the clamp. Abandoning it let a
      // multi-barrel table cut off its final column before resizing stopped.
      const minimumScale = Math.min(1, pairWidth / Math.max(1, requestedMinimum));
      const leftMinimum = minSizes[index] * minimumScale;
      const rightMinimum = minSizes[index + 1] * minimumScale;
      const low = Math.max(leftMinimum,
        pairWidth * minimumFractions[index]);
      const high = Math.max(low, Math.min(pairWidth - rightMinimum,
        pairWidth * (1 - minimumFractions[index + 1])));
      let left = widths[index] + delta;
      if (edge === "home") left = low;
      if (edge === "end") left = high;
      left = Math.max(low, Math.min(high, left));
      if (Math.abs(left - widths[index]) < .25) return false;
      widths[index] = left;
      widths[index + 1] = pairWidth - left;
      setSizes(widths, persist);
      return true;
    };
    const finishDrag = (divider, event) => {
      divider.classList.remove("dragging");
      document.body.classList.remove("lex-panel-layout-dragging");
      try {
        if (divider.hasPointerCapture?.(event.pointerId)) divider.releasePointerCapture(event.pointerId);
      } catch (_error) {}
      setSizes(sizes, true);
    };
    dividers.forEach((divider, index) => {
      divider.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        // Divider accessories are controls, not resize handles. Capturing their
        // pointer made the shared Barrels buttons appear live but do nothing.
        if (event.target.closest?.("button,input,select,textarea,[role=button]")) return;
        event.preventDefault();
        divider.classList.add("dragging");
        document.body.classList.add("lex-panel-layout-dragging");
        try { divider.setPointerCapture?.(event.pointerId); } catch (_error) {}
      });
      divider.addEventListener("pointermove", event => {
        if (!divider.classList.contains("dragging")) return;
        const box = divider.getBoundingClientRect();
        resizePair(index, event.clientX - (box.left + box.width / 2));
      });
      divider.addEventListener("pointerup", event => finishDrag(divider, event));
      divider.addEventListener("pointercancel", event => finishDrag(divider, event));
      divider.addEventListener("keydown", event => {
        const pairWidth = nodes[index].getBoundingClientRect().width +
          nodes[index + 1].getBoundingClientRect().width;
        const step = pairWidth * (event.shiftKey ? .05 : .02);
        if (event.key === "ArrowLeft") resizePair(index, -step, true);
        else if (event.key === "ArrowRight") resizePair(index, step, true);
        else if (event.key === "Home") resizePair(index, 0, true, "home");
        else if (event.key === "End") resizePair(index, 0, true, "end");
        else return;
        event.preventDefault();
      });
      divider.addEventListener("contextmenu", event => {
        event.preventDefault();
        setSizes(defaults, true);
      });
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
        eventName: "lex-list-detail-resize",
      });
    if (options.resizable !== false) root.classList.add("lex-list-detail-resizable");
    root.__lexListDetailObserver = root.__lexPanelLayoutObserver;
    return root;
  };
  const masterDetail = listDetail;

  // Fit a paged list to complete rendered rows. The caller owns the records and
  // pagination state; this shared measurement owns only visible capacity.
  const fitListPage = options => {
    const listNode = options.list;
    if (!listNode) return null;
    const availableNode = options.available || listNode;
    listNode.classList.add("lex-fitted-page");
    let frame = 0;
    const fixedRows = Math.max(0, Number(options.fixedRows) || 0);
    const fittedLists = (options.lists || [listNode]).filter(Boolean);
    let lastSize = Math.max(1, Number(options.pageSize) || 1);
    const measure = () => {
      frame = 0;
      if (!listNode.isConnected) return;
      const header = listNode.querySelector(options.headerSelector || ".lex-column-list-header, .loot-listhead, .rdr-listhead") ||
        (listNode.firstElementChild?.classList.contains("lex-list-row") ? null : listNode.firstElementChild);
      const rows = [...listNode.querySelectorAll(options.rowSelector || ".lex-list-row")];
      if (!rows.length) return;
      // A paged view can set one real CSS row height for content whose icons or
      // glyphs otherwise alter the line box. That keeps capacity independent
      // of the page being displayed. Measuring only the current page can make
      // two pages choose different sizes and repeatedly navigate into each
      // other. Views without a fixed row contract still use the rendered row.
      const configuredRowHeight = parseFloat(
        getComputedStyle(listNode).getPropertyValue("--lex-fitted-row-height")
      );
      const measuredRowHeight = rows[0].getBoundingClientRect().height;
      const naturalRowHeight = configuredRowHeight > 0 ? configuredRowHeight : measuredRowHeight;
      if (!(naturalRowHeight > 0) || !(availableNode.clientHeight > 0)) return;
      const headerHeight = header?.getBoundingClientRect().height || 0;
      const listStyle = getComputedStyle(listNode);
      const borderHeight = (parseFloat(listStyle.borderTopWidth) || 0) +
        (parseFloat(listStyle.borderBottomWidth) || 0);
      const available = Math.max(0, availableNode.clientHeight - borderHeight - headerHeight);
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
      const fittedHeight = full ? availableNode.clientHeight :
        Math.ceil(borderHeight + headerHeight + visibleRows * rowHeight);
      options.resize?.(fittedHeight, {full, pageSize, visibleRows, rowHeight});
      if ((!fixedRows || minimumRowHeight > 0) && pageSize !== lastSize) {
        lastSize = pageSize;
        options.change?.(pageSize);
      }
    };
    let fontsReady = !document.fonts;
    const schedule = () => {
      if (!fontsReady) return;
      // The fixed pager changes #main through :has(). Wait for two quiet
      // layout frames so a first measurement cannot use the pre-pager height
      // and then strand one clipped row after the content area contracts.
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(measure);
      });
    };
    if (document.fonts) {
      document.fonts.ready.then(() => {
        fontsReady = true;
        schedule();
      });
    } else {
      schedule();
    }
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

  const pager = options => {
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
    const first = total ? page * pageSize + 1 : 0;
    const last = total ? Math.min(total, first + pageSize - 1) : 0;
    const controls = element("div", {class: "lex-pager-controls"},
      button("<<", 0, page <= 0, "First page"),
      button("<", page - 1, page <= 0, "Previous page"),
      element("span", {class: "lex-page-position"},
        pageInput, element("span", {"aria-hidden": "true"}, "/"),
        element("span", {class: "lex-page-total", text: pages})),
      button(">", page + 1, page + 1 >= pages, "Next page"),
      button(">>", pages - 1, page + 1 >= pages, "Last page"));
    const left = element("div", {class: "lex-pager-left"},
      options.search ? bottomSearch(options.search) : null);
    let rowControl = null;
    if (options.rowControl) {
      const commitRows = input => options.rowControl.change?.(input.value);
      const rowInput = element("input", {
        type: "number", min: "5", max: "80", step: "1", value: options.rowControl.value,
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
      ...(options.filters || []),
      element("span", {class: "lex-page-summary", text: `${formatNumber(first)}-${formatNumber(last)}/${formatNumber(total)}`}));
    return element("div", {
      class: `lex-pager${pages === 1 ? " single-page" : ""}`,
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

  const pagedListDetail = options => {
    const slotBased = options.slots !== false;
    if (options.slots === undefined && sharedSettingsSnapshot?.developerMode) {
      console.warn(`Table "${options.splitKey || options.noun || "records"}" does not declare slots:`
        + " true for fixed slots, false for a growable list.");
    }
    const emptyRow = slotBased && typeof options.empty === "function" ? options.empty : null;
    const hideEmptyKey = slotTablePreferenceKey(options);
    const hideEmpty = Boolean(emptyRow) && readHideEmpty(hideEmptyKey);
    const suppliedRows = Array.isArray(options.rows) ? options.rows : [];
    const records = hideEmpty ? suppliedRows.filter(record => !emptyRow(record)) : suppliedRows;
    const emptyCount = emptyRow ? suppliedRows.reduce(
      (count, record) => count + (emptyRow(record) ? 1 : 0), 0) : 0;
    // Set the id width before either pane renders so the detail heading and
    // the table agree on padding.
    setRecordIdWidth(records, {wholeSet: true});
    const keyOf = options.key;
    // A Table page uses one global row target. Plugin-local page sizes are only
    // compatibility state until the shared settings snapshot arrives.
    const rowPreferenceKey = tableRowPreferenceKey(options);
    const fitMinimum = Math.max(0, Number(options.fit?.minRowHeight) || 0);
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
    if (options.revealSelected !== false && requestedIndex >= 0 &&
        (requestedIndex < page * barrelSize || requestedIndex >= (page + 1) * barrelSize)) {
      page = Math.floor(requestedIndex / barrelSize);
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
      const targetPage = Math.max(0, Math.min(Number(target) || 0, pages - 1));
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
    let detailNode = picked
      ? options.detail(picked)
      : (typeof options.emptyDetail === "function" ? options.emptyDetail() : options.emptyDetail || element("div", {class: "lex-detail"}));
    let leadingNode = typeof options.leadingPanel === "function" && picked ? options.leadingPanel(picked) : null;
    let masterNodes = [];
    const select = record => {
      const nextSelected = keyOf(record);
      if (nextSelected === selected) return false;
      selected = nextSelected;
      options.sync?.({page, pageSize, selected, reason:"select"});
      for (const node of masterNodes) {
        node.querySelectorAll(".lex-list-row[data-key]").forEach(row => {
          const active = String(row.dataset.key) === String(selected);
          row.classList.toggle("selected", active);
          row.classList.remove("sel");
          row.setAttribute("aria-selected", String(active));
        });
      }
      const replacement = options.detail(record);
      if (detailNode.classList.contains("lex-panel-layout-pane")) replacement.classList.add("lex-panel-layout-pane");
      const fixedHeight = detailNode.style.height;
      if (fixedHeight) replacement.style.height = fixedHeight;
      detailNode.replaceWith(replacement);
      detailNode = replacement;
      if (leadingNode) {
        const nextLeading = options.leadingPanel(record);
        nextLeading.classList.add("lex-panel-layout-pane");
        leadingNode.replaceWith(nextLeading);
        leadingNode = nextLeading;
        refreshReferences(nextLeading);
      }
      refreshReferences(replacement);
      return true;
    };
    masterNodes = barrelRows.map((rows, index) => {
      const node = typeof options.master === "function"
        ? options.master({rows, selected, select, barrel: index, barrels})
        : list({...options.list, rows, key: keyOf, selected, select});
      fitBarrelTableColumns(node);
      // Filler rows exist to square off a growable list. A slot table shows one
      // row per real slot, so a short last page simply ends.
      if (!slotBased) padBarrelTable(node, pageSize);
      node.classList.add("lex-page-sized-table");
      node.style.setProperty("--lex-page-row-count", String(rowCapacity));
      node.dataset.lexBarrel = String(index + 1);
      if (index) node.classList.add("lex-fitted-page");
      return node;
    });
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
    // A fitted master has no vertical scroll range, so use its wheel as the
    // quickest page control. High-resolution wheels emit many small events for
    // one gesture; lock after the first page until that event stream is quiet.
    let wheelDelta = 0;
    let wheelLocked = false;
    let wheelQuietTimer = 0;
    masterNode.addEventListener("wheel", event => {
      if (event.ctrlKey || event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY) ||
          event.target.closest?.("input,select,textarea,[contenteditable=true]")) return;
      const scale = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16
        : event.deltaMode === WheelEvent.DOM_DELTA_PAGE ? Math.max(1, masterNode.clientHeight) : 1;
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
      changePage(page + (wheelDelta > 0 ? 1 : -1));
    }, {passive:false});
    const barrelPanelMinimum = Math.max(160, Number(options.minLeft) || 280) * barrels +
      7 * (barrels - 1);
    const root = leadingNode ? panelLayout([leadingNode, masterNode, detailNode],
      `lex-list-detail lex-master-detail lex-list-detail-resizable lex-leading-list-detail ${options.className || ""}`, {
        defaultSizes: [options.defaultLeadingWidth || 25, 30, 45],
        minSizes: [Math.max(220, Number(options.minLeading) || 300), barrelPanelMinimum, Math.max(240, Number(options.minRight) || 360)],
        storageKey: options.splitKey ? `lexeditor:leading-list-detail:${options.splitKey}` : "",
        dividerClass: "lex-list-detail-divider",
        dividerAccessories: [null, barrelControl],
        dividerLabels: ["Resize secondary panel and list", "Resize list and detail panels"],
        eventName: "lex-list-detail-resize",
      }) : listDetail(masterNode, detailNode, options.className || "", {
      splitKey: options.splitKey,
      defaultSplit: options.defaultSplit,
      minLeft: barrelPanelMinimum,
      minRight: options.minRight,
      minimumSplit: Math.min(78, 22 * barrels),
      dividerAccessories: [barrelControl],
    });
    root.classList.add("lex-paged-list-detail");
    root.dataset.lexPage = String(page);
    root.dataset.lexPageSize = String(pageSize);
    const bottomTools = [...(options.filters || [])];
    if (!slotBased && typeof options.add === "function") {
      bottomTools.push(newButton({
        class: "lex-pager-add",
        title: options.addTitle || `Add ${options.noun || "record"}`,
        disabled: options.addDisabled === true,
        onclick: () => options.add(),
      }));
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
        const selectedIndex = records.findIndex(record => keyOf(record) === selected);
        const anchor = selectedIndex >= 0 ? selectedIndex : groupStart;
        const nextBarrelSize = nextSize * barrels;
        const nextPages = Math.max(1, Math.ceil(records.length / nextBarrelSize));
        const nextPage = Math.max(0, Math.min(Math.floor(anchor / nextBarrelSize), nextPages - 1));
        change("table-rows", {page: nextPage, pageSize: nextSize});
      };
      const rowControl = sharedSettingsSnapshot?.developerMode ? {
        value: pageSize,
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
      if (window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          if (!root.isConnected) { observer.disconnect(); return; }
          measurePager();
        });
        observer.observe(pagerNode);
        setTimeout(() => observer.disconnect(), 10000);
      }
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
          masterNode.style.height = `${height}px`;
          root.classList.toggle("lex-full-table-page", !!measurement?.full);
          detailNode.style.height = measurement?.full ? `${height}px` : "";
        },
        change: nextSize => {
          if (fitMinimum) tableFitCapacityCache.set(rowPreferenceKey, {capacity: nextSize, requested: requestedPageSize});
          const selectedIndex = records.findIndex(record => keyOf(record) === selected);
          const anchor = selectedIndex >= 0 ? selectedIndex : groupStart;
          const nextBarrelSize = nextSize * barrels;
          const nextPages = Math.max(1, Math.ceil(records.length / nextBarrelSize));
          const nextPage = Math.max(0, Math.min(Math.floor(anchor / nextBarrelSize), nextPages - 1));
          change("resize", {page: nextPage, pageSize: nextSize});
        },
      });
    }
    return root;
  };

  const shortReferenceName = source => {
    if (source.shortName) return source.shortName;
    if (String(source.name || "").toLocaleLowerCase() === "vanilla") return "V";
    const words = String(source.name || "").trim().split(/\s+/).filter(Boolean);
    if (words.length > 1) return words.map(word => word[0]).join("").slice(0, 3).toLocaleUpperCase();
    return String(source.name || "").slice(0, 5).toLocaleUpperCase();
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
      if (typeof value === "number") return formatNumber(value);
      if (typeof value === "string" && /^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value.trim())) return formatNumber(value);
      return String(value);
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
      const description = formatted instanceof Node ? formatted.textContent : String(formatted);
      return element("button", {
        type: "button",
        class: ["lex-reference-value", `lex-reference-slot-${source.referenceIndex}`, source.className || ""].filter(Boolean).join(" "),
        "data-reference-index": String(source.referenceIndex),
        title: `Use ${source.name}: ${description}`,
        onclick: event => options.apply?.(clone(source.value), event, source),
      },
      element("span", {class: "lex-reference-tag"}, shortReferenceName(source)),
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
    const root = element("div", {
      class: ["lex-source-control", options.internal ? "lex-source-control-internal" : ""].filter(Boolean).join(" "),
    }, options.control);
    const referenceCharacters = Math.max(1, ...sources.map(source => {
      const formatted = (options.format || (value => typeof value === "number" ? formatNumber(value) : String(value ?? "")))(source.value, source);
      const value = formatted instanceof Node ? formatted.textContent : String(formatted);
      return shortReferenceName(source).length + value.length + 1;
    }));
    if (options.internal) {
      const reserve = Math.max(2.15, Math.min(6.25, referenceCharacters * .38 + .35));
      root.style.setProperty("--lex-internal-reference-width", `${reserve}em`);
    } else {
      const reserve = Math.max(2.35, Math.min(6.25, referenceCharacters * .44 + .45));
      // Sizing the rail per control makes value boxes on the same panel end
      // at different edges, because one reference reading "V25" needs less
      // room than one reading "R130". The requirement is recorded here and a
      // single widest value is applied across the panel below.
      root.dataset.lexRailWidth = String(reserve);
      root.style.setProperty("--lex-reference-rail-width", `${reserve}em`);
    }
    const currentValue = () => typeof options.current === "function" ? options.current() : options.current;
    root.lexVanillaValue = () => options.vanilla;
    root.lexRevert = event => {
      const reference = root.querySelector(".lex-reference-values .lex-reference-value button");
      if (reference) { reference.click(); return true; }
      options.apply?.(options.vanilla, event, sources[0]);
      refresh();
      return true;
    };
    const refresh = () => {
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
      root.classList.toggle("no-reference", !reference);
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
    const icon = normalized === "partial"
      ? element("span", {class: "lex-mixture-mark", "aria-hidden": "true"})
      : element("span", {class: "lex-status-mark lex-ui-symbol", "aria-hidden": "true"}, normalized === "integrated" ? "✓" : "×");
    return element("span", {
      class: `lex-integration-status ${normalized}`,
      title: labels[normalized],
      "aria-label": labels[normalized],
    }, icon);
  };

  const dataMap = options => {
    const query = String(options.query || "").trim().toLocaleLowerCase();
    const wantedStatus = options.status || "";
    const searchFields = ["filename", "controls", "notes"];
    let filtered = options.rows.filter(row => {
      if (wantedStatus && row.status !== wantedStatus) return false;
      return !query || searchFields.some(field => String(row[field] || "").toLocaleLowerCase().includes(query));
    });
    const [sortKey, sortDirection] = options.sort || ["filename", 1];
    const statusRank = {integrated: 0, partial: 1, "not-integrated": 2};
    filtered = [...filtered].sort((left, right) => {
      const a = sortKey === "status" ? statusRank[left.status] : left[sortKey];
      const b = sortKey === "status" ? statusRank[right.status] : right[sortKey];
      return sortDirection * String(a ?? "").localeCompare(String(b ?? ""), undefined, {numeric: true});
    });
    const pageSize = options.pageSize || 100;
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const page = Math.max(0, Math.min(options.page || 0, pages - 1));
    const shown = filtered.slice(page * pageSize, (page + 1) * pageSize);
    const statusFilter = element("select", {
      "aria-label": "Filter files by integration status",
      onchange: event => options.changeStatus(event.target.value),
    },
        ...[["", "All statuses"], ["integrated", "Integrated"], ["partial", "Partial"],
          ["not-integrated", "Not integrated"]].map(([value, label]) => {
            const choice = element("option", {value}, label);
            if (value === wantedStatus) choice.selected = true;
            return choice;
          }));
    const table = columnList({
      rows: shown,
      key: row => row.filename,
      class: "lex-data-map-table",
      template: "minmax(180px,25fr) minmax(240px,33fr) minmax(240px,34fr) minmax(72px,8fr)",
      sortState: {key: sortKey, dir: sortDirection},
      columns: [
        {key: "filename", label: "Filename", sortable: true, align:"start", render: row => element("span", {class:"lex-data-map-file"},
          element("button", {class:"lex-data-map-location", type:"button", title:`Open original file location: ${row.filename}`, "aria-label":`Open original file location: ${row.filename}`,
            onclick: async event => {event.stopPropagation();try {const opened=await callWindow("open_game_data_location", document.body.dataset.lexPlugin, row.filename);if(opened===false)throw new Error("Open this page in the desktop editor to reveal original files.")} catch(error) {showToast(error.message || String(error), true)}}}, folderIcon()),
          row.openable && options.open
            ? element("button", {class: "lex-data-map-link", title: row.openLabel || "Open this file's editor", onclick: () => options.open(row)}, row.filename)
            : element("code", {}, row.filename))},
        {key: "controls", label: "What it controls", sortable: true, align:"start"},
        {key: "notes", label: "Notes", sortable: true, align:"start", cellClass:"lex-data-map-notes"},
        {key: "status", label: "Status", sortable: true, render: row => integrationStatus(row.status)},
      ],
      sort: options.changeSort,
    });
    const commandBar = pager({page, pages, total: filtered.length, pageSize, noun: "files",
      change: options.changePage,
      search: {key: options.searchKey || "data-map", value: options.query || "",
        placeholder: "Search filenames, systems, or notes…", label: "Search the data map",
        change: options.changeQuery},
      filters: [statusFilter]});
    const content = element("div", {class: "lex-data-map-view"}, table, commandBar);
    return {controls: [], content, page, pages, filtered};
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
    const sections = config.sections.map(section => {
      const fields = section.fields.map(field => {
        const searchText = `${section.label} ${field.label} ${field.key} ${field.description}`.toLocaleLowerCase();
        const node = detailField({
          className: "lex-platform-config-field", label: field.label.toLocaleUpperCase(),
          help: field.description ? infoHelp(field.description) : null,
          dataType: field.kind === "boolean" ? "BOOL" : field.kind === "integer" || field.kind === "enum" ? "INT" : field.kind === "number" ? "FLOAT" : field.kind === "list" ? "LIST" : "STRING",
          min: field.minimum, max: field.maximum, control: controlFor(field),
        });
        node.dataset.platformSearch = searchText;
        node.hidden = !!query && !searchText.includes(query);
        return node;
      });
      const sectionNode = element("details", {class: "lex-platform-config-section", open: true},
        element("summary", {}, section.label),
        element("div", {class: "lex-platform-config-fields"}, ...fields));
      sectionNode.hidden = fields.every(field => field.hidden);
      return sectionNode;
    });
    const fieldCount = config.sections.reduce((total, section) => total + section.fields.length, 0);
    const applySearch = value => {
      options.search(value);
      const normalized = String(value).toLocaleLowerCase();
      const root = document.querySelector(".lex-platform-config");
      if (!root) return;
      for (const section of root.querySelectorAll(".lex-platform-config-section")) {
        const fields = [...section.querySelectorAll(".lex-platform-config-field")];
        for (const field of fields) field.hidden = !!normalized && !field.dataset.platformSearch.includes(normalized);
        section.hidden = fields.every(field => field.hidden);
      }
    };
    const commandBar = pager({
      page:0, pages:1, total:fieldCount, pageSize:Math.max(1,fieldCount), noun:"settings",
      search:{key:`platform-${config.runtime || "settings"}`,value:options.query || "",label:`Search ${config.runtime} settings`,change:applySearch},
    });
    return element("section", {class: "lex-platform-config"},
      options.showHeader === false ? null : element("header", {class: "lex-platform-config-head"},
        element("div", {}, element("h2", {}, `${config.runtime} settings`), element("p", {}, config.message), element("code", {}, config.path))),
      element("div", {class: "lex-platform-config-sections"}, ...sections), commandBar)
  };

  window.LexeditorUI = {element, el: element, newButton, infoHelp, unitField, readonlyField, formatNumber, numberValue, magnitudeValue, recordId, detailPanel, tabbedPanel, detailSection, detailField, detailGroup, detailRow, multiNumberRow, subtabBar, toggleRow, autoFitControlText, showToast, copyText, curveEditor, refreshReferences, closeButton, hoverable, settingsIcon, infoIcon, folderIcon, searchIcon, saveIcon, settingsSaveControl, bottomSearch, beginSearcher, finishSearcher, decorateSearchCandidate, openGameFolder, finishPluginLoading, configureThemeSounds, playThemeSound, sharedSettings, soundCoverageTable, clone, applyTheme, EditHistory, NavigationHistory, installBrowserHistoryGuard, installExtendedMouseHistory, bindSettingDependencies, showAlert, confirmUnsavedExit, confirmDiscardChanges, createWindowActions, installWindowFrame, openSettings, mountShell, list, columnList, columnPreferences, hasEnabledProperty, panelLayout, listDetail, masterDetail, fitListPage, pagedListDetail, pager, referenceDisplay, provenanceControl, booleanMark, enabledMark, integrationStatus, dataMap, platformConfigView};
})();
