'use strict';

// Utilities

function $(sel, ctx) { return (ctx || document).querySelector(sel); }
function $$(sel, ctx) { return [...(ctx || document).querySelectorAll(sel)]; }

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Toast

function toast(msg, type = 'info', duration = 3000) {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  $('#toast-container').appendChild(el);
  setTimeout(() => {
    el.style.animation = 'toastOut 200ms ease forwards';
    setTimeout(() => el.remove(), 200);
  }, duration);
}
function toastWithUndo(msg, onUndo, duration = 5000) {
  const el = document.createElement('div');
  el.className = 'toast info undo-toast';
  el.innerHTML = `<span>${esc(msg)}</span><button class="toast-undo-btn">Undo</button>`;
  $('#toast-container').appendChild(el);
  let undone = false;
  el.querySelector('.toast-undo-btn').addEventListener('click', () => {
    undone = true; el.remove(); onUndo();
  });
  setTimeout(() => {
    if (!undone && el.parentNode) {
      el.style.animation = 'toastOut 200ms ease forwards';
      setTimeout(() => el.remove(), 200);
    }
  }, duration);
}
// Text-input modal (replaces window.prompt — avoids ugly 127.0.0.1 popup)

let _inputResolve = null;

function inputPrompt(title, placeholder = '', defaultVal = '') {
  return new Promise(resolve => {
    _inputResolve = resolve;
    $('#input-modal-title').textContent = title;
    $('#input-modal-input').placeholder = placeholder;
    $('#input-modal-input').value = defaultVal;
    openModal('input-modal-backdrop');
    setTimeout(() => $('#input-modal-input').select(), 60);
  });
}

function _inputSubmit() {
  const val = $('#input-modal-input').value.trim();
  closeModal('input-modal-backdrop');
  if (_inputResolve) { _inputResolve(val || null); _inputResolve = null; }
}

function _inputCancel() {
  closeModal('input-modal-backdrop');
  if (_inputResolve) { _inputResolve(null); _inputResolve = null; }
}

$('#input-modal-ok').addEventListener('click', _inputSubmit);
$('#input-modal-cancel').addEventListener('click', _inputCancel);
$('#input-modal-close').addEventListener('click', _inputCancel);
$('#input-modal-input').addEventListener('keydown', e => {
  if (e.key === 'Enter')  _inputSubmit();
  if (e.key === 'Escape') _inputCancel();
});

// Confirm dialog

let _confirmResolve = null;

function confirm(title, message, confirmLabel = 'Confirm') {
  return new Promise(resolve => {
    _confirmResolve = resolve;
    $('#confirm-title').textContent = title;
    $('#confirm-message').textContent = message;
    $('#confirm-ok').textContent = confirmLabel;
    openModal('confirm-backdrop');
  });
}

$('#confirm-ok').addEventListener('click', () => {
  closeModal('confirm-backdrop');
  if (_confirmResolve) { _confirmResolve(true); _confirmResolve = null; }
});

$('#confirm-cancel').addEventListener('click', () => {
  closeModal('confirm-backdrop');
  if (_confirmResolve) { _confirmResolve(false); _confirmResolve = null; }
});

// Modal helpers

function openModal(id) { $('#' + id).classList.add('open'); }
function closeModal(id) { $('#' + id).classList.remove('open'); }

// Close on backdrop click
$$('.modal-backdrop').forEach(bd => {
  bd.addEventListener('click', e => {
    if (e.target === bd) bd.classList.remove('open');
  });
});

// Navigation

function navigate(page) {
  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + page));
  loadPage(page);
}

$$('.nav-item').forEach(btn => btn.addEventListener('click', () => navigate(btn.dataset.page)));

function loadPage(page) {
  if      (page === 'apps')     renderApps();
  else if (page === 'profiles') renderProfiles();
  else if (page === 'settings') renderSettings();
  else if (page === 'log') {
    if (_logTab === 'history') renderHistory();
    else renderLog();
  }
}

// API wrapper — waits for pywebview to be ready

let _apiReady = false;

function callApi(method, ...args) {
  return new Promise((resolve, reject) => {
    function attempt() {
      if (window.pywebview && window.pywebview.api) {
        window.pywebview.api[method](...args).then(resolve).catch(reject);
      } else {
        setTimeout(attempt, 80);
      }
    }
    attempt();
  });
}

// Status push (called by runner.py via evaluate_js)

