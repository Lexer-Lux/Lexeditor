/* Structured RDR1 string-table Table+Detail UI.
   This module owns only the .strtbl interaction surface; parsing/writing stays
   in games/rdr/string_tables.py and server.py. */
(function (global) {
  "use strict";

  global.RDRStringTablesUI = function RDRStringTablesUI(deps) {
    const state = deps.state;
    const api = deps.api;
    const el = deps.el;
    const list = deps.list;
    const pagedListDetail = deps.pagedListDetail;
    const recordCell = deps.recordCell;
    const detailField = deps.detailField;
    const sourceControl = deps.sourceControl;
    const modOnlySpec = deps.modOnlySpec;
    const setStatus = deps.setStatus;
    const shell = deps.shell;
    const UI = global.LexeditorUI;

    function tableMeta(id) {
      const wanted = id === undefined ? state.stringTableId : id;
      return (state.strings && state.strings.tables || []).find(function (table) {
        return table.id === wanted;
      });
    }

    function value(row) {
      const edit = state.stringEdits[row.id];
      return edit ? edit.value : row.text;
    }

    function edit(row, next) {
      if (next === row.text) {
        delete state.stringEdits[row.id];
      } else {
        state.stringEdits[row.id] = {
          value: next,
          tableId: row.tableId,
          source: row.source,
          path: row.path,
          languageIndex: row.languageIndex,
          entryIndex: row.entryIndex,
          expectedHash: row.hash,
          expectedText: row.text
        };
      }
      shell().refresh();
    }

    function matchingRows() {
      const needle = state.stringQuery.trim().toLowerCase();
      return (state.stringTable && state.stringTable.rows || []).filter(function (row) {
        const matchesText = !needle || [row.identifier, row.hash, value(row), row.language].some(
          function (candidate) {
            return String(candidate || "").toLowerCase().includes(needle);
          }
        );
        return matchesText && (!state.stringLanguage || row.language === state.stringLanguage);
      });
    }

    async function load(id, renderAfter) {
      if (renderAfter === undefined) renderAfter = true;
      const tables = state.strings && state.strings.tables || [];
      let meta = tables.find(function (table) {
        return table.id === id && table.available;
      });
      if (!meta) meta = tables.find(function (table) { return table.available; });
      state.stringTableId = meta ? meta.id : "";
      state.stringLoadError = "";
      state.stringSelected = "";
      if (!meta) {
        state.stringTable = null;
        state.vanilla.stringTable = null;
        if (renderAfter) render();
        return;
      }

      const query = new URLSearchParams({source: meta.source, path: meta.path}).toString();
      try {
        if (state.activeSource === "vanilla") {
          const payload = await api("/api/string-table?" + query + "&dataset=vanilla");
          state.stringTable = payload;
          state.vanilla.stringTable = UI.clone(payload);
        } else {
          const payloads = await Promise.all([
            api("/api/string-table?" + query),
            api("/api/string-table?" + query + "&dataset=vanilla")
          ]);
          state.stringTable = payloads[0];
          state.vanilla.stringTable = payloads[1];
        }
        const first = state.stringTable.rows && state.stringTable.rows[0];
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
      await load(id, true);
    }

    function rowView(row) {
      return el("div", {class: "rdr-record-row rdr-string-row"},
        recordCell("rdr-record-name", row.identifier || row.hash),
        recordCell("rdr-record-source", value(row), value(row)),
        recordCell("rdr-record-type", row.language),
        recordCell("rdr-record-id", row.hash)
      );
    }

    function selectRow(row) {
      state.stringSelected = row.id;
      render();
    }

    function detail() {
      const row = (state.stringTable && state.stringTable.rows || []).find(function (entry) {
        return entry.id === state.stringSelected;
      });
      if (!row) {
        return el("div", {class: "lex-detail empty"}, el("div", {},
          el("h2", {}, "Select a localized string"),
          el("p", {}, "Only parsed PC STRTBL text is editable; hashes and layout metadata remain structural.")
        ));
      }
      const vanilla = state.vanilla.stringTable && state.vanilla.stringTable.rows &&
        state.vanilla.stringTable.rows.find(function (entry) { return entry.id === row.id; });
      const control = el("textarea", {
        value: value(row),
        disabled: state.activeSource !== "mine",
        spellcheck: true,
        "aria-label": "Localized text",
        oninput: function (event) { edit(row, event.target.value); }
      });
      return UI.detailPanel({
        className: "record-detail string-detail",
        title: row.identifier || row.hash,
        identity: UI.recordId(row.entryIndex),
        meta: row.language + " · " + row.hash,
        actions: el("span", {class: "badge" + (row.project ? " project" : "")},
          row.project ? "Project" : "Vanilla"),
        body: [
          detailField("Table", state.stringTable.table.label, "",
            "The PC STRTBL resource that owns this localized text."),
          detailField("Key", row.identifier || "Hash only", "",
            "The stable game key when the identifier table resolves this hash uniquely."),
          detailField("Hash", el("code", {}, row.hash), "",
            "The game lookup hash is identity metadata and is not rewritten."),
          detailField("Language", row.language, "",
            row.sharedLanguageBlock
              ? "These language slots share one physical block in the source table; Lexeditor preserves that sharing."
              : "The language block that owns this text."),
          detailField("Source", el("code", {title: row.sourcePath}, row.sourcePath), "",
            "Read-only prepared bytes from the installed archive."),
          detailField("Override", el("code", {title: row.projectPath}, row.projectPath), "",
            "Save writes a separate STRTBL override; the installed archive stays unchanged."),
          detailField("Text",
            sourceControl(control, function () { return value(row); },
              vanilla ? vanilla.text : undefined,
              function (next) { edit(row, String(next)); }),
            "The localized text shown by the game for this key. Changing it does not rename the identifier or alter font/layout metrics.",
            "Lexeditor re-encodes only this UTF-16 text and preserves the entry hash, glyph metrics, scale/offset metadata, shared language blocks, and unknown padding.")
        ]
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
      const toolbar = document.querySelector("#toolbar");
      const main = document.querySelector("#main");
      const tables = state.strings && state.strings.tables || [];
      const selector = el("select", {
        "aria-label": "Select string table",
        onchange: function (event) { chooseTable(event.target.value); }
      }, ...(tables.length ? tables.map(function (table) {
        return el("option", {
          value: table.id,
          selected: table.id === state.stringTableId,
          disabled: !table.available
        }, table.sourceLabel + " · " + table.path + (table.available ? "" : " — unavailable"));
      }) : [el("option", {value: ""}, "No prepared PC string tables")]));

      if (!state.stringTable) {
        toolbar.replaceChildren(selector,
          el("span", {class: "count"}, state.stringLoadError ||
            String(state.strings && state.strings.counts && state.strings.counts.available || 0) + " parsed tables"));
        main.replaceChildren(el("section", {class: "card"},
          el("h2", {}, "String Tables"),
          el("p", {class: state.stringLoadError ? "error" : "source-note"},
            state.stringLoadError ||
            "Prepare RDR data to extract supported PC .strtbl resources. Console-targeted _ps3.strtbl duplicates remain intentionally unavailable.")
        ));
        shell().refresh();
        return;
      }

      const rows = matchingRows();
      const languages = Array.from(new Set(state.stringTable.rows.map(function (row) {
        return row.language;
      }))).sort(function (a, b) { return a.localeCompare(b); });
      const languageFilter = el("select", {
        "aria-label": "Filter localized strings by language",
        onchange: function (event) {
          state.stringLanguage = event.target.value;
          state.stringPage = 0;
          render();
        }
      }, el("option", {value: "", selected: !state.stringLanguage}, "All languages"),
      ...languages.map(function (language) {
        return el("option", {
          value: language,
          selected: language === state.stringLanguage
        }, language);
      }));
      const discardButton = el("button", {
        type: "button",
        disabled: !Object.keys(state.stringEdits).length,
        onclick: discard
      }, "Discard string edits");
      toolbar.replaceChildren(selector, languageFilter, discardButton,
        el("span", {class: "count"},
          String(state.stringTable.counts.records) + " strings · " +
          String(state.stringTable.counts.languages) + " language blocks"));

      main.replaceChildren(pagedListDetail({
        modOnly: modOnlySpec(state.stringEdits, function () { state.stringPage = 0; }),
        rows: rows,
        key: function (row) { return row.id; },
        slots: false,
        page: state.stringPage,
        pageSize: state.stringPageSize,
        selected: state.stringSelected,
        noun: "strings",
        splitKey: "rdr-strings",
        className: "rdr-split",
        defaultSplit: 48,
        fit: {rowSelector: ".rdr-record-entry", headerSelector: ".rdr-listhead", minRowHeight: 32},
        search: {
          key: "rdr-strings",
          value: state.stringQuery,
          placeholder: "Search identifiers, hashes, text or language…",
          change: function (next) {
            state.stringQuery = next;
            state.stringPage = 0;
            render();
          }
        },
        filters: [],
        master: function (options) {
          return list({
            rows: options.rows,
            key: function (row) { return row.id; },
            selected: options.selected,
            selectedClass: "sel",
            select: options.select,
            class: "rdr-record-list",
            header: el("div", {class: "rdr-listhead rdr-string-row"},
              el("span", {}, "Key"), el("span", {}, "Text"),
              el("span", {}, "Language"), el("span", {}, "Hash")),
            rowClass: "rdr-record-entry",
            render: rowView,
            "aria-label": "RDR localized strings"
          });
        },
        detail: detail,
        sync: function (next) {
          state.stringPage = next.page;
          state.stringPageSize = next.pageSize;
          state.stringSelected = next.selected || "";
        },
        change: function (next) {
          state.stringPage = next.page;
          state.stringPageSize = next.pageSize;
          state.stringSelected = next.selected || "";
          render();
        }
      }));
      shell().refresh();
    }

    function validate() {
      Object.values(state.stringEdits).forEach(function (edit) {
        if (typeof edit.value !== "string") throw new Error("Localized string text must be text");
        if (edit.value.includes("\u0000")) throw new Error("Localized string text cannot contain NUL characters");
      });
    }

    async function savePending(saved) {
      const groups = {};
      Object.entries(state.stringEdits).forEach(function (pair) {
        const id = pair[0], edit = pair[1];
        const key = edit.source + "\u0000" + edit.path;
        const group = groups[key] || (groups[key] = {
          source: edit.source, path: edit.path, ids: [], edits: []
        });
        group.ids.push(id);
        group.edits.push({
          languageIndex: edit.languageIndex,
          entryIndex: edit.entryIndex,
          expectedHash: edit.expectedHash,
          expectedText: edit.expectedText,
          value: edit.value
        });
      });
      for (const group of Object.values(groups)) {
        const result = await api("/api/string-table/save", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({source: group.source, path: group.path, edits: group.edits})
        });
        group.ids.forEach(function (id) { delete state.stringEdits[id]; });
        saved.push(String(result.saved) + " localized string" +
          (result.saved === 1 ? "" : "s") + " in " + group.path);
      }
    }

    function clearEdits() {
      state.stringEdits = {};
    }

    function dirtyCount() {
      return Object.keys(state.stringEdits).length;
    }

    function firstAvailableId() {
      const table = state.strings && state.strings.tables &&
        state.strings.tables.find(function (candidate) { return candidate.available; });
      return table ? table.id : "";
    }

    return {
      render: render,
      load: load,
      validate: validate,
      savePending: savePending,
      clearEdits: clearEdits,
      dirtyCount: dirtyCount,
      firstAvailableId: firstAvailableId
    };
  };
})(window);
