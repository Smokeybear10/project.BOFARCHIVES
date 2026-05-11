/* BOF Terminal — live filterable dashboard with cross-filtering, search,
 * presets, paginated records table, detail modal, URL state sync, CSV export.
 * No build step.
 */

const CSV_URL = 'output/all_structured_records.csv';
const BUDGET_CSV_URL = 'output/budget_master_ledger.csv';
const APPROPRIATIONS_CSV_URL = 'output/bof_appropriations.csv';
const ALLOTMENTS_CSV_URL = 'output/bof_allotments.csv';

// Null-safe Plotly.react: skip rendering if the target div was removed
// from the DOM (so cutting chart panels in index.html doesn't blow up
// the rest of the dashboard). Returns a resolved Promise to keep
// chained `.then(() => attachClick(...))` calls happy.
(function hardenPlotly() {
  if (typeof Plotly === 'undefined' || Plotly.__hardened) return;
  Plotly.__hardened = true;
  const _react = Plotly.react.bind(Plotly);
  Plotly.react = function (target, ...rest) {
    const el = typeof target === 'string' ? document.getElementById(target) : target;
    if (!el) return Promise.resolve();
    return _react(el, ...rest);
  };
})();

const THEMES = {
  slate: {
    bg: '#131316', panel: '#131316', border: '#232327',
    text: '#ECEDEE', textMid: '#9698A1', textSoft: '#5C5E66',
    accent: '#8DA2FB', amber: '#E8B86A', red: '#E5736D',
    cyan: '#7BB7E8', magenta: '#B58AD9',
    cluster: {
      'Artillery':                      '#7BB7E8',
      'Explosives':                     '#B58AD9',
      'Small Arms':                     '#7DD3A1',
      'Armor and Protection':           '#E8B86A',
      'Fortification and Engineering':  '#94D5BB',
      'Communications and Observation': '#A5B4FC',
      'Logistics and Support':          '#D6A0A0',
      'Other/Unclassified':             '#8E939C',
    },
    fontFamily: "'Inter', -apple-system, system-ui, sans-serif",
  },
  paper: {
    bg: '#FFFFFF', panel: '#FFFFFF', border: '#E1E3E6',
    text: '#1A1F36', textMid: '#5A6075', textSoft: '#8C92A4',
    accent: '#635BFF', amber: '#B45309', red: '#B91C1C',
    cyan: '#0570DE', magenta: '#9333EA',
    cluster: {
      'Artillery':                      '#0570DE',
      'Explosives':                     '#9333EA',
      'Small Arms':                     '#0E7C66',
      'Armor and Protection':           '#B45309',
      'Fortification and Engineering':  '#15803D',
      'Communications and Observation': '#4F46E5',
      'Logistics and Support':          '#B91C1C',
      'Other/Unclassified':             '#697386',
    },
    fontFamily: "'Inter', -apple-system, system-ui, sans-serif",
  },
};

let CURRENT_THEME = 'paper';
let COLORS = THEMES.paper;
let STATUS_COLOR = makeStatusColor(COLORS);
let CLUSTER_COLOR = COLORS.cluster;
let PLOT_FONT = makePlotFont(COLORS);

function makeStatusColor(c) {
  return {
    Approved:      c.accent,
    Investigating: c.amber,
    Rejected:      c.red,
    Other:         c.textSoft,
  };
}

function makePlotFont(c) {
  return { family: c.fontFamily, size: 11, color: c.text };
}

function heatmapScale() {
  // Theme-aware sequential scale for cell density
  return [
    [0,    COLORS.panel],
    [0.06, COLORS.border],
    [0.25, COLORS.cyan],
    [0.55, COLORS.cyan],
    [0.80, COLORS.amber],
    [1,    COLORS.accent],
  ];
}

let PLOT_BASE_LAYOUT = makeBaseLayout();
let PLOT_AXIS = makeAxis();

function makeBaseLayout() {
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor:  'rgba(0,0,0,0)',
    font:          PLOT_FONT,
    margin: { l: 50, r: 16, t: 12, b: 40 },
    hoverlabel: {
      bgcolor: COLORS.bg,
      bordercolor: COLORS.border,
      font: { family: PLOT_FONT.family, size: 11, color: COLORS.text },
    },
  };
}

function makeAxis() {
  return {
    gridcolor: COLORS.border,
    linecolor: COLORS.border,
    zerolinecolor: COLORS.border,
    tickcolor: COLORS.border,
    tickfont: { color: COLORS.textMid, size: 10 },
  };
}

const PLOT_CONFIG = { displayModeBar: false, responsive: true };

// ── Theme switching ───────────────────────────────────────────────────
function setTheme(name) {
  // Falls back to 'paper' for any unknown theme (incl. retired terminal/broadsheet from localStorage)
  if (!THEMES[name]) name = 'paper';
  CURRENT_THEME = name;
  COLORS = THEMES[name];
  STATUS_COLOR = makeStatusColor(COLORS);
  CLUSTER_COLOR = COLORS.cluster;
  PLOT_FONT = makePlotFont(COLORS);
  PLOT_BASE_LAYOUT = makeBaseLayout();
  PLOT_AXIS = makeAxis();
  document.documentElement.className = `theme-${name}`;
  try { localStorage.setItem('bof-theme', name); } catch {}
  updateThemeButtons();
  if (ALL.length > 0) apply();
}

function updateThemeButtons() {
  document.querySelectorAll('.theme-switch button').forEach(b => {
    b.classList.toggle('active', b.dataset.theme === CURRENT_THEME);
  });
}

function wireThemes() {
  document.querySelectorAll('.theme-switch button').forEach(btn => {
    btn.addEventListener('click', () => setTheme(btn.dataset.theme));
  });
  const saved = (() => { try { return localStorage.getItem('bof-theme'); } catch { return null; } })();
  setTheme(saved || 'paper');
}

// ── State ─────────────────────────────────────────────────────────────
let VIEW = 'proposals';
let ALL = [];
let FILTERED = [];
let FILTERS = {
  yearMin: 1897,
  yearMax: 1908,
  cluster: '',
  status:  '',
  proposer: '',
  search:  '',
};
let SORT = { key: 'year', dir: 'asc' };
let PAGE = 1;
const PAGE_SIZE = 20;

let ALL_BUDGET = [];
let FILTERED_BUDGET = [];
let BUDGET_FILTERS = {
  yearMin: 1866,
  yearMax: 1920,
  branch:  '',
  units:   '2025',  // '2025' or 'nominal'
};
let BUDGET_SORT = { key: 'year', dir: 'asc' };
let BUDGET_PAGE = 1;
let BUDGET_RENDERED = false;

let ALL_APPROPRIATIONS = [];
let ALL_ALLOTMENTS = [];
let FILTERED_ALLOTMENTS = [];
let SPENDING_FILTERS = {
  yearMin: 1888,
  yearMax: 1920,
  revoked: '', // 'active', 'revoked', or '' for all
  search:  '',
};
let SPENDING_SORT = { key: 'year', dir: 'asc' };
let SPENDING_PAGE = 1;
let SPENDING_RENDERED = false;

// ── Bucketing ─────────────────────────────────────────────────────────
function statusBucket(s) {
  if (!s || typeof s !== 'string') return 'Other';
  const x = s.toLowerCase();
  if (x.includes('approv') || x.includes('adopt')) return 'Approved';
  if (x.includes('reject') || x.includes('not recommend')) return 'Rejected';
  if (x.includes('investigat') || x.includes('test') || x.includes('allotment')) return 'Investigating';
  return 'Other';
}

function proposerType(t) {
  if (!t || typeof t !== 'string') return 'unknown';
  const x = t.toLowerCase();
  if (x.includes('gov') || x.includes('army') || x.includes('navy') || x.includes('officer') || x.includes('ordnance')) return 'government';
  if (x.includes('private') || x.includes('individual') || x.includes('civil')) return 'private';
  return 'unknown';
}

// ── Load ──────────────────────────────────────────────────────────────
async function load() {
  const [propText, budgetText, approText, allotText] = await Promise.all([
    fetch(CSV_URL).then(r => r.text()),
    fetch(BUDGET_CSV_URL).then(r => r.text()),
    fetch(APPROPRIATIONS_CSV_URL).then(r => r.text()),
    fetch(ALLOTMENTS_CSV_URL).then(r => r.text()),
  ]);

  // Proposals
  const parsed = Papa.parse(propText, { header: true, skipEmptyLines: true });
  ALL = parsed.data
    .map((r, i) => ({
      id: i,
      year: parseInt(r.year, 10),
      cluster: (r.primary_cluster || 'Other/Unclassified').trim() || 'Other/Unclassified',
      status: statusBucket(r.status),
      statusRaw: r.status || '',
      proposer: (r['Proposed By'] || r.proposer_text || '').trim(),
      proposerType: proposerType(r.proposer_type),
      subject: (r.Subject || r.subject_text || '').trim(),
      action: (r.Action || r.action_text || '').trim(),
      reasoning: (r['Recommendation Reasoning'] || r.reasoning_text || '').trim(),
      report: r['BOF Annual Report #'] || '',
    }))
    .filter(r => Number.isFinite(r.year));

  // Budget
  const bparsed = Papa.parse(budgetText, { header: true, skipEmptyLines: true });
  ALL_BUDGET = bparsed.data
    .map((r, i) => ({
      id: i,
      year: parseInt(r.year, 10),
      branch: (r.branch || '').trim(),
      decade: (r.decade || '').trim(),
      nominal: parseFloat(r.appropriation_usd) || 0,
      adjusted: parseFloat(r.appropriation_2025_usd) || 0,
    }))
    .filter(r => Number.isFinite(r.year) && r.branch);

  // BOF appropriations (annual congressional give to the Board)
  const aparsed = Papa.parse(approText, { header: true, skipEmptyLines: true });
  ALL_APPROPRIATIONS = aparsed.data
    .map((r, i) => ({
      id: i,
      year: parseInt(r.Year, 10),
      amount: parseFloat(r.Amount_Numeric || r.Amount) || 0,
      remarks: (r.Remarks || '').trim(),
      requested: parseFloat(r['Estimate Originally Requested by BOF (Not from the same source, but from the prior year\'s annual report)']) || null,
      justification: (r['Justification for Estimate/Request'] || '').trim(),
      legislation: (r['Legislation Making Appropriations for the Board'] || '').trim(),
      permalink: (r['Permalink to Legislation/Act'] || '').trim(),
    }))
    .filter(r => Number.isFinite(r.year));

  // BOF allotments (individual research expenditures)
  const lparsed = Papa.parse(allotText, { header: true, skipEmptyLines: true });
  ALL_ALLOTMENTS = lparsed.data
    .map((r, i) => ({
      id: i,
      year: parseInt(parseFloat(r.Year), 10),
      description: (r['Project/Line Item Description'] || '').trim(),
      amount: parseFloat(r.Allotted_Numeric || r['Allotted ($)']) || 0,
      dateAllotted: (r['Date Allotted'] || '').trim(),
      revoked: /^y/i.test(r['Revoked Allotment?'] || ''),
      dateRevoked: (r['Date of Revocation'] || '').trim(),
      page: (r.Page || '').trim(),
      notes: (r.Notes || '').trim(),
    }))
    .filter(r => Number.isFinite(r.year) && r.description);

  // Populate cluster filter
  const clusters = [...new Set(ALL.map(r => r.cluster))].sort();
  const clusterSel = document.getElementById('f-cluster');
  for (const c of clusters) {
    const opt = document.createElement('option');
    opt.value = c; opt.textContent = c;
    clusterSel.appendChild(opt);
  }

  wireFilters();
  wirePresets();
  wireTable();
  wireModal();
  wireKeyboard();
  wireThemes();
  wireBudgetFilters();
  wireBudgetPresets();
  wireBudgetTable();
  wireTimelineFilters();
  wireSpendingFilters();
  wireSpendingTable();
  wireViewTabs();

  document.getElementById('rec-count').textContent = ALL.length.toLocaleString();
  document.getElementById('vt-prop-count').textContent = ALL.length.toLocaleString();
  document.getElementById('vt-budget-count').textContent = ALL_BUDGET.length.toLocaleString();

  // Derive year bounds from data so users can expand/contract freely.
  setupYearBounds();
  if (window.TIMELINE_GROUPS) {
    document.getElementById('vt-timeline-count').textContent = window.TIMELINE_GROUPS.length.toLocaleString();
  }
  document.getElementById('vt-spending-count').textContent = ALL_ALLOTMENTS.length.toLocaleString();
  computePresetCounts();
  stateFromHash();
  apply();
  // stateFromHash already calls setView('budget') if needed, which triggers applyBudget()
}

