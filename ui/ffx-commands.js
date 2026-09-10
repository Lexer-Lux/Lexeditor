"use strict";

(() => {
  const nav = document.querySelector('.ffxx2-nav');
  const workspace = document.querySelector('.ffxx2-workspace');
  const x2Panel = document.querySelector('[data-panel="ffx2-abilities"]');
  if (!nav || !workspace || !x2Panel || document.querySelector('[data-panel="ffx-commands"]')) return;

  const navButton = document.createElement('button');
  navButton.type = 'button';
  navButton.dataset.view = 'ffx-commands';
  navButton.textContent = 'FFX Abilities';
  const x2Button = nav.querySelector('[data-view="ffx2-abilities"]');
  nav.insertBefore(navButton, x2Button || null);

  const panel = document.createElement('main');
  panel.className = 'ffxx2-panel';
  panel.dataset.panel = 'ffx-commands';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="ffxx2-panel-head">
      <div class="ffxx2-panel-title">
        <h2>FFX Ability Animations</h2>
        <p><span id="ffx-command-path" class="ffxx2-path">new_uspc/battle/kernel/command.bin</span> · only animation IDs at record +0x10/+0x12 are editable.</p>
      </div>
      <button id="ffx-command-save" class="ffxx2-button save" type="button" disabled>Save edits</button>
    </div>
    <div class="ffxx2-panel-body">
      <div class="ffxx2-toolbar">
        <label>Table<select id="ffx-command-table">
          <option value="command">Commands</option>
          <option value="item">Items</option>
          <option value="monmagic1">Monster Magic 1</option>
          <option value="monmagic2">Monster Magic 2</option>
        </select></label>
        <label class="ffxx2-grow">Filter<input id="ffx-command-filter" type="search" placeholder="record or animation ID …"></label>
        <button id="ffx-command-refresh" class="ffxx2-button" type="button">Refresh source</button>
      </div>
      <p id="ffx-command-summary" class="ffxx2-summary"></p>
      <div class="ffxx2-table-wrap"><table class="ffxx2-table">
        <thead><tr><th>Record</th><th>Animation 1</th><th>Animation 2</th></tr></thead>
        <tbody id="ffx-command-rows"></tbody>
      </table></div>
    </div>`;
  workspace.insertBefore(panel, x2Panel);

  const ffxCard = document.querySelector('[data-panel="dashboard"] .ffxx2-dashboard-card:nth-child(1)');
  if (ffxCard) {
    const detail = ffxCard.querySelector('p');
    const count = ffxCard.querySelector('.big');
    if (detail) detail.textContent = 'Treasure rewards, prices, CTB timing, Mix results, shops, and four proved FFX ability-animation tables are patched surgically.';
    if (count) count.textContent = '11 editors';
  }

  let state = null;
  const dirty = new Set();

  function tableKey() {
    return $('ffx-command-table').value;
  }

  function render() {
    if (!state) return;
    const needle = $('ffx-command-filter').value.trim().toLowerCase();
    const rows = state.rows.filter(row => !needle ||
      `${row.id} ${hex(row.id)} ${row.animation1} ${hex(row.animation1)} ${row.animation2} ${hex(row.animation2)}`.toLowerCase().includes(needle));
    $('ffx-command-rows').innerHTML = rows.map(row => `
      <tr data-ffx-command="${row.id}" class="${dirty.has(row.id) ? 'ffxx2-dirty' : ''}">
        <td class="ffxx2-hex">${row.id} · ${hex(row.id)}</td>
        <td><input data-field="animation1" type="number" min="0" max="65535" value="${row.animation1}"> <span class="ffxx2-hex">${hex(row.animation1)}</span></td>
        <td><input data-field="animation2" type="number" min="0" max="65535" value="${row.animation2}"> <span class="ffxx2-hex">${hex(row.animation2)}</span></td>
      </tr>`).join('') || `<tr><td class="ffxx2-empty" colspan="3">No ${esc(state.label || 'FFX ability')} records match this filter.</td></tr>`;
    $('ffx-command-save').disabled = dirty.size === 0;
    $('ffx-command-path').textContent = state.archivePath.replace(/^FFX_Data\/ffx_ps2\/ffx\/master\//, '');
    $('ffx-command-summary').textContent =
      `${state.rows.length.toLocaleString()} ${state.label.toLowerCase()} record(s) · ` +
      `${state.source === 'project' ? 'staged FFX project override' : 'installed FFX VBF'} · ` +
      `0x${Number(state.recordSize).toString(16).toUpperCase()} bytes/record${dirty.size ? ` · ${dirty.size} unsaved` : ''}`;
  }

  async function refresh() {
    showError();
    const selected = tableKey();
    state = await api(`/api/ffx-commands?table=${encodeURIComponent(selected)}`);
    dirty.clear();
    render();
  }

  function inputChanged(target) {
    const tr = target.closest('[data-ffx-command]');
    if (!tr || !state) return;
    const id = Number(tr.dataset.ffxCommand);
    const row = state.rows.find(item => item.id === id);
    if (!row) return;
    row.animation1 = Number(tr.querySelector('[data-field="animation1"]').value);
    row.animation2 = Number(tr.querySelector('[data-field="animation2"]').value);
    dirty.add(id);
    tr.classList.add('ffxx2-dirty');
    const labels = tr.querySelectorAll('input + .ffxx2-hex');
    if (labels[0]) labels[0].textContent = hex(row.animation1);
    if (labels[1]) labels[1].textContent = hex(row.animation2);
    $('ffx-command-save').disabled = false;
    $('ffx-command-summary').textContent = `${state.rows.length.toLocaleString()} ${state.label.toLowerCase()} record(s) · ${dirty.size} unsaved animation edit(s)`;
  }

  async function save() {
    showError();
    if (!state || !dirty.size) return;
    const edits = [...dirty].sort((a, b) => a - b).map(id => {
      const row = state.rows.find(item => item.id === id);
      return {id: row.id, animation1: row.animation1, animation2: row.animation2};
    });
    state = await api('/api/ffx-commands/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        table: state.table,
        headerMd5: state.headerMd5,
        baselineSha256: state.baselineSha256,
        edits,
      }),
    });
    dirty.clear();
    render();
    await Promise.all([refreshOverview(), refreshMap(), searchArchive()]);
  }

  $('ffx-command-table').addEventListener('change', () => refresh().catch(showError));
  $('ffx-command-filter').addEventListener('input', render);
  $('ffx-command-refresh').addEventListener('click', () => refresh().catch(showError));
  $('ffx-command-save').addEventListener('click', () => save().catch(showError));
  $('ffx-command-rows').addEventListener('input', event => inputChanged(event.target));

  const originalExtractIndex = extractIndex;
  extractIndex = async function patchedFfxCommandExtractIndex(index) {
    const entry = catalog?.entries?.[index];
    await originalExtractIndex(index);
    if (entry?.eflPath === state?.archivePath) await refresh();
  };

  refresh().catch(showError);
})();