window.__ignitionStatusUpdate = function(status, newLogEntries) {
  const dot  = $('#status-dot');
  const text = $('#status-text');
  if (status.iracing_running) {
    dot.classList.add('online');
    const labels = { race: 'Racing 🏁', service: 'Service Online' };
    text.textContent = 'iRacing · ' + (labels[status.session_type] || 'Online');
  } else {
    dot.classList.remove('online');
    text.textContent = 'iRacing · Offline';
  }
  // Pause button state
  const pb = $('#pause-btn');
  if (pb) {
    pb.classList.toggle('paused', !!status.paused);
    pb.querySelector('.pause-label').textContent = status.paused ? 'Resume' : 'Pause';
  }
  // Apps badge
  const badge = $('#apps-count-badge');
  if (badge) {
    if (status.managed_count > 0) {
      badge.textContent = status.managed_count;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  }
  // Log entries
  if (newLogEntries && newLogEntries.length > 0) appendLogEntries(newLogEntries);
};

// Activity log buffer

const _logEntries = [];
const _LOG_META = {
  launch:      { sym: '▶', cls: 'log-launch'      },
  stop:        { sym: '◼', cls: 'log-stop'         },
  skipped:     { sym: '⊘', cls: 'log-skip'         },
  error:       { sym: '✖', cls: 'log-error'        },
  iracing_start: { sym: '●', cls: 'log-iracing-on' },
  iracing_stop:  { sym: '●', cls: 'log-iracing-off'},
  paused:      { sym: '⏸', cls: 'log-paused'       },
  resumed:     { sym: '▶', cls: 'log-resumed'      },
};

function appendLogEntries(entries) {
  entries.forEach(e => _logEntries.push(e));
  // badge
  const badge = $('#log-count-badge');
  if (badge) {
    badge.textContent = _logEntries.length;
    badge.style.display = _logEntries.length ? '' : 'none';
  }
  // update live if log page is open
  const logPage = $('#page-log');
  if (logPage && logPage.classList.contains('active')) renderLog();
}

function renderLog() {
  const list = $('#log-list');
  if (!list) return;
  if (!_logEntries.length) {
    list.innerHTML = '<div class="log-empty">No events yet. Start iRacing to see activity.</div>';
    return;
  }
  // show newest first, max 200 rows
  list.innerHTML = [..._logEntries].reverse().slice(0, 200).map(e => {
    const meta = _LOG_META[e.type] || { sym: '·', cls: '' };
    const appSpan = e.app ? `<span class="log-app">${esc(e.app)}</span>` : '';
    return `<div class="log-row ${meta.cls}">` +
      `<span class="log-time">${esc(e.time)}</span>` +
      `<span class="log-sym">${meta.sym}</span>` +
      appSpan +
      `<span class="log-msg">${esc(e.msg)}</span>` +
      `</div>`;
  }).join('');
}

$('#clear-log-btn').addEventListener('click', async () => {
  if (_logTab === 'history') {
    await callApi('clear_session_history');
    renderHistory();
    toast('History cleared', 'info');
  } else {
    await callApi('clear_log');
    _logEntries.length = 0;
    const badge = $('#log-count-badge');
    if (badge) badge.style.display = 'none';
    renderLog();
    toast('Log cleared', 'info');
  }
});

let _logTab = 'events';

$$('[data-log-tab]').forEach(btn => {
  btn.addEventListener('click', () => {
    _logTab = btn.dataset.logTab;
    $$('[data-log-tab]').forEach(b => b.classList.toggle('active', b.dataset.logTab === _logTab));
    const evPan   = $('#log-events-panel');
    const histPan = $('#log-history-panel');
    if (evPan)   evPan.style.display   = _logTab === 'events'  ? '' : 'none';
    if (histPan) histPan.style.display = _logTab === 'history' ? '' : 'none';
    if (_logTab === 'events') renderLog(); else renderHistory();
  });
});

$('#clear-history-btn').addEventListener('click', async () => {
  await callApi('clear_session_history');
  renderHistory();
  toast('History cleared', 'info');
});

async function renderHistory() {
  const list = $('#session-list');
  if (!list) return;
  let sessions;
  try { sessions = await callApi('get_session_history'); } catch(e) { return; }
  if (!sessions || !sessions.length) {
    list.innerHTML = '<div class="log-empty">No sessions recorded yet. They appear here after iRacing closes.</div>';
    return;
  }
  list.innerHTML = sessions.map(s => {
    const dur  = _fmtDuration(s.duration_seconds);
    const date = _fmtDate(s.started_at);
    const chips = (s.apps_launched || []).map(a =>
      `<span class="session-app-chip">${esc(a)}</span>`).join('');
    return `<div class="session-card">
      <div class="session-header">
        <span class="session-date">${esc(date)}</span>
        <span class="session-duration">⏱ ${esc(dur)}</span>
        <span class="session-profile">${esc(s.profile_name || '?')}</span>
      </div>
      ${chips
        ? `<div class="session-apps">${chips}</div>`
        : '<div style="color:var(--text-muted);font-size:12px">No apps launched</div>'}
    </div>`;
  }).join('');
}

function _fmtDuration(secs) {
  if (!secs || secs < 60) return `${Math.round(secs || 0)}s`;
  const m = Math.floor(secs / 60), s = Math.round(secs % 60);
  if (m < 60) return `${m}m ${s}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function _fmtDate(iso) {
  if (!iso) return '?';
  try {
    return new Date(iso).toLocaleString(undefined,
      { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch(e) { return iso; }
}

// APPS PAGE
// View mode (card / compact)
let _appsView = (() => {
  try { return localStorage.getItem('ig-apps-view') || 'card'; } catch(_) { return 'card'; }
})();

function _applyAppsView() {
  const list = $('#apps-list');
  if (!list) return;
  list.classList.toggle('compact', _appsView === 'compact');
  $$('.view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === _appsView));
}

$$('.view-btn').forEach(btn => btn.addEventListener('click', () => {
  _appsView = btn.dataset.view;
  try { localStorage.setItem('ig-apps-view', _appsView); } catch(_) {}
  _applyAppsView();
}));
function renderApps() {
  callApi('get_apps').then(apps => {
    const list  = $('#apps-list');
    const empty = $('#apps-empty');
    if (!apps || apps.length === 0) {
      list.style.display = 'none';
      empty.style.display = '';
      return;
    }
    list.style.display = '';
    empty.style.display = 'none';
    list.innerHTML = apps.map(a => appCard(a)).join('');
    bindAppCardActions();
    _applyAppsView();
    loadAppIcons();
    setupDragReorder();
  }).catch(() => toast('Failed to load apps', 'error'));
}

// Deterministic accent color per app name initial
const _cardColors = ['#3D6EF5','#9F4EF5','#E05353','#F5A623','#2BD97E','#0099CC','#E8689A','#26B8B8'];
function _cardColor(name) {
  return _cardColors[(name || '?').toUpperCase().charCodeAt(0) % _cardColors.length];
}

function appCard(a) {
  const initial = (a.name || '?')[0].toUpperCase();
  const color   = _cardColor(a.name);
  const badges  = [];
  if (a.start_delay_seconds > 0)  badges.push(`<span class="app-badge">${a.start_delay_seconds}s delay</span>`);
  if (a.start_minimized)          badges.push('<span class="app-badge">Minimized</span>');
  if (a.start_if_already_running) badges.push('<span class="app-badge">Allow duplicate</span>');
  if (!a.kill_on_iracing_exit)    badges.push('<span class="app-badge keep">Keeps running</span>');
  if (a.enabled === false)        badges.push('<span class="app-badge" style="color:var(--text-muted)">Disabled</span>');
  const badgeHtml = badges.length ? `<div class="app-card-badges">${badges.join('')}</div>` : '';
  const disabledClass = a.enabled === false ? ' disabled' : '';
  const toggleTitle = a.enabled !== false ? 'Disable app' : 'Enable app';
  const toggleIcon = a.enabled !== false
    ? `<svg viewBox="0 0 16 16" fill="none" width="14" height="14"><path d="M3 8l4 4 6-7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><rect x="1.5" y="1.5" width="13" height="13" rx="2" stroke="currentColor" stroke-width="1.4"/></svg>`
    : `<svg viewBox="0 0 16 16" fill="none" width="14" height="14"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.4"/><path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`;
  return `
    <div class="app-card${disabledClass}" data-id="${esc(a.app_id)}" data-exe="${esc(a.executable_path)}" draggable="true">
      <div class="drag-handle" title="Drag to reorder">
        <svg viewBox="0 0 16 16" fill="none" width="12" height="12"><path d="M3 5h10M3 8h10M3 11h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </div>
      <div class="app-card-icon">
        <svg class="app-card-placeholder" viewBox="0 0 20 20" fill="none" width="18" height="18">
          <rect x="2" y="4" width="16" height="13" rx="2" stroke="currentColor" stroke-width="1.4"/>
          <path d="M2 8h16" stroke="currentColor" stroke-width="1.2"/>
          <circle cx="5" cy="6" r=".9" fill="currentColor"/>
          <circle cx="8" cy="6" r=".9" fill="currentColor"/>
        </svg>
        <img class="app-card-img" src="" alt="" />
      </div>
      <div class="app-card-body">
        <div class="app-card-name">${esc(a.name)}</div>
        <div class="app-card-path" title="${esc(a.executable_path)}">${esc(a.executable_path)}</div>
        ${badgeHtml}
      </div>
      <div class="app-card-actions">
        <button class="icon-btn" title="${esc(toggleTitle)}" data-action="toggle">${toggleIcon}</button>
        <button class="icon-btn" title="Test launch" data-action="test">
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><path d="M4 2l10 6-10 6V2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>
        </button>
        <button class="icon-btn" title="Edit" data-action="edit">
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
            <path d="M11 2l3 3L5 14H2v-3L11 2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
          </svg>
        </button>
        <button class="icon-btn danger" title="Delete" data-action="delete">
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
            <path d="M3 4h10M6 4V2.5h4V4M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4H5z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>`;
}

function bindAppCardActions() {
  $$('#apps-list .app-card').forEach(card => {
    const id = card.dataset.id;
    card.querySelector('[data-action=toggle]').addEventListener('click', async () => {
      const res = await callApi('toggle_app_enabled', id);
      if (res && res.ok) {
        toast(res.enabled ? 'App enabled' : 'App disabled', 'info');
        renderApps();
      } else toast('Failed to toggle app', 'error');
    });
    card.querySelector('[data-action=test]').addEventListener('click', async () => {
      const res = await callApi('test_launch_app', id);
      if (res && res.ok) toast('Test launch successful', 'success');
      else toast((res && res.error) || 'Launch failed', 'error');
    });
    card.querySelector('[data-action=edit]').addEventListener('click', () => openAppModal(id));
    card.querySelector('[data-action=delete]').addEventListener('click', () => deleteApp(id));
  });
}

async function deleteApp(id) {
  const apps = await callApi('get_apps').catch(() => null);
  const idx  = apps ? apps.findIndex(a => a.app_id === id) : -1;
  const snap = idx >= 0 ? JSON.stringify(apps[idx]) : null;
  const res  = await callApi('remove_app', id);
  if (!res || !res.ok) { toast('Failed to remove app', 'error'); return; }
  renderApps();
  if (snap !== null) {
    toastWithUndo('App removed', async () => {
      await callApi('undo_remove_app', snap, idx);
      renderApps();
    });
  }
}

// Load real exe icons
function loadAppIcons() {
  $$('#apps-list .app-card[data-exe]').forEach(card => {
    const exe = card.dataset.exe;
    if (!exe) return;
    const img = card.querySelector('.app-card-img');
    if (!img) return;
    callApi('get_app_icon', exe).then(dataUrl => {
      if (dataUrl) {
        img.src = dataUrl;
        img.onload = () => {
          img.classList.add('loaded');
          const ph = card.querySelector('.app-card-placeholder');
          if (ph) ph.style.display = 'none';
        };
      }
    }).catch(() => {});
  });
}

// Drag-to-reorder
let _dragSrcId = null;

function setupDragReorder() {
  const cards = $$('#apps-list .app-card');
  cards.forEach(card => {
    card.addEventListener('dragstart', e => {
      _dragSrcId = card.dataset.id;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      $$('#apps-list .app-card').forEach(c => c.classList.remove('drag-over'));
    });
    card.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (card.dataset.id !== _dragSrcId) {
        $$('#apps-list .app-card').forEach(c => c.classList.remove('drag-over'));
        card.classList.add('drag-over');
      }
    });
    card.addEventListener('drop', async e => {
      e.preventDefault();
      card.classList.remove('drag-over');
      const targetId = card.dataset.id;
      if (!_dragSrcId || _dragSrcId === targetId) return;
      // build new order: swap src before target
      const allCards = $$('#apps-list .app-card');
      const ids = allCards.map(c => c.dataset.id);
      const fromIdx = ids.indexOf(_dragSrcId);
      const toIdx   = ids.indexOf(targetId);
      ids.splice(fromIdx, 1);
      ids.splice(toIdx, 0, _dragSrcId);
      const res = await callApi('reorder_apps', JSON.stringify(ids));
      if (res && res.ok) renderApps();
      else toast('Failed to reorder apps', 'error');
    });
  });
}