function wireFilters() {
  document.getElementById('f-year-min').addEventListener('change', e => { FILTERS.yearMin = parseInt(e.target.value, 10); PAGE = 1; apply(); });
  document.getElementById('f-year-max').addEventListener('change', e => { FILTERS.yearMax = parseInt(e.target.value, 10); PAGE = 1; apply(); });
  document.getElementById('f-cluster').addEventListener('change', e => { FILTERS.cluster = e.target.value; PAGE = 1; apply(); });
  document.getElementById('f-status').addEventListener('change', e => { FILTERS.status = e.target.value; PAGE = 1; apply(); });
  document.getElementById('f-proposer').addEventListener('change', e => { FILTERS.proposer = e.target.value; PAGE = 1; apply(); });
  document.getElementById('btn-clear').addEventListener('click', resetFilters);

  // Search (debounced)
  const searchInput = document.getElementById('f-search');
  const searchWrap = document.getElementById('search-wrap');
  let searchTimer;
  searchInput.addEventListener('input', e => {
    clearTimeout(searchTimer);
    const v = e.target.value;
    if (v) searchWrap.classList.add('has-value'); else searchWrap.classList.remove('has-value');
    searchTimer = setTimeout(() => { FILTERS.search = v.trim(); PAGE = 1; apply(); }, 180);
  });
  document.getElementById('btn-clear-search').addEventListener('click', () => {
    searchInput.value = '';
    searchWrap.classList.remove('has-value');
    FILTERS.search = '';
    PAGE = 1;
    apply();
  });

  document.getElementById('btn-export').addEventListener('click', exportCSV);
}

function wirePresets() {
  document.querySelectorAll('.preset').forEach(btn => {
    btn.addEventListener('click', () => applyPreset(btn.dataset.preset));
  });
}

function applyPreset(name) {
  // Toggle behavior: clicking active preset resets
  const presets = {
    'approved':  { yearMin: 1897, yearMax: 1908, cluster: '', status: 'Approved', proposer: '', search: '' },
    '1901':      { yearMin: 1901, yearMax: 1901, cluster: '', status: '',         proposer: '', search: '' },
    'private':   { yearMin: 1897, yearMax: 1908, cluster: '', status: '',         proposer: 'private', search: '' },
    'comm-zero': { yearMin: 1897, yearMax: 1908, cluster: 'Communications and Observation', status: '', proposer: '', search: '' },
    'artillery': { yearMin: 1897, yearMax: 1908, cluster: 'Artillery', status: '', proposer: '', search: '' },
  };
  const p = presets[name];
  if (!p) return;
  // If preset is already active (exact match), toggle off
  const active = JSON.stringify(FILTERS) === JSON.stringify(p);
  FILTERS = active ? { yearMin: 1897, yearMax: 1908, cluster: '', status: '', proposer: '', search: '' } : { ...p };
  syncFilterControls();
  PAGE = 1;
  apply();
  toast(active ? 'Preset cleared' : `Preset: ${name}`);
}

function resetFilters() {
  FILTERS = { yearMin: PROP_DEFAULT.min, yearMax: PROP_DEFAULT.max, cluster: '', status: '', proposer: '', search: '' };
  syncFilterControls();
  PAGE = 1;
  apply();
}

function syncFilterControls() {
  document.getElementById('f-year-min').value = FILTERS.yearMin;
  document.getElementById('f-year-max').value = FILTERS.yearMax;
  document.getElementById('f-cluster').value = FILTERS.cluster;
  document.getElementById('f-status').value = FILTERS.status;
  document.getElementById('f-proposer').value = FILTERS.proposer;
  const searchInput = document.getElementById('f-search');
  searchInput.value = FILTERS.search;
  document.getElementById('search-wrap').classList.toggle('has-value', !!FILTERS.search);
}

// ── Filter + apply ────────────────────────────────────────────────────
function apply() {
  const q = FILTERS.search.toLowerCase();
  FILTERED = ALL.filter(r =>
    r.year >= FILTERS.yearMin &&
    r.year <= FILTERS.yearMax &&
    (!FILTERS.cluster  || r.cluster === FILTERS.cluster) &&
    (!FILTERS.status   || r.status === FILTERS.status) &&
    (!FILTERS.proposer || r.proposerType === FILTERS.proposer) &&
    (!q || r.subject.toLowerCase().includes(q) || r.proposer.toLowerCase().includes(q))
  );

  document.getElementById('match-n').textContent = FILTERED.length.toLocaleString();
  renderActiveChips();
  syncPresetActive();
  renderKPIs();
  renderTimeline();
  renderClusterMix();
  renderStatusByCluster();
  renderTopProposers();
  renderHeatmap();
  renderTable();
  updateHash();
  resizeCharts();
}

function resizeCharts() {
  // Force Plotly to re-measure each chart container after layout settles.
  // Belt-and-suspenders against zero-size renders.
  requestAnimationFrame(() => {
    ['chart-timeline', 'chart-cluster', 'chart-status', 'chart-proposers', 'chart-heatmap'].forEach(id => {
      const el = document.getElementById(id);
      if (el && el._fullLayout) {
        try { Plotly.Plots.resize(el); } catch {}
      }
    });
  });
}

window.addEventListener('resize', () => {
  if (typeof resizeCharts === 'function') resizeCharts();
});

// ── Active filter chips ───────────────────────────────────────────────
function renderActiveChips() {
  const chips = [];
  if (FILTERS.yearMin !== PROP_DEFAULT.min || FILTERS.yearMax !== PROP_DEFAULT.max) {
    const range = FILTERS.yearMin === FILTERS.yearMax ? `${FILTERS.yearMin}` : `${FILTERS.yearMin}–${FILTERS.yearMax}`;
    chips.push({ key: 'year', label: 'YEAR', val: range });
  }
  if (FILTERS.cluster)  chips.push({ key: 'cluster',  label: 'CLUSTER',  val: FILTERS.cluster });
  if (FILTERS.status)   chips.push({ key: 'status',   label: 'STATUS',   val: FILTERS.status });
  if (FILTERS.proposer) chips.push({ key: 'proposer', label: 'PROPOSER', val: FILTERS.proposer });
  if (FILTERS.search)   chips.push({ key: 'search',   label: 'Q',        val: `"${FILTERS.search}"` });

  const container = document.getElementById('active-chips');
  container.innerHTML = chips.map(c =>
    `<span class="chip" data-clear="${c.key}"><span class="label">${c.label}</span><span class="val">${escapeHTML(c.val)}</span><span class="x">✕</span></span>`
  ).join('');
  container.querySelectorAll('.chip').forEach(el => {
    el.addEventListener('click', () => clearFilter(el.dataset.clear));
  });
}

function clearFilter(key) {
  if (key === 'year') { FILTERS.yearMin = 1897; FILTERS.yearMax = 1908; }
  else if (key === 'search') FILTERS.search = '';
  else FILTERS[key] = '';
  syncFilterControls();
  PAGE = 1;
  apply();
}

function syncPresetActive() {
  const presetMap = {
    'approved':  { yearMin: 1897, yearMax: 1908, cluster: '', status: 'Approved', proposer: '', search: '' },
    '1901':      { yearMin: 1901, yearMax: 1901, cluster: '', status: '',         proposer: '', search: '' },
    'private':   { yearMin: 1897, yearMax: 1908, cluster: '', status: '',         proposer: 'private', search: '' },
    'comm-zero': { yearMin: 1897, yearMax: 1908, cluster: 'Communications and Observation', status: '', proposer: '', search: '' },
    'artillery': { yearMin: 1897, yearMax: 1908, cluster: 'Artillery', status: '', proposer: '', search: '' },
  };
  const cur = JSON.stringify(FILTERS);
  document.querySelectorAll('.preset').forEach(btn => {
    btn.classList.toggle('active', JSON.stringify(presetMap[btn.dataset.preset]) === cur);
  });
}

function computePresetCounts() {
  if (!document.getElementById('cnt-approved')) return;  // presets cut from index.html
  const c = id => document.getElementById(id);
  c('cnt-approved').textContent  = ALL.filter(r => r.status === 'Approved').length;
  c('cnt-1901').textContent      = ALL.filter(r => r.year === 1901).length;
  c('cnt-private').textContent   = ALL.filter(r => r.proposerType === 'private').length;
  c('cnt-comm').textContent      = ALL.filter(r => r.cluster === 'Communications and Observation').length;
  c('cnt-art').textContent       = ALL.filter(r => r.cluster === 'Artillery').length;
}

// ── KPIs ──────────────────────────────────────────────────────────────
let lastKPIs = { total: 0, approved: 0, rate: 0 };

function renderKPIs() {
  if (!document.querySelector('[data-kpi="total"]')) return;  // KPIs cut from index.html
  const total    = FILTERED.length;
  const approved = FILTERED.filter(r => r.status === 'Approved').length;
  const rate     = total > 0 ? (approved / total * 100) : 0;

  const clusterCounts = {};
  for (const r of FILTERED) clusterCounts[r.cluster] = (clusterCounts[r.cluster] || 0) + 1;
  const topClusterEntry = Object.entries(clusterCounts).sort((a, b) => b[1] - a[1])[0];
  const topCluster = topClusterEntry ? topClusterEntry[0] : '—';
  const topClusterCount = topClusterEntry ? topClusterEntry[1] : 0;

  const propCounts = {};
  for (const r of FILTERED) {
    if (!r.proposer) continue;
    const k = r.proposer.slice(0, 60);
    propCounts[k] = (propCounts[k] || 0) + 1;
  }
  const topPropEntry = Object.entries(propCounts).sort((a, b) => b[1] - a[1])[0];
  const topProp = topPropEntry ? topPropEntry[0] : '—';
  const topPropCount = topPropEntry ? topPropEntry[1] : 0;

  animateNumber(document.querySelector('[data-kpi="total"]'),    lastKPIs.total,    total,    v => Math.round(v).toLocaleString());
  animateNumber(document.querySelector('[data-kpi="approved"]'), lastKPIs.approved, approved, v => Math.round(v).toLocaleString());
  animateNumber(document.querySelector('[data-kpi="rate"]'),     lastKPIs.rate,     rate,     v => v.toFixed(1) + '<span class="unit">%</span>');

  document.querySelector('[data-kpi="top-cluster"]').textContent = topCluster;
  document.querySelector('[data-kpi="top-proposer"]').textContent = topProp || '—';

  const yearsActive = new Set(FILTERED.map(r => r.year)).size;
  document.getElementById('kpi-total-sub').innerHTML = `across <strong>${yearsActive}</strong> active years`;
  document.getElementById('kpi-approved-sub').innerHTML = approved > 0 ? `<span class="delta-up">▲</span> filter has hits` : '<span class="delta-down">▼</span> no approvals in slice';
  document.getElementById('kpi-rate-sub').innerHTML = rate >= 5 ? `<span class="delta-up">▲</span> above archive avg` : `vs <strong>2.9%</strong> archive avg`;
  document.getElementById('kpi-cluster-sub').innerHTML = `<strong>${topClusterCount.toLocaleString()}</strong> records`;
  document.getElementById('kpi-proposer-sub').innerHTML = topPropCount > 0 ? `<strong>${topPropCount}</strong> submissions` : '—';

  lastKPIs = { total, approved, rate };
}

