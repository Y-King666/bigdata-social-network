export const COLORS = {
  primary: "#C0392B",
  secondary: "#1F3A5F",
  accent: "#E8A33D",
  green: "#2E8B57",
  violet: "#7D5BA6",
  teal: "#0E8B8B",
  muted: "#6B7280",
  grid: "#EEF0F3",
  axis: "#D1D5DB",
};

const CONFIG = {
  responsive: true,
  displaylogo: false,
  topojsonURL: "/vendor/topojson/",
  modeBarButtonsToRemove: [
    "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
    "hoverClosestCartesian", "hoverCompareCartesian",
  ],
};

let loading = null;

export function ensurePlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/vendor/plotly.min.js";
    script.async = true;
    script.onload = () => window.Plotly ? resolve(window.Plotly) : reject(new Error("Plotly 加载失败"));
    script.onerror = () => reject(new Error("Plotly 资源加载失败"));
    document.head.appendChild(script);
  });
  return loading;
}

function merge(base, extra) {
  const out = { ...base };
  for (const [key, value] of Object.entries(extra || {})) {
    if (value && typeof value === "object" && !Array.isArray(value) && base[key] && typeof base[key] === "object") {
      out[key] = merge(base[key], value);
    } else {
      out[key] = value;
    }
  }
  return out;
}

export function baseLayout(extra = {}) {
  const base = {
    font: { family: '"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif', size: 11, color: "#4B5563" },
    margin: { l: 54, r: 54, t: 14, b: 42 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    hovermode: "x unified",
    hoverlabel: { bgcolor: "#FFFFFF", bordercolor: "#D1D5DB", font: { color: "#1F2937", size: 11 } },
    xaxis: {
      gridcolor: COLORS.grid, zeroline: false, linecolor: COLORS.axis,
      tickfont: { size: 10 }, automargin: true,
    },
    yaxis: {
      gridcolor: COLORS.grid, zeroline: false, linecolor: COLORS.axis,
      tickfont: { size: 10 }, automargin: true,
    },
    legend: { orientation: "h", x: 0, y: 1.12, font: { size: 11 } },
    bargap: 0.3,
  };
  return merge(base, extra);
}

export async function render(element, traces, layout = {}) {
  await ensurePlotly();
  if (!element || !element.isConnected) return;
  await window.Plotly.react(element, traces, baseLayout(layout), CONFIG);
}

export function purge(element) {
  if (element && window.Plotly) {
    try { window.Plotly.purge(element); } catch (err) { /* 已移除的节点无需清理 */ }
  }
}
