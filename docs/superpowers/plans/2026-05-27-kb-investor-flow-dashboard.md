# KB 투자자별 매매동향 실시간 대시보드 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KB증권 투자자별 매매동향 페이지를 1분 간격으로 로컬 PC에서 수집해 GitHub data 브랜치에 푸시하고, GitHub Pages의 정적 사이트에서 ECharts로 시계열/스냅샷 차트를 실시간 표시한다.

**Architecture:** Python 수집기(`collect/`)가 Windows Task Scheduler로 1분마다 트리거되어 KB의 KOSPI/KOSDAQ 페이지를 HTTP fetch → BeautifulSoup 파싱 → 일별 JSON 파일에 snapshot append → data 브랜치 worktree에서 git commit/push. 사이트는 main 브랜치(Pages)에 정적 배포, raw.githubusercontent.com에서 데이터를 `?t=<unix>` 쿼리 캐시버스팅으로 fetch.

**Tech Stack:** Python 3.10+ (requests, beautifulsoup4), HTML/CSS/JS (vanilla), ECharts 5 (CDN), Git, GitHub Pages, Windows Task Scheduler.

**Spec:** [docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md](../specs/2026-05-27-kb-investor-flow-dashboard-design.md)

---

## File Structure

**프로젝트 루트:** `C:\Users\suble\Desktop\work\project\kb-investor-flow\`
이 디렉토리 자체가 main 브랜치 클론. data 브랜치는 sibling 디렉토리 `kb-investor-flow-data\`에 worktree로 둠.

```
kb-investor-flow\                       (main 브랜치 클론 = 프로젝트 루트)
├── index.html                          (대시보드 진입점)
├── assets\
│   ├── app.js                          (차트 4종 + 자동 갱신)
│   └── style.css                       (레이아웃 + 모바일 반응형)
├── collect\
│   ├── parse.py                        (HTML → dict 변환 — 순수 함수, 단위 테스트)
│   ├── storage.py                      (JSON 파일 I/O + 시간 유틸)
│   ├── fetch.py                        (HTTP GET + 재시도)
│   ├── git_sync.py                     (git add/commit/push 래퍼)
│   ├── collect.py                      (CLI 진입점 — 위 모듈 조합)
│   ├── requirements.txt                (requests, beautifulsoup4)
│   ├── tests\
│   │   ├── test_parse.py
│   │   ├── test_storage.py
│   │   └── fixtures\
│   │       ├── kospi_sample.html
│   │       └── kosdaq_sample.html
│   └── README.md
├── docs\superpowers\
│   ├── specs\2026-05-27-kb-investor-flow-dashboard-design.md  (기존)
│   └── plans\2026-05-27-kb-investor-flow-dashboard.md         (이 문서)
├── .gitignore
└── README.md

kb-investor-flow-data\                  (data 브랜치 worktree, sibling)
└── data\
    └── 2026-05-27.json                 (수집기가 매분 갱신)
```

**파일별 책임:**

| 파일 | 책임 | 인터페이스 |
|---|---|---|
| `collect/parse.py` | KB HTML 문자열 → 구조화 dict. 순수 함수. | `parse_market_html(html: str) -> dict` |
| `collect/storage.py` | 일별 JSON 파일 로드/append/저장 + KST 시간 유틸 | `load_or_init`, `append_snapshot`, `save`, `today_str`, `now_iso` |
| `collect/fetch.py` | HTTP GET + 1회 재시도 + EUC-KR 디코드 | `fetch_market_html(url) -> str` |
| `collect/git_sync.py` | git add/commit/push 서브프로세스 호출 | `commit_and_push(repo_dir, relpath, message)` |
| `collect/collect.py` | CLI: --dry-run, --no-push 옵션 + 전체 오케스트레이션 | `__main__` |
| `assets/app.js` | ECharts 4종 초기화 + 60초 polling + 탭 전환 | 페이지 로드 시 자동 실행 |
| `assets/style.css` | 레이아웃, 모바일 적층 (max-width: 768px) | — |
| `index.html` | DOM 구조 + ECharts CDN + app.js 로드 | — |

---

## Task 1: 프로젝트 부트스트랩 (git init + 디렉토리 + .gitignore)

**Files:**
- Create: `kb-investor-flow\.gitignore`
- Create: `kb-investor-flow\README.md`
- Create: `kb-investor-flow\collect\requirements.txt`
- Create: `kb-investor-flow\collect\README.md`

- [ ] **Step 1: git init**

Run from `C:\Users\suble\Desktop\work\project\kb-investor-flow\`:
```powershell
git init
git branch -m main
```

Expected: `Initialized empty Git repository`.

- [ ] **Step 2: .gitignore 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\.gitignore`:
```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.venv/
venv/

# OS
Thumbs.db
.DS_Store

# Editor
.vscode/
.idea/

# Local secrets / logs
*.log
.env
```

- [ ] **Step 3: README 스켈레톤**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\README.md`:
```markdown
# KB 투자자별 매매동향 실시간 대시보드

KB증권 투자자별 매매동향 페이지(KOSPI/KOSDAQ)를 1분 간격으로 수집해 정적 웹 대시보드로 시각화.

- **대시보드:** https://<USER>.github.io/<REPO>/
- **설계:** [docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md](docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md)
- **구현 계획:** [docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md](docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md)

## 구성
- `index.html`, `assets/` — 정적 대시보드
- `collect/` — 로컬 PC에서 동작하는 Python 수집기
- `data/` (별도 브랜치) — 수집된 일별 JSON
```

- [ ] **Step 4: collect/requirements.txt**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\requirements.txt`:
```
requests>=2.31
beautifulsoup4>=4.12
pytest>=7.4
```

- [ ] **Step 5: collect/README.md**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\README.md`:
```markdown
# collect

KB 투자자별 매매동향 수집기. Windows Task Scheduler에서 1분마다 트리거되어 데이터를
data 브랜치 worktree에 푸시.

## 설치

```powershell
pip install -r requirements.txt
```

## 사용

```powershell
# 파싱 결과만 출력 (네트워크는 호출, 파일/git은 안 건드림)
python collect.py --dry-run

# 파일 저장하되 git push는 안 함 (로컬 검증용)
python collect.py --no-push

# 정식 실행 (Task Scheduler가 호출하는 형태)
python collect.py
```

## 테스트

