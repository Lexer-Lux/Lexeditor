"use strict";

const {
  el, columnList, columnPreferences, detailPanel, detailSection, detailField,
  readonlyField, recordId, infoHelp, infoIcon, pagedListDetail, clone, booleanMark,
} = LexeditorUI;
const $ = selector => document.querySelector(selector);
const FIELD_KEYS = ["Price", "Edibility", "IsDrink"];
const PRICE_MAX = 2147483647;
const EDIBILITY_MIN = -300;
const state = {
  tab: "objects", dashboard: null, dataMap: null, objects: null, rows: [], savedRows: [],
  selected: null, page: 0, pageSize: 30, query: "", sort: {key: "id", dir: 1},
  mapPage: 0, mapQuery: "", mapStatus: "", mapSort: ["filename", 1], busy: false, error: "",
  datasetKey: "objects", dataset: null, datasetRows: [], datasetSavedRows: [], datasetSelected: null,
  datasetPage: 0, datasetQuery: "", datasetSort: {key: "id", dir: 1},
};

async function api(path, body) {
  const response = await fetch(path, body === undefined ? undefined : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || response.statusText);
  return payload;
}

const has = (row, key) => Object.prototype.hasOwnProperty.call(row.fields || {}, key);
const hasBase = (row, key) => Object.prototype.hasOwnProperty.call(row.baseFields || {}, key);
const baseValue = (row, key) => hasBase(row, key) ? row.baseFields[key] : null;
const effective = (row, key) => has(row, key) ? row.fields[key] : baseValue(row, key);

function rowSignature(rows) {
  return JSON.stringify([...rows]
    .filter(row => row.sourcePresent || row.unsupportedFieldCount || Object.keys(row.fields || {}).length)
    .sort((a, b) => a.id.localeCompare(b.id))
    .map(row => ({id: row.id, fields: row.fields || {}})));
}
function dirtyCount() {
  const objectsDirty = state.objects && rowSignature(state.rows) !== rowSignature(state.savedRows);
  const datasetDirty = state.dataset && rowSignature(state.datasetRows) !== rowSignature(state.datasetSavedRows);
  return objectsDirty || datasetDirty ? 1 : 0;
}
function sortedRows() {
  const query = state.query.trim().toLocaleLowerCase();
  return [...state.rows]
    .filter(row => !query || [row.id, row.name, row.internalName]
      .some(value => String(value || "").toLocaleLowerCase().includes(query)))
    .sort((a, b) => {
      let left = state.sort.key === "id" ? a.id : state.sort.key === "name" ? a.name : effective(a, state.sort.key);
      let right = state.sort.key === "id" ? b.id : state.sort.key === "name" ? b.name : effective(b, state.sort.key);
      if (left === null || left === undefined) left = "";
      if (right === null || right === undefined) right = "";
      const result = typeof left === "string"
        ? left.localeCompare(String(right), undefined, {numeric: true, sensitivity: "base"})
        : Number(left) - Number(right);
      return result * state.sort.dir;
    });
}
function installObjects(payload) {
  state.objects = payload;
  state.rows = clone(payload.rows);
  state.savedRows = clone(payload.rows);
  if (!state.rows.some(row => row.id === state.selected)) state.selected = state.rows[0]?.id ?? null;
  return payload;
}
function diffEdits() {
  const old = Object.fromEntries(state.savedRows.map(row => [row.id, row]));
  const current = Object.fromEntries(state.rows.map(row => [row.id, row]));
  const ids = new Set([...Object.keys(old), ...Object.keys(current)]);
  const edits = [];
  for (const id of ids) {
    const before = old[id]?.fields || {};
    const after = current[id]?.fields || {};
    const fields = {};
    for (const key of FIELD_KEYS) {
      const beforeHas = Object.prototype.hasOwnProperty.call(before, key);
      const afterHas = Object.prototype.hasOwnProperty.call(after, key);
      if (beforeHas !== afterHas || (afterHas && JSON.stringify(before[key]) !== JSON.stringify(after[key]))) {
        fields[key] = afterHas ? after[key] : null;
      }
    }
    if (Object.keys(fields).length) edits.push({id, fields});
  }
  return edits;
}