// App modal
$('#add-app-btn').addEventListener('click', () => openAppModal(null));
$('#app-modal-close').addEventListener('click', () => closeModal('app-modal-backdrop'));
$('#app-modal-cancel').addEventListener('click', () => closeModal('app-modal-backdrop'));

$('#fm-browse-exe').addEventListener('click', () => {
  callApi('browse_exe').then(p => { if (p) $('#fm-exe').value = p; });
});

$('#fm-browse-wd').addEventListener('click', () => {
  callApi('browse_directory').then(p => { if (p) $('#fm-wd').value = p; });
});

$('#fm-wait-for').addEventListener('input', function() {
  const g = $('#fm-wait-timeout-group');
  if (g) g.style.display = this.value.trim() ? '' : 'none';
});

function openAppModal(appId) {
  if (!appId) {
    // New app — reset form
    $('#app-modal-title').textContent = 'Add App';
    $('#fm-app-id').value = '';
    $('#fm-name').value = '';
    $('#fm-exe').value  = '';
    $('#fm-args').value = '';
    $('#fm-wd').value   = '';
    $('#fm-delay').value = '0';
    $('#fm-start-min').checked    = false;
    $('#fm-allow-running').checked = false;
    $('#fm-kill-on-exit').checked  = true;
    $('#fm-kill-tree').checked     = true;
    $('#fm-wait-for').value = '';
    $('#fm-wait-timeout').value = '30';
    const _wtg = $('#fm-wait-timeout-group');
    if (_wtg) _wtg.style.display = 'none';
    openModal('app-modal-backdrop');
    return;
  }
  // Load existing app data
  callApi('get_apps').then(apps => {
    const a = apps.find(x => x.app_id === appId);
    if (!a) return;
    $('#app-modal-title').textContent = 'Edit App';
    $('#fm-app-id').value  = a.app_id;
    $('#fm-name').value    = a.name;
    $('#fm-exe').value     = a.executable_path;
    $('#fm-args').value    = a.arguments || '';
    $('#fm-wd').value      = a.working_directory || '';
    $('#fm-delay').value   = a.start_delay_seconds || 0;
    $('#fm-start-min').checked     = !!a.start_minimized;
    $('#fm-allow-running').checked = !!a.start_if_already_running;
    $('#fm-kill-on-exit').checked  = a.kill_on_iracing_exit !== false;
    $('#fm-kill-tree').checked     = a.kill_process_tree !== false;
    $('#fm-wait-for').value = a.wait_for_process || '';
    $('#fm-wait-timeout').value   = a.wait_timeout_seconds || 30;
    const _wtg2 = $('#fm-wait-timeout-group');
    if (_wtg2) _wtg2.style.display = (a.wait_for_process || '').trim() ? '' : 'none';
    openModal('app-modal-backdrop');
  });
}

