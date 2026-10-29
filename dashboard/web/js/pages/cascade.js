import { esc, kpiRow, num } from "../format.js";

const POL_COLORS = { "正面": "#2E8B57", "中性": "#9AA5B1", "负面": "#C0392B" };

export async function mount(root, ctx) {
  const data = await ctx.api.get("/api/cascade", null, { signal: ctx.signal });
  if (ctx.signal.aborted) return null;

  const candidates = data.candidates || [];
  const top = data.top || [];
  const polarity = data.sentiment?.polarity || [];
  const buckets = data.sentiment?.buckets || [];
  const notes = (data.notes || []).map((note) => "<p>" + esc(note) + "</p>").join("");
  const tableRows = top.map((row) =>
    '<tr><td class="mono" title="' + esc(row.orig_id) + '">' + esc(row.orig_id) + '</td>' +
    '<td class="num">' + num(row.reposters) + '</td>' +
    '<td class="mono" title="' + esc(row.target_user) + '">' + esc(row.target_user) + '</td>' +
    '<td class="num">' + (row.fans_num == null ? "N/A" : num(row.fans_num)) + '</td>' +
    '<td class="num">' + (row.fans_rank == null ? "N/A" : "第 " + num(row.fans_rank) + " 名") + '</td>' +
    '<td>' + esc(row.province || "N/A") + '</td></tr>'
  ).join("");
  const polarityRows = polarity.map((row) => {
    const color = POL_COLORS[row.polarity] || "#6B7280";
    return '<tr><td><span class="dot" style="background:' + color + '"></span>' + esc(row.polarity) + '</td>' +
      '<td class="num">' + num(row.posts) + '</td><td class="num">' + Number(row.avg_reposts).toFixed(2) + '</td>' +
      '<td class="num">' + num(row.posts_ge_100) + '</td><td class="num">' + num(row.posts_ge_1000) + '</td></tr>';
  }).join("");

  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>传播分析</h1>' +
      '<p>把同一条微博的所有转发聚合成级联，观察它的规模分布与扩散节奏。</p></div>' +
      '<div class="page-rule"></div>' +
      kpiRow(data.kpis) +
      '<div class="grid-2">' +
        '<div class="panel"><div class="panel-head"><h2>级联规模分布</h2>' +
        '<span>纵轴为对数 · 11 个区间</span></div><div id="cascade-bins" class="chart cascade"></div></div>' +
        '<div class="panel"><div class="panel-head"><h2>扩散节奏</h2>' +
        '<span>单条微博的扩散过程</span></div>' +
        '<div class="field" style="margin-bottom:8px"><label for="cascade-select">被转发微博</label>' +
        '<select id="cascade-select" style="min-width:0;width:100%">' +
        candidates.map((item) => '<option value="' + esc(item.orig_id) + '">' + esc(item.label) + '</option>').join("") +
        '</select></div><div id="cascade-growth" class="chart cascade-growth"></div>' +
        '<p class="caption" id="cascade-caption"></p></div>' +
      '</div>' +
      '<div class="section-title">粉丝多 ≠ 传播广' +
      '<small>转发量最高的 20 条微博与原作者粉丝数对照</small></div>' +
      '<div class="panel table-wrap"><table class="data table-compact"><thead><tr>' +
      '<th>微博</th><th class="num">转发者</th><th>原作者</th><th class="num">粉丝数</th>' +
      '<th class="num">粉丝排名</th><th>省份</th></tr></thead><tbody>' + tableRows + '</tbody></table></div>' +
      '<div class="section-title">情感倾向与传播规模' +
      '<small>对 4,089 万条推文逐条打分后的结果</small></div>' +
      '<div class="grid-2">' +
        '<div class="panel"><div class="panel-head"><h2>各极性平均转发量</h2><span>条均被转发次数</span></div>' +
        '<div id="cascade-polarity" class="chart sentiment"></div></div>' +
        '<div class="panel"><div class="panel-head"><h2>各极性在转发量区间上的分布</h2>' +
        '<span>纵轴为对数</span></div><div id="cascade-buckets" class="chart sentiment"></div></div>' +
      '</div>' +
      '<div class="panel table-wrap" style="margin-top:16px"><table class="data table-compact"><thead><tr>' +
      '<th>极性</th><th class="num">推文数</th><th class="num">平均转发</th>' +
      '<th class="num">转发 ≥ 100</th><th class="num">转发 ≥ 1000</th></tr></thead><tbody>' +
      polarityRows + '</tbody></table></div>' +
      (notes ? '<div class="notes">' + notes + '</div>' : "") +
    '</div>';

  const binsEl = root.querySelector("#cascade-bins");
  const growthEl = root.querySelector("#cascade-growth");
  const polarityEl = root.querySelector("#cascade-polarity");
  const bucketsEl = root.querySelector("#cascade-buckets");
  const captionEl = root.querySelector("#cascade-caption");
  const selectEl = root.querySelector("#cascade-select");
  let disposed = false;
  let seq = 0;
  let growthAbort = null;

  async function loadGrowth(origId) {
    const mine = ++seq;
    if (growthAbort) growthAbort.abort();
    growthAbort = new AbortController();
    growthEl.classList.add("is-loading");
    try {
      const growth = await ctx.api.get("/api/cascade/growth", { orig_id: origId }, { signal: growthAbort.signal });
      if (disposed || ctx.signal.aborted || mine !== seq) return;
      const all = growth.rows || [];
      const spanHours = all.length > 1
        ? (Date.parse(all[all.length - 1].hour) - Date.parse(all[0].hour)) / 3600000 : 0;
      const daily = spanHours > 24 * 7;
      captionEl.textContent = (growth.caption || "") + (daily ? " 图中按天汇总。" : "");
      let rows = all;
      if (daily) {
        const days = new Map();
        all.forEach((row) => {
          const day = row.hour.slice(0, 10);
          days.set(day, (days.get(day) || 0) + Number(row.new_reposters));
        });
        rows = [...days].map(([hour, new_reposters]) => ({ hour, new_reposters }));
      }
      const unit = daily ? "每日" : "每小时";
      let running = 0;
      const cumulative = rows.map((row) => (running += Number(row.new_reposters)));
      await ctx.charts.render(growthEl, [
        {
          type: "scatter", mode: "lines", x: rows.map((row) => row.hour),
          y: rows.map((row) => row.new_reposters), fill: "tozeroy",
          name: unit + "新增转发", line: { color: "#C0392B", width: 1.4 },
          fillcolor: "rgba(192,57,43,0.24)",
          hovertemplate: "%{x|%m-%d}" + (daily ? "" : " %H:%M") + "<br>新增 %{y:,}<extra></extra>",
        },
        {
          type: "scatter", mode: "lines", x: rows.map((row) => row.hour), y: cumulative,
          name: "累计转发（右轴）", yaxis: "y2", line: { color: "#1F3A5F", width: 2.2 },
          hovertemplate: "累计 %{y:,}<extra></extra>",
        },
      ], {
        margin: { l: 54, r: 58, t: 26, b: 40 },
        xaxis: {
          type: "date", nticks: 6,
          tickformat: daily ? "%m-%d" : "%m-%d %H:%M",
          hoverformat: daily ? "%Y-%m-%d" : "%Y-%m-%d %H:%M",
        },
        yaxis: { title: { text: unit + "新增转发", font: { size: 10.5 } }, rangemode: "tozero" },
        yaxis2: {
          title: { text: "累计转发", font: { size: 10.5 } }, overlaying: "y", side: "right",
          showgrid: false, rangemode: "tozero",
        },
        legend: { x: 0, y: 1.16, font: { size: 10.5 } },
      });
    } catch (err) {
      if (err.name !== "AbortError" && !disposed) captionEl.textContent = "扩散数据加载失败：" + err.message;
    } finally {
      if (!disposed && mine === seq) growthEl.classList.remove("is-loading");
    }
  }

  selectEl.addEventListener("change", () => loadGrowth(selectEl.value));

  const bucketNames = [...new Set(buckets.map((row) => row.polarity))];
  const bucketTraces = bucketNames.map((name) => {
    const part = buckets.filter((row) => row.polarity === name);
    return {
      type: "scatter", mode: "lines+markers", name,
      x: part.map((row) => row.bucket), y: part.map((row) => Number(row.share) * 100),
      line: { color: POL_COLORS[name] || "#6B7280", width: 2.2 },
      marker: { size: 5 },
      hovertemplate: "%{x}<br>%{y:.3f}%<extra>" + name + "</extra>",
    };
  });

  const polarityTraces = [{
    type: "bar", x: polarity.map((row) => row.polarity), y: polarity.map((row) => row.avg_reposts),
    marker: { color: polarity.map((row) => POL_COLORS[row.polarity] || "#6B7280") },
    text: polarity.map((row) => Number(row.avg_reposts).toFixed(2)),
    textposition: "outside", cliponaxis: false,
    hovertemplate: "%{x}<br>平均转发 %{y:.2f}<extra></extra>",
  }];

  await Promise.all([
    ctx.charts.render(binsEl, [{
      type: "bar", x: data.bins.map((row) => row.label), y: data.bins.map((row) => row.count),
      marker: { color: "#1F3A5F", opacity: 0.86 },
      text: data.bins.map((row) => num(row.count)), textposition: "outside",
      textfont: { size: 9.5, color: "#6B7280" }, cliponaxis: false,
      hovertemplate: "%{x} 人<br>微博 %{y:,} 条<extra></extra>",
    }], {
      margin: { l: 58, r: 18, t: 16, b: 72 },
      xaxis: { title: { text: "转发者人数", font: { size: 10.5 } }, tickangle: -32, tickfont: { size: 9.5 } },
      yaxis: { title: { text: "微博条数（对数）", font: { size: 10.5 } }, type: "log", dtick: 1 },
      showlegend: false, bargap: 0.3,
    }),
    ctx.charts.render(polarityEl, polarityTraces, {
      margin: { l: 54, r: 18, t: 16, b: 40 },
      yaxis: { title: { text: "平均被转发次数", font: { size: 10.5 } }, rangemode: "tozero" },
      showlegend: false, bargap: 0.45,
    }),
    ctx.charts.render(bucketsEl, bucketTraces, {
      margin: { l: 56, r: 18, t: 28, b: 50 },
      xaxis: {
        type: "category", title: { text: "被转发次数区间", font: { size: 10.5 } },
        tickfont: { size: 9.5 }, tickangle: -28,
        categoryorder: "array",
        categoryarray: [...new Set(buckets.map((row) => row.bucket))],
      },
      yaxis: { title: { text: "该区间推文占比（%）", font: { size: 10.5 } }, type: "log", dtick: 1 },
      legend: { x: 0, y: 1.18, font: { size: 10.5 } },
    }),
    loadGrowth(candidates[0]?.orig_id),
  ]);

  return () => {
    disposed = true;
    seq += 1;
    if (growthAbort) growthAbort.abort();
    ctx.charts.purge(binsEl);
    ctx.charts.purge(growthEl);
    ctx.charts.purge(polarityEl);
    ctx.charts.purge(bucketsEl);
  };
}