import { esc, human, kpiRow, num } from "../format.js";

function pathTable(rows) {
  if (!rows.length) return '<div class="empty-note">这条链路上没有可展示的用户。</div>';
  return '<div class="table-wrap"><table class="data table-compact"><thead><tr>' +
    '<th>序号</th><th>用户</th><th class="num">粉丝数</th><th class="num">被转发</th>' +
    '<th class="num">PageRank</th><th>省份</th><th class="num">社区</th></tr></thead><tbody>' +
    rows.map((row) => '<tr><td class="num">' + (Number(row.seq) + 1) + '</td>' +
      '<td class="mono" title="' + esc(row.user_id) + '">' + esc(row.user_id) + '</td>' +
      '<td class="num">' + human(row.fans_num) + '</td>' +
      '<td class="num">' + num(row.in_degree) + '</td>' +
      '<td class="num">' + Number(row.pagerank).toFixed(6) + '</td>' +
      '<td>' + esc(row.province || "—") + '</td>' +
      '<td class="num">#' + esc(row.community) + '</td></tr>').join("") +
    '</tbody></table></div>';
}

function oneHop(label, side, userId) {
  return '<div class="panel"><div class="panel-head"><h2>' + label + '</h2>' +
    '<span class="mono" title="' + esc(userId) + '">' + esc(userId) + '</span></div>' +
    '<div class="stat-strip two">' +
      '<div><span>转发过他的人</span><b>' + num(side.reposters) + '</b></div>' +
      '<div><span>他转发过的人</span><b>' + num(side.follows) + '</b></div>' +
    '</div></div>';
}

export async function mount(root, ctx) {
  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>关系发现</h1>' +
      '<p>在用户级转发网络上寻找两个用户之间的最短链路，并展开每一跳的转发方向。</p></div>' +
      '<div class="page-rule"></div>' +
      '<div class="panel" style="padding:14px 16px 12px">' +
        '<form id="relations-form" class="controls" style="margin:0">' +
          '<div class="field"><label for="relations-a">用户 A</label>' +
          '<input id="relations-a" spellcheck="false" autocomplete="off" placeholder="16 位十六进制字符串"></div>' +
          '<div class="field"><label for="relations-b">用户 B</label>' +
          '<input id="relations-b" spellcheck="false" autocomplete="off" placeholder="16 位十六进制字符串"></div>' +
          '<button class="btn" type="submit">查找链路</button>' +
          '<span class="caption" style="padding-bottom:8px">默认取 PageRank Top 6 中的第 1 与第 4 位。</span>' +
        '</form>' +
      '</div>' +
      '<div id="relations-body"><div class="skeleton chart"></div></div>' +
    '</div>';

  const form = root.querySelector("#relations-form");
  const inputA = root.querySelector("#relations-a");
  const inputB = root.querySelector("#relations-b");
  const body = root.querySelector("#relations-body");
  const button = form.querySelector("button");
  let disposed = false;
  let seq = 0;
  let abort = null;

  function render(data) {
    if (data.defaults && data.defaults.length === 2) {
      if (!inputA.value) inputA.value = data.defaults[0];
      if (!inputB.value) inputB.value = data.defaults[1];
    }
    if (data.status === "invalid") {
      body.innerHTML = '<div class="panel"><div class="empty-note">' + esc(data.message) + '</div></div>';
      return;
    }
    const path = data.path || [];
    const rows = data.rows || [];
    const hops = Math.max(0, path.length - 1);
    const middle = Math.max(0, path.length - 2);
    const kpis = [
      { label: "链路长度", value: num(hops) + " 跳", hint: "按无向转发关系计算" },
      { label: "中间人", value: num(middle), hint: "链路上的中转用户" },
      { label: "网络节点", value: human(2336558), hint: "转发图覆盖的用户数" },
    ];
    let html = data.status === "same"
      ? '<div class="notes"><p>' + esc(data.message) + '</p></div>'
      : "";
    if (data.status === "disconnected") {
      html += '<div class="notes"><p>' + esc(data.message) + '</p></div>';
    }
    html += kpiRow(kpis).replace('class="kpis"', 'class="kpis three"');
    if (data.status === "ok" || data.status === "same") {
      html += '<div class="section-title">最短链路 <small>' +
        (hops ? "共 " + hops + " 跳" : "两个 id 相同") + '</small></div>' +
        '<div class="panel">' + pathTable(rows) + '</div>';
      if (data.directions && data.directions.length) {
        html += '<div class="section-title">逐跳方向 <small>解释每一跳谁转发了谁</small></div>' +
          '<div class="panel"><div class="notes">' +
          data.directions.map((item) => '<p>第 ' + esc(item.hop) + ' 跳：' + esc(item.text) + '</p>').join("") +
          '</div></div>';
      }
    }
    if (data.one_hop) {
      html += '<div class="section-title">两端的一跳关系 <small>只统计直接相邻的用户</small></div>' +
        '<div class="grid-2">' +
          oneHop("A 端", data.one_hop.a, data.a || "") +
          oneHop("B 端", data.one_hop.b, data.b || "") +
        '</div>';
    }
    html += '<div class="notes"><p>链路按无向转发边计算最短跳数，方向只用于解释每一跳谁转发了谁。' +
      '两个用户可能分属不同的弱连通分量，此时不存在任何链路。</p></div>';
    body.innerHTML = html;
  }

  async function load(a, b) {
    const mine = ++seq;
    if (abort) abort.abort();
    abort = new AbortController();
    body.classList.add("is-loading");
    button.disabled = true;
    try {
      const data = await ctx.api.get("/api/relations", { a: a || "", b: b || "" }, { signal: abort.signal });
      if (disposed || ctx.signal.aborted || mine !== seq) return;
      render(data);
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

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load(inputA.value.trim(), inputB.value.trim());
  });

  await load("", "");
  return () => {
    disposed = true;
    seq += 1;
    if (abort) abort.abort();
  };
}