function installDataset(payload) {
  state.dataset = payload;
  state.datasetKey = payload.datasetKey;
  state.datasetRows = clone(payload.rows);
  state.datasetSavedRows = clone(payload.rows);
  if (!state.datasetRows.some(row => row.id === state.datasetSelected)) {
    state.datasetSelected = state.datasetRows[0]?.id ?? null;
  }
  return payload;
}
function datasetDiffEdits() {
  const keys = state.dataset?.schema?.fields?.map(field => field.key) || [];
  const old = Object.fromEntries(state.datasetSavedRows.map(row => [row.id, row]));
  const current = Object.fromEntries(state.datasetRows.map(row => [row.id, row]));
  const ids = new Set([...Object.keys(old), ...Object.keys(current)]);
  const edits = [];
  for (const id of ids) {
    const before = old[id]?.fields || {};
    const after = current[id]?.fields || {};
    const fields = {};
    for (const key of keys) {
      const beforeHas = Object.prototype.hasOwnProperty.call(before, key);
      const afterHas = Object.prototype.hasOwnProperty.call(after, key);
      if (beforeHas !== afterHas || (afterHas && JSON.stringify(before[key]) !== JSON.stringify(after[key]))) {
        fields[key] = afterHas ? after[key] : null;
      }
    }
    if (Object.keys(fields).length) edits.push({id, fields});
  }
  return edits;
}
function sortedDatasetRows() {
  const query = state.datasetQuery.trim().toLocaleLowerCase();
  return [...state.datasetRows]
    .filter(row => !query || [row.id, row.name, row.internalName]
      .some(value => String(value || "").toLocaleLowerCase().includes(query)))
    .sort((a, b) => {
      let left = state.datasetSort.key === "id" ? a.id
        : state.datasetSort.key === "name" ? a.name : effective(a, state.datasetSort.key);
      let right = state.datasetSort.key === "id" ? b.id
        : state.datasetSort.key === "name" ? b.name : effective(b, state.datasetSort.key);
      if (left === null || left === undefined) left = "";
      if (right === null || right === undefined) right = "";
      const result = typeof left === "string"
        ? left.localeCompare(String(right), undefined, {numeric: true, sensitivity: "base"})
        : Number(left) - Number(right);
      return result * state.datasetSort.dir;
    });
}


function clampInteger(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(min, Math.min(max, Math.round(number)));
}
function setOverride(row, key, value) {
  if (row.draft || state.busy) return;
  row.fields[key] = value;
  state.error = "";
}
function numericCellEditor(key, min, max) {
  return (row, commit) => {
    const input = el("input", {
      type: "number", min, max, step: 1, value: effective(row, key) ?? (key === "Price" ? 0 : EDIBILITY_MIN),
      "aria-label": key === "Price" ? "Sell price" : key,
    });
    let finished = false;
    const finish = cancel => {
      if (finished) return;
      finished = true;
      if (cancel) commit(undefined);
      else {
        const value = clampInteger(input.value, min, max);
        if (value === null) commit(undefined); else commit(value);
      }
    };
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); finish(false); }
      if (event.key === "Escape") { event.preventDefault(); finish(true); }
    });
    input.addEventListener("blur", () => finish(false), {once: true});
    return input;
  };
}
function booleanCellEditor(row, commit) {
  const input = el("input", {
    type: "checkbox", checked: !!effective(row, "IsDrink"), "aria-label": "Drink",
  });
  let finished = false;
  const finish = value => { if (!finished) { finished = true; commit(value); } };
  input.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); finish(input.checked); }
    if (event.key === "Escape") { event.preventDefault(); finish(undefined); }
  });
  input.addEventListener("change", () => finish(input.checked), {once: true});
  input.addEventListener("blur", () => finish(input.checked), {once: true});
  return input;
}
function objectColumns() {
  return [
    {key: "id", label: "Object key", sortable: true, width: "9em", help: "The unqualified Data/Objects key used to identify this object."},
    {key: "name", label: "Name", sortable: true, width: "minmax(10em,1.4fr)", render: row => row.name || row.id},
    {
      key: "Price", label: "Sell price", sortable: true, numeric: true, width: "8em",
      help: "The object's base sell price in gold. Shop purchase prices can use separate shop data.",
      sortValue: row => effective(row, "Price") ?? -1,
      render: row => effective(row, "Price") === null ? "—" : String(effective(row, "Price")),
      editor: numericCellEditor("Price", 0, PRICE_MAX), edit: (row, value) => setOverride(row, "Price", value),
    },
    {
      key: "Edibility", label: "Edibility", sortable: true, numeric: true, width: "8em",
      help: "Controls food recovery: energy is edibility × 2.5 and health is edibility × 1.125. -300 is inedible.",
      sortValue: row => effective(row, "Edibility") ?? EDIBILITY_MIN - 1,
      render: row => effective(row, "Edibility") === null ? "—" : String(effective(row, "Edibility")),
      editor: numericCellEditor("Edibility", EDIBILITY_MIN, PRICE_MAX), edit: (row, value) => setOverride(row, "Edibility", value),
    },
    {
      key: "IsDrink", label: "Drink", sortable: true, width: "6em",
      help: "When edible, the item uses drinking behavior instead of eating behavior.",
      sortValue: row => effective(row, "IsDrink") === null ? -1 : Number(effective(row, "IsDrink")),
      render: row => effective(row, "IsDrink") === null ? "—" : booleanMark(!!effective(row, "IsDrink")),
      editor: booleanCellEditor, edit: (row, value) => setOverride(row, "IsDrink", !!value),
    },
  ];
}
const prefs = columnPreferences("stardew-objects", objectColumns(), () => render());

