"use strict";

// Keep the menu document alive. Only the editor frame enters and leaves it.
(() => {
  let frame = null;
  let origin = null;
  let opening = null;
  let leaving = false;
  const menu = () => document.querySelector("#chooser-surface");
  const paint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const send = message => frame?.contentWindow.postMessage(message, origin);
  const slide = async entering => {
    const nodes = [menu(), frame];
    nodes.forEach(node => { node.inert = true; });
    const positions = entering ? [["0%", "-100%"], ["100%", "0%"]] : [["-100%", "0%"], ["0%", "100%"]];
    const animations = nodes.map((node, index) => node.animate(
      positions[index].map(x => ({transform: `translateX(${x})`})),
      {duration: 300, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards"}));
    await Promise.all(animations.map(animation => animation.finished));
    nodes.forEach((node, index) => { node.style.transform = `translateX(${positions[index][1]})`; });
    animations.forEach(animation => animation.cancel());
    nodes[entering ? 1 : 0].inert = false;
  };

  async function home() {
    if (leaving || !frame) return {hostNavigates: true};
    leaving = true;
    try {
      await window.pywebview.api.set_dirty_count(0);
      await window.__lexChooser.load();
      await Promise.all([...menu().querySelectorAll("img")].map(image => image.decode().catch(() => {})));
      await slide(false);
      const old = frame;
      frame = null;
      // Resolve the child's bridge call before releasing its document.
      setTimeout(() => old.remove(), 0);
      document.querySelector("#resident-handle")?.focus();
      return {hostNavigates: true};
    } finally { leaving = false; }
  }

  addEventListener("message", async event => {
    if (!frame || event.source !== frame.contentWindow || event.origin !== origin) return;
    const message = event.data;
    if (message?.type !== "lexeditor-host-call") return;
    const source = event.source;
    try {
      let result;
      if (message.method === "editor_ready") {
        if (opening) {
          await document.fonts.ready;
          await paint();
          await slide(true);
          menu().inert = true;
          frame.focus();
          opening.resolve();
          opening = null;
        }
        result = true;
      } else if (message.method === "return_to_main_menu") {
        result = await home();
      } else {
        const method = window.pywebview?.api?.[message.method];
        if (typeof method !== "function" || message.method.startsWith("_")) throw new Error("Unknown host action");
        result = await method(...message.args);
        // Restart can change the service port before the frame navigates.
        if (message.method === "restart_plugin" && result?.url) origin = new URL(result.url).origin;
      }
      source.postMessage({type: "lexeditor-host-result", id: message.id, result}, event.origin);
    } catch (error) {
      source.postMessage({type: "lexeditor-host-result", id: message.id, error: String(error.message || error)}, event.origin);
    }
  });

  window.LexeditorHost = {
    async open(url) {
      if (frame || opening) return;
      const destination = new URL(url);
      // The parent owns the slide; the child still owns its loading message.
      origin = destination.origin;
      frame = document.createElement("iframe");
      frame.id = "lexeditor-editor";
      frame.name = "lexeditor-editor";
      frame.title = "Game editor";
      frame.style.cssText = "position:fixed;inset:0;width:100%;height:100%;border:0;z-index:85;transform:translateX(100%);background:var(--lex-bg)";
      const ready = new Promise((resolve, reject) => { opening = {resolve, reject}; });
      frame.src = destination.href;
      document.body.append(frame);
      const timeout = setTimeout(() => opening?.reject(new Error("The editor did not finish loading. Try opening it again.")), 120000);
      try {
        await ready;
      } catch (error) {
        frame?.remove();
        frame = null;
        opening = null;
        menu().style.transform = "none";
        menu().inert = false;
        throw error;
      } finally { clearTimeout(timeout); }
    },
    installCallbacks() {
      for (const name of ["__lexeditorRequestWindowClose", "__lexeditorNavigateHistory", "__lexeditorApplyWindowState"]) {
        const original = window[name];
        window[name] = (...args) => {
          if (frame) send({type: "lexeditor-host-event", name, args});
          else original?.(...args);
        };
      }
    },
  };
})();
