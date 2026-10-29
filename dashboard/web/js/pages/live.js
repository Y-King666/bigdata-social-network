const TEMPLATE = `
<div class="live-page" id="stage">
  <div class="live-head-row">
    <div class="page-head live-head">
      <h1>实时监测</h1>
      <p>逐分钟回放：1× 每秒推进 1 个模拟分钟，2× / 5× / 10× 倍速；60 分钟滚动窗口。</p>
    </div>
    <div class="live-actions">
      <div class="live-state">
        <span id="phaseDot" class="phase-dot"></span>
        <span id="phaseText">连接中</span>
        <span class="live-sep"></span>
        <span id="simDate" class="sim-date">等待数据</span>
      </div>
      <div class="live-controls" id="liveControls">
        <div class="seg" id="speedGroup" aria-label="回放倍速">
          <button type="button" data-speed="1">1×</button>
          <button type="button" data-speed="2">2×</button>
          <button type="button" data-speed="5">5×</button>
          <button type="button" data-speed="10">10×</button>
        </div>
        <button type="button" id="pauseBtn" class="btn ghost live-btn">暂停</button>
        <button type="button" id="resetBtn" class="btn ghost live-btn reset">重置</button>
        <button type="button" id="fullBtn" class="btn ghost live-btn">全屏</button>
      </div>
    </div>
  </div>
  <div class="page-rule live-rule"></div>

  <section class="kpis live-kpis">
    <article class="kpi live-kpi">
      <div class="kpi-label">模拟时间 <em>北京时间</em></div>
      <div class="kpi-value"><strong id="kpiTime">--:--</strong></div>
      <div class="kpi-hint" id="kpiDate">等待数据</div>
    </article>
    <article class="kpi live-kpi">
      <div class="kpi-label">实时速率 <em>最近一分钟</em></div>
      <div class="kpi-value"><strong id="kpiRate">N/A</strong><span class="live-unit">条 / 分</span></div>
      <div class="kpi-hint" id="kpiRateSub">等待分钟数据</div>
    </article>
    <article class="kpi live-kpi">
      <div class="kpi-label">累计事件 <em>自本次起点</em></div>
      <div class="kpi-value"><strong id="kpiTotal">0</strong><span class="live-unit">条</span></div>
    </article>
    <article class="kpi live-kpi">
      <div class="kpi-label">累计告警 <em>规则命中</em></div>
      <div class="kpi-value"><strong id="kpiAlerts">0</strong><span class="live-unit">条</span></div>
      <div class="kpi-hint" id="kpiAlertSub">暂无告警</div>
    </article>
  </section>

  <section class="live-main-grid">
    <article class="panel live-chart-panel">
      <div class="panel-head">
        <h2>逐分钟发帖速率</h2>
        <div class="legend">
          <span class="legend-item"><i class="swatch bar"></i>发帖量</span>
          <span class="legend-item"><i class="swatch line"></i>正面占比</span>
        </div>
        <span class="panel-meta">最近 60 分钟</span>
      </div>
      <div class="canvas-wrap">
        <canvas id="mainChart"></canvas>
        <div id="mainEmpty" class="empty-overlay">
          <span>等待分钟数据</span>
          <small>重置后从 2020-01-22 00:00:00 开始</small>
        </div>
      </div>
    </article>

    <article class="panel live-chart-panel">
      <div class="panel-head">
        <h2>情感构成</h2>
        <div class="legend sentiment-legend">
          <span class="legend-item"><i class="swatch pos"></i>正面 <b id="sentPos">N/A</b></span>
          <span class="legend-item"><i class="swatch neu"></i>中性 <b id="sentNeu">N/A</b></span>
          <span class="legend-item"><i class="swatch neg"></i>负面 <b id="sentNeg">N/A</b></span>
        </div>
        <span class="panel-meta">100% 堆叠</span>
      </div>
      <div class="canvas-wrap">
        <canvas id="sentChart"></canvas>
        <div id="sentEmpty" class="empty-overlay">
          <span>等待分钟数据</span>
          <small>正面 / 中性 / 负面占比</small>
        </div>
      </div>
    </article>
  </section>

  <section class="live-bottom-grid">
    <article class="panel live-rank-panel">
      <div class="panel-head"><h2>热点话题</h2><span class="panel-meta">60 分钟滚动 Top 10</span></div>
      <div id="topicRank" class="rank-list"></div>
      <div id="topicEmpty" class="empty-note live-empty">暂无话题数据</div>
    </article>

    <article class="panel live-rank-panel">
      <div class="panel-head"><h2>地域分布</h2><span class="panel-meta">按用户省份 · 60 分钟</span></div>
      <div id="regionRank" class="rank-list"></div>
      <div id="regionEmpty" class="empty-note live-empty">暂无地域数据</div>
    </article>

    <article class="panel live-table-panel">
      <div class="panel-head"><h2>逐分钟数据</h2></div>
      <div class="table-head live-table-head">
        <span>时间</span><span class="num">发帖</span><span class="num">正面</span>
        <span class="num">负面</span><span class="num">中性</span><span class="num">转发</span>
        <span>热门话题</span>
      </div>
      <div id="tableViewport" class="table-viewport">
        <div id="tableBody" class="table-body"></div>
      </div>
      <div id="tableEmpty" class="empty-note live-empty">等待分钟数据</div>
    </article>
  </section>

  <section class="alerts-strip live-alerts">
    <div class="alerts-title">
      <span class="pulse-dot"></span>
      <span>实时告警</span>
      <b id="alertCount">0</b>
    </div>
    <div id="alertsList" class="alerts-list"></div>
  </section>

  <footer class="statusline live-status">
    <span id="statusLeft">正在连接大屏后端…</span>
    <span id="statusRight">逐分钟聚合 · 60 分钟滚动窗口</span>
  </footer>
</div>

<div id="resetModal" class="live-modal hidden" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
  <div class="live-modal-backdrop" data-close="1"></div>
  <div class="live-modal-card">
    <div class="live-modal-kicker">RESET THE CLOCK</div>
    <h3 id="modalTitle">确认重置监测大屏？</h3>
    <p>所有图表、排行榜与逐分钟数据将归零，坐标轴清空；随后从 <b>2020-01-22 00:00</b> 重新开始逐分钟回放。</p>
    <div class="live-modal-actions">
      <button type="button" id="modalCancel" class="btn ghost live-btn">取消</button>
      <button type="button" id="modalConfirm" class="btn live-btn danger">确认重置</button>
    </div>
  </div>
</div>

<div id="toast" class="toast hidden"></div>
`;

