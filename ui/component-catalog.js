/* The shared UI, organised so it can be browsed.
 *
 * Every component the framework hands out is listed here with the level it
 * belongs to, what it is for, and - where one exists - a live sample. Blank
 * renders this catalogue, and the shared UI contract check fails when a
 * component is exported without being listed, so the catalogue grows with the
 * framework instead of drifting behind it.
 *
 * Levels, in the usual vocabulary for a component library:
 *   atom      one control: a button, a field, a mark.
 *   molecule  a few atoms doing one job: a labelled field, a row of flags.
 *   organism  a whole region: a list, a detail panel, a tab bar, a section.
 *   template  a page shape the games fill in.
 *   utility   not drawn: state, history, formatting, host calls.
 */
(() => {
  const UI = window.LexeditorUI;
  if (!UI) return;
  const el = UI.el;
  const rows = [
    {id: 1, name: "Example Item", category: "Common", value: 25, enabled: true},
    {id: 2, name: "Second Item", category: "Rare", value: 100, enabled: false},
    {id: 3, name: "Null Sword", category: "Weapon", value: 255, enabled: true},
  ];

  const entries = [
    // ---- atoms -----------------------------------------------------------
    {id: "element", level: "atom", summary: "Builds one DOM node. Every other component is made of these.",
      sample: () => el("code", {}, 'element("button", {type: "button"}, "Press")')},
    {id: "el", level: "atom", summary: "The short name for element(), used inside plugins."},
    {id: "newButton", level: "atom", summary: "The standard button.",
      sample: () => el("div", {class: "lex-reshade-actions"},
        UI.newButton({label: "Do the thing"}))},
    {id: "closeButton", level: "atom", summary: "The mark that dismisses a dialog or panel.",
      sample: () => UI.closeButton({onclick: () => {}})},
    {id: "readonlyField", level: "atom", summary: "A value that can be read and copied but not changed.",
      sample: () => UI.readonlyField("Cannot be edited here")},
    {id: "booleanMark", level: "atom", summary: "Yes or no, as a mark rather than a word.",
      sample: () => el("div", {class: "lex-reshade-actions"}, UI.booleanMark(true), UI.booleanMark(false))},
    {id: "recordId", level: "atom", summary: "A record's own id, formatted the same way everywhere.",
      sample: () => UI.recordId(7)},
    {id: "infoIcon", level: "atom", summary: "The information glyph used by help controls.",
      sample: () => UI.infoIcon()},
    {id: "infoHelp", level: "atom", summary: "A help bubble that explains one control in one sentence.",
      sample: () => el("div", {class: "lex-reshade-actions"}, el("span", {}, "Power"),
        UI.infoHelp("How hard the attack hits."))},
    {id: "unitField", level: "atom", summary: "A number with its unit kept beside it.",
      sample: () => UI.unitField(el("input", {type: "number", value: "60"}), "fps")},
    {id: "magnitudeValue", level: "atom", summary: "A number scaled for reading: 12.4k rather than 12,431.",
      sample: () => el("div", {class: "lex-reshade-actions"}, UI.magnitudeValue(12431), UI.magnitudeValue(980))},
    {id: "numberValue", level: "atom", summary: "A number formatted for a table cell.",
      sample: () => UI.numberValue(1250)},
    {id: "formatNumber", level: "atom", summary: "Shared number formatting, so no plugin invents its own.",
      sample: () => el("code", {}, "formatNumber(1234567) is " + UI.formatNumber(1234567))},
    {id: "saveIcon", level: "atom", summary: "The save glyph used by the shell.", sample: () => UI.saveIcon()},
    {id: "searchIcon", level: "atom", summary: "The search glyph.", sample: () => UI.searchIcon()},
    {id: "settingsIcon", level: "atom", summary: "The settings glyph.", sample: () => UI.settingsIcon()},
    {id: "folderIcon", level: "atom", summary: "The folder glyph.", sample: () => UI.folderIcon()},
    {id: "enabledMark", level: "atom", summary: "The mark on the shared list's enabled column.",
      sample: () => UI.enabledMark()},
    {id: "copyText", level: "atom", summary: "Copies a value to the clipboard and says so.",
      sample: () => UI.newButton({label: "Copy a value", onclick: () => UI.copyText("Example Item")})},
    {id: "hoverable", level: "atom", summary: "A value that links to the record it names.",
      sample: () => UI.hoverable({label: "Example Item", targetLabel: "Example Item", open: () => {}})},

    // ---- molecules -------------------------------------------------------
    {id: "detailField", level: "molecule", summary: "One property: label, control, help, and its changed state.",
      sample: () => UI.detailField({label: "POWER", control: UI.readonlyField("128"),
        help: UI.infoHelp("Damage before defence.")})},
    {id: "detailRow", level: "molecule", summary: "The same field under another name, for rows outside a section.",
      sample: () => UI.detailRow({label: "LEVEL", control: UI.readonlyField("42")})},
    {id: "detailNote", level: "molecule", summary: "A sentence inside a section that is not a property.",
      sample: () => UI.detailNote("Nothing in this section applies to this record.")},
    {id: "toggleRow", level: "molecule", summary: "A row of on/off flags that wraps instead of stretching.",
      sample: () => UI.toggleRow({toggles: [
        {key: "menu", label: "Menu", checked: true, change: () => {}},
        {key: "battle", label: "Battle", checked: false, change: () => {}},
        {key: "field", label: "Field", checked: true, change: () => {}}]})},
    {id: "multiNumberRow", level: "molecule", summary: "Several numbers that belong together, such as a stat block.",
      sample: () => UI.multiNumberRow([
        {label: "HP", control: el("input", {type: "number", value: "2400"})},
        {label: "STR", control: el("input", {type: "number", value: "24"})},
        {label: "MAG", control: el("input", {type: "number", value: "31"})}])},
    {id: "pager", level: "molecule", summary: "Page controls for a long list.",
      sample: () => UI.pager({page: 1, pages: 4, change: () => {}})},
    {id: "pagerSelect", level: "molecule", summary: "A filter beside the pager.",
      sample: () => UI.pagerSelect({label: "Category", change: () => {},
        options: [{value: "", label: "All categories"}, {value: "rare", label: "Rare"}]})},
    {id: "pagerToggle", level: "molecule", summary: "A switch beside the pager, such as mod contents only.",
      sample: () => UI.pagerToggle({label: "Mod contents only", checked: false, change: () => {}})},
    {id: "controlHelp", level: "molecule", summary: "The help text attached to a control a page built itself.",
      sample: () => {
        const box = el("input", {type: "text", value: "Typed value", title: "What this box is for."});
        UI.controlHelp(box);
        return box;
      }},
    {id: "provenanceControl", level: "molecule", summary: "A value with what the game shipped, and any reference mods, beside it.",
      sample: () => UI.provenanceControl({control: el("input", {type: "number", value: "40"}),
        current: () => 40, vanilla: 25, apply: () => {},
        references: [{name: "Reference mod", shortName: "R", value: 32}]})},
    {id: "referenceDisplay", level: "molecule", summary: "Shows the same value in other mods, for comparison.",
      sample: () => UI.referenceDisplay({current: 40, sources: [{name: "Vanilla", shortName: "V", value: 25},
        {name: "Reference mod", shortName: "R", value: 32}]})},
    {id: "integrationStatus", level: "molecule", summary: "How far Lexeditor understands one game file.",
      sample: () => el("div", {class: "lex-reshade-actions"}, UI.integrationStatus("integrated"),
        UI.integrationStatus("partial"), UI.integrationStatus("not-integrated"))},
    {id: "settingsSaveControl", level: "molecule", summary: "The save button for a settings page, with its pending count.",
      sample: () => UI.settingsSaveControl({dirtyCount: () => 2,
        pendingChanges: () => ["Sample setting", "Another setting"]})},
    {id: "uiScaleControl", level: "molecule", summary: "The interface scale slider in the window bar.",
      sample: () => UI.uiScaleControl()},
    {id: "bottomSearch", level: "molecule", summary: "The search bar that sits under a list.",
      sample: () => UI.bottomSearch({key: "lex-sample-search", label: "Search records", value: "", change: () => {}})},
    {id: "decorateSearchCandidate", level: "molecule", summary: "Marks a row as a search candidate while typing.",
      sample: () => {
        const row = el("div", {class: "lex-sample-candidate"}, "Example Item");
        UI.decorateSearchCandidate(row, {query: "exam"});
        return row;
      }},

    // ---- organisms -------------------------------------------------------
    {id: "columnList", level: "organism", summary: "The shared list: columns, sorting, selection, pinning, the pointer.",
      sample: () => UI.columnList({rows, key: row => row.id, selected: 2, select: () => {},
        sortState: {key: "name", dir: 1}, sort: () => {}, enabledChange: () => {},
        columns: [{key: "id", label: "ID"}, {key: "name", label: "Name"},
          {key: "category", label: "Category"}, {key: "value", label: "Value", numeric: true}]})},
    {id: "detailPanel", level: "organism", summary: "The panel one record is edited in, with its heading and identity.",
      sample: () => UI.detailPanel({title: "Example Item", body: [UI.detailSection({title: "ITEM",
        body: [UI.detailField({label: "VALUE", control: UI.readonlyField("25")})]})]})},
    {id: "detailSection", level: "organism", summary: "A titled group of fields inside a panel.",
      sample: () => UI.detailSection({title: "GROUP", body: [
        UI.detailField({label: "NAME", control: UI.readonlyField("Example Item")}),
        UI.detailField({label: "CATEGORY", control: UI.readonlyField("Common")}),
        UI.detailField({label: "VALUE", control: UI.readonlyField("25")}),
      ]})},
    {id: "detailGroup", level: "organism", summary: "The same section under another name, for fields that group rather than title.",
      sample: () => UI.detailGroup({title: "RESISTANCES", body: [
        UI.detailField({label: "FIRE", control: UI.readonlyField("0")}),
        UI.detailField({label: "ICE", control: UI.readonlyField("100")}),
      ]})},
    {id: "subtabBar", level: "organism", summary: "One level of tabs inside a page.",
      sample: () => UI.subtabBar({label: "Sample views", active: "one", change: () => {},
        tabs: [{id: "one", label: "ONE"}, {id: "two", label: "TWO"}]})},
    {id: "tabbedPanel", level: "organism", summary: "A panel whose body switches between tabs."},
    {id: "modLoaderSection", level: "organism", summary: "How this game loads mods, in the same five fields for every game.",
      sample: () => UI.modLoaderSection({loader: "Sample loader beside the game.",
        output: "Sample output folder.", order: "Sample load order.",
        safety: "Nothing of the game's own is written.", removal: "Delete the folder."})},
    {id: "reshadeSection", level: "organism", summary: "ReShade for one game: the switch, each effect and its controls.",
      // Its own sample state, so the section draws in full here whether or not
      // this machine has ReShade in a game.
      sample: () => UI.reshadeSection({act: () => {}, snapshot: {
        available: true, installed: true, gameFound: true, developerMode: true,
        hasDefaults: true, renderer: "dxgi", error: "",
        effects: [
          {id: "Colors", file: "Colors.fx", label: "Colors", tooltip: "Brightness, contrast, saturation, vibrance and gamma.",
           enabled: true, values: {Brightness: 0.1, Saturation: 0, Gamma: 1},
           controls: [
             {name: "Brightness", type: "float", widget: "slider", label: "Brightness", min: -1, max: 1, step: 0.01, default: 0, tooltip: "Lightens or darkens everything."},
             {name: "Saturation", type: "float", widget: "slider", label: "Saturation", min: -1, max: 1, step: 0.01, default: 0, tooltip: "How strong the colours are."},
             {name: "Gamma", type: "float", widget: "slider", label: "Gamma", min: 0.5, max: 2, step: 0.01, default: 1, tooltip: "Midtones only."}]},
          {id: "Vignette", file: "Vignette.fx", label: "Vignette", tooltip: "Darkens the edges of the screen.",
           enabled: false, values: {Amount: 0.4, Shape: 0},
           controls: [
             {name: "Amount", type: "float", widget: "slider", label: "Amount", min: 0, max: 1, step: 0.01, default: 0.4, tooltip: "How dark the edges get."},
             {name: "Shape", type: "int", widget: "combo", label: "Shape", items: ["Round", "Screen-shaped"], default: 0, tooltip: "A circle or an oval."}]},
        ]}})},
    {id: "creditsPanel", level: "organism", summary: "Who made what, from the generated credits.",
      sample: () => UI.creditsPanel("blank")},
    {id: "dataMap", level: "organism", summary: "Which of a game's files Lexeditor understands."},
    {id: "curveEditor", level: "organism", summary: "A formula drawn as a curve, edited by its terms."},
    {id: "soundCoverageTable", level: "organism", summary: "Which interface sounds a theme provides.",
      sample: () => UI.soundCoverageTable([{event: "save", label: "Save", provided: true},
        {event: "back", label: "Back", provided: false}])},
    {id: "platformConfigView", level: "organism", summary: "A game runtime's own configuration file, edited safely."},
    {id: "settingsColumns", level: "organism", summary: "Settings cards laid out in columns that reflow.",
      sample: () => UI.settingsColumns([
        UI.detailSection({title: "ONE", body: [UI.detailField({label: "FIELD", control: UI.readonlyField("value")})]}),
        UI.detailSection({title: "TWO", body: [UI.detailField({label: "FIELD", control: UI.readonlyField("value")})]}),
        UI.detailSection({title: "THREE", body: [UI.detailField({label: "FIELD", control: UI.readonlyField("value")})]}),
      ])},
    {id: "paginateSettings", level: "organism", summary: "Splits a long settings page into pages.",
      sample: () => UI.paginateSettings(el("div", {},
        ...Array.from({length: 8}, (_value, index) => UI.detailSection({title: `SECTION ${index + 1}`,
          body: [UI.detailField({label: "FIELD", control: UI.readonlyField(String(index))})]}))))},
    {id: "columnPreferences", level: "organism", summary: "Which columns a list shows, and in what order.",
      sample: () => {
        const prefs = UI.columnPreferences("lex-sample-columns", [{key: "id", label: "ID"},
          {key: "name", label: "Name"}, {key: "value", label: "Value"}]);
        return el("div", {class: "lex-reshade-actions"},
          ...prefs.all().map(column => el("span", {class: "lex-pinnable-property"},
            prefs.pinButton(column.key, column.label), el("span", {}, column.label))));
      }},
    {id: "showAlert", level: "organism", summary: "Lexeditor's own message box. Never the browser's.",
      sample: () => UI.newButton({label: "Show a message", onclick: () => UI.showAlert(
        {title: "Sample message", message: "This is the shared message box."})})},
    {id: "showToast", level: "organism", summary: "A short message that fades by itself.",
      sample: () => UI.newButton({label: "Show a toast", onclick: () => UI.showToast("Saved.")})},
    {id: "confirmAction", level: "organism", summary: "Lexeditor's own yes/no question.",
      sample: () => UI.newButton({label: "Ask a question", onclick: () => UI.confirmAction(
        {title: "Do the thing?", message: "Nothing happens either way here.", confirmLabel: "Do it"})})},
    {id: "confirmDiscardChanges", level: "organism", summary: "Asks before throwing away edits.",
      sample: () => UI.newButton({label: "Discard edits", onclick: () => UI.confirmDiscardChanges(
        {dirtyCount: () => 3, discard: async () => {}})})},
    {id: "confirmUnsavedExit", level: "organism", summary: "Asks before leaving with unsaved edits.",
      sample: () => UI.newButton({label: "Leave with edits", onclick: () => UI.confirmUnsavedExit(
        {dirtyCount: () => 2, save: async () => {}}, async () => true,
        {question: "Save before leaving this sample?"})})},
    {id: "openSettings", level: "organism", summary: "The shared settings dialog.",
      sample: () => UI.newButton({label: "Open settings", onclick: () => UI.openSettings()})},
    {id: "sharedSettings", level: "organism", summary: "The settings every game has in common, as this page sees them.",
      sample: () => UI.readonlyField(JSON.stringify(UI.sharedSettings() || {}).slice(0, 120) || "No settings loaded here.")},
    {id: "openGameFolder", level: "organism", summary: "Opens this game's folder in the file browser.",
      sample: () => UI.newButton({label: "Open the game folder", onclick: () => UI.openGameFolder("blank")})},

    // ---- templates -------------------------------------------------------
    {id: "mountShell", level: "template", summary: "The window: brand, tabs, project selector, save, play, history. Everything above this page is it."},
    {id: "panelLayout", level: "template", summary: "One, two or three resizable panes across a page."},
    {id: "list", level: "organism", summary: "A plain list of rows, without columns."},
    {id: "listDetail", level: "template", summary: "A list beside the detail of the selected row."},
    {id: "masterDetail", level: "template", summary: "The older list and detail shape, kept for existing pages."},
    {id: "pagedListDetail", level: "template", summary: "List, detail, search and paging as one page.",
      sample: () => UI.pagedListDetail({rows, key: row => row.id, selected: 1, page: 0, pageSize: 10,
        noun: "records", splitKey: "lex-sample-paged", rowsKey: "lex-sample-paged",
        change: () => {}, sync: () => {},
        master: ({rows: listed, selected, select}) => UI.columnList({rows: listed, key: row => row.id,
          selected, select, template: "60px minmax(120px,1fr)",
          columns: [{key: "id", label: "ID"}, {key: "name", label: "Name"}]}),
        detail: row => UI.detailPanel({title: row.name, body: [UI.detailSection({title: "RECORD",
          body: [UI.detailField({label: "VALUE", control: UI.readonlyField(String(row.value))})]})]})})},
    {id: "fitListPage", level: "template", summary: "Chooses how many rows fit the page height. The list to the left is sized by it."},
    {id: "installWindowFrame", level: "template", summary: "The window buttons and the regions that drag it. The bar at the top of this window is it."},
    {id: "createWindowActions", level: "template", summary: "Minimise, maximise and close, wired to the host. Top right of this window."},
    {id: "applyTheme", level: "template", summary: "Applies a game's tokens. Tokens only, never geometry: Blank's green is this.",
      sample: () => UI.readonlyField("This page's accent, panel and text colours come from applyTheme.")},
    {id: "finishPluginLoading", level: "template", summary: "Clears the loading screen once a page is ready. The screen you saw opening this one."},

    // ---- utilities -------------------------------------------------------
    {id: "callWindow", level: "utility", summary: "Calls the desktop host from a page."},
    {id: "clone", level: "utility", summary: "A deep copy, for keeping an untouched baseline."},
    {id: "EditHistory", level: "utility", summary: "Undo and redo over a page's own state."},
    {id: "NavigationHistory", level: "utility", summary: "Back and forward between tabs."},
    {id: "installBrowserHistoryGuard", level: "utility", summary: "Keeps the browser's own back button in step."},
    {id: "installExtendedMouseHistory", level: "utility", summary: "The mouse's back and forward buttons."},
    {id: "installControlHelp", level: "utility", summary: "Attaches help to controls a page built itself."},
    {id: "bindSettingDependencies", level: "utility", summary: "Disables settings whose dependency is off."},
    {id: "hasEnabledProperty", level: "utility", summary: "Whether a record carries an enabled flag."},
    {id: "refreshReferences", level: "utility", summary: "Re-reads reference mods after a change."},
    {id: "autoFitControlText", level: "utility", summary: "Shrinks text to fit a fixed control."},
    {id: "beginSearcher", level: "utility", summary: "Starts a hold-to-search interaction."},
    {id: "finishSearcher", level: "utility", summary: "Ends one."},
    {id: "playThemeSound", level: "utility", summary: "Plays one interface sound from the active theme."},
    {id: "configureThemeSounds", level: "utility", summary: "Sets which interface sounds a theme uses."},
  ];

  window.LexeditorComponentCatalog = {
    levels: [
      {id: "atom", label: "Atoms", summary: "One control: a button, a field, a mark."},
      {id: "molecule", label: "Molecules", summary: "A few atoms doing one job."},
      {id: "organism", label: "Organisms", summary: "A whole region: a list, a panel, a section."},
      {id: "template", label: "Templates", summary: "A page shape the games fill in."},
      {id: "utility", label: "Utilities", summary: "Not drawn: state, history, formatting, host calls."},
    ],
    entries,
  };
})();