```powershell
cd tests
pytest -v
```
```

- [ ] **Step 6: 첫 커밋**

```powershell
git add .gitignore README.md collect/requirements.txt collect/README.md
git commit -m "chore: bootstrap project structure"
```

---

## Task 2: spec / plan 문서를 첫 커밋에 포함

**Files:**
- Already exist: `docs\superpowers\specs\2026-05-27-kb-investor-flow-dashboard-design.md`
- Already exist: `docs\superpowers\plans\2026-05-27-kb-investor-flow-dashboard.md`

- [ ] **Step 1: docs 커밋**

```powershell
git add docs/
git commit -m "docs: add design spec and implementation plan"
```

Expected: 2 files committed.

---

## Task 3: KB HTML 픽스처 캡처

수집기 테스트용 정적 HTML 픽스처를 KB 페이지에서 1회 받아 저장.

**Files:**
- Create: `kb-investor-flow\collect\tests\fixtures\kospi_sample.html`
- Create: `kb-investor-flow\collect\tests\fixtures\kosdaq_sample.html`

- [ ] **Step 1: fixtures 디렉토리 생성**

```powershell
New-Item -ItemType Directory -Force "collect\tests\fixtures" | Out-Null
```

- [ ] **Step 2: KOSPI 픽스처 저장**

PowerShell:
```powershell
$client = New-Object System.Net.WebClient
$bytes  = $client.DownloadData("https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0")
$text   = [System.Text.Encoding]::GetEncoding("euc-kr").GetString($bytes)
[System.IO.File]::WriteAllText("collect\tests\fixtures\kospi_sample.html", $text, [System.Text.Encoding]::UTF8)
```

Expected: 약 5KB UTF-8 파일 생성 (원본은 EUC-KR이지만 fixture는 UTF-8로 저장해 파싱 테스트 단순화).

- [ ] **Step 3: KOSDAQ 픽스처 저장**

```powershell
$bytes = $client.DownloadData("https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=1")
$text  = [System.Text.Encoding]::GetEncoding("euc-kr").GetString($bytes)
[System.IO.File]::WriteAllText("collect\tests\fixtures\kosdaq_sample.html", $text, [System.Text.Encoding]::UTF8)
```

- [ ] **Step 4: 한글 확인**

```powershell
Select-String -Path "collect\tests\fixtures\kospi_sample.html" -Pattern "외국인" -SimpleMatch | Select-Object -First 1
```

Expected: 매치되는 줄 출력. 한글이 깨져있으면 디코딩 실패.

- [ ] **Step 5: 커밋**

```powershell
git add collect/tests/fixtures/
git commit -m "test: add KOSPI/KOSDAQ HTML fixtures for parser tests"
```

---

## Task 4: parse.py — KOSPI 픽스처에서 최상위 4분류 파싱 (TDD)

**Files:**
- Create: `kb-investor-flow\collect\tests\test_parse.py`
- Create: `kb-investor-flow\collect\parse.py`

- [ ] **Step 1: 실패하는 첫 테스트 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\tests\test_parse.py`:
```python
import sys
from pathlib import Path

# parse.py는 collect/ 직속, 테스트는 collect/tests/ — 부모 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import parse

FIXTURES = Path(__file__).resolve().parent / "fixtures"

def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_kospi_has_four_top_level_categories():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    assert set(result.keys()) == {"외국인", "개인", "기관", "기타법인"}


def test_kospi_외국인_has_three_values():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    foreigner = result["외국인"]
    assert set(foreigner.keys()) == {"매도", "매수", "순매수"}
    assert all(isinstance(v, int) for v in foreigner.values())
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```powershell
cd collect
pytest tests/test_parse.py -v
```

Expected: `ModuleNotFoundError: No module named 'parse'` (이 파일은 아직 없음).

- [ ] **Step 3: parse.py 최소 구현**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\parse.py`:
```python
"""KB 투자자별 매매동향 HTML 파서.

KB증권 모바일 페이지의 단일 시장(KOSPI 또는 KOSDAQ) HTML을 받아
{외국인, 개인, 기관, 기타법인} 4개 최상위 카테고리 dict로 변환.
기관은 8개 세부 카테고리를 `세부` 키 아래 중첩.
"""
from bs4 import BeautifulSoup

_INSTITUTION_PARENT_IN  = "기관계"
_INSTITUTION_PARENT_OUT = "기관"


def parse_market_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tbody tr")
    result: dict = {}
    current_parent_key: str | None = None

    for tr in rows:
        cells = tr.find_all("td")
        if len(cells) != 4:
            continue

        name = cells[0].get_text(strip=True)
        values = _row_values(cells[1:])

        if name.startswith("- "):
            child = name[2:].strip()
            if current_parent_key:
                result[current_parent_key].setdefault("세부", {})[child] = values
            continue

        if name == _INSTITUTION_PARENT_IN:
            current_parent_key = _INSTITUTION_PARENT_OUT
            result[current_parent_key] = {**values, "세부": {}}
        else:
            result[name] = values
            current_parent_key = None

    return result


def _row_values(cells) -> dict:
    sell, buy, net = (_to_int(c.get_text(strip=True)) for c in cells)
    return {"매도": sell, "매수": buy, "순매수": net}


def _to_int(text: str) -> int:
    return int(text.replace(",", "").strip())
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
pytest tests/test_parse.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add collect/parse.py collect/tests/test_parse.py
git commit -m "feat(parse): parse KB market HTML into top-level categories"
```

---

## Task 5: parse.py — 기관 세부 8분류 확장 (TDD)

**Files:**
- Modify: `kb-investor-flow\collect\tests\test_parse.py`

- [ ] **Step 1: 실패하는 테스트 추가**

Append to `collect\tests\test_parse.py`:
```python
def test_kospi_기관_has_eight_subcategories():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    expected_subs = {
        "금융투자", "투신", "보험", "사모펀드",
        "은행", "기타금융", "연기금등", "국가/지자체",
    }
    assert set(result["기관"]["세부"].keys()) == expected_subs


def test_kospi_기관_세부_금융투자_has_values():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    finance = result["기관"]["세부"]["금융투자"]
    assert set(finance.keys()) == {"매도", "매수", "순매수"}
    assert isinstance(finance["순매수"], int)


def test_kospi_기관_top_has_aggregate_and_세부_keys():
    """기관 dict는 합계(매도/매수/순매수) + 세부 트리를 함께 가짐."""
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    inst = result["기관"]
    assert "매도" in inst and "매수" in inst and "순매수" in inst
    assert "세부" in inst
```