// 逐分钟监测大屏：Canvas 主图 + 竞速式排行榜 + 传送带式分钟表。

export function mount(root) {
  root.innerHTML = TEMPLATE;

  const $ = function (id) { return root.querySelector('#' + id); };
  const stage = $('stage');
  const phaseDot = $('phaseDot');
  const phaseText = $('phaseText');
  const simDate = $('simDate');
  const speedGroup = $('speedGroup');
  const pauseBtn = $('pauseBtn');
  const resetBtn = $('resetBtn');
  const fullBtn = $('fullBtn');
  const kpiTime = $('kpiTime');
  const kpiDate = $('kpiDate');
  const kpiRate = $('kpiRate');
  const kpiTotal = $('kpiTotal');
  const kpiAlerts = $('kpiAlerts');
  const kpiRateSub = $('kpiRateSub');
  const kpiAlertSub = $('kpiAlertSub');
  const mainChart = $('mainChart');
  const sentChart = $('sentChart');
  const mainEmpty = $('mainEmpty');
  const sentEmpty = $('sentEmpty');
  const sentPos = $('sentPos');
  const sentNeu = $('sentNeu');
  const sentNeg = $('sentNeg');
  const topicRankEl = $('topicRank');
  const regionRankEl = $('regionRank');
  const topicEmpty = $('topicEmpty');
  const regionEmpty = $('regionEmpty');
  const tableBody = $('tableBody');
  const tableViewport = $('tableViewport');
  const tableEmpty = $('tableEmpty');
  const alertsList = $('alertsList');
  const alertCount = $('alertCount');
  const statusLeft = $('statusLeft');
  const statusRight = $('statusRight');
  const resetModal = $('resetModal');
  const modalConfirm = $('modalConfirm');
  const modalCancel = $('modalCancel');
  const toast = $('toast');

  const WINDOW_MINUTES = 60;
  const WINDOW_SECONDS = WINDOW_MINUTES * 60;
  const MINUTE_SECONDS = 60;
  const TABLE_VISIBLE = 16;
  const RANK_ROWS = 10;
  const DEFAULT_START_TS = Date.UTC(2020, 0, 22, 0, 0, 0) / 1000;
  const POLL_MS = 550;

  let disposed = false;
  let pollTimer = null;
  let rafId = 0;
  let resizeRaf = 0;
  let pollAbort = null;

  function onResize() {
    if (disposed) return;
    if (resizeRaf) cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(function () {
      resizeCanvases();
      initMetrics();
      renderTable(true);
    });
  }

  function onKey(ev) {
    if (ev.key === 'Escape' && !resetModal.classList.contains('hidden')) closeModal();
  }

  function onFullscreen() {
    fullBtn.textContent = document.fullscreenElement ? '退出全屏' : '全屏';
    onResize();
  }

  const resizeObserver = typeof ResizeObserver === 'function' ? new ResizeObserver(onResize) : null;
const state = {
  snapshot: null,
  runId: null,
  startTs: DEFAULT_START_TS,
  phase: 'connecting',
  speed: 1,
  paused: false,
  displayTime: DEFAULT_START_TS,
  targetTime: DEFAULT_START_TS,
  data: new Map(),
  latestT: null,
  chartYMax: 10,
  tableT: null,
  tableRowH: 21,
  alerts: [],
  alertsSig: '',
  online: null,
  pollBusy: false,
  lastFrame: 0,
  toastTimer: null,
};

/* ---------- formatting ---------- */

function pad2(n) { return n < 10 ? '0' + n : String(n); }

function fmtMinute(epoch) {
  if (epoch === null || epoch === undefined || !Number.isFinite(Number(epoch))) return '--:--';
  const d = new Date(Number(epoch) * 1000);
  return pad2(d.getUTCHours()) + ':' + pad2(d.getUTCMinutes());
}

function fmtDate(epoch) {
  if (epoch === null || epoch === undefined || !Number.isFinite(Number(epoch))) return '--';
  const d = new Date(Number(epoch) * 1000);
  return d.getUTCFullYear() + '-' + pad2(d.getUTCMonth() + 1) + '-' + pad2(d.getUTCDate());
}

function fmtInt(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '0';
  return Math.round(n).toLocaleString('zh-CN');
}

function fmtCompact(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return '0';
  if (n >= 100000000) return (n / 100000000).toFixed(2) + ' 亿';
  if (n >= 10000) return (n / 10000).toFixed(1) + ' 万';
  return Math.round(n).toLocaleString('zh-CN');
}

function fmtPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 'N/A';
  return (n * 100).toFixed(1) + '%';
}

function fmtAge(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return '--';
  return n < 10 ? n.toFixed(1) + 's' : Math.round(n) + 's';
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (ch) {
    if (ch === '&') return '&amp;';
    if (ch === '<') return '&lt;';
    if (ch === '>') return '&gt;';
    if (ch === '"') return '&quot;';
    return '&#39;';
  });
}

/* ---------- stage / canvas ---------- */

function resizeCanvas(canvas) {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
}

function resizeCanvases() {
  resizeCanvas(mainChart);
  resizeCanvas(sentChart);
}

/* ---------- rank animation ---------- */

class Ranker {
  constructor(el, emptyEl, maxRows) {
    this.el = el;
    this.emptyEl = emptyEl;
    this.maxRows = maxRows;
    this.items = new Map();
    this.rowH = 32;
    this.el.innerHTML = '';
  }

  setRowHeight(h) {
    if (h > 12) this.rowH = h;
  }

  clear() {
    this.items.clear();
    this.el.innerHTML = '';
    this.emptyEl.classList.remove('hidden');
  }