$('#app-modal-save').addEventListener('click', async () => {
  const name = $('#fm-name').value.trim();
  const exe  = $('#fm-exe').value.trim();
  if (!name || !exe) { toast('Name and executable are required', 'error'); return; }

  const appData = {
    app_id:               $('#fm-app-id').value || null,
    name,
    executable_path:      exe,
    arguments:            $('#fm-args').value.trim(),
    working_directory:    $('#fm-wd').value.trim(),
    start_delay_seconds:  parseFloat($('#fm-delay').value) || 0,
    start_minimized:      $('#fm-start-min').checked,
    start_if_already_running: $('#fm-allow-running').checked,
    kill_on_iracing_exit: $('#fm-kill-on-exit').checked,
    kill_process_tree:    $('#fm-kill-tree').checked,
    wait_for_process:     $('#fm-wait-for').value.trim(),
    wait_timeout_seconds: parseFloat($('#fm-wait-timeout').value) || 30,
  };

  const json = JSON.stringify(appData);
  let res;
  if (appData.app_id) {
    res = await callApi('edit_app', json);
  } else {
    res = await callApi('add_app', json);
  }

  if (res && res.ok) {
    closeModal('app-modal-backdrop');
    toast(appData.app_id ? 'App updated' : 'App added', 'success');
    renderApps();
  } else {
    toast((res && res.error) || 'Failed to save app', 'error');
  }
});
// Template picker
$('#template-picker-btn').addEventListener('click', openTemplateModal);
$('#template-modal-close').addEventListener('click',  () => closeModal('template-modal-backdrop'));
$('#template-modal-cancel').addEventListener('click', () => closeModal('template-modal-backdrop'));

