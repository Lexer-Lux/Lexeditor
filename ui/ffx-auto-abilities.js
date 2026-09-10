"use strict";

(() => {
  const nav = document.querySelector('.ffxx2-nav');
  const workspace = document.querySelector('.ffxx2-workspace');
  const x2Panel = document.querySelector('[data-panel="ffx2-abilities"]');
  if (!nav || !workspace || !x2Panel || document.querySelector('[data-panel="ffx-auto-abilities"]')) return;

  const navButton = document.createElement('button');
  navButton.type = 'button';
  navButton.dataset.view = 'ffx-auto-abilities';
  navButton.textContent = 'FFX Auto-Abilities';
  const x2Button = nav.querySelector('[data-view="ffx2-abilities"]');
  nav.insertBefore(navButton, x2Button || null);

  const panel = document.createElement('main');
  panel.className = 'ffxx2-panel';
  panel.dataset.panel = 'ffx-auto-abilities';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="ffxx2-panel-head">
      <div class="ffxx2-panel-title">
        <h2>FFX Auto-Ability Elements</h2>
        <p><span class="ffxx2-path">new_uspc/battle/kernel/a_ability.bin</span> · only known elemental bits at +0x11..+0x15 are editable.</p>
      </div>
      <button id="ffx-auto-ability-save" class="ffxx2-button save" type="button" disabled>Save edits</button>
    </div>
    <div class="ffxx2-panel-body">
      <div class="ffxx2-toolbar">
        <label>Auto-Ability<select id="ffx-auto-ability-select"></select></label>
        <button id="ffx-auto-ability-refresh" class="ffxx2-button" type="button">Refresh source</button>
      </div>
      <p id="ffx-auto-ability-summary" class="ffxx2-summary"></p>
      <div id="ffx-auto-ability-fields" class="ffxx2-slot-grid"></div>
    </div>`;
  workspace.insertBefore(panel, x2Panel);

  let state = null;
  const dirty = new Set();
  const fields = [
    ['strike', 'Strike'],
    ['absorb', 'Absorb'],
    ['immune', 'Immune'],
    ['resist', 'Resist'],
    ['weak', 'Weak'],
  ];

  function selected() {
    if (!state) return null;
    const id = Number($('ffx-auto-ability-select').value);
    return state.rows.find(row => row.id === id) || state.rows[0] || null;
  }

  function renderSelector(preferred) {
    if (!state) return;
    $('ffx-auto-ability-select').innerHTML = state.rows.map(row =>
      `<option value="${row.id}">${hex(row.abilityId)} · record ${row.id}</option>`
    ).join('');
    if (preferred != null && state.rows.some(row => row.id === preferred)) {
      $('ffx-auto-ability-select').value = String(preferred);
    }
  }

  function elementName(mask) {
    const names = state.elements.filter(element => mask & element.bit).map(element => element.label);
    return names.length ? names.join(', ') : 'None';
  }

  function render() {
    const row = selected();
    if (!row) {
      $('ffx-auto-ability-fields').innerHTML = '<div class="ffxx2-empty">No auto-ability records.</div>';
      $('ffx-auto-ability-save').disabled = true;
      return;
    }
    $('ffx-auto-ability-fields').innerHTML = fields.map(([field, label]) => {
      const mask = Number(row[field]);
      const checks = state.elements.map(element => `
        <label style="display:flex;gap:7px;align-items:center;font-weight:600;text-transform:none;letter-spacing:0">
          <input style="width:auto;min-height:0;padding:0" type="checkbox" data-element-field="${field}" data-element-bit="${element.bit}" ${mask & element.bit ? 'checked' : ''}>
          <span>${esc(element.label)}</span>
        </label>`).join('');
      return `<section class="ffxx2-slot ${dirty.has(row.id) ? 'ffxx2-dirty' : ''}" style="display:block" data-element-group="${field}">
        <div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:8px"><span>${label}</span><span class="ffxx2-hex">${hex(mask,2)}</span></div>
        <div style="display:grid;gap:6px">${checks}</div>
        <div class="ffxx2-summary" style="margin:8px 0 0">${esc(elementName(mask))}</div>
      </section>`;
    }).join('');
    const opaque = fields.map(([field, label]) => `${label} ${hex(row.unknownBits[field],2)}`).join(' · ');
    $('ffx-auto-ability-summary').textContent =
      `${hex(row.abilityId)} · record ${row.id} · ${state.source === 'project' ? 'staged FFX project override' : 'installed FFX VBF'} · ` +
      `opaque upper bits preserved (${opaque})${dirty.has(row.id) ? ' · unsaved element edit' : ''}`;
    $('ffx-auto-ability-save').disabled = dirty.size === 0;
  }

  async function refresh() {
    showError();
    const previous = selected()?.id;
    state = await api('/api/ffx-auto-abilities');
    dirty.clear();
    renderSelector(previous);
    render();
  }

  function inputChanged(target) {
    const field = target.dataset.elementField;
    const bit = Number(target.dataset.elementBit);
    const row = selected();
    if (!row || !fields.some(([key]) => key === field) || !state.elements.some(element => element.bit === bit)) return;
    if (target.checked) row[field] |= bit;
    else row[field] &= ~bit;
    row[field] &= Number(state.elementMask);
    dirty.add(row.id);
    render();
  }

  async function save() {
    showError();
    if (!state || !dirty.size) return;
    const edits = [...dirty].sort((a, b) => a - b).map(id => {
      const row = state.rows.find(item => item.id === id);
      return {
        id: row.id,
        strike: row.strike,
        absorb: row.absorb,
        immune: row.immune,
        resist: row.resist,
        weak: row.weak,
      };
    });
    const previous = selected()?.id;
    state = await api('/api/ffx-auto-abilities/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({headerMd5: state.headerMd5, baselineSha256: state.baselineSha256, edits}),
    });
    dirty.clear();
    renderSelector(previous);
    render();
    await Promise.all([refreshOverview(), refreshMap(), searchArchive()]);
  }

  $('ffx-auto-ability-select').addEventListener('change', render);
  $('ffx-auto-ability-refresh').addEventListener('click', () => refresh().catch(showError));
  $('ffx-auto-ability-save').addEventListener('click', () => save().catch(showError));
  $('ffx-auto-ability-fields').addEventListener('change', event => inputChanged(event.target));

  const originalExtractIndex = extractIndex;
  extractIndex = async function patchedAutoAbilityExtractIndex(index) {
    const entry = catalog?.entries?.[index];
    await originalExtractIndex(index);
    if (entry?.eflPath === state?.archivePath) await refresh();
  };

  refresh().catch(showError);
})();
