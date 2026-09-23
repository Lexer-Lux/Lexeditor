"use strict";

const {
  el, actionRow, badge, columnList, columnPreferences, detailField, detailNote,
  detailPanel, detailSection, infoHelp, notice, pagedListDetail, panelLayout,
  readonlyField, toolbar, unitField, booleanMark,
} = LexeditorUI;

const KINDS = ["recipes", "items", "machines", "technologies"];
const LABELS = {
  recipes: "Recipes",
  items: "Items",
  machines: "Machines",
  technologies: "Technologies",
};
const state = {
  tab: "recipes",
  config: null,
  data: {recipes: [], items: [], machines: [], technologies: []},
  selected: {recipes: "", items: "", machines: "", technologies: ""},
  page: {recipes: 0, items: 0, machines: 0, technologies: 0},
  pageSize: {recipes: 15, items: 15, machines: 15, technologies: 15},
  query: {recipes: "", items: "", machines: "", technologies: ""},
  modOnly: {recipes: false, items: false, machines: false, technologies: false},
  sort: {
    recipes: {key: "name", dir: 1}, items: {key: "name", dir: 1},
    machines: {key: "name", dir: 1}, technologies: {key: "name", dir: 1},
  },
  datamap: null,
  map: {page: 0, query: "", status: "", sort: ["filename", 1]},
  exportResult: null,
  booting: true,
  error: "",
};

async function api(path, options) {
  const response = await fetch(path, options);
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}

const jsonPost = (path, value) => api(path, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(value),
});

const refreshShell = () => shell?.refresh?.();
const dirtyCount = () => Number(state.config?.dirty || 0);

function sourceReady() {
  return Boolean(state.config?.source?.ready);
}

function editingAllowed() {
  const config = state.config || {};
  const install = config.install || {};
  return !config.projectError && (!install.root || install.state === "supported");
}

function sourceState() {
  const source = state.config?.source || {};
  const message = source.error ||
    "Create a Factorio 2.1 data.raw JSON dump with the game's documented --dump-data command, then copy it into this project's source folder as data-raw-dump.json.";
  return detailPanel({className: "lex-information-panel",
    title: source.error ? "Prototype dump could not be read" : "Prototype dump required",
    body: [
      detailNote(message),
      detailNote("Lexeditor will not execute source-mod Lua. The dump stays read-only; edits are stored in overrides.json."),
      detailNote(source.path || "source/data-raw-dump.json"),
      actionRow(el("button", {type: "button", onclick: reopen}, "Reopen project"))]});
}

function errorState(message) {
  return detailPanel({className: "lex-information-panel", title: "Factorio editor error",
    body: [
      detailNote(message),
      actionRow(el("button", {type: "button", onclick: reopen}, "Reopen project"))]});
}

function loadingState(message = "Loading Factorio project…") {
  return detailPanel({className: "lex-information-panel", title: message,
    body: [detailNote("Reading the project through the Factorio plugin service.")]});
}

function inputNumber(value, options, change) {
  const input = el("input", {
    type: "number",
    value: value ?? "",
    step: options.step ?? "any",
    "aria-label": options.label,
    onchange: event => {
      if (event.target.value === "") {
        event.target.setCustomValidity("A numeric value is required.");
        event.target.reportValidity();
        return;
      }
      const number = Number(event.target.value);
      if (!Number.isFinite(number)) {
        event.target.setCustomValidity("Enter a finite number.");
        event.target.reportValidity();
        return;
      }
      const validation = typeof options.validate === "function" ? options.validate(number) : "";
      if (validation) {
        event.target.setCustomValidity(validation);
        event.target.reportValidity();
        return;
      }
      event.target.setCustomValidity("");
      void change(number);
    },
  });
  if (options.min !== undefined) input.min = String(options.min);
  if (options.max !== undefined) input.max = String(options.max);
  return options.unit ? unitField(input, options.unit) : input;
}

