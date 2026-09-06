from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


# Central GitHub issue tracker, filtered by game label.
p = "plugin_api.py"
t = read(p)
t = replace_once(
    t,
    'class GitHubRepository:\n    """One owner-only issue tracker associated with a game plugin."""\n\n    full_name: str\n    authorized_logins: tuple[str, ...]\n',
    'class GitHubRepository:\n    """One owner-only issue tracker associated with a game plugin."""\n\n    full_name: str\n    authorized_logins: tuple[str, ...]\n    issue_label: str = ""\n',
    "GitHubRepository issue label",
)
write(p, t)

p = "github_integration.py"
t = read(p)
t = replace_once(
    t,
    '        return {\n            "repository": repository.full_name,\n            "login": str(login),\n        }\n',
    '        return {\n            "repository": repository.full_name,\n            "login": str(login),\n            "issueLabel": repository.issue_label,\n        }\n',
    "visible repository label",
)
t = replace_once(
    t,
    '        payload = self._json([\n            "issue", "list", "--repo", repository.full_name,\n            "--state", normalized_state, "--limit", str(normalized_limit),\n            "--json", "number,title,state,labels,updatedAt,author",\n        ])\n',
    '        arguments = [\n            "issue", "list", "--repo", repository.full_name,\n            "--state", normalized_state, "--limit", str(normalized_limit),\n        ]\n        if repository.issue_label:\n            arguments.extend(["--label", repository.issue_label])\n        arguments.extend(["--json", "number,title,state,labels,updatedAt,author"])\n        payload = self._json(arguments)\n',
    "filter GitHub issues",
)
write(p, t)

p = "desktop_host.py"
t = read(p)
t = replace_once(
    t,
    '''    def lexeditor_settings(self) -> dict:\n        """Return shared settings and managed-helper state."""\n        payload = self._settings.snapshot()\n        identity = self._github.visible_repository(LEXEDITOR_REPOSITORY)\n        payload["lexerAuthorized"] = bool(identity)\n        payload["lexerLogin"] = (identity or {}).get("login", "")\n        if not identity:\n            payload["lexerMode"] = False\n        return payload\n''',
    '''    def lexeditor_settings(self) -> dict:\n        """Return shared settings; Developer Mode is owner-authenticated."""\n        payload = self._settings.snapshot()\n        identity = self._github.visible_repository(LEXEDITOR_REPOSITORY)\n        authorized = bool(identity)\n        # There is one privileged mode: Developer Mode. It is an identity\n        # fact, not a preference. The legacy lexer field stays internal until\n        # older settings files age out.\n        payload["developerMode"] = authorized\n        payload["lexerMode"] = authorized\n        payload["lexerAuthorized"] = authorized\n        payload["lexerLogin"] = (identity or {}).get("login", "")\n        return payload\n''',
    "automatic Developer Mode",
)
t = replace_once(
    t,
    '''        lexer_mode = bool(payload.get("lexerMode"))\n        authorized = bool(self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True))\n        if lexer_mode and not authorized:\n            raise PermissionError("Lexer Mode requires Lexer's active GitHub account")\n        self._settings.save(\n            str(payload.get("updateCheckFrequency", "daily")),\n            None if "developerMode" not in payload else bool(payload["developerMode"]),\n            bool(lexer_mode) if authorized else False,\n''',
    '''        authorized = bool(self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True))\n        self._settings.save(\n            str(payload.get("updateCheckFrequency", "daily")),\n            authorized,\n            authorized,\n''',
    "save automatic Developer Mode",
)
legacy_gate = '''        if not self._settings.snapshot().get("lexerMode"):\n            raise PermissionError("Lexer Mode is not enabled")\n        if not self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True):\n            raise PermissionError("Lexer's active GitHub account is required")\n'''
t = t.replace(
    legacy_gate,
    '''        if not self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True):\n            raise PermissionError("Developer Mode requires Lexer's active GitHub account")\n''',
)
t = replace_once(
    t,
    '''    def _github_repository(self, plugin_id: str):\n        """Resolve one configured repository before the owner check."""\n        plugin = self._plugins.get(plugin_id)\n        if plugin is None:\n            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")\n        if plugin.github is None:\n            raise ValueError(f"{plugin.name} has no configured GitHub repository")\n        return plugin.github\n\n    def github_repository(self, plugin_id: str) -> dict | None:\n        """Show safe repository metadata only to an allowed active owner."""\n        plugin = self._plugins.get(plugin_id)\n        if plugin is None:\n            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")\n        if plugin.github is None:\n            return None\n        repository = self._github_repository(plugin_id)\n        return self._github.visible_repository(repository)\n''',
    '''    def _github_repository(self, plugin_id: str):\n        """Use the central Lexeditor tracker, filtered to this game."""\n        plugin = self._plugins.get(plugin_id)\n        if plugin is None:\n            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")\n        return GitHubRepository(\n            full_name=LEXEDITOR_REPOSITORY.full_name,\n            authorized_logins=LEXEDITOR_REPOSITORY.authorized_logins,\n            issue_label=plugin_id,\n        )\n\n    def github_repository(self, plugin_id: str) -> dict | None:\n        """Show the central game-filtered issue tracker to the owner."""\n        return self._github.visible_repository(self._github_repository(plugin_id))\n''',
    "central game GitHub repository",
)
write(p, t)

