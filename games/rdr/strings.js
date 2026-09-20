/* Structured RDR1 string-table editor module.
   Parsing and serialization live in string_tables.py/server.py. */
(function (global) {
  "use strict";

  global.RDRStringTablesUI = function RDRStringTablesUI(deps) {
    const {state, api, el, columnList, pagedListDetail, cell, shown,
      detailField, sourceControl, modOnlySpec, setStatus, shell} = deps;
    const UI = global.LexeditorUI;

    const tableMeta = id => (state.strings?.tables || [])
      .find(table => table.id === (id === undefined ? state.stringTableId : id));
    const value = row => state.stringEdits[row.id]?.value ?? row.text;

    function edit(row, next) {
      if (next === row.text) delete state.stringEdits[row.id];
      else state.stringEdits[row.id] = {
        value: next, tableId: row.tableId, source: row.source, path: row.path,
        languageIndex: row.languageIndex, entryIndex: row.entryIndex,
        expectedHash: row.hash, expectedText: row.text,
      };
      shell().refresh();
    }

    function matchingRows() {
      const needle = state.stringQuery.trim().toLowerCase();
      return (state.stringTable?.rows || []).filter(row =>
        (!needle || [row.identifier, row.hash, value(row), row.language]
          .some(candidate => String(candidate || "").toLowerCase().includes(needle)))
        && (!state.stringLanguage || row.language === state.stringLanguage));
    }

    async function load(id = state.stringTableId, renderAfter = true) {
      const tables = state.strings?.tables || [];
      let meta = tables.find(table => table.id === id && table.available)
        || tables.find(table => table.available);
      state.stringTableId = meta?.id || "";
      state.stringLoadError = "";
      state.stringSelected = "";
      if (!meta) {
        state.stringTable = null;
        state.vanilla.stringTable = null;
        if (renderAfter) render();
        return;
      }
      const query = new URLSearchParams({source: meta.source, path: meta.path});
      try {
        if (state.activeSource === "vanilla") {
          const payload = await api(`/api/string-table?${query}&dataset=vanilla`);
          state.stringTable = payload;
          state.vanilla.stringTable = UI.clone(payload);
        } else {
          [state.stringTable, state.vanilla.stringTable] = await Promise.all([
            api(`/api/string-table?${query}`),
            api(`/api/string-table?${query}&dataset=vanilla`),
          ]);
        }
        const first = state.stringTable.rows?.[0];
        if (first) state.stringSelected = first.id;
      } catch (error) {
        state.stringTable = null;
        state.vanilla.stringTable = null;
        state.stringLoadError = error.message || String(error);
      }
      if (renderAfter) render();
    }

    async function chooseTable(id) {
      state.stringPage = 0;
      state.stringLanguage = "";
      await load(id);
    }

    const COLUMNS = [
      {key:"key", label:"Key", width:"minmax(0,1fr)",
        render:row=>cell(row.identifier || row.hash)},
      {key:"text", label:"Text", width:"minmax(0,1.65fr)",
        render:row=>cell(value(row))},
      {key:"language", label:"Language", width:"minmax(0,.8fr)",
        render:row=>cell(row.language)},
      {key:"hash", label:"Hash", width:"minmax(0,.65fr)",
        render:row=>cell(row.hash)},
    ];

    function detail() {
      const row = (state.stringTable?.rows || [])
        .find(entry => entry.id === state.stringSelected);
      if (!row) return UI.detailPanel({
        className:"record-detail string-detail",
        title:"Select a localized string",
        body:[UI.detailNote(
          "Only parsed PC STRTBL text is editable; hashes and layout metadata remain structural.")],
      });
      const vanilla = state.vanilla.stringTable?.rows
        ?.find(entry => entry.id === row.id);
      const control = el("textarea", {
        disabled: state.activeSource !== "mine",
        spellcheck: true,
        "aria-label": "Localized text",
        oninput: event => edit(row, event.target.value),
      }, value(row));
      return UI.detailPanel({
        className:"record-detail string-detail",
        title: row.identifier || row.hash,
        identity: UI.recordId(row.entryIndex),
        meta: `${row.language} · ${row.hash}`,
        actions: UI.badge(row.project ? "Project" : "Vanilla",
          {tone: row.project ? "success" : null}),
        body:[
          detailField("Table", shown(state.stringTable.table.label), "",
            "The PC STRTBL resource that owns this localized text."),
          detailField("Key", shown(row.identifier || "Hash only"), "",
            "The stable game key when the identifier table resolves this hash uniquely."),
          detailField("Hash", shown(row.hash), "",
            "The game lookup hash is identity metadata and is not rewritten."),
          detailField("Language", shown(row.language), "",
            row.sharedLanguageBlock
              ? "These language slots share one physical source block; Lexeditor preserves that sharing."
              : "The language block that owns this text."),
          detailField("Source", shown(row.sourcePath), "",
            "Read-only prepared bytes from the installed archive."),
          detailField("Override", shown(row.projectPath), "",
            "Save writes a separate STRTBL override; the installed archive stays unchanged."),
          detailField("Text",
            sourceControl(control, () => value(row), vanilla?.text,
              next => edit(row, String(next))),
            "The localized text shown by the game for this key. Changing it does not rename the identifier or alter font/layout metrics.",
            "Lexeditor re-encodes only this UTF-16 text and preserves the entry hash, glyph metrics, scale/offset metadata, shared language blocks, and unknown padding."),
        ],
      });
    }

    function discard() {
      state.stringEdits = {};
      shell().history.clear();
      setStatus("Discarded unsaved string-table edits");
      render();
      shell().refresh();
    }

    function render() {
      const tables = state.strings?.tables || [];
      const selector = el("select", {
        "aria-label":"Select string table",
        onchange:event=>chooseTable(event.target.value),
      }, ...(tables.length ? tables.map(table => el("option", {
        value:table.id, selected:table.id === state.stringTableId,
        disabled:!table.available,
      }, `${table.sourceLabel} · ${table.path}${table.available ? "" : " — unavailable"}`))
        : [el("option",{value:""},"No prepared PC string tables")]));

      if (!state.stringTable) {
        document.querySelector("#toolbar").replaceChildren(
          selector,
          el("span",{class:"count"},state.stringLoadError
            || `${state.strings?.counts?.available || 0} parsed tables`));
        document.querySelector("#main").replaceChildren(UI.detailPanel({
          className:"lex-information-panel",
          title:"String Tables",
          body:[UI.detailNote(state.stringLoadError
            || "Prepare RDR data to extract supported PC .strtbl resources. Console-targeted _ps3.strtbl duplicates remain intentionally unavailable.")],
        }));
        shell().refresh();
        return;
      }

      const rows = matchingRows();
      const languages = [...new Set(state.stringTable.rows.map(row => row.language))]
        .sort((a,b)=>a.localeCompare(b));
      const languageFilter = el("select", {
        "aria-label":"Filter localized strings by language",
        onchange:event=>{state.stringLanguage=event.target.value;state.stringPage=0;render();},
      }, el("option",{value:"",selected:!state.stringLanguage},"All languages"),
      ...languages.map(language=>el("option",{
        value:language,selected:language===state.stringLanguage},language)));
      const discardButton = el("button", {
        type:"button", disabled:!Object.keys(state.stringEdits).length,
        onclick:discard,
      }, "Discard string edits");
      document.querySelector("#toolbar").replaceChildren(
        selector, languageFilter, discardButton,
        el("span",{class:"count"},
          `${state.stringTable.counts.records} strings · ${state.stringTable.counts.languages} language blocks`));

      document.querySelector("#main").replaceChildren(pagedListDetail({
        modOnly:modOnlySpec(state.stringEdits,()=>{state.stringPage=0;}),
        rows,key:row=>row.id,slots:false,page:state.stringPage,
        pageSize:state.stringPageSize,selected:state.stringSelected,noun:"strings",
        splitKey:"rdr-strings",className:"rdr-split",defaultSplit:48,
        fit:{minRowHeight:32},
        search:{key:"rdr-strings",value:state.stringQuery,
          placeholder:"Search identifiers, hashes, text or language…",
          change:next=>{state.stringQuery=next;state.stringPage=0;render();}},
        filters:[],
        master:({rows,selected,select})=>columnList({
          rows,key:row=>row.id,columns:COLUMNS,selected,selectedClass:"sel",select,
          class:"rdr-record-list","aria-label":"RDR localized strings"}),
        detail,
        sync:next=>{state.stringPage=next.page;state.stringPageSize=next.pageSize;
          state.stringSelected=next.selected||"";},
        change:next=>{state.stringPage=next.page;state.stringPageSize=next.pageSize;
          state.stringSelected=next.selected||"";render();},
      }));
      shell().refresh();
    }

    function validate() {
      for (const edit of Object.values(state.stringEdits)) {
        if (typeof edit.value !== "string")
          throw new Error("Localized string text must be text");
        if (edit.value.includes("\u0000"))
          throw new Error("Localized string text cannot contain NUL characters");
      }
    }

    async function savePending(saved) {
      const groups = {};
      for (const [id,edit] of Object.entries(state.stringEdits)) {
        const key = `${edit.source}\u0000${edit.path}`;
        const group = groups[key] ||= {
          source:edit.source,path:edit.path,ids:[],edits:[],
        };
        group.ids.push(id);
        group.edits.push({
          languageIndex:edit.languageIndex,entryIndex:edit.entryIndex,
          expectedHash:edit.expectedHash,expectedText:edit.expectedText,
          value:edit.value,
        });
      }
      for (const group of Object.values(groups)) {
        const result = await api("/api/string-table/save", {
          method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({source:group.source,path:group.path,edits:group.edits}),
        });
        for (const id of group.ids) delete state.stringEdits[id];
        saved.push(`${result.saved} localized string${result.saved===1?"":"s"} in ${group.path}`);
      }
    }

    const clearEdits = () => { state.stringEdits = {}; };
    const firstAvailableId = () => (state.strings?.tables || [])
      .find(table => table.available)?.id || "";

    return {render,load,validate,savePending,clearEdits,
      dirtyCount:()=>Object.keys(state.stringEdits).length,firstAvailableId};
  };
})(window);