  update(list) {
    if (!list || !list.length) {
      this.clear();
      return;
    }
    this.emptyEl.classList.add('hidden');
    const now = performance.now();
    const maxCount = Math.max(1, ...list.map(function (x) { return Number(x.count) || 0; }));
    const seen = new Set();

    list.forEach((entry, index) => {
      const key = String(entry.key || '');
      if (!key) return;
      seen.add(key);
      let item = this.items.get(key);
      if (!item) {
        item = this.createItem(key, entry, index, now);
        this.items.set(key, item);
      } else {
        const prevRank = item.rank;
        if (index !== prevRank) {
          item.delta = prevRank - index;
          item.deltaUntil = now + 2400;
        }
        item.rank = index;
        item.targetRank = index;
        item.count = Number(entry.count) || 0;
        item.leaving = false;
        item.leaveAt = 0;
        item.opacity = 1;
      }
      item.targetWidth = Math.max(0, Math.min(1, item.count / maxCount));
      this.paintItem(item, index, now);
    });

    for (const [key, item] of Array.from(this.items.entries())) {
      if (!seen.has(key)) {
        item.leaving = true;
        item.targetRank = this.maxRows;
        item.opacity = 0;
      }
    }
    this.cleanup(now);
  }

  createItem(key, entry, index, now) {
    const el = document.createElement('div');
    el.className = 'rank-row';
    el.innerHTML = '<span class="rank-no"></span><span class="rank-name"></span>' +
      '<span class="rank-delta"></span><span class="rank-bar"><i></i></span><span class="rank-count"></span>';
    el.style.top = '0px';
    el.style.height = Math.max(14, this.rowH - 4) + 'px';
    el.style.opacity = '0';
    this.el.appendChild(el);
    return {
      key: key,
      el: el,
      rank: index,
      targetRank: index,
      y: this.maxRows * this.rowH,
      vy: 0,
      count: Number(entry.count) || 0,
      width: 0,
      targetWidth: 0,
      delta: 0,
      deltaUntil: 0,
      leaving: false,
      leaveAt: 0,
      opacity: 0,
      born: now,
    };
  }

  paintItem(item, index, now) {
    const row = item.el;
    row.classList.toggle('top1', index === 0);
    row.classList.toggle('top2', index === 1);
    row.classList.toggle('top3', index === 2);

    const no = row.querySelector('.rank-no');
    if (no) no.textContent = String(index + 1);

    const name = row.querySelector('.rank-name');
    if (name) {
      name.textContent = item.key;
      name.title = item.key;
    }

    const count = row.querySelector('.rank-count');
    if (count) count.textContent = fmtInt(item.count);

    const delta = row.querySelector('.rank-delta');
    if (delta) {
      let text = '';
      let cls = 'rank-delta';
      if (now < item.deltaUntil && item.delta) {
        if (item.delta > 0) {
          text = '▲' + item.delta;
          cls += ' up';
        } else {
          text = '▼' + Math.abs(item.delta);
          cls += ' down';
        }
      } else if (item.born && now - item.born < 1500) {
        text = 'NEW';
        cls += ' new';
      }
      delta.textContent = text;
      delta.className = cls;
    }
  }

  step(dt) {
    if (!this.items.size) return;
    const now = performance.now();
    const rowH = this.rowH;
    const k = 95;
    const damp = 24;
    const active = [];

    for (const item of this.items.values()) {
      const target = item.targetRank * rowH;
      const ay = (target - item.y) * k - item.vy * damp;
      item.vy += ay * dt;
      item.vy = Math.max(-900, Math.min(900, item.vy));
      item.y += item.vy * dt;
      item.width += (item.targetWidth - item.width) * Math.min(1, dt * 9);
      if (item.leaving) {
        item.opacity += (0 - item.opacity) * Math.min(1, dt * 8);
        if (!item.leaveAt) item.leaveAt = now;
      } else {
        item.opacity += (1 - item.opacity) * Math.min(1, dt * 10);
        active.push(item);
      }
    }

    active.sort(function (a, b) { return a.targetRank - b.targetRank; });
    for (let pass = 0; pass < 2; pass++) {
      for (let i = 0; i < active.length - 1; i++) {
        const a = active[i];
        const b = active[i + 1];
        const gap = b.y - a.y;
        const minGap = rowH * 0.94;
        if (gap < minGap) {
          const fix = (minGap - gap) * 0.18;
          a.y -= fix;
          b.y += fix;
        }
      }
    }

    for (const item of this.items.values()) {
      if (item.leaving) {
        item.y += (this.maxRows * rowH + rowH - item.y) * Math.min(1, dt * 3);
      }
      if (item.y < -rowH * 1.2) {
        item.y = -rowH * 1.2;
        if (item.vy < 0) item.vy = 0;
      }
      if (item.y > this.maxRows * rowH + rowH) {
        item.y = this.maxRows * rowH + rowH;
        if (item.vy > 0) item.vy = 0;
      }

      const speed = Math.max(-1, Math.min(1, item.vy / 700));
      const sy = 1 + Math.abs(speed) * 0.07;
      const sx = 1 - Math.abs(speed) * 0.035;
      const el = item.el;
      el.style.transform = 'translate3d(0,' + item.y.toFixed(2) + 'px,0) scale(' + sx.toFixed(3) + ',' + sy.toFixed(3) + ')';
      el.style.zIndex = String(100 - item.targetRank);
      el.style.opacity = item.opacity.toFixed(3);
      el.style.height = Math.max(14, rowH - 4) + 'px';

      const bar = el.querySelector('.rank-bar i');
      if (bar) bar.style.width = (Math.max(0, Math.min(1, item.width)) * 100).toFixed(1) + '%';

      const delta = el.querySelector('.rank-delta');
      if (delta && item.deltaUntil && now > item.deltaUntil && !item.leaving) {
        item.delta = 0;
        item.deltaUntil = 0;
        delta.textContent = '';
        delta.className = 'rank-delta';
      }
    }

    this.cleanup(now);
  }

  cleanup(now) {
    for (const [key, item] of Array.from(this.items.entries())) {
      if (item.leaving && (!item.leaveAt || now - item.leaveAt > 1200 || item.opacity < 0.03)) {
        item.el.remove();
        this.items.delete(key);
      }
    }
  }
}

