"use strict";
/* Opt-in, in-memory review surface for #99 and #299. No game data or settings writes. */
(() => {
  const el = (...args) => window.LexeditorUI.el(...args);
  const samples = [
    {id: 0, name: "Example Potion", value: 25},
    {id: 1, name: "Example Sword", value: 150},
    {id: 2, name: "Example Shield", value: 90},
  ];
  const choices = (label, entries, value, change) => {
    const control = el("select", {"aria-label": label, title: label, onchange: e => change(e.target.value)},
      ...entries.map(([id, text]) => el("option", {value: id, selected: id === value}, text)));
    return el("label", {class: "lex-review-choice"}, el("span", {}, label), control);
  };
  function shellProposal() {
    let mode = "tabs", selected = 0, previewOpen = true;
    const root = el("section", {class: "lex-review-section"});
    const status = el("p", {role: "status", class: "lex-review-status"});
    const canvas = el("div", {class: "lex-review-shell"});
    const button = (text, help, className = "") => el("button", {type: "button", class: className,
      title: help, "aria-label": help, onclick: () => { status.textContent = `${help} — preview only; no application action is executed.`; }}, text);
    function render() {
      const record = samples[selected];
      canvas.dataset.layout = mode;
      const utilities = el("div", {class: "lex-review-utilities", "aria-label": "Utility and window positions"},
        button("?", "Help", "lex-review-circle"), button("i", "Information", "lex-review-circle"),
        button("⚙", "Settings", "lex-review-circle"), button("−", "Minimize"), button("□", "Maximize"), button("×", "Close"));
      const titlebar = el("div", {class: "lex-review-titlebar"}, el("strong", {}, "LEXEDITOR"), utilities);
      const project = choices("Mod", [["example", "My Example Mod"]], "example", () => {});
      const commands = el("div", {class: "lex-review-commands"}, button("↶", "Undo"), button("↷", "Redo"), button("Save", "Save this mod"), button("▶ Play", "Play this mod"));
      const tabs = el("div", {class: "lex-review-nav", "aria-label": "Proposed section navigation"},
        ...["Characters", "Items", "Shops", "Tweaks"].map(name => button(name, `${name} tab preview`)));
      const commandbar = el("div", {class: "lex-review-commandbar"}, project, commands);
      const list = el("section", {class: "lex-review-list", "aria-label": "Example records"}, el("h4", {}, "Items"),
        ...samples.map(row => el("button", {type: "button", title: `Select ${row.name}`, "aria-pressed": row.id === selected,
          onclick: () => { selected = row.id; render(); }}, el("span", {class: "lex-review-id"}, `${row.id}`), row.name)));
      const toggle = el("button", {type: "button", "aria-expanded": previewOpen,
        title: "Show or hide only this mock 3D preview; it does not change editor settings.",
        onclick: () => { previewOpen = !previewOpen; render(); }}, previewOpen ? "Hide preview" : "Show preview");
      const identity = el("div", {class: "lex-review-identity"}, el("h4", {}, record.name), toggle);
      const preview = el("aside", {class: "lex-review-model", hidden: !previewOpen, "aria-label": "Proposed 3D preview location"},
        el("strong", {}, "3D preview"), el("p", {}, "A real game's model would appear here. This is a layout placeholder, not a model renderer."));
      const details = el("section", {class: "lex-review-details", "aria-label": "Editable-detail space"}, identity,
        el("label", {}, "Name", el("input", {value: record.name, title: "Edit the preview item name.", "aria-label": "Preview item name", oninput: () => { status.textContent = "In-memory layout example only. This field does not edit a game or saved mod."; }})),
        el("label", {}, "Buy price", el("input", {type: "number", min: 0, max: 65535, step: 1, value: record.value, title: "Set the preview buy price from 0 to 65535.", "aria-label": "Preview buy price"})),
        el("p", {}, "The selected record's properties stay together here."));
      const editorBody = el("div", {class: "lex-review-body"}, list, details);
      let workspace;
      if (mode === "tabs") {
        const tabRow = el("div", {class: "lex-review-tab-command-row"}, tabs, commandbar);
        details.append(preview);
        workspace = el("div", {class: "lex-review-workspace"}, tabRow, editorBody);
        canvas.replaceChildren(titlebar, workspace);
        status.textContent = "C · Tab-first compact header: the familiar section tabs stay horizontal and primary. Mod, Undo/Redo, Save and Play share their row; the optional 3D preview is a drawer inside the detail pane.";
      } else {
        const rail = el("aside", {class: "lex-review-side-rail", "aria-label": "Vertical workspace navigation"}, tabs, project);
        const content = el("div", {class: "lex-review-rail-content"}, commandbar, editorBody);
        if (previewOpen) content.append(preview);
        workspace = el("div", {class: "lex-review-workspace lex-review-workspace-rail"}, rail, content);
        canvas.replaceChildren(titlebar, workspace);
        status.textContent = "D · Vertical workspace rail: section navigation and the mod selector move off the menu bar. Undo/Redo/Save/Play stay directly above the editor; the 3D preview is a collapsible right/bottom drawer.";
      }
    }
    root.append(el("h3", {}, "Shared layout alternatives"),
      el("p", {}, "The two earlier menu-bar proposals were rejected. These are new alternatives; the production menu remains unchanged."),
      choices("Layout proposal", [["tabs", "C · Tab-first compact header"], ["rail", "D · Vertical workspace rail"]], mode, value => { mode = value; render(); }), canvas, status);
    render(); return root;
  }
  function formulaProposal() {
    let a = 1, x = 45;
    const root = el("section", {class: "lex-review-section"});
    const ns = "http://www.w3.org/2000/svg";
    const svgEl = (tag, attrs = {}) => { const node = document.createElementNS(ns, tag); for (const [key, val] of Object.entries(attrs)) node.setAttribute(key, val); return node; };
    const svg = svgEl("svg", {viewBox: "0 0 640 300", role: "img", "aria-label": "Approved graph design A on an example quadratic curve"});
    const axes = svgEl("path", {d: "M32 16 V270 H610", class: "lex-review-axes"});
    const path = svgEl("path", {class: "lex-review-curve"});
    svg.append(axes, path);
    const plot = el("div", {class: "lex-review-plot"}, svg);
    const label = el("div", {class: "lex-review-formula"});
    const minimum = el("span", {class: "lex-review-extremum lex-review-min"});
    const maximum = el("span", {class: "lex-review-extremum lex-review-max"});
    plot.append(label, minimum, maximum);
    function refresh() {
      const point = n => ({x: 32 + n / 100 * 576, y: 270 - a * n * n / 100 / 200 * 230});
      path.setAttribute("d", Array.from({length: 101}, (_, i) => { const p = point(i); return `${i ? "L" : "M"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`; }).join(" "));
      const p = point(x), slope = -(2 * a * x / 100 / 200 * 230) / (576 / 100);
      const angle = Math.atan(slope) * 180 / Math.PI;
      const square = () => el("span", {}, "L", el("sup", {}, "2"));
      const expression = el("span", {class: "lex-review-fraction"}, el("span", {}, "A × ", square()), el("span", {}, "100"));
      label.replaceChildren(el("span", {}, "Value = "), expression);
      label.setAttribute("aria-label", `Value equals A times level squared divided by 100. A is ${a}.`);
      label.style.left = `${p.x / 640 * 100}%`; label.style.top = `${p.y / 300 * 100}%`;
      label.style.transform = `translate(-50%, calc(-100% - 8px)) rotate(${angle}deg)`;
      minimum.textContent = "min 0"; maximum.textContent = `max ${a * 100}`;
    }
    const slider = (name, min, max, step, value, update) => {
      const output = el("output", {}, String(value));
      const input = el("input", {type: "range", min, max, step, value, title: `${name}: ${min} to ${max}.`, "aria-label": name,
        oninput: e => { const n = Number(e.target.value); output.textContent = String(n); update(n); refresh(); }});
      return el("label", {class: "lex-review-slider"}, name, input, output);
    };
    root.append(el("h3", {}, "Approved graph design A"),
      el("p", {}, "Design A is settled: natural weight and shadow, transparent background, curve-following placement, raised powers, stacked fractions, and matching minimum/maximum labels. This review only exercises position and scale; there is no remaining A/B choice."),
      el("div", {class: "lex-review-graph-controls"}, slider("Multiplier A", .5, 2, .1, a, value => { a = value; }), slider("Label position along curve", 25, 65, 1, x, value => { x = value; })),
      plot, el("p", {}, "The shared production curve editor uses the approved treatment and keeps formula backgrounds transparent."));
    refresh(); return root;
  }
  window.LexeditorDesignReview = {render: () => el("div", {class: "lex-design-review"},
    el("h2", {}, "Design review"), el("p", {}, "In-memory review controls only: no preferences are saved, no game launches, and no game/mod data changes."), shellProposal(), formulaProposal())};
})();
