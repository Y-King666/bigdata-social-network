import { esc, kpiRow, num } from "../format.js";

function table(rows, emptyText) {
  if (!rows.length) return '<div class="empty-note">' + emptyText + '</div>';
  return '<div class="table-wrap"><table class="data table-compact"><thead><tr>' +
    '<th>用户</th><th class="num">次数</th><th>首次转发</th></tr></thead><tbody>' +
    rows.map((row) => '<tr><td class="mono" title="' + esc(row.user_id) + '">' + esc(row.user_id) + '</td>' +
      '<td class="num">' + num(row.count) + '</td><td>' + esc(String(row.first_time || "").slice(0, 16)) + '</td></tr>').join("") +
    '</tbody></table></div>';
}

export async function mount(root, ctx) {
  root.innerHTML =
    '<div class="page">' +
      '<div class="page-head"><h1>用户画像查询</h1>' +
      '<p>输入任意用户 id，从 2,000 万条用户画像和 326 万条转发关系中查询。</p></div>' +
      '<div class="page-rule"></div>' +
      '<div class="panel" style="padding:14px 16px 12px">' +
        '<form id="profile-form" class="controls" style="margin:0">' +
          '<div class="field"><label for="profile-id">用户 id</label>' +
          '<input id="profile-id" value="a7cc49c3878a4842" spellcheck="false" autocomplete="off" ' +
          'placeholder="16 位十六进制字符串"></div>' +
          '<button class="btn" type="submit">查询</button>' +
          '<span class="caption" style="padding-bottom:8px">id 为 16 位十六进制；可先去「影响力与社区」复制一个。</span>' +
        '</form>' +
      '</div>' +
      '<div id="profile-body"><div class="skeleton chart"></div></div>' +
    '</div>';

  const form = root.querySelector("#profile-form");
  const input = root.querySelector("#profile-id");
  const body = root.querySelector("#profile-body");
  const button = form.querySelector("button");
  let disposed = false;
  let seq = 0;
  let abort = null;

  function invalid(message) {
    body.innerHTML = '<div class="panel"><div class="empty-note">' + esc(message) + '</div></div>';
  }

  function render(data) {
    if (data.status !== "ok") {
      invalid(data.message || "没有找到这个用户。");
      return;
    }
    const p = data.profile;
    const g = data.graph;
    const profileKpis = p ? [
      { label: "粉丝数", value: num(p.fans_num), hint: "资料中记录的粉丝量" },
      { label: "性别", value: p.gender || "未知", hint: "来自用户画像" },
      { label: "所在地", value: [p.province, p.city].filter(Boolean).join(" · ") || "未知", hint: "来自用户画像" },
      { label: "会员等级", value: p.vip_level || "未知", hint: "微博会员等级" },
    ] : null;
    const graphKpis = g ? [
      { label: "被转发次数", value: num(g.in_degree), hint: "有多少人转发过他" },
      { label: "转发次数", value: num(g.out_degree), hint: "他转发过多少人" },
      { label: "PageRank", value: Number(g.pagerank).toFixed(6), hint: "全图影响力得分" },
      { label: "所属社区", value: "#" + esc(g.leiden), hint: "Leiden 社区编号" },
    ] : null;

    const outRows = data.out.rows || [];
    const inRows = data.in.rows || [];
    const outPanel = '<div class="panel"><div class="panel-head"><h2>他转发过谁</h2><span>共 ' +
      num(data.out.count) + ' 条</span></div>' + table(outRows, "没有他发出的转发记录。") + '</div>';
    const inPanel = '<div class="panel"><div class="panel-head"><h2>谁转发过他</h2><span>共 ' +
      num(data.in.count) + ' 条</span></div>' + table(inRows, "没有他被人转发的记录。") + '</div>';
    let behavior;
    if (outRows.length && inRows.length) {
      behavior = '<div class="grid-2">' + outPanel + inPanel + '</div>';
    } else if (outRows.length) {
      behavior = outPanel;
    } else if (inRows.length) {
      behavior = inPanel;
    } else {
      behavior = '<div class="panel"><div class="empty-note">没有这个用户的转发行为记录。</div></div>';
    }

    body.innerHTML =
      (p ? '<div class="section-title">用户画像 <small>' + esc(p.user_id) + '</small></div>' + kpiRow(profileKpis) : "") +
      (g ? '<div class="section-title">转发图指标 <small>来自 326 万条用户级转发边</small></div>' + kpiRow(graphKpis) : "") +
      (!p ? '<div class="notes"><p>该用户不在 2,000 万条画像样本中，只能展示转发图指标。</p></div>' : "") +
      (!g ? '<div class="notes"><p>该用户不在转发关系图中，只能展示用户画像。</p></div>' : "") +
      '<div class="section-title">转发行为 <small>每个方向只展示次数最多的 10 位</small></div>' +
      behavior +
      '<div class="notes"><p>用户画像来自 2,000 万条用户表；转发图指标与行为来自 326 万条用户级转发边。' +
      '两套数据的覆盖范围不同，因此可能出现只有其中一侧记录的情况。</p></div>';
      '两套数据的覆盖范围不同，因此可能出现只有其中一侧记录的情况。</p></div>';
  }

  async function load(uid) {
    if (!uid) {
      invalid("请输入用户 id。可以先到「影响力与社区」页面复制一个 id。");
      return;
    }
    const mine = ++seq;
    if (abort) abort.abort();
    abort = new AbortController();
    body.classList.add("is-loading");
    button.disabled = true;
    try {
      const data = await ctx.api.get("/api/profile", { user_id: uid }, { signal: abort.signal });
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
    load(input.value.trim());
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      load(input.value.trim());
    }
  });

  await load(input.value.trim());
  return () => {
    disposed = true;
    seq += 1;
    if (abort) abort.abort();
  };
}
