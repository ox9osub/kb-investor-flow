# KB 투자자별 매매동향 실시간 대시보드 — 설계 문서

- **작성일:** 2026-05-27
- **상태:** Draft (사용자 검토 대기)
- **저자:** 브레인스토밍 세션 (Claude + 사용자)
- **플레이스홀더:** `<USER>` = GitHub username, `<REPO>` = 리포명 (구현 단계에서 확정)

---

## 1. 개요

### 1.1 목표

KB증권 "투자자별 매매동향" 페이지(https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0)의
KOSPI/KOSDAQ 데이터를 한국 정규 장중(평일 09:00–15:30 KST) 1분 간격으로 수집하여, 무료
정적 웹 대시보드(GitHub Pages)에서 시계열·스냅샷 차트로 시각화한다.

### 1.2 핵심 제약

- **무료 호스팅** — GitHub (Repo + Pages) 외 추가 비용 없음.
- **정확히 1분 주기** — GitHub Actions의 스케줄 지연(분 단위 흔들림)이 허용되지 않음. 로컬 PC의
  Windows Task Scheduler가 정확한 1분 트리거를 보장.
- **봇 차단 회피** — 로컬 PC가 일반 HTTP 클라이언트로 호출 (현재 KB 페이지는 로그인·봇 차단 없음, 검증 완료).

### 1.3 비목표 (Out of Scope, v1)

- 휴장일 자동 감지 (한국 공휴일 캘린더) — v1은 평일 트리거하되 응답값 동일하면 그대로 기록.
- 알림(Slack/이메일) — 파싱 실패 시 stderr 로그만.
- 과거 날짜 조회 UI — 데이터는 일별로 보존되지만 v1 대시보드는 "오늘"만 표시.
- 종목별 매매 상위 N — 페이지의 11개 투자자 분류 데이터만 사용.
- 모바일 앱 / PWA — 반응형 정적 사이트로 충분.
- 데이터 백필(과거 데이터 가져오기) — 시작일 이후만 수집.
- 사용자 인증·다중 사용자 — 공개 대시보드.

---

## 2. 시스템 아키텍처

```
┌────────────────────────────────────────────────────────────────┐
│  Local Windows PC                                              │
│                                                                │
│  Windows Task Scheduler                                        │
│  ├─ 트리거: 평일 09:00~15:30, 매 1분                            │
│  └─ 동작: python collect.py                                    │
│                                                                │
│        collect.py:                                             │
│          1. GET KOSPI 페이지   (gubun=0, ~5KB)                 │
│          2. GET KOSDAQ 페이지  (gubun=1, ~5KB)                 │
│          3. EUC-KR 디코드 → BeautifulSoup 파싱                  │
│          4. data/YYYY-MM-DD.json 로드 → snapshot append → 저장 │
│          5. git add + commit + push (data 브랜치)              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                          │ git push (every 1 min)
                          ▼
┌────────────────────────────────────────────────────────────────┐
│  GitHub Repo: <USER>/<REPO>                                    │
│                                                                │
│  main 브랜치 (사이트, 거의 변경 없음, Pages 소스)               │
│   ├── index.html, assets/, collect/                            │
│                                                                │
│  data 브랜치 (orphan, 매분 푸시, Pages 미감지)                  │
│   └── data/YYYY-MM-DD.json                                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
        │ Pages serves main                  │ raw.githubusercontent serves data
        ▼                                    ▼
┌────────────────────────────────────────────────────────────────┐
│  사용자 브라우저                                                 │
│  https://<USER>.github.io/<REPO>/                              │
│                                                                │
│  app.js: setInterval(60s, fetch(raw URL + ?t=Date.now()))      │
│          → ECharts setOption 갱신                              │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 핵심 아키텍처 결정

| 결정 | 이유 |
|---|---|
| **사이트와 데이터를 다른 브랜치로 분리** (main / data orphan) | data 브랜치 푸시는 Pages 빌드를 트리거하지 않음 → 매분 푸시 가능 + main 히스토리 깨끗. |
| **데이터는 raw.githubusercontent.com에서 fetch** | Pages 빌드 우회 + CORS 허용. `?t=<unix>` 쿼리스트링으로 Fastly CDN 캐시버스팅 → 1분 내 신선도. |
| **Task Scheduler 1분 트리거** (long-running daemon 아님) | 각 실행이 독립 → 크래시/재부팅 자가 회복. Python cold start ~2초 무시 가능. |
| **데이터 파일 매분 덮어쓰기** (JSONL append 아님) | 대시보드가 단일 fetch로 전일 분량 수신. 브라우저 측 파싱 단순. |
| **로컬 git worktree** (main + data 동시 체크아웃) | 한 클론으로 두 브랜치 분리 작업. 수집기는 `data\` worktree만 만짐. |

---

## 3. 데이터 추출 (KB 페이지 분석 결과)

### 3.1 페이지 특성 (2026-05-27 확인)

| 항목 | 내용 |
|---|---|
| 렌더링 방식 | 서버사이드 HTML (SPA 아님 — JS 실행 불필요) |
| 인코딩 | EUC-KR |
| 보호 | 로그인/봇 차단 없음, `WebClient.DownloadData` 1회 호출 시 200 OK |
| 페이지 크기 | 약 5KB |
| 시장 구분 | URL 파라미터 `gubun=0`(KOSPI), `gubun=1`(KOSDAQ) |
| 응답 구조 | 단일 `<tbody>` 내 11행 × 4컬럼 (구분 / 매도 / 매수 / 순매수, 단위: 억원) |

### 3.2 11개 투자자 분류 (시장별 동일 구조)

```
외국인
개인
기관계 (소계)
  - 금융투자
  - 투신
  - 보험
  - 사모펀드
  - 은행
  - 기타금융
  - 연기금등
  - 국가/지자체