function animateNumber(el, from, to, fmt) {
  const start = performance.now();
  const dur = 380;
  function tick(now) {
    const t = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - t, 3);
    const v = from + (to - from) * eased;
    el.innerHTML = fmt(v);
    if (t < 1) requestAnimationFrame(tick);
    else el.innerHTML = fmt(to);
  }
  requestAnimationFrame(tick);
}

// ── Charts ────────────────────────────────────────────────────────────
const CLICK_ATTACHED = new Set();

function attachClick(divId, handler) {
  if (CLICK_ATTACHED.has(divId)) return;
  const el = document.getElementById(divId);
  if (!el || !el.on) return;  // chart was cut from index.html
  CLICK_ATTACHED.add(divId);
  el.on('plotly_click', handler);
}

function renderTimeline() {
  const byYearStatus = {};
  const statuses = ['Approved', 'Investigating', 'Rejected', 'Other'];
  for (let y = FILTERS.yearMin; y <= FILTERS.yearMax; y++) {
    byYearStatus[y] = { Approved: 0, Investigating: 0, Rejected: 0, Other: 0 };
  }
  for (const r of FILTERED) byYearStatus[r.year][r.status]++;

  const years = Object.keys(byYearStatus).map(Number).sort((a, b) => a - b);
  const traces = statuses.map(s => ({
    type: 'bar',
    name: s,
    x: years,
    y: years.map(y => byYearStatus[y][s]),
    marker: { color: STATUS_COLOR[s], line: { width: 0 } },
    hovertemplate: `<b>${s}</b><br>%{x}: %{y} <span style="opacity:.6">(click to drill)</span><extra></extra>`,
  }));

  Plotly.react('chart-timeline', traces, {
    ...PLOT_BASE_LAYOUT,
    barmode: 'stack',
    showlegend: true,
    legend: { orientation: 'h', x: 0, y: 1.16, font: { color: COLORS.textMid, size: 10 } },
    xaxis: { ...PLOT_AXIS, dtick: 1, title: '' },
    yaxis: { ...PLOT_AXIS, title: '' },
    margin: { l: 50, r: 16, t: 36, b: 36 },
  }, PLOT_CONFIG).then(() => attachClick('chart-timeline', e => {
    const yr = e.points[0].x;
    FILTERS.yearMin = yr; FILTERS.yearMax = yr;
    syncFilterControls(); PAGE = 1; apply();
    toast(`Drilled to ${yr}`);
  }));
}

function renderClusterMix() {
  const counts = {};
  for (const r of FILTERED) counts[r.cluster] = (counts[r.cluster] || 0) + 1;
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const labels = entries.map(e => e[0]);
  const values = entries.map(e => e[1]);
  const colors = labels.map(l => CLUSTER_COLOR[l] || COLORS.textSoft);

  Plotly.react('chart-cluster', [{
    type: 'pie',
    hole: 0.62,
    labels,
    values,
    marker: { colors, line: { color: COLORS.bg, width: 1 } },
    textinfo: 'none',
    hovertemplate: '<b>%{label}</b><br>%{value} (%{percent}) <span style="opacity:.6">click to filter</span><extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: 'v', x: 1.05, y: 0.5, font: { color: COLORS.textMid, size: 9 } },
    margin: { l: 6, r: 0, t: 6, b: 6 },
    annotations: [{
      text: `<b>${FILTERED.length.toLocaleString()}</b><br><span style="color:${COLORS.textMid};font-size:9px;letter-spacing:1.4px;">RECORDS</span>`,
      showarrow: false, font: { color: COLORS.text, size: 18, family: PLOT_FONT.family },
      x: 0.5, y: 0.5,
    }],
  }, PLOT_CONFIG).then(() => attachClick('chart-cluster', e => {
    const cluster = e.points[0].label;
    FILTERS.cluster = FILTERS.cluster === cluster ? '' : cluster;
    syncFilterControls(); PAGE = 1; apply();
    toast(FILTERS.cluster ? `Cluster: ${cluster}` : 'Cluster cleared');
  }));
}

function renderStatusByCluster() {
  const clusters = [...new Set(FILTERED.map(r => r.cluster))]
    .map(c => ({ c, n: FILTERED.filter(r => r.cluster === c).length }))
    .sort((a, b) => a.n - b.n)
    .map(o => o.c);

  const statuses = ['Approved', 'Investigating', 'Rejected', 'Other'];
  const totals = clusters.map(c => FILTERED.filter(r => r.cluster === c).length);
  const traces = statuses.map(s => {
    const counts = clusters.map(c => FILTERED.filter(r => r.cluster === c && r.status === s).length);
    return {
      type: 'bar',
      orientation: 'h',
      name: s,
      y: clusters,
      x: counts.map((n, i) => totals[i] > 0 ? n / totals[i] * 100 : 0),
      customdata: counts.map((n, i) => [n, totals[i], s]),
      marker: { color: STATUS_COLOR[s], line: { width: 0 } },
      hovertemplate: `<b>%{y}</b><br>${s}: %{customdata[0]} of %{customdata[1]} (%{x:.1f}%) <span style="opacity:.6">click to filter</span><extra></extra>`,
    };
  });

  Plotly.react('chart-status', traces, {
    ...PLOT_BASE_LAYOUT,
    barmode: 'stack',
    showlegend: true,
    legend: { orientation: 'h', x: 0, y: 1.16, font: { color: COLORS.textMid, size: 10 } },
    xaxis: { ...PLOT_AXIS, range: [0, 100], ticksuffix: '%' },
    yaxis: { ...PLOT_AXIS, automargin: true },
    margin: { l: 12, r: 16, t: 36, b: 32 },
  }, PLOT_CONFIG).then(() => attachClick('chart-status', e => {
    const p = e.points[0];
    const cluster = p.y;
    const status = p.customdata[2];
    FILTERS.cluster = cluster;
    FILTERS.status = status;
    syncFilterControls(); PAGE = 1; apply();
    toast(`${cluster} · ${status}`);
  }));
}

function renderTopProposers() {
  const counts = {};
  const fullName = {};
  for (const r of FILTERED) {
    if (!r.proposer) continue;
    const k = r.proposer.length > 36 ? r.proposer.slice(0, 36) + '…' : r.proposer;
    counts[k] = (counts[k] || 0) + 1;
    fullName[k] = r.proposer;
  }
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12).reverse();
  const labels = top.map(e => e[0]);
  const values = top.map(e => e[1]);

  Plotly.react('chart-proposers', [{
    type: 'bar',
    orientation: 'h',
    x: values,
    y: labels,
    customdata: labels.map(l => fullName[l]),
    marker: { color: COLORS.cyan, line: { width: 0 } },
    text: values.map(v => v.toString()),
    textposition: 'outside',
    textfont: { color: COLORS.textMid, size: 10, family: PLOT_FONT.family },
    hovertemplate: '<b>%{customdata}</b><br>%{x} submissions <span style="opacity:.6">click to search</span><extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    xaxis: { ...PLOT_AXIS, title: '' },
    yaxis: { ...PLOT_AXIS, automargin: true, tickfont: { ...PLOT_AXIS.tickfont, size: 9 } },
    margin: { l: 8, r: 36, t: 12, b: 32 },
  }, PLOT_CONFIG).then(() => attachClick('chart-proposers', e => {
    const full = e.points[0].customdata;
    FILTERS.search = full;
    syncFilterControls(); PAGE = 1; apply();
    toast(`Search: ${full.slice(0, 30)}`);
  }));
}

function renderHeatmap() {
  const clusters = [...new Set(ALL.map(r => r.cluster))].sort();
  const years = [];
  for (let y = FILTERS.yearMin; y <= FILTERS.yearMax; y++) years.push(y);

  const z = clusters.map(c =>
    years.map(y => FILTERED.filter(r => r.cluster === c && r.year === y).length)
  );

  Plotly.react('chart-heatmap', [{
    type: 'heatmap',
    x: years,
    y: clusters,
    z,
    colorscale: heatmapScale(),
    showscale: true,
    colorbar: {
      thickness: 8, len: 0.8, outlinewidth: 0,
      tickfont: { color: COLORS.textMid, size: 9, family: PLOT_FONT.family },
    },
    hovertemplate: '<b>%{y}</b> · %{x}<br>%{z} submissions <span style="opacity:.6">click to drill</span><extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    xaxis: { ...PLOT_AXIS, dtick: 1 },
    yaxis: { ...PLOT_AXIS, automargin: true, tickfont: { ...PLOT_AXIS.tickfont, size: 9 } },
    margin: { l: 8, r: 50, t: 12, b: 36 },
  }, PLOT_CONFIG).then(() => attachClick('chart-heatmap', e => {
    const p = e.points[0];
    FILTERS.cluster = p.y;
    FILTERS.yearMin = p.x; FILTERS.yearMax = p.x;
    syncFilterControls(); PAGE = 1; apply();
    toast(`${p.y} · ${p.x}`);
  }));
}

// ── Records table ─────────────────────────────────────────────────────
function wireTable() {
  document.querySelectorAll('.records-table thead th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (SORT.key === key) SORT.dir = SORT.dir === 'asc' ? 'desc' : 'asc';
      else { SORT.key = key; SORT.dir = 'asc'; }
      renderTable();
    });
  });
}

function renderTable() {
  const sorted = [...FILTERED].sort((a, b) => {
    const av = a[SORT.key], bv = b[SORT.key];
    if (typeof av === 'number') return SORT.dir === 'asc' ? av - bv : bv - av;
    const as = String(av || '').toLowerCase();
    const bs = String(bv || '').toLowerCase();
    return SORT.dir === 'asc' ? as.localeCompare(bs) : bs.localeCompare(as);
  });

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  if (PAGE > totalPages) PAGE = 1;
  const start = (PAGE - 1) * PAGE_SIZE;
  const slice = sorted.slice(start, start + PAGE_SIZE);

  // Header sort indicators
  document.querySelectorAll('.records-table thead th').forEach(th => {
    th.classList.toggle('sorted', th.dataset.sort === SORT.key);
    const ind = th.querySelector('.sort-ind');
    ind.textContent = SORT.dir === 'asc' ? '▲' : '▼';
  });

  // Body
  const tbody = document.getElementById('records-tbody');
  if (sorted.length === 0) {
    tbody.innerHTML = '';
    document.getElementById('records-empty').style.display = 'block';
    document.getElementById('records-table').style.display = 'none';
  } else {
    document.getElementById('records-empty').style.display = 'none';
    document.getElementById('records-table').style.display = '';
    tbody.innerHTML = slice.map(r => `
      <tr data-id="${r.id}">
        <td class="col-year">${r.year}</td>
        <td class="col-subject" title="${escapeHTML(r.subject)}">${highlightMatch(r.subject)}</td>
        <td class="col-proposer" title="${escapeHTML(r.proposer)}">${highlightMatch(r.proposer)}</td>
        <td class="col-cluster">${escapeHTML(r.cluster)}</td>
        <td class="col-status"><span class="badge b-${r.status.toLowerCase()}">${r.status.toUpperCase()}</span></td>
      </tr>
    `).join('');
    tbody.querySelectorAll('tr').forEach(tr => {
      tr.addEventListener('click', () => openDetail(parseInt(tr.dataset.id, 10)));
    });
  }

  // Info
  if (sorted.length > 0) {
    document.getElementById('rec-range').textContent = `${start + 1}–${Math.min(start + PAGE_SIZE, sorted.length)}`;
  } else {
    document.getElementById('rec-range').textContent = '0';
  }
  document.getElementById('rec-total').textContent = sorted.length.toLocaleString();

  // Pager
  renderPager(totalPages);
}