const topicRanker = new Ranker(topicRankEl, topicEmpty, RANK_ROWS);
const regionRanker = new Ranker(regionRankEl, regionEmpty, RANK_ROWS);

function initMetrics() {
  const rh = (topicRankEl.clientHeight || 350) / RANK_ROWS;
  topicRanker.setRowHeight(rh);
  regionRanker.setRowHeight(rh);
  state.tableRowH = (tableViewport.clientHeight || 330) / TABLE_VISIBLE;
  tableBody.style.height = (state.tableRowH * (TABLE_VISIBLE + 1)).toFixed(2) + 'px';
  renderTable(true);
}

/* ---------- table ---------- */

function renderTable(force) {
  const t = Math.floor((state.displayTime || state.startTs || DEFAULT_START_TS) / MINUTE_SECONDS) * MINUTE_SECONDS;
  if (!force && state.tableT === t) return;
  state.tableT = t;
  const rowH = state.tableRowH;
  const hasAny = state.data.size > 0 || state.latestT !== null;
  const start = Math.floor((state.startTs || DEFAULT_START_TS) / MINUTE_SECONDS) * MINUTE_SECONDS;
  const parts = [];

  for (let i = 0; i < TABLE_VISIBLE + 1; i++) {
    const minute = t - (TABLE_VISIBLE - 1 - i) * MINUTE_SECONDS;
    const d = state.data.get(minute);
    const atStart = minute >= start;
    const known = atStart && (!!d || (state.latestT !== null && minute <= state.latestT));
    const time = hasAny && atStart ? fmtMinute(minute) : '--:--';
    const cls = 'table-row' +
      (d && minute === t && known ? ' latest' : '') +
      (!known ? ' pending' : '');
    const posts = known ? fmtInt(d ? d.posts : 0) : 'N/A';
    const pos = known ? fmtInt(d ? d.positive : 0) : 'N/A';
    const neg = known ? fmtInt(d ? d.negative : 0) : 'N/A';
    const neu = known ? fmtInt(d ? d.neutral : 0) : 'N/A';
    const rep = known ? fmtInt(d ? d.reposts : 0) : 'N/A';
    const topic = known ? escapeHtml(d && d.top_topic ? d.top_topic : '—') : 'N/A';
    const topicTitle = known && d && d.top_topic ? ' title="' + escapeHtml(d.top_topic) + '"' : '';

    parts.push(
      '<div class="' + cls + '" style="top:' + (i * rowH).toFixed(2) + 'px;height:' + rowH.toFixed(2) + 'px">' +
        '<span class="cell time">' + time + '</span>' +
        '<span class="cell num">' + posts + '</span>' +
        '<span class="cell num pos">' + pos + '</span>' +
        '<span class="cell num neg">' + neg + '</span>' +
        '<span class="cell num neu">' + neu + '</span>' +
        '<span class="cell num">' + rep + '</span>' +
        '<span class="cell topic"' + topicTitle + '>' + topic + '</span>' +
      '</div>'
    );
  }

  tableBody.innerHTML = parts.join('');
  tableBody.style.height = (rowH * (TABLE_VISIBLE + 1)).toFixed(2) + 'px';
  applyTableTransform();
}

function applyTableTransform() {
  const phase = (((state.displayTime || 0) % MINUTE_SECONDS) + MINUTE_SECONDS) % MINUTE_SECONDS / MINUTE_SECONDS;
  const y = -phase * state.tableRowH;
  tableBody.style.transform = 'translate3d(0,' + y.toFixed(2) + 'px,0)';
}

function updateTable() {
  const t = Math.floor((state.displayTime || state.startTs) / MINUTE_SECONDS) * MINUTE_SECONDS;
  if (state.tableT !== t) renderTable(false);
  applyTableTransform();
}

/* ---------- alerts ---------- */

function alertValueText(alert) {
  if (String(alert.type || '').indexOf('负面') >= 0) return fmtPct(alert.value);
  return fmtInt(alert.value) + ' 条';
}

function alertBaselineText(alert) {
  if (String(alert.type || '').indexOf('负面') >= 0) return fmtPct(alert.baseline);
  return fmtInt(alert.baseline) + ' 条';
}

function renderAlerts(force) {
  const alerts = state.alerts || [];
  alertCount.textContent = String(alerts.length);
  const signature = JSON.stringify(alerts.map(function (a) {
    return [a.id, a.status, a.value, a.baseline, a.t];
  }));
  if (!force && signature === state.alertsSig) return;
  state.alertsSig = signature;

  if (!alerts.length) {
    alertsList.innerHTML = '<div class="alerts-empty"><span class="pulse-dot"></span>暂无告警 · 规则监测中</div>';
    return;
  }

  const cards = alerts.slice(0, 4).map(function (a) {
    const status = a.status || '新';
    const statusCls = status === '已确认' ? 's-acked' : (status === '已忽略' ? 's-ignored' : 's-new');
    const level = String(a.level || '');
    const levelCls = level.indexOf('高') >= 0 ? 'l-high' : (level.indexOf('中') >= 0 ? 'l-mid' : 'l-low');
    const id = escapeHtml(a.id);
    let actions = '';
    if (status === '新') {
      actions = '<div class="alert-actions">' +
        '<button type="button" class="ack-btn" data-ack="已确认" data-id="' + id + '">确认</button>' +
        '<button type="button" class="ack-btn ignore" data-ack="已忽略" data-id="' + id + '">忽略</button>' +
        '</div>';
    }
    return '<div class="alert-card ' + statusCls + ' ' + levelCls + '">' +
      '<div class="alert-top">' +
        '<span class="alert-type">' + escapeHtml(a.type) + '</span>' +
        '<span class="alert-time">' + fmtMinute(a.t) + '</span>' +
        '<span class="alert-status">' + escapeHtml(status) + '</span>' +
      '</div>' +
      '<div class="alert-main">' +
        '<span class="alert-key" title="' + escapeHtml(a.key) + '">' + escapeHtml(a.key) + '</span>' +
        '<span class="alert-value">' + alertValueText(a) + '</span>' +
      '</div>' +
      '<div class="alert-bottom"><span>基线 ' + alertBaselineText(a) + '</span>' + actions + '</div>' +
    '</div>';
  }).join('');

  alertsList.innerHTML = cards;
}

