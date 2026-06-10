const REFRESH_MS = 60_000;
const USE_MOCK = false;
// raw.githubusercontent 사용: jsdelivr는 쿼리스트링을 캐시 키에서 무시해 ?t= 캐시버스터가
// 안 먹히고 엣지가 s-maxage(12h) 동안 같은 사본을 내려줘 1분 신선도가 깨졌음.
// raw는 ?t= + cache:no-store 를 존중하므로 매 분 최신 스냅샷을 받는다.
const RAW_BASE = "https://raw.githubusercontent.com/ox9osub/kb-investor-flow/data";

const charts = { kospi: {}, kosdaq: {} };
let currentMarket = "kospi";
let selectedDate = todayKstDateStr();  // 지금 보고 있는 날짜 (기본: 오늘 KST)

document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  initTabs();
  initDatePicker();
  refresh();
  setInterval(refresh, REFRESH_MS);
  window.addEventListener("resize", resizeAll);
});

function initDatePicker() {
  const el = document.getElementById("datePicker");
  const today = todayKstDateStr();
  el.max = today;          // 미래 날짜 선택 불가
  el.value = today;        // 페이지를 새로 열면 항상 오늘
  selectedDate = today;
  el.addEventListener("change", () => {
    selectedDate = el.value || today;
    refresh();             // 날짜 변경 시 즉시 1회 로드
  });
}

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
  const date = selectedDate;
  const isToday = date === todayKstDateStr();
  let data;
  try {
    data = await fetchData(date, isToday);
  } catch (e) {
    console.warn("fetch failed:", e);
    return;
  }
  // 과거 날짜에 데이터가 없으면(404 등) 안내 후 종료 (Task 3에서 처리 강화)
  if (!data) { showNoData(date, isToday); return; }
  updateAllCharts(data);
  updateHeader(data.updated_at);
  const note = document.getElementById("refreshNote");
  note.textContent = isToday ? "자동 새로고침 60s" : `선택일: ${date} (과거)`;
}

// raw·jsdelivr 모두 ?t= 쿼리스트링을 캐시 키에서 무시하므로, 누적 파일은 CDN 캐시로
// 최대 5분 낡아 있다. 그래서 (1) 누적 파일로 과거 본체를 받고, (2) 그 마지막 시점 이후
// 현재 분까지의 부족분을 파일명에 시·분을 박은 분 파일(고유 URL → 캐시 우회)로 메운다.
// 메우는 개수는 캐시 TTL(약 5분)에 묶여 최대 ~6개 — 장 후반에도 늘지 않는다.
const MINUTE_FILL_MAX = 8;

async function fetchData(date, isToday) {
  if (USE_MOCK) {
    const r = await fetch("assets/mock-data.json", { cache: "no-store" });
    return r.ok ? r.json() : null;
  }

  const r = await fetch(`${RAW_BASE}/data/${date}.json?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) return null;
  const data = await r.json();

  // 오늘만 라이브 보정: 분 파일로 최신분 채우기 (INVARIANT — 오늘 경로 그대로).
  // 과거 날짜는 완성된 정적 파일이라 채우기 불필요.
  if (isToday) {
    await fillRecentMinutes(data, date);
  }
  return data;
}

function showNoData(date, isToday) {
  // 차트를 비운다 (이전 날짜 잔상 제거).
  for (const market of Object.keys(charts)) {
    for (const c of Object.values(charts[market])) c.clear();
  }
  const updated = document.getElementById("updated");
  updated.textContent = "-";
  const note = document.getElementById("refreshNote");
  note.textContent = isToday ? "장 시작 전 — 데이터 없음" : `${date} — 해당 일자 데이터 없음`;
}

// 누적 파일의 마지막 스냅샷 이후 ~ 현재 분까지를, 분 파일로 채워 넣는다.
async function fillRecentMinutes(data, date) {
  const snaps = data.snapshots;
  const lastTs = snaps.length ? snaps[snaps.length - 1].ts : null;
  const lastMin = lastTs ? hhmmToMinutes(lastTs.slice(11, 16)) : -1;
  const nowMin = hhmmToMinutes(nowKstHHMM());

  const wanted = [];
  for (let m = lastMin + 1; m <= nowMin && wanted.length < MINUTE_FILL_MAX; m++) {
    wanted.push(minutesToHHMM(m));
  }
  if (!wanted.length) return;

  const fetched = await Promise.all(wanted.map(hhmm =>
    fetch(`${RAW_BASE}/data/${date}/${hhmm}.json?t=${Date.now()}`, { cache: "no-store" })
      .then(res => res.ok ? res.json() : null)
      .catch(() => null)
  ));

  for (const snap of fetched) {
    if (snap && snap.ts) {
      snaps.push(snap);
      data.updated_at = snap.ts;
    }
  }
}

function hhmmToMinutes(hhmm) {
  const [h, m] = hhmm.split(":");
  return Number(h) * 60 + Number(m);
}

function minutesToHHMM(min) {
  const h = String(Math.floor(min / 60)).padStart(2, "0");
  const m = String(min % 60).padStart(2, "0");
  return `${h}-${m}`;  // 파일명 형식: 10-47
}

function nowKstHHMM() {
  return new Date().toLocaleTimeString("en-GB", {
    timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hour12: false,
  });  // "10:47"
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

const INDEX_LABEL = { kospi: "코스피지수", kosdaq: "코스닥지수" };

function indexValue(snap, market) {
  return snap.index?.[market]?.지수 ?? null;
}

// 매매동향 라인 차트에 우측 보조축으로 얹는 지수 시리즈 (검은 실선).
// 순매수(억원, 좌축)와 스케일이 전혀 달라 yAxisIndex:1 + scale:true로 분리.
function indexSeries(market, data) {
  return {
    name: INDEX_LABEL[market],
    type: "line",
    yAxisIndex: 1,
    smooth: true,
    showSymbol: false,
    z: 10,
    lineStyle: { color: "#000", width: 2 },
    itemStyle: { color: "#000" },
    data: data.snapshots.map(s => [s.ts, indexValue(s, market)]),
  };
}

// 좌(억원) + 우(지수) 2축. 우축은 0 기준이 아닌 실제 지수 범위로 자동 스케일.
function dualYAxis() {
  return [
    { type: "value", name: "억원" },
    { type: "value", name: "지수", position: "right", scale: true,
      splitLine: { show: false } },
  ];
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
  series.push(indexSeries(market, data));
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: [...MAIN_CATEGORIES, INDEX_LABEL[market]] },
    grid: { top: 40, left: 60, right: 60, bottom: 60 },
    xAxis: { type: "time" },
    yAxis: dualYAxis(),
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
  series.push(indexSeries(market, data));
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: [...INSTITUTION_SUBS, INDEX_LABEL[market]], type: "scroll" },
    grid: { top: 50, left: 60, right: 60, bottom: 60 },
    xAxis: { type: "time" },
    yAxis: dualYAxis(),
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
