"use strict";

(async () => {
  const plugin = await (await fetch("/api/plugin")).json();
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
    if (!response.ok) throw new Error(result.error || "Native port request failed");
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
    control.setAttribute("aria-label", spec.label);
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
    if (!state.game.supported) notices.push(UI.notice({tone: "warning", title: "Locate " + plugin.portName, message: "Choose the " + plugin.portName + " installation on the main menu."}));
    else if (state.game.running) notices.push(UI.notice({tone: "warning", title: plugin.portName + " is running", message: "Close the game, then refresh this page before changing settings."}));
    const body = [...new Set(state.preferences.fields.map(spec => spec.section))].map(section =>
      UI.detailSection({title: section, body: state.preferences.fields.filter(spec => spec.section === section).map(field)}));
    const button = document.createElement("button");
    button.type = "button"; button.textContent = "Refresh";
    button.disabled = busy || dirty(); button.addEventListener("click", () => refresh().catch(showError));
    main.replaceChildren(...notices, UI.detailPanel({title: "Settings", actions: [button], paginate: true, body}));
  }

  function info() {
    main.replaceChildren(UI.detailPanel({title: plugin.name, paginate: true, body: [
      UI.detailSection({title: "Installation", body: [
        UI.detailField({label: "Game", control: UI.readonlyField(plugin.gameIdentity)}),
        UI.detailField({label: "Port", control: UI.readonlyField(state.game.root)}),
        UI.detailField({label: "Settings and saves", control: UI.readonlyField(state.game.dataRoot)})
      ]}),
      UI.modLoaderSection(plugin.modLoading)
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
    plugin: {id: plugin.pluginId, name: plugin.name, theme: {accent: plugin.accent}},
    tabs: [{id: "settings", label: "Settings", help: "Changes the port's saved controls. Close the game before saving so it cannot replace your changes."}],
    activeTab: () => tab, navigate, readonly, dirtyCount: dirty, save,
    discard: async () => { values = copy(saved); problem = ""; render(); },
    pendingChanges: () => UI.pendingChangeList(saved, values, "Settings"),
    info: () => navigate("info"), infoActive: () => tab === "info",
    help: () => navigate("datamap"), helpActive: () => tab === "datamap",
    helpTitle: "Open " + plugin.name + " Data Map"});
  addEventListener("focus", () => refresh().catch(showError));
  Promise.all([api("/api/state"), api("/api/datamap")]).then(([loaded, mapping]) => {
    state = loaded; map = mapping; accept(state.preferences); render(); UI.finishPluginLoading();
  }).catch(error => {main.replaceChildren(UI.notice({tone: "error", title: "Could not open " + plugin.name, message: error.message})); UI.finishPluginLoading();});
})().catch(error => {
  document.querySelector("#main").replaceChildren(LexeditorUI.notice({tone: "error", title: "Could not open settings", message: error.message}));
  LexeditorUI.finishPluginLoading();
});
