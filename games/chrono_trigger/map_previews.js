"use strict";

(() => {
  const style = document.createElement("style");
  style.textContent = `
    .ct-raster-wrap{overflow:auto;max-height:62vh;border:1px solid var(--lex-border);background:var(--lex-bg)}
    .ct-raster-image{display:block;image-rendering:pixelated;max-width:none}
    .ct-raster-policy{margin-top:10px}
    .ct-render-diagnostics{margin:0 0 10px;border:1px solid var(--lex-border);background:var(--lex-bg)}
    .ct-render-diagnostics>summary{padding:8px 10px;cursor:pointer;font-weight:600}
    .ct-render-diag-grid{display:grid;grid-template-columns:minmax(130px,190px) 1fr;gap:5px 10px;padding:8px 10px;border-top:1px solid var(--lex-border);font-size:.88em}
    .ct-render-diag-grid strong{color:var(--lex-muted);font-weight:500}
    .ct-animation-table{font-size:.84em;border-top:1px solid var(--lex-border)}
  `;
  document.head.append(style);

  if (!Number.isInteger(state.worlds.mapLayer)) state.worlds.mapLayer = 1;

  function rasterNode(url, alt, policy) {
    const wrap = el("div", {class: "ct-raster-wrap"});
    const image = el("img", {class: "ct-raster-image", src: url, alt, draggable: false});
    image.addEventListener("error", () => {
      wrap.replaceChildren(el("div", {class: "ct-warning"},
        "Raster preview could not be rendered from the selected source. The current PC resources may be missing, truncated, or use a layout this renderer intentionally does not guess."));
    }, {once: true});
    wrap.append(image);
    return el("div", {}, wrap, el("div", {class: "ct-table-note ct-raster-policy"}, policy));
  }

  const layerNames = {layer1: "L1", layer2: "L2", layer3: "L3", sprites: "sprites"};
  function enabledNames(flags) {
    const names = Object.entries(flags || {}).filter(([, enabled]) => enabled).map(([name]) => layerNames[name] || name);
    return names.length ? names.join(", ") : "none";
  }

  function sceneDiagnostics(data) {
    const composition = data.compositionBits || {};
    const screen = composition.screen || {};
    const effects = composition.effects || {};
    const animations = data.chipAnimations || {};
    const animationSummary = animations.present
      ? `${animations.decodedAnimationCount ?? 0}/${animations.declaredAnimationCount ?? 0} BGAnime records`
      : "no BGAnime descriptor";
    const effectExtras = [
      effects.defaultColor ? "default-color" : null,
      effects.halfIntensity ? "half-intensity" : null,
      effects.subtract ? "subtract" : null,
      effects.unknown08 ? "unknown-0x08" : null,
    ].filter(Boolean);
    const details = el("details", {class: "ct-render-diagnostics"},
      el("summary", {}, `Render diagnostics · ${animationSummary}`),
      el("div", {class: "ct-render-diag-grid"},
        el("strong", {}, "MapTable screen bits"),
        el("span", {}, `main: ${enabledNames(screen.main)} · sub: ${enabledNames(screen.sub)}`),
        el("strong", {}, "MapTable effect bits"),
        el("span", {}, `targets: ${enabledNames(effects.targets)}${effectExtras.length ? ` · ${effectExtras.join(", ")}` : ""}`),
        el("strong", {}, "PrioMap"),
        el("span", {}, data.layerPriorities ? `${data.layerPriorities.join(" / ")} · raw PC bytes; semantics unknown` : "not present"),
        el("strong", {}, "Chip animation"),
        el("span", {}, animations.present
          ? `${animations.path} · descriptor decoded read-only; runtime phase/initial frame not inferred`
          : `${animations.path || "BGAnime"} · descriptor not present`),
      ),
    );
    if (animations.valid === false) {
      details.append(el("div", {class: "ct-warning"}, `BGAnime diagnostics stopped safely: ${animations.error || "invalid descriptor"}`));
    } else if (animations.present && Array.isArray(animations.animations) && animations.animations.length) {
      const visible = animations.animations.slice(0, 32);
      details.append(el("table", {class: "ct-animation-table"},
        el("thead", {}, el("tr", {}, el("th", {}, "Animation"), el("th", {}, "Destination"), el("th", {}, "Frames"))),
        el("tbody", {}, ...visible.map(animation => el("tr", {},
          el("td", {class: "ct-number"}, String(animation.index)),
          el("td", {class: "ct-mono"}, `chips ${animation.destinationChipRange?.join("–") || "?"}`),
          el("td", {}, ...(animation.frames || []).map((frame, index) => el("span", {},
            `${index ? " · " : ""}src ${frame.sourceChipRange?.join("–") || "?"}, ` +
            `${frame.durationTicks == null ? `raw 0x${Number(frame.durationRaw || 0).toString(16).padStart(2, "0")}` : `${frame.durationTicks} ticks`}`
          ))),
        ))),
      ));
      if (animations.animations.length > visible.length) {
        details.append(el("div", {class: "ct-table-note"}, `${animations.animations.length - visible.length} additional animation records omitted from this compact view.`));
      }
    }
    details.append(el("div", {class: "ct-table-note"},
      "These are PC resource bit/record diagnostics only. Lexeditor still does not emulate animation playback, main/sub-screen blending, or PrioMap render ordering."));
    return details;
  }

  function sceneRasterPanel(data, layer) {
    const layerData = data.layers[`layer${layer}`];
    const width = Number(layerData.width) * 16;
    const height = Number(layerData.height) * 16;
    const url = `/api/scene-raster?${new URLSearchParams({
      scene: String(state.scenes.selected), layer: String(layer), source: state.source,
    })}`;
    const limitation = layer === 3
      ? "Color-zero transparency is preserved; main/sub-screen blend/priority composition is not emulated."
      : "Color-zero transparency is preserved; animated chips are decoded as diagnostics but not played, and main/sub-screen blend/priority composition is not emulated.";
    return rasterNode(
      url,
      `Chrono Trigger scene ${state.scenes.selected} rendered layer ${layer}`,
      `Actual PC L${layer} raster · ${width}×${height}px · isolated layer only. ${limitation}`,
    );
  }

  mapPanel = function () {
    const data = state.scenes.map;
    if (!data) return el("div", {class: "ct-empty"}, "Loading scene map layout…");
    const modes = [
      ["raster1", "Rendered L1"], ["raster2", "Rendered L2"], ["raster3", "Rendered L3"],
      ["collision", "Collision"], ["layer1", "L1 tile IDs"], ["layer2", "L2 tile IDs"],
      ["layer3", "L3 tile IDs"],
    ].filter(([id]) => !["raster3", "layer3"].includes(id) || data.layers.layer3.enabled);
    const selected = modes.some(([id]) => id === state.scenes.mapMode) ? state.scenes.mapMode : modes[0][0];
    if (selected !== state.scenes.mapMode) state.scenes.mapMode = selected;
    const select = el("select", {value: selected, onchange: event => {
      state.scenes.mapMode = event.target.value;
      render();
    }}, ...modes.map(([id, label]) => {
      const option = el("option", {value: id}, label);
      option.selected = id === selected;
      return option;
    }));
    const controls = el("div", {class: "ct-map-controls"},
      el("strong", {}, `${data.sceneWidth}×${data.sceneHeight} map tiles`), select,
      el("span", {}, `MapTable ${data.mapId} · L2 scroll ${data.header.scrollLayer2.xPixelsPerSecond}, ${data.header.scrollLayer2.yPixelsPerSecond} px/s`),
      data.layerPriorities ? el("span", {}, `PrioMap ${data.layerPriorities.join("/")} (raw)`) : null,
    );
    const diagnostics = sceneDiagnostics(data);
    if (selected.startsWith("raster")) {
      const layer = Number(selected.slice("raster".length));
      return el("div", {class: "ct-map-panel"}, controls, diagnostics, sceneRasterPanel(data, layer));
    }
    const collision = el("div", {class: "ct-collision-summary"},
      ...Object.entries(data.collisionCounts).sort((a, b) => b[1] - a[1])
        .map(([name, count]) => el("span", {class: "ct-collision-chip"}, `${name}: ${count}`)));
    return el("div", {class: "ct-map-panel"}, controls, diagnostics,
      el("div", {class: "ct-map-canvas-wrap"}, mapCanvas(data, selected)),
      selected === "collision" ? collision : null,
      el("div", {class: "ct-table-note"},
        `Structural view from ${data.path}. Property stream: ${data.propertyStats.encodedRecords} encoded records → ` +
        `${data.propertyStats.expected} cells${data.propertyStats.padded ? `, padded ${data.propertyStats.padded}` : ""}` +
        `${data.propertyStats.trimmed ? `, trimmed ${data.propertyStats.trimmed}` : ""}.`));
  };

  function worldMapPanel(row) {
    const layer = state.worlds.mapLayer === 2 ? 2 : 1;
    const select = el("select", {value: String(layer), onchange: event => {
      state.worlds.mapLayer = Number(event.target.value) === 2 ? 2 : 1;
      render();
    }}, el("option", {value: "1"}, "Rendered L1"), el("option", {value: "2"}, "Rendered L2"));
    select.value = String(layer);
    const url = `/api/world-raster?${new URLSearchParams({
      world: String(row.id), layer: String(layer), source: state.source,
    })}`;
    return el("div", {class: "ct-map-panel"},
      el("div", {class: "ct-map-controls"}, el("strong", {}, "96×64 map tiles"), select,
        el("span", {}, `Map ${row.values.map} · Palette ${row.values.palette} · Assembly ${row.values.assemblyL12}`)),
      rasterNode(
        url,
        `${row.name} rendered overworld layer ${layer}`,
        `Actual PC overworld L${layer} raster · 1536×1024px · isolated layer only. ` +
        "Color-zero transparency is preserved; this view does not claim main/sub-screen composition or animation emulation.",
      ));
  }

  worldsView = function () {
    const data = state.worlds.data;
    if (!data) return el("div", {class: "ct-view"}, errorNode() || el("div", {class: "ct-empty"}, "Loading overworld headers…"));
    const list = el("div", {class: "ct-list"});
    for (const row of data.rows) {
      list.append(el("button", {
        type: "button", class: `ct-list-row${row.id === state.worlds.selected ? " active" : ""}`,
        onclick: () => selectWorld(row.id),
      }, el("span", {class: "ct-list-id"}, String(row.id)), el("span", {}, row.name), sourceBadge(row.source)));
    }
    const row = data.rows.find(value => value.id === state.worlds.selected);
    let detail = el("div", {class: "ct-detail"}, el("div", {class: "ct-empty"}, "No world selected."));
    if (row) {
      const section = state.worlds.section;
      const tabsNode = el("div", {class: "ct-section-tabs"},
        ...[["header", "Header"], ["map", "Map"], ["navigation", "Exits / Triggers"], ["script", "Script"]]
          .map(([id, label]) => el("button", {type: "button", class: id === section ? "active" : "",
            onclick: () => selectWorldSection(id)}, label)));
      const body = section === "map" ? worldMapPanel(row)
        : section === "navigation" ? worldNavigationPanel()
        : section === "script" ? worldScriptPanel() : worldHeaderPanel(row, data);
      detail = el("div", {class: "ct-detail"}, el("h2", {}, `${row.name} · World ${row.id}`), tabsNode, body);
    }
    return el("div", {class: "ct-view"},
      el("div", {class: "ct-summary"}, el("span", {}, el("strong", {}, String(data.rows.length)), " overworld headers"),
        data.labelLanguage ? el("span", {}, `Labels: ${data.labelLanguage}`) : null,
        el("span", {}, "Fixed editors + isolated PC raster previews + fail-closed script disassembly"),
        worldChanges().length + worldTableDirty() ? el("span", {},
          el("strong", {}, String(worldChanges().length + worldTableDirty())), " edited world records") : null),
      errorNode(), el("div", {class: "ct-split"}, list, detail));
  };
})();
