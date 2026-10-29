import { esc, human, kpiRow, num } from "../format.js";

export async function mount(root, ctx) {
  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>传播模拟</h1>' +
      '<p>用独立级联模型在转发网络上模拟信息扩散，比较不同起点与传播概率。</p></div>' +
      '<div class="page-rule"></div>' +
      '<div class="panel" style="padding:14px 16px 12px">' +
        '<div class="controls" style="margin:0">' +
          '<div class="field" style="min-width:440px;flex:1"><label for="sim-seed">起点用户</label>' +
          '<select id="sim-seed" style="width:100%;min-width:0"><option value="">载入中…</option></select></div>' +
          '<div class="field"><label for="sim-prob">传播概率 <span id="sim-prob-text" class="mono">0.05</span></label>' +
          '<input id="sim-prob" type="range" min="0.01" max="0.30" step="0.01" value="0.05"></div>' +
          '<div class="field"><label for="sim-rounds">传播轮数 <span id="sim-rounds-text" class="mono">8</span></label>' +
          '<input id="sim-rounds" type="range" min="1" max="15" step="1" value="8"></div>' +
          '<button class="btn" type="button" id="sim-run">重新模拟</button>' +
        '</div>' +
      '</div>' +
      '<div id="simulate-body"><div class="skeleton chart"></div></div>' +
    '</div>';

  const body = root.querySelector("#simulate-body");
  const seedEl = root.querySelector("#sim-seed");
  const probEl = root.querySelector("#sim-prob");
  const roundsEl = root.querySelector("#sim-rounds");
  const probText = root.querySelector("#sim-prob-text");
  const roundsText = root.querySelector("#sim-rounds-text");
  const button = root.querySelector("#sim-run");
  let disposed = false;
  let seq = 0;
  let abort = null;
  let seedsFilled = false;

  probEl.addEventListener("input", () => { probText.textContent = Number(probEl.value).toFixed(2); });
  roundsEl.addEventListener("input", () => { roundsText.textContent = String(roundsEl.value); });

  function fillSeeds(seeds) {
    if (seedsFilled || !seeds || !seeds.length) return;
    seedEl.innerHTML = seeds.map((item) =>
      '<option value="' + esc(item.user_id) + '">' + esc(item.label) + '</option>').join("");
    seedsFilled = true;
  }

  function shell(data) {
    body.innerHTML =
      kpiRow(data.kpis) +
      '<div class="grid-2">' +
        '<div class="panel"><div class="panel-head"><h2>逐轮扩散</h2><span>每轮新增与累计感染</span></div>' +
        '<div id="sim-growth" class="chart medium"></div></div>' +
        '<div class="panel"><div class="panel-head"><h2>概率敏感性</h2><span>固定起点与轮数，扫描传播概率</span></div>' +
        '<div id="sim-sensitivity" class="chart medium"></div></div>' +
      '</div>' +
      '<div class="section-title">不同起点 <small>同样的概率与轮数，比较三个起点的感染规模</small></div>' +
      '<div class="panel" id="sim-probe"><div class="skeleton chart mini"></div></div>' +
      '<div class="notes">' + (data.notes || []).map((note) => '<p>' + esc(note) + '</p>').join("") + '</div>';
  }

  function renderGrowth(data) {
    const el = root.querySelector("#sim-growth");
    if (!el) return;
    ctx.charts.render(el, [
      { type: "bar", name: "每轮新增", x: data.growth.map((row) => row.round),
        y: data.growth.map((row) => row.new), marker: { color: "#1F3A5F" },
        hovertemplate: "第 %{x} 轮<br>新增 %{y:,} 人<extra></extra>" },
      { type: "scatter", mode: "lines+markers", name: "累计感染", x: data.growth.map((row) => row.round),
        y: data.growth.map((row) => row.cumulative), yaxis: "y2", line: { color: "#C0392B", width: 2 },
        marker: { size: 4 }, hovertemplate: "第 %{x} 轮<br>累计 %{y:,} 人<extra></extra>" },
    ], {
      xaxis: { title: { text: "轮次", font: { size: 11 } }, dtick: 1 },
      yaxis: { title: { text: "每轮新增（人）", font: { size: 11 } }, rangemode: "tozero" },
      yaxis2: { title: { text: "累计感染（人）", font: { size: 11 } }, overlaying: "y", side: "right",
                rangemode: "tozero", showgrid: false },
      hovermode: "x unified",
    });
  }

  function renderSensitivity(data) {
    const el = root.querySelector("#sim-sensitivity");
    if (!el) return;
    const probs = (data.probs || []).map((value) => value * 100);
    const finals = data.finals || [];
    const current = Number(data.current) * 100;
    const shapes = Number.isFinite(current) ? [{
      type: "line", x0: current, x1: current, y0: 0, y1: 1, yref: "paper",
      line: { color: "#C0392B", width: 1, dash: "dot" },
    }] : [];
    ctx.charts.render(el, [
      { type: "scatter", mode: "lines+markers", name: "最终感染", x: probs, y: finals,
        line: { color: "#1F3A5F", width: 2 }, marker: { size: 6 },
        hovertemplate: "概率 %{x:.0f}%<br>最终 %{y:,} 人<extra></extra>" },
    ], {
      xaxis: { title: { text: "传播概率（%）", font: { size: 11 } }, ticksuffix: "%" },
      yaxis: { title: { text: "最终感染人数", font: { size: 11 } }, rangemode: "tozero" },
      shapes,
      annotations: Number.isFinite(current) ? [{
        x: current, y: 1, yref: "paper", text: "当前 " + current.toFixed(0) + "%",
        showarrow: false, yshift: 10, font: { size: 10, color: "#C0392B" },
      }] : [],
      hovermode: "x unified",
    });
  }

  function renderProbe(data) {
    const el = root.querySelector("#sim-probe");
    if (!el) return;
    const rows = data.rows || [];
    el.innerHTML = '<div class="panel-head"><h2>起点对照</h2><span>被转发 = 原数据中的直接转发人数</span></div>' +
      '<table class="data table-compact"><thead><tr><th>起点用户</th>' +
      '<th class="num">被转发</th><th class="num">粉丝数</th><th class="num">感染人数</th></tr></thead><tbody>' +
      rows.map((row) => '<tr><td class="mono" title="' + esc(row.user_id) + '">' + esc(row.user_id) + '</td>' +
        '<td class="num">' + num(row.reposters) + '</td>' +
        '<td class="num">' + human(row.fans_num) + '</td>' +
        '<td class="num">' + num(row.infected) + '</td></tr>').join("") +
      '</tbody></table>';
  }

  async function run(seed, prob, rounds) {
    const mine = ++seq;
    if (abort) abort.abort();
    abort = new AbortController();
    const signal = abort.signal;
    body.classList.add("is-loading");
    button.disabled = true;
    try {
      const data = await ctx.api.get("/api/simulate", { seed, prob, rounds }, { signal });
      if (disposed || ctx.signal.aborted || mine !== seq) return;
      fillSeeds(data.seeds);
      seedEl.value = data.seed;
      shell(data);
      renderGrowth(data);
      body.classList.remove("is-loading");

      const [sens, probe] = await Promise.all([
        ctx.api.get("/api/simulate/sensitivity", { seed: data.seed, prob, rounds }, { signal }),
        ctx.api.get("/api/simulate/probe", { seed: data.seed, prob, rounds }, { signal }),
      ]);
      if (disposed || ctx.signal.aborted || mine !== seq) return;
      renderSensitivity(sens);
      renderProbe(probe);
    } catch (err) {
      if (err.name !== "AbortError" && !disposed) {
        body.innerHTML = '<div class="error-box">' + esc(err.message) + '</div>';
      }
    } finally {
      if (!disposed && mine === seq) {
        body.classList.remove("is-loading");
        button.disabled = false;
      }
    }
  }

  button.addEventListener("click", () => {
    run(seedEl.value, Number(probEl.value).toFixed(2), Number(roundsEl.value));
  });

  await run("", "0.05", 8);
  return () => {
    disposed = true;
    seq += 1;
    if (abort) abort.abort();
  };
}