기타법인
```

### 3.3 파싱 전략

- `requests.get(url)` + `response.encoding = 'euc-kr'`
- `BeautifulSoup(response.text, 'html.parser')`
- `<table>` 안의 `<tr>` 순회 → `<td class="tL">` 으로 카테고리명, 나머지 `<td class="tR">` 로 매도/매수/순매수
- 숫자 파싱: 쉼표 제거 후 `int()`. 텍스트 자체에 부호 포함됨 (예: `-778`, `0`, `3791`).
  `stockUp`/`stockDw` class는 색상 힌트일 뿐 부호 판정에 사용 안 함.
- 세부 카테고리는 텍스트 앞에 `- ` 접두사 (예: `- 금융투자`) → 접두사 strip하여 키로.
- **카테고리명 정규화**: KB 페이지의 `기관계`는 스키마에서 `기관`으로 키 변경 (다른 카테고리는 페이지 표기 그대로).

---

## 4. 데이터 스키마

### 4.1 일별 파일 (`data/YYYY-MM-DD.json`)

```json
{
  "date": "2026-05-27",
  "unit": "억원",
  "source": {
    "kospi":  "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0",
    "kosdaq": "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=1"
  },
  "updated_at": "2026-05-27T15:30:12+09:00",
  "snapshots": [
    {
      "ts": "2026-05-27T09:00:12+09:00",
      "kospi": {
        "외국인":   { "매도": 62198, "매수": 61420, "순매수": -778 },
        "개인":     { "매도": 94465, "매수": 91684, "순매수": -2781 },
        "기관":     {
          "매도": 51817, "매수": 56083, "순매수": 4266,
          "세부": {
            "금융투자":   { "매도": 23741, "매수": 27532, "순매수": 3791 },
            "투신":       { "매도": 2307,  "매수": 1601,  "순매수": -705 },
            "보험":       { "매도": 330,   "매수": 181,   "순매수": -149 },
            "사모펀드":   { "매도": 2032,  "매수": 2082,  "순매수": 49 },
            "은행":       { "매도": 57,    "매수": 24,    "순매수": -33 },
            "기타금융":   { "매도": 55,    "매수": 31,    "순매수": -24 },
            "연기금등":   { "매도": 23294, "매수": 24632, "순매수": 1337 },
            "국가/지자체": { "매도": 0,    "매수": 0,     "순매수": 0 }
          }
        },
        "기타법인": { "매도": 2188, "매수": 1482, "순매수": -706 }
      },
      "kosdaq": { /* 동일 구조 */ }
    }
  ]
}
```

### 4.2 스키마 결정 근거

| 결정 | 이유 |
|---|---|
| 키를 한국어로 (영문 매핑 안 함) | KB 페이지의 카테고리는 한국 시장 고유 용어. 영문 변환 시 의미 손실. JSON/JS는 유니코드 키 정상 지원. |
| 기관 = 합계(매도/매수/순매수) + 세부 트리 | 페이지 자체가 합계 + 8개 들여쓰기 자식 구조. 동일하게 표현해 의미 보존. 차트 토글 용이. |
| 단위는 최상위에 한 번만 | 모든 숫자가 억원. 행마다 반복하면 노이즈. |
| 타임스탬프 ISO 8601 + KST 오프셋 | JS `Date`가 그대로 파싱. `HH:MM:SS`만 쓰는 절약(~6KB)은 무의미. |
| snapshots는 시간 순 배열 | 차트가 그대로 `.map(s => [s.ts, s.kospi.외국인.순매수])` 형태로 소비. |
| `updated_at` 최상위 별도 필드 | 헤더 "마지막 업데이트" 표시용. 마지막 snapshot ts 읽는 것보다 단순. |

### 4.3 크기 추정

| 항목 | 값 |
|---|---|
| 분당 snapshot 크기 (minified) | ~700 bytes |
| 일간 파일 크기 (390 snapshot) | ~270 KB |
| gzip 압축 후 | ~30 KB |
| 연간 누적 (250 영업일) | ~70 MB |

---

## 5. 대시보드 UI

### 5.1 화면 구성 (데스크톱)

```
┌──────────────────────────────────────────────────────────────────┐
│ KB 투자자별 매매동향 실시간                                        │
│ 마지막 업데이트: 14:32:12 KST | 단위: 억원 | 자동 새로고침 60s    │
├──────────────────────────────────────────────────────────────────┤
│ [ KOSPI ]  [ KOSDAQ ]   ← 탭                                      │
├──────────────────────────────────────────────────────────────────┤
│ ① 주요 4분류 순매수 추이 (라인)                                    │
│   외국인 / 개인 / 기관 / 기타법인 — 4 lines                         │
│                                                                   │
│ ② 기관 세부 8분류 순매수 추이 (라인)                               │
│   금융투자 / 투신 / 보험 / 사모펀드 / 은행 / 기타금융 / 연기금등 / │
│   국가/지자체 — 8 lines                                            │
│                                                                   │
│ ③ 현재 순매수 스냅샷 (수평 막대)                                   │
│   주요 4분류 + 양/음 색 구분                                       │
│                                                                   │
│ ④ 매도 vs 매수 현재 비교 (그룹 막대)                               │
│   주요 4분류, 각 카테고리당 매도/매수 두 막대                      │
└──────────────────────────────────────────────────────────────────┘
```

모바일: 탭 유지, ③④는 위아래로 적층.

### 5.2 차트별 책임

| 차트 | 시각화 데이터 | 답하는 질문 |
|---|---|---|
| ① 라인 (주요 4분류) | 순매수 시계열 | "오늘 외국인은 어느 시점부터 사기 시작했나?" |
| ② 라인 (기관 세부 8) | 순매수 시계열 | "기관 매도세 중 연기금이 차지하는 비중은?" |
| ③ 수평 막대 (현재) | 현재 순매수 스냅샷 | "지금 누가 사고 누가 파나?" |
| ④ 그룹 막대 (매도 vs 매수) | 현재 거래 규모 | "외국인 거래량이 평소 대비 큰가?" |

4개 차트가 매도·매수·순매수 × 11카테고리 × 시간축을 전부 커버.

### 5.3 인터랙션 (ECharts 표준 기능)

- **호버 툴팁**: 모든 시리즈의 그 시점 값을 한꺼번에 표시
- **범례 토글**: 라인 이름 클릭 → 시리즈 숨김/표시
- **dataZoom 슬라이더**: 차트 하단 시간 슬라이더로 09:00~현재 구간 자유 확대

### 5.4 자동 갱신 로직 (`app.js` 의사코드)

```js
const REFRESH_MS = 60_000;
const RAW_BASE = "https://raw.githubusercontent.com/<USER>/<REPO>/data";

