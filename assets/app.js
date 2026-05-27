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

const INSTITUTION_SUBS = [
  "금융투자", "투신", "보험", "사모펀드",
  "은행", "기타금융", "연기금등", "국가/지자체",
];

function institutionSubNet(snap, market, sub) {
  const subs = snap[market]?.["기관"]?.세부;
  return subs && subs[sub] ? subs[sub].순매수 : null;
}

function setInstitutionLines(market, data) {
  const chart = charts[market].institutionLines;
  if (!chart) return;
  const series = INSTITUTION_SUBS.map(sub => ({
    name: sub,
    type: "line",
    smooth: true,
    showSymbol: false,
    data: data.snapshots.map(s => [s.ts, institutionSubNet(s, market, sub)]),
  }));
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: INSTITUTION_SUBS, type: "scroll" },
    grid: { top: 50, left: 60, right: 24, bottom: 60 },
    xAxis: { type: "time" },
    yAxis: { type: "value", name: "억원" },
    dataZoom: [{ type: "slider", bottom: 10, height: 20 }],
    series,
  });
}

function latestTopLevel(data, market, category) {
  const snaps = data.snapshots;
  if (!snaps.length) return null;
  return snaps[snaps.length - 1][market]?.[category] || null;
}

function setNetBar(market, data) {
  const chart = charts[market].netBar;
  if (!chart) return;
  const values = MAIN_CATEGORIES.map(cat => {
    const v = latestTopLevel(data, market, cat);
    return v ? v.순매수 : 0;
  });
  chart.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { top: 16, left: 80, right: 32, bottom: 32 },
    xAxis: { type: "value", name: "억원" },
    yAxis: { type: "category", data: MAIN_CATEGORIES, inverse: true },
    series: [{
      type: "bar",
      data: values.map(v => ({
        value: v,
        itemStyle: { color: v >= 0 ? "#43a047" : "#e53935" },
      })),
      label: { show: true, position: "right", formatter: ({value}) => value.toLocaleString() },
    }],
  });
}

function setVolumeBar(market, data) {
  const chart = charts[market].volumeBar;
  if (!chart) return;
  const sells = MAIN_CATEGORIES.map(cat => latestTopLevel(data, market, cat)?.매도 || 0);
  const buys  = MAIN_CATEGORIES.map(cat => latestTopLevel(data, market, cat)?.매수 || 0);
  chart.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, data: ["매도", "매수"] },
    grid: { top: 40, left: 60, right: 24, bottom: 32 },
    xAxis: { type: "category", data: MAIN_CATEGORIES },
    yAxis: { type: "value", name: "억원" },
    series: [
      { name: "매도", type: "bar", data: sells, itemStyle: { color: "#ef9a9a" } },
      { name: "매수", type: "bar", data: buys,  itemStyle: { color: "#a5d6a7" } },
    ],
  });
}
