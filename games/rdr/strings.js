/* Structured RDR1 string-table editor module.
   Parsing and serialization live in string_tables.py/server.py. */
(function (global) {
  "use strict";

  global.RDRStringTablesUI = function RDRStringTablesUI(deps) {
    const {state, api, el, columnList, pagedListDetail, cell, shown,
      detailField, sourceControl, modOnlySpec, setStatus, shell} = deps;
    const UI = global.LexeditorUI;
    const LANGUAGE_FLAGS = {
      "English":"🇺🇸", "Spanish":"🇪🇸", "French":"🇫🇷", "German":"🇩🇪",
      "Italian":"🇮🇹", "Japanese":"🇯🇵", "Chinese (Traditional)":"🇹🇼",
      "Chinese (Simplified)":"🇨🇳", "Korean":"🇰🇷", "Spanish (Spain)":"🇪🇸",
      "Spanish (Mexico)":"🇲🇽", "Portuguese":"🇧🇷", "Polish":"🇵🇱", "Russian":"🇷🇺",
    };
    const value = row => state.stringEdits[row.id]?.value ?? row.text;
    const languageId = language => String(language?.index ?? language?.id ?? "");

    let discardButton = null;
    const refreshDiscardButton = () => {
      if (discardButton?.isConnected)
        discardButton.disabled = !Object.keys(state.stringEdits).length;
    };

    function edit(row, next) {
      if (next === row.text) delete state.stringEdits[row.id];
      else state.stringEdits[row.id] = {
        value: next, tableId: row.tableId, source: row.source, path: row.path,
        languageIndex: row.languageIndex, entryIndex: row.entryIndex,
        expectedHash: row.hash, expectedText: row.text,
      };
      refreshDiscardButton();
      shell().refresh();
    }

    function matchingRows() {
      const needle = state.stringQuery.trim().toLowerCase();
      return (state.stringTable?.rows || []).filter(row =>
        !needle || [row.identifier, row.hash, value(row), row.path, row.sourceLabel]
          .some(candidate => String(candidate || "").toLowerCase().includes(needle)));
    }

    const firstLanguageId = () => languageId((state.strings?.languages || [])[0]);

    async function load(id = state.stringLanguage || firstLanguageId(), renderAfter = true) {
      const languages = state.strings?.languages || [];
      let language = languages.find(row => languageId(row) === String(id))
        || languages[0];
      state.stringLanguage = languageId(language);
      state.stringLoadError = "";
      state.stringSelected = "";
      if (!language) {
        state.stringTable = null;
        state.vanilla.stringTable = null;
        if (renderAfter) render();
        return;
      }
      const query = new URLSearchParams({language: String(language.index)});
      try {
        if (state.activeSource === "vanilla") {
          const payload = await api(`/api/strings?${query}&dataset=vanilla`);
          state.stringTable = payload;
          state.vanilla.stringTable = UI.clone(payload);
        } else {
          [state.stringTable, state.vanilla.stringTable] = await Promise.all([
            api(`/api/strings?${query}`),
            api(`/api/strings?${query}&dataset=vanilla`),
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

    async function chooseLanguage(id) {
      if (String(id) === state.stringLanguage) return;
      state.stringPage = 0;
      await load(id);
    }

    const COLUMNS = [
      {key:"key", label:"Key", width:"minmax(0,1fr)",
        render:row=>cell(row.identifier || row.hash)},
      {key:"text", label:"Text", width:"minmax(0,1.65fr)",
        render:row=>cell(value(row))},
      {key:"resource", label:"Resource", width:"minmax(0,1.05fr)",
        render:row=>cell(row.path)},
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
        meta: `${row.sourceLabel} · ${row.hash}`,
        body:[
          detailField("Resource", shown(row.path), "",
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

    function languageTabs() {
      return UI.subtabBar({
        tabs:(state.strings?.languages || []).map(language => ({
          id:languageId(language),
          label:`${LANGUAGE_FLAGS[language.label] || "🏳️"} ${language.label}`,
        })),
        active:state.stringLanguage,
        label:"Languages",
        className:"lex-subtab-bar-fill",
        change:chooseLanguage,
      });
    }

    function render() {
      discardButton = el("button", {
        type:"button", disabled:!Object.keys(state.stringEdits).length,
        onclick:discard,
      }, "Discard string edits");
      const count = state.stringTable?.counts
        ? `${state.stringTable.counts.records} strings · ${state.stringTable.counts.tables} resources`
        : state.stringLoadError || `${state.strings?.counts?.available || 0} parsed resources`;
      document.querySelector("#toolbar").replaceChildren(
        languageTabs(), discardButton, el("span",{class:"count"},count));

      if (!state.stringTable) {
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
      document.querySelector("#main").replaceChildren(pagedListDetail({
        modOnly:modOnlySpec(state.stringEdits,()=>{state.stringPage=0;}),
        rows,key:row=>row.id,slots:false,page:state.stringPage,
        pageSize:state.stringPageSize,selected:state.stringSelected,noun:"strings",
        splitKey:"rdr-strings",className:"rdr-split",defaultSplit:48,
        fit:{minRowHeight:32},
        search:{key:`rdr-strings-${state.stringLanguage}`,value:state.stringQuery,
          placeholder:"Search identifiers, hashes, text or resource…",
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

    const clearEdits = () => { state.stringEdits = {}; refreshDiscardButton(); };

    return {render,load,validate,savePending,clearEdits,
      dirtyCount:()=>Object.keys(state.stringEdits).length,firstLanguageId};
  };
})(window);