function ackAlert(id, status) {
  const alert = state.alerts.find(function (a) { return a.id === id; });
  if (!alert) return;
  const old = alert.status;
  alert.status = status;
  state.alertsSig = '';
  renderAlerts(true);
  postJson('/api/ack', { id: id, status: status }).catch(function () {
    alert.status = old;
    state.alertsSig = '';
    renderAlerts(true);
    showToast('告警状态写入失败，请重试', true);
  });
}

/* ---------- charts ---------- */

function chartFont(ctx, size) {
  ctx.font = size + 'px "Microsoft YaHei", "PingFang SC", sans-serif';
}

function getChartWindow(now) {
  const start = Math.floor((state.startTs || DEFAULT_START_TS) / MINUTE_SECONDS) * MINUTE_SECONDS;
  if (now - start < WINDOW_SECONDS) {
    return { lo: start, hi: start + WINDOW_SECONDS, span: WINDOW_SECONDS };
  }
  return { lo: now - WINDOW_SECONDS, hi: now, span: WINDOW_SECONDS };
}

function drawMain() {
  const canvas = mainChart;
  const ctx = canvas.getContext('2d');
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  const pscale = canvas.width / w;
  ctx.setTransform(pscale, 0, 0, pscale, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const L = 48, R = 52, T = 20, B = 26;
  const pw = w - L - R;
  const ph = h - T - B;
  if (pw <= 0 || ph <= 0) return;
  const base = T + ph;
  const now = state.displayTime || state.startTs || DEFAULT_START_TS;
  const win = getChartWindow(now);
  const lo = win.lo;
  const hi = win.hi;
  const first = Math.floor(lo / MINUTE_SECONDS) * MINUTE_SECONDS;
  const last = Math.ceil(hi / MINUTE_SECONDS) * MINUTE_SECONDS;
  const px = pw / win.span;
  const xOf = function (t) { return L + ((t - lo) / win.span) * pw; };

  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {
    const y = T + ph * i / 5;
    ctx.strokeStyle = i === 5 ? '#dfe3e9' : '#eef0f3';
    ctx.beginPath();
    ctx.moveTo(L, y);
    ctx.lineTo(L + pw, y);
    ctx.stroke();
  }

  for (let k = 0; k <= 4; k++) {
    const vt = lo + win.span * k / 4;
    const x = xOf(vt);
    if (x < L || x > L + pw) continue;
    ctx.strokeStyle = '#f3f5f8';
    ctx.beginPath();
    ctx.moveTo(x, T);
    ctx.lineTo(x, base);
    ctx.stroke();
  }

  let maxPosts = 0;
  for (let t = first; t <= last; t += MINUTE_SECONDS) {
    const d = state.data.get(t);
    if (d && d.posts > maxPosts) maxPosts = d.posts;
  }
  const targetMax = Math.max(10, maxPosts * 1.18);
  state.chartYMax += (targetMax - state.chartYMax) * 0.12;
  const unit = state.chartYMax < 250 ? 10 : 25;
  const step = Math.max(1, Math.ceil(state.chartYMax / 5 / unit) * unit);
  const yMax = step * 5;

  chartFont(ctx, 9);
  ctx.fillStyle = '#6b7280';
  ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    ctx.fillText(String(step * (5 - i)), L - 8, T + ph * i / 5 + 3);
  }
  ctx.textAlign = 'left';
  for (let i = 0; i <= 5; i++) {
    ctx.fillText((100 - i * 20) + '%', L + pw + 8, T + ph * i / 5 + 3);
  }

  const bw = Math.max(2, px * MINUTE_SECONDS * 0.62);
  for (let t = first; t <= last; t += MINUTE_SECONDS) {
    const d = state.data.get(t);
    if (!d) continue;
    const x = xOf(t + MINUTE_SECONDS / 2);
    if (x < L - 2 || x > L + pw + 2) continue;
    const bh = (d.posts / yMax) * ph;
    if (bh > 0.5) {
      ctx.fillStyle = 'rgba(31,58,95,.78)';
      ctx.fillRect(x - bw / 2, base - bh, bw, bh);
      ctx.fillStyle = '#1f3a5f';
      ctx.fillRect(x - bw / 2, base - bh, bw, Math.min(1.4, bh));
    } else {
      ctx.fillStyle = 'rgba(31,58,95,.15)';
      ctx.fillRect(x - bw / 2, base - 1, bw, 1);
    }
  }

  ctx.save();
  ctx.beginPath();
  let started = false;
  for (let t = first; t <= last; t += MINUTE_SECONDS) {
    const d = state.data.get(t);
    if (!d) {
      started = false;
      continue;
    }
    const share = d.posts > 0 ? d.positive / d.posts : 0;
    const x = xOf(t + MINUTE_SECONDS / 2);
    const y = base - Math.max(0, Math.min(1, share)) * ph;
    if (!started) {
      ctx.moveTo(x, y);
      started = true;
    } else {
      ctx.lineTo(x, y);
    }
  }
  ctx.strokeStyle = '#c0392b';
  ctx.lineWidth = 1.6;
  ctx.stroke();
  ctx.restore();

  const xn = xOf(now);
  if (xn >= L && xn <= L + pw) {
    ctx.save();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = 'rgba(31,58,95,.22)';
    ctx.beginPath();
    ctx.moveTo(xn, T);
    ctx.lineTo(xn, base);
    ctx.stroke();
    ctx.restore();
  }

  chartFont(ctx, 9);
  ctx.fillStyle = '#6b7280';
  ctx.textAlign = 'center';
  for (let k = 0; k <= 4; k++) {
    const t = lo + win.span * k / 4;
    const x = xOf(t);
    ctx.textAlign = k === 0 ? 'left' : (k === 4 ? 'right' : 'center');
    if (x >= L - 1 && x <= L + pw + 1) ctx.fillText(fmtMinute(t), x, base + 16);
  }

  chartFont(ctx, 8);
  ctx.fillStyle = '#9aa3af';
  ctx.textAlign = 'left';
  ctx.fillText('条 / 分', L, 12);
  ctx.textAlign = 'right';
  ctx.fillText('正面占比', L + pw, 12);
}

