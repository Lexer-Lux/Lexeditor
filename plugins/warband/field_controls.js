"use strict";
// Controls for Warband fields that name a finite set.
//
// A Module System record is Python source, so every flag, enum and mesh is
// really an expression. Where the project's own headers or records name the
// set, a free text box invites a typo the build rejects - or, worse, a value
// the game accepts and reads as something else. These controls offer the named
// set and keep every part of the source they do not own.
(() => {
  const {el, detailField, detailSection, readonlyField, infoHelp} = LexeditorUI;

  // Split on a separator that is not inside brackets or a string. Returns null
  // when the expression is not a flat chain, which is the signal to fall back
  // to rewriting around the whole expression instead of editing parts of it.
  function splitTop(text, separator) {
    const parts = [];
    let depth = 0, start = 0, cursor = 0;
    while (cursor < text.length) {
      const char = text[cursor];
      if (char === '"' || char === "'") {
        const quote = char;
        cursor += 1;
        while (cursor < text.length) {
          if (text[cursor] === "\\") { cursor += 2; continue; }
          if (text[cursor] === quote) { cursor += 1; break; }
          cursor += 1;
        }
        continue;
      }
      if ("([{".includes(char)) depth += 1;
      else if (")]}".includes(char)) { depth -= 1; if (depth < 0) return null; }
      else if (char === separator && depth === 0) { parts.push(text.slice(start, cursor)); start = cursor + 1; }
      cursor += 1;
    }
    if (depth !== 0) return null;
    parts.push(text.slice(start));
    return parts;
  }

  const chain = expression => splitTop(String(expression ?? "").trim(), "|");

  function hasToken(expression, name) {
    const parts = chain(expression);
    if (parts) return parts.some(part => part.trim() === name);
    return new RegExp(`(^|[^A-Za-z0-9_])${name}([^A-Za-z0-9_]|$)`).test(String(expression));
  }

  // The number a chain of known constants and literals stands for, or null when
  // any part is something this control does not own.
  function reduce(expression, values) {
    const parts = chain(expression);
    if (!parts) return null;
    let total = 0;
    for (const part of parts) {
      const text = part.trim();
      if (/^\d+$/.test(text)) { total |= Number(text); continue; }
      if (Object.prototype.hasOwnProperty.call(values, text)) {
        // A name the project uses but whose value this editor cannot see still
        // counts as known text, so the control edits tokens instead of numbers.
        if (!Number.isInteger(values[text])) return null;
        if (values[text] === null) return null;
        total |= values[text];
        continue;
      }
      if (text === "0") continue;
      return null;
    }
    return total;
  }

  function toggle(expression, flags, name, on) {
    const values = {};
    for (const flag of flags) values[flag.name] = flag.value;
    const numeric = reduce(expression, values);
    if (numeric === null || !Number.isInteger(values[name])) return withToken(expression, name, on);
    const bit = values[name];
    const next = on ? (numeric | bit) : (numeric & ~bit);
    // Rebuild from the names, so the boxes and the source keep saying the same
    // thing. Bits no known flag covers stay, as a number.
    const parts = [];
    let covered = 0;
    for (const flag of flags) {
      if ((next & flag.value) === flag.value) { parts.push(flag.name); covered |= flag.value; }
    }
    const rest = next & ~covered;
    if (rest) parts.push(String(rest));
    return parts.join("|") || "0";
  }

  function withToken(expression, name, on) {
    const current = String(expression ?? "").trim();
    const parts = chain(current);
    if (on) {
      if (hasToken(current, name)) return current;
      if (parts && parts.every(part => part.trim())) return [...parts.map(part => part.trim()), name].join("|");
      return current && current !== "0" ? `(${current}) | ${name}` : name;
    }
    if (parts) {
      const kept = parts.map(part => part.trim()).filter(part => part && part !== name);
      if (kept.length !== parts.filter(part => part.trim()).length) return kept.join("|") || "0";
    }
    return `(${current}) & ~${name}`;
  }

  const isSet = (expression, flag) => hasToken(expression, flag.name)
    || (Number.isInteger(flag.value) && flag.value > 0
      && (reduce(expression, {[flag.name]: flag.value}) & flag.value) === flag.value);

  // A flag field becomes one checkbox per named flag. Anything in the source
  // that is not one of those names is shown, not hidden, so nobody has to guess
  // what a checkbox is building on.
  function bitFields(options) {
    const rows = options.flags.map(flag => detailField({
      label: flag.label || flag.name,
      property: flag.name,
      dataType: "BOOL",
      description: `Turns ${flag.name} on or off in ${options.label}.`,
      control: el("input", {
        type: "checkbox", checked: isSet(options.expression, flag), disabled: options.readOnly,
        onchange: event => options.apply(toggle(options.expression, options.flags, flag.name, event.target.checked)),
      }),
    }));
    const left = (chain(options.expression) || [])
      .map(part => part.trim())
      .filter(part => part && !options.flags.some(flag => flag.name === part)
        // A plain number is already the state of the boxes above, and the
        // owner's own part (an item's itp_type_*, say) has its own property.
        && !/^\d+$/.test(part)
        && !(options.ownOther && options.ownOther.test(part)));
    if (left.length) rows.push(detailField({
      label: "Also set", property: `${options.label} other`, dataType: "EXPR", showType: false,
      description: "These parts of the source expression are not one of the named flags, so they are preserved rather than rewritten.",
      control: readonlyField(left.join(" | "), {format: false}),
    }));
    // A section's help is one of the shared question-mark bubbles, not a
    // paragraph beside its title. A pin beside the section title adds the whole
    // field to the table, because the boxes are one property.
    const title = options.pin
      ? el("span", {class: "lex-pinnable-property"}, options.label, options.pin)
      : options.label;
    return detailSection({title, help: options.help ? infoHelp(options.help) : null, body: rows});
  }

  // A known enum: the current value stays selectable even when the project's
  // header does not name it, so opening the record never rewrites it.
  function enumSelect(options) {
    const select = el("select", {
      disabled: options.readOnly,
      onchange: event => options.apply(event.target.value),
    });
    const known = options.options.some(entry => entry.name === options.value);
    if (!known && options.value) select.append(el("option", {value: options.value, selected: true}, options.value));
    for (const entry of options.options) {
      select.append(el("option", {value: entry.name, selected: entry.name === options.value}, entry.label || entry.name));
    }
    return select;
  }

  // name(arg, arg)|name(arg) - the shape every item stat macro uses.
  function parseCalls(expression) {
    const parts = splitTop(String(expression ?? "").trim(), "|");
    if (!parts) return null;
    const calls = [];
    for (const part of parts) {
      const text = part.trim();
      if (!text) continue;
      const match = /^([A-Za-z_]\w*)\s*\(([\s\S]*)\)$/.exec(text);
      if (!match) return null;
      const args = splitTop(match[2], ",");
      if (!args) return null;
      calls.push({name: match[1], args: args.map(arg => arg.trim())});
    }
    return calls;
  }

  const callExpression = calls => calls
    .map(call => `${call.name}(${call.args.join(", ")})`)
    .join("|");

  // [("mesh", 0), ("other", 0)] - the shape an item's meshes field uses.
  function parseMeshes(expression) {
    const match = /^\[\s*([\s\S]*?)\s*\]$/.exec(String(expression ?? "").trim());
    if (!match) return null;
    const inner = match[1].trim();
    if (!inner) return [];
    const parts = splitTop(inner, ",");
    if (!parts) return null;
    const entries = [];
    for (const part of parts) {
      const text = part.trim();
      if (!text) continue;
      const pair = /^\(\s*(["'])([^"'\\]+)\1\s*(?:,\s*([^,]*?)\s*)?\)$/.exec(text);
      if (!pair) return null;
      entries.push({name: pair[2], flag: (pair[3] ?? "0").trim() || "0"});
    }
    return entries;
  }

  const meshExpression = entries => `[${entries
    .filter(entry => entry && entry.name)
    .map(entry => `("${entry.name}", ${entry.flag || "0"})`)
    .join(", ")}]`;

  // The stats of an item: one row per stat, each with a number box per
  // argument, and an add row that offers the project's own macro names.
  function statRows(options) {
    const rows = options.calls.map((call, index) => detailField({
      label: call.name,
      property: `stat-${call.name}`,
      dataType: call.args.every(arg => /^-?\d+(\.\d+)?$/.test(arg)) ? "FLOAT" : "EXPR",
      description: `${call.name}(${options.macros.includes(call.name) ? "value" : "value"}) - change a value here, or remove the stat. Values are numbers because the Module System reads them as numbers.`,
      control: el("div", {class: "lex-action-row"},
        ...call.args.map((arg, position) => {
          const change = value => {
            if (value === "") return;
            const next = options.calls.map(entry => ({...entry, args: [...entry.args]}));
            next[index].args[position] = String(value);
            options.apply(callExpression(next));
          };
          // A position the project fills with a name (swing_damage(16, blunt))
          // is a choice among the names this project uses there, not a box.
          const names = options.arguments?.[call.name]?.[position];
          if (Array.isArray(names)) {
            const select = el("select", {disabled: options.readOnly,
              "aria-label": `${call.name} argument ${position + 1}`,
              onchange: event => change(event.target.value)});
            if (!names.includes(arg)) select.append(el("option", {value: arg, selected: true}, arg));
            for (const name of names) select.append(el("option", {value: name, selected: name === arg}, name));
            return select;
          }
          return el("input", {
            type: "number", step: "any", value: arg, disabled: options.readOnly,
            // Keep the panel's own text size: a fitted number box beside it
            // would read as a different property from the one above.
            "data-lex-autofit": "false",
            "aria-label": `${call.name} value ${position + 1}`,
            onchange: event => change(event.target.value),
          });
        }),
        el("button", {
          type: "button", disabled: options.readOnly,
          "aria-label": `Remove the ${call.name} stat`,
          onclick: () => options.apply(callExpression(options.calls.filter((_, other) => other !== index))),
        }, "Remove")),
    }));
    const picker = el("select", {"aria-label": "Stat to add"});
    for (const macro of options.macros) picker.append(el("option", {value: macro}, macro));
    const add = el("button", {
      type: "button", disabled: options.readOnly || !options.macros.length,
      onclick: () => options.apply(callExpression([...options.calls, {name: picker.value, args: ["1"]}])),
    }, "Add stat");
    rows.push(detailField({
      label: "", showType: false, dataType: "EXPR",
      description: "Stat macros this project already uses, plus the ones its header_items.py defines.",
      control: el("div", {class: "lex-action-row"}, picker, add),
    }));
    return rows;
  }

  // Mesh entries: one row per mesh with the project's known mesh resources, a
  // way to open that mesh in the Meshes area, and the flags value it carries.
  function meshRows(options) {
    const names = options.choices.map(choice => choice.name);
    const option = (name, selected) => el("option", {value: name, selected}, name);
    const rows = options.entries.map((entry, index) => {
      const select = el("select", {
        disabled: options.readOnly, "aria-label": `${options.label} ${index + 1}`,
        onchange: event => {
          const next = options.entries.map(item => ({...item}));
          next[index].name = event.target.value;
          options.apply(next);
        },
      });
      if (!names.includes(entry.name)) select.append(option(entry.name, true));
      for (const name of names) select.append(option(name, name === entry.name));
      const open = options.open ? el("button", {
        type: "button", disabled: !options.choices.some(choice => choice.name === entry.name && choice.recordIndex !== undefined && choice.recordIndex !== null),
        title: `Show ${entry.name} in the Meshes area`,
        "aria-label": `Show ${entry.name} in the Meshes area`,
        onclick: () => options.open(entry),
      }, "Show mesh") : null;
      const remove = el("button", {
        type: "button", disabled: options.readOnly, "aria-label": `Remove ${options.label} ${index + 1}`,
        onclick: () => options.apply(options.entries.filter((_, other) => other !== index)),
      }, "Remove");
      return detailField({
        label: `${options.label} ${index + 1}`, property: `${options.property}-${index + 1}`,
        dataType: "MESH", showType: false, pin: options.pin || null,
        description: "A mesh resource name this project uses or declares. \"Show mesh\" opens that mesh's record in the Meshes area.",
        control: el("div", {class: "lex-action-row"}, select, open, remove),
      });
    });
    if (options.choices.length && options.add !== false) {
      const picker = el("select", {"aria-label": `Mesh to add to ${options.label}`});
      for (const name of names) picker.append(option(name, false));
      rows.push(detailField({
        label: "", showType: false, dataType: "MESH",
        description: "Adds a mesh entry with zero flags, which is what a plain inventory or scene mesh uses.",
        control: el("div", {class: "lex-action-row"}, picker, el("button", {
          type: "button", disabled: options.readOnly,
          onclick: () => options.apply([...options.entries, {name: picker.value, flag: "0"}]),
        }, "Add mesh")),
      }));
    }
    return rows;
  }

  window.WarbandFieldControls = {splitTop, chain, hasToken, withToken, reduce, toggle,
    bitFields, enumSelect, parseCalls, callExpression, parseMeshes, meshExpression,
    statRows, meshRows, infoHelp};
})();
