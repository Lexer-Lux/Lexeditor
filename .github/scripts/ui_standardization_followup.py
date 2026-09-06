from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return text.replace(old, new, 1)


p = "ui/framework.js"
t = read(p)

# Generated Enabled is now a normal pinnable column whenever the records really
# have an enabled boolean. Saved column preferences decide whether it is shown.
t = one(t, '''  const withEnabledColumn = (declared, rows, change) => {\n    const columns = declared || [];\n    if (!hasEnabledProperty(rows)) return columns;\n    if (columns.some(column => String(column.key).toLocaleLowerCase() === ENABLED_KEY)) return columns;\n    return [enabledColumn(change), ...columns];\n  };\n\n  const columnPreferences = (viewKey, definitions, changed = () => {}) => {\n    const key = `lexeditor:columns:${String(viewKey || "view")}`;\n    const source = numberedIdColumns(definitions || [], []);\n    const byKey = new Map(source.map(column => [column.key, column]));\n    const defaults = source.filter(column => column.pinned !== false).map(column => column.key);\n''', '''  const withEnabledColumn = (declared, rows, change, autoAdd = true) => {\n    const columns = declared || [];\n    const enabledIndex = columns.findIndex(\n      column => String(column.key).toLocaleLowerCase() === ENABLED_KEY);\n    if (!hasEnabledProperty(rows)) {\n      return columns.filter((column, index) =>\n        index !== enabledIndex || !column.generated);\n    }\n    if (enabledIndex >= 0) {\n      return columns.map((column, index) =>\n        index === enabledIndex && column.generated ? enabledColumn(change) : column);\n    }\n    return autoAdd ? [enabledColumn(change), ...columns] : columns;\n  };\n\n  const columnPreferences = (viewKey, definitions, changed = () => {}) => {\n    const key = `lexeditor:columns:${String(viewKey || "view")}`;\n    const declared = numberedIdColumns(definitions || [], []);\n    const source = declared.some(column => String(column.key).toLocaleLowerCase() === ENABLED_KEY)\n      ? declared : [enabledColumn(null), ...declared];\n    const byKey = new Map(source.map(column => [column.key, column]));\n    const defaults = source.filter(column => column.pinned !== false).map(column => column.key);\n''', "pinnable enabled column")

t = one(t, '''      // A changed column set changes the table's real minimum width. Discard\n      // the old divider size so the shared layout can fit the new table.\n      for (const layoutKey of [\n        `lexeditor:panel-layout:${viewKey}`,\n        `lexeditor:list-detail:${viewKey}`,\n      ]) {\n        try { localStorage.removeItem(layoutKey); } catch (_error) {}\n      }\n      changed([...order]);\n''', '''      // Preserve the user's divider position while pinning. Re-rendering the\n      // table at a new minimum width is enough; clearing the split caused the\n      // detail pane to flash to its default width on every pin click.\n      changed([...order]);\n''', "pin flash")

t = one(t, '''    const columns = preferredColumns\n      ? withEnabledColumn(preferredColumns, options.rows, options.enabledChange)\n      : numberedIdColumns(\n          withEnabledColumn(options.columns, options.rows, options.enabledChange),\n          options.rows || []);\n''', '''    const columns = preferredColumns\n      ? withEnabledColumn(preferredColumns, options.rows, options.enabledChange, false)\n      : numberedIdColumns(\n          withEnabledColumn(options.columns, options.rows, options.enabledChange),\n          options.rows || []);\n''', "honor enabled pin preference")

# LL gets a semantic class, not an index-dependent colour.
t = one(t,
    '      element("span", {class: "lex-reference-tag"}, shortReferenceName(source)),\n',
    '      element("span", {class: `lex-reference-tag${shortReferenceName(source) === "LL" ? " lex-reference-ll" : ""}`}, shortReferenceName(source)),\n',
    "LL ref class")

# Current project is a source too: show editable icon and enabled check/cross in
# the trigger, and show the same state inside project menu rows.
t = one(t, '''      const selectedSource = sources.find(row => String(row.key) === activeSource);\n      mode.hidden = !selectedSource;\n      mode.textContent = selectedSource?.readOnly === false ? "📝" : "🔒";\n      mode.setAttribute("aria-label", selectedSource?.readOnly === false ? "Editable" : "Read only");\n      name.textContent = selectedSource?.label || current?.name || "Select a mod";\n      status.hidden = !selectedSource;\n      status.textContent = selectedSource?.enabled === false ? "×" : "✓";\n      status.className = `lex-project-source-status ${selectedSource?.enabled === false ? "disabled" : "enabled"}`;\n      status.setAttribute("aria-label", selectedSource?.enabled === false ? "Disabled" : "Enabled");\n      path.textContent = selectedSource?.path || (selectedSource\n        ? "Read-only reference"\n        : current?.path || "New Mod or Find a Mod");\n''', '''      const selectedReference = sources.find(row => String(row.key) === activeSource);\n      const selectedSource = activeSource === "mine" ? {\n        key:"mine", label:current?.name || "My Mod", path:current?.path || "",\n        readOnly:false, enabled:current?.enabled !== false,\n      } : selectedReference;\n      mode.hidden = !selectedSource;\n      mode.textContent = selectedSource?.readOnly === false ? "📝" : "🔒";\n      mode.setAttribute("aria-label", selectedSource?.readOnly === false ? "Editable" : "Read only");\n      name.textContent = selectedSource?.label || current?.name || "Select a mod";\n      status.hidden = !selectedSource;\n      status.textContent = selectedSource?.enabled === false ? "×" : "✓";\n      status.className = `lex-project-source-status ${selectedSource?.enabled === false ? "disabled" : "enabled"}`;\n      status.setAttribute("aria-label", selectedSource?.enabled === false ? "Disabled" : "Enabled");\n      path.textContent = selectedSource?.path || (selectedSource\n        ? "Read-only reference"\n        : current?.path || "New Mod or Find a Mod");\n''', "active project status")