function referenceList(values, kind = "", empty = "None") {
  const list = Array.isArray(values) ? values : [];
  if (!list.length) return detailNote(empty);
  return toolbar(...list.map(value => {
    const label = typeof value === "string" ? value :
      `${value?.name || "?"}${value?.amount !== undefined ? ` × ${value.amount}` : ""}`;
    const name = typeof value === "string" ? value : value?.name;
    const canOpen = kind && name && state.data[kind]?.some(row => row.name === name);
    return canOpen
      ? el("button", {type: "button", title: `Open ${label}`, onclick: () => navigateTo(kind, name)}, label)
      : badge(label);
  }));
}

function prototypeIdentity(row) {
  return readonlyField(`${row.prototypeType} / ${row.name}`);
}

function rowChanges(kind, row) {
  if (kind === "recipes") return {
    enabled: Boolean(row.enabled),
    energy_required: Number(row.energyRequired),
    maximum_productivity: Number(row.maximumProductivity),
  };
  if (kind === "items") return {stack_size: Number(row.stackSize)};
  if (kind === "machines") return {crafting_speed: Number(row.craftingSpeed)};
  const value = {
    enabled: Boolean(row.enabled),
    prerequisites: [...(row.prerequisites || [])],
  };
  if (row.unitCount !== null && row.unitCount !== undefined && !row.unitCountFormula)
    value.unit_count = Number(row.unitCount);
  if (row.unitTime !== null && row.unitTime !== undefined)
    value.unit_time = Number(row.unitTime);
  return value;
}

async function commitRow(kind, row) {
  try {
    const result = await jsonPost("/api/edit", {
      kind, name: row.name, changes: rowChanges(kind, row),
    });
    const rows = state.data[kind];
    const index = rows.findIndex(value => value.name === row.name);
    if (index >= 0) rows[index] = result.row;
    state.config.dirty = result.dirty;
    render();
    refreshShell();
  } catch (error) {
    LexeditorUI.showToast?.(error.message, true);
    render();
  }
}

function changedCopy(row, key, value) {
  const copy = LexeditorUI.clone(row);
  copy[key] = value;
  return copy;
}

function recipePanel(row) {
  const enabled = el("input", {
    type: "checkbox", checked: row.enabled, "aria-label": "Enabled",
    onchange: event => commitRow("recipes", changedCopy(row, "enabled", event.target.checked)),
  });
  const energy = inputNumber(row.energyRequired, {
    label: "Crafting time", step: "any", unit: "s",
    validate: value => value > 0.001 ? "" : "Crafting time must be greater than 0.001 seconds.",
  }, value => commitRow("recipes", changedCopy(row, "energyRequired", value)));
  const productivity = inputNumber(row.maximumProductivity, {
    label: "Maximum productivity", min: 0, step: 0.01, unit: "×",
  }, value => commitRow("recipes", changedCopy(row, "maximumProductivity", value)));
  return detailPanel({
    title: row.name,
    identity: null,
    meta: row.modified ? "recipe · modified by this project" : "recipe · source value",
    body: [
      detailSection({title: "PROTOTYPE", body: [
        detailField({label: "IDENTITY", control: prototypeIdentity(row),
          help: infoHelp("The data.raw prototype type and name form the stable edit identity. Lexeditor does not rename prototypes.")}),
        detailField({label: "ENABLED", dataType: "BOOL", control: enabled,
          help: infoHelp("Whether the recipe starts enabled. Recipes unlocked by technology are normally disabled initially.")}),
        detailField({label: "CRAFT TIME", dataType: "FLOAT", range: "(> 0.001)", control: energy,
          help: infoHelp("Base crafting time at crafting speed 1. Raising it makes this recipe take longer in every compatible crafting machine; lowering it shortens the craft before machine speed bonuses.")}),
        detailField({label: "MAX PRODUCTIVITY", dataType: "FLOAT", min: 0, control: productivity,
          help: infoHelp("Caps the productivity bonus this recipe can receive after machine and module effects are combined.")}),
        detailField({label: "CATEGORIES", control: referenceList(row.categories, "", "crafting"),
          help: infoHelp("Recipe categories are reference data in this scope; category editing is not yet integrated.")}),
      ]}),
      detailSection({title: "REFERENCES", body: [
        detailField({label: "INGREDIENTS", control: referenceList(row.ingredients, "items"),
          help: infoHelp("Ingredients come from the imported post-load prototype dump. Item references can be opened when they are an editable ItemPrototype descendant.")}),
        detailField({label: "RESULTS", control: referenceList(row.results, "items"),
          help: infoHelp("Products are preserved from the source dump and are not rewritten by the current recipe editor.")}),
      ]}),
    ],
  });
}

