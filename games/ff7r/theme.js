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

  let bitmapState = null;
  let bitmapObserver = null;

  const loadImage = url => new Promise((resolve, reject) => {
    const image = new Image();
    image.decoding = "async";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("FF7R bitmap font atlas did not load"));
    image.src = url;
  });

  function measureLabel(label, glyphs) {
    let pen = 0;
    let minX = 0;
    let maxX = 0;
    let minY = 0;
    let maxY = 0;
    const rows = [];
    for (const character of [...label]) {
      const codepoint = character.codePointAt(0);
      const glyph = glyphs.get(codepoint);
      if (!glyph) return null;
      const left = pen + Number(glyph.xOffset || 0);
      const top = Number(glyph.yOffset || 0);
      const width = Number(glyph.width || 0);
      const height = Number(glyph.height || 0);
      minX = Math.min(minX, left);
      maxX = Math.max(maxX, left + width);
      minY = Math.min(minY, top);
      maxY = Math.max(maxY, top + height);
      rows.push({glyph, pen});
      pen += Number(glyph.xAdvance || width);
      maxX = Math.max(maxX, pen);
    }
    return {rows, minX, maxX, minY, maxY, advance: pen};
  }

  function bitmapize(node) {
    if (!bitmapState || !(node instanceof Element)) return false;
    const stored = node.dataset.lexFf7rBitmapLabel;
    const label = String(stored || node.textContent || "").replace(/\s+/g, " ").trim();
    if (!label) return false;
    if (stored && node.querySelector(":scope > canvas.ff7r-bitmap-label")) return true;
    const measured = measureLabel(label, bitmapState.glyphs);
    if (!measured) return false;

    const computed = getComputedStyle(node);
    const cssFontSize = Math.max(9, Number.parseFloat(computed.fontSize) || 15);
    const sourceFontSize = Math.max(1, Number(bitmapState.fontSize) || 1);
    const scale = cssFontSize / sourceFontSize;
    const width = Math.max(1, Math.ceil((measured.maxX - measured.minX) * scale));
    const height = Math.max(1, Math.ceil((measured.maxY - measured.minY) * scale));
    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    const canvas = document.createElement("canvas");
    canvas.className = "ff7r-bitmap-label";
    canvas.setAttribute("aria-hidden", "true");
    canvas.width = Math.ceil(width * dpr);
    canvas.height = Math.ceil(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const context = canvas.getContext("2d", {alpha: true});
    if (!context) return false;
    context.imageSmoothingEnabled = true;
    context.setTransform(scale * dpr, 0, 0, scale * dpr, 0, 0);

    for (const {glyph, pen} of measured.rows) {
      const glyphWidth = Number(glyph.width || 0);
      const glyphHeight = Number(glyph.height || 0);
      if (!glyphWidth || !glyphHeight) continue;
      context.drawImage(
        bitmapState.image,
        Number(glyph.x), Number(glyph.y), glyphWidth, glyphHeight,
        pen + Number(glyph.xOffset || 0) - measured.minX,
        Number(glyph.yOffset || 0) - measured.minY,
        glyphWidth, glyphHeight
      );
    }

    node.dataset.lexFf7rBitmapLabel = label;
    if (!node.getAttribute("aria-label")) node.setAttribute("aria-label", label);
    node.replaceChildren(canvas);
    node.classList.add("ff7r-bitmapized");
    return true;
  }

  function bitmapizeDocument() {
    if (!bitmapState) return;
    document.querySelectorAll("#lexeditor-shell button[data-tab], .lex-detail-panel-title")
      .forEach(bitmapize);
  }

  async function installBitmapFont(font) {
    if (!font?.available || !font.atlasUrl || !Array.isArray(font.glyphs) || !font.glyphs.length) return false;
    const image = await loadImage(font.atlasUrl);
    bitmapState = {
      image,
      fontSize: Number(font.fontSize) || 1,
      glyphs: new Map(font.glyphs.map(glyph => [Number(glyph.codepoint), glyph]))
    };
    document.documentElement.dataset.lexFf7rBitmapFont = "installed";
    bitmapizeDocument();
    if (!bitmapObserver) {
      const main = document.querySelector("#main");
      if (main) {
        bitmapObserver = new MutationObserver(() => bitmapizeDocument());
        bitmapObserver.observe(main, {childList: true, subtree: true});
      }
    }
    return true;
  }

  function apply(payload = {}) {
    if (!window.LexeditorUI) return;
    LexeditorUI.applyTheme({...fallback, ...(payload.theme || {})});
    const rows = payload.sounds?.rows;
    LexeditorUI.configureThemeSounds(Array.isArray(rows) ? rows : []);
    document.documentElement.dataset.lexFf7rAssets = payload.assetMode === "installed" ? "installed" : "fallback";
    document.documentElement.dataset.lexFf7rCookedSources = String(payload.cookedSourceCount || 0);
    if (payload.bitmapFont?.sourceFound) document.documentElement.dataset.lexFf7rBitmapFont = "source";
    if (payload.bitmapFont?.available) installBitmapFont(payload.bitmapFont).catch(() => {});
  }

  // Paint the game-specific fallback synchronously. The local service then
  // upgrades it with browser-ready resources and decoded assets from this
  // installed copy of FF7R.
  apply();
  fetch("/api/theme?scan=1", {cache: "no-store"})
    .then(response => response.ok ? response.json() : Promise.reject(new Error(response.statusText)))
    .then(apply)
    .catch(() => apply());

  window.LexeditorFF7RTheme = Object.freeze({fallback, apply});
})();