function highlightMatch(text) {
  const safe = escapeHTML(text);
  if (!FILTERS.search) return safe;
  const re = new RegExp('(' + FILTERS.search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
  return safe.replace(re, '<mark style="background:rgba(91,188,255,0.25);color:var(--cyan);padding:0 1px;">$1</mark>');
}

function renderPager(totalPages) {
  const pager = document.getElementById('pager');
  if (totalPages <= 1) { pager.innerHTML = ''; return; }

  const buttons = [];
  buttons.push(`<button id="pg-prev" ${PAGE === 1 ? 'disabled' : ''}>‹ prev</button>`);

  // Show: 1 ... PAGE-1 PAGE PAGE+1 ... totalPages
  const pages = new Set([1, totalPages, PAGE - 1, PAGE, PAGE + 1]);
  const sortedPages = [...pages].filter(p => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  let last = 0;
  for (const p of sortedPages) {
    if (last && p - last > 1) buttons.push('<span style="color:var(--text-soft);padding:0 4px;">…</span>');
    buttons.push(`<button data-page="${p}" class="${p === PAGE ? 'active' : ''}">${p}</button>`);
    last = p;
  }

  buttons.push(`<button id="pg-next" ${PAGE === totalPages ? 'disabled' : ''}>next ›</button>`);
  buttons.push(`<span class="pg-info">page ${PAGE} of ${totalPages}</span>`);

  pager.innerHTML = buttons.join('');
  pager.querySelectorAll('button[data-page]').forEach(b => b.addEventListener('click', () => { PAGE = parseInt(b.dataset.page, 10); renderTable(); }));
  const prev = document.getElementById('pg-prev');
  const next = document.getElementById('pg-next');
  if (prev) prev.addEventListener('click', () => { PAGE = Math.max(1, PAGE - 1); renderTable(); });
  if (next) next.addEventListener('click', () => { PAGE = Math.min(totalPages, PAGE + 1); renderTable(); });
}

// ── Detail modal ──────────────────────────────────────────────────────
function wireModal() {
  document.getElementById('modal-close').addEventListener('click', closeDetail);
  document.getElementById('modal-backdrop').addEventListener('click', e => {
    if (e.target.id === 'modal-backdrop') closeDetail();
  });
}

function openDetail(id) {
  const r = ALL.find(x => x.id === id);
  if (!r) return;
  document.getElementById('m-year').textContent = r.year;
  document.getElementById('m-cluster').textContent = r.cluster;
  document.getElementById('m-status').textContent = r.status.toUpperCase();
  document.getElementById('m-status').style.color = STATUS_COLOR[r.status];
  document.getElementById('m-subject').textContent = r.subject || '(no subject recorded)';
  document.getElementById('m-action').textContent = r.action || '(none recorded)';
  document.getElementById('m-reasoning').textContent = r.reasoning || '(none recorded)';
  document.getElementById('m-proposer').textContent = r.proposer || '(unattributed)';
  document.getElementById('m-report').textContent = r.report || '—';
  document.getElementById('m-status-raw').textContent = r.statusRaw || '—';
  document.getElementById('m-action-section').style.display = r.action ? '' : 'none';
  document.getElementById('m-reasoning-section').style.display = r.reasoning ? '' : 'none';
  document.getElementById('modal-backdrop').classList.add('open');
}

function closeDetail() {
  document.getElementById('modal-backdrop').classList.remove('open');
}

// ── Keyboard shortcuts ────────────────────────────────────────────────
function wireKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDetail();
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
      e.preventDefault();
      document.getElementById('f-search').focus();
    }
    if (e.key === 'r' && e.metaKey === false && e.ctrlKey === false && document.activeElement.tagName !== 'INPUT') {
      resetFilters();
      toast('Filters reset');
    }
  });
}

// ── URL hash sync ─────────────────────────────────────────────────────
function updateHash() {
  const params = new URLSearchParams();
  if (VIEW !== 'proposals') params.set('view', VIEW);
  if (VIEW === 'proposals') {
    if (FILTERS.yearMin !== PROP_DEFAULT.min || FILTERS.yearMax !== PROP_DEFAULT.max) params.set('y', `${FILTERS.yearMin}-${FILTERS.yearMax}`);
    if (FILTERS.cluster)  params.set('c', FILTERS.cluster);
    if (FILTERS.status)   params.set('s', FILTERS.status);
    if (FILTERS.proposer) params.set('p', FILTERS.proposer);
    if (FILTERS.search)   params.set('q', FILTERS.search);
  } else if (VIEW === 'budget') {
    if (BUDGET_FILTERS.yearMin !== BUDGET_DEFAULT.min || BUDGET_FILTERS.yearMax !== BUDGET_DEFAULT.max) params.set('by', `${BUDGET_FILTERS.yearMin}-${BUDGET_FILTERS.yearMax}`);
    if (BUDGET_FILTERS.branch) params.set('bb', BUDGET_FILTERS.branch);
    if (BUDGET_FILTERS.units !== '2025') params.set('bu', BUDGET_FILTERS.units);
  } else if (VIEW === 'timeline') {
    if (TIMELINE_FILTERS.category) params.set('tc', TIMELINE_FILTERS.category);
    if (TIMELINE_FILTERS.outcome) params.set('to', TIMELINE_FILTERS.outcome);
    if (TIMELINE_FILTERS.source) params.set('ts', TIMELINE_FILTERS.source);
    if (TIMELINE_FILTERS.search) params.set('tq', TIMELINE_FILTERS.search);
  } else if (VIEW === 'spending') {
    if (SPENDING_FILTERS.yearMin !== SPENDING_DEFAULT.min || SPENDING_FILTERS.yearMax !== SPENDING_DEFAULT.max) params.set('sy', `${SPENDING_FILTERS.yearMin}-${SPENDING_FILTERS.yearMax}`);
    if (SPENDING_FILTERS.revoked) params.set('sr', SPENDING_FILTERS.revoked);
    if (SPENDING_FILTERS.search) params.set('sq', SPENDING_FILTERS.search);
  }
  const h = params.toString();
  history.replaceState(null, '', h ? '#' + h : window.location.pathname);
}

function stateFromHash() {
  if (!window.location.hash) return;
  const params = new URLSearchParams(window.location.hash.slice(1));
  if (params.has('view')) VIEW = params.get('view');
  if (params.has('y')) {
    const [a, b] = params.get('y').split('-').map(Number);
    if (Number.isFinite(a) && Number.isFinite(b)) { FILTERS.yearMin = a; FILTERS.yearMax = b; }
  }
  if (params.has('c')) FILTERS.cluster = params.get('c');
  if (params.has('s')) FILTERS.status  = params.get('s');
  if (params.has('p')) FILTERS.proposer = params.get('p');
  if (params.has('q')) FILTERS.search   = params.get('q');
  if (params.has('by')) {
    const [a, b] = params.get('by').split('-').map(Number);
    if (Number.isFinite(a) && Number.isFinite(b)) { BUDGET_FILTERS.yearMin = a; BUDGET_FILTERS.yearMax = b; }
  }
  if (params.has('bb')) BUDGET_FILTERS.branch = params.get('bb');
  if (params.has('bu')) BUDGET_FILTERS.units = params.get('bu');
  if (params.has('tc')) TIMELINE_FILTERS.category = params.get('tc');
  if (params.has('to')) TIMELINE_FILTERS.outcome = params.get('to');
  if (params.has('ts')) TIMELINE_FILTERS.source = params.get('ts');
  if (params.has('tq')) TIMELINE_FILTERS.search = params.get('tq');
  if (params.has('sy')) {
    const [a, b] = params.get('sy').split('-').map(Number);
    if (Number.isFinite(a) && Number.isFinite(b)) { SPENDING_FILTERS.yearMin = a; SPENDING_FILTERS.yearMax = b; }
  }
  if (params.has('sr')) SPENDING_FILTERS.revoked = params.get('sr');
  if (params.has('sq')) SPENDING_FILTERS.search = params.get('sq');
  syncFilterControls();
  syncBudgetControls();
  syncTimelineControls();
  syncSpendingControls();
  if (VIEW === 'budget') setView('budget');
  else if (VIEW === 'timeline') setView('timeline');
  else if (VIEW === 'spending') setView('spending');
}

function syncTimelineControls() {
  document.getElementById('t-category').value = TIMELINE_FILTERS.category;
  document.getElementById('t-outcome').value = TIMELINE_FILTERS.outcome;
  document.getElementById('t-source').value = TIMELINE_FILTERS.source;
  const search = document.getElementById('t-search');
  search.value = TIMELINE_FILTERS.search;
  document.getElementById('t-search-wrap').classList.toggle('has-value', !!TIMELINE_FILTERS.search);
}

// ── CSV export ────────────────────────────────────────────────────────
function exportCSV() {
  if (FILTERED.length === 0) { toast('Nothing to export'); return; }
  const headers = ['year', 'subject', 'proposer', 'cluster', 'status', 'status_raw', 'report', 'action', 'reasoning'];
  const rows = FILTERED.map(r => headers.map(h => {
    const map = { status_raw: r.statusRaw };
    const v = h in map ? map[h] : r[h];
    const s = String(v == null ? '' : v).replace(/"/g, '""');
    return `"${s}"`;
  }).join(','));
  const csv = headers.join(',') + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `bof-filtered-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast(`Exported ${FILTERED.length.toLocaleString()} records`);
}

// ── Toast ─────────────────────────────────────────────────────────────
function toast(msg) {
  const host = document.getElementById('toast-host');
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => el.classList.add('fade-out'), 1400);
  setTimeout(() => el.remove(), 1800);
}

// ── Ticker ────────────────────────────────────────────────────────────
function buildTicker() {
  const sample = [];
  const candidates = ALL.filter(r => r.subject && r.proposer).slice();
  for (let i = 0; i < 60 && candidates.length > 0; i++) {
    const idx = Math.floor(Math.random() * candidates.length);
    sample.push(candidates.splice(idx, 1)[0]);
  }
  const html = sample.map(r => {
    const subj = r.subject.length > 60 ? r.subject.slice(0, 60) + '…' : r.subject;
    const by = r.proposer.length > 30 ? r.proposer.slice(0, 30) + '…' : r.proposer;
    return `<span class="tick" data-id="${r.id}">
      <span class="yr">${r.year}</span>
      <span class="subj">${escapeHTML(subj)}</span>
      <span class="by">${escapeHTML(by)}</span>
      <span class="st-${r.status.toLowerCase()}">${r.status.toUpperCase()}</span>
    </span>`;
  }).join('');
  const ticker = document.getElementById('ticker');
  ticker.innerHTML = html + html;
  ticker.querySelectorAll('.tick').forEach(el => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => openDetail(parseInt(el.dataset.id, 10)));
  });
}

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

// ── Clock ─────────────────────────────────────────────────────────────
function tickClock() {
  const d = new Date();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  document.getElementById('clock').textContent = `${hh}:${mm}:${ss}`;
}
setInterval(tickClock, 1000); tickClock();

// ── Budget view ───────────────────────────────────────────────────────
const BRANCH_COLOR = () => ({
  Army: COLORS.accent,
  Navy: COLORS.cyan,
});

function fmtUSD(v) {
  if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (Math.abs(v) >= 1e9)  return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`;
  if (Math.abs(v) >= 1e3)  return `$${(v / 1e3).toFixed(0)}K`;
  return `$${Math.round(v).toLocaleString()}`;
}

function budgetVal(r) { return BUDGET_FILTERS.units === '2025' ? r.adjusted : r.nominal; }
function budgetUnitLabel() { return BUDGET_FILTERS.units === '2025' ? '2025 $' : 'Nominal $'; }

function wireBudgetFilters() {
  document.getElementById('b-year-min').addEventListener('change', e => {
    BUDGET_FILTERS.yearMin = parseInt(e.target.value, 10); BUDGET_PAGE = 1; applyBudget();
  });
  document.getElementById('b-year-max').addEventListener('change', e => {
    BUDGET_FILTERS.yearMax = parseInt(e.target.value, 10); BUDGET_PAGE = 1; applyBudget();
  });
  document.getElementById('b-branch').addEventListener('change', e => {
    BUDGET_FILTERS.branch = e.target.value; BUDGET_PAGE = 1; applyBudget();
  });
  document.getElementById('b-units').addEventListener('change', e => {
    BUDGET_FILTERS.units = e.target.value; applyBudget();
  });
  document.getElementById('btn-clear-budget').addEventListener('click', resetBudgetFilters);
  document.getElementById('btn-export-budget').addEventListener('click', exportBudgetCSV);
}

function wireBudgetPresets() {
  const presets = {
    reconstruction: { yearMin: 1866, yearMax: 1879 },
    gilded:         { yearMin: 1880, yearMax: 1897 },
    'span-am':      { yearMin: 1898, yearMax: 1900 },
    prewwi:         { yearMin: 1901, yearMax: 1916 },
    wwi:            { yearMin: 1917, yearMax: 1920 },
  };
  document.querySelectorAll('[data-budget-preset]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = presets[btn.dataset.budgetPreset];
      if (!p) return;
      const cur = JSON.stringify({ yearMin: BUDGET_FILTERS.yearMin, yearMax: BUDGET_FILTERS.yearMax });
      const target = JSON.stringify(p);
      const active = cur === target;
      BUDGET_FILTERS.yearMin = active ? 1866 : p.yearMin;
      BUDGET_FILTERS.yearMax = active ? 1920 : p.yearMax;
      BUDGET_FILTERS.branch = '';
      syncBudgetControls();
      BUDGET_PAGE = 1;
      applyBudget();
      toast(active ? 'Era cleared' : `Era: ${btn.textContent.trim().split(' ')[0]}`);
    });
  });
}