function itemPanel(row) {
  const stack = inputNumber(row.stackSize, {
    label: "Stack size", min: 1, max: 4294967295, step: 1, unit: "items",
  }, value => commitRow("items", changedCopy(row, "stackSize", Math.trunc(value))));
  return detailPanel({
    title: row.name, identity: null,
    meta: `${row.prototypeType}${row.modified ? " · modified by this project" : ""}`,
    body: [
      detailSection({title: "ITEM", body: [
        detailField({label: "IDENTITY", control: prototypeIdentity(row),
          help: infoHelp("Real Factorio prototype identity; no synthetic numeric ID is invented.")}),
        detailField({label: "STACK SIZE", dataType: "INT", min: 1, max: 4294967295, control: stack,
          help: infoHelp("Controls how many of this item fit in one inventory slot. Items marked not-stackable remain single-item stacks.")}),
        detailField({label: "FLAGS", control: referenceList(row.flags, "", "None"),
          help: infoHelp("Item flags are shown from the source dump and remain read-only in this scope.")}),
        detailField({label: "PLACE RESULT", control: readonlyField(row.placeResult || "—"),
          help: infoHelp("Entity placed by this item, when any. It is shown for context but is not rewritten.")}),
      ]}),
    ],
  });
}

function machinePanel(row) {
  const speed = inputNumber(row.craftingSpeed, {
    label: "Crafting speed", step: "any", unit: "×",
    validate: value => value > 0 ? "" : "Crafting speed must be greater than 0.",
  }, value => commitRow("machines", changedCopy(row, "craftingSpeed", value)));
  return detailPanel({
    title: row.name, identity: null,
    meta: `${row.prototypeType}${row.modified ? " · modified by this project" : ""}`,
    body: [
      detailSection({title: "CRAFTING MACHINE", body: [
        detailField({label: "IDENTITY", control: prototypeIdentity(row)}),
        detailField({label: "CRAFTING SPEED", dataType: "FLOAT", range: "(> 0)", control: speed,
          help: infoHelp("Scales how quickly this machine executes recipes relative to crafting speed 1, before other speed effects.")}),
        detailField({label: "CATEGORIES", control: referenceList(row.craftingCategories, "", "None"),
          help: infoHelp("Recipe categories this machine can use. Read-only until category-list editing has dedicated reference controls.")}),
        detailField({label: "ENERGY USE", control: readonlyField(row.energyUsage || "—"),
          help: infoHelp("The machine's source Energy value. This scope does not rewrite energy source or consumption.")}),
        detailField({label: "MODULE SLOTS", control: readonlyField(row.moduleSlots ?? "—"),
          help: infoHelp("Shown from the imported prototype. Module-slot editing is not yet integrated.")}),
      ]}),
    ],
  });
}

function prerequisiteControl(row) {
  const selected = new Set(row.prerequisites || []);
  const select = el("select", {
    multiple: true, size: 7,
    "aria-label": "Technology prerequisites",
    onchange: event => {
      const values = [...event.target.selectedOptions].map(option => option.value);
      void commitRow("technologies", changedCopy(row, "prerequisites", values));
    },
  });
  for (const candidate of state.data.technologies) {
    if (candidate.name === row.name) continue;
    select.append(el("option", {
      value: candidate.name, selected: selected.has(candidate.name),
    }, candidate.name));
  }
  return select;
}