# Shared behavior belongs in framework.js rather than Blank-only code.
p = "ui/framework.js"
t = read(p)
t = replace_once(
    t,
    '          masterNode.style.height = `${height}px`;\n          root.classList.toggle("lex-full-table-page", !!measurement?.full);\n          detailNode.style.height = measurement?.full ? `${height}px` : "";\n',
    '          const fittedHeight = measurement?.full ? `${height}px` : "";\n          masterNode.style.height = fittedHeight;\n          root.classList.toggle("lex-full-table-page", !!measurement?.full);\n          detailNode.style.height = fittedHeight;\n',
    "barrel panel height",
)
t = replace_once(
    t,
    '  const shortReferenceName = source => {\n    if (source.shortName) return source.shortName;\n    if (String(source.name || "").toLocaleLowerCase() === "vanilla") return "V";\n',
    '  const shortReferenceName = source => {\n    if (source.shortName) return source.shortName;\n    const normalized = String(source.name || "").trim().toLocaleLowerCase();\n    if (normalized === "vanilla") return "V";\n    if (["lexer", "lexer lux", "lexer-lux", "lexer\'s mod", "lexers mod", "lexers-mod"].includes(normalized)) return "LL";\n',
    "LL reference code",
)
t = t.replace(
    'if (!button || button.querySelector(".lex-tab-ordinal")) return;',
    'if (!button || button.querySelector(".lex-tab-ordinal,.lex-tab-shortcut")) return;',
)
marker = "/* LEXEDITOR_SHARED_UI_STANDARDIZATION_20260906 */"
if marker not in t:
    t += r'''

/* LEXEDITOR_SHARED_UI_STANDARDIZATION_20260906 */
(() => {
  const ui = window.LexeditorUI;
  if (!ui || ui.__sharedStandardization20260906) return;
  ui.__sharedStandardization20260906 = true;

  const attachModelPreview = (panel, spec) => {
    if (!(panel instanceof Element) || !spec) return panel;
    const heading = panel.querySelector(':scope > .lex-detail-panel-heading');
    const icon = heading?.querySelector('.lex-detail-panel-icon');
    if (!heading || !icon) return panel;
    const getContent = typeof spec === 'function' ? spec : () => spec.content;
    const onOpen = typeof spec === 'object' ? spec.onOpen : null;
    const onClose = typeof spec === 'object' ? spec.onClose : null;
    const drawer = document.createElement('section');
    drawer.className = 'lex-model-preview-drawer';
    drawer.hidden = true;
    drawer.setAttribute('aria-label', typeof spec === 'object' && spec.label ? spec.label : 'Model preview');
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'lex-model-preview-close';
    close.textContent = '×';
    close.title = 'Close model preview';
    close.setAttribute('aria-label', close.title);
    heading.append(close);
    heading.after(drawer);
    const open = async () => {
      if (!drawer.childNodes.length) {
        const content = await getContent?.();
        if (content instanceof Node) drawer.append(content);
      }
      drawer.hidden = false;
      panel.classList.add('lex-model-preview-open');
      icon.setAttribute('aria-expanded', 'true');
      await onOpen?.(drawer);
    };
    const shut = async () => {
      await onClose?.(drawer);
      panel.classList.remove('lex-model-preview-open');
      drawer.hidden = true;
      icon.setAttribute('aria-expanded', 'false');
    };
    icon.classList.add('lex-model-preview-trigger');
    icon.tabIndex = 0;
    icon.setAttribute('role', 'button');
    icon.setAttribute('aria-label', typeof spec === 'object' && spec.openLabel ? spec.openLabel : 'Open model preview');
    icon.setAttribute('aria-expanded', 'false');
    icon.addEventListener('click', open);
    icon.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
    close.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      shut();
    });
    panel.lexModelPreview = {open, close: shut, drawer};
    return panel;
  };
  ui.attachModelPreview = attachModelPreview;
  const originalDetailPanel = ui.detailPanel;
  ui.detailPanel = options => {
    const panel = originalDetailPanel(options);
    return options?.modelPreview ? attachModelPreview(panel, options.modelPreview) : panel;
  };

  const hoverKey = node => node?.dataset?.lexProperty || node?.dataset?.columnKey || '';
  document.addEventListener('pointerover', event => {
    const node = event.target.closest?.('.lex-detail-field,[data-column-key]');
    if (!node) return;
    node.classList.add('lex-self-hover');
    const key = hoverKey(node);
    if (!key) return;
    const escaped = CSS.escape(String(key));
    document.querySelectorAll(`[data-column-key="${escaped}"],[data-lex-property="${escaped}"]`)
      .forEach(peer => peer.classList.add('lex-column-lit'));
  });
  document.addEventListener('pointerout', event => {
    const node = event.target.closest?.('.lex-detail-field,[data-column-key]');
    if (!node || node.contains(event.relatedTarget)) return;
    node.classList.remove('lex-self-hover');
    const key = hoverKey(node);
    if (!key) return;
    const escaped = CSS.escape(String(key));
    document.querySelectorAll(`[data-column-key="${escaped}"],[data-lex-property="${escaped}"]`)
      .forEach(peer => peer.classList.remove('lex-column-lit'));
  });

  document.addEventListener('click', event => {
    const label = event.target.closest?.('.lex-boolean-field > .lex-detail-field-label');
    if (!label) return;
    const input = label.parentElement?.querySelector('.lex-detail-field-control input[type="checkbox"]');
    if (!input || input.disabled) return;
    event.preventDefault();
    input.click();
  });

  const syncRange = field => {
    if (!field) return;
    const number = field.querySelector('input[type="number"]');
    const range = field.querySelector('input[type="range"]');
    if (number && range && range.value !== number.value) {
      range.value = number.value;
      range.dispatchEvent(new Event('input', {bubbles: true}));
    }
  };
  document.addEventListener('contextmenu', event => {
    const field = event.target.closest?.('.lex-detail-field');
    if (!field) return;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      syncRange(field);
      const target = getComputedStyle(field).backgroundColor;
      const accent = getComputedStyle(document.documentElement).getPropertyValue('--lex-accent').trim() || target;
      field.animate(
        [{backgroundColor: accent}, {backgroundColor: target}],
        {duration: 420, easing: 'cubic-bezier(.2,.75,.2,1)'},
      );
    }));
  }, true);

  const dedupeShortcuts = root => root.querySelectorAll?.('nav button[data-tab]').forEach(button => {
    if (button.querySelector('.lex-tab-shortcut')) {
      button.querySelectorAll('.lex-tab-ordinal').forEach(node => node.remove());
    }
  });
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node instanceof Element) dedupeShortcuts(node.closest('header') || node);
  }))).observe(document.documentElement, {childList: true, subtree: true});
  dedupeShortcuts(document);

  const fitLabel = label => {
    if (!(label instanceof HTMLElement)) return;
    label.style.fontSize = '';
    let size = parseFloat(getComputedStyle(label).fontSize) || 12;
    while (size > 8 && (label.scrollHeight > label.clientHeight + 1 || label.scrollWidth > label.clientWidth + 1)) {
      size -= .5;
      label.style.fontSize = `${size}px`;
    }
  };
  const fitAllLabels = root => root.querySelectorAll?.(
    '.lex-detail-field-label,.lex-toggle-label,.lex-flag-label',
  ).forEach(fitLabel);
  const labelObserver = new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node instanceof Element) fitAllLabels(node);
  })));
  labelObserver.observe(document.documentElement, {childList: true, subtree: true});
  window.addEventListener('resize', () => fitAllLabels(document));
  requestAnimationFrame(() => fitAllLabels(document));
})();
'''
write(p, t)