- [ ] **Step 2: 테스트 실행 — 통과 확인 (parse.py가 이미 기관 세부 처리)**

```powershell
cd collect
pytest tests/test_parse.py -v
```

Expected: `5 passed` (전부 통과 — 구현이 이미 세부 처리). 만약 실패하면 parse.py의 `if name.startswith("- ")` 분기를 점검.

- [ ] **Step 3: 음수/0 값 처리 회귀 테스트**

Append to `collect\tests\test_parse.py`:
```python
def test_kospi_negative_values_parsed_correctly():
    """음수 텍스트(-778 등)가 음수 int로 파싱되어야 함."""
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    # KOSPI 외국인 순매수가 픽스처에서 음수임 (수집 시점에 따라 변동 가능 — 부호 보존만 확인)
    foreigner_net = result["외국인"]["순매수"]
    assert isinstance(foreigner_net, int)
    # 모든 숫자가 int인지 전수 확인
    for cat_data in result.values():
        for key in ("매도", "매수", "순매수"):
            assert isinstance(cat_data[key], int)


def test_kosdaq_parses_with_same_structure():
    """KOSDAQ도 동일한 키 구조로 파싱."""
    html = _read("kosdaq_sample.html")
    result = parse.parse_market_html(html)
    assert set(result.keys()) == {"외국인", "개인", "기관", "기타법인"}
    assert len(result["기관"]["세부"]) == 8
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```powershell
pytest tests/test_parse.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add collect/tests/test_parse.py
git commit -m "test(parse): cover 기관 세부, negative values, KOSDAQ"
```

---

## Task 6: storage.py — 시간 유틸 + 일별 파일 I/O (TDD)

**Files:**
- Create: `kb-investor-flow\collect\tests\test_storage.py`
- Create: `kb-investor-flow\collect\storage.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\tests\test_storage.py`:
```python
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import storage


def test_today_str_format():
    s = storage.today_str()
    assert len(s) == 10 and s[4] == "-" and s[7] == "-"


def test_now_iso_has_kst_offset():
    s = storage.now_iso()
    # +09:00 KST 오프셋 포함
    assert s.endswith("+09:00")


