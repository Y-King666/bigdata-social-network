import { esc, kpiRow, num } from "../format.js";

function tablePanel(title, hint, rows) {
  const body = rows.map((row) =>
    '<tr><td class="topic" title="' + esc(row.topic) + '">' + esc(row.topic) + '</td>' +
    '<td class="num">' + num(row.occurrences) + '</td>' +
    '<td class="num">' + num(row.peak_heat) + '</td>' +
    '<td class="num">第 ' + num(row.best_rank) + ' 名</td></tr>'
  ).join("");
  return '<div class="panel"><div class="panel-head"><h2>' + esc(title) + '</h2><span>' + esc(hint) + '</span></div>' +
    '<div class="table-wrap"><table class="data"><thead><tr><th>话题</th>' +
    '<th class="num">推文提及</th><th class="num">峰值热度</th><th class="num">最高排名</th>' +
    '</tr></thead><tbody>' + body + '</tbody></table></div></div>';
}

export async function mount(root, ctx) {
  const data = await ctx.api.get("/api/topics", null, { signal: ctx.signal });
  if (ctx.signal.aborted) return null;

  const top20 = (data.top20 || []).slice().reverse();
  const short = (topic) => topic.length > 22 ? topic.slice(0, 21) + "…" : topic;
  const corr = data.correlations || {};
  const notes = (data.notes || []).map((note) => "<p>" + esc(note) + "</p>").join("");

  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>热点话题</h1>' +
      '<p>从推文正文中抽取的话题标签，以及与热搜榜单的交叉对照。</p></div>' +
      '<div class="page-rule"></div>' +
      kpiRow(data.kpis) +
      '<div class="section-title">话题规模 Top 20<small>按全部推文中的提及次数排序</small></div>' +
      '<div class="panel"><div id="topics-top20" class="chart topics"></div></div>' +
      '<div class="grid-2" style="margin-top:16px">' +
        '<div class="panel"><div class="panel-head"><h2>单话题逐日走势</h2>' +
        '<span>Top 60 候选</span></div>' +
        '<div class="field" style="margin-bottom:8px"><label for="topic-select">选择话题</label>' +
        '<select id="topic-select" style="min-width:0;width:100%">' +
        (data.options || []).map((topic) => '<option value="' + esc(topic) + '"' +
          (topic === data.default_topic ? " selected" : "") + '>' + esc(topic) + '</option>').join("") +
        '</select></div>' +
        '<div id="topic-daily" class="chart topic-daily"></div>' +
        '<p class="caption" id="topic-caption"></p></div>' +
        '<div class="panel"><div class="panel-head"><h2>热搜热度与站内发帖量</h2>' +
        '<span>双对数 · 每个点是一个话题</span></div>' +
        '<div class="stat-strip">' +
          '<div><span>与峰值热度相关</span><b>' + Number(corr.peak_heat).toFixed(3) + '</b></div>' +
          '<div><span>与上榜次数相关</span><b>' + Number(corr.appearances).toFixed(3) + '</b></div>' +
          '<div><span>与最高排名相关</span><b>' + Number(corr.best_rank).toFixed(3) + '</b></div>' +
        '</div>' +
        '<div id="topics-scatter" class="chart scatter"></div>' +
        '<p class="caption">三个相关系数都接近 0：在疫情话题范围内，站内发帖量无法预测热搜热度。</p></div>' +
      '</div>' +
      '<div class="section-title">两类反差话题<small>发帖最多的话题未必最热，反之亦然</small></div>' +
      '<div class="grid-2">' +
        tablePanel("发帖量最高", "按推文提及排序", data.tables?.top_posts || []) +
        tablePanel("热搜热度最高", "按峰值热度排序", data.tables?.top_heat || []) +
      '</div>' +
      (notes ? '<div class="notes">' + notes + '</div>' : "") +
    '</div>';

  const topEl = root.querySelector("#topics-top20");
  const dailyEl = root.querySelector("#topic-daily");
  const scatterEl = root.querySelector("#topics-scatter");
  const captionEl = root.querySelector("#topic-caption");
  const selectEl = root.querySelector("#topic-select");
  let disposed = false;
  let seq = 0;
  let dailyAbort = null;

  async function loadDaily(topic) {
    const mine = ++seq;
    if (dailyAbort) dailyAbort.abort();
    dailyAbort = new AbortController();
    dailyEl.classList.add("is-loading");
    try {
      const daily = await ctx.api.get("/api/topics/daily", { topic }, { signal: dailyAbort.signal });
      if (disposed || ctx.signal.aborted || mine !== seq) return;
      captionEl.textContent = daily.caption || "";
      await ctx.charts.render(dailyEl, [
        {
          type: "bar", x: daily.rows.map((row) => row.day), y: daily.rows.map((row) => row.occurrences),
          name: "每日提及次数", marker: { color: "rgba(192,57,43,0.72)" },
          hovertemplate: "%{x|%m-%d}<br>提及 %{y:,}<extra></extra>",
        },
        {
          type: "scatter", mode: "lines", x: daily.rows.map((row) => row.day),
          y: daily.rows.map((row) => row.users), name: "参与用户数（右轴）", yaxis: "y2",
          line: { color: "#1F3A5F", width: 2 },
          hovertemplate: "用户 %{y:,}<extra></extra>",
        },
      ], {
        margin: { l: 52, r: 56, t: 26, b: 38 },
        xaxis: { type: "date", tickformat: "%m-%d", nticks: 7, hoverformat: "%Y-%m-%d" },
        yaxis: { title: { text: "提及次数", font: { size: 10.5 } }, rangemode: "tozero" },
        yaxis2: {
          title: { text: "参与用户数", font: { size: 10.5 } }, overlaying: "y", side: "right",
          showgrid: false, rangemode: "tozero",
        },
        bargap: 0.18,
        legend: { x: 0, y: 1.16, font: { size: 10.5 } },
      });
    } catch (err) {
      if (err.name !== "AbortError" && !disposed) captionEl.textContent = "逐日数据加载失败：" + err.message;
    } finally {
      if (!disposed && mine === seq) dailyEl.classList.remove("is-loading");
    }
  }

  selectEl.addEventListener("change", () => loadDaily(selectEl.value));

  await Promise.all([
    ctx.charts.render(topEl, [{
      type: "bar", x: top20.map((row) => row.occurrences), y: top20.map((row) => row.topic),
      orientation: "h", marker: { color: "#1F3A5F", opacity: 0.86 },
      customdata: top20.map((row) => [row.posts, row.users]),
      hovertemplate: "%{y}<br>提及 %{x:,}<br>帖子 %{customdata[0]:,}<br>用户 %{customdata[1]:,}<extra></extra>",
    }], {
      margin: { l: 250, r: 32, t: 6, b: 38 },
      xaxis: { title: { text: "提及次数", font: { size: 10.5 } }, rangemode: "tozero" },
      yaxis: {
        tickmode: "array", tickvals: top20.map((row) => row.topic),
        ticktext: top20.map((row) => short(row.topic)), tickfont: { size: 10 },
      },
      showlegend: false, bargap: 0.28,
    }),
    ctx.charts.render(scatterEl, [{
      type: "scattergl", mode: "markers",
      x: data.scatter.map((row) => row.occurrences),
      y: data.scatter.map((row) => row.peak_heat),
      customdata: data.scatter.map((row) => [row.topic, row.appearances, row.best_rank]),
      marker: { size: 4.2, color: "#1F3A5F", opacity: 0.34 },
      hovertemplate: "%{customdata[0]}<br>推文提及 %{x:,}<br>峰值热度 %{y:,}" +
        "<br>上榜 %{customdata[1]} 次 / 最高第 %{customdata[2]} 名<extra></extra>",
    }], {
      margin: { l: 64, r: 22, t: 8, b: 44 },
      xaxis: { title: { text: "推文提及次数（对数）", font: { size: 10.5 } }, type: "log", dtick: 1 },
      yaxis: { title: { text: "热搜峰值热度（对数）", font: { size: 10.5 } }, type: "log", dtick: 1 },
      showlegend: false,
    }),
    loadDaily(data.default_topic),
  ]);

  return () => {
    disposed = true;
    if (dailyAbort) dailyAbort.abort();
    ctx.charts.purge(topEl);
    ctx.charts.purge(dailyEl);
    ctx.charts.purge(scatterEl);
  };
}