function drawSent() {
  const canvas = sentChart;
  const ctx = canvas.getContext('2d');
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  const pscale = canvas.width / w;
  ctx.setTransform(pscale, 0, 0, pscale, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const L = 42, R = 14, T = 20, B = 26;
  const pw = w - L - R;
  const ph = h - T - B;
  if (pw <= 0 || ph <= 0) return;
  const base = T + ph;
  const now = state.displayTime || state.startTs || DEFAULT_START_TS;
  const win = getChartWindow(now);
  const lo = win.lo;
  const hi = win.hi;
  const first = Math.floor(lo / MINUTE_SECONDS) * MINUTE_SECONDS;
  const last = Math.ceil(hi / MINUTE_SECONDS) * MINUTE_SECONDS;
  const xOf = function (t) { return L + ((t - lo) / win.span) * pw; };

  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = T + ph * i / 4;
    ctx.strokeStyle = i === 4 ? '#dfe3e9' : '#eef0f3';
    ctx.beginPath();
    ctx.moveTo(L, y);
    ctx.lineTo(L + pw, y);
    ctx.stroke();
  }

  chartFont(ctx, 9);
  ctx.fillStyle = '#6b7280';
  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    ctx.fillText(Math.round(100 * (1 - i / 4)) + '%', L - 8, T + ph * i / 4 + 3);
  }

  const pts = [];
  for (let t = first; t <= last; t += MINUTE_SECONDS) {
    const d = state.data.get(t);
    if (!d) continue;
    const total = d.posts || 0;
    const p = total > 0 ? Math.max(0, Math.min(1, d.positive / total)) : 0;
    const n = total > 0 ? Math.max(0, Math.min(1, d.neutral / total)) : 0;
    const g = total > 0 ? Math.max(0, Math.min(1, d.negative / total)) : 0;
    const sum = p + n + g;
    pts.push({
      x: xOf(t + MINUTE_SECONDS / 2),
      p: sum > 0 ? p / sum : 0,
      n: sum > 0 ? n / sum : 0,
      g: sum > 0 ? g / sum : 0,
    });
  }

  if (pts.length > 1) {
    const fillBand = function (lower, upper, color) {
      ctx.beginPath();
      for (let i = 0; i < pts.length; i++) {
        const y = base - upper(pts[i]) * ph;
        if (i === 0) ctx.moveTo(pts[i].x, y);
        else ctx.lineTo(pts[i].x, y);
      }
      for (let i = pts.length - 1; i >= 0; i--) {
        const y = base - lower(pts[i]) * ph;
        ctx.lineTo(pts[i].x, y);
      }
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    };

    fillBand(function (pt) { return 0; }, function (pt) { return pt.p; }, 'rgba(46,139,87,.55)');
    fillBand(function (pt) { return pt.p; }, function (pt) { return pt.p + pt.n; }, 'rgba(154,165,177,.5)');
    fillBand(function (pt) { return pt.p + pt.n; }, function (pt) { return 1; }, 'rgba(192,57,43,.55)');

    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(46,139,87,.35)';
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const y = base - pts[i].p * ph;
      if (i === 0) ctx.moveTo(pts[i].x, y);
      else ctx.lineTo(pts[i].x, y);
    }
    ctx.stroke();

    ctx.strokeStyle = 'rgba(192,57,43,.35)';
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const y = base - (pts[i].p + pts[i].n) * ph;
      if (i === 0) ctx.moveTo(pts[i].x, y);
      else ctx.lineTo(pts[i].x, y);
    }
    ctx.stroke();
  }

  chartFont(ctx, 9);
  ctx.fillStyle = '#6b7280';
  ctx.textAlign = 'center';
  for (let k = 0; k < 4; k++) {
    const t = lo + win.span * k / 3;
    const x = xOf(t);
    ctx.textAlign = k === 0 ? 'left' : (k === 3 ? 'right' : 'center');
    if (x >= L - 1 && x <= L + pw + 1) ctx.fillText(fmtMinute(t), x, base + 16);
  }

  chartFont(ctx, 8);
  ctx.fillStyle = '#9aa3af';
  ctx.textAlign = 'left';
  ctx.fillText('占比', L, 12);
}

/* ---------- state / UI ---------- */

function setPhase(phase) {
  const map = {
    connecting: ['连接中', 'idle'],
    running: ['实时运行', 'live'],
    paused: ['已暂停', 'idle'],
    resetting: ['重置中', 'warn'],
    waiting: ['等待数据', 'warn'],
    catchup: ['流任务追赶中', 'warn'],
    finished: ['回放结束', 'done'],
    stalled: ['数据流中断', 'bad'],
    offline: ['连接中断', 'bad'],
  };
  const item = map[phase] || [phase, 'idle'];
  phaseText.textContent = item[0];
  phaseDot.className = 'phase-dot ' + item[1];
}

function updateChrome() {
  setPhase(state.phase);
  const speed = Number(state.speed) || 1;
  const buttons = speedGroup.querySelectorAll('button[data-speed]');
  for (let i = 0; i < buttons.length; i++) {
    buttons[i].classList.toggle('on', Number(buttons[i].getAttribute('data-speed')) === speed);
  }
  pauseBtn.textContent = state.paused ? '继续' : '暂停';
  resetBtn.disabled = state.phase === 'resetting';
}