function fieldControl(row, key, kind, min, max, help) {
  const enabled = has(row, key);
  const fallback = kind === "boolean" ? false : kind === "price" ? 0 : EDIBILITY_MIN;
  const inherited = baseValue(row, key);
  const shown = enabled ? row.fields[key] : (inherited ?? fallback);
  const valueLabel = key === "Price" ? "Sell price" : key === "IsDrink" ? "Drink" : "Edibility";
  const input = el("input", kind === "boolean" ? {
    type: "checkbox", checked: !!shown, disabled: !enabled || state.busy || row.draft, "aria-label": valueLabel,
    onchange: event => { row.fields[key] = event.target.checked; shell.refresh(); },
  } : {
    type: "number", min, max, step: 1, value: shown, disabled: !enabled || state.busy || row.draft, "aria-label": valueLabel,
    oninput: event => {
      const value = clampInteger(event.target.value, min, max);
      if (value !== null) row.fields[key] = value;
      shell.refresh();
    },
  });
  const override = el("input", {
    type: "checkbox", checked: enabled, disabled: state.busy || row.draft, "aria-label": `Override ${key}`,
    onchange: event => {
      if (event.target.checked) row.fields[key] = inherited ?? fallback;
      else delete row.fields[key];
      state.error = "";
      render(); shell.refresh();
    },
  });
  return detailField({
    label: key === "Price" ? "SELL PRICE" : key === "IsDrink" ? "DRINK" : "EDIBILITY",
    help: infoHelp(help),
    control: el("div", {class: "lex-action-row"}, el("label", {}, override, "Override"), input),
    dataType: kind === "boolean" ? "BOOL" : "INT", min, max,
    pin: prefs.pinButton(key, valueLabel),
    attrs: {"data-lex-property": key},
  });
}
function tablePanel(rows = sortedRows(), picked = state.selected, select = row => { if (state.selected === row.id) return; state.selected = row.id; render(); }) {
  return columnList({
    rows, key: row => row.id, selected: picked, select, sortState: state.sort,
    sort: key => { state.sort = state.sort.key === key ? {key, dir: -state.sort.dir} : {key, dir: 1}; state.page = 0; render(); },
    columnPreferences: prefs, columns: objectColumns(), "aria-label": "Stardew objects",
    refresh: () => { render(); shell.refresh(); },
  });
}
function clearOverrides(row) {
  for (const key of FIELD_KEYS) delete row.fields[key];
  if (!row.sourcePresent && !row.unsupportedFieldCount) {
    state.rows = state.rows.filter(candidate => candidate !== row.id);
    state.selected = state.rows[0]?.id ?? null;
  }
  state.error = "";
  render(); shell.refresh();
}
function renameDraft(row, value) {
  const clean = String(value || "").trim();
  if (!clean || clean.length > 160 || /[\r\n]/.test(clean)) {
    state.error = "Object key must be 1–160 characters with no line breaks.";
    render(); return;
  }
  if (state.rows.some(candidate => candidate !== row && candidate.id === clean)) {
    state.error = `Object key ${clean} already exists.`;
    render(); return;
  }
  row.id = clean; row.name = clean; row.internalName = clean; row.draft = false;
  state.selected = clean; state.error = ""; render(); shell.refresh();
}
function detail(row) {
  if (!row) {
    const source = state.objects?.baseSource;
    const message = source?.available
      ? "No Data/Objects records match the current search."
      : "No object records are available yet. Add a patch by object key, or provide an existing StardewXnbHack Data/Objects export to browse vanilla objects.";
    return detailPanel({title: "Data/Objects", meta: "No records", body: [el("p", {class: "lex-notice"}, message)]});
  }
  const remove = el("button", {
    type: "button", disabled: state.busy || !FIELD_KEYS.some(key => has(row, key)), onclick: () => clearOverrides(row),
  }, "Clear supported overrides");
  const sourceMeta = row.sourcePresent ? "Vanilla source + project patch" : "Project/external record only";
  const idControl = row.draft
    ? el("input", {type: "text", value: row.id, disabled: state.busy, "aria-label": "Object key", onchange: event => renameDraft(row, event.target.value)})
    : readonlyField(row.internalName || row.id, {format: false});
  const longKey = String(row.id).length > 8;
  return detailPanel({
    title: row.name || "Object", identity: longKey ? null : recordId(row.id),
    meta: longKey ? `${row.id} · ${sourceMeta}` : sourceMeta,
    body: [
      detailSection({title: "SOURCE", body: [
        detailField({
          label: row.draft ? "OBJECT KEY" : "INTERNAL NAME", control: idControl,
          help: row.draft ? infoHelp("This becomes the unqualified Data/Objects key used by Content Patcher and Stardew to identify the object.") : null,
        }),
        detailField({label: "DESCRIPTION", control: readonlyField(row.description || "—", {format: false})}),
      ]}),
      detailSection({title: "ECONOMY & CONSUMPTION", body: [
        fieldControl(row, "Price", "price", 0, PRICE_MAX,
          "The object's base sell price in gold. This does not directly set a shop's purchase price; shops can define their own pricing."),
        fieldControl(row, "Edibility", "integer", EDIBILITY_MIN, PRICE_MAX,
          "Controls what eating or drinking restores: energy is edibility × 2.5 and health is edibility × 1.125. -300 makes the item inedible; negative values above -300 reduce health and energy."),
        fieldControl(row, "IsDrink", "boolean", null, null,
          "When the item is edible, this makes Stardew use drinking behavior instead of eating behavior."),
      ]}),
      detailSection({title: "PATCH", body: [
        detailField({label: "ACTIONS", control: el("div", {class: "lex-action-row"}, remove)}),
        ...(row.unsupportedFieldCount ? [el("p", {class: "lex-notice"}, `${row.unsupportedFieldCount} unsupported field(s) in this record are preserved unchanged.`)] : []),
      ]}),
    ],
  });
}
function addRecord() {
  let index = 1, id = "new-object";
  while (state.rows.some(row => row.id === id)) id = `new-object-${++index}`;
  state.rows.push({
    id, name: id, internalName: id, description: "", baseFields: {}, sourcePresent: false,
    fields: {}, present: [], unsupportedFieldCount: 0, draft: true,
  });
  state.selected = id; state.page = 0; state.error = ""; render(); shell.refresh();
}
function objectsPanel() {
  const records = sortedRows();
  return pagedListDetail({
    rows: records, key: row => row.id, slots: false, add: addRecord, addTitle: "Add Data/Objects patch",
    addDisabled: state.busy, selected: state.selected, page: state.page, pageSize: state.pageSize, noun: "objects",
    splitKey: "stardew-objects", rowsKey: "stardew-objects", defaultSplit: 48,
    minLeft: 360, minRight: 400,
    search: {key: "stardew-objects-search", value: state.query, label: "Search object keys or names", change: value => { state.query = value; state.page = 0; render(); }},
    emptyDetail: () => detail(null), master: view => tablePanel(view.rows, view.selected, view.select), detail,
    sync: next => { state.page = next.page; state.pageSize = next.pageSize; if (next.selected !== null) state.selected = next.selected; },
    change: next => { state.page = next.page; state.pageSize = next.pageSize; if (next.selected !== null) state.selected = next.selected; render(); },
  });
}

