"use strict";

(() => {
  const style = document.createElement("style");
  style.textContent = `
    .ct-command-editor-row td{padding:0;border-bottom:1px solid var(--lex-border)}
    .ct-command-editor{display:flex;flex-wrap:wrap;align-items:end;gap:8px;padding:8px 10px;background:var(--lex-bg)}
    .ct-command-field{display:grid;gap:3px;min-width:110px}
    .ct-command-field label{font-size:.78em;color:var(--lex-muted)}
    .ct-command-field input[type="number"]{width:120px;padding:4px 6px;border:1px solid var(--lex-border);background:var(--lex-input-bg,#fff);color:var(--lex-text)}
    .ct-command-field.boolean{display:flex;align-items:center;gap:6px;min-width:150px;padding-bottom:5px}
    .ct-command-editor button{padding:5px 10px}
    .ct-command-editor-note{flex-basis:100%;font-size:.78em;color:var(--lex-muted)}
    .ct-command-summary{max-width:300px;color:var(--lex-muted)}
    .ct-event-audit{display:grid;gap:8px;padding:10px;border:1px solid var(--lex-border);background:var(--lex-panel)}
    .ct-event-audit-head{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
    .ct-event-audit-head button{padding:5px 10px}
    .ct-event-audit-note{font-size:.82em;color:var(--lex-muted)}
    .ct-event-audit-stats{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.88em}
    .ct-event-audit-hotspots{display:grid;grid-template-columns:minmax(72px,auto) 1fr auto;gap:0;border:1px solid var(--lex-border);font-size:.84em}
    .ct-event-audit-hotspots>span{padding:5px 7px;border-bottom:1px solid var(--lex-border)}
    .ct-event-audit-hotspots>span:nth-last-child(-n+3){border-bottom:0}
    .ct-event-audit-opcode{font-family:var(--lex-mono,monospace);font-weight:700}
    .ct-event-audit-dynamic{color:#e4bd62}
  `;
  document.head.append(style);

  async function saveEventCommand(objectId, functionId, commandIndex, command) {
    if (state.source !== "mine" || state.busy || !command.editor) return;
    state.busy = true;
    state.error = "";
    try {
      const saved = await api("/api/save/event-fields", {
        eventId: state.events.selected,
        objectId,
        functionId,
        commandIndex,
        sha256: state.events.detail.sha256,
        values: command.editor.values,
      });
      state.events.detail = saved;
      const row = state.events.data?.rows?.find(value => value.id === state.events.selected);
      if (row) {
        row.source = saved.source;
        row.sha256 = saved.sha256;
      }
      state.events.audit = null;
      state.events.auditSource = null;
      await loadDashboard();
    } catch (error) {
      state.error = String(error?.message || error);
    } finally {
      state.busy = false;
      render();
      refreshShell();
    }
  }

  async function runEventAudit() {
    if (state.busy) return;
    state.busy = true;
    state.error = "";
    const source = state.source;
    state.events.audit = null;
    state.events.auditSource = source;
    render();
    try {
      state.events.audit = await api(`/api/event-audit?${new URLSearchParams({source})}`);
    } catch (error) {
      if (state.events.auditSource === source) state.events.audit = null;
      state.error = String(error?.message || error);
    } finally {
      state.busy = false;
      render();
      refreshShell();
    }
  }

  function downloadEventAudit() {
    const current = state.events.auditSource === state.source ? state.events.audit : null;
    if (!current) return;
    const blob = new Blob([`${JSON.stringify(current, null, 2)}\n`], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `chrono-trigger-event-audit-${state.source}.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function eventAuditPanel() {
    const current = state.events.auditSource === state.source ? state.events.audit : null;
    const button = el("button", {
      type: "button",
      disabled: state.busy,
      onclick: runEventAudit,
    }, current ? "Refresh coverage audit" : state.busy && state.events.auditSource === state.source ? "Auditing…" : "Run coverage audit");
    const download = current ? el("button", {
      type: "button",
      disabled: state.busy,
      onclick: downloadEventAudit,
    }, "Download audit JSON") : null;
    const head = el("div", {class: "ct-event-audit-head"},
      el("strong", {}, "Real-install event coverage"), button, download,
      el("span", {class: "ct-event-audit-note"},
        `Read-only ${state.source === "vanilla" ? "Vanilla" : "selected project + Vanilla fallback"} scan; runs only on request.`));
    if (!current) {
      return el("div", {class: "ct-event-audit"}, head,
        el("div", {class: "ct-event-audit-note"},
          "Ranks fail-closed parser stops first, then argument-bearing commands that still lack a named editor. Aliased function bounds and zero-argument commands are excluded from gap inflation."));
    }

    const audited = current.auditedEventIds?.length ?? current.events ?? (current.eventId === undefined ? 0 : 1);
    const selected = current.selectedEventIds?.length ?? audited;
    const stats = el("div", {class: "ct-event-audit-stats"},
      el("span", {}, el("strong", {}, String(audited)), `/${selected} events audited`),
      el("span", {}, el("strong", {}, String(current.argumentCommands ?? 0)), " argument commands"),
      el("span", {}, el("strong", {}, `${Number(current.writablePercent ?? 0).toFixed(2)}%`), " named-editor coverage"),
      el("span", {}, el("strong", {}, String(current.problemFunctions ?? 0)), " fail-closed functions"),
      current.scanErrorCount ? el("span", {class: "ct-event-audit-dynamic"},
        el("strong", {}, String(current.scanErrorCount)), " scan error(s)") : null,
    );

    let hotspots = current.hotspots || [];
    if (!hotspots.length && current.opcodes) {
      hotspots = current.opcodes.filter(row => Number(row.readOnly) > 0).map(row => ({
        opcodeHex: row.opcodeHex,
        readOnlyCount: row.readOnly,
        stopCount: 0,
        dynamicOrUnresolvedBoundary: row.dynamicOrUnresolvedBoundary,
      }));
    }
    hotspots = hotspots.slice(0, 8);
    const hotspotGrid = hotspots.length ? el("div", {class: "ct-event-audit-hotspots"}) : null;
    if (hotspotGrid) {
      for (const row of hotspots) {
        const stops = Number(row.stopCount || 0);
        const readOnly = Number(row.readOnlyCount || 0);
        const sampleIds = (row.sampleEventIds || []).slice(0, 8)
          .map(value => String(value).padStart(4, "0"));
        const sampleText = sampleIds.length
          ? ` · event${sampleIds.length === 1 ? "" : "s"} ${sampleIds.join(", ")}${row.sampleEventIdsTruncated ? "…" : ""}`
          : "";
        hotspotGrid.append(
          el("span", {class: `ct-event-audit-opcode${row.dynamicOrUnresolvedBoundary ? " ct-event-audit-dynamic" : ""}`}, row.opcodeHex),
          el("span", {}, stops
            ? `${stops} parser stop${stops === 1 ? "" : "s"}${readOnly ? ` · ${readOnly} decoded read-only` : ""}`
            : `${readOnly} argument command${readOnly === 1 ? "" : "s"} read-only`),
          el("span", {}, `${row.dynamicOrUnresolvedBoundary ? "dynamic/unresolved" : "fixed boundary"}${sampleText}`),
        );
      }
    }
    const errors = current.scanErrors?.length
      ? el("details", {}, el("summary", {}, `${current.scanErrors.length} event scan error(s)`),
          ...current.scanErrors.slice(0, 8).map(row => el("div", {class: "ct-event-audit-note ct-mono"},
            `${String(row.eventId).padStart(4, "0")} · ${row.error}`)))
      : null;
    return el("div", {class: "ct-event-audit"}, head, stats,
      hotspotGrid || el("div", {class: "ct-event-audit-note"}, "No argument-bearing read-only or parser-stop hotspots found."),
      errors);
  }

  function eventCommandEditor(objectId, functionId, commandIndex, command) {
    const schema = command.editor;
    if (!schema) return null;
    const disabled = state.source !== "mine" || state.busy || !state.dashboard?.project?.writable;
    const controls = [];
    for (const field of schema.fields) {
      if (field.kind === "boolean") {
        const input = el("input", {
          type: "checkbox",
          disabled,
          onchange: event => { schema.values[field.key] = event.target.checked; },
        });
        input.checked = Boolean(schema.values[field.key]);
        controls.push(el("div", {class: "ct-command-field boolean"}, input, el("label", {}, field.label)));
      } else {
        controls.push(el("div", {class: "ct-command-field"},
          el("label", {}, field.label),
          numericInput(schema.values[field.key], field.min, field.max,
            value => { schema.values[field.key] = value; }, disabled),
        ));
      }
    }
    controls.push(el("button", {
      type: "button",
      disabled,
      onclick: () => saveEventCommand(objectId, functionId, commandIndex, command),
    }, "Apply command"));
    controls.push(el("div", {class: "ct-command-editor-note"},
      state.source === "vanilla"
        ? "Vanilla reference: named values are visible but cannot be changed."
        : "Fixed-width PC command: Apply rewrites only existing argument bytes; opcode, size and pointers stay unchanged.",
    ));
    return el("div", {class: "ct-command-editor"}, ...controls);
  }

  functionCommandView = function (fn, objectId) {
    if (!fn.commands?.length && !fn.problem) {
      return el("span", {class: "ct-function-summary"}, fn.length ? "No decoded commands" : "Empty function");
    }
    const wrap = el("div");
    if (fn.commands?.length) {
      const tbody = el("tbody");
      for (const [commandIndex, command] of fn.commands.entries()) {
        tbody.append(el("tr", {},
          el("td", {class: "ct-mono"}, `0x${command.offset.toString(16).toUpperCase()}`),
          el("td", {class: "ct-mono"}, `0x${command.opcode.toString(16).toUpperCase().padStart(2, "0")}`),
          el("td", {}, command.name),
          el("td", {class: "ct-number"}, String(command.size)),
          el("td", {class: "ct-hex"}, command.argumentsHex || "—"),
          el("td", {class: "ct-command-summary"}, command.semantic?.summary || "—"),
        ));
        const editor = eventCommandEditor(objectId, fn.id, commandIndex, command);
        if (editor) {
          tbody.append(el("tr", {class: "ct-command-editor-row"}, el("td", {colspan: 6}, editor)));
        }
      }
      wrap.append(el("table", {class: "ct-command-table"},
        el("thead", {}, el("tr", {},
          el("th", {}, "Offset"), el("th", {}, "Opcode"), el("th", {}, "Command"),
          el("th", {}, "Bytes"), el("th", {}, "Arguments"), el("th", {}, "Meaning"),
        )), tbody));
    }
    if (fn.problem) {
      wrap.append(el("div", {class: "ct-function-problem"},
        `Stopped at 0x${fn.problem.offset.toString(16).toUpperCase()}: ${fn.problem.reason} ` +
        `(0x${fn.problem.opcode.toString(16).toUpperCase().padStart(2, "0")}). Remaining bytes are not guessed.`));
    }
    return wrap;
  };

  eventsView = function () {
    const data = state.events.data;
    if (!data) return el("div", {class: "ct-view"}, errorNode() || el("div", {class: "ct-empty"}, "Loading field events…"));
    const search = el("input", {
      type: "search", value: state.events.query, placeholder: "Filter Atel event IDs or paths…",
      oninput: event => {
        state.events.query = event.target.value;
        state.events.offset = 0;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(loadActive, 180);
      },
    });
    const list = el("div", {class: "ct-list"});
    for (const row of data.rows) {
      list.append(el("button", {
        type: "button", class: `ct-list-row${row.id === state.events.selected ? " active" : ""}`,
        onclick: () => selectEvent(row.id),
      }, el("span", {class: "ct-list-id"}, String(row.id).padStart(4, "0")),
      el("span", {}, `${row.objectCount} objects · ${row.decodedCommandCount} commands`), sourceBadge(row.source)));
    }
    let detail = el("div", {class: "ct-detail"}, el("div", {class: "ct-empty"},
      state.events.selected === null ? "No event selected." : "Loading event structure…"));
    const event = state.events.detail;
    if (event) {
      const body = [];
      for (const object of event.objects) {
        const functions = [];
        for (const fn of object.functions) {
          functions.push(el("details", {class: "ct-object", open: object.id === 0 && fn.id === 0},
            el("summary", {}, `${fn.id.toString(16).toUpperCase()} · ${fn.name} · ` +
              `0x${fn.start.toString(16).toUpperCase()}–0x${fn.end.toString(16).toUpperCase()} · ` +
              `${fn.commands?.length || 0} command(s)${fn.complete ? " · complete" : ""}`),
            functionCommandView(fn, object.id)));
        }
        body.push(el("details", {class: "ct-object", open: object.id === 0},
          el("summary", {}, `Object ${object.id.toString(16).toUpperCase().padStart(2, "0")} · ` +
            `0x${object.start.toString(16).toUpperCase()}–0x${object.end.toString(16).toUpperCase()}`), ...functions));
      }
      const policy = state.source === "vanilla"
        ? "Vanilla reference is read-only."
        : "Named controls are enabled only for proven fixed-width PC commands; all other commands remain read-only.";
      detail = el("div", {class: "ct-detail"}, el("h2", {}, `${event.name} · ${event.path}`),
        el("div", {class: "ct-event-meta"},
          `${event.objectCount} objects · ${event.uniqueFunctionBounds} unique function bounds · ` +
          `${event.decodedCommandCount} decoded commands · ${event.completeFunctionBounds} complete bounds · ` +
          `${event.problemFunctionBounds} fail-closed bounds. ${policy}`), ...body);
    }
    const start = data.matchCount ? data.offset + 1 : 0;
    const end = data.offset + data.rows.length;
    return el("div", {class: "ct-view"}, el("div", {class: "ct-toolbar"}, search),
      el("div", {class: "ct-summary"}, el("span", {}, el("strong", {}, String(data.matchCount)), " field events"),
        el("span", {}, state.source === "vanilla"
          ? "PC command-boundary disassembly · Vanilla read-only"
          : "PC command-boundary disassembly · named fixed-width edits")),
      eventAuditPanel(), errorNode(), el("div", {class: "ct-split"}, list, detail),
      el("div", {class: "ct-footer"}, el("span", {}, `Showing ${start}–${end} of ${data.matchCount}`),
        el("div", {}, el("button", {type: "button", disabled: data.offset <= 0,
          onclick: () => { state.events.offset = Math.max(0, state.events.offset - state.events.limit); loadActive(); }}, "Previous"),
        " ", el("button", {type: "button", disabled: data.offset + data.rows.length >= data.matchCount,
          onclick: () => { state.events.offset += state.events.limit; loadActive(); }}, "Next"))));
  };
})();