let _templateApps = [];

async function openTemplateModal() {
  const list  = $('#template-list');
  const empty = $('#template-empty');
  if (list)  list.innerHTML = '<div class="log-empty" style="padding:16px 0">Scanning...</div>';
  if (empty) empty.style.display = 'none';
  openModal('template-modal-backdrop');
  try { _templateApps = await callApi('get_common_apps'); }
  catch(e) { _templateApps = []; }
  if (!list) return;
  if (!_templateApps || !_templateApps.length) {
    list.innerHTML = '';
    if (empty) empty.style.display = '';
    return;
  }
  list.innerHTML = _templateApps.map((a, i) => {
    const color   = _cardColor(a.name);
    const initial = (a.name || '?')[0].toUpperCase();
    return `<div class="template-item" data-idx="${i}">
      <div class="template-icon">
        <svg viewBox="0 0 20 20" fill="none" width="16" height="16" style="color:var(--text-muted)">
          <rect x="2" y="4" width="16" height="13" rx="2" stroke="currentColor" stroke-width="1.4"/>
          <path d="M2 8h16" stroke="currentColor" stroke-width="1.2"/>
          <circle cx="5" cy="6" r=".9" fill="currentColor"/>
          <circle cx="8" cy="6" r=".9" fill="currentColor"/>
        </svg>
      </div>
      <div style="flex:1;min-width:0">
        <div class="template-name">${esc(a.name)}</div>
        <div class="template-path">${esc(a.executable_path)}</div>
      </div>
      <input type="checkbox" class="checkbox template-check" />
    </div>`;
  }).join('');
  $$('#template-list .template-item').forEach(item => {
    item.addEventListener('click', e => {
      if (e.target.type === 'checkbox') return;
      const cb = item.querySelector('.template-check');
      cb.checked = !cb.checked;
      item.classList.toggle('selected', cb.checked);
    });
    item.querySelector('.template-check').addEventListener('change', function() {
      item.classList.toggle('selected', this.checked);
    });
  });
}