function technologyPanel(row) {
  const enabled = el("input", {
    type: "checkbox", checked: row.enabled, "aria-label": "Technology enabled",
    onchange: event => commitRow("technologies", changedCopy(row, "enabled", event.target.checked)),
  });
  const count = row.unitCountFormula
    ? readonlyField(`Formula: ${row.unitCountFormula}`)
    : row.unitCount === null || row.unitCount === undefined
      ? readonlyField("Trigger-only technology")
      : inputNumber(row.unitCount, {
          label: "Research unit count", min: 1, max: Number.MAX_SAFE_INTEGER, step: 1, unit: "units",
        }, value => commitRow("technologies", changedCopy(row, "unitCount", Math.trunc(value))));
  const time = row.unitTime === null || row.unitTime === undefined
    ? readonlyField("—")
    : inputNumber(row.unitTime, {
        label: "Research unit time", step: "any", unit: "s",
      }, value => commitRow("technologies", changedCopy(row, "unitTime", value)));
  return detailPanel({
    title: row.name, identity: null,
    meta: row.modified ? "technology · modified by this project" : "technology · source value",
    body: [
      detailSection({title: "TECHNOLOGY", body: [
        detailField({label: "IDENTITY", control: prototypeIdentity(row)}),
        detailField({label: "ENABLED", dataType: "BOOL", control: enabled,
          help: infoHelp("Whether the technology is enabled and available to its normal research conditions.")}),
        detailField({label: "PREREQUISITES", dataType: "REFS", control: prerequisiteControl(row),
          help: infoHelp("A prerequisite must be researched before this technology can be researched, shaping the technology-tree progression.")}),
        detailField({label: "UNIT COUNT", dataType: row.unitCountFormula ? "FORMULA" : "INT", min: 1, control: count,
          help: infoHelp("How many research units the technology consumes. Technologies whose cost changes by level keep their authored formula instead of replacing it with a fixed cost.")}),
        detailField({label: "UNIT TIME", dataType: "FLOAT", control: time,
          help: infoHelp("Research time for one unit in a lab running at speed 1. Total research time also depends on the unit count and lab speed.")}),
      ]}),
      detailSection({title: "REFERENCES", body: [
        detailField({label: "SCIENCE", control: referenceList(row.science, "items"),
          help: infoHelp("Research ingredients are source references in this scope.")}),
        detailField({label: "UNLOCKS", control: referenceList(row.unlocks, "recipes"),
          help: infoHelp("Recipes unlocked by technology effects. Click an integrated recipe to open it.")}),
      ]}),
    ],
  });
}

const panels = {
  recipes: recipePanel,
  items: itemPanel,
  machines: machinePanel,
  technologies: technologyPanel,
};

function booleanCellEditor(row, key, commit, label) {
  const input = el("input", {
    type: "checkbox",
    checked: Boolean(row[key]),
    "aria-label": label,
  });
  input.addEventListener("change", () => commit(input.checked));
  input.addEventListener("blur", () => commit(input.checked));
  input.addEventListener("keydown", event => {
    if (event.key === "Escape") { event.preventDefault(); commit(undefined); }
    if (event.key === "Enter") { event.preventDefault(); commit(input.checked); }
  });
  return input;
}

function unavailableCellEditor(message, commit) {
  const control = el("button", {
    type: "button",
    title: message,
    onclick: () => commit(undefined),
    onblur: () => commit(undefined),
    onkeydown: event => {
      if (event.key === "Escape" || event.key === "Enter") {
        event.preventDefault();
        commit(undefined);
      }
    },
  }, "Read only");
  return control;
}

function optionalNumberCellEditor(row, key, commit, options = {}) {
  if (typeof options.available === "function" && !options.available(row))
    return unavailableCellEditor(options.unavailable || "This value is source-controlled.", commit);
  const input = el("input", {
    type: "number",
    value: row[key] ?? "",
    step: options.step ?? "any",
    "aria-label": options.label || key,
  });
  if (options.min !== undefined) input.min = String(options.min);
  if (options.max !== undefined) input.max = String(options.max);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); commit(input.value); }
    if (event.key === "Escape") { event.preventDefault(); commit(undefined); }
  });
  input.addEventListener("blur", () => commit(input.value));
  return input;
}

