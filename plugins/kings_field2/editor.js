"use strict";

(() => {
  const UI = LexeditorUI;
  const main = document.querySelector("#main");
  const toolbar = document.querySelector("#toolbar");
  let tab = "settings", state = null, values = {}, saved = {}, map = null;
  let busy = false, problem = "";
  let mapQuery = "", mapStatus = "", mapPage = 0, mapSort = ["filename", 1];
  const copy = value => JSON.parse(JSON.stringify(value));
  const changes = () => Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== saved[key]));
  const dirty = () => Object.keys(changes()).length;
  const readonly = () => busy || !state?.game.supported || state?.game.running;

  async function api(path, payload) {
    const response = await fetch(path, payload === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Verdite2 request failed");
    return result;
  }

  function accept(preferences) {
    state.preferences = preferences;
    values = Object.fromEntries(preferences.fields.map(field => [field.key, field.value]));
    saved = copy(values);
  }

  async function refresh() {
    if (dirty() || busy) return;
    state = await api("/api/state");
    accept(state.preferences);
    problem = "";
    render();
  }

  async function save() {
    if (readonly()) return;
    busy = true;
    shell.refresh();
    try {
      accept(await api("/api/preferences", {changes: changes(), fingerprint: state.preferences.fingerprint}));
      problem = "";
    } catch (error) { problem = error.message; throw error; }
    finally { busy = false; render(); }
  }

  function field(spec) {
    const control = document.createElement("input");
    control.type = spec.kind === "boolean" ? "checkbox" : "number";
    control.disabled = readonly();
    if (spec.kind === "boolean") control.checked = values[spec.key];
    else {
      control.min = spec.min; control.max = spec.max; control.step = spec.step;
      control.value = values[spec.key];
    }
    control.addEventListener("change", () => {
      if (!control.checkValidity()) { control.reportValidity(); return; }
      values[spec.key] = spec.kind === "boolean" ? control.checked : control.valueAsNumber;
      shell.refresh();
    });
    return UI.detailField({label: spec.label, description: spec.help, control});
  }

  function settings() {
    const notices = [];
    if (problem) notices.push(UI.notice({tone: "error", title: "Could not save settings", message: problem}));
    if (!state.game.supported) notices.push(UI.notice({tone: "warning", title: "Set up Lexer's Verdite2 fork",
      message: state.game.fork.message || "Choose the fork installation for King's Field II on the main menu."}));
    else if (state.game.running) notices.push(UI.notice({tone: "warning", title: "Verdite2 is running", message: "Close the game, then refresh this page before changing settings."}));
    const body = [...new Set(state.preferences.fields.map(spec => spec.section))].map(section =>
      UI.detailSection({title: section, body: state.preferences.fields.filter(spec => spec.section === section).map(field)}));
    const button = document.createElement("button");
    button.type = "button"; button.textContent = "Refresh";
    button.disabled = busy || dirty(); button.addEventListener("click", () => refresh().catch(showError));
    main.replaceChildren(...notices, UI.detailPanel({title: "Settings", actions: [button], paginate: true, body}));
  }

  function info() {
    main.replaceChildren(UI.detailPanel({title: "King's Field II", paginate: true, body: [
      UI.detailSection({title: "Installation", body: [
        UI.detailField({label: "Game", control: UI.readonlyField("Japanese King's Field II / US King's Field, SLUS-00158")}),
        UI.detailField({label: "Port", control: UI.readonlyField(state.game.root)}),
        UI.detailField({label: "Port version", control: UI.readonlyField(state.game.fork.installed ? state.game.fork.pinned : "Not installed")}),
        UI.detailField({label: "Settings and saves", control: UI.readonlyField(state.game.dataRoot)})
      ]}),
      UI.modLoaderSection({loader: "Verdite2 / RecompOne compiles source mods and attaches their native hooks. Play starts the pinned fork launcher.",
        output: "Each mod has a folder with mod.json and C# source. Enabled mods receive owned copies in the port's mods folder.",
        order: "Native dependencies and IDs decide mod load order. The library list order does not change it.",
        safety: "Mod deployment preserves game binaries, discs, memory cards and separately installed native mods.",
        removal: "Disable it in Mods with the game closed. Lexeditor removes its deployed copy and switches off its native flag."})
    ]}));
  }

  function dataMap() {
    const view = UI.dataMap({rows: map.rows, query: mapQuery, status: mapStatus, page: mapPage, sort: mapSort,
      open: row => { if (row.target === "mods") shell.nav.querySelector('[data-tab="mods"]')?.click(); else if (row.target) navigate(row.target); },
      changeQuery: value => {mapQuery = value; mapPage = 0; render();},
      changeStatus: value => {mapStatus = value; mapPage = 0; render();},
      changePage: value => {mapPage = value; render();},
      changeSort: key => {mapSort = [key, mapSort[0] === key ? -mapSort[1] : 1]; render();}
    });
    toolbar.replaceChildren(view.controls); main.replaceChildren(view.content); mapPage = view.page;
  }

  function navigate(value) { tab = value; render(); }
  function showError(error) { problem = error.message; render(); }
  function render() {
    if (!state) return;
    toolbar.replaceChildren(); toolbar.hidden = tab !== "datamap";
    if (tab === "info") info(); else if (tab === "datamap") dataMap(); else settings();
    shell.refresh();
  }

  const shell = UI.mountShell({host: "#lexeditor-shell", brand: "LEXEDITOR",
    plugin: {id: "kings-field2", name: "King's Field II", theme: {accent: "#b5a05d"}},
    tabs: [{id: "settings", label: "Settings", help: "Changes the port's saved controls. Close Verdite2 before saving so it cannot replace your changes."}],
    activeTab: () => tab, navigate, readonly, dirtyCount: dirty, save,
    discard: async () => { values = copy(saved); problem = ""; render(); },
    pendingChanges: () => UI.pendingChangeList(saved, values, "Settings"),
    info: () => navigate("info"), infoActive: () => tab === "info",
    help: () => navigate("datamap"), helpActive: () => tab === "datamap",
    helpTitle: "Open King's Field II Data Map"});
  addEventListener("focus", () => refresh().catch(showError));
  Promise.all([api("/api/state"), api("/api/datamap")]).then(([loaded, mapping]) => {
    state = loaded; map = mapping; accept(state.preferences); render(); UI.finishPluginLoading();
  }).catch(error => {main.replaceChildren(UI.notice({tone: "error", title: "Could not open King's Field II", message: error.message})); UI.finishPluginLoading();});
})();