$('#template-modal-add').addEventListener('click', async () => {
  const selected = [];
  $$('#template-list .template-item').forEach(item => {
    if (item.querySelector('.template-check').checked)
      selected.push(_templateApps[parseInt(item.dataset.idx)]);
  });
  if (!selected.length) { toast('Select at least one app', 'error'); return; }
  let added = 0;
  for (const a of selected) {
    const res = await callApi('add_app', JSON.stringify({ name: a.name, executable_path: a.executable_path }));
    if (res && res.ok) added++;
  }
  closeModal('template-modal-backdrop');
  if (added > 0) { toast(`Added ${added} app${added > 1 ? 's' : ''}`, 'success'); renderApps(); }
  else toast('Failed to add apps', 'error');
});
// PROFILES PAGE

function renderProfiles() {
  callApi('get_profiles').then(profiles => {
    const list   = $('#profiles-list');
    const empty  = $('#profiles-empty');
    if (!profiles || profiles.length === 0) {
      list.style.display = 'none';
      empty.style.display = '';
      return;
    }
    list.style.display = '';
    empty.style.display = 'none';
    list.innerHTML = profiles.map(p => profileCard(p)).join('');
    bindProfileCardActions();
  }).catch(() => toast('Failed to load profiles', 'error'));
}

const _PROFILE_COLORS = ['#E53935','#F57C00','#FBC02D','#388E3C','#0288D1','#7B1FA2','#C2185B','#546E7A'];

function profileCard(p) {
  const activeBadge = p.is_active
    ? '<span class="badge badge-active">Active</span>'
    : '';
  const tags = p.trigger_process_names && p.trigger_process_names.length
    ? p.trigger_process_names.map(t => `<span class="trigger-tag">${esc(t)}</span>`).join('')
    : '<span class="trigger-tag-empty">No triggers set</span>';
  const activateBtn = !p.is_active
    ? `<button class="icon-btn" title="Set active" data-action="activate">
        <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
          <path d="M3 8l4 4 6-7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>` : '';
  const appCount = p.app_count != null ? p.app_count : '';
  const expandBtn = `<button class="icon-btn profile-expand-btn" title="Show apps" data-action="expand">
        <svg viewBox="0 0 16 16" fill="none" width="12" height="12"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        ${appCount !== '' ? `<span style="font-size:11px">${appCount} app${appCount === 1 ? '' : 's'}</span>` : 'Apps'}
      </button>`;
  const colorPip = p.color
    ? `<span class="profile-color-pip" style="background:${esc(p.color)};margin-right:2px"></span>`
    : '';
  const colorDots = [..._PROFILE_COLORS, ''].map(c =>
    `<span class="color-dot${p.color === c ? ' selected' : ''}" style="background:${c || 'var(--border-normal)'}" data-color="${c}" title="${c || 'None'}"></span>`
  ).join('');
  return `
    <div class="profile-card${p.is_active ? ' active' : ''}" data-id="${esc(p.profile_id)}">
      <div class="profile-card-header">
        <div class="profile-card-name">${colorPip}${esc(p.name)}</div>
        ${activeBadge}
        <div class="profile-card-actions">
          ${activateBtn}
          ${expandBtn}
          <button class="icon-btn" title="Color" data-action="color">
            <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
              <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.4"/>
              ${p.color ? `<circle cx="8" cy="8" r="3" fill="${esc(p.color)}"/>` : '<circle cx="8" cy="8" r="3" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 1.5"/>'}
            </svg>
          </button>
          <button class="icon-btn" title="Edit trigger processes" data-action="triggers">
            <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
              <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.4"/>
              <path d="M8 5v3l2 1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
          </button>
          <button class="icon-btn" title="Rename" data-action="rename">
            <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
              <path d="M11 2l3 3L5 14H2v-3L11 2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
            </svg>
          </button>
          <button class="icon-btn danger" title="Delete" data-action="delete">
            <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
              <path d="M3 4h10M6 4V2.5h4V4M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4H5z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
      <div class="profile-card-triggers">${tags}</div>
      <div class="profile-color-row" data-color-panel="${esc(p.profile_id)}" style="display:none">${colorDots}</div>
      <div class="profile-apps-expand" style="display:none" data-expand-id="${esc(p.profile_id)}"></div>
    </div>`;
}

