import { api } from "./api.js";
import * as format from "./format.js";
import * as charts from "./charts.js";

const PAGES = {
  "/live": { title: "监测大屏", module: "./pages/live.js" },
  "/overview": { title: "数据概览", module: "./pages/overview.js" },
  "/geo": { title: "空间热点", module: "./pages/geo.js" },
  "/topics": { title: "热点话题", module: "./pages/topics.js" },
  "/cascade": { title: "传播分析", module: "./pages/cascade.js" },
  "/influence": { title: "影响力与社区", module: "./pages/influence.js" },
  "/profile": { title: "用户画像查询", module: "./pages/profile.js" },
  "/relations": { title: "关系发现", module: "./pages/relations.js" },
  "/simulate": { title: "传播模拟", module: "./pages/simulate.js" },
};

const view = document.getElementById("view");
let active = null;
let currentRoute = null;

function skeleton() {
  return '<div class="page"><div class="skeleton" style="width:260px;height:34px;margin-bottom:14px"></div>' +
    '<div class="skeleton" style="width:620px;height:14px;margin-bottom:28px"></div>' +
    '<div class="kpis">' + '<div class="skeleton kpi"></div>'.repeat(4) + '</div>' +
    '<div class="skeleton chart"></div></div>';
}

function showError(message, route) {
  view.innerHTML = '<div class="page"><div class="error-box">' + format.esc(message) +
    '<button type="button" data-retry>重新加载</button></div></div>';
  view.querySelector("[data-retry]").addEventListener("click", () => render(route, false));
}

function setActive(route) {
  document.querySelectorAll(".nav a[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
}

function scrollTop() {
  document.querySelector(".main").scrollTo({ top: 0, behavior: "auto" });
}

async function render(route, push) {
  if (!PAGES[route]) {
    route = "/overview";
    history.replaceState({ route }, "", route);
  }
  if (push) history.pushState({ route }, "", route);
  if (active && active.destroy) active.destroy();
  if (active && active.controller) active.controller.abort();
  active = null;
  currentRoute = route;
  setActive(route);
  document.title = PAGES[route].title + " · 社交网络分析系统";
  scrollTop();

  const controller = new AbortController();
  active = { controller, destroy: null };
  view.innerHTML = skeleton();
  try {
    const mod = await import(PAGES[route].module);
    if (controller.signal.aborted || currentRoute !== route) return;
    const destroy = await mod.mount(view, {
      api, charts, format, route, navigate,
      signal: controller.signal,
      pageTitle: PAGES[route].title,
    });
    if (controller.signal.aborted || currentRoute !== route) {
      if (typeof destroy === "function") destroy();
      return;
    }
    active = { controller, destroy };
  } catch (err) {
    if (err && err.name === "AbortError") return;
    console.error(err);
    if (currentRoute === route) showError(err.message || "页面加载失败", route);
  }
}

function navigate(route, push = true) {
  if (route === currentRoute) return;
  render(route, push);
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-link]");
  if (!link) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  navigate(link.dataset.route || link.getAttribute("href"), true);
});

window.addEventListener("popstate", () => {
  const route = PAGES[location.pathname] ? location.pathname : "/overview";
  render(route, false);
});

const initial = PAGES[location.pathname] ? location.pathname : "/overview";
history.replaceState({ route: initial }, "", initial);
render(initial, false);