const datasetPrefs = new Map();
function datasetColumns() {
  const fields = state.dataset?.schema?.fields || [];
  return [
    {key: "id", label: "Record key", sortable: true, width: "10em"},
    {key: "name", label: "Name", sortable: true, width: "minmax(10em,1.4fr)", render: row => row.name || row.id},
    ...fields.slice(0, 3).map(field => ({
      key: field.key, label: field.label, sortable: true, width: "9em",
      numeric: field.kind === "int" || field.kind === "number",
      sortValue: row => effective(row, field.key),
      render: row => {
        const value = effective(row, field.key);
        if (value === null || value === undefined) return "—";
        if (field.kind === "bool") return booleanMark(!!value);
        const option = field.options?.find(candidate => candidate.value === value);
        return option ? option.label : String(value);
      },
    })),
  ];
}
function currentDatasetPrefs() {
  const key = state.datasetKey;
  if (!datasetPrefs.has(key)) {
    datasetPrefs.set(key, columnPreferences("stardew-"+key, datasetColumns(), () => render()));
  }
  return datasetPrefs.get(key);
}
function defaultDatasetValue(field) {
  if (Object.prototype.hasOwnProperty.call(field, "default")) return field.default;
  if (field.kind === "bool") return false;
  if (field.kind === "enum") return field.options?.[0]?.value ?? "";
  return field.min ?? 0;
}
function datasetFieldControl(row, field) {
  const key = field.key;
  const enabled = has(row, key);
  const inherited = baseValue(row, key);
  const shown = enabled ? row.fields[key] : (inherited ?? defaultDatasetValue(field));
  let control;
  if (field.kind === "bool") {
    control = el("input", {
      type: "checkbox", checked: !!shown, disabled: !enabled || state.busy,
      "aria-label": field.label,
      onchange: event => { row.fields[key] = event.target.checked; shell.refresh(); },
    });
  } else if (field.kind === "enum") {
    control = el("select", {
      disabled: !enabled || state.busy, "aria-label": field.label,
      onchange: event => { row.fields[key] = JSON.parse(event.target.value); shell.refresh(); },
    }, ...(field.options || []).map(option => el("option", {
      value: JSON.stringify(option.value), selected: JSON.stringify(option.value) === JSON.stringify(shown),
    }, option.label)));
  } else {
    control = el("input", {
      type: "number", min: field.min, max: field.max, step: field.kind === "int" ? 1 : (field.step || 0.01),
      value: shown, disabled: !enabled || state.busy, "aria-label": field.label,
      oninput: event => {
        const raw = Number(event.target.value);
        if (!Number.isFinite(raw)) return;
        const normalized = field.kind === "int" ? Math.round(raw) : raw;
        const value = Math.max(field.min, Math.min(field.max, normalized));
        event.target.value = String(value);
        row.fields[key] = value;
        shell.refresh();
      },
    });
  }
  const override = el("input", {
    type: "checkbox", checked: enabled, disabled: state.busy, "aria-label": "Override "+field.label,
    onchange: event => {
      if (event.target.checked) row.fields[key] = inherited ?? defaultDatasetValue(field);
      else delete row.fields[key];
      state.error = ""; render(); shell.refresh();
    },
  });
  return detailField({
    label: field.label.toUpperCase(),
    help: field.help ? infoHelp(field.help) : null,
    control: el("div", {class: "lex-action-row"}, el("label", {}, override, "Override"), control),
    dataType: field.kind === "bool" ? "BOOL" : field.kind === "enum" ? "ENUM" : field.kind.toUpperCase(),
    min: field.min, max: field.max, attrs: {"data-lex-property": key},
  });
}