p = "ui/framework.css"
t = read(p)
css_marker = "/* LEXEDITOR_SHARED_UI_STANDARDIZATION_20260906 */"
if css_marker not in t:
    t += r'''

/* LEXEDITOR_SHARED_UI_STANDARDIZATION_20260906 */
:root { --lex-detail-label-width:10%; }
.lex-detail-field { grid-template-columns:var(--lex-detail-label-width) minmax(0,1fr); }
.lex-detail-field-label {
  min-width:0; min-height:0; height:100%; overflow:hidden;
  white-space:normal; overflow-wrap:anywhere; line-height:1.05;
  align-content:center; text-align:center;
}
.lex-info-help {
  display:inline-grid !important; place-items:center !important;
  align-items:center !important; justify-items:center !important;
  padding:0 !important; line-height:1 !important; text-align:center !important;
}
.lex-info-help::before,
.lex-info-help > * { place-self:center !important; line-height:1 !important; transform:none !important; }
.lex-field-type-rail .lex-info-help {
  position:absolute; left:50%; top:50%; transform:translate(-50%,-50%) !important;
}
.lex-reference-values .lex-reference-value { align-items:center; padding-block:1px 2px; }
.lex-reference-values .lex-reference-tag { margin-right:.28em; align-self:center; }
.lex-reference-values .lex-boolean-mark { display:inline-grid; place-items:center; margin:0; line-height:1; }
.lex-reference-tag.lex-reference-ll { color:#72ff1e !important; }
.lex-detail-field-control :is(.lex-toggle-label,.lex-flag-label,.lex-bit-label,.flag-list label) {
  writing-mode:horizontal-tb !important; transform:none !important;
  min-width:0; white-space:normal; overflow-wrap:anywhere; text-orientation:mixed;
}
.lex-column-list-cell.lex-cell-editing { min-width:0; padding:inherit; font:inherit; }
.lex-cell-editing .lex-column-cell-content { display:block; width:100%; min-width:0; height:100%; }
.lex-cell-editing .lex-column-cell-content > :is(input,select,textarea) {
  box-sizing:border-box; width:100%; min-width:0; height:100%; min-height:0;
  margin:0; padding:0; border:0; border-radius:0; outline:1px solid var(--lex-accent);
  outline-offset:-1px; background:transparent; color:inherit; font:inherit; line-height:inherit;
}
.lex-detail-field:hover,.lex-detail-field.lex-self-hover,
.lex-column-list-cell:hover,.lex-column-list-head-cell:hover,
.lex-column-list-cell.lex-self-hover,.lex-column-list-head-cell.lex-self-hover {
  background:color-mix(in srgb,var(--lex-highlight) 8%,transparent);
}
.lex-detail-field-control,
.lex-detail-field-control > *,
.lex-detail-field-control input[type="range"],
.lex-unit-field { min-width:0; max-width:100%; box-sizing:border-box; }
.lex-detail-field-control input[type="range"] { width:100%; }
.lex-boolean-field .lex-field-boolean-arrow {
  position:static !important; align-self:center; transform:none !important;
}
.lex-paged-list-detail,.lex-barrelled-master,.lex-barrel-grid { min-height:0; }
.lex-paged-list-detail:not(.lex-full-table-page) .lex-barrelled-master,
.lex-paged-list-detail:not(.lex-full-table-page) .lex-detail-panel { align-self:stretch; height:auto; }
.lex-model-preview-trigger { cursor:pointer; }
.lex-model-preview-close {
  display:none; box-sizing:border-box; width:var(--lex-detail-icon-size,64px);
  height:var(--lex-detail-icon-size,64px); padding:0; border:0; background:transparent;
  color:inherit; font:700 1.6em/1 var(--lex-symbol-font); place-items:center; cursor:pointer;
}
.lex-model-preview-open > .lex-detail-panel-heading .lex-detail-panel-icon {
  visibility:hidden; pointer-events:none;
}
.lex-model-preview-open > .lex-detail-panel-heading .lex-model-preview-close { display:grid; }
.lex-model-preview-drawer {
  min-width:0; min-height:260px; overflow:hidden;
  transform-origin:top; animation:lex-model-preview-open .2s ease-out both;
}
@keyframes lex-model-preview-open {
  from { opacity:0; transform:translateY(-10px); }
  to { opacity:1; transform:translateY(0); }
}
.lex-settings-lane-lexer,.lex-lexer-setting { display:none !important; }
.lex-tab-ordinal { display:none !important; }
.lex-project-reference:has(.lex-project-source-status.disabled),
.lex-project-menu-item:has(.lex-project-source-status.disabled) {
  position:relative; filter:grayscale(1); opacity:.48;
}
.lex-project-reference:has(.lex-project-source-status.disabled)::after,
.lex-project-menu-item:has(.lex-project-source-status.disabled)::after {
  content:""; position:absolute; inset:0; background:rgb(128 128 128 / 18%); pointer-events:none;
}
.lex-curve-editor { overflow:visible; }
.lex-curve-heading :is(h2,h3,.lex-curve-title) {
  text-transform:uppercase; font-size:clamp(24px,3vw,42px) !important;
  line-height:1 !important; transform:none !important; font-stretch:normal !important;
  letter-spacing:.04em !important;
}
.lex-curve-editor::before { content:none !important; display:none !important; }
.lex-curve-path-formula,.lex-curve-path-formula * { transform:none; font-stretch:normal; }
.lex-curve-variables.lex-curve-variable-strip {
  position:absolute; z-index:5; top:0; left:50%; right:auto; bottom:auto;
  max-width:min(92%,900px); transform:translate(-50%,-105%);
  transition:transform .18s ease,opacity .18s ease; opacity:.92;
}
.lex-curve-editor:focus-within .lex-curve-variables.lex-curve-variable-strip,
.lex-curve-editor:hover .lex-curve-variables.lex-curve-variable-strip {
  transform:translate(-50%,0); opacity:1;
}
.lex-curve-axis { transform:none !important; }
.lex-curve-axis-right,.lex-curve-y-axis-right,
.lex-curve-right-axis :is(.lex-curve-axis,.lex-curve-axis-label,.lex-curve-axis-number) {
  writing-mode:vertical-rl; transform:rotate(180deg) !important; text-orientation:mixed;
}
'''
write(p, t)