t = one(t, '''      }, element("span", {class: "lex-project-menu-name"}, row.name),\n      element("span", {class: "lex-project-menu-path"}, row.path));\n''', '''      }, element("span", {class: "lex-project-source-mode", "aria-label":"Editable"}, "📝"),\n      element("span", {class: "lex-project-menu-name"}, row.name),\n      element("span", {class: "lex-project-menu-path"}, row.path),\n      element("span", {class:`lex-project-source-status ${row.enabled === false ? "disabled" : "enabled"}`,\n        "aria-label":row.enabled === false ? "Disabled" : "Enabled"}, row.enabled === false ? "×" : "✓"));\n''', "project menu status")

# A Boolean property behaves as one control surface except where a nested
# control/info/ref action owns the click.
t = t.replace("    const label = event.target.closest?.('.lex-boolean-field > .lex-detail-field-label');\n    if (!label) return;\n    const input = label.parentElement?.querySelector('.lex-detail-field-control input[type=\"checkbox\"]');\n",
'''    const field = event.target.closest?.('.lex-boolean-field');\n    if (!field || event.target.closest?.('input,button,a,select,textarea,.lex-info-help,.lex-reference-values,.lex-column-pin')) return;\n    const input = field.querySelector('.lex-detail-field-control input[type="checkbox"]');\n''')

# Make the model-preview X literally inherit the measured header-icon rectangle.
t = one(t, '''    heading.append(close);\n    heading.after(drawer);\n    const open = async () => {\n''', '''    heading.style.position = 'relative';\n    heading.append(close);\n    heading.after(drawer);\n    const syncCloseSlot = () => {\n      close.style.left = `${icon.offsetLeft}px`;\n      close.style.top = `${icon.offsetTop}px`;\n      close.style.width = `${icon.offsetWidth}px`;\n      close.style.height = `${icon.offsetHeight}px`;\n    };\n    const open = async () => {\n      syncCloseSlot();\n''', "model close slot")

write(p, t)

p = "ui/framework.css"
t = read(p)
t += r'''

/* LEXEDITOR_SHARED_UI_STANDARDIZATION_FOLLOWUP_20260906 */
/* Sorting never deletes the property label or info bubble. The triangle gets
   its own lower rail position while help remains centred and clickable. */
.lex-detail-field[data-lex-sort] .lex-field-type-rail > .lex-info-help {
  display:inline-grid !important; opacity:1 !important;
}
.lex-detail-field[data-lex-sort] .lex-field-type-rail::after {
  top:auto !important; bottom:2px !important; left:50% !important;
  transform:translateX(-50%) !important; opacity:1 !important;
}
.lex-detail-field[data-lex-sort]:hover .lex-field-type-rail::after,
.lex-detail-field[data-lex-sort]:focus-within .lex-field-type-rail::after {
  content:attr(data-never) !important; opacity:0 !important;
}
.lex-detail-field[data-lex-sort] > .lex-detail-field-label {
  display:flex !important; visibility:visible !important; opacity:1 !important;
}

.lex-toggle-name,.lex-toggle-label,.lex-flag-label {
  writing-mode:horizontal-tb !important; text-orientation:mixed !important;
  transform:none !important; white-space:normal; overflow-wrap:anywhere;
}

/* Close is overlaid on the measured icon slot instead of becoming a fourth
   heading-grid column. */
.lex-model-preview-close { position:absolute !important; z-index:4; margin:0 !important; }

/* Graph contract: title is the large all-caps h4; y scale and y name live in
   the right margin, all rotated 90 degrees CCW. X scale stays in bottom margin. */
.lex-curve-editor { position:relative; }
.lex-curve-heading > h4,.lex-curve-heading-title {
  margin:0 !important; text-transform:uppercase !important;
  font-size:clamp(26px,3.2vw,46px) !important; line-height:1 !important;
  transform:none !important; font-stretch:normal !important; letter-spacing:.04em !important;
}
.lex-curve-plot { --lex-curve-margin-right:42px !important; }
.lex-curve-axis-top,.lex-curve-axis-bottom {
  left:auto !important; right:7px !important;
  writing-mode:vertical-rl !important; text-orientation:mixed !important;
  transform:rotate(180deg) !important;
}
.lex-curve-axis-top { top:calc(var(--lex-curve-margin-top) + 2px) !important; }
.lex-curve-axis-bottom { bottom:calc(var(--lex-curve-margin-bottom) + 2px) !important; }
.lex-curve-axis-name-y {
  left:auto !important; right:22px !important; top:50% !important; bottom:auto !important;
  writing-mode:vertical-rl !important; text-orientation:mixed !important;
  transform:translateY(-50%) rotate(180deg) !important;
}
.lex-curve-axis-start,.lex-curve-axis-end,.lex-curve-axis-name-x {
  top:auto !important; bottom:4px !important;
}

/* Project rows use one compact state rail. Disabled rows are greyed as an
   entire object, including their buttons and name. */
.lex-project-menu-item-select {
  grid-template-columns:auto minmax(0,1fr) minmax(0,1fr) auto;
}
.lex-project-menu-item:has(.lex-project-source-status.disabled),
.lex-project-reference:has(.lex-project-source-status.disabled) {
  filter:grayscale(1) !important; opacity:.42 !important;
}
'''
write(p, t)
