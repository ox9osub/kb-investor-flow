# 날짜 피커(과거 일자 조회) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웹페이지에서 2026-05-28~오늘 범위의 특정 날짜를 선택해 그 날의 매매동향을 조회할 수 있게 하고, 페이지를 새로 열면 기본값을 항상 오늘로 한다.

**Architecture:** `index.html` 헤더에 `<input type="date">`를 추가하고, `app.js`에 전역 `selectedDate` 상태를 도입한다. `fetchData(date)`로 날짜를 파라미터화하고, `refresh()` 진입부에서 "오늘이면 라이브(누적+분파일+인터벌), 과거면 1회 정적 로드"로 분기한다. 인터벌은 끄지 않고 단일 `setInterval`을 유지한 채 진입부 가드로만 제어한다.

**Tech Stack:** Vanilla JS, ECharts 5, 정적 HTML/CSS. JS 테스트 러너 없음 → 검증은 브라우저 수동 확인(로컬 정적 서버).

**INVARIANT (최우선 제약):** 당일 라이브 갱신 경로(`fetchData`→`fillRecentMinutes`→60초 인터벌)의 동작·순서를 절대 바꾸지 않는다. `selectedDate === 오늘`일 때는 현재와 100% 동일하게 돌아야 한다. 위반 시 변경을 되돌린다.

**검증용 로컬 서버 (모든 태스크 공통):**
```bash
# 프로젝트 루트에서
python -m http.server 8000
# 브라우저로 http://localhost:8000 접속 (데이터는 raw.githubusercontent에서 실시간 fetch)
```

---

## File Structure

- `index.html` — 헤더 `.meta`에 date input 마크업 추가. (변경)
- `assets/app.js` — `selectedDate` 상태, `fetchData(date)`, onChange 핸들러, `refresh()` 분기, 헤더 표시 분기, 데이터 없음 처리. (변경)
- `assets/style.css` — date input 스타일. (변경)

각 태스크는 독립적으로 동작·검증 가능한 단위로 나눈다. Task 1(마크업) → Task 2(상태/분기 로직) → Task 3(과거/없음 표시) → Task 4(헤더 문구) → Task 5(스타일) 순.

---

### Task 1: 헤더에 날짜 피커 마크업 추가

**Files:**
- Modify: `index.html:12-18` (헤더 `.meta` 블록)

- [ ] **Step 1: `.meta` 블록에 date input 추가**

`index.html`의 기존 `.meta` 블록:
```html
    <div class="meta">
      <span>마지막 업데이트: <time id="updated">-</time> KST</span>
      <span class="sep">|</span>
      <span>단위: 억원</span>
      <span class="sep">|</span>
      <span>자동 새로고침 60s</span>
    </div>
```
를 다음으로 교체한다:
```html
    <div class="meta">
      <span>마지막 업데이트: <time id="updated">-</time> KST</span>
      <span class="sep">|</span>
      <span>단위: 억원</span>
      <span class="sep">|</span>
      <label class="date-pick">날짜:
        <input type="date" id="datePicker" min="2026-05-28" />
      </label>
      <span class="sep">|</span>
      <span id="refreshNote">자동 새로고침 60s</span>
    </div>
```
(주의: `max`와 기본 `value`는 JS가 설정하므로 HTML에는 넣지 않는다. `id="refreshNote"`는 Task 4에서 문구를 바꾸기 위한 핸들.)

- [ ] **Step 2: 브라우저로 마크업 확인**