def test_load_or_init_creates_skeleton_when_missing(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = storage.load_or_init(path, "2026-05-27")
    assert data["date"] == "2026-05-27"
    assert data["unit"] == "억원"
    assert data["snapshots"] == []
    assert "kospi" in data["source"] and "kosdaq" in data["source"]


def test_append_snapshot_grows_list_and_updates_timestamp(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = storage.load_or_init(path, "2026-05-27")
    kospi = {"외국인": {"매도": 1, "매수": 2, "순매수": 1}}
    kosdaq = {"외국인": {"매도": 3, "매수": 4, "순매수": 1}}
    data = storage.append_snapshot(data, "2026-05-27T09:00:12+09:00", kospi, kosdaq)
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["ts"] == "2026-05-27T09:00:12+09:00"
    assert data["updated_at"] == "2026-05-27T09:00:12+09:00"


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = storage.load_or_init(path, "2026-05-27")
    data = storage.append_snapshot(data, "2026-05-27T09:00:12+09:00", {}, {})
    storage.save(path, data)

    reloaded = storage.load_or_init(path, "2026-05-27")
    assert reloaded["updated_at"] == "2026-05-27T09:00:12+09:00"
    assert len(reloaded["snapshots"]) == 1


def test_save_writes_utf8_with_unicode_keys(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = {"date": "2026-05-27", "snapshots": [{"외국인": 1}]}
    storage.save(path, data)
    raw = path.read_text(encoding="utf-8")
    # 한글이 \uXXXX로 이스케이프되지 않고 그대로 저장
    assert "외국인" in raw
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```powershell
cd collect
pytest tests/test_storage.py -v
```

Expected: `ModuleNotFoundError: No module named 'storage'`.

- [ ] **Step 3: storage.py 구현**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\storage.py`:
```python
"""일별 JSON 파일 I/O + KST 시간 유틸."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_KOSPI_URL  = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0"
_KOSDAQ_URL = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=1"


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def load_or_init(path: Path, date: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "date": date,
        "unit": "억원",
        "source": {"kospi": _KOSPI_URL, "kosdaq": _KOSDAQ_URL},
        "updated_at": None,
        "snapshots": [],
    }


def append_snapshot(data: dict, ts: str, kospi: dict, kosdaq: dict) -> dict:
    data["snapshots"].append({"ts": ts, "kospi": kospi, "kosdaq": kosdaq})
    data["updated_at"] = ts
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
pytest tests/test_storage.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add collect/storage.py collect/tests/test_storage.py
git commit -m "feat(storage): daily JSON file I/O with KST timestamps"
```

---

## Task 7: fetch.py — HTTP GET + EUC-KR 디코드 + 1회 재시도

**Files:**
- Create: `kb-investor-flow\collect\fetch.py`

- [ ] **Step 1: fetch.py 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\fetch.py`:
```python
"""KB 페이지 HTTP fetch — EUC-KR 디코드 + 1회 재시도."""
import time
import requests

KOSPI_URL  = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0"
KOSDAQ_URL = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=1"

_TIMEOUT_SEC      = 10
_RETRY_DELAY_SEC  = 5
_MAX_RETRIES      = 1  # 최초 + 재시도 1회 = 총 2회 시도


def fetch_market_html(url: str) -> str:
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=_TIMEOUT_SEC)
            r.encoding = "euc-kr"
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SEC)
    raise RuntimeError(f"fetch failed after {_MAX_RETRIES + 1} attempts: {last_err}")
```

- [ ] **Step 2: 스모크 테스트 (네트워크 실호출)**

PowerShell:
```powershell
cd collect
python -c "import fetch; t = fetch.fetch_market_html(fetch.KOSPI_URL); print('LEN:', len(t)); print('HAS_외국인:', '외국인' in t)"
```

Expected: `LEN: 5000+`, `HAS_외국인: True`.

- [ ] **Step 3: 커밋**

```powershell
cd ..
git add collect/fetch.py
git commit -m "feat(fetch): HTTP fetcher with EUC-KR decode and retry"
```

---

## Task 8: git_sync.py — git add/commit/push 래퍼

**Files:**
- Create: `kb-investor-flow\collect\git_sync.py`

- [ ] **Step 1: git_sync.py 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\git_sync.py`:
```python
"""data 브랜치 worktree에서 add/commit/push 수행.

멱등성: 'nothing to commit' 케이스는 정상 종료.
"""
import subprocess
from pathlib import Path


def commit_and_push(repo_dir: Path, relpath: str, message: str) -> None:
    _run(["git", "add", relpath], cwd=repo_dir)

    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if commit.returncode != 0:
        combined = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in combined or "no changes added" in combined:
            return  # 멱등 — 동일 파일 재커밋
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")

    _run(["git", "push", "origin", "HEAD"], cwd=repo_dir)


def _run(args: list[str], cwd: Path) -> None:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"git command failed ({' '.join(args)}): {res.stderr.strip()}"
        )
```

- [ ] **Step 2: 임시 git 리포로 add+commit 동작 확인**

본격 통합 검증은 Task 10 Step 3(`collect.py --no-push` 실행 후 worktree에 commit이 들어가는지)에서 수행. 여기서는 모듈 import만 빠르게 확인:

```powershell
cd collect
python -c "import git_sync; print('OK:', git_sync.commit_and_push.__doc__ is not None or 'callable')"
```

Expected: `OK: callable` 또는 docstring 출력. 에러 없이 import되면 통과.

- [ ] **Step 3: 커밋**

```powershell
cd ..
git add collect/git_sync.py
git commit -m "feat(git_sync): idempotent add/commit/push wrapper for data branch"
```

---

## Task 9: collect.py — CLI 진입점

위 4개 모듈(parse, storage, fetch, git_sync)을 조합해 한 분의 수집 사이클 수행.

**Files:**
- Create: `kb-investor-flow\collect\collect.py`

- [ ] **Step 1: collect.py 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\collect.py`:
```python
"""KB 투자자별 매매동향 1분 수집 사이클 진입점.

Task Scheduler가 매분 호출하는 CLI. --dry-run, --no-push 지원.
data worktree는 본 스크립트의 부모 디렉토리 sibling인
'kb-investor-flow-data\\' 라고 가정.
"""
import argparse
import json
import sys
from pathlib import Path

import fetch
import git_sync
import parse
import storage

_THIS_DIR = Path(__file__).resolve().parent              # ...\kb-investor-flow\collect
_MAIN_REPO_ROOT = _THIS_DIR.parent                       # ...\kb-investor-flow
_DATA_REPO_ROOT = _MAIN_REPO_ROOT.parent / "kb-investor-flow-data"  # sibling


def collect_once(dry_run: bool = False, skip_push: bool = False) -> None:
    kospi_html  = fetch.fetch_market_html(fetch.KOSPI_URL)
    kosdaq_html = fetch.fetch_market_html(fetch.KOSDAQ_URL)
    kospi  = parse.parse_market_html(kospi_html)
    kosdaq = parse.parse_market_html(kosdaq_html)

    date = storage.today_str()
    ts   = storage.now_iso()

    if dry_run:
        print(json.dumps(
            {"ts": ts, "kospi": kospi, "kosdaq": kosdaq},
            ensure_ascii=False, indent=2,
        ))
        return

    rel = f"data/{date}.json"
    path = _DATA_REPO_ROOT / rel
    data = storage.load_or_init(path, date)
    data = storage.append_snapshot(data, ts, kospi, kosdaq)
    storage.save(path, data)
    print(f"wrote {path} ({len(data['snapshots'])} snapshots, updated_at={ts})")

    if skip_push:
        return

    git_sync.commit_and_push(
        repo_dir=_DATA_REPO_ROOT,
        relpath=rel,
        message=f"data: {date} {ts[11:19]} KST",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="KB 투자자별 매매동향 1분 수집기")
    p.add_argument("--dry-run", action="store_true",
                   help="파싱 결과를 stdout에 출력만, 파일/git 손대지 않음")
    p.add_argument("--no-push", action="store_true",
                   help="파일은 저장하되 git commit/push 안 함")
    args = p.parse_args()

    try:
        collect_once(dry_run=args.dry_run, skip_push=args.no_push)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: --dry-run 검증 (네트워크 실호출, 파일/git 안 건드림)**

```powershell
cd collect
python collect.py --dry-run
```

Expected: stdout에 JSON 출력 — `ts`, `kospi`, `kosdaq` 키 포함, 한글 카테고리 정상 표시. `kospi.기관.세부.금융투자.순매수` 같은 경로 접근 가능 구조.

- [ ] **Step 3: 커밋**

```powershell
cd ..
git add collect/collect.py
git commit -m "feat(collect): CLI orchestrator with --dry-run and --no-push"
```

---

## Task 10: data 브랜치 orphan 생성 + worktree 셋업

main 브랜치까지의 작업물을 GitHub에 푸시 후 (Task 18에서), data 브랜치 worktree를 sibling 디렉토리에 만들기 위한 준비.

본 task는 **로컬에서만** 동작. GitHub 원격 푸시는 Task 18에서.

**Files:**
- Created: `kb-investor-flow-data\` (sibling 디렉토리, data 브랜치 worktree)

- [ ] **Step 1: data orphan 브랜치 생성**

```powershell
cd C:\Users\suble\Desktop\work\project\kb-investor-flow
git checkout --orphan data
git rm -rf .
Set-Content -Path "README.md" -Value "# Auto-generated data branch`r`n`r`n이 브랜치는 collect.py가 1분마다 자동으로 갱신합니다. 직접 수정하지 마세요."
git add README.md
git commit -m "chore: init data branch"
git checkout main
```

Expected: `data` 브랜치가 1개 커밋(README.md만)만 가지고 존재. main 체크아웃으로 복귀.

- [ ] **Step 2: data worktree 추가**

```powershell
git worktree add ..\kb-investor-flow-data data
```

Expected: `kb-investor-flow-data\` 디렉토리 생성, 안에 README.md만 존재.

- [ ] **Step 3: --no-push로 collect 한 번 실행 → data worktree에 파일 생성 확인**

```powershell
cd collect
python collect.py --no-push
```

Expected:
- stdout: `wrote C:\...\kb-investor-flow-data\data\<오늘>.json (1 snapshots, ...)`.
- 파일 실제 존재: `Test-Path "..\..\kb-investor-flow-data\data\$(Get-Date -Format yyyy-MM-dd).json"` → True.

- [ ] **Step 4: data worktree에서 git status로 변경 확인**

```powershell
cd ..\..\kb-investor-flow-data
git status
```

Expected: `data/` 디렉토리에 새 파일 untracked.

- [ ] **Step 5: 정리 (해당 데이터 파일 삭제 — 본격 운영 전 클린 상태로)**

```powershell
Remove-Item -Recurse -Force data
cd ..\kb-investor-flow
```

---

## Task 11: index.html + style.css — 정적 사이트 스켈레톤

**Files:**
- Create: `kb-investor-flow\index.html`
- Create: `kb-investor-flow\assets\style.css`

- [ ] **Step 1: index.html 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\index.html`:
```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>KB 투자자별 매매동향 실시간</title>
  <link rel="stylesheet" href="assets/style.css" />
</head>
<body>
  <header class="site-header">
    <h1>KB 투자자별 매매동향 실시간</h1>
    <div class="meta">
      <span>마지막 업데이트: <time id="updated">-</time> KST</span>
      <span class="sep">|</span>
      <span>단위: 억원</span>
      <span class="sep">|</span>
      <span>자동 새로고침 60s</span>
    </div>
  </header>

  <nav class="tabs" role="tablist">
    <button class="tab active" role="tab" data-market="kospi" aria-selected="true">KOSPI</button>
    <button class="tab"        role="tab" data-market="kosdaq" aria-selected="false">KOSDAQ</button>
  </nav>

  <main>
    <section class="market-panel" data-market="kospi">
      <h2>주요 4분류 순매수 추이</h2>
      <div class="chart" data-chart="mainLines"></div>

      <h2>기관 세부 8분류 순매수 추이</h2>
      <div class="chart" data-chart="institutionLines"></div>

      <div class="snapshot-row">
        <div>
          <h2>현재 순매수</h2>
          <div class="chart half" data-chart="netBar"></div>
        </div>
        <div>
          <h2>매도 vs 매수</h2>
          <div class="chart half" data-chart="volumeBar"></div>
        </div>
      </div>
    </section>

    <section class="market-panel hidden" data-market="kosdaq">
      <h2>주요 4분류 순매수 추이</h2>
      <div class="chart" data-chart="mainLines"></div>

      <h2>기관 세부 8분류 순매수 추이</h2>
      <div class="chart" data-chart="institutionLines"></div>

      <div class="snapshot-row">
        <div>
          <h2>현재 순매수</h2>
          <div class="chart half" data-chart="netBar"></div>
        </div>
        <div>
          <h2>매도 vs 매수</h2>
          <div class="chart half" data-chart="volumeBar"></div>
        </div>
      </div>
    </section>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <script src="assets/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\assets\style.css`:
```css
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif; color: #1a1a1a; background: #fafafa; }

.site-header { padding: 16px 24px; background: #fff; border-bottom: 1px solid #e5e5e5; }
.site-header h1 { margin: 0 0 4px; font-size: 18px; }
.site-header .meta { font-size: 12px; color: #666; }
.site-header .meta .sep { margin: 0 8px; color: #ccc; }

.tabs { display: flex; gap: 4px; padding: 0 24px; background: #fff; border-bottom: 1px solid #e5e5e5; }
.tab { padding: 10px 18px; border: none; background: transparent; cursor: pointer; font-size: 14px; color: #666; border-bottom: 2px solid transparent; }
.tab.active { color: #1a1a1a; border-bottom-color: #1976d2; font-weight: 600; }

main { padding: 16px 24px; max-width: 1200px; margin: 0 auto; }
.market-panel.hidden { display: none; }
.market-panel h2 { font-size: 14px; margin: 16px 0 8px; color: #444; }

.chart { width: 100%; height: 320px; background: #fff; border: 1px solid #e5e5e5; border-radius: 4px; }
.chart.half { height: 280px; }

.snapshot-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px; }

@media (max-width: 768px) {
  .site-header { padding: 12px 16px; }
  .site-header h1 { font-size: 16px; }
  main { padding: 12px 16px; }
  .snapshot-row { grid-template-columns: 1fr; }
  .chart { height: 280px; }
  .chart.half { height: 240px; }
}
```

- [ ] **Step 3: 로컬 브라우저로 빈 골격 확인**

```powershell
cd C:\Users\suble\Desktop\work\project\kb-investor-flow
python -m http.server 8000
```

브라우저: `http://localhost:8000/` → 헤더, 탭, 빈 차트 박스 4개가 보이는지 확인. 콘솔 오류 없으면 OK. 서버 종료(`Ctrl+C`).

- [ ] **Step 4: 커밋**

```powershell
git add index.html assets/style.css
git commit -m "feat(site): static skeleton with header, tabs, chart placeholders"
```

---

## Task 12: app.js — 데이터 로더 (목 데이터로 먼저)

차트 구현 전에 데이터 로딩 파이프라인을 먼저 검증. 이후 차트 task들이 이 함수를 사용.

**Files:**
- Create: `kb-investor-flow\assets\app.js`
- Create: `kb-investor-flow\assets\mock-data.json` (목 데이터)

- [ ] **Step 1: 목 데이터 생성 (collect.py --no-push 3회 활용)**

Task 10에서 data worktree가 만들어졌으므로 `--no-push`로 3개 snapshot을 실제 KB 데이터로 누적. 1초 간격이면 ts가 달라 시계열 차트 검증에 충분.

```powershell
cd collect
python collect.py --no-push
Start-Sleep -Seconds 1
python collect.py --no-push
Start-Sleep -Seconds 1
python collect.py --no-push
```

Expected: 3회 모두 `wrote ... (1 snapshots / 2 snapshots / 3 snapshots ...)` 출력.

오늘 날짜 데이터 파일을 `assets/mock-data.json`으로 복사:

```powershell
$today = (Get-Date -Format yyyy-MM-dd)
Copy-Item "..\..\kb-investor-flow-data\data\$today.json" "..\assets\mock-data.json"
cd ..
```

Expected: `assets\mock-data.json` 생성. 내용은 실제 KB 데이터 3 snapshot. JSON 열어서 `snapshots` 배열에 3개 객체 있는지 확인.

- [ ] **Step 2: app.js 초기 스켈레톤 작성**

Write `C:\Users\suble\Desktop\work\project\kb-investor-flow\assets\app.js`:
```javascript
// 데이터 소스 — 운영에서는 raw URL, 개발에서는 로컬 mock
const REFRESH_MS = 60_000;
const USE_MOCK = true;  // Task 16에서 false로 변경하며 raw URL 활성화
const RAW_BASE = "https://raw.githubusercontent.com/<USER>/<REPO>/data";

// ECharts 인스턴스: market(kospi|kosdaq) → chartKey → instance
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
      // 숨겨진 동안 resize 큐가 누락되었을 수 있으니 표시 직후 1회 리사이즈
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
  // YYYY-MM-DD in KST
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

function updateHeader(updatedAt) {
  const el = document.getElementById("updated");
  if (!updatedAt) { el.textContent = "-"; return; }
  // "2026-05-27T15:30:12+09:00" → "15:30:12"
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

// 각 차트 setter는 Task 13~15에서 채움 — 일단 no-op
function setMainLines() {}
function setInstitutionLines() {}
function setNetBar() {}
function setVolumeBar() {}
```

- [ ] **Step 3: 로컬에서 데이터 로딩 검증**

```powershell
python -m http.server 8000
```

브라우저: `http://localhost:8000/` → DevTools Console 열고 새로고침.
Expected:
- Network 탭: `assets/mock-data.json` 200 OK
- Console: 에러 없음
- 헤더의 `<time id="updated">`가 "15:30:00"으로 변경됨
- 차트는 아직 빈 박스 (setter가 no-op)

서버 종료.

- [ ] **Step 4: 커밋**

```powershell
git add assets/app.js assets/mock-data.json
git commit -m "feat(site): app.js bootstrap with mock data loader and tab switching"
```

---

## Task 13: app.js — 차트 ①  주요 4분류 순매수 라인

**Files:**
- Modify: `kb-investor-flow\assets\app.js`

- [ ] **Step 1: 헬퍼 함수와 setMainLines 채우기**

Edit `assets\app.js`. 파일 하단의 `function setMainLines() {}` 를 다음 코드로 교체. 이미 정의된 `function setInstitutionLines() {}`, `setNetBar`, `setVolumeBar` 는 그대로 둠.

```javascript
const MAIN_CATEGORIES = ["외국인", "개인", "기관", "기타법인"];

// 색상 팔레트 — 직관에 가까운 관행
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
```

- [ ] **Step 2: 시각 확인**

```powershell
python -m http.server 8000
```

브라우저 새로고침. Expected:
- KOSPI 탭의 첫 번째 차트("주요 4분류 순매수 추이")에 4개 라인이 보임
- 범례에 외국인/개인/기관/기타법인 4개
- 하단 dataZoom 슬라이더 존재
- 마우스 호버 시 툴팁에 4 시리즈 값 모두 표시
- KOSDAQ 탭 클릭 시 같은 차트가 KOSDAQ 데이터로 렌더

서버 종료.

- [ ] **Step 3: 커밋**

```powershell
git add assets/app.js
git commit -m "feat(chart): main 4-category net buy line chart"
```

---

## Task 14: app.js — 차트 ② 기관 세부 8분류 순매수 라인

**Files:**
- Modify: `kb-investor-flow\assets\app.js`

- [ ] **Step 1: setInstitutionLines 구현**

Edit `assets\app.js`. `function setInstitutionLines() {}` 교체:

```javascript
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
```

- [ ] **Step 2: 시각 확인**

```powershell
python -m http.server 8000
```

Expected:
- 두 번째 차트("기관 세부 8분류")에 8개 라인
- 범례가 너무 길면 자동 스크롤 (legend.type: "scroll")
- 호버 시 8 시리즈 값 동시 표시
- KOSDAQ 탭에서도 동일 동작

서버 종료.

- [ ] **Step 3: 커밋**

```powershell
git add assets/app.js
git commit -m "feat(chart): institution 8-subcategory net buy line chart"
```

---

## Task 15: app.js — 차트 ③④ 현재 순매수 + 매도/매수 비교 (수평/그룹 막대)

**Files:**
- Modify: `kb-investor-flow\assets\app.js`

- [ ] **Step 1: setNetBar 와 setVolumeBar 구현**

Edit `assets\app.js`. `function setNetBar()` 와 `function setVolumeBar()` 둘 다 교체:

```javascript
function latestTopLevel(data, market, category) {
  // 가장 최근 snapshot의 그 카테고리 dict
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
        itemStyle: { color: v >= 0 ? "#43a047" : "#e53935" },  // 양:초록, 음:빨강
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
```

- [ ] **Step 2: 시각 확인**

```powershell
python -m http.server 8000
```

Expected:
- ③ 현재 순매수: 수평 막대 4개, 양수는 초록·음수는 빨강, 막대 오른쪽에 값 라벨
- ④ 매도 vs 매수: 4 카테고리별로 매도(연빨강)·매수(연초록) 인접 막대 2개씩
- KOSDAQ 탭에서도 동일 동작

서버 종료.

- [ ] **Step 3: 커밋**

```powershell
git add assets/app.js
git commit -m "feat(chart): current net (horizontal) and sell-vs-buy (grouped) bars"
```

---

## Task 16: app.js — raw URL 실데이터 fetch로 전환

목 데이터에서 운영 데이터로 토글.

**Files:**
- Modify: `kb-investor-flow\assets\app.js`

- [ ] **Step 1: USE_MOCK 끄기 + RAW_BASE 확정**

GitHub `<USER>`/`<REPO>` 값이 확정되어야 함 — Task 18에서 GitHub 리포 생성 시점에 확정.

이 task는 Task 18 직후에 실행. Edit `assets\app.js` 상단:
```javascript
// 변경 전
const USE_MOCK = true;
const RAW_BASE = "https://raw.githubusercontent.com/<USER>/<REPO>/data";

// 변경 후 (실제 값으로 치환)
const USE_MOCK = false;
const RAW_BASE = "https://raw.githubusercontent.com/실제USER/실제REPO/data";
```

- [ ] **Step 2: 로컬에서 raw URL fetch 검증**

(Task 10에서 data 브랜치는 만들어졌고 push까지 됐다고 가정 — Task 18 이후)

```powershell
python -m http.server 8000
```

브라우저 → DevTools Network 탭 확인:
- `https://raw.githubusercontent.com/.../data/<오늘>.json?t=<unix>` 요청 200 OK
- 60초 후 자동으로 다음 fetch (또 다른 `?t=` 값)
- 응답 헤더 `cache-control: max-age=300` 보이지만 쿼리스트링 차이로 origin 도달

데이터가 비어있으면 (장중 외 시간) 헤더만 갱신, 차트는 비어있어도 OK.

- [ ] **Step 3: mock-data.json 정리 + 커밋**

```powershell
git rm assets/mock-data.json
git add assets/app.js
git commit -m "feat(site): switch to live raw.githubusercontent.com data"
```

---

## Task 17: README 최종 정비 + 로컬 사용 안내

**Files:**
- Modify: `kb-investor-flow\README.md`

- [ ] **Step 1: README 확장**

Write (덮어쓰기) `C:\Users\suble\Desktop\work\project\kb-investor-flow\README.md`:
```markdown
# KB 투자자별 매매동향 실시간 대시보드

KB증권 [투자자별 매매동향 페이지](https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0)의
KOSPI/KOSDAQ 데이터를 한국 정규 장중(평일 09:00–15:30 KST) 1분 간격으로 로컬 PC에서 수집해,
GitHub Pages의 정적 사이트에서 ECharts로 시계열·스냅샷 차트로 시각화합니다.

- **라이브 대시보드:** https://<USER>.github.io/<REPO>/
- **설계 문서:** [docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md](docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md)
- **구현 계획:** [docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md](docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md)

## 구성

- `index.html`, `assets/` — 정적 대시보드 (GitHub Pages가 main 브랜치에서 서빙)
- `collect/` — Python 수집기 (로컬 PC의 Task Scheduler가 1분마다 실행)
- `data/` (별도 브랜치 `data` — orphan) — 일별 JSON, 매분 푸시

## 데이터 흐름

```
[Local PC] Task Scheduler → collect.py → KB 페이지 fetch → JSON append → git push (data 브랜치)
                                                                                ↓
[GitHub] data 브랜치 ← raw.githubusercontent.com (CORS + ?t= 캐시버스팅)
[GitHub] main 브랜치 → GitHub Pages → 정적 사이트 → fetch raw URL → ECharts 갱신
```

## 로컬 셋업 (수집기)

상세 안내: [collect/README.md](collect/README.md). 요약:

1. Python 3.10+ 설치, `pip install -r collect/requirements.txt`
2. data 브랜치를 sibling 디렉토리에 worktree:
   `git worktree add ../kb-investor-flow-data data`
3. 1회 검증: `cd collect && python collect.py --dry-run`
4. Windows Task Scheduler 등록 — 평일 09:00 시작 / 1분 반복 / 15:30 종료

## 로컬 사이트 미리보기

```powershell
python -m http.server 8000
# http://localhost:8000/
```
```

- [ ] **Step 2: 커밋**

```powershell
git add README.md
git commit -m "docs: expand README with architecture and setup overview"
```

---

## Task 18: GitHub 리포 생성 + 원격 푸시 + Pages 활성화

이 시점에 `<USER>`/`<REPO>` 가 확정되어야 함.

**Files:**
- 변경 없음 (외부 GitHub 작업)

- [ ] **Step 1: GitHub에 리포 생성**

GitHub UI 또는 `gh` CLI:
```powershell
gh repo create <USER>/<REPO> --public --source=. --remote=origin
# 또는 GitHub UI에서 빈 리포 생성 후:
# git remote add origin git@github.com:<USER>/<REPO>.git
```

- [ ] **Step 2: main 푸시**

```powershell
cd C:\Users\suble\Desktop\work\project\kb-investor-flow
git push -u origin main
```

- [ ] **Step 3: data 브랜치 푸시**

```powershell
git push -u origin data
```

- [ ] **Step 4: Pages 활성화**

GitHub UI: `Settings → Pages`
- Source: `Deploy from a branch`
- Branch: `main` / Folder: `/ (root)`
- Save

수 분 대기 후 `https://<USER>.github.io/<REPO>/` 접근. 헤더와 빈 차트가 표시되는지 확인 (현 시점 data 브랜치엔 README만 — fetch는 404).

- [ ] **Step 5: app.js의 placeholder 치환**

Task 16의 Step 1을 실행 — `<USER>`, `<REPO>` 실제 값으로 변경.

```powershell
# 예시 (sed 대체 — PowerShell)
$f = "assets\app.js"
(Get-Content $f) -replace '<USER>', '실제유저명' -replace '<REPO>', '실제리포명' | Set-Content $f
(Get-Content $f) -replace 'const USE_MOCK = true;', 'const USE_MOCK = false;' | Set-Content $f
```

- [ ] **Step 6: 변경 푸시**

```powershell
git rm assets/mock-data.json -f
git add assets/app.js
git commit -m "feat(site): switch to live raw URL with real repo name"
git push
```

GitHub Pages 재배포 대기 (~1분).

---

## Task 19: Windows Task Scheduler 등록

**Files:**
- 변경 없음 (Windows 시스템 작업)

- [ ] **Step 1: Python 실행파일 절대 경로 확인**

```powershell
(Get-Command python).Source
```

Expected 예: `C:\Users\suble\AppData\Local\Programs\Python\Python311\python.exe`. 이 값을 `<PYTHON_EXE>`로 메모.

- [ ] **Step 2: Task Scheduler에 작업 등록 (PowerShell)**

```powershell
$python = (Get-Command python).Source
$script = "C:\Users\suble\Desktop\work\project\kb-investor-flow\collect\collect.py"
$workDir = "C:\Users\suble\Desktop\work\project\kb-investor-flow\collect"

$action = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $workDir

# 평일 09:00 시작, 1분 반복, 6시간 30분(15:30) 동안
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00 -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At 09:00 -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Hours 6 -Minutes 30)).Repetition

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName "KB-InvestorFlow-Collect" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "KB 투자자별 매매동향 1분 수집"
```

Expected: `TaskName: KB-InvestorFlow-Collect, State: Ready`.

> **Note:** `New-ScheduledTaskTrigger`가 직접 daily-weekdays + per-minute repetition 조합을 지원하지 않아 두 단계로 빌드. PowerShell 5.1 표준 패턴.

- [ ] **Step 3: 즉시 1회 수동 실행으로 검증**

```powershell
Start-ScheduledTask -TaskName "KB-InvestorFlow-Collect"
# 잠시 대기 후
Get-ScheduledTaskInfo -TaskName "KB-InvestorFlow-Collect" | Select-Object LastTaskResult, LastRunTime
```

Expected: `LastTaskResult: 0` (성공). 만약 0이 아니면 Task Scheduler GUI(`taskschd.msc`)에서 이력 탭 확인.

- [ ] **Step 4: 수집된 데이터가 GitHub data 브랜치에 도착했는지 확인**

```powershell
# 1~2분 대기 후 GitHub 측 확인:
gh api repos/<USER>/<REPO>/contents/data?ref=data
```

Expected: 오늘 날짜 JSON 파일이 리스트에 보임.

브라우저: `https://raw.githubusercontent.com/<USER>/<REPO>/data/data/<오늘>.json?t=$(Get-Date -UFormat %s)`
Expected: JSON 응답, snapshots 배열에 최소 1개 항목.

- [ ] **Step 5: 대시보드 라이브 확인**

`https://<USER>.github.io/<REPO>/` 접근. Expected:
- 헤더 "마지막 업데이트"에 방금 시각 표시
- 4개 차트 중 시계열은 1~2점만 (이제 막 시작), 막대는 현재값 표시
- 60초 후 새 데이터 자동 fetch (Network 탭에서 확인)

---

## Task 20: Day 1 운영 검증

장중 첫날 종료 후 데이터 무결성 확인.

**Files:**
- 변경 없음 (검증 task)

- [ ] **Step 1: 첫 영업일 15:30 이후 Snapshot 개수 확인**

```powershell
$today = Get-Date -Format yyyy-MM-dd
$url = "https://raw.githubusercontent.com/<USER>/<REPO>/data/data/$today.json"
$data = (Invoke-WebRequest $url).Content | ConvertFrom-Json
Write-Output "Snapshots: $($data.snapshots.Count)"
Write-Output "First TS: $($data.snapshots[0].ts)"
Write-Output "Last  TS: $($data.snapshots[-1].ts)"
```

Expected:
- Snapshots: 380~390 (이론 최대 390 = 6.5시간 × 60분, 일부 실패 허용)
- First TS: ~09:00:xx
- Last TS: ~15:30:xx

- [ ] **Step 2: Task Scheduler 최근 실행 결과 확인**

```powershell
Get-ScheduledTaskInfo -TaskName "KB-InvestorFlow-Collect" |
  Select-Object LastTaskResult, LastRunTime, NextRunTime, NumberOfMissedRuns
```

Expected:
- `LastTaskResult`: 0 (성공)
- `NumberOfMissedRuns`: 0~5 (트리거 누락 — 5 이내면 정상)
- `NextRunTime`: 다음 영업일 09:00

상세 이력은 `taskschd.msc` GUI → 작업 선택 → 하단 "기록" 탭에서 확인.

- [ ] **Step 3: 대시보드 시각 확인**

`https://<USER>.github.io/<REPO>/` 새로고침. Expected:
- 시계열 라인 차트 2종에 09:00~15:30 데이터가 부드러운 라인으로 표시
- KOSPI/KOSDAQ 탭 전환 정상
- dataZoom 슬라이더로 구간 확대 가능
- 모바일 viewport (DevTools Device Mode 375px)에서 적층 레이아웃

- [ ] **Step 4: 익일 09:00 새 파일 생성 확인 (다음날)**

다음 영업일 09:01 경:
```powershell
$today = Get-Date -Format yyyy-MM-dd
Invoke-WebRequest "https://raw.githubusercontent.com/<USER>/<REPO>/data/data/$today.json" | Out-Null
"OK: new file created"
```

Expected: 200 OK — 자정 리셋 작업 없이도 새 파일 자동 생성됨.

---

## 부록: 일반 오류 트러블슈팅

| 증상 | 점검 |
|---|---|
| Task Scheduler `LastTaskResult` 가 0이 아님 | `taskschd.msc` 이력 탭에서 정확한 에러. `python` 경로, `--no-push` 옵션으로 수동 실행해 분리 검증. |
| `git push` 인증 실패 | Windows Credential Manager에 `git:https://github.com` 항목 / SSH 키 등록 확인 (`ssh -T git@github.com`). |
| 대시보드가 데이터 못 받음 | DevTools Network → raw URL 응답 코드. 404면 data 브랜치 푸시 안 됨. CORS 오류면 raw 도메인 아님 (예: github.com/.../raw/...는 CORS 차단). |
| 차트가 갱신 안 됨 | Console 에러 확인. 데이터 스키마 불일치 가능성 — 파싱 함수가 변경된 페이지 구조를 받았는지. |
| 한글 깨짐 | JSON 파일 인코딩 (`Get-Content -Encoding UTF8 file.json` 첫 줄 확인). storage.save에서 `ensure_ascii=False` + `encoding='utf-8'` 사용 중인지. |
| 휴장일에 같은 값 반복 기록됨 | 의도된 동작 (v1 비목표). v2에서 `pykrx` 등으로 캘린더 추가. |

---

## Spec 커버리지 확인

| Spec 섹션 | 구현 Task |
|---|---|
| 1.1 목표 | Task 1–20 전체 |
| 2 아키텍처 | Task 1, 10, 18 |
| 3 KB 페이지 분석 / 파싱 전략 | Task 3, 4, 5 |
| 4 데이터 스키마 | Task 6 (storage.py 골격), 4–5 (파서가 채움) |
| 5.1–5.4 대시보드 UI / 차트 4종 / 자동 갱신 | Task 11, 12, 13, 14, 15, 16 |
| 5.5 깜빡임 방지 (`setOption`) | Task 13–15에서 setOption 사용 |
| 6 디렉토리 구조 | Task 1 (main), 10 (data worktree) |
| 7 셋업 체크리스트 | Task 7 (fetch smoke), 10 (worktree), 18 (GitHub), 19 (Scheduler) |
| 8 운영 (정상 흐름 / 오류 시나리오) | Task 7 (재시도), 8 (멱등 commit), 부록 |
| 9.1 단위 테스트 | Task 4, 5, 6 |
| 9.2 통합 테스트 | Task 9 (--dry-run), 10 (--no-push) |
| 9.3 시각 확인 | Task 11–15 각 Step 2 |
| 9.4 Day 1 운영 확인 | Task 20 |
