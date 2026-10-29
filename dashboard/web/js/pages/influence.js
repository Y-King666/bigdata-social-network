import { esc, human, kpiRow, num } from "../format.js";

const PR_FLOOR = 1e-7;

export async function mount(root, ctx) {
  const data = await ctx.api.get("/api/influence", null, { signal: ctx.signal });
  if (ctx.signal.aborted) return null;

  const top20 = data.top20 || [];
  const sample = data.scatter?.sample || [];
  const top100 = data.scatter?.top100 || [];
  const communities = data.communities || [];
  const lowFans = top100.filter((row) => row.fans_rank == null || row.fans_rank > 10000).length;

  const tableRows = top20.map((row) =>
    '<tr><td class="mono" title="' + esc(row.user_id) + '">' + esc(row.user_id) + '</td>' +
    '<td class="num mono">' + Number(row.pagerank).toFixed(6) + '</td>' +
    '<td class="num">' + num(row.in_degree) + '</td>' +
    '<td class="num">' + num(row.fans_num) + '</td>' +
    '<td class="num">' + (row.fans_rank == null ? "N/A" : "第 " + num(row.fans_rank) + " 名") + '</td>' +
    '<td>' + esc(row.province || "N/A") + (row.city ? " · " + esc(row.city) : "") + '</td>' +
    '<td class="num">#' + esc(row.community) + '</td></tr>'
  ).join("");

  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>影响力与社区</h1>' +
      '<p>PageRank 衡量用户在转发有向图中的被转载影响力，社区由 Leiden 算法划分。</p></div>' +
      '<div class="page-rule"></div>' +
      kpiRow(data.kpis) +
      '<div class="section-title">影响力 Top 20 <small>按 PageRank 从高到低排序</small></div>' +
      '<div class="panel table-wrap"><table class="data table-compact"><thead><tr>' +
      '<th>用户</th><th class="num">PageRank</th><th class="num">入度</th><th class="num">粉丝数</th>' +
      '<th class="num">粉丝排名</th><th>地域</th><th class="num">社区</th></tr></thead><tbody>' +
      tableRows + '</tbody></table></div>' +
      '<div class="section-title">粉丝规模与 PageRank' +
      '<small>横轴为粉丝数，纵轴为 PageRank，双对数坐标</small></div>' +
      '<div class="panel"><div id="influence-scatter" class="chart influence"></div>' +
      '<p class="caption">30,000 名随机用户样本（深蓝）+ PageRank 前 100（红）；' +
      '其中 ' + lowFans + ' 名头部用户的粉丝排名在 10,000 名之外。' +
      'PageRank 为 0 的零入度用户统一画在底部 10⁻⁷ 处。</p></div>' +
      '<div class="section-title">社区结构' +
      '<small>41,837 个 Leiden 社区中规模最大的 20 个</small></div>' +
      '<div class="grid-2">' +
        '<div class="panel"><div class="panel-head"><h2>社区规模 Top 20</h2>' +
        '<span>黄色为当前查看的社区</span></div><div id="influence-community" class="chart community"></div></div>' +
        '<div class="panel"><div class="panel-head"><h2>社区画像</h2><span>性别与省份 Top 5</span></div>' +
        '<div class="field" style="margin-bottom:10px"><label for="community-select">选择社区</label>' +
        '<select id="community-select" style="min-width:0;width:100%">' +
        communities.map((item) => '<option value="' + item.id + '"' +
          (item.id === data.default_community ? " selected" : "") + '>社区 ' + item.id +
          '（' + human(item.size) + ' 人）</option>').join("") +
        '</select></div>' +
        '<div id="community-stats" class="stat-strip two"></div>' +
        '<div class="grid-2" style="gap:10px">' +
          '<div><div class="mini-title">性别 Top 5</div><div id="community-gender" class="chart mini"></div></div>' +
          '<div><div class="mini-title">省份 Top 5</div><div id="community-province" class="chart mini"></div></div>' +
        '</div></div>' +
      '</div>' +
      '<div class="notes"><p>PageRank 在 326 万条用户级转发边上迭代计算，入度表示被多少人直接转发；' +
      '粉丝数为用户资料中的粉丝数量，与转发影响力并不等价。' +
      '社区画像取自用户资料表，性别与省份字段存在缺失与少量脏值，比例按有效值计算。</p></div>' +
    '</div>';

  const scatterEl = root.querySelector("#influence-scatter");
  const communityEl = root.querySelector("#influence-community");
  const genderEl = root.querySelector("#community-gender");
  const provinceEl = root.querySelector("#community-province");
  const statsEl = root.querySelector("#community-stats");
  const selectEl = root.querySelector("#community-select");
  let disposed = false;
  let detailSeq = 0;
  let detailAbort = null;

  function renderCommunityBars(selectedId) {
    const rows = communities.slice().reverse();
    const labels = rows.map((row) => "社区 " + row.id);
    const colors = rows.map((row) => (row.id === selectedId ? "#E8A33D" : "#1F3A5F"));
    return ctx.charts.render(communityEl, [{
      type: "bar", orientation: "h", x: rows.map((row) => row.size), y: labels,
      marker: { color: colors, opacity: 0.9 },
      text: rows.map((row) => human(row.size)), textposition: "outside",
      textfont: { size: 9.5, color: "#6B7280" }, cliponaxis: false,
      hovertemplate: "%{y}<br>%{x:,} 人<extra></extra>",
    }], {
      margin: { l: 74, r: 48, t: 8, b: 36 },
      xaxis: { title: { text: "社区规模（人）", font: { size: 10.5 } }, rangemode: "tozero" },
      yaxis: { tickfont: { size: 9.5 }, automargin: false },
      showlegend: false, bargap: 0.34,
    });
  }

  function miniTrace(rows, color) {
    const part = rows.filter((row) => !String(row.key).includes(":")).slice(0, 5).reverse();
    return [{
      type: "bar", orientation: "h", x: part.map((row) => row.count), y: part.map((row) => row.key),
      marker: { color, opacity: 0.88 },
      text: part.map((row) => num(row.count)), textposition: "outside",
      textfont: { size: 8.5, color: "#6B7280" }, cliponaxis: false,
      hovertemplate: "%{y}<br>%{x:,} 人<extra></extra>",
    }];
  }

  async function loadCommunity(id) {
    const mine = ++detailSeq;
    if (detailAbort) detailAbort.abort();
    detailAbort = new AbortController();
    const panel = genderEl.closest(".panel");
    panel.classList.add("is-loading");
    try {
      const detail = await ctx.api.get("/api/influence/community", { id }, { signal: detailAbort.signal });
      if (disposed || ctx.signal.aborted || mine !== detailSeq) return;
      statsEl.innerHTML =
        '<div><span>社区规模</span><strong>' + human(detail.size) + '</strong></div>' +
        '<div><span>平均粉丝数</span><strong>' + human(detail.avg_fans) + '</strong></div>';
      await Promise.all([
        ctx.charts.render(genderEl, miniTrace(detail.gender || [], "#C0392B"), {
          margin: { l: 58, r: 34, t: 8, b: 24 },
          xaxis: { tickfont: { size: 8.5 } }, yaxis: { tickfont: { size: 9 } },
          showlegend: false, bargap: 0.4,
        }),
        ctx.charts.render(provinceEl, miniTrace(detail.province || [], "#1F3A5F"), {
          margin: { l: 58, r: 34, t: 8, b: 24 },
          xaxis: { tickfont: { size: 8.5 } }, yaxis: { tickfont: { size: 9 } },
          showlegend: false, bargap: 0.4,
        }),
      ]);
    } catch (err) {
      if (err.name !== "AbortError" && !disposed) {
        statsEl.innerHTML = '<div><span>社区画像</span><strong>加载失败</strong></div>';
      }
    } finally {
      if (!disposed && mine === detailSeq) panel.classList.remove("is-loading");
    }
  }

  selectEl.addEventListener("change", () => {
    const id = Number(selectEl.value);
    renderCommunityBars(id);
    loadCommunity(id);
  });

  const sampleTrace = {
    type: "scattergl", mode: "markers", name: "随机用户样本",
    x: sample.map((row) => row.fans_num),
    y: sample.map((row) => Math.max(Number(row.pagerank), PR_FLOOR)),
    customdata: sample.map((row) => [row.pagerank]),
    marker: { size: 3.4, color: "rgba(31,58,95,0.30)", line: { width: 0 } },
    hovertemplate: "粉丝 %{x:,}<br>PageRank %{customdata[0]:.7f}<extra></extra>",
  };
  const topTrace = {
    type: "scattergl", mode: "markers", name: "PageRank Top 100",
    x: top100.map((row) => row.fans_num),
    y: top100.map((row) => Number(row.pagerank)),
    customdata: top100.map((row) => [row.pagerank, row.in_degree, row.user_id]),
    marker: { size: 7, color: "rgba(192,57,43,0.9)", line: { width: 0.5, color: "#FFFFFF" } },
    hovertemplate: "用户 %{customdata[2]}<br>粉丝 %{x:,}<br>PageRank %{customdata[0]:.6f}" +
      "<br>入度 %{customdata[1]:,}<extra></extra>",
  };

  await Promise.all([
    ctx.charts.render(scatterEl, [sampleTrace, topTrace], {
      margin: { l: 62, r: 20, t: 18, b: 52 },
      xaxis: { title: { text: "粉丝数（对数）", font: { size: 10.5 } }, type: "log", dtick: 1 },
      yaxis: { title: { text: "PageRank（对数）", font: { size: 10.5 } }, type: "log", dtick: 1 },
      legend: { x: 0, y: 1.14, font: { size: 10.5 } },
      shapes: [{
        type: "line", x0: 10000, x1: 10000, y0: 0, y1: 1, yref: "paper",
        line: { color: "#9AA5B1", width: 1, dash: "dot" },
      }],
      annotations: [{
        x: 10000, y: 1, yref: "paper", yanchor: "bottom", xanchor: "left",
        text: "粉丝 10,000", showarrow: false, font: { size: 9.5, color: "#6B7280" },
      }],
    }),
    renderCommunityBars(data.default_community),
    loadCommunity(data.default_community),
  ]);

  return () => {
    disposed = true;
    detailSeq += 1;
    if (detailAbort) detailAbort.abort();
    ctx.charts.purge(scatterEl);
    ctx.charts.purge(communityEl);
    ctx.charts.purge(genderEl);
    ctx.charts.purge(provinceEl);
  };
}