function numberCellEdit(kind, key, options = {}) {
  return (row, value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      LexeditorUI.showToast?.("Enter a finite number.", true);
      return;
    }
    const next = options.integer ? Math.trunc(number) : number;
    const validation = typeof options.validate === "function" ? options.validate(next) : "";
    if (validation) {
      LexeditorUI.showToast?.(validation, true);
      return;
    }
    void commitRow(kind, changedCopy(row, key, next));
  };
}

const columns = {
  recipes: [
    {key: "name", label: "Recipe"},
    {
      key: "enabled", label: "Enabled", render: row => booleanMark(row.enabled),
      editor: (row, commit) => booleanCellEditor(row, "enabled", commit, "Recipe enabled"),
      edit: (row, value) => void commitRow("recipes", changedCopy(row, "enabled", Boolean(value))),
    },
    {
      key: "energyRequired", label: "Craft time", numeric: true, step: "any",
      edit: numberCellEdit("recipes", "energyRequired", {
        validate: value => value > 0.001 ? "" : "Crafting time must be greater than 0.001 seconds.",
      }),
    },
    {
      key: "maximumProductivity", label: "Max prod.", numeric: true, min: 0, step: 0.01,
      edit: numberCellEdit("recipes", "maximumProductivity", {
        validate: value => value >= 0 ? "" : "Maximum productivity must be at least 0.",
      }),
    },
  ],
  items: [
    {key: "name", label: "Item"},
    {key: "prototypeType", label: "Type"},
    {
      key: "stackSize", label: "Stack", numeric: true, min: 1, max: 4294967295, step: 1,
      edit: numberCellEdit("items", "stackSize", {
        integer: true,
        validate: value => value >= 1 && value <= 4294967295
          ? "" : "Stack size must be between 1 and 4,294,967,295.",
      }),
    },
    {key: "placeResult", label: "Places", render: row => row.placeResult || "—"},
  ],
  machines: [
    {key: "name", label: "Machine"},
    {key: "prototypeType", label: "Type"},
    {
      key: "craftingSpeed", label: "Speed", numeric: true, step: "any",
      edit: numberCellEdit("machines", "craftingSpeed", {
        validate: value => value > 0 ? "" : "Crafting speed must be greater than 0.",
      }),
    },
    {key: "energyUsage", label: "Energy", render: row => row.energyUsage || "—"},
  ],
  technologies: [
    {key: "name", label: "Technology"},
    {
      key: "enabled", label: "Enabled", render: row => booleanMark(row.enabled),
      editor: (row, commit) => booleanCellEditor(row, "enabled", commit, "Technology enabled"),
      edit: (row, value) => void commitRow("technologies", changedCopy(row, "enabled", Boolean(value))),
    },
    {
      key: "unitCount", label: "Units", numeric: true,
      render: row => row.unitCountFormula ? "formula" : (row.unitCount ?? "—"),
      editor: (row, commit) => optionalNumberCellEditor(row, "unitCount", commit, {
        available: row => !row.unitCountFormula && row.unitCount !== null && row.unitCount !== undefined,
        unavailable: row?.unitCountFormula ? "Formula-controlled research count." : "Trigger-only technology.",
        min: 1, max: Number.MAX_SAFE_INTEGER, step: 1, label: "Research unit count",
      }),
      edit: (row, value) => {
        if (row.unitCountFormula || row.unitCount === null || row.unitCount === undefined) return;
        numberCellEdit("technologies", "unitCount", {
          integer: true,
          validate: number => number >= 1 && number <= Number.MAX_SAFE_INTEGER
            ? "" : "This UI accepts fixed research counts from 1 through JavaScript's exact integer limit.",
        })(row, value);
      },
    },
    {
      key: "unitTime", label: "Time", numeric: true, render: row => row.unitTime ?? "—",
      editor: (row, commit) => optionalNumberCellEditor(row, "unitTime", commit, {
        available: row => row.unitTime !== null && row.unitTime !== undefined,
        unavailable: "Trigger-only technology.",
        step: "any", label: "Research unit time",
      }),
      edit: (row, value) => {
        if (row.unitTime === null || row.unitTime === undefined) return;
        numberCellEdit("technologies", "unitTime")(row, value);
      },
    },
  ],
};