function wireBudgetTable() {
  document.querySelectorAll('#b-records-table thead th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.bsort;
      if (BUDGET_SORT.key === key) BUDGET_SORT.dir = BUDGET_SORT.dir === 'asc' ? 'desc' : 'asc';
      else { BUDGET_SORT.key = key; BUDGET_SORT.dir = 'asc'; }
      renderBudgetTable();
    });
  });
}

function resetBudgetFilters() {
  BUDGET_FILTERS = { yearMin: BUDGET_DEFAULT.min, yearMax: BUDGET_DEFAULT.max, branch: '', units: BUDGET_FILTERS.units };
  syncBudgetControls();
  BUDGET_PAGE = 1;
  applyBudget();
}

function syncBudgetControls() {
  document.getElementById('b-year-min').value = BUDGET_FILTERS.yearMin;
  document.getElementById('b-year-max').value = BUDGET_FILTERS.yearMax;
  document.getElementById('b-branch').value = BUDGET_FILTERS.branch;
  document.getElementById('b-units').value = BUDGET_FILTERS.units;
}

function applyBudget() {
  FILTERED_BUDGET = ALL_BUDGET.filter(r =>
    r.year >= BUDGET_FILTERS.yearMin &&
    r.year <= BUDGET_FILTERS.yearMax &&
    (!BUDGET_FILTERS.branch || r.branch === BUDGET_FILTERS.branch)
  );

  renderBudgetActiveChips();
  renderBudgetKPIs();
  renderBudgetTimeline();
  renderBudgetBranch();
  renderBudgetDecade();
  renderBudgetYoY();
  renderBudgetTable();
  updateHash();
  resizeBudgetCharts();
}

function renderBudgetActiveChips() {
  const chips = [];
  if (BUDGET_FILTERS.yearMin !== BUDGET_DEFAULT.min || BUDGET_FILTERS.yearMax !== BUDGET_DEFAULT.max) {
    const range = BUDGET_FILTERS.yearMin === BUDGET_FILTERS.yearMax
      ? `${BUDGET_FILTERS.yearMin}` : `${BUDGET_FILTERS.yearMin}–${BUDGET_FILTERS.yearMax}`;
    chips.push({ key: 'year', label: 'YEAR', val: range });
  }
  if (BUDGET_FILTERS.branch) chips.push({ key: 'branch', label: 'BRANCH', val: BUDGET_FILTERS.branch });
  if (BUDGET_FILTERS.units !== '2025') chips.push({ key: 'units', label: 'UNITS', val: 'Nominal' });

  const c = document.getElementById('budget-active-chips');
  c.innerHTML = chips.map(ch =>
    `<span class="chip" data-bclear="${ch.key}"><span class="label">${ch.label}</span><span class="val">${escapeHTML(ch.val)}</span><span class="x">✕</span></span>`
  ).join('');
  c.querySelectorAll('.chip').forEach(el => el.addEventListener('click', () => clearBudgetFilter(el.dataset.bclear)));
}

function clearBudgetFilter(key) {
  if (key === 'year') { BUDGET_FILTERS.yearMin = 1866; BUDGET_FILTERS.yearMax = 1920; }
  else if (key === 'units') BUDGET_FILTERS.units = '2025';
  else BUDGET_FILTERS[key] = '';
  syncBudgetControls();
  BUDGET_PAGE = 1;
  applyBudget();
}

function renderBudgetKPIs() {
  if (!document.querySelector('[data-bkpi="total"]')) return;  // KPIs cut from index.html
  const total = FILTERED_BUDGET.reduce((s, r) => s + budgetVal(r), 0);
  const years = [...new Set(FILTERED_BUDGET.map(r => r.year))];
  const yearTotals = {};
  for (const r of FILTERED_BUDGET) yearTotals[r.year] = (yearTotals[r.year] || 0) + budgetVal(r);
  const peakEntry = Object.entries(yearTotals).sort((a, b) => b[1] - a[1])[0];
  const peakYear = peakEntry ? peakEntry[0] : '—';
  const peakAmt = peakEntry ? peakEntry[1] : 0;
  const avg = years.length > 0 ? total / years.length : 0;

  const armyTotal = FILTERED_BUDGET.filter(r => r.branch === 'Army').reduce((s, r) => s + budgetVal(r), 0);
  const armyShare = total > 0 ? (armyTotal / total * 100) : 0;

  const fmtSum = document.getElementById('b-match-sum');
  fmtSum.textContent = fmtUSD(total);
  document.getElementById('b-match-n').textContent = FILTERED_BUDGET.length.toLocaleString();

  document.querySelector('[data-bkpi="total"]').textContent = fmtUSD(total);
  document.getElementById('bkpi-total-sub').innerHTML = `<strong>${budgetUnitLabel()}</strong> over ${years.length} years`;

  document.querySelector('[data-bkpi="peak-year"]').textContent = peakYear;
  document.getElementById('bkpi-peak-sub').innerHTML = peakAmt > 0 ? `<strong>${fmtUSD(peakAmt)}</strong> total that year` : '—';

  document.querySelector('[data-bkpi="avg"]').textContent = fmtUSD(avg);
  document.getElementById('bkpi-avg-sub').innerHTML = `per fiscal year`;

  const armyEl = document.querySelector('[data-bkpi="army-share"]');
  armyEl.innerHTML = `${armyShare.toFixed(0)}<span class="unit">%</span>`;
  document.getElementById('bkpi-army-sub').innerHTML = `Navy: <strong>${(100 - armyShare).toFixed(0)}%</strong>`;

  document.querySelector('[data-bkpi="years"]').textContent = years.length;
  document.getElementById('bkpi-years-sub').innerHTML = years.length > 0
    ? `<strong>${Math.min(...years)}–${Math.max(...years)}</strong>` : '—';
}

function renderBudgetTimeline() {
  const yearsAll = [...new Set(FILTERED_BUDGET.map(r => r.year))].sort((a, b) => a - b);
  const branches = BUDGET_FILTERS.branch ? [BUDGET_FILTERS.branch] : ['Army', 'Navy'];
  const colors = BRANCH_COLOR();

  const traces = branches.map(b => {
    const yvals = yearsAll.map(y => {
      const rec = FILTERED_BUDGET.find(r => r.year === y && r.branch === b);
      return rec ? budgetVal(rec) : 0;
    });
    return {
      type: 'scatter',
      mode: 'lines',
      name: b,
      x: yearsAll,
      y: yvals,
      stackgroup: 'one',
      fillcolor: colors[b],
      line: { color: colors[b], width: 1.5 },
      hovertemplate: `<b>${b}</b><br>%{x}: %{y:$,.0f}<extra></extra>`,
    };
  });

  Plotly.react('b-chart-timeline', traces, {
    ...PLOT_BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: 'h', x: 0, y: 1.16, font: { color: COLORS.textMid, size: 10 } },
    xaxis: { ...PLOT_AXIS, dtick: 5, title: '' },
    yaxis: { ...PLOT_AXIS, title: '', tickformat: '$.2s' },
    margin: { l: 64, r: 16, t: 36, b: 36 },
  }, PLOT_CONFIG);
}

