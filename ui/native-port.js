"use strict";

(async () => {
  const plugin = await (await fetch("/api/plugin")).json();
  const UI = LexeditorUI;
  const main = document.querySelector("#main");
  const toolbar = document.querySelector("#toolbar");
  let tab = "settings", state = null, values = {}, saved = {}, map = null;
  let busy = false, problem = "";
  let controlSetup = false, controlProfile = "keep";
  let mapQuery = "", mapStatus = "", mapPage = 0, mapSort = ["filename", 1];
  const copy = value => JSON.parse(JSON.stringify(value));
  const changes = () => Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== saved[key]));
  const dirty = () => Object.keys(changes()).length;
  const readonly = () => busy || !state?.game.supported || state?.game.running;
  const controlsBlocked = () => readonly() || dirty() || !state?.preferences.controls;

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
    const loaded = await api("/api/state");
    if (dirty() || busy) return;
    state = loaded;
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

  async function finishControlSetup() {
    if (controlsBlocked()) return;
    const controls = state.preferences.controls;
    const fingerprint = state.preferences.fingerprint;
    const profile = controlProfile;
    busy = true;
    render();
    try {
      let replaceCustom = false;
      if (profile !== "keep" && controls.selected === "custom") {
        replaceCustom = await UI.confirmAction({title: "Replace custom bindings?",
          message: "This replaces your keyboard and controller bindings with the selected preset.",
          confirmLabel: "Replace bindings", cancelLabel: "Keep my bindings"});
        if (!replaceCustom) return;
      }
      accept(await api("/api/control-setup", {fingerprint, controlsSha256: controls.sha256, profile, replaceCustom}));
      controlSetup = false;
      problem = "";
    } catch (error) { problem = error.message; }
    finally { busy = false; render(); }
  }

  function controlsSection() {
    const controls = state.preferences.controls;
    const button = (label, action) => {
      const control = document.createElement("button");
      control.type = "button"; control.textContent = label;
      control.disabled = controlsBlocked(); control.addEventListener("click", action);
      return control;
    };
    const names = {classic: "Classic Controls", modern: "Modern Controls", custom: "Custom bindings"};
    const body = [UI.detailField({label: "Current controls", control: UI.readonlyField(names[controls.selected] || controls.selected)})];
    if (controlSetup) {
      const select = document.createElement("select");
      select.setAttribute("aria-label", "Control preset"); select.disabled = controlsBlocked();
      for (const [value, label] of [["keep", "Keep current bindings"], ["classic", "Classic Controls"], ["modern", "Modern Controls"]]) {
        const option = document.createElement("option");
        option.value = value; option.textContent = label; select.append(option);
      }
      select.value = controlProfile;
      select.addEventListener("change", () => { controlProfile = select.value; });
      const cancel = button("Cancel", () => { controlSetup = false; render(); });
      cancel.disabled = busy;
      body.push(UI.detailField({label: "Control preset", control: select}),
        UI.actionRow(button("Finish control setup", finishControlSetup), cancel));
    } else {
      body.push(UI.actionRow(button("Run control setup again", () => {
        if (controlsBlocked()) return;
        controlSetup = true; controlProfile = "keep"; render();
      })));
    }
    return UI.detailSection({title: "Controls", help: controls.help ? UI.infoHelp(controls.help) : null, body});
  }

  function field(spec) {
    const control = document.createElement("input");
    control.type = spec.kind === "boolean" ? "checkbox" : "number";
    control.setAttribute("aria-label", spec.label);
    control.disabled = readonly() || controlSetup;
    if (spec.kind === "boolean") control.checked = values[spec.key];
    else {
      control.min = spec.min; control.max = spec.max; control.step = spec.step;
      control.value = values[spec.key];
    }
    control.addEventListener("change", () => {
      control.setCustomValidity(spec.kind !== "boolean" && spec.nonzeroMin && control.valueAsNumber !== 0 && control.valueAsNumber < spec.nonzeroMin
        ? `${spec.label} must be zero or at least ${spec.nonzeroMin}.` : "");
      if (!control.checkValidity()) { control.reportValidity(); return; }
      values[spec.key] = spec.kind === "boolean" ? control.checked : control.valueAsNumber;
      if (state.preferences.controls) render(); else shell.refresh();
    });
    return UI.detailField({label: spec.label, description: spec.help, control});
  }

  function settings() {
    const notices = [];
    if (problem) notices.push(UI.notice({tone: "error", title: "Could not save settings", message: problem}));
    if (!state.game.supported) notices.push(UI.notice({tone: "warning", title: "Set up " + (state.game.runtime?.runtime || plugin.portName),
      message: state.game.runtime?.message || state.game.error || "Choose the " + plugin.portName + " installation on the main menu."}));
    else if (state.game.running) notices.push(UI.notice({tone: "warning", title: plugin.portName + " is running", message: "Settings unlock automatically when the game closes."}));
    const body = [...(state.preferences.controls ? [controlsSection()] : []),
      ...[...new Set(state.preferences.fields.map(spec => spec.section))].map(section =>
        UI.detailSection({title: section, body: state.preferences.fields.filter(spec => spec.section === section).map(field)}))];
    const button = document.createElement("button");
    button.type = "button"; button.textContent = "Refresh";
    button.disabled = busy || dirty(); button.addEventListener("click", () => refresh().catch(showError));
    main.replaceChildren(...notices, UI.detailPanel({title: "Settings", actions: [button], paginate: true, body}));
  }

  function info() {
    main.replaceChildren(UI.detailPanel({className: "lex-information-panel", title: plugin.name, paginate: true, body: [
      UI.detailSection({title: "Installation", body: [
        UI.detailField({label: "Game", control: UI.readonlyField(plugin.gameIdentity)}),
        UI.detailField({label: "Port", control: UI.readonlyField(state.game.root)}),
        ...(state.game.runtime ? [UI.detailField({label: "Port version", control: UI.readonlyField(
          state.game.runtime.installed ? state.game.runtime.pinned || state.game.runtime.version : "Not installed")})] : []),
        UI.detailField({label: "Settings and saves", control: UI.readonlyField(state.game.dataRoot)})
      ]}),
      UI.modLoaderSection(plugin.modLoading),
      UI.creditsPanel(plugin.pluginId)
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
    gameProcessChanged: status => {
      if (!state || state.game.running === status.running) return;
      const stopped = state.game.running && !status.running;
      state.game.running = status.running;
      render();
      if (stopped) refresh().catch(showError);
    },
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
