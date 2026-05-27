const REFRESH_MS = 60_000;
const USE_MOCK = true;
const RAW_BASE = "https://raw.githubusercontent.com/<USER>/<REPO>/data";

const charts = { kospi: {}, kosdaq: {} };
let currentMarket = "kospi";

document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  initTabs();
  refresh();
  setInterval(refresh, REFRESH_MS);
  window.addEventListener("resize", resizeAll);
});

function initCharts() {
  document.querySelectorAll(".market-panel").forEach(panel => {
    const market = panel.dataset.market;
    panel.querySelectorAll(".chart").forEach(el => {
      const key = el.dataset.chart;
      charts[market][key] = echarts.init(el);
    });
  });
}

function initTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const market = tab.dataset.market;
      if (market === currentMarket) return;
      currentMarket = market;
      document.querySelectorAll(".tab").forEach(t => {
        const active = t.dataset.market === market;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", String(active));
      });
      document.querySelectorAll(".market-panel").forEach(p => {
        p.classList.toggle("hidden", p.dataset.market !== market);
      });
      requestAnimationFrame(resizeAll);
    });
  });
}

function resizeAll() {
  for (const market of Object.keys(charts)) {
    for (const c of Object.values(charts[market])) c.resize();
  }
}

async function refresh() {
  let data;
  try {
    data = await fetchData();
  } catch (e) {
    console.warn("fetch failed:", e);
    return;
  }
  if (!data) return;
  updateAllCharts(data);
  updateHeader(data.updated_at);
}

async function fetchData() {
  const url = USE_MOCK
    ? "assets/mock-data.json"
    : `${RAW_BASE}/data/${todayKstDateStr()}.json?t=${Date.now()}`;
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) return null;
  return r.json();
}

function todayKstDateStr() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

function updateHeader(updatedAt) {
  const el = document.getElementById("updated");
  if (!updatedAt) { el.textContent = "-"; return; }
  el.textContent = updatedAt.slice(11, 19);
}

function updateAllCharts(data) {
  for (const market of ["kospi", "kosdaq"]) {
    setMainLines(market, data);
    setInstitutionLines(market, data);
    setNetBar(market, data);
    setVolumeBar(market, data);
  }
}

const MAIN_CATEGORIES = ["외국인", "개인", "기관", "기타법인"];

const COLOR = {
  "외국인":   "#1976d2",
  "개인":     "#43a047",
  "기관":     "#e64a19",
  "기타법인": "#8e24aa",
};

function topLevelNet(snap, market, category) {
  const v = snap[market]?.[category];
  return v ? v.순매수 : null;
}

function setMainLines(market, data) {
  const chart = charts[market].mainLines;
  if (!chart) return;
  const series = MAIN_CATEGORIES.map(cat => ({
    name: cat,
    type: "line",
    smooth: true,
    showSymbol: false,
    itemStyle: { color: COLOR[cat] },
    data: data.snapshots.map(s => [s.ts, topLevelNet(s, market, cat)]),
  }));
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: MAIN_CATEGORIES },
    grid: { top: 40, left: 60, right: 24, bottom: 60 },
    xAxis: { type: "time" },
    yAxis: { type: "value", name: "억원" },
    dataZoom: [{ type: "slider", bottom: 10, height: 20 }],
    series,
  });
}
function setInstitutionLines() {}
function setNetBar() {}
function setVolumeBar() {}