function updateKpi() {
  const start = state.startTs || DEFAULT_START_TS;
  const hasData = !!(state.snapshot && state.data.size > 0 && state.phase !== 'resetting');
  const k = hasData && state.snapshot.kpi ? state.snapshot.kpi : {};
  const time = hasData ? (Number(k.sim_time) || start) : start;

  kpiTime.textContent = fmtMinute(time);
  kpiDate.textContent = fmtDate(time) + (hasData ? '' : ' · 等待数据');
  simDate.textContent = fmtDate(time);

  if (hasData) {
    kpiRate.textContent = fmtInt(k.rate);
    kpiTotal.textContent = fmtCompact(k.total_posts);
    kpiAlerts.textContent = fmtInt(k.alerts);
    kpiRateSub.textContent = '批次 #' + fmtInt(k.batch) + ' · 本批 ' + fmtInt(k.batch_posts) + ' 条';
    kpiAlertSub.textContent = '当前 ' + state.alerts.length + ' 条 · 规则命中';
  } else {
    kpiRate.textContent = 'N/A';
    kpiTotal.textContent = '0';
    kpiAlerts.textContent = '0';
    kpiRateSub.textContent = '等待分钟数据';
    kpiAlertSub.textContent = '暂无告警';
  }
}

function updateSentLegend() {
  const rows = (state.snapshot && state.snapshot.minutes) || [];
  let pos = 0, neg = 0, neu = 0, posts = 0;
  for (const row of rows) {
    pos += Number(row.positive) || 0;
    neg += Number(row.negative) || 0;
    neu += Number(row.neutral) || 0;
    posts += Number(row.posts) || 0;
  }
  if (posts > 0) {
    sentPos.textContent = fmtPct(pos / posts);
    sentNeu.textContent = fmtPct(neu / posts);
    sentNeg.textContent = fmtPct(neg / posts);
  } else {
    sentPos.textContent = 'N/A';
    sentNeu.textContent = 'N/A';
    sentNeg.textContent = 'N/A';
  }
}

function updateEmpty() {
  const hasData = state.data.size > 0 && state.phase !== 'resetting';
  mainEmpty.classList.toggle('hidden', hasData);
  sentEmpty.classList.toggle('hidden', hasData);
  tableEmpty.classList.toggle('hidden', hasData);
}

function updateStatus() {
  if (state.online === false) {
    statusLeft.textContent = '大屏后端连接中断 · 正在重试';
    statusRight.textContent = '保留最后画面';
    return;
  }
  if (state.phase === 'resetting') {
    statusLeft.textContent = '重置已提交 · 等待流任务清空并重建';
    statusRight.textContent = '图表将从空坐标轴重新开始';
    return;
  }
  const snap = state.snapshot;
  const s = snap && snap.status ? snap.status : {};
  const k = snap && snap.kpi ? snap.kpi : {};
  const parts = [];
  parts.push('流任务 ' + fmtAge(s.stream_age));
  parts.push('回放 ' + fmtAge(s.replay_age));
  parts.push('积压 ' + fmtInt(s.backlog));
  if (state.phase === 'waiting') parts.push('等待首批分钟数据');
  statusLeft.textContent = parts.join(' · ');
  statusRight.textContent = '逐分钟聚合 · 60 分钟滚动窗口 · 批次 #' + fmtInt(k.batch);
}

function setOnline(ok) {
  if (state.online === ok) return;
  state.online = ok;
  if (!ok) {
    setPhase('offline');
    updateStatus();
  } else if (state.snapshot) {
    setPhase(state.phase);
    updateStatus();
  }
}

function clearAll() {
  state.data.clear();
  state.latestT = null;
  state.snapshot = null;
  state.alerts = [];
  state.alertsSig = '';
  state.paused = false;
  state.displayTime = state.startTs;
  state.targetTime = state.startTs;
  state.tableT = null;
  state.chartYMax = 10;
  state.phase = 'resetting';
  topicRanker.clear();
  regionRanker.clear();
  renderTable(true);
  updateKpi();
  updateSentLegend();
  updateEmpty();
  renderAlerts(true);
  setPhase('resetting');
  updateChrome();
  updateStatus();
}

function applySnapshot(snap) {
  if (!snap) return;
  const prevRun = state.runId;
  const first = prevRun === null;

  if (first) {
    state.runId = snap.run_id;
    state.startTs = Number(snap.start_ts) || DEFAULT_START_TS;
    state.displayTime = state.startTs;
    state.targetTime = state.startTs;
  } else if (snap.run_id !== prevRun) {
    state.runId = snap.run_id;
    state.startTs = Number(snap.start_ts) || state.startTs;
    clearAll();
  }

  if (!first && snap.run_id === state.runId && snap.phase === 'resetting' && state.phase !== 'resetting') {
    state.startTs = Number(snap.start_ts) || state.startTs;
    clearAll();
  }

  state.snapshot = snap;
  state.phase = snap.phase || 'running';
  state.speed = Number(snap.status && snap.status.speed) || state.speed;
  state.paused = !!(snap.status && snap.status.paused);
  state.startTs = Number(snap.start_ts) || state.startTs;
  state.alerts = Array.isArray(snap.alerts) ? snap.alerts : [];
  state.alertsSig = '';

  const mins = Array.isArray(snap.minutes) ? snap.minutes : [];
  let latest = null;
  if (mins.length) {
    for (let i = 0; i < mins.length; i++) {
      const row = mins[i];
      const t = Number(row.t);
      if (!Number.isFinite(t)) continue;
      const old = state.data.get(t);
      if (!old || row.has_data || !old.has_data) state.data.set(t, row);
    }
    const last = mins[mins.length - 1];
    latest = Number(last.t);
    if (Number.isFinite(latest)) {
      const prevLatest = state.latestT;
      state.latestT = latest;
      if (prevLatest === null || latest > prevLatest) {
        state.targetTime = latest + MINUTE_SECONDS - 0.5;
      }
      if (first) {
        state.displayTime = latest + 0.5;
        state.targetTime = latest + MINUTE_SECONDS - 0.5;
      }
    }
  } else if (state.phase === 'resetting' || state.phase === 'waiting') {
    state.displayTime = state.startTs;
    state.targetTime = state.startTs;
  }

  if (state.phase === 'resetting') {
    state.data.clear();
    state.latestT = null;
    state.displayTime = state.startTs;
    state.targetTime = state.startTs;
  }

  if (state.latestT !== null) {
    const cutoff = state.latestT - 300 * 60;
    for (const t of Array.from(state.data.keys())) {
      if (t < cutoff) state.data.delete(t);
    }
  }

  updateKpi();
  updateSentLegend();
  updateEmpty();
  updateChrome();
  updateStatus();
  renderAlerts(false);
  topicRanker.update(snap.rank && snap.rank.topics ? snap.rank.topics : []);
  regionRanker.update(snap.rank && snap.rank.regions ? snap.rank.regions : []);
  renderTable(true);
}