function renderBudgetBranch() {
  const branchTotals = {};
  for (const r of FILTERED_BUDGET) {
    branchTotals[r.branch] = (branchTotals[r.branch] || 0) + budgetVal(r);
  }
  const labels = Object.keys(branchTotals);
  const values = Object.values(branchTotals);
  const colors = labels.map(b => BRANCH_COLOR()[b] || COLORS.textSoft);
  const total = values.reduce((s, v) => s + v, 0);

  Plotly.react('b-chart-branch', [{
    type: 'pie',
    hole: 0.62,
    labels,
    values,
    marker: { colors, line: { color: COLORS.bg, width: 1 } },
    textinfo: 'none',
    hovertemplate: '<b>%{label}</b><br>%{value:$,.0f} (%{percent})<extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: 'v', x: 1.05, y: 0.5, font: { color: COLORS.textMid, size: 10 } },
    margin: { l: 6, r: 0, t: 6, b: 6 },
    annotations: [{
      text: `<b>${fmtUSD(total)}</b><br><span style="color:${COLORS.textMid};font-size:9px;letter-spacing:1.4px;">TOTAL</span>`,
      showarrow: false, font: { color: COLORS.text, size: 16, family: PLOT_FONT.family },
      x: 0.5, y: 0.5,
    }],
  }, PLOT_CONFIG);
}

function renderBudgetDecade() {
  const decades = [...new Set(FILTERED_BUDGET.map(r => r.decade))].sort();
  const branches = BUDGET_FILTERS.branch ? [BUDGET_FILTERS.branch] : ['Army', 'Navy'];
  const colors = BRANCH_COLOR();

  const traces = branches.map(b => ({
    type: 'bar',
    name: b,
    x: decades,
    y: decades.map(d => FILTERED_BUDGET
      .filter(r => r.decade === d && r.branch === b)
      .reduce((s, r) => s + budgetVal(r), 0)),
    marker: { color: colors[b], line: { width: 0 } },
    hovertemplate: `<b>${b}</b><br>%{x}: %{y:$,.0f}<extra></extra>`,
  }));

  Plotly.react('b-chart-decade', traces, {
    ...PLOT_BASE_LAYOUT,
    barmode: 'stack',
    showlegend: true,
    legend: { orientation: 'h', x: 0, y: 1.16, font: { color: COLORS.textMid, size: 10 } },
    xaxis: { ...PLOT_AXIS, title: '' },
    yaxis: { ...PLOT_AXIS, title: '', tickformat: '$.2s' },
    margin: { l: 64, r: 16, t: 36, b: 36 },
  }, PLOT_CONFIG);
}

function renderBudgetYoY() {
  // Year-over-year percent change in total spend
  const yearTotals = {};
  for (const r of FILTERED_BUDGET) {
    yearTotals[r.year] = (yearTotals[r.year] || 0) + budgetVal(r);
  }
  const years = Object.keys(yearTotals).map(Number).sort((a, b) => a - b);
  const changes = [];
  for (let i = 1; i < years.length; i++) {
    const prev = yearTotals[years[i - 1]];
    const cur = yearTotals[years[i]];
    if (prev > 0) changes.push({ year: years[i], pct: (cur - prev) / prev * 100 });
  }

  const xs = changes.map(c => c.year);
  const ys = changes.map(c => c.pct);
  const colors = ys.map(v => v >= 0 ? COLORS.accent : COLORS.red);

  Plotly.react('b-chart-yoy', [{
    type: 'bar',
    x: xs,
    y: ys,
    marker: { color: colors, line: { width: 0 } },
    hovertemplate: '<b>%{x}</b><br>%{y:+.1f}% vs prior year<extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    xaxis: { ...PLOT_AXIS, dtick: 5, title: '' },
    yaxis: { ...PLOT_AXIS, title: '', ticksuffix: '%', zeroline: true, zerolinecolor: COLORS.textMid },
    margin: { l: 50, r: 16, t: 12, b: 36 },
  }, PLOT_CONFIG);
}

function renderBudgetTable() {
  const sorted = [...FILTERED_BUDGET].sort((a, b) => {
    let av, bv;
    if (BUDGET_SORT.key === 'appropriation_2025_usd') { av = a.adjusted; bv = b.adjusted; }
    else if (BUDGET_SORT.key === 'appropriation_usd') { av = a.nominal;  bv = b.nominal; }
    else { av = a[BUDGET_SORT.key]; bv = b[BUDGET_SORT.key]; }
    if (typeof av === 'number') return BUDGET_SORT.dir === 'asc' ? av - bv : bv - av;
    return BUDGET_SORT.dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  if (BUDGET_PAGE > totalPages) BUDGET_PAGE = 1;
  const start = (BUDGET_PAGE - 1) * PAGE_SIZE;
  const slice = sorted.slice(start, start + PAGE_SIZE);

  document.querySelectorAll('#b-records-table thead th').forEach(th => {
    th.classList.toggle('sorted', th.dataset.bsort === BUDGET_SORT.key);
    const ind = th.querySelector('.sort-ind');
    if (ind) ind.textContent = BUDGET_SORT.dir === 'asc' ? '▲' : '▼';
  });

  const tbody = document.getElementById('b-records-tbody');
  if (sorted.length === 0) {
    tbody.innerHTML = '';
    document.getElementById('b-records-empty').style.display = 'block';
    document.getElementById('b-records-table').style.display = 'none';
  } else {
    document.getElementById('b-records-empty').style.display = 'none';
    document.getElementById('b-records-table').style.display = '';
    tbody.innerHTML = slice.map(r => `
      <tr>
        <td class="col-year">${r.year}</td>
        <td class="col-cluster">${escapeHTML(r.branch)}</td>
        <td class="col-subject">${fmtUSD(r.adjusted)}</td>
        <td class="col-proposer">${fmtUSD(r.nominal)}</td>
        <td class="col-status">${escapeHTML(r.decade)}</td>
      </tr>
    `).join('');
  }

  if (sorted.length > 0) {
    document.getElementById('b-rec-range').textContent = `${start + 1}–${Math.min(start + PAGE_SIZE, sorted.length)}`;
  } else {
    document.getElementById('b-rec-range').textContent = '0';
  }
  document.getElementById('b-rec-total').textContent = sorted.length.toLocaleString();

  renderBudgetPager(totalPages);
}

function renderBudgetPager(totalPages) {
  const pager = document.getElementById('b-pager');
  if (totalPages <= 1) { pager.innerHTML = ''; return; }

  const buttons = [];
  buttons.push(`<button id="b-pg-prev" ${BUDGET_PAGE === 1 ? 'disabled' : ''}>‹ prev</button>`);
  const pages = new Set([1, totalPages, BUDGET_PAGE - 1, BUDGET_PAGE, BUDGET_PAGE + 1]);
  const sortedPages = [...pages].filter(p => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  let last = 0;
  for (const p of sortedPages) {
    if (last && p - last > 1) buttons.push('<span style="color:var(--text-soft);padding:0 4px;">…</span>');
    buttons.push(`<button data-bpage="${p}" class="${p === BUDGET_PAGE ? 'active' : ''}">${p}</button>`);
    last = p;
  }
  buttons.push(`<button id="b-pg-next" ${BUDGET_PAGE === totalPages ? 'disabled' : ''}>next ›</button>`);
  buttons.push(`<span class="pg-info">page ${BUDGET_PAGE} of ${totalPages}</span>`);

  pager.innerHTML = buttons.join('');
  pager.querySelectorAll('button[data-bpage]').forEach(b => b.addEventListener('click', () => { BUDGET_PAGE = parseInt(b.dataset.bpage, 10); renderBudgetTable(); }));
  const prev = document.getElementById('b-pg-prev'); if (prev) prev.addEventListener('click', () => { BUDGET_PAGE = Math.max(1, BUDGET_PAGE - 1); renderBudgetTable(); });
  const next = document.getElementById('b-pg-next'); if (next) next.addEventListener('click', () => { BUDGET_PAGE = Math.min(totalPages, BUDGET_PAGE + 1); renderBudgetTable(); });
}

function exportBudgetCSV() {
  if (FILTERED_BUDGET.length === 0) { toast('Nothing to export'); return; }
  const headers = ['year', 'branch', 'decade', 'appropriation_usd', 'appropriation_2025_usd'];
  const rows = FILTERED_BUDGET.map(r => [
    r.year, r.branch, r.decade, r.nominal, r.adjusted
  ].map(v => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`).join(','));
  const csv = headers.join(',') + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `bof-budget-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast(`Exported ${FILTERED_BUDGET.length.toLocaleString()} records`);
}

// Compute data-driven year bounds for each view's filter inputs.
// FILTERS defaults stay at the BOF reporting window for the focused first view;
// inputs allow expanding to the full data span (and a comfortable margin).
const PROP_DEFAULT = { min: 1897, max: 1908 };
const BUDGET_DEFAULT = { min: 1866, max: 1920 };
const SPENDING_DEFAULT = { min: 1888, max: 1920 };

function setupYearBounds() {
  const propYears = ALL.map(r => r.year).filter(Number.isFinite);
  const budgetYears = ALL_BUDGET.map(r => r.year).filter(Number.isFinite);
  const spendYears = [
    ...ALL_ALLOTMENTS.map(r => r.year),
    ...ALL_APPROPRIATIONS.map(r => r.year),
  ].filter(Number.isFinite);

  const propMin = propYears.length ? Math.min(...propYears) : 1897;
  const propMax = propYears.length ? Math.max(...propYears) : 1908;
  const budgetMin = budgetYears.length ? Math.min(...budgetYears) : 1866;
  const budgetMax = budgetYears.length ? Math.max(...budgetYears) : 1920;
  const spendMin = spendYears.length ? Math.min(...spendYears) : 1888;
  const spendMax = spendYears.length ? Math.max(...spendYears) : 1920;

  // Pad inputs by ±5 years so users can manually overshoot if they like.
  const setBounds = (id, lo, hi) => {
    const el = document.getElementById(id);
    if (el) { el.min = lo; el.max = hi; }
  };
  setBounds('f-year-min', propMin - 5, propMax + 5);
  setBounds('f-year-max', propMin - 5, propMax + 5);
  setBounds('b-year-min', budgetMin - 5, budgetMax + 5);
  setBounds('b-year-max', budgetMin - 5, budgetMax + 5);
  setBounds('s-year-min', spendMin - 5, spendMax + 5);
  setBounds('s-year-max', spendMin - 5, spendMax + 5);

  // Update defaults to match the actual data span (used by reset + active-chip detection).
  PROP_DEFAULT.min = propMin;     PROP_DEFAULT.max = propMax;
  BUDGET_DEFAULT.min = budgetMin; BUDGET_DEFAULT.max = budgetMax;
  SPENDING_DEFAULT.min = spendMin; SPENDING_DEFAULT.max = spendMax;

  // Initial filter values — start at the data span on first load.
  if (FILTERS.yearMin === 1897 && FILTERS.yearMax === 1908) {
    FILTERS.yearMin = propMin; FILTERS.yearMax = propMax;
    document.getElementById('f-year-min').value = propMin;
    document.getElementById('f-year-max').value = propMax;
  }
  if (BUDGET_FILTERS.yearMin === 1866 && BUDGET_FILTERS.yearMax === 1920) {
    BUDGET_FILTERS.yearMin = budgetMin; BUDGET_FILTERS.yearMax = budgetMax;
    document.getElementById('b-year-min').value = budgetMin;
    document.getElementById('b-year-max').value = budgetMax;
  }
  if (SPENDING_FILTERS.yearMin === 1888 && SPENDING_FILTERS.yearMax === 1920) {
    SPENDING_FILTERS.yearMin = spendMin; SPENDING_FILTERS.yearMax = spendMax;
    document.getElementById('s-year-min').value = spendMin;
    document.getElementById('s-year-max').value = spendMax;
  }
}

function resizeBudgetCharts() {
  requestAnimationFrame(() => {
    ['b-chart-timeline', 'b-chart-branch', 'b-chart-decade', 'b-chart-yoy'].forEach(id => {
      const el = document.getElementById(id);
      if (el && el._fullLayout) {
        try { Plotly.Plots.resize(el); } catch {}
      }
    });
  });
}

// ── Timeline view ─────────────────────────────────────────────────────
// Schema (from Paul B's hohhamnap.github.io):
//   PERIODS: ["1888-89", ..., "1915-16"] (28 entries)
//   GROUPS:  [{name, cat, periods: {periodName: [{action, source}]}}]
let TIMELINE_FILTERS = { category: '', outcome: '', source: '', search: '' };

function timelineOutcome(action) {
  const s = (action || '').toLowerCase();
  if (/adopted|recommended\.?$|accepted/.test(s) && !/not\s+rec/.test(s)) return 'a';
  if (/not\s+rec|rejected|failed|adverse|revoked/.test(s)) return 'r';
  if (/allotment|under test|provision made|test\b|granted|under review/.test(s)) return 't';
  return 'o';
}

function timelineColor(action) {
  const o = timelineOutcome(action);
  if (o === 'a') return '#0E7C66';
  if (o === 'r') return '#B91C1C';
  if (o === 't') return '#B45309';
  return '#8C92A4';
}

function wireTimelineFilters() {
  document.getElementById('t-category').addEventListener('change', e => {
    TIMELINE_FILTERS.category = e.target.value; applyTimeline();
  });
  document.getElementById('t-outcome').addEventListener('change', e => {
    TIMELINE_FILTERS.outcome = e.target.value; applyTimeline();
  });
  document.getElementById('t-source').addEventListener('change', e => {
    TIMELINE_FILTERS.source = e.target.value; applyTimeline();
  });
  const searchInput = document.getElementById('t-search');
  const searchWrap = document.getElementById('t-search-wrap');
  let searchTimer;
  searchInput.addEventListener('input', e => {
    clearTimeout(searchTimer);
    const v = e.target.value;
    if (v) searchWrap.classList.add('has-value'); else searchWrap.classList.remove('has-value');
    searchTimer = setTimeout(() => { TIMELINE_FILTERS.search = v.trim().toLowerCase(); applyTimeline(); }, 180);
  });
  document.getElementById('t-btn-clear-search').addEventListener('click', () => {
    searchInput.value = '';
    searchWrap.classList.remove('has-value');
    TIMELINE_FILTERS.search = '';
    applyTimeline();
  });
  document.getElementById('btn-clear-timeline').addEventListener('click', () => {
    TIMELINE_FILTERS = { category: '', outcome: '', source: '', search: '' };
    document.getElementById('t-category').value = '';
    document.getElementById('t-outcome').value = '';
    document.getElementById('t-source').value = '';
    searchInput.value = '';
    searchWrap.classList.remove('has-value');
    applyTimeline();
  });

  document.addEventListener('mousemove', e => {
    const tt = document.getElementById('t-tooltip');
    if (tt && tt.style.display !== 'none') positionTooltip(e);
  });
}

// Filter a group's period entries by source. Returns a new periods object
// containing only entries that match the source filter (or all if no filter).
function filterPeriodsBySource(periods, source) {
  if (!source) return periods;
  const out = {};
  for (const [p, entries] of Object.entries(periods)) {
    const kept = entries.filter(e => e.source === source);
    if (kept.length) out[p] = kept;
  }
  return out;
}

// Determine the "last" entry across periods for outcome classification.
// Periods are ordered chronologically by TIMELINE_PERIODS.
function lastEntryAcrossPeriods(periodsObj) {
  const order = window.TIMELINE_PERIODS;
  for (let i = order.length - 1; i >= 0; i--) {
    const entries = periodsObj[order[i]];
    if (entries && entries.length) return entries[entries.length - 1];
  }
  return null;
}

function applyTimeline() {
  const groups = window.TIMELINE_GROUPS || [];
  const f = TIMELINE_FILTERS;

  // Build filtered groups — each gets source-filtered periods, drop empties.
  let entries = groups.map(g => ({
    name: g.name,
    cat: g.cat,
    periods: filterPeriodsBySource(g.periods, f.source),
  })).filter(g => Object.keys(g.periods).length > 0);

  if (f.category) entries = entries.filter(g => g.cat === f.category);

  if (f.search) {
    entries = entries.filter(g => {
      if (g.name.toLowerCase().includes(f.search)) return true;
      for (const arr of Object.values(g.periods))
        for (const e of arr)
          if (e.action.toLowerCase().includes(f.search)) return true;
      return false;
    });
  }

  if (f.outcome) {
    entries = entries.filter(g => {
      for (const arr of Object.values(g.periods))
        for (const e of arr)
          if (timelineOutcome(e.action) === f.outcome) return true;
      return false;
    });
  }

  entries.sort((a, b) => a.name.localeCompare(b.name));

  // Stats — outcome from the chronologically last entry per group.
  let acc = 0, rej = 0, tst = 0, oth = 0;
  for (const g of entries) {
    const last = lastEntryAcrossPeriods(g.periods);
    if (!last) { oth++; continue; }
    const o = timelineOutcome(last.action);
    if (o === 'a') acc++; else if (o === 'r') rej++; else if (o === 't') tst++; else oth++;
  }

  const total = entries.length;
  if (document.querySelector('[data-tkpi="total"]')) {  // KPIs may be cut from index.html
    document.querySelector('[data-tkpi="total"]').textContent = total;
    document.querySelector('[data-tkpi="accepted"]').textContent = acc;
    document.querySelector('[data-tkpi="rejected"]').textContent = rej;
    document.querySelector('[data-tkpi="testing"]').textContent = tst;
    document.querySelector('[data-tkpi="other"]').textContent = oth;
    const subEl = document.getElementById('tkpi-accepted-sub');
    if (subEl) subEl.innerHTML = total > 0
      ? `<strong>${(acc / total * 100).toFixed(1)}%</strong> of filtered`
      : '—';
  }
  const matchEl = document.getElementById('t-match-n');
  if (matchEl) matchEl.textContent = total;

  renderTimelineTable(entries);
  updateHash();
}

function renderTimelineTable(entries) {
  const wrap = document.getElementById('t-table-wrap');
  if (entries.length === 0) {
    wrap.innerHTML = '<div class="t-empty">⊘ No technologies match this filter</div>';
    return;
  }

  const periods = window.TIMELINE_PERIODS;
  let h = '<table class="timeline-table"><thead><tr>';
  h += `<th>Technology (${entries.length})</th>`;
  for (const p of periods) h += `<th>${p}</th>`;
  h += '</tr></thead><tbody>';

  for (const g of entries) {
    const safeName = escapeHTML(g.name);
    let totalEntries = 0;
    for (const arr of Object.values(g.periods)) totalEntries += arr.length;

    h += `<tr><td title="${safeName}">${safeName}${totalEntries > 1 ? `<span class="t-cnt">${totalEntries}×</span>` : ''}</td>`;
    for (const p of periods) {
      const arr = g.periods[p];
      h += '<td class="tlc">';
      if (arr && arr.length) {
        // Color = last entry's action; source mix dictates bar style.
        const last = arr[arr.length - 1];
        const c = timelineColor(last.action);
        const sources = new Set(arr.map(e => e.source));
        const isDashed = sources.size === 1 && sources.has('financial');
        const dashStyle = isDashed
          ? `background:repeating-linear-gradient(45deg, ${c}, ${c} 4px, transparent 4px, transparent 7px); border:1.5px solid ${c};`
          : `background:${c};`;
        const meta = encodeURIComponent(JSON.stringify({
          n: g.name,
          a: last.action,
          y: p,
          cnt: arr.length,
          src: [...sources].join(' + ')
        }));
        h += `<div class="t-bar" style="${dashStyle}" data-meta="${meta}"></div>`;
      }
      h += '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table>';
  wrap.innerHTML = h;

  wrap.querySelectorAll('.t-bar').forEach(el => {
    el.addEventListener('mouseenter', e => showTimelineTooltip(e, el));
    el.addEventListener('mouseleave', hideTimelineTooltip);
  });
}

function showTimelineTooltip(e, el) {
  const d = JSON.parse(decodeURIComponent(el.dataset.meta));
  document.getElementById('t-tt-name').textContent = d.n;
  document.getElementById('t-tt-action').textContent = d.a;
  const meta = [d.y];
  if (d.cnt > 1) meta.push(`${d.cnt} entries`);
  if (d.src) meta.push(`source: ${d.src}`);
  document.getElementById('t-tt-meta').textContent = meta.join(' · ');
  document.getElementById('t-tooltip').style.display = 'block';
  positionTooltip(e);
}

function hideTimelineTooltip() {
  document.getElementById('t-tooltip').style.display = 'none';
}

function positionTooltip(e) {
  const t = document.getElementById('t-tooltip');
  let x = e.clientX + 14, y = e.clientY - 12;
  if (x + 310 > window.innerWidth) x = e.clientX - 320;
  if (y + 100 > window.innerHeight) y = e.clientY - 110;
  t.style.left = x + 'px';
  t.style.top = y + 'px';
}

// ── Spending view ─────────────────────────────────────────────────────
function wireSpendingFilters() {
  document.getElementById('s-year-min').addEventListener('change', e => {
    SPENDING_FILTERS.yearMin = parseInt(e.target.value, 10); SPENDING_PAGE = 1; applySpending();
  });
  document.getElementById('s-year-max').addEventListener('change', e => {
    SPENDING_FILTERS.yearMax = parseInt(e.target.value, 10); SPENDING_PAGE = 1; applySpending();
  });
  document.getElementById('s-revoked').addEventListener('change', e => {
    SPENDING_FILTERS.revoked = e.target.value; SPENDING_PAGE = 1; applySpending();
  });
  const searchInput = document.getElementById('s-search');
  const searchWrap = document.getElementById('s-search-wrap');
  let searchTimer;
  searchInput.addEventListener('input', e => {
    clearTimeout(searchTimer);
    const v = e.target.value;
    if (v) searchWrap.classList.add('has-value'); else searchWrap.classList.remove('has-value');
    searchTimer = setTimeout(() => { SPENDING_FILTERS.search = v.trim().toLowerCase(); SPENDING_PAGE = 1; applySpending(); }, 180);
  });
  document.getElementById('s-btn-clear-search').addEventListener('click', () => {
    searchInput.value = '';
    searchWrap.classList.remove('has-value');
    SPENDING_FILTERS.search = '';
    SPENDING_PAGE = 1;
    applySpending();
  });
  document.getElementById('btn-clear-spending').addEventListener('click', () => {
    SPENDING_FILTERS = { yearMin: SPENDING_DEFAULT.min, yearMax: SPENDING_DEFAULT.max, revoked: '', search: '' };
    syncSpendingControls();
    SPENDING_PAGE = 1;
    applySpending();
  });
  document.getElementById('btn-export-spending').addEventListener('click', exportSpendingCSV);
}

function syncSpendingControls() {
  document.getElementById('s-year-min').value = SPENDING_FILTERS.yearMin;
  document.getElementById('s-year-max').value = SPENDING_FILTERS.yearMax;
  document.getElementById('s-revoked').value = SPENDING_FILTERS.revoked;
  const search = document.getElementById('s-search');
  search.value = SPENDING_FILTERS.search;
  document.getElementById('s-search-wrap').classList.toggle('has-value', !!SPENDING_FILTERS.search);
}

function wireSpendingTable() {
  document.querySelectorAll('#s-records-table thead th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.ssort;
      if (SPENDING_SORT.key === key) SPENDING_SORT.dir = SPENDING_SORT.dir === 'asc' ? 'desc' : 'asc';
      else { SPENDING_SORT.key = key; SPENDING_SORT.dir = 'asc'; }
      renderSpendingTable();
    });
  });
}

function applySpending() {
  const q = SPENDING_FILTERS.search;
  FILTERED_ALLOTMENTS = ALL_ALLOTMENTS.filter(r =>
    r.year >= SPENDING_FILTERS.yearMin &&
    r.year <= SPENDING_FILTERS.yearMax &&
    (SPENDING_FILTERS.revoked === '' ||
     (SPENDING_FILTERS.revoked === 'active' && !r.revoked) ||
     (SPENDING_FILTERS.revoked === 'revoked' && r.revoked)) &&
    (!q || r.description.toLowerCase().includes(q) || (r.notes && r.notes.toLowerCase().includes(q)))
  );

  renderSpendingKPIs();
  renderSpendingTimeline();
  renderSpendingRevoked();
  renderSpendingTop();
  renderSpendingTable();
  updateHash();
  resizeSpendingCharts();
}

function renderSpendingKPIs() {
  if (!document.querySelector('[data-skpi="total"]')) return;  // KPIs cut from index.html
  const totalAllot = FILTERED_ALLOTMENTS.reduce((s, r) => s + r.amount, 0);
  const revokedCount = FILTERED_ALLOTMENTS.filter(r => r.revoked).length;
  const revokeRate = FILTERED_ALLOTMENTS.length > 0 ? (revokedCount / FILTERED_ALLOTMENTS.length * 100) : 0;

  // Total appropriated within filter
  const filteredAppro = ALL_APPROPRIATIONS.filter(r =>
    r.year >= SPENDING_FILTERS.yearMin && r.year <= SPENDING_FILTERS.yearMax
  );
  const totalAppro = filteredAppro.reduce((s, r) => s + r.amount, 0);

  // Top year by allotment count
  const yearCounts = {};
  for (const r of FILTERED_ALLOTMENTS) yearCounts[r.year] = (yearCounts[r.year] || 0) + 1;
  const topYearEntry = Object.entries(yearCounts).sort((a, b) => b[1] - a[1])[0];
  const topYear = topYearEntry ? topYearEntry[0] : '—';
  const topYearCount = topYearEntry ? topYearEntry[1] : 0;

  document.querySelector('[data-skpi="total"]').textContent = fmtUSD(totalAllot);
  document.getElementById('skpi-total-sub').innerHTML = `across <strong>${new Set(FILTERED_ALLOTMENTS.map(r => r.year)).size}</strong> years`;

  document.querySelector('[data-skpi="appropriated"]').textContent = fmtUSD(totalAppro);
  document.getElementById('skpi-appropriated-sub').innerHTML = `<strong>${filteredAppro.length}</strong> annual acts`;

  document.querySelector('[data-skpi="count"]').textContent = FILTERED_ALLOTMENTS.length.toLocaleString();

  const revokeEl = document.querySelector('[data-skpi="revoke"]');
  revokeEl.innerHTML = `${revokeRate.toFixed(1)}<span class="unit">%</span>`;
  document.getElementById('skpi-revoke-sub').innerHTML = `<strong>${revokedCount}</strong> of ${FILTERED_ALLOTMENTS.length} returned`;

  document.querySelector('[data-skpi="topyear"]').textContent = topYear;
  document.getElementById('skpi-topyear-sub').innerHTML = topYearCount > 0 ? `<strong>${topYearCount}</strong> allotments` : '—';

  document.getElementById('s-match-n').textContent = FILTERED_ALLOTMENTS.length.toLocaleString();
  document.getElementById('s-match-sum').textContent = fmtUSD(totalAllot);
}

function renderSpendingTimeline() {
  const yearsAll = [];
  for (let y = SPENDING_FILTERS.yearMin; y <= SPENDING_FILTERS.yearMax; y++) yearsAll.push(y);

  const allotByYear = yearsAll.map(y =>
    FILTERED_ALLOTMENTS.filter(r => r.year === y).reduce((s, r) => s + r.amount, 0)
  );
  const approByYear = yearsAll.map(y => {
    const a = ALL_APPROPRIATIONS.find(r => r.year === y);
    return a ? a.amount : 0;
  });

  Plotly.react('s-chart-timeline', [
    {
      type: 'bar',
      name: 'Allotted',
      x: yearsAll,
      y: allotByYear,
      marker: { color: COLORS.accent, line: { width: 0 } },
      hovertemplate: '<b>%{x}</b><br>Allotted: %{y:$,.0f}<extra></extra>',
    },
    {
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Appropriated by Congress',
      x: yearsAll,
      y: approByYear,
      line: { color: COLORS.cyan, width: 2 },
      marker: { color: COLORS.cyan, size: 6 },
      hovertemplate: '<b>%{x}</b><br>Appropriated: %{y:$,.0f}<extra></extra>',
    },
  ], {
    ...PLOT_BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: 'h', x: 0, y: 1.16, font: { color: COLORS.textMid, size: 10 } },
    xaxis: { ...PLOT_AXIS, dtick: 2, title: '' },
    yaxis: { ...PLOT_AXIS, title: '', tickformat: '$.2s' },
    margin: { l: 64, r: 16, t: 36, b: 36 },
  }, PLOT_CONFIG);
}

function renderSpendingRevoked() {
  const active = FILTERED_ALLOTMENTS.filter(r => !r.revoked).reduce((s, r) => s + r.amount, 0);
  const revoked = FILTERED_ALLOTMENTS.filter(r => r.revoked).reduce((s, r) => s + r.amount, 0);
  const total = active + revoked;

  Plotly.react('s-chart-revoked', [{
    type: 'pie',
    hole: 0.62,
    labels: ['Active', 'Revoked'],
    values: [active, revoked],
    marker: { colors: [COLORS.accent, COLORS.red], line: { color: COLORS.bg, width: 1 } },
    textinfo: 'none',
    hovertemplate: '<b>%{label}</b><br>%{value:$,.0f} (%{percent})<extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    showlegend: true,
    legend: { orientation: 'v', x: 1.05, y: 0.5, font: { color: COLORS.textMid, size: 10 } },
    margin: { l: 6, r: 0, t: 6, b: 6 },
    annotations: [{
      text: `<b>${fmtUSD(total)}</b><br><span style="color:${COLORS.textMid};font-size:9px;letter-spacing:1.4px;">TOTAL</span>`,
      showarrow: false, font: { color: COLORS.text, size: 16, family: PLOT_FONT.family },
      x: 0.5, y: 0.5,
    }],
  }, PLOT_CONFIG);
}

function renderSpendingTop() {
  const top = [...FILTERED_ALLOTMENTS].sort((a, b) => b.amount - a.amount).slice(0, 15).reverse();
  const labels = top.map(r => {
    const desc = r.description.length > 60 ? r.description.slice(0, 60) + '…' : r.description;
    return `${r.year} · ${desc}`;
  });
  const values = top.map(r => r.amount);
  const colors = top.map(r => r.revoked ? COLORS.red : COLORS.accent);

  Plotly.react('s-chart-top', [{
    type: 'bar',
    orientation: 'h',
    x: values,
    y: labels,
    marker: { color: colors, line: { width: 0 } },
    text: values.map(v => fmtUSD(v)),
    textposition: 'outside',
    textfont: { color: COLORS.textMid, size: 10, family: PLOT_FONT.family },
    customdata: top.map(r => r.description),
    hovertemplate: '<b>%{customdata}</b><br>%{x:$,.0f}<extra></extra>',
  }], {
    ...PLOT_BASE_LAYOUT,
    xaxis: { ...PLOT_AXIS, tickformat: '$.2s', title: '' },
    yaxis: { ...PLOT_AXIS, automargin: true, tickfont: { ...PLOT_AXIS.tickfont, size: 9 } },
    margin: { l: 8, r: 56, t: 12, b: 36 },
  }, PLOT_CONFIG);
}

function renderSpendingTable() {
  const sorted = [...FILTERED_ALLOTMENTS].sort((a, b) => {
    let av = a[SPENDING_SORT.key], bv = b[SPENDING_SORT.key];
    if (SPENDING_SORT.key === 'revoked') { av = a.revoked ? 1 : 0; bv = b.revoked ? 1 : 0; }
    if (typeof av === 'number') return SPENDING_SORT.dir === 'asc' ? av - bv : bv - av;
    return SPENDING_SORT.dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  if (SPENDING_PAGE > totalPages) SPENDING_PAGE = 1;
  const start = (SPENDING_PAGE - 1) * PAGE_SIZE;
  const slice = sorted.slice(start, start + PAGE_SIZE);

  document.querySelectorAll('#s-records-table thead th').forEach(th => {
    th.classList.toggle('sorted', th.dataset.ssort === SPENDING_SORT.key);
    const ind = th.querySelector('.sort-ind');
    if (ind) ind.textContent = SPENDING_SORT.dir === 'asc' ? '▲' : '▼';
  });

  const tbody = document.getElementById('s-records-tbody');
  if (sorted.length === 0) {
    tbody.innerHTML = '';
    document.getElementById('s-records-empty').style.display = 'block';
    document.getElementById('s-records-table').style.display = 'none';
  } else {
    document.getElementById('s-records-empty').style.display = 'none';
    document.getElementById('s-records-table').style.display = '';
    tbody.innerHTML = slice.map(r => `
      <tr title="${escapeHTML(r.description)}${r.notes ? ' | Notes: ' + escapeHTML(r.notes) : ''}">
        <td class="col-year">${r.year}</td>
        <td class="col-subject">${escapeHTML(r.description.length > 80 ? r.description.slice(0, 80) + '…' : r.description)}</td>
        <td class="col-proposer">${fmtUSD(r.amount)}</td>
        <td class="col-cluster">${escapeHTML(r.dateAllotted)}</td>
        <td class="col-status">${r.revoked
          ? `<span class="badge b-rejected">REVOKED</span>`
          : `<span class="badge b-approved">ACTIVE</span>`}</td>
      </tr>
    `).join('');
  }

  if (sorted.length > 0) {
    document.getElementById('s-rec-range').textContent = `${start + 1}–${Math.min(start + PAGE_SIZE, sorted.length)}`;
  } else {
    document.getElementById('s-rec-range').textContent = '0';
  }
  document.getElementById('s-rec-total').textContent = sorted.length.toLocaleString();

  renderSpendingPager(totalPages);
}

function renderSpendingPager(totalPages) {
  const pager = document.getElementById('s-pager');
  if (totalPages <= 1) { pager.innerHTML = ''; return; }
  const buttons = [];
  buttons.push(`<button id="s-pg-prev" ${SPENDING_PAGE === 1 ? 'disabled' : ''}>‹ prev</button>`);
  const pages = new Set([1, totalPages, SPENDING_PAGE - 1, SPENDING_PAGE, SPENDING_PAGE + 1]);
  const sortedPages = [...pages].filter(p => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  let last = 0;
  for (const p of sortedPages) {
    if (last && p - last > 1) buttons.push('<span style="color:var(--text-soft);padding:0 4px;">…</span>');
    buttons.push(`<button data-spage="${p}" class="${p === SPENDING_PAGE ? 'active' : ''}">${p}</button>`);
    last = p;
  }
  buttons.push(`<button id="s-pg-next" ${SPENDING_PAGE === totalPages ? 'disabled' : ''}>next ›</button>`);
  buttons.push(`<span class="pg-info">page ${SPENDING_PAGE} of ${totalPages}</span>`);
  pager.innerHTML = buttons.join('');
  pager.querySelectorAll('button[data-spage]').forEach(b => b.addEventListener('click', () => { SPENDING_PAGE = parseInt(b.dataset.spage, 10); renderSpendingTable(); }));
  const prev = document.getElementById('s-pg-prev'); if (prev) prev.addEventListener('click', () => { SPENDING_PAGE = Math.max(1, SPENDING_PAGE - 1); renderSpendingTable(); });
  const next = document.getElementById('s-pg-next'); if (next) next.addEventListener('click', () => { SPENDING_PAGE = Math.min(totalPages, SPENDING_PAGE + 1); renderSpendingTable(); });
}

function exportSpendingCSV() {
  if (FILTERED_ALLOTMENTS.length === 0) { toast('Nothing to export'); return; }
  const headers = ['year', 'description', 'amount', 'dateAllotted', 'revoked', 'dateRevoked', 'page', 'notes'];
  const rows = FILTERED_ALLOTMENTS.map(r => [
    r.year, r.description, r.amount, r.dateAllotted, r.revoked ? 'Yes' : 'No', r.dateRevoked, r.page, r.notes
  ].map(v => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`).join(','));
  const csv = headers.join(',') + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `bof-allotments-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast(`Exported ${FILTERED_ALLOTMENTS.length} allotments`);
}

function resizeSpendingCharts() {
  requestAnimationFrame(() => {
    ['s-chart-timeline', 's-chart-revoked', 's-chart-top'].forEach(id => {
      const el = document.getElementById(id);
      if (el && el._fullLayout) {
        try { Plotly.Plots.resize(el); } catch {}
      }
    });
  });
}

// ── View tabs ─────────────────────────────────────────────────────────
function wireViewTabs() {
  document.querySelectorAll('.view-tab').forEach(btn => {
    btn.addEventListener('click', () => setView(btn.dataset.view));
  });
}

let TIMELINE_RENDERED = false;

function setView(name) {
  if (!['proposals', 'budget', 'timeline', 'spending'].includes(name)) name = 'proposals';
  VIEW = name;
  document.getElementById('view-proposals').hidden = (name !== 'proposals');
  document.getElementById('view-budget').hidden    = (name !== 'budget');
  document.getElementById('view-timeline').hidden  = (name !== 'timeline');
  document.getElementById('view-spending').hidden  = (name !== 'spending');
  document.querySelectorAll('.view-tab').forEach(b => {
    const active = b.dataset.view === name;
    b.classList.toggle('active', active);
    b.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  requestAnimationFrame(() => {
    if (name === 'budget' && !BUDGET_RENDERED) {
      applyBudget();
      BUDGET_RENDERED = true;
    } else if (name === 'budget') {
      resizeBudgetCharts();
    } else if (name === 'timeline' && !TIMELINE_RENDERED) {
      applyTimeline();
      TIMELINE_RENDERED = true;
    } else if (name === 'spending' && !SPENDING_RENDERED) {
      applySpending();
      SPENDING_RENDERED = true;
    } else if (name === 'spending') {
      resizeSpendingCharts();
    } else if (name === 'proposals') {
      resizeCharts();
    }
  });
  updateHash();
}

// ── Boot ──────────────────────────────────────────────────────────────
load().catch(e => {
  console.error(e);
  document.querySelectorAll('.loading').forEach(el => {
    el.textContent = 'LOAD FAILED — serve over HTTP, not file://';
    el.style.color = COLORS.red;
  });
});