const prefs = Object.fromEntries(KINDS.map(kind => [
  kind, columnPreferences(`factorio-${kind}`, columns[kind], () => render()),
]));

function filtered(kind) {
  const query = state.query[kind].trim().toLocaleLowerCase();
  return state.data[kind].filter(row => !query ||
    `${row.name} ${row.prototypeType}`.toLocaleLowerCase().includes(query));
}

function table(kind, rows, selected, select) {
  return columnList({
    rows, key: row => row.name, selected, select,
    columns: columns[kind], columnPreferences: prefs[kind],
    sortState: state.sort[kind],
    sort: key => {
      const current = state.sort[kind];
      state.sort[kind] = current.key === key ? {key, dir: -current.dir} : {key, dir: 1};
      render();
    },
    "aria-label": `Factorio ${LABELS[kind]}`,
  });
}

function sorted(kind, values) {
  const {key, dir} = state.sort[kind];
  return [...values].sort((left, right) => {
    const a = left[key] ?? "", b = right[key] ?? "";
    const result = typeof a === "number" && typeof b === "number"
      ? a - b : String(a).localeCompare(String(b), undefined, {numeric: true, sensitivity: "base"});
    return result * dir;
  });
}

function recordsPanel(kind) {
  if (!sourceReady()) return sourceState();
  const rows = sorted(kind, filtered(kind));
  return pagedListDetail({
    modOnly: {
      available: true,
      value: state.modOnly[kind],
      changed: row => row.modified,
      change: value => { state.modOnly[kind] = value; state.page[kind] = 0; render(); },
    },
    rows,
    key: row => row.name,
    slots: false,
    selected: state.selected[kind],
    page: state.page[kind],
    pageSize: state.pageSize[kind],
    noun: LABELS[kind].toLocaleLowerCase(),
    splitKey: `factorio-${kind}`,
    rowsKey: `factorio-${kind}`,
    defaultSplit: 55,
    minLeft: 400,
    minRight: 360,
    search: {
      key: `factorio-${kind}`,
      value: state.query[kind],
      label: `Search Factorio ${LABELS[kind]}`,
      placeholder: `Search ${LABELS[kind].toLocaleLowerCase()}…`,
      change: value => { state.query[kind] = value; state.page[kind] = 0; render(); },
    },
    sync: next => {
      state.page[kind] = next.page;
      state.pageSize[kind] = next.pageSize;
      if (next.selected !== null) state.selected[kind] = next.selected;
    },
    change: next => {
      state.page[kind] = next.page;
      state.pageSize[kind] = next.pageSize;
      state.selected[kind] = next.selected || "";
      render();
    },
    master: view => table(kind, view.rows, view.selected, view.select),
    detail: row => panels[kind](row),
    emptyDetail: () => detailPanel({className: "lex-information-panel",
      title: `No ${LABELS[kind].toLocaleLowerCase()} match`,
      body: [detailNote("Clear the search or turn off Mod contents only.")]}),
  });
}

function diagnosticsSection() {
  const rows = state.config?.diagnostics || [];
  if (!rows.length) return detailSection({title: "VALIDATION", body: [
    detailField({label: "SOURCE GRAPH", control: readonlyField("No modeled reference errors found")}),
  ]});
  return detailSection({title: `VALIDATION · ${rows.length}`, body: rows.slice(0, 12).map(row =>
    notice({message: `${row.severity.toUpperCase()} · ${row.record}: ${row.message}`,
      tone: row.severity === "error" ? "warning" : undefined}))});
}