function bindProfileCardActions() {
  $$('#profiles-list .profile-card').forEach(card => {
    const id = card.dataset.id;
    const actBtn   = card.querySelector('[data-action=activate]');
    const expBtn   = card.querySelector('[data-action=expand]');
    const colorBtn = card.querySelector('[data-action=color]');
    const trigBtn  = card.querySelector('[data-action=triggers]');
    const renBtn   = card.querySelector('[data-action=rename]');
    const delBtn   = card.querySelector('[data-action=delete]');
    if (actBtn)   actBtn.addEventListener('click',   () => activateProfile(id));
    if (expBtn)   expBtn.addEventListener('click',   () => toggleProfileAppsExpand(id, card));
    if (colorBtn) colorBtn.addEventListener('click', () => {
      const panel = card.querySelector(`[data-color-panel="${id}"]`);
      if (panel) panel.style.display = panel.style.display === 'none' ? '' : 'none';
    });
    if (trigBtn) trigBtn.addEventListener('click', () => openTriggersModal(id));
    if (renBtn)  renBtn.addEventListener('click',  () => renameProfile(id));
    if (delBtn)  delBtn.addEventListener('click',  () => deleteProfile(id));
    card.querySelectorAll('.color-dot').forEach(dot => {
      dot.addEventListener('click', async () => {
        const res = await callApi('set_profile_color', id, dot.dataset.color || '');
        if (res && res.ok) renderProfiles();
        else toast('Failed to set color', 'error');
      });
    });
  });
}

async function toggleProfileAppsExpand(profileId, card) {
  const panel = card.querySelector(`[data-expand-id="${profileId}"]`);
  if (!panel) return;
  const isOpen = panel.style.display !== 'none';
  if (isOpen) { panel.style.display = 'none'; return; }
  panel.style.display = '';
  panel.innerHTML = '<div class="expand-empty">Loading…</div>';
  try {
    const apps = await callApi('get_profile_apps', profileId);
    if (!apps || apps.length === 0) {
      panel.innerHTML = '<div class="expand-empty">No apps in this profile.</div>';
      return;
    }
    panel.innerHTML = apps.map(a => {
      const initial = (a.name || '?')[0].toUpperCase();
      const color   = _cardColor(a.name);
      const disabledTag = a.enabled === false ? ' <span style="color:var(--text-muted);font-size:10px">(disabled)</span>' : '';
      return `<div class="app-mini-row">
      <div class="app-mini-icon">
        <svg viewBox="0 0 16 16" fill="none" width="12" height="12" style="color:var(--text-muted)">
          <rect x="1" y="3" width="14" height="10" rx="1.5" stroke="currentColor" stroke-width="1.3"/>
          <path d="M1 6.5h14" stroke="currentColor" stroke-width="1"/>
        </svg>
      </div>
        <span class="app-mini-name">${esc(a.name)}${disabledTag}</span>
        <span class="app-mini-path">${esc(a.executable_path)}</span>
      </div>`;
    }).join('');
  } catch(e) {
    panel.innerHTML = '<div class="expand-empty">Failed to load apps.</div>';
  }
}

async function activateProfile(id) {
  const res = await callApi('set_active_profile', id);
  if (res && res.ok) { toast('Active profile changed', 'success'); renderProfiles(); }
  else toast('Failed to change profile', 'error');
}

async function renameProfile(id) {
  const profiles = await callApi('get_profiles');
  const p = profiles.find(x => x.profile_id === id);
  if (!p) return;
  const name = await inputPrompt('Rename Profile', p.name, p.name);
  if (!name || name.trim() === '') return;
  const res = await callApi('rename_profile', id, name.trim());
  if (res && res.ok) { toast('Profile renamed', 'success'); renderProfiles(); }
  else toast('Failed to rename', 'error');
}

async function deleteProfile(id) {
  const ok = await confirm('Delete profile', 'This will permanently delete the profile and all its apps. Continue?', 'Delete');
  if (!ok) return;
  const res = await callApi('remove_profile', id);
  if (res && res.ok) { toast('Profile deleted', 'success'); renderProfiles(); }
  else toast('Failed to delete profile', 'error');
}

// Add profile
$('#add-profile-btn').addEventListener('click', async () => {
  const name = await inputPrompt('New Profile', 'Profile name…');
  if (!name || !name.trim()) return;
  const res = await callApi('add_profile', name.trim());
  if (res && res.ok) { toast('Profile created', 'success'); renderProfiles(); }
  else toast((res && res.error) || 'Failed to create profile', 'error');
});

// Triggers modal
$('#triggers-modal-close').addEventListener('click',  () => closeModal('triggers-modal-backdrop'));
$('#triggers-modal-cancel').addEventListener('click', () => closeModal('triggers-modal-backdrop'));

async function openTriggersModal(profileId) {
  const profiles = await callApi('get_profiles');
  const p = profiles.find(x => x.profile_id === profileId);
  if (!p) return;
  $('#triggers-profile-id').value = profileId;
  $('#triggers-input').value = (p.trigger_process_names || []).join(', ');
  openModal('triggers-modal-backdrop');
}