function updateDisplayTime(dt) {
  if (!state.startTs) return;
  if (state.phase === 'resetting' || (state.phase === 'waiting' && state.data.size === 0)) {
    state.displayTime = state.startTs;
    return;
  }
  if (state.paused) return;
  const target = Math.max(state.startTs, state.targetTime || state.startTs);
  const gap = target - state.displayTime;
  if (gap > 0.0001) {
    let step = (Number(state.speed) || 1) * MINUTE_SECONDS * dt;
    if (gap > 2 * MINUTE_SECONDS) step = Math.max(step, gap * dt * 3);
    state.displayTime = Math.min(target, state.displayTime + step);
  } else if (gap < -0.5) {
    state.displayTime = target;
  }
}

/* ---------- polling / control ---------- */

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  let data = null;
  try { data = await response.json(); } catch (err) { data = null; }
  if (!response.ok || (data && data.ok === false)) {
    throw new Error((data && data.error) || ('HTTP ' + response.status));
  }
  return data || {};
}

async function poll() {
  if (disposed || state.pollBusy) return;
  state.pollBusy = true;
  const controller = new AbortController();
  pollAbort = controller;
  try {
    const response = await fetch('/api/snapshot', { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const snap = await response.json();
    if (!disposed) {
      applySnapshot(snap);
      setOnline(true);
    }
  } catch (err) {
    if (!disposed) setOnline(false);
  } finally {
    state.pollBusy = false;
    if (pollAbort === controller) pollAbort = null;
  }
}

function showToast(message, bad) {
  toast.textContent = message;
  toast.classList.toggle('bad', !!bad);
  toast.classList.remove('hidden');
  if (state.toastTimer) clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(function () {
    toast.classList.add('hidden');
  }, 2800);
}

function openModal() {
  resetModal.classList.remove('hidden');
  modalCancel.focus();
}

function closeModal() {
  resetModal.classList.add('hidden');
}

async function doReset() {
  modalConfirm.disabled = true;
  modalCancel.disabled = true;
  try {
    const result = await postJson('/api/reset', {});
    state.runId = result.run_id !== undefined ? result.run_id : state.runId;
    state.startTs = Number(result.start_ts) || Number(result.startTs) || DEFAULT_START_TS;
    clearAll();
    closeModal();
    showToast('已重置 · 从 2020-01-22 00:00 重新开始');
    poll();
  } catch (err) {
    showToast('重置失败，请检查后端连接', true);
  } finally {
    modalConfirm.disabled = false;
    modalCancel.disabled = false;
  }
}

/* ---------- animation ---------- */

function frame(ts) {
  if (disposed) return;
  const elapsed = Math.min(1.0, Math.max(0.001, (ts - state.lastFrame) / 1000));
  state.lastFrame = ts;
  updateDisplayTime(elapsed);
  updateTable();
  let left = elapsed;
  while (left > 0.0001) {
    const h = Math.min(1 / 60, left);
    topicRanker.step(h);
    regionRanker.step(h);
    left -= h;
  }
  drawMain();
  drawSent();
  rafId = requestAnimationFrame(frame);
}

/* ---------- init / events ---------- */

function init() {
  resizeCanvases();
  onResize();
  state.lastFrame = performance.now();
  initMetrics();
  renderTable(true);
  renderAlerts(true);
  updateKpi();
  updateChrome();
  updateStatus();
  rafId = requestAnimationFrame(frame);
  pollTimer = setInterval(poll, POLL_MS);
  poll();

  window.addEventListener('resize', onResize);
  document.addEventListener('fullscreenchange', onFullscreen);
  if (resizeObserver) resizeObserver.observe(stage);

  speedGroup.addEventListener('click', function (ev) {
    const button = ev.target.closest('button[data-speed]');
    if (!button) return;
    const speed = Number(button.getAttribute('data-speed'));
    if (!Number.isFinite(speed)) return;
    state.speed = speed;
    updateChrome();
    postJson('/api/control', { speed: speed }).catch(function () {
      showToast('倍速切换失败，请重试', true);
    });
  });

  pauseBtn.addEventListener('click', function () {
    const next = !state.paused;
    state.paused = next;
    updateChrome();
    postJson('/api/control', { paused: next }).catch(function () {
      state.paused = !next;
      updateChrome();
      showToast('暂停状态切换失败，请重试', true);
    });
  });

  resetBtn.addEventListener('click', openModal);
  modalCancel.addEventListener('click', closeModal);
  modalConfirm.addEventListener('click', doReset);
  resetModal.addEventListener('click', function (ev) {
    if (ev.target && ev.target.getAttribute('data-close') === '1') closeModal();
  });

  fullBtn.addEventListener('click', function () {
    if (!document.fullscreenElement) {
      if (stage.requestFullscreen) stage.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  });

  alertsList.addEventListener('click', function (ev) {
    const button = ev.target.closest('button[data-ack]');
    if (!button) return;
    ackAlert(button.getAttribute('data-id'), button.getAttribute('data-ack'));
  });

  document.addEventListener('keydown', onKey);
}


  function destroy() {
    if (disposed) return;
    disposed = true;
    if (pollTimer) clearInterval(pollTimer);
    if (rafId) cancelAnimationFrame(rafId);
    if (resizeRaf) cancelAnimationFrame(resizeRaf);
    if (pollAbort) pollAbort.abort();
    window.removeEventListener('resize', onResize);
    document.removeEventListener('keydown', onKey);
    document.removeEventListener('fullscreenchange', onFullscreen);
    if (resizeObserver) resizeObserver.disconnect();
    if (document.fullscreenElement === stage && document.exitFullscreen) {
      document.exitFullscreen().catch(function () {});
    }
    root.innerHTML = '';
  }

  init();
  return destroy;
}