function infoPanel() {
  const config = state.config || {};
  const install = config.install || {};
  const dlc = install.dlc || {};
  const support = config.support || {};
  const mod = config.project?.mod || {};
  const dependencies = config.exportDependencies || [];
  const buttons = actionRow(
    el("button", {type: "button", disabled: !sourceReady() || !editingAllowed(), onclick: exportCurrent}, "Export Mod"),
    el("button", {type: "button", onclick: reopen}, "Reopen Project"));
  const exportResult = state.exportResult
    ? el("div", {class: "factorio-export-result"},
        notice({title: state.exportResult.filename,
          message: `SHA-256: ${state.exportResult.sha256} — ${state.exportResult.message}`}))
    : readonlyField("No candidate exported in this session");
  return detailPanel({
    title: "Factorio Plugin",
    identity: null,
    meta: "2.1 structured prototype editor",
    body: [
      detailSection({title: "GAME", body: [
        detailField({label: "SUPPORTED", control: readonlyField(support.factorio || "2.1.x"),
          help: infoHelp("This implementation targets the Factorio 2.1 prototype schema. Other engine major/minor lines fail closed.")}),
        detailField({label: "DETECTED VERSION", control: readonlyField(install.version || "Not detected")}),
        detailField({label: "VERSION STATE", control: readonlyField(install.state || "Unknown")}),
        detailField({label: "SPACE AGE", control: readonlyField(
          `${dlc.spaceAge ? "installed" : "not detected"}; ${support.spaceAgeActiveInSource ? "active in imported mod set" : "not active in imported mod list"}`),
          help: infoHelp("Installation and source activation are separate facts. Lexeditor edits the same supported prototype families when Space Age data is present; it does not claim ownership of DLC-only fields outside this scope.")}),
        detailField({label: "QUALITY", control: readonlyField(dlc.quality ? "installed" : "not detected")}),
        detailField({label: "ELEVATED RAILS", control: readonlyField(dlc.elevatedRails ? "installed" : "not detected")}),
      ]}),
      detailSection({title: "PROJECT", body: [
        detailField({label: "MOD", control: readonlyField(mod.name ? `${mod.name} ${mod.version || ""}` : "Invalid project manifest")}),
        detailField({label: "SOURCE", control: readonlyField(config.source?.ready ? "Ready · immutable JSON snapshot" : (config.source?.error || "Missing data-raw-dump.json")),
          help: infoHelp("Lexeditor reads Factorio's --dump-data JSON. It never evaluates arbitrary source-mod Lua on the host.")}),
        detailField({label: "PROTOTYPES", control: readonlyField(
          KINDS.map(kind => `${LABELS[kind]} ${config.counts?.[kind] || 0}`).join(" · "))}),
        detailField({label: "DEPENDENCIES", control: referenceList(dependencies, "", "base >= 2.1.0"),
          help: infoHelp("Authored dependencies are preserved. Enabled source mods become optional dependencies so this override loads after them when they are present.")}),
        detailField({label: "ACTIONS", control: buttons}),
        detailField({label: "LAST EXPORT", control: exportResult}),
      ]}),
      diagnosticsSection(),
      LexeditorUI.modLoaderSection({
        loader: "Factorio's native mod loader. No third-party helper is required and Lexeditor performs no silent helper updates.",
        output: "Export Mod writes <project>/build/<name>_<version>.zip. The source prototype dump and source mods are never overwritten.",
        order: "The generated package declares Factorio 2.1 and runs typed changes from data-final-fixes.lua. Authored dependencies are preserved; enabled source mods are added as optional dependencies for deterministic late load order when present.",
        safety: "No untrusted Lua is executed by Lexeditor. Only Factorio's JSON dump is parsed, and generated Lua consists of validated field assignments guarded by existing prototype identity.",
        removal: "Remove or disable the generated Lexeditor mod in Factorio's normal mod manager. The source mods remain unchanged.",
      }),
    ],
  });
}

async function exportCurrent() {
  try {
    state.exportResult = await jsonPost("/api/export", {});
    render();
  } catch (error) {
    LexeditorUI.showToast?.(error.message, true);
  }
}

async function renderDataMap() {
  if (!state.datamap) state.datamap = await api("/api/datamap");
  const view = LexeditorUI.dataMap({
    rows: state.datamap.rows,
    query: state.map.query,
    status: state.map.status,
    page: state.map.page,
    sort: state.map.sort,
    pageSize: 100,
    changeQuery: value => { state.map.query = value; state.map.page = 0; void render(); },
    changeStatus: value => { state.map.status = value; state.map.page = 0; void render(); },
    changePage: page => { state.map.page = page; void render(); },
    changeSort: key => {
      const [active, direction] = state.map.sort;
      state.map.sort = [key, active === key ? -direction : 1];
      void render();
    },
    open: row => { if (row.target) navigate(row.target); },
  });
  state.map.page = view.page;
  return el("div", {class: "lex-stack"}, toolbar(...view.controls), view.content);
}