async function refresh() {
  const today = new Date().toLocaleDateString("sv-SE", {timeZone: "Asia/Seoul"});  // YYYY-MM-DD
  const url = `${RAW_BASE}/data/${today}.json?t=${Date.now()}`;
  const r = await fetch(url);
  if (!r.ok) return;  // 장중 외 시간엔 파일 없음 — 조용히 무시
  const data = await r.json();
  updateCharts(data);            // 4개 차트 각각 setOption({series: [...]}, false)
  updateHeaderTimestamp(data.updated_at);
}

refresh();
setInterval(refresh, REFRESH_MS);
```

### 5.5 차트 갱신 시 깜빡임 방지

- `chart.dispose()` 호출 안 함
- `chart.setOption(newOpts, false)` — `notMerge=false` 로 series 데이터만 교체, axis/legend/dataZoom 위치 유지
- ECharts 5는 내부적으로 diff 갱신하여 부드럽게 트랜지션

---

## 6. 디렉토리 구조

### 6.1 GitHub 리포 (main 브랜치)

```
<REPO>/
├── index.html
├── assets/
│   ├── app.js
│   └── style.css
├── collect/
│   ├── collect.py
│   ├── requirements.txt        # requests, beautifulsoup4
│   └── README.md
├── docs/
│   └── superpowers/specs/      # 이 문서
├── .gitignore
└── README.md
```

ECharts는 CDN(`https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js`) 직접 로드 — `node_modules` 없이 순수 정적 사이트.

### 6.2 GitHub 리포 (data 브랜치, orphan)

```
(orphan root)
├── README.md                  # "자동 생성된 데이터 브랜치 — 직접 수정 금지"
└── data/
    ├── 2026-05-27.json
    ├── 2026-05-26.json
    └── ...