# Blank: remove Design Review / obsolete Editable Table route and make the three
# panel gallery reuse the pageable/barrelled table implementation.
p = "games/blank/editor.html"
t = read(p)
t = t.replace('  <link rel="stylesheet" href="/shared/design-review.css">\n', '')
t = t.replace('  <script src="/shared/design-review.js"></script>\n', '')
t = t.replace('if(tab==="design")layout=LexeditorDesignReview.render();else ', '')
t = t.replace(
    'else if(tab==="editable")layout=panelLayout([editableTablePanel()],"blank-layout",{layoutKey:"blank-editable",defaultSizes:[100]});',
    '',
)
t = t.replace('{id:"design",label:"Design Review"},', '')
t = t.replace('{id:"editable",label:"Editable Table"},', '')
t = t.replace(
    'else if(tab==="three")layout=panelLayout([tablePanel(),recordPanel(),inspectorPanel()],"blank-layout",{layoutKey:"blank-three",defaultSizes:[34,38,28],minSizes:[280,340,260],stackAt:980});',
    'else if(tab==="three")layout=panelLayout([pagedTwoPanel(),inspectorPanel()],"blank-layout blank-three-layout",{layoutKey:"blank-three",defaultSizes:[72,28],minSizes:[620,260],stackAt:980});',
)
write(p, t)