async function render() {
  const main = document.querySelector("#main");
  if (!state.error && state.tab === "datamap" && !state.datamap) {
    main.replaceChildren(loadingState("Loading Data Map…"));
    refreshShell();
  }
  let content;
  try {
    if (state.error) content = errorState(state.error);
    else if (state.tab === "info") content = panelLayout([infoPanel()], {
      layoutKey: "factorio-info", defaultSizes: [100],
    });
    else if (state.tab === "datamap") content = await renderDataMap();
    else content = recordsPanel(state.tab);
  } catch (error) {
    state.error = error.message;
    content = errorState(state.error);
  }
  main.replaceChildren(content);
  refreshShell();
}

function navigate(tab) {
  if (![...KINDS, "datamap", "info"].includes(tab)) return;
  state.tab = tab;
  history.replaceState({lexeditor: true, tab}, "", `#${tab}`);
  void render();
}

function navigateTo(kind, name) {
  state.selected[kind] = name;
  state.query[kind] = "";
  state.modOnly[kind] = false;
  navigate(kind);
}

async function loadRows() {
  if (!sourceReady()) {
    for (const kind of KINDS) state.data[kind] = [];
    return;
  }
  const responses = await Promise.all(KINDS.map(kind => api(`/api/data?kind=${encodeURIComponent(kind)}`)));
  responses.forEach((payload, index) => {
    const kind = KINDS[index];
    state.data[kind] = payload.rows;
    if (!state.selected[kind] || !payload.rows.some(row => row.name === state.selected[kind]))
      state.selected[kind] = payload.rows[0]?.name || "";
  });
}

async function save() {
  if (!sourceReady()) return;
  const result = await jsonPost("/api/save", {});
  state.config.dirty = result.dirty;
  refreshShell();
}

async function discard() {
  if (!sourceReady()) return;
  await jsonPost("/api/discard", {});
  state.config = await api("/api/config");
  state.datamap = null;
  await loadRows();
  await render();
  refreshShell();
}

async function reopen() {
  document.querySelector("#main").replaceChildren(loadingState("Reopening Factorio project…"));
  refreshShell();
  try {
    await jsonPost("/api/reopen", {});
    state.config = await api("/api/config");
    state.datamap = null;
    state.exportResult = null;
    state.error = "";
    await loadRows();
    await render();
    refreshShell();
  } catch (error) {
    state.error = error.message;
    await render();
  }
}

const initial = location.hash.replace(/^#/, "");
if ([...KINDS, "datamap", "info"].includes(initial)) state.tab = initial;

const shell = LexeditorUI.mountShell({
  host: "#lexeditor-shell",
  brand: "LEXEDITOR",
  plugin: {
    id: "factorio",
    name: "Factorio",
    themeName: "factorio",
    theme: {
      accent: "#e69b36",
      "accent-text": "#20170b",
      highlight: "#f6bf66",
    },
  },
  tabs: KINDS.map(id => ({id, label: LABELS[id]})),
  activeTab: () => state.tab,
  navigate,
  help: () => navigate("datamap"),
  helpActive: () => state.tab === "datamap",
  helpTitle: "Open the Factorio Data Map",
  info: () => navigate("info"),
  infoActive: () => state.tab === "info",
  infoTitle: "Open Factorio setup, version, DLC and export information",
  dirtyCount,
  readonly: () => !editingAllowed(),
  save,
  discard,
});

window.addEventListener("beforeunload", event => {
  if (!window.__lexeditorNavigating && dirtyCount()) event.preventDefault();
});

async function boot() {
  try {
    state.config = await api("/api/config");
    await loadRows();
  } catch (error) {
    state.error = error.message;
  } finally {
    state.booting = false;
    await render();
    LexeditorUI.finishPluginLoading();
  }
}

document.querySelector("#main").replaceChildren(loadingState());
refreshShell();
void boot();
