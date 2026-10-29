const NUM = new Intl.NumberFormat("zh-CN");
const ONE = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 });
const TWO = new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? NUM.format(n) : "N/A";
}

export function human(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "N/A";
  if (Math.abs(n) >= 1e8) return TWO.format(n / 1e8) + " 亿";
  if (Math.abs(n) >= 1e4) return ONE.format(n / 1e4) + " 万";
  return NUM.format(n);
}

export function pct(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "N/A";
  return (n * 100).toFixed(digits) + "%";
}

export function pow(value, digits = 6) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "N/A";
  return n.toExponential(digits).replace("e+", "e");
}

export function date(value) {
  if (!value) return "N/A";
  const parts = String(value).slice(0, 10).split("-");
  if (parts.length !== 3) return String(value);
  return Number(parts[1]) + "月" + Number(parts[2]) + "日";
}

export function longDate(value) {
  if (!value) return "N/A";
  const parts = String(value).slice(0, 10).split("-");
  if (parts.length !== 3) return String(value);
  return parts[0] + "-" + parts[1] + "-" + parts[2];
}

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

export function kpiCard(item) {
  const long = String(item.value ?? "").length > 10 ? " small" : "";
  return '<div class="kpi"><div class="kpi-label">' + esc(item.label) + '</div>' +
    '<div class="kpi-value' + long + '" title="' + esc(item.value) + '">' + esc(item.value) + '</div>' +
    '<div class="kpi-hint">' + esc(item.hint || "") + '</div></div>';
}

export function kpiRow(items) {
  return '<div class="kpis">' + (items || []).map(kpiCard).join("") + '</div>';
}