```

### 6.3 로컬 PC 디렉토리

```
C:\Users\suble\Desktop\work\project\kb-investor-flow\
├── main\              # git clone — 개발 + 사이트 작업
│   ├── index.html
│   ├── assets\
│   ├── collect\
│   │   └── collect.py
│   └── docs\superpowers\specs\<이 문서>
└── data\              # git worktree add ../data data — 수집기 전용
    └── data\
        └── 2026-05-27.json
```

---

## 7. 셋업 (일회성)

```
1. GitHub에 <REPO> 리포 생성 (public)
2. 로컬 clone:
   git clone git@github.com:<USER>/<REPO>.git main
3. main에 초기 파일 푸시 (스켈레톤 index.html + collect.py)
4. data orphan 브랜치 생성:
   cd main
   git checkout --orphan data
   git rm -rf .
   echo "Auto-generated data branch" > README.md
   git add README.md
   git commit -m "init data branch"
   git push -u origin data
   git checkout main
5. data worktree 추가:
   git worktree add ../data data
6. Python 의존성:
   cd collect
   pip install -r requirements.txt
7. GitHub 인증 (PAT → Windows Credential Manager 또는 SSH 키)
8. 첫 수집 검증:
   python collect.py --dry-run    # 파싱 결과 stdout만, 푸시 안 함
   python collect.py              # 실제 실행
9. Task Scheduler 등록:
   - 트리거: 매일 09:00 시작, 1분 반복, 15:30까지, 평일만
   - 동작: python.exe ...\collect\collect.py
   - 시작 위치: ...\data\
   - 콘솔 숨김
10. GitHub Pages 활성화:
    Settings → Pages → Source: main, Folder: /