로컬 서버를 띄우고 `http://localhost:8000` 접속.
Expected: 헤더에 날짜 입력 박스가 보인다. 아직 기본값/동작은 없어도 됨(다음 태스크). 기존 차트·자동 갱신은 그대로 동작해야 함.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(ui): add date picker input to header"
```

---

### Task 2: selectedDate 상태 + fetchData 파라미터화 + refresh 분기

**Files:**
- Modify: `assets/app.js:8-9` (전역 상태)
- Modify: `assets/app.js:11-17` (DOMContentLoaded)
- Modify: `assets/app.js:54-86` (refresh, fetchData)

INVARIANT 보존이 핵심. 오늘 경로의 내부 호출 순서를 그대로 두고 분기만 감싼다.

- [ ] **Step 1: 전역에 selectedDate 추가**

`assets/app.js`의:
```js
const charts = { kospi: {}, kosdaq: {} };
let currentMarket = "kospi";
```
뒤에 다음 줄을 추가:
```js
let selectedDate = todayKstDateStr();  // 지금 보고 있는 날짜 (기본: 오늘 KST)
```
(`todayKstDateStr`은 파일 하단에 이미 정의돼 있으므로 호이스팅된 function 선언이라 사용 가능.)

- [ ] **Step 2: DOMContentLoaded에서 피커 초기화 + onChange 연결**

기존:
```js
document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  initTabs();
  refresh();
  setInterval(refresh, REFRESH_MS);
  window.addEventListener("resize", resizeAll);
});
```
를 다음으로 교체:
```js
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
```

- [ ] **Step 3: refresh를 오늘/과거로 분기**

기존:
```js
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
```
를 다음으로 교체:
```js
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
}
```
(`showNoData`는 Task 3에서 정의. 이 단계 커밋 전 Task 3까지 함께 진행하거나, 임시로 `function showNoData(){}` 빈 정의를 같이 넣어 동작시킨다. 아래 Step 4에서 임시 정의 포함.)

- [ ] **Step 4: fetchData를 파라미터화 (오늘 경로는 기존과 동일)**

기존:
```js
async function fetchData() {
  if (USE_MOCK) {
    const r = await fetch("assets/mock-data.json", { cache: "no-store" });
    return r.ok ? r.json() : null;
  }

  const date = todayKstDateStr();
  const r = await fetch(`${RAW_BASE}/data/${date}.json?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) return null;
  const data = await r.json();

  await fillRecentMinutes(data, date);
  return data;
}
```
를 다음으로 교체:
```js
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

// Task 3에서 본문 구현. 우선 빈 정의로 두어 refresh가 동작하게 한다.
function showNoData(date, isToday) {}
```
(오늘 경로: `isToday === true`이면 `fillRecentMinutes(data, date)`가 기존과 동일 인자·순서로 호출됨 → INVARIANT 충족.)

- [ ] **Step 5: 브라우저 검증 — 오늘 라이브 유지 + 과거 로드**

로컬 서버에서 `http://localhost:8000` 접속.
Expected:
1. 기본값 오늘, 차트가 평소처럼 그려지고 60초 후 자동 갱신·"마지막 업데이트" 시각이 갱신됨 (INVARIANT 확인).
2. 날짜를 과거(예: 2026-05-28)로 바꾸면 그 날 누적 데이터가 즉시 1회 로드됨.
3. 콘솔 Network 탭에서 과거 날짜일 때 `data/<날짜>/HH-MM.json`(분 파일) 요청이 **발생하지 않음** 확인.
4. 과거→오늘로 되돌리면 라이브가 재개됨.

- [ ] **Step 6: Commit**

```bash
git add assets/app.js
git commit -m "feat(date): selectedDate state, parameterized fetch, today/past branch"
```

---

### Task 3: 데이터 없는 날 처리 (showNoData)

**Files:**
- Modify: `assets/app.js` (Task 2에서 추가한 빈 `showNoData` 본문 구현)

- [ ] **Step 1: showNoData 본문 구현 + 차트 비우기**

Task 2 Step 4에서 넣은:
```js
// Task 3에서 본문 구현. 우선 빈 정의로 두어 refresh가 동작하게 한다.
function showNoData(date, isToday) {}
```
를 다음으로 교체:
```js
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
```
(차트를 `clear()`하면 빈 캔버스가 된다. 데이터가 다시 들어오면 `updateAllCharts`의 `setOption`이 다시 그린다.)

- [ ] **Step 2: 브라우저 검증 — 데이터 없는 날**

로컬 서버 접속 후, 데이터가 없는 날짜를 선택(예: 주말 — 2026-05-30(토) 또는 데이터 시작 전이 아닌 주말 일자).
Expected:
1. 콘솔 오류 없이 차트가 비워지고, 헤더에 "<날짜> — 해당 일자 데이터 없음" 표시.
2. 데이터 있는 평일로 다시 바꾸면 정상적으로 차트가 그려짐.

- [ ] **Step 3: Commit**

```bash
git add assets/app.js
git commit -m "feat(date): show 'no data' message and clear charts for empty days"
```

---

### Task 4: 헤더 새로고침 문구 분기 (오늘 vs 과거)

**Files:**
- Modify: `assets/app.js` (`refresh` 성공 경로에서 문구 갱신)

- [ ] **Step 1: 데이터 정상 로드 시 refreshNote 갱신**

Task 2에서 만든 `refresh`의 성공 경로:
```js
  if (!data) { showNoData(date, isToday); return; }
  updateAllCharts(data);
  updateHeader(data.updated_at);
```
를 다음으로 교체:
```js
  if (!data) { showNoData(date, isToday); return; }
  updateAllCharts(data);
  updateHeader(data.updated_at);
  const note = document.getElementById("refreshNote");
  note.textContent = isToday ? "자동 새로고침 60s" : `선택일: ${date} (과거)`;
```

- [ ] **Step 2: 브라우저 검증 — 문구 전환**

로컬 서버 접속.
Expected:
1. 오늘일 때 헤더 문구 "자동 새로고침 60s".
2. 과거(데이터 있는 평일)로 바꾸면 "선택일: <날짜> (과거)".
3. 과거→오늘 복귀 시 다시 "자동 새로고침 60s"로 돌아옴.

- [ ] **Step 3: Commit**

```bash
git add assets/app.js
git commit -m "feat(date): header note switches between live and past-date label"
```

---

### Task 5: 날짜 피커 스타일

**Files:**
- Modify: `assets/style.css:6-7` (`.meta` 관련 규칙 인근에 추가)

- [ ] **Step 1: date input 스타일 추가**

`assets/style.css`의:
```css
.site-header .meta .sep { margin: 0 8px; color: #ccc; }
```
바로 뒤에 다음을 추가:
```css
.site-header .meta .date-pick { color: #666; }
.site-header .meta .date-pick input { font-size: 12px; padding: 1px 4px; margin-left: 4px; border: 1px solid #d5d5d5; border-radius: 3px; color: #1a1a1a; background: #fff; cursor: pointer; }
```

- [ ] **Step 2: 브라우저 검증 — 정렬/모양**

로컬 서버 접속.
Expected: 날짜 입력 박스가 메타 줄에 자연스럽게 정렬되고, 모바일 폭(768px 이하)에서도 깨지지 않음.

- [ ] **Step 3: Commit**

```bash
git add assets/style.css
git commit -m "style(date): style the header date picker input"
```

---

## Self-Review (작성자 점검 결과)

**1. Spec coverage:**
- 선택 범위 2026-05-28~오늘 → Task 1(`min`), Task 2(`max`=today). ✅
- 기본값 오늘 → Task 2 Step 2 (`el.value = today`). ✅
- 오늘=라이브 / 과거=정적 1회 → Task 2 Step 3·4 분기. ✅
- INVARIANT(오늘 경로 보존) → Task 2 Step 4에서 `isToday` 시 기존과 동일 호출. ✅
- 데이터 없는 날 처리 → Task 3. ✅
- 헤더 문구 분기 → Task 4. ✅
- 변경 파일 3개 → Task 1~5에 모두 포함. ✅

**2. Placeholder scan:** Task 2에서 `showNoData` 빈 정의를 의도적으로 두지만, Task 3에서 실제 본문으로 교체하도록 명시 + 코드 제공. TBD/추상 지시 없음. ✅

**3. Type/이름 일관성:**
- `selectedDate`, `fetchData(date, isToday)`, `showNoData(date, isToday)`, `refresh()`, `initDatePicker()` — 정의·호출 시그니처 일치. ✅
- DOM id: `datePicker`, `refreshNote`, `updated` — HTML(Task 1)과 JS(Task 2~4) 일치. ✅
- `todayKstDateStr`, `fillRecentMinutes`, `updateAllCharts`, `updateHeader` — 기존 함수, 그대로 사용. ✅