function datasetDetail(row) {
  const schema = state.dataset?.schema;
  if (!row) {
    const source = state.dataset?.baseSource;
    const message = source?.available
      ? "No records match the current search."
      : "No records are available. Provide the read-only StardewXnbHack "+schema.target+" JSON export, or open a project that already contains Lexeditor field overrides for this family.";
    return detailPanel({title: schema?.target || "Data", meta: "No records",
      body: [el("p", {class: "lex-notice"}, message)]});
  }
  const remove = el("button", {
    type: "button", disabled: state.busy || !(schema.fields || []).some(field => has(row, field.key)),
    onclick: () => {
      for (const field of schema.fields || []) delete row.fields[field.key];
      state.error = ""; render(); shell.refresh();
    },
  }, "Clear supported overrides");
  const sourceMeta = row.sourcePresent ? "Vanilla source + project patch" : "Project/external record only";
  return detailPanel({
    title: row.name || row.id,
    identity: String(row.id).length <= 12 ? recordId(row.id) : null,
    meta: String(row.id).length <= 12 ? sourceMeta : row.id+" · "+sourceMeta,
    body: [
      detailSection({title: "SOURCE", body: [
        detailField({label: "RECORD KEY", control: readonlyField(row.id, {format: false})}),
        ...(row.description ? [detailField({label: "DESCRIPTION", control: readonlyField(row.description, {format: false})})] : []),
      ]}),
      detailSection({title: "EDITABLE FIELDS", body: (schema.fields || []).map(field => datasetFieldControl(row, field))}),
      detailSection({title: "PATCH", body: [
        detailField({label: "ACTIONS", control: el("div", {class: "lex-action-row"}, remove)}),
        ...(row.unsupportedFieldCount ? [el("p", {class: "lex-notice"}, row.unsupportedFieldCount+" unsupported project field(s) are preserved unchanged.")] : []),
        ...(row.invalidFieldCount ? [el("p", {class: "lex-notice"}, row.invalidFieldCount+" source field(s) could not be represented by this typed view and remain read-only.")] : []),
      ]}),
    ],
  });
}
function datasetPanel() {
  const records = sortedDatasetRows();
  const columns = datasetColumns();
  const prefs = currentDatasetPrefs();
  return pagedListDetail({addDisabledReason:"Lexeditor edits the entries this data asset already has here; adding one to this asset is not supported yet.",
    rows: records, key: row => row.id, slots: false,
    selected: state.datasetSelected, page: state.datasetPage, pageSize: state.pageSize,
    noun: state.dataset?.schema?.noun || "records",
    splitKey: "stardew-"+state.datasetKey, rowsKey: "stardew-"+state.datasetKey,
    defaultSplit: 48, minLeft: 360, minRight: 400,
    search: {key: "stardew-"+state.datasetKey+"-search", value: state.datasetQuery,
      label: "Search "+(state.dataset?.schema?.label || "data")+" keys or names",
      change: value => { state.datasetQuery = value; state.datasetPage = 0; render(); }},
    emptyDetail: () => datasetDetail(null),
    master: view => columnList({
      rows: view.rows, key: row => row.id, selected: view.selected, select: view.select,
      sortState: state.datasetSort,
      sort: key => { state.datasetSort = state.datasetSort.key === key
        ? {key, dir: -state.datasetSort.dir} : {key, dir: 1}; state.datasetPage = 0; render(); },
      columnPreferences: prefs, columns,
      "aria-label": "Stardew "+(state.dataset?.schema?.label || "data"), refresh: () => { render(); shell.refresh(); },
    }),
    detail: datasetDetail,
    sync: next => { state.datasetPage = next.page; state.pageSize = next.pageSize; if (next.selected !== null) state.datasetSelected = next.selected; },
    change: next => { state.datasetPage = next.page; state.pageSize = next.pageSize; if (next.selected !== null) state.datasetSelected = next.selected; render(); },
  });
}
async function openDataset(key) {
  if (dirtyCount()) {
    LexeditorUI.showAlert({title: "Save or discard changes first", message: "Switching data families is blocked while this project has unsaved edits."});
    return;
  }
  if (key === "objects") {
    state.datasetKey = "objects"; state.dataset = null; navigate("objects"); return;
  }
  state.busy = true; state.error = ""; shell.refresh();
  try {
    installDataset(await api("/api/datasets/"+encodeURIComponent(key)));
    state.datasetPage = 0; state.datasetQuery = ""; state.datasetSort = {key: "id", dir: 1};
    navigate("objects");
  } catch (error) {
    state.error = error.message;
    LexeditorUI.showAlert({title: "Could not open Stardew data", message: state.error});
  } finally {
    state.busy = false; render();
  }
}