```

---

## 8. 운영

### 8.1 정상 흐름 (장중, 1분 사이클 약 5초)

```
14:32:00  Task Scheduler 트리거
14:32:01  python collect.py 시작
14:32:02  GET kospi + kosdaq (병렬, ~300ms)
14:32:02  파싱 → snapshot dict
14:32:02  data\data\2026-05-27.json 로드 (있으면), append, 저장
14:32:03  git add + commit + push (data 브랜치)
14:32:05  완료
14:32:35  raw.githubusercontent.com 반영
14:33:00  대시보드 fetch → 새 snapshot 표시
```

### 8.2 오류 시나리오

| 시나리오 | 동작 |
|---|---|
| KB 페이지 5xx | 5초 후 1회 재시도 → 실패 시 그 분 스킵 |
| 파싱 실패 (페이지 구조 변경) | 그 분 스킵, stderr 로그 — 수동 조사 필요 |
| git push 네트워크 실패 | 로컬 커밋만 누적, 다음 분이 같이 푸시 |
| git push 충돌 | `git pull --rebase` 후 재시도 |
| PC 재부팅 | Task Scheduler 부팅 후 정상 트리거 |
| PC 장기간 꺼짐 | 그 시간 데이터 갭 → 차트는 자연스러운 빈 구간 |
| 한국 휴장일 (평일 공휴일) | v1: 트리거되지만 응답값 변화 없음 → 평평한 라인. v2에서 캘린더 추가. |

### 8.3 일별 파일 리셋

장 시작 후 첫 호출에서 `data/YYYY-MM-DD.json` 없으면 새로 생성. 자정 수동 리셋 작업 불필요.
전일 파일은 git에 동결 보존 — 향후 과거 조회 기능에 활용 가능.

---

## 9. 테스트 전략

### 9.1 단위 테스트 (`collect/test_parse.py`)

- KB 응답 HTML 픽스처(여러 시점 캡처본) 저장 → 파싱 함수가 기대 dict 반환하는지
- 음수/0/큰 숫자 케이스
- 페이지 구조 변경 시 파싱 실패가 명확한 예외로 표면화되는지

### 9.2 통합 테스트

- `python collect.py --dry-run` — 실제 KB 호출, 파싱, stdout 출력 (git 안 건드림)
- `python collect.py --once` — 1회 실제 실행, data 파일 확인, git status 확인

### 9.3 대시보드 시각 확인

- 로컬에서 `python -m http.server 8000` → 브라우저에서 `localhost:8000/index.html`
- 차트 4종이 정상 렌더되는지 (정적 픽스처 JSON으로 먼저)
- 60초 후 fetch 호출이 일어나는지 (DevTools Network 탭 확인)
- KOSPI ↔ KOSDAQ 탭 전환이 동작하는지
- 모바일 viewport(375px)에서 레이아웃이 적층되는지

### 9.4 운영 확인 (Day 1)

- Task Scheduler가 09:00~15:30 정확히 매분 트리거되는지 (이벤트 로그 확인)
- 첫 영업일 종료 후 `data/<오늘>.json`에 ~390 snapshot이 들어있는지
- 다음날 09:00 첫 호출 시 새 파일이 생성되는지

---

## 10. Open Items (구현 단계에서 확정)

- [ ] GitHub username (`<USER>`) 및 리포명 (`<REPO>`) 확정
- [ ] Python 버전 (3.10+ 가정) — 로컬 PC 설치 상태 확인
- [ ] GitHub 인증 방식 — PAT vs SSH 키 (기존 설정 활용)
- [ ] 한국 공휴일 캘린더 (v2): `pykrx` 패키지 vs 정적 JSON 리스트
- [ ] 대시보드 색상 팔레트 (외국인=파랑, 기관=주황 등 관행 따를지)

---

## 11. 변경 로그

- 2026-05-27 — 최초 작성
- 2026-05-27 (구현 단계) — **데이터 fetch URL을 raw.githubusercontent → cdn.jsdelivr.net/gh 로 변경.**
  실측 결과 raw 도메인은 Fastly 캐시에서 query string을 정규화해 `?t=<unix>` 캐시버스팅이
  무효 (5분 stale). jsdelivr는 push 후 `https://purge.jsdelivr.net/gh/<user>/<repo>@<branch>/<path>`
  를 GET하면 ~5초 내 모든 엣지(CF+Fastly) 캐시 무효화 — 60초 polling interval 내에서 fresh
  보장. `collect.py` 가 git push 직후 purge 호출 (best-effort, 실패 시 무시).
  Section 2.1 / 5.4의 raw URL은 다음으로 대체:
  - 사이트: `https://cdn.jsdelivr.net/gh/<USER>/<REPO>@data/data/${today}.json`
  - 구현은 commit `a011165` 참고.
