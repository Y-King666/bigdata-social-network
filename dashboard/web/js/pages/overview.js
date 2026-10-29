import { esc, human, kpiRow, longDate, num, pct } from "../format.js";

export async function mount(root, ctx) {
  const data = await ctx.api.get("/api/overview", null, { signal: ctx.signal });
  if (ctx.signal.aborted) return null;

  const inventory = (data.inventory || []).map((item) =>
    '<tr><td>' + esc(item.name) + '</td><td class="num">' + num(item.rows) +
    '</td><td class="num">' + Number(item.size_mb).toFixed(1) + '</td></tr>'
  ).join("");
  const layers = (data.layers || []).map((item) =>
    '<div class="card"><h3>' + esc(item.name) + '</h3><p>' + esc(item.description) + '</p></div>'
  ).join("");

  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>数据概览</h1>' +
      '<p>Weibo-COV：新冠疫情期间的公开微博数据，涵盖推文原文、用户画像、转发关系、话题与情感标注。' +
      '全部 ' + num(data.span.days) + ' 天，' + longDate(data.span.start) + ' 至 ' + longDate(data.span.end) + '。</p></div>' +
      '<div class="page-rule"></div>' +
      kpiRow(data.kpis) +
      '<div class="section-title">时间跨度与情感基调<small>全部 ' + num(data.span.days) +
      ' 天（' + longDate(data.span.start) + ' 至 ' + longDate(data.span.end) +
      '）；下图自 2020-01-20 全量采集起点起，共 ' + num(data.daily.length) + ' 天，正面占比稳定在 65% 以上</small></div>' +
      '<div class="panel"><div id="overview-daily" class="chart"></div></div>' +
      '<div class="section-title">数据集清单</div>' +
      '<div class="panel table-wrap"><table class="data"><thead><tr><th>数据集</th>' +
      '<th class="num">记录数</th><th class="num">体积 MB</th></tr></thead><tbody>' + inventory +
      '</tbody></table></div>' +
      '<div class="section-title">分析链路</div>' +
      '<div class="cards">' + layers + '</div>' +
    '</div>';

  const chart = root.querySelector("#overview-daily");
  const days = data.daily.map((row) => row.day);
  const posts = data.daily.map((row) => row.posts);
  const positive = data.daily.map((row) => Number(row.positive_share) * 100);

  await ctx.charts.render(chart, [
    {
      type: "bar", x: days, y: posts, name: "每日推文量",
      marker: { color: "#1F3A5F", opacity: 0.62 },
      hovertemplate: "%{x|%m-%d}<br>推文 %{y:,}<extra></extra>",
    },
    {
      type: "scatter", mode: "lines", x: days, y: positive, name: "正面占比（右轴）",
      yaxis: "y2", line: { color: "#C0392B", width: 2 },
      hovertemplate: "正面占比 %{y:.2f}%<extra></extra>",
    },
  ], {
    margin: { l: 54, r: 58, t: 8, b: 40 },
    xaxis: { type: "date", tickformat: "%m-%d", nticks: 9, hoverformat: "%Y-%m-%d" },
    yaxis: { title: { text: "每日推文量", font: { size: 11 } }, rangemode: "tozero" },
    yaxis2: {
      title: { text: "正面占比（%）", font: { size: 11 } }, overlaying: "y", side: "right",
      showgrid: false, range: [60, 92], ticksuffix: "%",
    },
    bargap: 0.32,
    legend: { x: 0, y: 1.08 },
  });

  return () => ctx.charts.purge(chart);
}