$('#triggers-modal-save').addEventListener('click', async () => {
  const id  = $('#triggers-profile-id').value;
  const csv = $('#triggers-input').value.trim();
  const res = await callApi('set_profile_triggers', id, csv);
  if (res && res.ok) {
    closeModal('triggers-modal-backdrop');
    toast('Triggers updated', 'success');
    renderProfiles();
  } else toast('Failed to update triggers', 'error');
});

// AUTOSTART PAGE

$('#race-btn').addEventListener('click', async () => {
  const res = await callApi('launch_iracing');
  if (res && res.ok) toast('Launching iRacing…', 'info');
  else toast((res && res.error) || 'Could not launch iRacing', 'error');
});

$('#pause-btn').addEventListener('click', async () => {
  const paused = $('#pause-btn').classList.contains('paused');
  const res = await callApi('set_monitoring_paused', !paused);
  if (res && res.ok) {
    toast(!paused ? 'Monitoring paused' : 'Monitoring resumed', 'info');
  } else toast('Failed to update monitoring state', 'error');
});

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  $$('.theme-btn').forEach(b => b.classList.toggle('active', b.dataset.theme === theme));
  try { localStorage.setItem('ig-theme', theme); } catch(_) {}
}

$$('.theme-btn').forEach(btn => btn.addEventListener('click', () => applyTheme(btn.dataset.theme)));

function renderSettings() {
  Promise.all([
    callApi('get_settings'),
    callApi('get_autostart_enabled'),
    callApi('get_config_path'),
  ]).then(([s, autostart, cfgPath]) => {
    $('#poll-interval').value = s.poll_interval_seconds ?? 1;
    $('#minimize-tray').checked = !!s.minimize_to_tray;
    $('#iracing-path').value = s.iracing_exe_path || '';
    const mode = s.trigger_mode || 'ui';
    const radio = document.querySelector(`input[name="trigger-mode"][value="${mode}"]`);
    if (radio) radio.checked = true;
    $('#autostart-toggle').checked = !!autostart;
    $('#config-path-label').textContent = cfgPath || '';
  }).catch(() => toast('Failed to load settings', 'error'));
}

$('#autostart-toggle').addEventListener('change', async e => {
  const res = await callApi('set_autostart', e.target.checked);
  if (res && res.ok) toast(e.target.checked ? 'Autostart enabled' : 'Autostart disabled', 'info');
  else { toast('Failed to update autostart', 'error'); e.target.checked = !e.target.checked; }
});

$('#browse-iracing-btn').addEventListener('click', () => {
  callApi('browse_iracing_exe').then(p => { if (p) $('#iracing-path').value = p; });
});

$('#save-settings-btn').addEventListener('click', async () => {
  const mode = (document.querySelector('input[name="trigger-mode"]:checked') || {}).value || 'ui';
  const settings = {
    poll_interval_seconds: parseFloat($('#poll-interval').value) || 1,
    minimize_to_tray:      $('#minimize-tray').checked,
    iracing_exe_path:      $('#iracing-path').value.trim(),
    trigger_mode:          mode,
  };
  const res = await callApi('save_settings', JSON.stringify(settings));
  if (res && res.ok) toast('Settings saved', 'success');
  else toast((res && res.error) || 'Failed to save settings', 'error');
});


$('#open-config-btn').addEventListener('click', () => callApi('open_config_folder'));
$('#open-log-btn').addEventListener('click',    () => callApi('open_log_folder'));

$('#export-config-btn').addEventListener('click', async () => {
  const path = await callApi('save_file_dialog', 'ignition-config.json');
  if (!path) return;
  const res = await callApi('export_config', path);
  if (res && res.ok) toast('Config exported', 'success');
  else toast((res && res.error) || 'Export failed', 'error');
});

$('#import-config-btn').addEventListener('click', async () => {
  const path = await callApi('open_file_dialog');
  if (!path) return;
  const ok = await confirm('Import config', 'This will replace your current configuration. Continue?', 'Import');
  if (!ok) return;
  const res = await callApi('import_config', path);
  if (res && res.ok) { toast('Config imported', 'success'); loadPage('settings'); }
  else toast((res && res.error) || 'Import failed', 'error');
});

// QUIT

$('#quit-btn').addEventListener('click', async () => {
  const ok = await confirm('Quit iGnition', 'iGnition will close completely. Any managed apps will remain running.', 'Quit');
  if (ok) callApi('quit_app');
});

// Boot

function init() {
  _apiReady = true;
  // Restore saved theme
  try {
    const saved = localStorage.getItem('ig-theme');
    if (saved) applyTheme(saved);
  } catch(_) {}
  navigate('apps');
}

// pywebview fires this event when the JS bridge is ready
window.addEventListener('pywebviewready', init);

// Fallback: if the event already fired or never fires (dev mode)
if (document.readyState === 'complete') {
  setTimeout(() => { if (!_apiReady) init(); }, 500);
} else {
  window.addEventListener('load', () => setTimeout(() => { if (!_apiReady) init(); }, 500));
}
