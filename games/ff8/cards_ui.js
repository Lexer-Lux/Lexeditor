/* Page-level graph treatment is isolated under /shared so the huge FF8 editor
 * does not grow another bespoke formula renderer. This bootstrap is loaded on
 * every FF8 editor page before any curve card is mounted. */
(() => {
  if (document.querySelector('script[data-lex-ff8-graph-design-a]')) return;
  const script = document.createElement('script');
  script.src = '/shared/ff8-graph-design-a.js';
  script.dataset.lexFf8GraphDesignA = 'true';
  document.head.append(script);
})();

/* Factory kept independent of the editor's page state. The host supplies its
 * existing list/detail, typed controls, provenance, and history helpers. */
window.FF8CardsUI = ({el, state, rowOf, filtered, showPaged, sharedDetail,
  detailSection, detailField, numberControl, selectControl, sourceControl,
  referenceValues, infoHelp, shell, noteFieldEdit, subtabBar, detailPanel,
  recordId, columnList}) => {
  // The card's own four sides, in the order Triple Triad draws them.
  const sides = ["top", "left", "right", "bottom"];
  const fields = [...sides, "element", "power"];
  const labels = {top:"Top", bottom:"Bottom", left:"Left", right:"Right", element:"Element", power:"Selection power"};
  const clone = value => JSON.parse(JSON.stringify(value));
  let mode = "cards", playerMap = "", playerData = null, playerBase = null,
      playerLoading = false, playerError = "", playerStatus = "";
  if (!document.getElementById("ff8-card-redesign-style")) {
    const style = document.createElement("style");
    style.id = "ff8-card-redesign-style";
    // No white slabs, no black text on them and no drop shadows. Every colour
    // here is the plugin's own theme token or the card's own blue.
    style.textContent = `
      .ff8-card-root{display:grid;grid-template-rows:auto minmax(0,1fr);min-height:0;height:100%}
      .ff8-card-root > .lex-subtab-bar{margin:0}

      /* One row: the card on the left, everything you can change on its right.
         Nothing stacked, nothing scrolling. */
      .ff8-card-detail .lex-detail-panel-body{
        display:grid;grid-template-columns:auto minmax(0,1fr);align-items:start;
        gap:18px;padding:14px 16px;min-height:0;overflow:hidden}
      .ff8-card-detail .lex-detail-section{border:0;background:transparent;margin:0;min-width:0}
      .ff8-card-detail .lex-detail-section > h3,
      .ff8-card-detail .lex-detail-section-title{display:none}
      .ff8-card-detail .lex-detail-section-content{min-width:0}
      @media (max-width:900px){
        .ff8-card-detail .lex-detail-panel-body{grid-template-columns:minmax(0,1fr)}
      }

      /* The card. Triple Triad draws a blue player card with a soft lit centre
         falling to a darker edge, a pale border and the ranks in a diamond in
         the top-left corner. */
      .ff8-card-preview{
        --ff8-card-width:clamp(150px,17vw,208px);
        position:relative;width:var(--ff8-card-width);aspect-ratio:3/4;
        flex:0 0 auto;overflow:hidden;border-radius:4px;
        border:2px solid #cfd8ef;
        background:
          radial-gradient(120% 95% at 50% 38%, #6f8fd8 0%, #3f61b4 46%, #22357e 78%, #16215a 100%);
        box-shadow:none}
      .ff8-card-preview img{position:absolute;inset:0;width:100%;height:100%;display:block;
        object-fit:contain;object-position:center 58%}
      .ff8-card-ranks{
        position:absolute;top:5px;left:6px;display:grid;
        grid-template-areas:"top top" "left right" "bottom bottom";
        justify-items:center;column-gap:1px;row-gap:0;
        font:700 clamp(15px,1.5vw,19px)/1 var(--lex-font,"FF8 Menu",Arial,sans-serif)}
      .ff8-card-rank{
        grid-area:var(--ff8-rank-area);
        min-width:1ch;padding:0 1px;border:0;border-radius:2px;
        background:transparent;color:#fff;font:inherit;text-align:center;cursor:pointer}
      .ff8-card-rank:is(:hover,:focus-visible){background:#ffffff2e;outline:none}
      .ff8-card-element{
        position:absolute;top:6px;right:6px;width:26px;height:26px;padding:0;
        display:grid;place-items:center;border:0;border-radius:50%;
        background:#00000055;color:#fff;
        font:700 10px/1 var(--lex-font,"FF8 Menu",Arial,sans-serif);cursor:pointer}
      .ff8-card-element:is(:hover,:focus-visible){background:#00000088;outline:none}
      .ff8-card-element.none{opacity:0}
      .ff8-card-preview:is(:hover,:focus-within) .ff8-card-element.none{opacity:.5}
      .ff8-card-power{
        position:absolute;right:6px;bottom:4px;
        color:#fff;font:700 clamp(17px,1.7vw,22px)/1 var(--lex-font,"FF8 Menu",Arial,sans-serif)}
      .ff8-card-element-picker{
        position:absolute;top:34px;right:6px;z-index:3;min-width:8.5em;
        color:var(--lex-text);border:1px solid var(--lex-border);
        background:var(--lex-panel);font:inherit}

      /* Players. A field, its card-game opponents, and the seven values each
         CARDGAME call pushes - as one table, not a wall of loose boxes. */
      .ff8-card-players{display:grid;grid-template-rows:auto auto minmax(0,1fr);gap:10px;min-height:0;height:100%}
      .ff8-card-player-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .ff8-card-player-toolbar select{min-width:min(430px,60vw)}
      .ff8-card-player-note{margin:0;color:var(--lex-muted);font-size:.92em;max-width:90ch}
      .ff8-card-player-state{margin:0;color:var(--lex-muted)}
      .ff8-card-player-state.error{color:#d64b4b}
    `;
    document.head.append(style);
  }
  const rank = value => Number(value) === 10 ? "A" : String(value);
  const elementOptions = () => state.data.cards.elements || [];
  const elementName = value => elementOptions()
    .find(entry => Number(entry.id) === Number(value))?.name || "";
  // The element mark is a short tag rather than the whole word: the corner it
  // sits in is twenty-six pixels wide, and "Thunder" is not.
  const elementMark = value => {
    const name = elementName(value);
    return name ? name.slice(0, 2).toLocaleUpperCase() : "";
  };

  // The card itself is the control. Every rank on it can be typed into and the
  // element corner opens its own list, so the values are edited where they are
  // read instead of only in a column of boxes beside the picture.
  const preview = (row, refresh) => {
    const update = (field, value) => {
      const limit = field === "power" ? 255 : 10;
      row[field] = Math.max(0, Math.min(limit, Number(value) || 0));
      noteFieldEdit("cards", {field});
      refresh();
    };
    const rankButton = side => el("button", {
      type: "button",
      class: "ff8-card-rank",
      style: `--ff8-rank-area:${side}`,
      title: `${labels[side]}: click to change`,
      "aria-label": `${labels[side]}, currently ${rank(row[side])}`,
      onclick: () => update(side, (Number(row[side]) % 10) + 1),
      oncontextmenu: event => {event.preventDefault();update(side, Number(row[side]) <= 1 ? 10 : Number(row[side]) - 1);},
    }, rank(row[side]));
    const picker = el("select", {
      class: "ff8-card-element-picker",
      hidden: true,
      "aria-label": "Element",
      onchange: event => update("element", event.target.value),
      onblur: event => {event.target.hidden = true;},
    }, ...elementOptions().map(entry => el("option",
      {value: entry.id, selected: Number(entry.id) === Number(row.element)}, entry.name)));
    const element = el("button", {
      type: "button",
      class: `ff8-card-element${Number(row.element) === 255 ? " none" : ""}`,
      title: Number(row.element) === 255 ? "No element: click to set one" : `${elementName(row.element)}: click to change`,
      "aria-label": `Element, currently ${Number(row.element) === 255 ? "none" : elementName(row.element)}`,
      onclick: () => {picker.hidden = false;picker.focus();},
    }, elementMark(row.element) || "–");
    return el("div", {class: "ff8-card-preview"},
      // A card with no artwork on disk shows the plain blue card, not a broken
      // image icon and its alt text painted across the ranks.
      el("img", {src: `/assets/cards/${row.id}.png`, alt: "",
        onerror: event => {event.target.hidden = true;}}),
      el("div", {class: "ff8-card-ranks"}, ...sides.map(rankButton)),
      element, picker,
      el("span", {class: "ff8-card-power", title: labels.power}, String(row.power)));
  };

  const renameCard = (row, value) => {
    row.name = String(value);
    const text = state.data.text.rows.find(entry =>
      entry.source === "exe_card_names" && entry.recordId === row.id);
    if (text) text.value = row.name;
    noteFieldEdit("cards", {field: "name"});
  };

  const detail = (row, prefs) => {
    const vanilla = rowOf(state.vanilla, "cards", row.id);
    const refresh = () => render();
    const properties = fields.map(field => {
      const update = value => {row[field] = Number(value);noteFieldEdit("cards", {field});};
      const options = elementOptions().map(entry => ({value: entry.id, name: entry.name}));
      const control = field === "element"
        ? selectControl(row[field], options, update)
        : numberControl(row[field], 0, field === "power" ? 255 : 10, 1, update,
          {"aria-label": `${row.name} ${labels[field]}`});
      const format = value => field === "element"
        ? options.find(entry => entry.value === Number(value))?.name || value
        : Number(value) === 10 && field !== "power" ? "A" : value;
      return detailField({label: labels[field].toUpperCase(),
        help: infoHelp(field === "power"
          ? "When you lose, the opponent prefers a card with a higher selection power."
          : field === "element" ? "The card's element under the Elemental rule."
          : "The value on this side of the card. Ten appears as A in Triple Triad."),
        control: sourceControl(control, () => row[field], vanilla[field],
          referenceValues("cards", row.id, value => value?.[field]), update, format)});
    });
    // No NAME property. The name is the heading, and the heading is typed into
    // directly, so a card no longer carries its own name twice.
    return detailPanel({
      className: "lex-detail detail ff8-card-detail",
      title: row.name,
      renameRecord: value => {renameCard(row, value);shell.refresh();},
      renameLabel: "Card name",
      identity: el("span", {class: "lex-pinnable-property"}, prefs?.pinButton("id", "ID"), recordId(row.id)),
      body: [
        detailSection({title: "PREVIEW", body: [preview(row, refresh)]}),
        detailSection({title: "CARD", body: properties}),
      ],
    });
  };

  const renderCards = () => showPaged("cards", filtered("cards", ["id", "name"]), [
    {key: "id", label: "ID"},
    // The name is edited in the table as well as in the heading: a rename is
    // the one edit you want without leaving the list you are scanning.
    {key: "name", label: "Card",
      edit: (row, value) => {renameCard(row, value);shell.refresh();}},
    ...fields.map(field => ({key: field, label: labels[field], pinned: false, numeric: true}))
  ], detail, "74px minmax(240px,1fr)", {}, false);
  let render = () => null;
  const loadPlayerMap = async key => {
    if (!key || playerLoading) return;
    playerLoading = true;playerError = "";playerStatus = "";
    try {
      const response = await fetch(`/api/field?map=${encodeURIComponent(key)}&dataset=current`);
      const payload = await response.json();
      if (!response.ok || payload.error) throw new Error(payload.error || `HTTP ${response.status}`);
      if (playerMap !== key) return;
      playerData = payload;playerBase = clone(payload);
    } catch (error) {if (playerMap === key) playerError = error.message;}
    finally {playerLoading = false;if (state.tab === "cards") render();}
  };
  const savePlayers = async () => {
    if (!playerData || !playerBase) return;
    const edits = [];
    for (const player of playerData.players || []) for (const param of player.params || []) {
      const before = playerBase.players?.[player.id]?.params?.[param.id];
      if (before && Number(before.value) !== Number(param.value)) {
        edits.push({map: playerData.key, player: player.id, param: param.id, value: Number(param.value)});
      }
    }
    if (!edits.length) {playerStatus = "No player changes to save.";render();return;}
    try {
      const response = await fetch("/api/field/save", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({edits})});
      const payload = await response.json();
      if (!response.ok || payload.error) throw new Error(payload.error || `HTTP ${response.status}`);
      playerBase = clone(playerData);
      playerStatus = `Saved ${edits.length} CARDGAME parameter change${edits.length === 1 ? "" : "s"}.`;
    } catch (error) {playerStatus = error.message;}
    render();
  };
  const renderPlayers = () => {
    const maps = state.data.fields?.rows || [];
    if (!playerMap && maps.length) playerMap = maps[0].key;
    if (playerMap && !playerData && !playerLoading) queueMicrotask(() => loadPlayerMap(playerMap));
    const selector = el("select", {value: playerMap, "aria-label": "Field", onchange: event => {
      playerMap = event.target.value;playerData = null;playerBase = null;playerError = "";playerStatus = "";render();
    }}, ...maps.map(row => el("option", {value: row.key, selected: row.key === playerMap}, `${row.name} — ${row.key}`)));
    const toolbar = el("div", {class: "ff8-card-player-toolbar"},
      el("strong", {}, "FIELD"), selector,
      playerData ? el("button", {type: "button", onclick: savePlayers}, "SAVE PLAYERS") : null);
    // Every opponent on the field is a row, and every value it pushes is a
    // column of that row's own table - the same list control the rest of the
    // editor uses, rather than a grid of loose boxes under a bold heading.
    let content;
    if (!maps.length) content = el("p", {class: "ff8-card-player-state"},
      "Field data has not been read yet. Open the FIELDS tab once and the opponents appear here.");
    else if (playerLoading) content = el("p", {class: "ff8-card-player-state"}, "Reading this field's card players…");
    else if (playerError) content = el("p", {class: "ff8-card-player-state error"},
      `This field could not be read: ${playerError}`);
    else if (!playerData) content = el("p", {class: "ff8-card-player-state"}, "Choose a field to inspect its Triple Triad opponents.");
    else if (!(playerData.players || []).length) content = el("p", {class: "ff8-card-player-state"},
      "No entity on this field calls CARDGAME, so it has no Triple Triad opponent.");
    else {
      const entries = (playerData.players || []).flatMap(player =>
        (player.params || []).map(param => ({id: `${player.id}-${param.id}`, player, param})));
      content = columnList({
        rows: entries, key: entry => entry.id, localSort: false,
        class: "ff8-record-list",
        columns: [
          {key: "entity", label: "Opponent", render: entry => entry.player.entity},
          {key: "script", label: "Script", render: entry => entry.player.script},
          {key: "parameter", label: "Value", render: entry => entry.param.name},
          {key: "mode", label: "Source",
            help: "Literal stores the number in the script. Savemap reads the numbered runtime variable. Editing keeps whichever it already is.",
            render: entry => entry.param.mode === "literal" ? "Literal"
              : entry.param.mode === "variable" ? "Savemap" : "Unsupported"},
          {key: "value", label: "Stored", numeric: true,
            help: "The exact 24-bit literal, or the savemap variable number, this push instruction holds.",
            render: entry => el("input", {type: "number", min: 0, max: 16777215, step: 1,
              value: entry.param.value, disabled: !entry.param.editable,
              "aria-label": `${entry.player.entity} ${entry.param.name}`,
              oninput: event => {
                entry.param.value = Number(event.target.value);
                playerStatus = "Unsaved player changes.";
              }})},
        ]});
    }
    return el("div", {class: "ff8-card-players"}, toolbar,
      el("p", {class: "ff8-card-player-note"},
        "An opponent's deck comes from the seven values pushed immediately before the field's CARDGAME call. A value stored as a savemap variable stays a variable; only the number it holds changes."),
      content,
      playerStatus ? el("p", {class: "ff8-card-player-state"}, playerStatus) : null);
  };
  render = () => {
    if (state.tab !== "cards") return null;
    const root = el("div", {class: "ff8-card-root"},
      subtabBar({
        label: "Cards views",
        active: mode,
        tabs: [{id: "cards", label: "CARDS"}, {id: "players", label: "PLAYERS"}],
        change: value => {mode = value;render();},
      }),
      mode === "players" ? renderPlayers() : renderCards());
    document.querySelector("#main")?.replaceChildren(root);
    shell.refresh();
    return root;
  };
  return {
    render,
    edits: () => state.data.cards.rows.flatMap(row => {
      const base = state.base.cards.find(value => value.id === row.id);
      return fields.filter(field => row[field] !== base[field])
        .map(field => ({id: row.id, field, value: row[field]}));
    })
  };
};

