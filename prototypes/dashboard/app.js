/* BOF Terminal — live filterable dashboard with cross-filtering, search,
 * presets, paginated records table, detail modal, URL state sync, CSV export.
 * No build step.
 */

const CSV_URL = '../../output/all_structured_records.csv';

const THEMES = {
  terminal: {
    bg: '#0F141C', panel: '#0F141C', border: '#1B2330',
    text: '#E6ECF3', textMid: '#8B95A4', textSoft: '#525C6B',
    accent: '#4DE685', amber: '#FFB347', red: '#FF6F6F',
    cyan: '#5BBCFF', magenta: '#C77DFF',
    cluster: {
      'Artillery':                      '#5BBCFF',
      'Explosives':                     '#C77DFF',
      'Small Arms':                     '#4DE685',
      'Armor and Protection':           '#FFB347',
      'Fortification and Engineering':  '#7DDFC0',
      'Communications and Observation': '#94A9FF',
      'Logistics and Support':          '#D88C8C',
      'Other/Unclassified':             '#8B95A4',
    },
    fontFamily: "'JetBrains Mono', 'SF Mono', Menlo, monospace",
  },
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
  broadsheet: {
    bg: '#FBF8F1', panel: '#FBF8F1', border: '#D4CCBC',
    text: '#1A1A1A', textMid: '#5A554C', textSoft: '#888073',
    accent: '#8B1A1A', amber: '#A88A3D', red: '#8B1A1A',
    cyan: '#1B4F72', magenta: '#6E3A82',
    cluster: {
      'Artillery':                      '#1B4F72',
      'Explosives':                     '#6E3A82',
      'Small Arms':                     '#2D6A4F',
      'Armor and Protection':           '#A88A3D',
      'Fortification and Engineering':  '#4D7C5F',
      'Communications and Observation': '#3A5683',
      'Logistics and Support':          '#8B3A3A',
      'Other/Unclassified':             '#7A7268',
    },
    fontFamily: "'Source Serif 4', Georgia, serif",
  },
};

let CURRENT_THEME = 'terminal';
let COLORS = THEMES.terminal;
let STATUS_COLOR = makeStatusColor(COLORS);
let CLUSTER_COLOR = COLORS.cluster;
let PLOT_FONT = makePlotFont(COLORS);

function makeStatusColor(c) {
  return {
    Approved:      c.accent === '#8B1A1A' ? '#2D6A4F' : c.accent,
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
  const resp = await fetch(CSV_URL);
  const text = await resp.text();
  const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
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
    .filter(r => r.year >= 1897 && r.year <= 1908);

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

  document.getElementById('rec-count').textContent = ALL.length.toLocaleString();
  buildTicker();
  computePresetCounts();
  stateFromHash();
  apply();
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
  FILTERS = { yearMin: 1897, yearMax: 1908, cluster: '', status: '', proposer: '', search: '' };
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
}

// ── Active filter chips ───────────────────────────────────────────────
function renderActiveChips() {
  const chips = [];
  if (FILTERS.yearMin !== 1897 || FILTERS.yearMax !== 1908) {
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
  CLICK_ATTACHED.add(divId);
  const el = document.getElementById(divId);
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
  if (FILTERS.yearMin !== 1897 || FILTERS.yearMax !== 1908) params.set('y', `${FILTERS.yearMin}-${FILTERS.yearMax}`);
  if (FILTERS.cluster)  params.set('c', FILTERS.cluster);
  if (FILTERS.status)   params.set('s', FILTERS.status);
  if (FILTERS.proposer) params.set('p', FILTERS.proposer);
  if (FILTERS.search)   params.set('q', FILTERS.search);
  const h = params.toString();
  history.replaceState(null, '', h ? '#' + h : window.location.pathname);
}

function stateFromHash() {
  if (!window.location.hash) return;
  const params = new URLSearchParams(window.location.hash.slice(1));
  if (params.has('y')) {
    const [a, b] = params.get('y').split('-').map(Number);
    if (Number.isFinite(a) && Number.isFinite(b)) { FILTERS.yearMin = a; FILTERS.yearMax = b; }
  }
  if (params.has('c')) FILTERS.cluster = params.get('c');
  if (params.has('s')) FILTERS.status  = params.get('s');
  if (params.has('p')) FILTERS.proposer = params.get('p');
  if (params.has('q')) FILTERS.search   = params.get('q');
  syncFilterControls();
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

// ── Boot ──────────────────────────────────────────────────────────────
load().catch(e => {
  console.error(e);
  document.querySelectorAll('.loading').forEach(el => {
    el.textContent = 'LOAD FAILED — serve over HTTP, not file://';
    el.style.color = COLORS.red;
  });
});
