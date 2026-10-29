import { esc, kpiRow } from "../format.js";

const SERIES = ["#1F3A5F", "#C0392B", "#E8A33D", "#2E8B57", "#7D5BA6", "#0E8B8B", "#6B7280", "#B7791F"];

function chartPanel(title, hint, id, cls) {
  return '<div class="panel"><div class="panel-head"><h2>' + esc(title) + '</h2><span>' + esc(hint) + '</span></div>' +
    '<div id="' + id + '" class="chart ' + cls + '"></div></div>';
}

export async function mount(root, ctx) {
  const data = await ctx.api.get("/api/geo", null, { signal: ctx.signal });
  if (ctx.signal.aborted) return null;

  const grid = (data.grid || []).filter((cell) => Number(cell.posts) >= 500);
  const province = (data.province || []).slice(0, 15).slice().reverse();
  const provinces = data.share?.provinces || [];
  const defaults = ["湖北", "广东", "北京", "上海", "浙江", "海外"].filter((name) => provinces.includes(name));
  const selected = new Set(defaults.length ? defaults : provinces.slice(0, 6));
  const notes = (data.notes || []).map((note) => "<p>" + esc(note) + "</p>").join("");

  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>空间热点</h1>' +
      '<p>带 GPS 坐标的微博按 0.25° 网格聚合后的分布，以及剥离采集节奏后的省份发言占比。</p></div>' +
      '<div class="page-rule"></div>' +
      kpiRow(data.kpis) +
      '<div class="section-title">空间热点分布' +
      '<small>仅展示发帖量 ≥ 500 的网格；点面积为对数发帖量，颜色越深表示越密集</small></div>' +
      '<div class="panel"><div id="geo-map" class="chart map"></div></div>' +
      '<div class="grid-2" style="margin-top:16px">' +
        chartPanel("省份推文量与传播强度", "条形末端为平均转发量", "geo-province", "medium") +
        '<div class="panel"><div class="panel-head"><h2>省份发言占比（归一化）</h2>' +
        '<span>占当日全部带坐标推文的比例</span></div>' +
        '<div class="chips" id="geo-share-chips">' +
        provinces.map((name) => '<button type="button" class="chip' + (selected.has(name) ? " on" : "") +
          '" data-province="' + esc(name) + '">' + esc(name) + '</button>').join("") +
        '</div><div id="geo-share" class="chart medium"></div>' +
        '<p class="caption">湖北的绝对发帖量最高值出现在 4 月；看占比时，峰值恰好落在封城窗口内。归一化纠正了采集节奏造成的假象。</p></div>' +
      '</div>' +
      (notes ? '<div class="notes">' + notes + '</div>' : "") +
    '</div>';

  const mapEl = root.querySelector("#geo-map");
  const provinceEl = root.querySelector("#geo-province");
  const shareEl = root.querySelector("#geo-share");
  const chips = root.querySelector("#geo-share-chips");

  const vmin = grid.length ? Math.min(...grid.map((cell) => Number(cell.v))) : 0;
  const vmax = grid.length ? Math.max(...grid.map((cell) => Number(cell.v))) : 1;
  const mapTrace = {
    type: "scattergeo",
    lon: grid.map((cell) => cell.glon),
    lat: grid.map((cell) => cell.glat),
    mode: "markers",
    marker: {
      size: grid.map((cell) => (Number(cell.v) - vmin + 0.6) * 4.5),
      color: grid.map((cell) => cell.v),
      cmin: vmin,
      cmax: vmax,
      colorscale: [[0, "#FFF6D6"], [0.35, "#FBD27A"], [0.62, "#F2913F"], [0.82, "#D6453C"], [1, "#7E1B1B"]],
      showscale: true,
      colorbar: {
        title: { text: "log₁₀ 发帖量", font: { size: 10 } },
        thickness: 12, len: 0.6, outlinewidth: 0,
        tickfont: { size: 9.5 }, x: 0.98,
      },
      line: { width: 0 },
      opacity: 0.86,
    },
    customdata: grid.map((cell) => [cell.posts, cell.users, cell.reposts]),
    hovertemplate: "%{lon:.2f}°E / %{lat:.2f}°N<br>发帖 %{customdata[0]:,}<br>用户 %{customdata[1]:,}" +
      "<br>转发 %{customdata[2]:,}<extra></extra>",
  };

  const provinceTrace = {
    type: "bar",
    x: province.map((row) => row.posts),
    y: province.map((row) => row.province),
    orientation: "h",
    marker: { color: "#C0392B", opacity: 0.88 },
    text: province.map((row) => "平均转发 " + Number(row.avg_reposts).toFixed(1)),
    textposition: "outside",
    cliponaxis: false,
    textfont: { size: 9.5, color: "#6B7280" },
    customdata: province.map((row) => [row.users, row.avg_reposts]),
    hovertemplate: "%{y}<br>推文 %{x:,}<br>用户 %{customdata[0]:,}" +
      "<br>平均转发 %{customdata[1]:.2f}<extra></extra>",
  };

  let shareToken = 0;
  async function drawShare() {
    const token = ++shareToken;
    const traces = provinces.filter((name) => selected.has(name)).map((name) => {
      const part = data.share.rows.filter((row) => row.province === name);
      const color = SERIES[provinces.indexOf(name) % SERIES.length];
      return {
        type: "scatter", mode: "lines", name,
        x: part.map((row) => row.day),
        y: part.map((row) => Number(row.share) * 100),
        line: { color, width: 2 },
        hovertemplate: "%{y:.2f}%<extra>" + name + "</extra>",
      };
    });
    await ctx.charts.render(shareEl, traces, {
      margin: { l: 50, r: 16, t: 34, b: 38 },
      xaxis: { type: "date", tickformat: "%m-%d", nticks: 6, hoverformat: "%Y-%m-%d" },
      yaxis: { title: { text: "占当日带坐标推文（%）", font: { size: 10.5 } }, rangemode: "tozero", ticksuffix: "%" },
      legend: { orientation: "h", x: 0, y: 1.18, font: { size: 10.5 } },
      shapes: [{
        type: "rect", xref: "x", yref: "paper", x0: data.lockdown.start, x1: data.lockdown.end,
        y0: 0, y1: 1, fillcolor: "#E8A33D", opacity: 0.12, line: { width: 0 }, layer: "below",
      }],
      annotations: selected.size ? [{
        x: data.lockdown.start, y: 1, xref: "x", yref: "paper", text: "武汉封城期",
        showarrow: false, xanchor: "left", yanchor: "bottom", font: { size: 10, color: "#B7791F" },
      }] : [{
        x: 0.5, y: 0.5, xref: "paper", yref: "paper", text: "请选择至少一个省份",
        showarrow: false, font: { size: 12, color: "#9AA3AF" },
      }],
    });
    if (token !== shareToken) return;
  }

  chips.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-province]");
    if (!button) return;
    const name = button.dataset.province;
    if (selected.has(name)) selected.delete(name);
    else selected.add(name);
    button.classList.toggle("on", selected.has(name));
    drawShare();
  });

  await Promise.all([
    ctx.charts.render(mapEl, [mapTrace], {
      margin: { l: 6, r: 6, t: 6, b: 6 },
      geo: {
        scope: "asia", resolution: 50, projection: { type: "mercator" },
        lonaxis: { range: [74, 135] }, lataxis: { range: [16, 54] },
        showland: true, landcolor: "#F4F6F8",
        showcountries: true, countrycolor: "#D8DEE6",
        showocean: true, oceancolor: "#FFFFFF",
        showcoastlines: true, coastlinecolor: "#D8DEE6",
        showframe: false, bgcolor: "rgba(0,0,0,0)",
      },
      showlegend: false,
    }),
    ctx.charts.render(provinceEl, [provinceTrace], {
      margin: { l: 76, r: 112, t: 8, b: 38 },
      xaxis: { title: { text: "推文数（条）", font: { size: 10.5 } }, rangemode: "tozero" },
      yaxis: { tickfont: { size: 10.5 } },
      showlegend: false,
      bargap: 0.28,
    }),
    drawShare(),
  ]);

  return () => {
    shareToken += 1;
    ctx.charts.purge(mapEl);
    ctx.charts.purge(provinceEl);
    ctx.charts.purge(shareEl);
  };
}
