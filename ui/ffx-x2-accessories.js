"use strict";

(() => {
  if (!document.querySelector('script[data-ffxx2-launch]')) {
    const launchScript = document.createElement('script');
    launchScript.src = '/shared/ffx-x2-launch.js';
    launchScript.dataset.ffxx2Launch = '1';
    document.head.appendChild(launchScript);
  }
  if (!document.querySelector('script[data-ffx-commands]')) {
    const commandScript = document.createElement('script');
    commandScript.src = '/shared/ffx-commands.js';
    commandScript.dataset.ffxCommands = '1';
    document.head.appendChild(commandScript);
  }

  const nav = document.querySelector('.ffxx2-nav');
  const workspace = document.querySelector('.ffxx2-workspace');
  const archivesPanel = document.querySelector('[data-panel="archives"]');
  if (!nav || !workspace || !archivesPanel || document.querySelector('[data-panel="ffx2-accessories"]')) return;

  const navButton = document.createElement('button');
  navButton.type = 'button';
  navButton.dataset.view = 'ffx2-accessories';
  navButton.textContent = 'X-2 Accessories';
  const archiveButton = nav.querySelector('[data-view="archives"]');
  nav.insertBefore(navButton, archiveButton || null);

  const panel = document.createElement('main');
  panel.className = 'ffxx2-panel';
  panel.dataset.panel = 'ffx2-accessories';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="ffxx2-panel-head">
      <div class="ffxx2-panel-title">
        <h2>FFX-2 Accessories</h2>
        <p><span class="ffxx2-path">new_uspc/battle/kernel/accessory.bin</span> · four base ability IDs and price only; creature/string data stays opaque.</p>
      </div>
      <button id="x2-accessory-save" class="ffxx2-button save" type="button" disabled>Save edits</button>
    </div>
    <div class="ffxx2-panel-body">
      <div class="ffxx2-toolbar">
        <label>Accessory<select id="x2-accessory-select"></select></label>
        <button id="x2-accessory-refresh" class="ffxx2-button" type="button">Refresh source</button>
      </div>
      <p id="x2-accessory-summary" class="ffxx2-summary"></p>
      <div id="x2-accessory-fields" class="ffxx2-slot-grid"></div>
    </div>`;
  workspace.insertBefore(panel, archivesPanel);

  const x2Card = document.querySelector('[data-panel="dashboard"] .ffxx2-dashboard-card:nth-child(2)');
  if (x2Card) {
    const detail = x2Card.querySelector('p');
    const count = x2Card.querySelector('.big');
    if (detail) detail.textContent = 'Command animation IDs plus accessory base abilities/prices are structured; text and accessory creature-extension data remain read-only.';
    if (count) count.textContent = '2 editors';
  }

  let state = null;
  const dirty = new Map();

  function selected() {
    if (!state) return null;
    const id = Number($('x2-accessory-select').value);
    return state.rows.find(row => row.id === id) || state.rows[0] || null;
  }

  function dirtyRecord(id) {
    if (!dirty.has(id)) dirty.set(id, {price: false, abilities: new Set()});
    return dirty.get(id);
  }

  function dirtyCount() {
    let count = 0;
    for (const value of dirty.values()) count += (value.price ? 1 : 0) + value.abilities.size;
    return count;
  }

  function renderSelector(preferred) {
    if (!state) return;
    $('x2-accessory-select').innerHTML = state.rows.map(row =>
      `<option value="${row.id}">${row.id} · ${hex(row.id)} · icon ${row.icon} · ${row.price} gil</option>`
    ).join('');
    if (preferred != null && state.rows.some(row => row.id === preferred)) {
      $('x2-accessory-select').value = String(preferred);
    }
  }

  function render() {
    const row = selected();
    if (!row) {
      $('x2-accessory-fields').innerHTML = '<div class="ffxx2-empty">No accessory records.</div>';
      $('x2-accessory-save').disabled = true;
      return;
    }
    const changed = dirty.get(row.id) || {price: false, abilities: new Set()};
    const cards = [
      `<label class="ffxx2-slot ${changed.price ? 'ffxx2-dirty' : ''}" data-x2-accessory-price>
        <span>Base price</span><span class="ffxx2-hex">u32</span>
        <input aria-label="Accessory ${row.id} price" type="number" min="0" max="4294967295" value="${row.price}">
      </label>`,
      ...row.abilityIds.map((abilityId, slot) =>
        `<label class="ffxx2-slot ${changed.abilities.has(slot) ? 'ffxx2-dirty' : ''}" data-x2-accessory-ability="${slot}">
          <span>Ability ${slot + 1}</span><span class="ffxx2-hex">${hex(abilityId)}</span>
          <input aria-label="Accessory ${row.id} ability ${slot + 1}" type="number" min="0" max="65535" value="${abilityId}">
        </label>`
      )
    ];
    $('x2-accessory-fields').innerHTML = cards.join('');
    const count = dirtyCount();
    $('x2-accessory-save').disabled = count === 0;
    $('x2-accessory-summary').textContent =
      `Accessory ${row.id} (${hex(row.id)}) · icon ${row.icon} · ` +
      `name ref ${hex(row.nameOffset)}/${hex(row.nameKey)} · help ref ${hex(row.helpOffset)}/${hex(row.helpKey)} · ` +
      `${state.source === 'project' ? 'staged X-2 project override' : 'installed FFX-2 VBF'}${count ? ` · ${count} unsaved field(s)` : ''}`;
  }

  async function refresh() {
    showError();
    const previous = selected()?.id;
    state = await api('/api/ffx2-accessories');
    dirty.clear();
    renderSelector(previous);
    render();
  }

  function inputChanged(target) {
    const row = selected();
    if (!row) return;
    const changed = dirtyRecord(row.id);
    const priceCard = target.closest('[data-x2-accessory-price]');
    if (priceCard) {
      row.price = Number(target.value);
      changed.price = true;
      priceCard.classList.add('ffxx2-dirty');
    }
    const abilityCard = target.closest('[data-x2-accessory-ability]');
    if (abilityCard) {
      const slot = Number(abilityCard.dataset.x2AccessoryAbility);
      row.abilityIds[slot] = Number(target.value);
      changed.abilities.add(slot);
      abilityCard.classList.add('ffxx2-dirty');
      const label = abilityCard.querySelector('.ffxx2-hex');
      if (label) label.textContent = hex(row.abilityIds[slot]);
    }
    $('x2-accessory-save').disabled = false;
    render();
  }

  async function save() {
    showError();
    if (!state || !dirtyCount()) return;
    const edits = [...dirty.entries()].sort((a, b) => a[0] - b[0]).map(([id, changed]) => {
      const row = state.rows.find(item => item.id === id);
      const edit = {id};
      if (changed.price) edit.price = row.price;
      if (changed.abilities.size) {
        edit.abilities = [...changed.abilities].sort((a, b) => a - b).map(slot => ({slot, abilityId: row.abilityIds[slot]}));
      }
      return edit;
    });
    const previous = selected()?.id;
    state = await api('/api/ffx2-accessories/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({headerMd5: state.headerMd5, baselineSha256: state.baselineSha256, edits}),
    });
    dirty.clear();
    renderSelector(previous);
    render();
    await Promise.all([refreshOverview(), refreshMap(), searchArchive()]);
  }

  $('x2-accessory-select').addEventListener('change', render);
  $('x2-accessory-refresh').addEventListener('click', () => refresh().catch(showError));
  $('x2-accessory-save').addEventListener('click', () => save().catch(showError));
  $('x2-accessory-fields').addEventListener('input', event => inputChanged(event.target));

  const originalExtractIndex = extractIndex;
  extractIndex = async function patchedExtractIndex(index) {
    const entry = catalog?.entries?.[index];
    await originalExtractIndex(index);
    if (entry?.eflPath === state?.archivePath) await refresh();
  };

  refresh().catch(showError);
})();