function dataMapPanel() {
  const view = LexeditorUI.dataMap({
    rows: state.dataMap.rows, query: state.mapQuery, status: state.mapStatus, page: state.mapPage,
    sort: state.mapSort, pageSize: 100, open: row => { if (row.datasetKey) openDataset(row.datasetKey); },
    changeQuery: value => { state.mapQuery = value; state.mapPage = 0; render(); },
    changeStatus: value => { state.mapStatus = value; state.mapPage = 0; render(); },
    changePage: page => { state.mapPage = page; render(); },
    changeSort: key => { const [active, direction] = state.mapSort; state.mapSort = [key, active === key ? -direction : 1]; render(); },
  });
  state.mapPage = view.page;
  return view.content;
}
function stardewModLoaderSection() {
  return LexeditorUI.modLoaderSection({
    loader: "SMAPI with Content Patcher 2.9.0 or newer.",
    output: "A normal Content Patcher content pack deployed under <Stardew Valley>/Mods/[CP] Lexeditor <project>.",
    order: "Content Patcher applies the pack through SMAPI; Lexeditor writes field-level EditData overrides so unrelated fields remain composable.",
    safety: "Installed Content/*.xnb files stay read-only, and managed deployment refuses externally changed copies.",
    removal: "Revert Lexeditor Mod removes only the Lexeditor-managed deployed copy; the source project is preserved.",
  });
}
function infoPanel() {
  const dashboard = state.dashboard;
  const loader = dashboard.loader;
  const deployment = dashboard.deployment;
  const source = dashboard.source || {};
  const acceptance = dashboard.acceptance || {};
  const read = value => readonlyField(String(value ?? "—"), {format: false});
  const contentPatcherState = !loader.contentPatcher ? "Not found"
    : loader.contentPatcherCompatible ? `Installed · ${loader.contentPatcherVersion || "version unknown"}`
      : `Update required · ${loader.contentPatcherVersion || "unknown"} (need ${loader.requiredContentPatcherVersion || "2.9.0"}+)`;
  const actions = el("div", {class: "lex-action-row"},
    el("button", {type: "button", disabled: state.busy || dirtyCount() > 0 || !loader.ready, onclick: () => deploymentAction("deploy")}, deployment.deployed ? "Redeploy Project" : "Deploy Project"),
    el("button", {type: "button", disabled: state.busy || !deployment.managed || deployment.externallyChanged, onclick: () => deploymentAction("revert")}, "Revert Lexeditor Mod"));
  const acceptanceActions = el("div", {class: "lex-action-row"},
    el("button", {type: "button", disabled: state.busy || dirtyCount() > 0 || !loader.ready || !deployment.managed || deployment.externallyChanged, onclick: acceptanceBegin}, acceptance.started ? "Reset Acceptance Baseline" : "Begin Acceptance"),
    el("button", {type: "button", disabled: state.busy || !acceptance.started, onclick: acceptanceVerify}, "Verify Acceptance Evidence"));
  const acceptanceState = acceptance.accepted ? "Accepted"
    : acceptance.state === "waiting-for-run" ? "Waiting for new SMAPI run"
      : acceptance.state === "failed" ? "Verification failed" : "Not started";
  const runtime = acceptance.smapiVersion
    ? `SMAPI ${acceptance.smapiVersion} · Stardew ${acceptance.gameVersion || "?"}${acceptance.gameBuild ? ` build ${acceptance.gameBuild}` : ""}`
    : "No post-baseline runtime detected";
  return detailPanel({className: "lex-information-panel", icon: infoIcon(), title: "Information",
    meta: "Stardew Valley installation, source data, loader, project deployment, and installed acceptance", body: [
      detailSection({title: "GAME", body: [
        detailField({label: "STATE", control: read(dashboard.game.ready ? "Ready" : "Incomplete")}),
        detailField({label: "FOLDER", control: read(dashboard.game.root)}),
      ]}),
      detailSection({title: "VANILLA DATA", body: [
        detailField({label: "OBJECTS", control: read(source.available ? `Ready — ${source.recordCount} records` : source.error ? "Invalid unpacked source" : "Unpacked source not found"),
          help: infoHelp("An existing StardewXnbHack Data/Objects export adds vanilla names, descriptions, and base values. It is optional for editing project-owned Content Patcher overrides.")}),
        detailField({label: "SOURCE", control: read(source.path)}),
        detailField({label: "STARDEWXNBHACK", control: read(source.helperInstalled ? "Detected in game folder" : "Not detected"),
          help: infoHelp("Lexeditor only reads an existing export in this slice; it does not trigger StardewXnbHack's full-content unpack automatically.")}),
      ]}),
      stardewModLoaderSection(),
      detailSection({title: "LOADER STATUS", body: [
        detailField({label: "SMAPI", control: read(loader.smapi ? "Installed" : "Not found")}),
        detailField({label: "CONTENT PATCHER", control: read(contentPatcherState)}),
      ]}),
      detailSection({title: "PROJECT", body: [
        detailField({label: "FOLDER", control: read(dashboard.project.root)}),
        detailField({label: "DEPLOYMENT", control: read(deployment.externallyChanged ? "Externally changed — blocked" : deployment.managed ? "Lexeditor-managed" : deployment.deployed ? "Unmanaged collision" : "Not deployed")}),
        detailField({label: "TARGET", control: read(deployment.target)}),
        detailField({label: "ACTIONS", control: actions}),
      ]}),
      detailSection({title: "INSTALLED ACCEPTANCE", body: [
        detailField({label: "STATE", control: read(acceptanceState), help: infoHelp("Acceptance proves this exact deployed pack was loaded by SMAPI and Content Patcher, the post-mod Data/Objects export contains the edited values, and the installed Objects.xnb stayed unchanged.")}),
        detailField({label: "TARGET", control: read(`Stardew ${acceptance.targetGameVersion || "1.6.15"}`)}),
        detailField({label: "RUNTIME", control: read(runtime)}),
        detailField({label: "CONTENT PATCHER", control: read(acceptance.contentPatcherSeen ? (acceptance.contentPatcherVersionFromLog ? `Seen · ${acceptance.contentPatcherVersionFromLog}` : "Seen in SMAPI log") : "Not yet seen in a new log")}),
        detailField({label: "LEXEDITOR PACK", control: read(acceptance.projectMentioned ? "Seen in new SMAPI log" : "Not yet seen in a new log")}),
        detailField({label: "OBJECTS.XNB", control: read(acceptance.started ? (acceptance.objectsXnbUnchanged ? "Byte-identical to baseline" : "Changed or missing") : "Baseline not captured")}),
        detailField({label: "SMAPI LOG", control: read(acceptance.smapiLogPath)}),
        ...(acceptance.blockers?.length ? [detailField({label: "BLOCKERS", control: read(acceptance.blockers.join(" · "))})] : []),
        detailField({label: "ACTIONS", control: acceptanceActions}),
      ]}),
      ...(state.error ? [detailSection({title: "ERROR", body: [el("p", {class: "lex-notice lex-tone-warning", role: "alert"}, state.error)]})] : []),
    ]});
}