/* Issue #93 extension. The main FF8 editor already loads this module on every
 * page, so the spellbook editor can attach to the existing GF detail surface
 * without duplicating the 300KB host document or creating a second GF editor. */
(() => {
  const STYLE_ID = "lexeditor-gf-spellbook-style";
  const PANEL_CLASS = "lexeditor-gf-spellbook";
  const clone = value => JSON.parse(JSON.stringify(value));
  const request = async (url, options) => {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok || payload?.error) throw new Error(payload?.error || `HTTP ${response.status}`);
    return payload;
  };
  const button = (text, onClick, title="") => {
    const value = document.createElement("button");
    value.type = "button";
    value.textContent = text;
    value.title = title;
    value.addEventListener("click", onClick);
    return value;
  };
  const select = (options, selected, onChange, emptyLabel=null) => {
    const value = document.createElement("select");
    if (emptyLabel !== null) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = emptyLabel;
      value.append(option);
    }
    options.forEach(row => {
      const option = document.createElement("option");
      option.value = String(row.id);
      option.textContent = `${row.id} — ${row.name}`;
      option.selected = Number(selected) === Number(row.id);
      value.append(option);
    });
    value.addEventListener("change", () => onChange(value.value === "" ? null : Number(value.value)));
    return value;
  };
  const ensureStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .${PANEL_CLASS}{margin-top:14px;padding:12px;border:1px solid var(--border,#52627c);border-radius:8px;background:rgba(0,0,0,.12)}
      .${PANEL_CLASS} h3{margin:0 0 5px;font-size:14px;letter-spacing:.05em}
      .${PANEL_CLASS} .lex-spell-note{opacity:.78;font-size:12px;margin:0 0 10px}
      .${PANEL_CLASS} .lex-spell-toolbar,.${PANEL_CLASS} .lex-spell-page-head,.${PANEL_CLASS} .lex-spell-row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
      .${PANEL_CLASS} .lex-spell-toolbar{margin:8px 0}
      .${PANEL_CLASS} .lex-spell-page{padding:8px;margin:8px 0;border:1px solid rgba(160,180,215,.28);border-radius:6px}
      .${PANEL_CLASS} .lex-spell-page-head{justify-content:space-between;margin-bottom:6px;font-size:12px;font-weight:700}
      .${PANEL_CLASS} .lex-spell-row{display:grid;grid-template-columns:28px minmax(150px,1fr) minmax(160px,1fr) auto;margin:5px 0}
      .${PANEL_CLASS} select{min-width:0;width:100%}
      .${PANEL_CLASS} button{white-space:nowrap}
      .${PANEL_CLASS} .lex-spell-status{font-size:12px;min-height:1.3em}
      @media(max-width:760px){.${PANEL_CLASS} .lex-spell-row{grid-template-columns:28px 1fr}.${PANEL_CLASS} .lex-spell-row select{grid-column:2}.${PANEL_CLASS} .lex-spell-actions{grid-column:2}}
    `;
    document.head.append(style);
  };
  const mount = async () => {
    const host = document.querySelector("#gf-detail[data-gf]");
    if (!host || host.querySelector(`.${PANEL_CLASS}`)) return;
    const gfId = Number(host.dataset.gf);
    if (!Number.isInteger(gfId) || gfId < 0 || gfId > 15) return;
    const marker = document.createElement("div");
    marker.className = PANEL_CLASS;
    marker.dataset.gf = String(gfId);
    marker.textContent = "Loading GF spellbook…";
    host.append(marker);
    ensureStyle();
    try {
      const payload = await request("/api/kernel?section=3&dataset=current");
      if (!marker.isConnected || Number(host.dataset.gf) !== gfId) return;
      const gf = payload.rows?.find(row => Number(row.id) === gfId);
      if (!gf) throw new Error(`GF ${gfId} is unavailable`);
      const meta = payload.spellbook || {};
      const magic = meta.magicOptions || [];
      const abilities = meta.abilityOptions || [];
      let pages = clone(gf.spellbook?.pages || []);
      let dirty = false;
      marker.replaceChildren();
      const title = document.createElement("h3");
      title.textContent = "SPELLBOOK";
      const note = document.createElement("p");
      note.className = "lex-spell-note";
      note.textContent = "Ordered Magic pages for this GF. Zero-stock spells remain visible but disabled in battle. Optional requirements use abilities learned by this GF. Runtime requires Single GF and Shared Magic off.";
      const toolbar = document.createElement("div");
      toolbar.className = "lex-spell-toolbar";
      const body = document.createElement("div");
      const status = document.createElement("div");
      status.className = "lex-spell-status";
      const setDirty = () => { dirty = true; status.textContent = "Unsaved spellbook changes"; };
      const usedMagic = (except=null) => new Set(pages.flatMap(page => page).filter(slot => slot !== except).map(slot => slot.magicId));
      const draw = () => {
        toolbar.replaceChildren();
        body.replaceChildren();
        if (!pages.length) {
          toolbar.append(button("ENABLE SPELLBOOK", () => {pages=[[]];setDirty();draw();}));
          const empty = document.createElement("div");
          empty.className = "lex-spell-note";
          empty.textContent = "No custom book: FF8 uses its native Magic stock list.";
          body.append(empty);
        } else {
          toolbar.append(
            button("ADD PAGE", () => {if(pages.length < (meta.maxPages||8)){pages.push([]);setDirty();draw();}}, "Maximum eight pages"),
            button("DISABLE", () => {pages=[];setDirty();draw();})
          );
          pages.forEach((page, pageIndex) => {
            const card = document.createElement("div");
            card.className = "lex-spell-page";
            const head = document.createElement("div");
            head.className = "lex-spell-page-head";
            const name = document.createElement("span");
            name.textContent = `PAGE ${pageIndex+1}`;
            const pageActions = document.createElement("span");
            pageActions.append(
              button("↑",()=>{if(pageIndex){[pages[pageIndex-1],pages[pageIndex]]=[pages[pageIndex],pages[pageIndex-1]];setDirty();draw();}},"Move page earlier"),
              button("↓",()=>{if(pageIndex<pages.length-1){[pages[pageIndex+1],pages[pageIndex]]=[pages[pageIndex],pages[pageIndex+1]];setDirty();draw();}},"Move page later"),
              button("REMOVE PAGE",()=>{pages.splice(pageIndex,1);setDirty();draw();})
            );
            head.append(name,pageActions);
            card.append(head);
            page.forEach((slot, slotIndex) => {
              const row = document.createElement("div");
              row.className = "lex-spell-row";
              const index = document.createElement("span");
              index.textContent = String(slotIndex+1);
              const spellChoices = magic.map(entry => ({...entry}));
              const magicSelect = select(spellChoices,slot.magicId,value=>{
                if(value===null)return;
                if(usedMagic(slot).has(value)){status.textContent="A spell can appear only once in this GF's book.";magicSelect.value=String(slot.magicId);return;}
                slot.magicId=value;setDirty();draw();
              });
              const abilitySelect = select(abilities,slot.abilityId,value=>{slot.abilityId=value;setDirty();},"No learned-ability requirement");
              const actions = document.createElement("span");
              actions.className = "lex-spell-actions";
              actions.append(
                button("↑",()=>{if(slotIndex){[page[slotIndex-1],page[slotIndex]]=[page[slotIndex],page[slotIndex-1]];setDirty();draw();}},"Move spell earlier"),
                button("↓",()=>{if(slotIndex<page.length-1){[page[slotIndex+1],page[slotIndex]]=[page[slotIndex],page[slotIndex+1]];setDirty();draw();}},"Move spell later"),
                button("×",()=>{page.splice(slotIndex,1);setDirty();draw();},"Remove spell")
              );
              row.append(index,magicSelect,abilitySelect,actions);
              card.append(row);
            });
            if (page.length < (meta.slotsPerPage||4)) {
              card.append(button("ADD SPELL",()=>{
                const used=usedMagic();const first=magic.find(entry=>!used.has(Number(entry.id)));
                if(!first){status.textContent="No unused spells remain.";return;}
                page.push({magicId:Number(first.id),abilityId:null});setDirty();draw();
              }));
            }
            body.append(card);
          });
        }
        const save = button("SAVE SPELLBOOK", async () => {
          save.disabled = true;
          status.textContent = "Saving…";
          try {
            await request("/api/kernel/save", {
              method:"POST", headers:{"Content-Type":"application/json"},
              body:JSON.stringify({section:3,edits:[{id:gfId,field:"__spellbook",value:pages.length?pages:null}]})
            });
            dirty=false;status.textContent="Spellbook saved. Save Gameplay settings too if you changed Single GF / Shared Magic.";
          } catch(error) {status.textContent=error.message;}
          finally {save.disabled=false;}
        });
        toolbar.append(save);
      };
      marker.append(title,note,toolbar,body,status);
      draw();
      window.addEventListener("beforeunload", event => {if(dirty){event.preventDefault();event.returnValue="";}}, {once:true});
    } catch (error) {
      marker.textContent = `Spellbook unavailable: ${error.message}`;
    }
  };
  const observer = new MutationObserver(() => queueMicrotask(mount));
  const start = () => {observer.observe(document.body,{childList:true,subtree:true});mount();};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",start,{once:true});
  else start();
})();