(() => {
  "use strict";

  const fallback = {
    bg: "#070b12",
    panel: "#0d1722f2",
    "panel-2": "#132334f2",
    border: "#456782",
    text: "#eef7ff",
    muted: "#91a7ba",
    accent: "#36b6ee",
    "accent-text": "#ffffff",
    highlight: "#88dcff",
    success: "#70d6b1",
    danger: "#ff6e76",
    font: '"Lex FF7R Local", Candara, "Segoe UI", system-ui, sans-serif',
    "heading-font": '"Lex FF7R Local", Candara, "Segoe UI", system-ui, sans-serif',
    radius: "1px",
    "panel-gap": "clamp(9px, .9vw, 14px)",
    "ff7r-background-image": "none",
    "ff7r-panel-image": "none"
  };

  function apply(payload = {}) {
    if (!window.LexeditorUI) return;
    LexeditorUI.applyTheme({...fallback, ...(payload.theme || {})});
    const rows = payload.sounds?.rows;
    LexeditorUI.configureThemeSounds(Array.isArray(rows) ? rows : []);
    document.documentElement.dataset.lexFf7rAssets = payload.assetMode === "installed" ? "installed" : "fallback";
    document.documentElement.dataset.lexFf7rCookedSources = String(payload.cookedSourceCount || 0);
  }

  // Paint the game-specific fallback synchronously. The local service then
  // upgrades it with browser-ready resources copied from the installed game.
  apply();
  fetch("/api/theme?scan=1", {cache: "no-store"})
    .then(response => response.ok ? response.json() : Promise.reject(new Error(response.statusText)))
    .then(apply)
    .catch(() => apply());

  window.LexeditorFF7RTheme = Object.freeze({fallback, apply});
})();