async function deploymentAction(action) {
  if (state.busy || dirtyCount()) return;
  if (action === "revert" && !(await LexeditorUI.confirmAction({
    title: "Revert Stardew deployment?", message: "Remove only this Lexeditor-managed Content Patcher deployment? The source project is preserved.", confirmLabel: "Revert deployment",
  }))) return;
  state.busy = true; state.error = ""; shell.refresh();
  try {
    state.dashboard.deployment = await api(`/api/deployment/${action}`, {});
    state.dashboard.loader = state.dashboard.deployment.loader;
    state.dashboard.acceptance = await api("/api/acceptance");
  } catch (error) { state.error = error.message; }
  finally { state.busy = false; render(); }
}
async function acceptanceBegin() {
  if (state.busy || dirtyCount()) return;
  const current = state.dashboard.acceptance || {};
  if (current.started && !(await LexeditorUI.confirmAction({
    title: "Reset acceptance baseline?", message: "Replace the existing acceptance baseline? You will need to launch Stardew through SMAPI again.", confirmLabel: "Reset baseline",
  }))) return;
  state.busy = true; state.error = ""; shell.refresh();
  try { state.dashboard.acceptance = await api("/api/acceptance/begin", {}); }
  catch (error) { state.error = error.message; LexeditorUI.showAlert({title: "Could not begin installed acceptance", message: state.error}); }
  finally { state.busy = false; render(); }
}
async function acceptanceVerify() {
  if (state.busy) return;
  state.busy = true; state.error = ""; shell.refresh();
  try { state.dashboard.acceptance = await api("/api/acceptance"); }
  catch (error) { state.error = error.message; LexeditorUI.showAlert({title: "Could not verify installed acceptance", message: state.error}); }
  finally { state.busy = false; render(); }
}
async function save() {
  if (state.busy) return;
  const editingTyped = state.datasetKey !== "objects" && state.dataset;
  const edits = editingTyped ? datasetDiffEdits() : diffEdits();
  if (!edits.length) return;
  state.busy = true; shell.refresh();
  try {
    if (editingTyped) {
      installDataset(await api("/api/datasets/"+encodeURIComponent(state.datasetKey)+"/save", {
        sha256: state.dataset.sha256, edits,
      }));
    } else {
      installObjects(await api("/api/objects/save", {sha256: state.objects.sha256, edits}));
    }
    state.error = "";
  } catch (error) {
    state.error = error.message;
    LexeditorUI.showAlert({title: "Could not save Stardew project", message: state.error});
  } finally { state.busy = false; render(); }
}
async function discard() {
  if (state.datasetKey !== "objects" && state.dataset) {
    installDataset(await api("/api/datasets/"+encodeURIComponent(state.datasetKey)));
  } else {
    installObjects(await api("/api/objects"));
  }
  state.error = ""; render();
}
async function refresh() {
  const requests = [api("/api/dashboard"), api("/api/datamap"), api("/api/objects")];
  if (state.datasetKey !== "objects") requests.push(api("/api/datasets/"+encodeURIComponent(state.datasetKey)));
  const values = await Promise.all(requests);
  state.dashboard = values[0]; state.dataMap = values[1]; installObjects(values[2]);
  if (values[3]) installDataset(values[3]);
}
function mainState(message, error = false) {
  $("#main").replaceChildren(error ? el("p", {class:"lex-notice",role:"alert"},message) : LexeditorUI.loadingPanel({label:message}));
}
function render() {
  if (!state.dashboard) return;
  let content;
  if (state.tab === "datamap") content = dataMapPanel();
  else if (state.tab === "info") content = infoPanel();
  else content = state.datasetKey === "objects" ? objectsPanel() : datasetPanel();
  $("#main").replaceChildren(content);
  shell.refresh();
}
function navigate(tab) {
  state.tab = tab;
  mainState(tab === "datamap" ? "Loading Data Map…" : tab === "info" ? "Loading plugin information…" : "Loading game data…");
  shell.refresh();
  requestAnimationFrame(render);
}

const shell = LexeditorUI.mountShell({
  host: "#lexeditor-shell", brand: "LEXEDITOR",
  plugin: {id: "stardew-valley", name: "Stardew Valley", themeName: "stardew-valley", theme: {accent: "#6cae43"}},
  tabs: [{id: "objects", label: "Data"}], activeTab: () => state.tab, navigate,
  help: () => navigate("datamap"), helpActive: () => state.tab === "datamap", helpTitle: "Open the Stardew Valley Data Map",
  info: () => navigate("info"), infoActive: () => state.tab === "info", infoTitle: "Open Stardew Valley plugin information",
  dirtyCount, readonly: () => state.busy, save, discard,
});
window.addEventListener("focus", () => {
  if (!state.dashboard || state.busy || dirtyCount()) return;
  refresh().then(render).catch(error => { state.error = error.message; render(); });
});
mainState("Loading Stardew Valley project…");
refresh().then(render).then(() => LexeditorUI.finishPluginLoading()).catch(error => {
  mainState(`Failed to load Stardew Valley project: ${error.message}`, true);
  LexeditorUI.finishPluginLoading();
});
