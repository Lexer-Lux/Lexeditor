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
  // A sample that opens something needs a button that says what it opens. The
  // add button is a plus and takes no words, so every dialog sample looked like
  // the same anonymous square.
  const sampleButton = (label, onclick) =>
    el("button", {type: "button", class: "lex-dialog-action", onclick}, label);
  const rows = [
    {id: 1, name: "Example Item", category: "Common", value: 25, enabled: true},
    {id: 2, name: "Second Item", category: "Rare", value: 100, enabled: false},
    {id: 3, name: "Null Sword", category: "Weapon", value: 255, enabled: true},
  ];

  const entries = [
    // ---- atoms -----------------------------------------------------------
    {id: "element", level: "utility", summary: "document.createElement with the boring parts done: attributes, event handlers, children, and nulls skipped. Not a component - the thing every component is built out of.",
      sample: () => el("div", {class: "lex-reshade-actions"},
        el("button", {type: "button", class: "lex-dialog-action", onclick: () => {}}, "A button it made"),
        el("span", {}, "and a span"))},
    {id: "el", level: "utility", summary: "The same function as element. Plugins destructure it under the short name."},
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
    {id: "magnifyIcon", level: "atom", summary: "The magnifier glyph that opens a map at full size.", sample: () => UI.magnifyIcon()},
    {id: "settingsIcon", level: "atom", summary: "The settings glyph.", sample: () => UI.settingsIcon()},
    {id: "folderIcon", level: "atom", summary: "The folder glyph.", sample: () => UI.folderIcon()},
    {id: "enabledMark", level: "atom", summary: "The mark on the shared list's enabled column.",
      sample: () => UI.enabledMark()},
    {id: "copyText", level: "atom", summary: "Copies a value to the clipboard and says so.",
      sample: () => sampleButton("Copy a value", () => UI.copyText("Example Item"))},
    {id: "hoverable", level: "atom", summary: "A value that links to the record it names.",
      sample: () => UI.hoverable({label: "Example Item", targetLabel: "Example Item", open: () => {}})},
    {id: "renameValue", level: "atom", summary: "A value a developer renames in place: the text becomes an input, and Enter hands the new name to the caller.",
      sample: () => {const value = el("span", {}, "Example Item");
        return el("div", {}, value, el("button", {onclick: () => UI.renameValue(value, {label: "example"})}, "Rename it"));}},

    // ---- molecules -------------------------------------------------------
    {id: "detailField", level: "molecule", summary: "One property: label, control, help, and its changed state.",
      sample: () => UI.detailField({label: "POWER", control: UI.readonlyField("128"),
        help: UI.infoHelp("Damage before defence.")})},
    {id: "detailRow", level: "molecule", summary: "One property row holding any mix of parts - numbers, choices, switches. Every box in a column starts at the same place.",
      sample: () => el("div", {}, UI.detailRow({label: "DAMAGE", controls: [
          {label: "Min", control: el("input", {type: "number", value: "12"})},
          {label: "Max", control: el("input", {type: "number", value: "48"})}]}),
        UI.detailRow({label: "BEHAVIOUR", controls: [
          {label: "Power", control: el("input", {type: "number", value: "128"})},
          {label: "Ranged", control: el("input", {type: "checkbox", checked: true})}]}))},
    {id: "pendingChangeList", level: "utility", summary: "The list of unsaved changes a save button shows before it saves."},
    {id: "panelIcon", level: "utility", summary: "A panel's icon box, for a page that draws a preview into it."},
    {id: "sectionParts", level: "utility", summary: "The title and content of a section, by name, for a page that rearranges one."},
    {id: "shellTextNodes", level: "utility", summary: "Every piece of the shell's own text, for a game that redraws it in its own font."},
    {id: "dismissDialogs", level: "utility", summary: "Closes any shared dialog that is open."},
    {id: "gameCard", level: "atom", summary: "A game as the home screen shows it: its cover (or initial) over its name; faded when not involved.",
      sample: () => UI.actionRow(UI.gameCard({name: "Final Fantasy VIII"}), UI.gameCard({name: "Red Dead Redemption 2", faded: true}))},
    {id: "pagedPane", level: "organism", summary: "A table that is its own pane, with its pager under it.",
      sample: () => UI.pagedPane(UI.columnList({rows, key: row => row.id, columns: [
        {key:"id",label:"ID"},{key:"name",label:"Name"}]}),
        UI.pager({page:0,pages:1,total:rows.length,pageSize:rows.length,change:()=>{}}))},
    {id: "badge", level: "atom", summary: "A short status beside a record heading.",
      sample: () => UI.badge("Project", {tone:"success"})},
    {id: "instructionList", level: "organism", summary: "Instruction rows with controls, explanations, drag handles and a fitted page above a fixed footer."},
    {id: "curveGrid", level: "organism", summary: "Graphs side by side, as many to a row as fit at a readable width."},
    {id: "componentSample", level: "utility", summary: "The component catalogue's frame for one live sample."},
    {id: "toolbar", level:"molecule", summary:"A row of page controls.", sample:()=>UI.toolbar(UI.readonlyField("Current table"))},
    {id: "textArea", level:"atom", summary:"An editable text block.", sample:()=>UI.textArea({value:"Example description",rows:2})},
    {id: "tileGrid",level:"template",summary:"A responsive grid of shared fields, sections, or cards.",sample:()=>UI.tileGrid([UI.detailSection({title:"First",body:"First value"}),UI.detailSection({title:"Second",body:"Second value"})])},
    {id: "inlineLabel",level:"molecule",summary:"A name with inline icons at one shared size.",sample:()=>UI.inlineLabel(UI.infoIcon(),"Example item")},
    {id: "choiceField",level:"molecule",summary:"A value with a separate selection action.",sample:()=>UI.choiceField("Potion",el("button",{},UI.selectionIcon()))},
    {id: "statCard",level:"molecule",summary:"An image card with directional ranks and corner controls.",sample:()=>UI.statCard({ranks:["8","5","3","6"].map(value=>el("button",{},value)),corner:el("button",{},"+"),footer:"70"})},
    {id: "choicePopover",level:"molecule",summary:"An accessible menu of named choices.",sample:()=>{const menu=UI.choicePopover({choices:[{value:1,label:"First"},{value:2,label:"Second"}]});const button=el("button",{onclick:()=>menu.openFor(button)},"Choose");return button;}},
    {id: "mathFormula", level:"atom", summary:"A mathematical expression with fractions and powers.", sample:()=>UI.mathFormula("HP(L)=C+L*A+floor(10*L^2/B)")},
    {id: "controlGroup", level:"molecule", summary:"Any set of controls with aligned labels.", sample:()=>UI.controlGroup([{label:"Name",control:el("input",{value:"Potion"})},{label:"Count",control:el("input",{type:"number",min:0,max:99,value:2})}])},
    {id: "stack", level: "template", summary: "A bar over the content it switches: the bar keeps its height, the content takes the rest."},
    {id: "bitmapText", level: "atom", summary: "Text in a game's own bitmap font, one masked glyph per character from --lex-bitmap-atlas."},
    {id: "imageMap", level: "organism", summary: "An image with selectable cells and point markers.", sample:()=>UI.imageMap({columns:4,rows:3,cells:Array.from({length:12},(_,id)=>({id,label:`Cell ${id+1}`,selected:id===3})),points:[{x:.5,y:.5,label:"Point"}]})},
    {id: "mapMagnifier", level: "organism", summary: "The magnifier a map carries: the same map at the size of the window, with a crosshair and a live readout.", sample:()=>UI.imageMap({fill:false,columns:4,rows:3,label:"Map with a magnifier",points:[{x:.5,y:.5,label:"Point"}],magnify:()=>({fill:false,columns:4,rows:3,label:"Map with a magnifier",points:[{x:.5,y:.5,label:"Point"}],readout:point=>`cell ${point.column}, ${point.row}`,place:()=>{}})})},
    {id: "modelStage", level: "organism", summary: "A turnable model's stage: the canvas a renderer draws into and the message shown until it has.",
      sample: () => UI.modelStage({message: "This item has no inventory mesh."})},
    {id: "iconSlot", level: "atom", summary: "What fills a detail heading's icon box: a picture, a small stage, or a line saying why there is neither.",
      sample: () => UI.iconSlot({message: "No mesh"})},
    {id: "figureGrid", level: "organism", summary: "Pictures side by side, each over its caption.",
      sample: () => UI.figureGrid([{media: UI.modelStage({message: "Sword"}), caption: "Sword"}, {media: UI.modelStage({message: "Shield"}), caption: "Shield"}])},
    {id: "treeGraph", level: "organism", summary: "Records joined by arrows on a stage the game lays out; pressing a node selects it.",
      sample: () => UI.treeGraph({width: 400, height: 170, selected: "recruit",
        nodes: [{id: "recruit", x: 200, y: 135, label: "Recruit", sub: "recruit"}, {id: "footman", x: 200, y: 35, label: "Footman", sub: "footman"}],
        edges: [{from: "recruit", to: "footman"}]})},
    {id: "codeField", level: "atom", summary: "An expression or a source line, edited as text in a monospace box.",
      sample: () => UI.codeField({value: "itp_type_one_handed_wpn|itp_primary"})},
    {id: "logView", level: "atom", summary: "A log's text as it was written.",
      sample: () => UI.logView("Build verified: 412 items, 3 troop trees.")},
    {id: "detailText", level: "atom", summary: "Prose in a section, keeping the author's line breaks.",
      sample: () => UI.detailText("Set graphics properly:\nTurn HDR off and antialiasing up.")},
    {id: "quantityChoice", level: "molecule", summary: "A choice and how many of it, as one value: an item and its count.",
      sample: () => UI.quantityChoice(UI.element("select", {}, UI.element("option", {}, "Potion")), UI.element("input", {type: "number", value: 3, min: 0, max: 99}))},
    {id: "iconValue", level: "molecule", summary: "An icon and its name that toggle a state (immune or not), beside the value that applies otherwise.",
      sample: () => UI.iconValue({icon: UI.infoIcon(), label: "Fire", toggle: UI.element("input", {type: "checkbox"}), control: UI.element("input", {type: "number", value: 100})})},
    {id: "selectionIcon", level: "atom", summary: "The two-arrow mark for choosing between records.",
      sample: () => UI.selectionIcon()},
    {id: "actionRow", level: "molecule", summary: "Buttons that act on the thing above them, in one wrapping row.",
      sample: () => UI.actionRow(UI.element("button", {type: "button"}, "Install"), UI.element("button", {type: "button"}, "Open settings"))},
    {id: "notice", level: "molecule", summary: "A banner above a page: a title, a sentence and the one action that deals with it.",
      sample: () => UI.notice({title: "Setup is not finished", message: "Clear the shader cache once before playing.",
        action: UI.element("button", {type: "button", class: "lex-dialog-action primary"}, "Clear cache")})},
    {id: "detailNote", level: "molecule", summary: "A sentence inside a section that is not a property.",
      sample: () => UI.detailNote("Nothing in this section applies to this record.")},
    {id: "toggleRow", level: "molecule", summary: "detailRow whose parts are all switches, laid out as many to a line as fit.",
      sample: () => UI.toggleRow({toggles: [
        {key: "menu", label: "Menu", checked: true, change: () => {}},
        {key: "battle", label: "Battle", checked: false, change: () => {}},
        {key: "field", label: "Field", checked: true, change: () => {}}]})},
    {id: "multiNumberRow", level: "molecule", summary: "detailRow whose parts are labelled numbers, each with its own copy button.",
      sample: () => UI.multiNumberRow([
        {label: "HP", control: el("input", {type: "number", value: "2400"})},
        {label: "STR", control: el("input", {type: "number", value: "24"})},
        {label: "MAG", control: el("input", {type: "number", value: "31"})}])},
    {id: "pager", level: "molecule", summary: "Page controls for a long list.",
      sample: () => UI.pager({page: 1, pages: 4, change: () => {}, inline: true})},
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
    {id: "modLoaderSection", level: "organism", expect: "every game", summary: "How this game loads mods, in the same five fields for every game.",
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
        // The pin sits on the property, and pinning it puts that property in
        // the list's columns. Shown the way a record's panel shows it.
        // The generated enabled column is the list's own, not a property.
        const properties = prefs.all().filter(column => typeof column.label === "string");
        return UI.detailSection({title: "PIN A PROPERTY INTO THE LIST", body: properties.map(column =>
          UI.detailField({label: String(column.label ?? column.key).toUpperCase(),
            pin: prefs.pinButton(column.key, column.label),
            control: UI.readonlyField(column.key === "value" ? "25" : "Example Item")}))});
      }},
    {id: "showAlert", level: "organism", summary: "Lexeditor's own message box. Never the browser's.",
      sample: () => sampleButton("Show a message", () => UI.showAlert(
        {title: "Sample message", message: "This is the shared message box."}))},
    {id: "showToast", level: "organism", summary: "A short message that fades by itself.",
      sample: () => sampleButton("Show a toast", () => UI.showToast("Saved."))},
    {id: "confirmAction", level: "organism", summary: "Lexeditor's own yes/no question.",
      sample: () => sampleButton("Ask a question", () => UI.confirmAction(
        {title: "Do the thing?", message: "Nothing happens either way here.", confirmLabel: "Do it"}))},
    {id: "confirmDiscardChanges", level: "organism", summary: "Asks before throwing away edits.",
      sample: () => sampleButton("Discard edits", () => UI.confirmDiscardChanges(
        {dirtyCount: () => 3, discard: async () => {}}))},
    {id: "confirmUnsavedExit", level: "organism", summary: "Asks before leaving with unsaved edits.",
      sample: () => sampleButton("Leave with edits", () => UI.confirmUnsavedExit(
        {dirtyCount: () => 2, save: async () => {}}, async () => true,
        {question: "Save before leaving this sample?"}))},
    {id: "openSettings", level: "organism", summary: "The shared settings dialog.",
      sample: () => sampleButton("Open settings", () => UI.openSettings())},
    {id: "sharedSettings", level: "organism", summary: "The settings every game has in common, as this page sees them.",
      sample: () => {
        const settings = UI.sharedSettings();
        const rows = Object.entries(settings || {}).slice(0, 6);
        if (!rows.length) return UI.detailNote("No shared settings on this page yet; the desktop host provides them.");
        return UI.detailSection({title: "AS THIS PAGE SEES THEM", body: rows.map(([name, value]) =>
          UI.detailField({label: name.toUpperCase(),
            control: UI.readonlyField(typeof value === "object" ? JSON.stringify(value).slice(0, 60) : String(value))}))});
      }},
    {id: "openGameFolder", level: "organism", summary: "Opens this game's folder in the file browser.",
      sample: () => sampleButton("Open the game folder", () => UI.openGameFolder("blank"))},

    // ---- templates -------------------------------------------------------
    {id: "mountShell", level: "template", expect: "every game", summary: "The window: brand, tabs, project selector, save, play, history. Everything above this page is it."},
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
    {id: "finishPluginLoading", level: "template", expect: "every game", summary: "Clears the loading screen once a page is ready. The screen you saw opening this one."},

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
    {id: "lazyOptions", level: "utility", summary: "Fills a long select's options the first time it is used."},
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