# Warband model preview uses the shared detail-panel drawer.
p = "games/warband/editor.html"
t = read(p)
t = replace_once(
    t,
    '''    let data=null,open=true,generation=0;\n    const action=el("button",{class:"warband-item-preview-action",disabled:true,title:"Checking mesh and texture dependencies…","aria-label":"Close 3D preview"},"×");\n    const detail=detailPanel({className:"warband-item-detail",icon:thumbnail,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(item.name,24)),identity:item.id,actions:action,\n      body:[el("div",{class:"warband-mesh-list"},el("b",{},"Meshes: "),item.meshes.length?item.meshes.join(" · "):"None"),stage,facts]});\n''',
    '''    let data=null,open=false,generation=0;\n    const previewBody=el("div",{class:"warband-shared-model-preview"},stage,facts);\n    const detail=detailPanel({className:"warband-item-detail",icon:thumbnail,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(item.name,24)),identity:item.id,\n      body:[el("div",{class:"warband-mesh-list"},el("b",{},"Meshes: "),item.meshes.length?item.meshes.join(" · "):"None")],\n      modelPreview:{content:previewBody,label:`${item.name} 3D model preview`,onOpen:async()=>{open=true;generation++;if(data)await showPreview();},onClose:()=>{open=false;generation++;disposeWarbandPreview();}}});\n''',
    "Warband shared preview setup",
)
t = t.replace(
    '        window.__warbandPreview=[controller];message.hidden=true;action.disabled=false;action.title="Close 3D preview";\n',
    '        window.__warbandPreview=[controller];message.hidden=true;\n',
)
t = t.replace(
    '    action.onclick=()=>{open=!open;generation++;stage.hidden=!open;disposeWarbandPreview();action.textContent=open?"×":"◉";action.setAttribute("aria-label",open?"Close 3D preview":"Open 3D preview");action.title=action.getAttribute("aria-label");if(open){action.disabled=true;showPreview();}};\n',
    '',
)
t = t.replace('        await showPreview();\n', '        if(open)await showPreview();\n')
t = t.replace(
    '      }catch(error){if(detail.isConnected){message.textContent=error.message;action.title=error.message;}}\n',
    '      }catch(error){if(detail.isConnected){message.textContent=error.message;message.title=error.message;}}\n',
)
write(p, t)

