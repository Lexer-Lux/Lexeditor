"use strict";

(() => {
  const nav = document.querySelector('.ffxx2-nav');
  const workspace = document.querySelector('.ffxx2-workspace');
  const x2Panel = document.querySelector('[data-panel="ffx2-abilities"]');
  if (!nav || !workspace || !x2Panel || document.querySelector('[data-panel="ffx-player-stats"]')) return;

  const navButton = document.createElement('button');
  navButton.type = 'button';
  navButton.dataset.view = 'ffx-player-stats';
  navButton.textContent = 'FFX Base Stats';
  const x2Button = nav.querySelector('[data-view="ffx2-abilities"]');
  nav.insertBefore(navButton, x2Button || null);

  const panel = document.createElement('main');
  panel.className = 'ffxx2-panel';
  panel.dataset.panel = 'ffx-player-stats';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="ffxx2-panel-head">
      <div class="ffxx2-panel-title">
        <h2>FFX Player Base Stats</h2>
        <p><span class="ffxx2-path">new_uspc/battle/kernel/ply_save.bin</span> · only the independently agreed base-stat prefix at +0x04..+0x13 is editable.</p>
      </div>
      <button id="ffx-player-save" class="ffxx2-button save" type="button" disabled>Save edits</button>
    </div>
    <div class="ffxx2-panel-body">
      <div class="ffxx2-toolbar">
        <label>Record<select id="ffx-player-select"></select></label>
        <button id="ffx-player-refresh" class="ffxx2-button" type="button">Refresh source</button>
      </div>
      <p id="ffx-player-summary" class="ffxx2-summary"></p>
      <div id="ffx-player-fields" class="ffxx2-slot-grid"></div>
    </div>`;
  workspace.insertBefore(panel, x2Panel);

  const ffxCard = document.querySelector('[data-panel="dashboard"] .ffxx2-dashboard-card:nth-child(1)');
  if (ffxCard) {
    const detail = ffxCard.querySelector('p');
    const count = ffxCard.querySelector('.big');
    if (detail) detail.textContent = 'Treasure rewards, prices, player base stats, CTB timing, Mix results, shops, ability animations, and auto-ability element masks are patched surgically.';
    if (count) count.textContent = '13 editors';
  }

  const fieldSpecs = [
    ['baseHp', 'Base HP', 0, 4294967295],
    ['baseMp', 'Base MP', 0, 4294967295],
    ['strength', 'Strength', 0, 255],
    ['defense', 'Defense', 0, 255],
    ['magic', 'Magic', 0, 255],
    ['magicDefense', 'Magic Defense', 0, 255],
    ['agility', 'Agility', 0, 255],
    ['luck', 'Luck', 0, 255],
    ['evasion', 'Evasion', 0, 255],
    ['accuracy', 'Accuracy', 0, 255],
  ];
  let state = null;
  const dirty = new Set();

  function selected() {
    if (!state) return null;
    const id = Number($('ffx-player-select').value);
    return state.rows.find(row => row.id === id) || state.rows[0] || null;
  }

  function renderSelector(preferred) {
    if (!state) return;
    $('ffx-player-select').innerHTML = state.rows.map(row =>
      `<option value="${row.id}">Record ${row.id} · ${hex(row.id)}</option>`
    ).join('');
    if (preferred != null && state.rows.some(row => row.id === preferred)) {
      $('ffx-player-select').value = String(preferred);
    }
  }

  function render() {
    const row = selected();
    if (!row) {
      $('ffx-player-fields').innerHTML = '<div class="ffxx2-empty">No player-stat records.</div>';
      $('ffx-player-save').disabled = true;
      return;
    }
    $('ffx-player-fields').innerHTML = fieldSpecs.map(([key, label, minimum, maximum]) => `
      <label class="ffxx2-slot ${dirty.has(row.id) ? 'ffxx2-dirty' : ''}" data-player-field="${key}">
        <span>${esc(label)}</span><span class="ffxx2-hex">${Number(row[key]).toLocaleString()}</span>
        <input aria-label="${esc(label)} for player-stat record ${row.id}" type="number" min="${minimum}" max="${maximum}" step="1" value="${row[key]}">
      </label>`).join('');
    $('ffx-player-summary').textContent =
      `Record ${row.id} (${hex(row.id)}) · ${state.source === 'project' ? 'staged FFX project override' : 'installed FFX VBF'} · ` +
      `0x${Number(state.recordSize).toString(16).toUpperCase()} bytes/record · bytes +0x14 onward remain opaque${dirty.has(row.id) ? ' · unsaved base-stat edit' : ''}`;
    $('ffx-player-save').disabled = dirty.size === 0;
  }

  async function refresh() {
    showError();
    const previous = selected()?.id;
    state = await api('/api/ffx-player-stats');
    dirty.clear();
    renderSelector(previous);
    render();
  }

  function inputChanged(target) {
    const wrapper = target.closest('[data-player-field]');
    const row = selected();
    if (!wrapper || !row) return;
    const key = wrapper.dataset.playerField;
    if (!fieldSpecs.some(([field]) => field === key)) return;
    row[key] = Number(target.value);
    dirty.add(row.id);
    render();
  }

  async function save() {
    showError();
    if (!state || !dirty.size) return;
    const edits = [...dirty].sort((a, b) => a - b).map(id => {
      const row = state.rows.find(item => item.id === id);
      return Object.fromEntries([
        ['id', row.id],
        ...fieldSpecs.map(([key]) => [key, row[key]]),
      ]);
    });
    const previous = selected()?.id;
    state = await api('/api/ffx-player-stats/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({headerMd5: state.headerMd5, baselineSha256: state.baselineSha256, edits}),
    });
    dirty.clear();
    renderSelector(previous);
    render();
    await Promise.all([refreshOverview(), refreshMap(), searchArchive()]);
  }

  $('ffx-player-select').addEventListener('change', render);
  $('ffx-player-refresh').addEventListener('click', () => refresh().catch(showError));
  $('ffx-player-save').addEventListener('click', () => save().catch(showError));
  $('ffx-player-fields').addEventListener('input', event => inputChanged(event.target));

  const originalExtractIndex = extractIndex;
  extractIndex = async function patchedPlayerStatsExtractIndex(index) {
    const entry = catalog?.entries?.[index];
    await originalExtractIndex(index);
    if (entry?.eflPath === state?.archivePath) await refresh();
  };

  refresh().catch(showError);
})();