# Manual terminology and architecture.
p = "docs/UI-MANUAL.md"
t = read(p)
t = t.replace(
    'A **reference rail** shows only values that differ from the current value.',
    'A **ref rail** shows only values that differ from the current value.',
)
t = t.replace(
    'A reference rail is a vertical stack with at most four sources.',
    'A ref rail is a vertical stack with at most four sources.',
)
t = t.replace(
    'Reference values always use the same player-facing format as the live value.',
    'Ref-rail values always use the same player-facing format as the live value.',
)
t = replace_once(
    t,
    '''A value with only two valid states is a boolean control. A numeric 0/1 input\nmust not be used when a checkbox or compact check/X toggle can prevent invalid\nvalues.\n''',
    '''Every variable uses the most human-friendly semantic control available; its raw\nstorage representation is an implementation detail, not UI. Booleans are normally\ncheckboxes. A **checkless toggle** is the compact on/off alternative when a checkbox\nwould add visual noise. A stored `0/1` is never exposed as a numeric field. Enums\nshow named choices. Bitflags are decomposed into a property group of checkboxes,\ncheckless toggles and/or enum controls as appropriate; never expose a whole flag\nbyte or integer merely because that is how the game stores it. Raw numbers are for\nvalues that are genuinely numeric to a human.\n''',
    "semantic control manual",
)
t = t.replace(
    '''Help uses a filled circular `?`. The component shape and interaction are\nshared. Its glyph uses the active game's font when that font contains a usable\nquestion mark.\n''',
    '''An **info bubble** is the filled circular `?` beside a property. Its circle,\nglyph, placement and interaction are shared. It is centred in the metadata space\nbetween the panel edge and the property label, and its glyph is centred inside the\ncircle.\n''',
)
start = t.find("## Setting scopes\n")
end = t.find("## Setting dependencies\n")
if start < 0 or end < 0 or end <= start:
    raise SystemExit("settings manual section not found")
replacement = '''## Developer Mode\n\nLexeditor has one privileged mode: **Developer Mode**. It activates automatically\nonly when the active GitHub CLI account is the authorized `Lexer-Lux` account and\nis not a user preference. Developer Mode exposes diagnostics, the embedded GitHub\nworkspace, helper/version authoring, distributable defaults and shared layout\nauthoring. Signing out (or switching GitHub accounts) disables those privileges.\nThere is no separate Lexer Mode.\n\nHolding right-click on a page tab to save its layout for everyone is therefore a\nDeveloper Mode authoring action. Ordinary page and setting changes remain local.\n\n## Model preview drawer\n\nA Detail panel can declare an optional **model preview drawer**. The standard\nheader icon is its open control. Activating that icon slides the preview out from\nthe Detail panel; while open, an `×` occupies exactly the same header-icon slot\nand closes it. Plugins provide only the preview content/lifecycle callbacks. They\nmust not invent a separate preview-panel type or a different close position.\n\n'''
t = t[:start] + replacement + t[end:]
write(p, t)

p = "docs/ADDING_A_GAME.md"
t = read(p)
if "central Lexeditor issue tracker" not in t:
    t += '''\n\n## Shared UI contracts\n\nDo not clone Blank-specific markup into a plugin. Blank exercises the same shared\nframework controls that every plugin receives. Use `detailPanel({modelPreview: …})`\nfor model previews; the framework owns the drawer and header-icon open/close slot.\nEvery game uses the central Lexeditor issue tracker; the host filters it by the\nplugin id label. Variable editors must expose semantic human controls rather than\nraw storage encodings (checkbox/toggle for booleans, named enums, decomposed\nbitflags).\n'''
write(p, t)
