# 슬랙 알림 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 단일 라벨변화 알림을 12종 감지기 다중 이벤트 버스로 바꿔, 분당 1메시지 통합 + 전일종가 기준 지수헤더 + 라이브 가지치기(states footer)를 제공한다.

**Architecture:** 순수함수 감지기를 신규 `collect/events.py`로 분리(Event=dict, pandas/requests 의존 없음). `collect/notify.py`는 데이터 로드·상태관리·감지기 실행·분당 통합·포맷·발송만 담당. 노이즈는 롤링 드로다운 래칫으로 차단하고 임계값은 `collect/calibrate.py`가 과거일 리플레이로 확정한다.

**Tech Stack:** Python 3.8+ 순수(표준 라이브러리만, 수집 데몬 venv는 requests/bs4만 보유), pytest. trend.py(pandas)는 분석/검증용으로 불변.

스펙: [docs/superpowers/specs/2026-06-11-slack-alerts-v2-design.md](../specs/2026-06-11-slack-alerts-v2-design.md)

---

## File Structure

| 파일 | 책임 | 변경 |
|------|------|------|
| `collect/events.py` | `Event`, `CFG`, `EVENT_KINDS`, `COOLDOWN`, 라벨아이콘, `enabled_events()`, `render_roster()`, 12개 감지기 순수함수 + 래칫 | 신규 |
| `collect/notify.py` | `classify_full()`(e_dir 노출), 지수/헤더 헬퍼, `check_and_notify()` 리팩터, `_format_v2()`, 상태 스키마 확장 | 수정 |
| `collect/calibrate.py` | 과거일 분단위 리플레이 → 감지기별 발사횟수/오발사 리포트 | 신규 |
| `collect/tests/test_events.py` | 감지기 단위테스트 (계단 노이즈 케이스 포함) | 신규 |
| `collect/tests/test_notify_v2.py` | `classify_full` 파리티 + 통합 발송 테스트 | 신규 |
| `collect/trend.py` | 불변 (selftest 기준) | — |

테스트 실행은 `collect/` 디렉토리에서 `python -m pytest tests/ -v`. 기존 테스트(`test_parse.py`,`test_storage.py`)와 동일하게 `sys.path.insert`로 `collect/`를 path에 넣는다.

---

## Task 1: events.py 토대 (Event·로스터·CFG)

**Files:**
- Create: `collect/events.py`
- Test: `collect/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_events.py
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import events


def test_ev_builds_event_with_rank_and_dedup():
    e = events.ev("지수스파이크", "⚡", "KOSPI 1분 +0.30%")
    assert e["kind"] == "지수스파이크"
    assert e["icon"] == "⚡"
    assert e["text"] == "KOSPI 1분 +0.30%"
    assert e["rank"] == events.EVENT_KINDS.index("지수스파이크")
    assert e["dedup"] == "지수스파이크"  # 기본 dedup = kind


def test_enabled_events_default_is_full_roster(monkeypatch):
    monkeypatch.delenv("NOTIFY_EVENTS", raising=False)
    assert events.enabled_events() == events.EVENT_KINDS


def test_enabled_events_whitelist_filters_and_preserves_order(monkeypatch):
    monkeypatch.setenv("NOTIFY_EVENTS", "지수스파이크, 확정전환")
    assert events.enabled_events() == ["확정전환", "지수스파이크"]


def test_render_roster_marks_fired_first():
    enabled = ["확정전환", "잠정전환", "지수윈도우"]
    fired = {"확정전환", "지수윈도우"}
    out = events.render_roster(enabled, fired)
    assert out == "states: ●확정전환 ●지수윈도우 · 잠정전환"


def test_render_roster_all_quiet_has_no_separator():
    out = events.render_roster(["확정전환", "잠정전환"], set())
    assert out == "states: 확정전환 잠정전환"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'events'`

- [ ] **Step 3: Write minimal implementation**

```python
# collect/events.py
"""슬랙 알림 v2 — 순수함수 감지기 모음 + 임계값 상수.

pandas/requests 의존 없음(수집 데몬 venv 호환). 각 감지기는 호출측이 만든
순수 데이터(이미 파싱된 board/누적시퀀스/상태 dict)를 받아 list[Event]를 반환한다.
부수효과 없음 → 단위테스트 가능. 임계값(CFG)은 calibrate.py 산출로 갱신한다.
"""
from __future__ import annotations
import os

# 메시지 줄 정렬 우선순위 = 이 리스트의 인덱스. states footer 로스터 순서도 동일.
EVENT_KINDS = [
    "확정전환", "잠정전환", "지수윈도우", "지수스파이크", "정렬",
    "신고저", "개인디버전스", "개장마감", "flow급증", "지수디버전스",
    "마일스톤", "하트비트",
]

# 8라벨 아이콘 (trend._ARROW / notify.ICON와 동일).
LABEL_ICON = {"지속매수": "🔥", "매수전환": "❤️", "매수둔화": "🔸", "혼조": "💤",
              "중립": "◽", "매도둔화": "🔹", "매도전환": "💙", "지속매도": "💦"}

# 동일 dedup 키가 이 분(分) 안에 또 떠도 억제. 미등록 kind = 0(항상 허용).
COOLDOWN = {
    "지수윈도우": 5, "지수스파이크": 3, "신고저": 0, "flow급증": 5,
    "정렬": 10, "개인디버전스": 10, "지수디버전스": 10,
}

# 임계값 — calibrate.py로 확정하는 출발점.
CFG = {
    "heartbeat_min": 5,
    "win_n": 5, "win_pct": 0.30,
    "spike_pct": 0.20,
    "ratchet_D": 30.0, "ratchet_W": 20,
    "hilo_eps": 0.5,
    "flow_z": 2.5, "flow_win": 20,
    "align_eps": 1.0, "indiv_eps": 1.0,
    "milestone_marks": [30, 60, 90],
    "idxdiv_pct": 0.20,
}

BUY_FAM = {"지속매수", "매수전환", "매수둔화"}
SELL_FAM = {"지속매도", "매도전환", "매도둔화"}


def ev(kind: str, icon: str, text: str, dedup: str | None = None) -> dict:
    return {"kind": kind, "icon": icon, "text": text,
            "rank": EVENT_KINDS.index(kind), "dedup": dedup or kind}


def enabled_events() -> list:
    env = os.environ.get("NOTIFY_EVENTS", "").strip()
    if not env:
        return list(EVENT_KINDS)
    picked = {a.strip() for a in env.split(",") if a.strip()}
    return [k for k in EVENT_KINDS if k in picked]


def render_roster(enabled: list, fired: set) -> str:
    fr = [k for k in enabled if k in fired]
    qt = [k for k in enabled if k not in fired]
    roster = " ".join("●" + k for k in fr)
    if fr and qt:
        roster += " · "
    roster += " ".join(qt)
    return "states: " + roster
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add collect/events.py collect/tests/test_events.py
git commit -m "feat(notify): events.py 토대 — Event·로스터·임계값 상수"
```

---

## Task 2: classify_full — 확정방향(e_dir) 노출

`notify.classify_last`는 (공식라벨, 속도)만 준다. 잠정전환은 sticky 확정방향 `E`가 디바운스 공식라벨보다 먼저 뒤집히는 순간을 잡아야 하므로 `e_dir`을 노출하는 `classify_full`을 추가하고, `classify_last`를 위임시킨다(단일 소스). 공식라벨 산출 로직은 불변 → `--selftest` 유지.

**Files:**
- Modify: `collect/notify.py` (classify_last 교체 영역 `notify.py:97-153`)
- Test: `collect/tests/test_notify_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_notify_v2.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notify


def test_classify_last_delegates_to_full():
    cum = [0, 10, 25, 45, 70, 100, 135]  # 단조 강한 매수
    label, pace = notify.classify_last(cum)
    full = notify.classify_full(cum)
    assert full["official"] == label
    assert full["pace"] == pace
    assert set(full.keys()) == {"official", "pace", "e_dir"}


def test_classify_full_e_dir_positive_on_sustained_buying():
    cum = [0, 10, 25, 45, 70, 100, 135, 175]
    assert notify.classify_full(cum)["e_dir"] == 1


def test_classify_full_neutral_on_flat():
    cum = [0, 0, 0, 0, 0, 0]
    full = notify.classify_full(cum)
    assert full["e_dir"] == 0
    assert full["official"] in {"중립", "혼조"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_notify_v2.py -v`
Expected: FAIL — `AttributeError: module 'notify' has no attribute 'classify_full'`

- [ ] **Step 3: Write minimal implementation**

`collect/notify.py`에서 기존 `classify_last`(라인 97~153) 함수를 아래 두 함수로 교체한다. 루프 본문은 동일하고, 마지막에 `E`를 함께 반환하도록만 바꾼다.

```python
def classify_full(cum, pace_span=9, base_span=30, dead_frac=0.4, floor=1.0,
                  confirm=3, stop_n=3, chop_win=7, chop_n=4, hold=3):
    """누적순매수 시퀀스 → 마지막 분 {official, pace, e_dir}. trend.classify와 동일 로직.

    official = 출력 디바운스된 공식라벨, e_dir = sticky 확정방향 E(-1/0/+1).
    e_dir이 official 계열보다 먼저 뒤집히는 구간이 '잠정 전환'(events.py)이다.
    """
    pace = typ = None
    E = run_dir = run_len = 0
    signs: list[int] = []
    last_pace, prev_cum = 0.0, None
    cur_off, cand, cand_len = "중립", None, 0
    for c in cum:
        if prev_cum is None:
            prev_cum = c
            continue
        flow = c - prev_cum
        prev_cum = c
        pace = _ema(flow, pace, pace_span)
        typ = _ema(abs(flow), typ, base_span)
        eps = max(dead_frac * typ, floor)
        di = 1 if pace > eps else (-1 if pace < -eps else 0)
        signs.append(0 if flow == 0 else (1 if flow > 0 else -1))
        win = signs[-chop_win:]
        flips = sum(1 for a, b in zip(win, win[1:]) if a != b)

        if di == run_dir:
            run_len += 1
        else:
            run_dir, run_len = di, 1
        confirmed = run_dir != 0 and run_len >= confirm
        newly = confirmed and run_dir != E
        if newly:
            E = run_dir
        stopped = run_dir == 0 and run_len >= stop_n
        choppy = flips >= chop_n and run_len < confirm

        if newly:
            lab = "매수전환" if E == 1 else "매도전환"
        elif E == 1:
            lab = "매수둔화" if stopped else ("혼조" if choppy else "지속매수")
        elif E == -1:
            lab = "매도둔화" if stopped else ("혼조" if choppy else "지속매도")
        else:
            lab = "혼조" if choppy else "중립"

        reg = {"매수전환": "지속매수", "매도전환": "지속매도"}.get(lab, lab)
        if reg == cur_off:
            cand, cand_len = None, 0
        elif reg == cand:
            cand_len += 1
            if cand_len >= hold:
                cur_off, cand, cand_len = reg, None, 0
        else:
            cand, cand_len = reg, 1
        last_pace = pace
    return {"official": cur_off, "pace": round(last_pace, 1), "e_dir": E}


def classify_last(cum, **kw):
    """하위호환 래퍼 — (공식라벨, 속도). 신규 코드는 classify_full 사용."""
    f = classify_full(cum, **kw)
    return f["official"], f["pace"]
```

- [ ] **Step 4: Run tests to verify they pass (parity 포함)**

Run: `cd collect && python -m pytest tests/test_notify_v2.py -v`
Expected: PASS (3 passed)

Run (회귀 — 기존 selftest가 최신 데이터로 여전히 일치):
`cd collect && python notify.py --selftest`
Expected: 각 주체 `OK`, 마지막 줄 `일치`

- [ ] **Step 5: Commit**

```bash
git add collect/notify.py collect/tests/test_notify_v2.py
git commit -m "feat(notify): classify_full로 확정방향 e_dir 노출, classify_last 위임"
```

---

## Task 3: 래칫 + 전환 감지기 (계단 노이즈 차단)

롤링 드로다운 래칫: 매도전환은 최근 `W`분 누적 고점 대비 `D`억 무너질 때만, 매수전환은 저점 대비 `D`억 회복할 때만 인정. 계단참 횡보의 미세하락은 게이트 미통과 → 침묵.

**Files:**
- Modify: `collect/events.py`
- Test: `collect/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_events.py 에 추가
def test_drawdown_ok_sell_requires_drop_from_recent_high():
    cum = [0, 50, 100, 150, 200, 198]  # 고점 200, 현재 198 → 2 하락
    assert events._drawdown_ok(-1, cum, D=30, W=20) is False
    cum2 = [0, 50, 100, 150, 200, 160]  # 40 하락 → 통과
    assert events._drawdown_ok(-1, cum2, D=30, W=20) is True


def test_drawdown_ok_buy_requires_rise_from_recent_low():
    cum = [0, -50, -100, -150, -120]  # 저점 -150, 현재 -120 → 30 회복
    assert events._drawdown_ok(1, cum, D=30, W=20) is True
    assert events._drawdown_ok(1, [0, -50, -100, -150, -145], D=30, W=20) is False


def test_confirmed_transition_fires_on_family_flip_with_drawdown():
    detail = {"official": "지속매도", "pace": -40.0, "e_dir": -1}
    cum = [0, 50, 100, 150, 200, 150, 110]  # 고점200 → 110, 90 하락(>D)
    out = events.detect_confirmed_transition("금융투자", detail, "지속매수", cum, events.CFG)
    assert len(out) == 1
    assert out[0]["kind"] == "확정전환"
    assert "매도전환" in out[0]["text"]


def test_confirmed_transition_suppressed_when_drawdown_too_small():
    # 계단 횡보 미세하락: official이 매도로 잠깐 바뀌어도 래칫 미통과 → 침묵
    detail = {"official": "지속매도", "pace": -2.0, "e_dir": -1}
    cum = [0, 50, 100, 150, 200, 199, 198, 197]  # 고점 대비 3 하락뿐
    out = events.detect_confirmed_transition("금융투자", detail, "지속매수", cum, events.CFG)
    assert out == []


def test_provisional_transition_fires_before_official_catches_up():
    # e_dir은 매수(+1)로 확정됐지만 official은 아직 매도계열 → 잠정 매수전환?
    detail = {"official": "지속매도", "pace": 35.0, "e_dir": 1}
    cum = [0, -50, -100, -150, -150, -110]  # 저점 -150 → -110, 40 회복(>D)
    out = events.detect_provisional_transition("금융투자", detail, prev_fast=-1,
                                               cum=cum, cfg=events.CFG)
    assert len(out) == 1
    assert out[0]["kind"] == "잠정전환"
    assert "매수전환?" in out[0]["text"]


def test_provisional_not_refired_same_regime():
    detail = {"official": "지속매도", "pace": 35.0, "e_dir": 1}
    cum = [0, -50, -100, -150, -150, -110]
    out = events.detect_provisional_transition("금융투자", detail, prev_fast=1,
                                               cum=cum, cfg=events.CFG)
    assert out == []  # prev_fast가 이미 +1 → 같은 국면, 재발사 안 함
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: FAIL — `AttributeError: module 'events' has no attribute '_drawdown_ok'`

- [ ] **Step 3: Write minimal implementation**

```python
# collect/events.py 에 추가
def _fam(label: str) -> int:
    return 1 if label in BUY_FAM else (-1 if label in SELL_FAM else 0)


def _drawdown_ok(direction: int, cum, D: float, W: int) -> bool:
    """direction +1=매수전환(저점대비 D 회복), -1=매도전환(고점대비 D 하락)."""
    if not cum:
        return False
    window = cum[-W:]
    last = cum[-1]
    if direction == -1:
        return (max(window) - last) >= D
    if direction == 1:
        return (last - min(window)) >= D
    return False


def detect_confirmed_transition(actor, detail, prev_official, cum, cfg):
    cur = detail["official"]
    cf = _fam(cur)
    if cf == 0 or prev_official is None:
        return []
    if cf == _fam(prev_official):
        return []
    if not _drawdown_ok(cf, cum, cfg["ratchet_D"], cfg["ratchet_W"]):
        return []
    label = "매수전환" if cf == 1 else "매도전환"
    text = f"{actor}  {prev_official}→{label}  ({detail['pace']:+.0f}억)"
    return [ev("확정전환", LABEL_ICON[label], text, dedup=f"confirm:{actor}")]


def detect_provisional_transition(actor, detail, prev_fast, cum, cfg):
    e = detail["e_dir"]
    if e == 0 or e == _fam(detail["official"]):
        return []                      # 방향 없음/official이 이미 따라잡음
    if e == prev_fast:
        return []                      # 같은 국면 — 이미 잠정 발사함
    if not _drawdown_ok(e, cum, cfg["ratchet_D"], cfg["ratchet_W"]):
        return []
    base = "매수전환" if e == 1 else "매도전환"
    text = f"{actor}  {detail['official']}→{base}?  ({detail['pace']:+.0f}억)"
    return [ev("잠정전환", LABEL_ICON[base], text, dedup=f"prov:{actor}")]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: PASS (이전 5 + 신규 7 = 12 passed)

- [ ] **Step 5: Commit**

```bash
git add collect/events.py collect/tests/test_events.py
git commit -m "feat(notify): 드로다운 래칫 + 확정/잠정 전환 감지기 (계단노이즈 차단)"
```

---

## Task 4: 지수 감지기 (윈도우·스파이크·신고저·디버전스)

**Files:**
- Modify: `collect/events.py`
- Test: `collect/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_events.py 에 추가
def test_index_window_fires_above_threshold():
    series = [100.0] * 6 + [100.4]  # 직전 5분前 100.0 → 100.4 = +0.40%
    out = events.detect_index_window("kospi", series, events.CFG)
    assert len(out) == 1 and out[0]["kind"] == "지수윈도우"
    assert "+0.40%" in out[0]["text"]


def test_index_window_silent_below_threshold():
    series = [100.0] * 6 + [100.1]  # +0.10% < 0.30%
    assert events.detect_index_window("kospi", series, events.CFG) == []


def test_index_spike_fires_on_one_minute_move():
    series = [100.0, 100.0, 100.25]  # 직전 100.0 → 100.25 = +0.25%
    out = events.detect_index_spike("kosdaq", series, events.CFG)
    assert len(out) == 1 and "+0.25%" in out[0]["text"]


def test_new_high_records_and_fires():
    out = events.detect_new_high_low("kospi", 2700.0, day_high=2680.0,
                                     day_low=2650.0, cfg=events.CFG)
    assert len(out) == 1 and "신고가" in out[0]["text"]


def test_new_low_fires():
    out = events.detect_new_high_low("kospi", 2640.0, day_high=2680.0,
                                     day_low=2650.0, cfg=events.CFG)
    assert len(out) == 1 and "신저가" in out[0]["text"]


def test_new_high_low_silent_within_range():
    assert events.detect_new_high_low("kospi", 2665.0, 2680.0, 2650.0, events.CFG) == []


def test_index_divergence_fires_on_opposite_moves():
    kospi = [100.0] * 6 + [100.3]   # +0.30%
    kosdaq = [100.0] * 6 + [99.7]   # -0.30%
    out = events.detect_index_divergence(kospi, kosdaq, events.CFG)
    assert len(out) == 1 and out[0]["kind"] == "지수디버전스"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_events.py -k "index or high or low or divergence" -v`
Expected: FAIL — `AttributeError: ... 'detect_index_window'`

- [ ] **Step 3: Write minimal implementation**

```python
# collect/events.py 에 추가
def detect_index_window(market, series, cfg):
    n = cfg["win_n"]
    if len(series) <= n:
        return []
    base, cur = series[-n - 1], series[-1]
    if not base:
        return []
    pct = (cur - base) / base * 100
    if abs(pct) < cfg["win_pct"]:
        return []
    icon = "📈" if pct > 0 else "📉"
    return [ev("지수윈도우", icon, f"{market.upper()} {n}분 {pct:+.2f}%",
               dedup=f"win:{market}:{'up' if pct > 0 else 'dn'}")]


def detect_index_spike(market, series, cfg):
    if len(series) < 2:
        return []
    base, cur = series[-2], series[-1]
    if not base:
        return []
    pct = (cur - base) / base * 100
    if abs(pct) < cfg["spike_pct"]:
        return []
    icon = "⚡"
    return [ev("지수스파이크", icon, f"{market.upper()} 1분 {pct:+.2f}%",
               dedup=f"spike:{market}")]


def detect_new_high_low(market, cur, day_high, day_low, cfg):
    eps = cfg["hilo_eps"]
    if day_high is None or cur > day_high + eps:
        return [ev("신고저", "🏁", f"{market.upper()} 당일 신고가 {cur:,.1f}",
                   dedup=f"hi:{market}")]
    if day_low is None or cur < day_low - eps:
        return [ev("신고저", "🏁", f"{market.upper()} 당일 신저가 {cur:,.1f}",
                   dedup=f"lo:{market}")]
    return []


def detect_index_divergence(kospi_series, kosdaq_series, cfg):
    n = cfg["win_n"]
    if len(kospi_series) <= n or len(kosdaq_series) <= n:
        return []

    def pct(s):
        b = s[-n - 1]
        return (s[-1] - b) / b * 100 if b else 0.0

    pk, pq = pct(kospi_series), pct(kosdaq_series)
    if pk * pq < 0 and abs(pk - pq) >= cfg["idxdiv_pct"] * 2:
        return [ev("지수디버전스", "↔️", f"코스피 {pk:+.2f}% ↔ 코스닥 {pq:+.2f}%",
                   dedup="idxdiv")]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: PASS (12 + 7 = 19 passed)

- [ ] **Step 5: Commit**

```bash
git add collect/events.py collect/tests/test_events.py
git commit -m "feat(notify): 지수 감지기 — 윈도우·스파이크·신고저·디버전스"
```

---

## Task 5: 주체 관계 감지기 (정렬·개인디버전스·flow급증·마일스톤)

**Files:**
- Modify: `collect/events.py`
- Test: `collect/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_events.py 에 추가
def test_alignment_fires_when_all_managed_buy():
    details = {"금융투자": {"e_dir": 1}, "외국인": {"e_dir": 1}, "연기금등": {"e_dir": 1}}
    out = events.detect_alignment(details, events.CFG)
    assert len(out) == 1 and "동반매수" in out[0]["text"]


def test_alignment_silent_when_mixed():
    details = {"금융투자": {"e_dir": 1}, "외국인": {"e_dir": -1}, "연기금등": {"e_dir": 0}}
    assert events.detect_alignment(details, events.CFG) == []


def test_individual_divergence_managed_buy_individual_sell():
    details = {"금융투자": {"e_dir": 1}, "외국인": {"e_dir": 1},
               "연기금등": {"e_dir": 1}, "개인": {"e_dir": -1}}
    out = events.detect_individual_divergence(details, ["금융투자", "외국인", "연기금등"], events.CFG)
    assert len(out) == 1 and out[0]["kind"] == "개인디버전스"


def test_flow_spike_fires_on_zscore_outlier():
    cum = [0]
    for i in range(1, 25):
        cum.append(cum[-1] + 5)       # 분당 +5 평탄
    cum.append(cum[-1] + 80)          # 급증
    out = events.detect_flow_spike("금융투자", cum, events.CFG)
    assert len(out) == 1 and out[0]["kind"] == "flow급증"


def test_flow_spike_silent_on_steady_flow():
    cum = [0]
    for i in range(1, 26):
        cum.append(cum[-1] + 5)
    assert events.detect_flow_spike("금융투자", cum, events.CFG) == []


def test_milestone_fires_exactly_on_mark():
    out = events.detect_milestone("금융투자", 30, events.CFG)
    assert len(out) == 1 and "30분" in out[0]["text"]
    assert events.detect_milestone("금융투자", 31, events.CFG) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_events.py -k "alignment or individual or flow or milestone" -v`
Expected: FAIL — `AttributeError: ... 'detect_alignment'`

- [ ] **Step 3: Write minimal implementation**

```python
# collect/events.py 에 추가
def detect_alignment(details, cfg):
    dirs = {d["e_dir"] for d in details.values()}
    if dirs == {1} or dirs == {-1}:
        side = "매수" if 1 in dirs else "매도"
        names = " ".join(details.keys())
        return [ev("정렬", "🧭", f"관리주체 동반{side} 정렬 ({names})", dedup="정렬")]
    return []


def detect_individual_divergence(details, managed, cfg):
    mdirs = [details[a]["e_dir"] for a in managed if a in details]
    ind = details.get("개인", {}).get("e_dir", 0)
    if mdirs and all(x == 1 for x in mdirs) and ind == -1:
        return [ev("개인디버전스", "🪞", "관리주체 매수 ↔ 개인 매도 (역추세 확인)", dedup="indiv")]
    if mdirs and all(x == -1 for x in mdirs) and ind == 1:
        return [ev("개인디버전스", "🪞", "관리주체 매도 ↔ 개인 매수", dedup="indiv")]
    return []


def detect_flow_spike(actor, cum, cfg):
    w = cfg["flow_win"]
    if len(cum) < w + 2:
        return []
    flows = [cum[i] - cum[i - 1] for i in range(1, len(cum))]
    last = flows[-1]
    base = flows[-w - 1:-1]
    mean = sum(base) / len(base)
    sd = (sum((x - mean) ** 2 for x in base) / len(base)) ** 0.5
    if sd == 0:
        return []
    z = (last - mean) / sd
    if abs(z) < cfg["flow_z"]:
        return []
    return [ev("flow급증", "💥", f"{actor} 분당 {last:+.0f}억 급증 (z{z:+.1f})",
               dedup=f"flow:{actor}")]


def detect_milestone(actor, streak, cfg):
    if streak in cfg["milestone_marks"]:
        return [ev("마일스톤", "🎯", f"{actor} 지속매수 {streak}분 연속",
                   dedup=f"mile:{actor}:{streak}")]
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: PASS (19 + 6 = 25 passed)

- [ ] **Step 5: Commit**

```bash
git add collect/events.py collect/tests/test_events.py
git commit -m "feat(notify): 주체 관계 감지기 — 정렬·개인디버전스·flow급증·마일스톤"
```

---

## Task 6: 개장/마감 세션 감지기

**Files:**
- Modify: `collect/events.py`
- Test: `collect/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_events.py 에 추가
def test_session_open_fires_once():
    done = {}
    out = events.detect_session("09:01", done, "KOSPI 2,650.0 (+0.10%)", events.CFG)
    assert len(out) == 1 and "개장" in out[0]["text"] and out[0]["dedup"] == "open"


def test_session_close_fires_after_1520():
    out = events.detect_session("15:21", {"open": True}, "KOSPI 2,650.0 (+0.10%)", events.CFG)
    kinds = [e["dedup"] for e in out]
    assert "close" in kinds


def test_session_silent_when_already_done():
    out = events.detect_session("15:25", {"open": True, "close": True}, "hdr", events.CFG)
    assert out == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_events.py -k session -v`
Expected: FAIL — `AttributeError: ... 'detect_session'`

- [ ] **Step 3: Write minimal implementation**

```python
# collect/events.py 에 추가
def detect_session(hhmm, session_done, header, cfg):
    out = []
    if not session_done.get("open") and hhmm >= "09:00":
        out.append(ev("개장마감", "🔔", f"개장 — {header}", dedup="open"))
    if not session_done.get("close") and hhmm >= "15:20":
        out.append(ev("개장마감", "🔔", f"마감 임박 — {header}", dedup="close"))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_events.py -v`
Expected: PASS (25 + 3 = 28 passed)

- [ ] **Step 5: Commit**

```bash
git add collect/events.py collect/tests/test_events.py
git commit -m "feat(notify): 개장/마감 세션 감지기"
```

---

## Task 7: notify.py 오케스트레이션 리팩터 (통합·포맷·상태)

`check_and_notify`를 다중 감지기 실행 + 분당 통합 + 새 포맷(헤더/요약/states footer) + 하트비트로 재작성한다. `DEFAULT_TRIGGERS`에 `연기금등`을 추가한다.

**Files:**
- Modify: `collect/notify.py` (`DEFAULT_TRIGGERS` `notify.py:31`, `check_and_notify` `notify.py:230-260`, 헬퍼 추가)
- Test: `collect/tests/test_notify_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_notify_v2.py 에 추가
import json


def _make_day(tmp_path, date, snaps):
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date}.json").write_text(
        json.dumps({"date": date, "snapshots": snaps}, ensure_ascii=False),
        encoding="utf-8")
    return tmp_path


def _snap(ts, k_idx, q_idx, fin_net):
    """최소 스냅샷: 금융투자 누적순매수=fin_net, 지수 포함."""
    block = lambda net: {
        "외국인": {"순매수": 0}, "개인": {"순매수": 0}, "기타법인": {"순매수": 0},
        "기관": {"순매수": net, "세부": {
            "금융투자": {"순매수": net}, "투신": {"순매수": 0}, "보험": {"순매수": 0},
            "사모펀드": {"순매수": 0}, "은행": {"순매수": 0}, "기타금융": {"순매수": 0},
            "연기금등": {"순매수": 0}, "국가/지자체": {"순매수": 0}}}}
    return {"ts": ts, "kospi": block(fin_net), "kosdaq": block(0),
            "index": {"kospi": {"지수": k_idx, "전일대비": 0.0, "등락률": 0.0},
                      "kosdaq": {"지수": q_idx, "전일대비": 0.0, "등락률": 0.0}}}


def test_index_header_format(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "_STATE_FILE", tmp_path / ".state.json")
    snaps = [_snap(f"2026-06-11T09:0{i}:00+09:00", 2650.0, 770.0, 0) for i in range(6)]
    snaps[-1]["index"]["kospi"]["등락률"] = 0.42
    snaps[-1]["index"]["kosdaq"]["등락률"] = -0.15
    root = _make_day(tmp_path, "2026-06-11", snaps)
    # 첫 호출 = 기준선(침묵), 둘째 호출에서 메시지 생성되도록 스파이크 유발
    notify.check_and_notify("2026-06-11", "kospi", data_root=root, test=True)
    snaps.append(_snap("2026-06-11T09:06:00+09:00", 2658.0, 770.0, 0))  # +0.30% 스파이크
    snaps[-1]["index"]["kospi"]["등락률"] = 0.42
    snaps[-1]["index"]["kosdaq"]["등락률"] = -0.15
    _make_day(tmp_path, "2026-06-11", snaps)
    msg = notify.check_and_notify("2026-06-11", "kospi", data_root=root, test=True)
    assert msg is not None
    assert "KOSPI 2,658.0 (+0.42%)" in msg
    assert "KOSDAQ 770.0 (-0.15%)" in msg
    assert msg.strip().splitlines()[-1].startswith("states:")
    assert "●지수스파이크" in msg


def test_first_observation_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "_STATE_FILE", tmp_path / ".state.json")
    snaps = [_snap(f"2026-06-11T09:0{i}:00+09:00", 2650.0, 770.0, 0) for i in range(3)]
    root = _make_day(tmp_path, "2026-06-11", snaps)
    assert notify.check_and_notify("2026-06-11", "kospi", data_root=root, test=True) is None


def test_default_triggers_include_yeongigeum():
    assert "연기금등" in notify.DEFAULT_TRIGGERS


def test_out_of_session_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "_STATE_FILE", tmp_path / ".state.json")
    snaps = [_snap("2026-06-11T08:50:00+09:00", 2650.0, 770.0, 0)]
    root = _make_day(tmp_path, "2026-06-11", snaps)
    assert notify.check_and_notify("2026-06-11", "kospi", data_root=root, test=True) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_notify_v2.py -v`
Expected: FAIL — `assert '연기금등' in [...]` 및 헤더/footer 미존재

- [ ] **Step 3: Write minimal implementation**

3a. `notify.py:31` 의 기본 트리거에 `연기금등` 추가:

```python
DEFAULT_TRIGGERS = ["금융투자", "외국인", "연기금등"]
```

3b. 헬퍼 추가(파일 하단, `_post_slack` 위 아무 곳):

```python
def _index_series(snaps, market):
    out = []
    for s in snaps:
        if not ("09:00" <= s["ts"][11:16] <= "15:30"):
            continue
        idx = s.get("index")
        if idx and market in idx and idx[market].get("지수") is not None:
            out.append(idx[market]["지수"])
    return out


def _index_rate(snaps, market):
    for s in reversed(snaps):
        idx = s.get("index")
        if idx and market in idx:
            return idx[market].get("지수"), idx[market].get("등락률")
    return None, None


def _index_header(snaps):
    parts = []
    for m in ("kospi", "kosdaq"):
        v, rate = _index_rate(snaps, m)
        if v is None:
            continue
        r = f"{rate:+.2f}%" if rate is not None else "?"
        parts.append(f"{m.upper()} {v:,.1f} ({r})")
    return " · ".join(parts)


def _minutes_between(a, b):
    from datetime import datetime
    return abs((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()) / 60


def _save_state_full(state):
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _format_v2(header, fired, details, ts, enabled, fired_kinds, heartbeat):
    import events
    lines = [header] if header else []
    for e in sorted(fired, key=lambda x: x["rank"]):
        lines.append(f"{e['icon']} {e['text']}")
    core = [a for a in BOARD if a in details]
    hb = "💤 " if heartbeat else ""
    lines.append(hb + "요약 : " + " ".join(f"{a}{ICON[details[a]['official']]}" for a in core))
    lines.append(f"{ts[:16].replace('T', ' ')} · 통합")
    lines.append(f"<{DASHBOARD_URL}|대시보드 열기>")
    lines.append(events.render_roster(enabled, fired_kinds))
    return "\n".join(lines)
```

3c. `check_and_notify`(라인 230~260) 전체를 교체:

```python
def check_and_notify(date=None, market="kospi", data_root=_DATA_REPO_ROOT, test=False):
    """수집 직후 1회 호출. 다중 감지기 → 분당 1통합 메시지 발송(또는 test 시 stdout)."""
    import events
    if date is None:
        import storage
        date = storage.today_str()

    data = json.loads((Path(data_root) / "data" / f"{date}.json").read_text(encoding="utf-8"))
    snaps = data["snapshots"]
    if not snaps:
        return None
    ts = snaps[-1]["ts"]
    if not ("09:00" <= ts[11:16] <= "15:30"):
        return None

    cfg = events.CFG
    managed = _monitor_actors()
    details, cums = {}, {}
    for a in ALL_ACTORS:
        cum = _series(snaps, a, market)
        cums[a] = cum
        details[a] = classify_full(cum) if len(cum) >= 2 else {"official": "중립", "pace": 0.0, "e_dir": 0}

    st = _load_state()
    fresh_day = st.get("date") != date
    prev_labels = {} if fresh_day else st.get("labels", {})
    prev_fast = {} if fresh_day else st.get("fast_dir", {})
    fired_map = {} if fresh_day else st.get("fired", {})
    day_high = {} if fresh_day else st.get("day_high", {})
    day_low = {} if fresh_day else st.get("day_low", {})
    streak = {} if fresh_day else st.get("streak", {})
    session_done = {} if fresh_day else st.get("session_done", {})
    last_alert = None if fresh_day else st.get("last_alert_ts")

    for a in ALL_ACTORS:
        streak[a] = streak.get(a, 0) + 1 if details[a]["official"] == "지속매수" else 0

    enabled = events.enabled_events()
    cur_series = _index_series(snaps, market)
    header = _index_header(snaps)
    raw = []

    if not fresh_day:
        for a in managed:
            if "확정전환" in enabled:
                raw += events.detect_confirmed_transition(a, details[a], prev_labels.get(a), cums[a], cfg)
            if "잠정전환" in enabled:
                raw += events.detect_provisional_transition(a, details[a], prev_fast.get(a, 0), cums[a], cfg)
            if "flow급증" in enabled:
                raw += events.detect_flow_spike(a, cums[a], cfg)
            if "마일스톤" in enabled:
                raw += events.detect_milestone(a, streak.get(a, 0), cfg)
        if "정렬" in enabled:
            raw += events.detect_alignment({a: details[a] for a in managed}, cfg)
        if "개인디버전스" in enabled:
            raw += events.detect_individual_divergence(details, managed, cfg)
        if "지수윈도우" in enabled:
            raw += events.detect_index_window(market, cur_series, cfg)
        if "지수스파이크" in enabled:
            raw += events.detect_index_spike(market, cur_series, cfg)
        if "신고저" in enabled and cur_series:
            raw += events.detect_new_high_low(market, cur_series[-1], day_high.get(market), day_low.get(market), cfg)
        if "지수디버전스" in enabled:
            raw += events.detect_index_divergence(_index_series(snaps, "kospi"), _index_series(snaps, "kosdaq"), cfg)
        if "개장마감" in enabled:
            raw += events.detect_session(ts[11:16], session_done, header, cfg)

    # 쿨다운/dedup 필터
    fired = []
    for e in raw:
        last = fired_map.get(e["dedup"])
        cd = events.COOLDOWN.get(e["kind"], 0)
        if last is not None and _minutes_between(last, ts) < cd:
            continue
        fired.append(e)
        fired_map[e["dedup"]] = ts
    for e in fired:
        if e["dedup"] == "open":
            session_done["open"] = True
        if e["dedup"] == "close":
            session_done["close"] = True
    if cur_series:
        c = cur_series[-1]
        day_high[market] = max(day_high.get(market, c), c)
        day_low[market] = min(day_low.get(market, c), c)

    heartbeat = (not fired and not fresh_day and "하트비트" in enabled and
                 (last_alert is None or _minutes_between(last_alert, ts) >= cfg["heartbeat_min"]))

    new_state = {
        "date": date,
        "labels": {a: details[a]["official"] for a in managed},
        "fast_dir": {a: details[a]["e_dir"] for a in managed},
        "fired": fired_map, "day_high": day_high, "day_low": day_low,
        "streak": streak, "session_done": session_done, "last_alert_ts": last_alert,
    }
    if fresh_day or (not fired and not heartbeat):
        _save_state_full(new_state)
        return None

    new_state["last_alert_ts"] = ts
    _save_state_full(new_state)

    fired_kinds = {e["kind"] for e in fired}
    if heartbeat:
        fired_kinds.add("하트비트")
    msg = _format_v2(header, fired, details, ts, enabled, fired_kinds, heartbeat)

    cfg_slack = _slack_config()
    if not test and (cfg_slack.get("token") or cfg_slack.get("webhook")):
        try:
            _post_slack(msg, cfg_slack)
        except Exception as e:
            print(f"[notify] slack post failed: {e}", flush=True)
    else:
        print("[notify]\n" + msg, flush=True)
    return msg
```

3d. 더 이상 쓰지 않는 옛 헬퍼 정리: `_format`(구버전), `_disp`, `current_board`, `_save_state`는 `_selftest`가 `current_board`를 쓰므로 **남겨둔다**. 옛 `_format`/`_disp`는 미사용이지만 selftest 무관 — 제거해도 되나 본 작업 범위 밖이면 남겨도 무방.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_notify_v2.py -v`
Expected: PASS (Task2 3개 + 신규 4개 = 7 passed)

Run (전체 회귀): `cd collect && python -m pytest tests/ -v`
Expected: 전부 PASS

Run (selftest 회귀): `cd collect && python notify.py --selftest`
Expected: `일치`

- [ ] **Step 5: Commit**

```bash
git add collect/notify.py collect/tests/test_notify_v2.py
git commit -m "feat(notify): 다중 이벤트 통합 발송 + 지수헤더 + states footer + 하트비트"
```

---

## Task 8: calibrate.py — 과거일 리플레이로 임계값 확정

감지기별 일일 발사횟수와 확정전환 오발사 후보를 뽑아 `CFG`(특히 `ratchet_D`, `win_pct`, `spike_pct`)를 데이터로 정한다. 테스트보다 **분석 도구**라 단위테스트는 1개(스모크)만 둔다.

**Files:**
- Create: `collect/calibrate.py`
- Test: `collect/tests/test_notify_v2.py` (스모크)

- [ ] **Step 1: Write the failing test**

```python
# collect/tests/test_notify_v2.py 에 추가
def test_calibrate_replay_counts_events(tmp_path):
    import calibrate
    snaps = []
    base = 0
    for i in range(60):
        base += 5 if i < 30 else -8  # 전반 매수 → 후반 매도 (확정전환 1회 기대)
        hh, mm = divmod(i, 60)
        snaps.append(_snap(f"2026-06-11T09:{i:02d}:00+09:00", 2650.0 + i * 0.5, 770.0, base))
    _make_day(tmp_path, "2026-06-11", snaps)
    report = calibrate.replay("2026-06-11", "kospi", data_root=tmp_path)
    assert isinstance(report, dict)
    assert report.get("확정전환", 0) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd collect && python -m pytest tests/test_notify_v2.py -k calibrate -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'calibrate'`

- [ ] **Step 3: Write minimal implementation**

```python
# collect/calibrate.py
"""과거 거래일을 분단위로 리플레이해 감지기별 발사횟수를 집계한다.

CFG(임계값) 튜닝 근거용. 누적 데이터 파일의 스냅샷을 1분씩 늘려가며
notify.check_and_notify와 동일한 감지 로직을 재현, kind별 카운트를 낸다.
사용:  python calibrate.py 2026-06-01 --market kospi
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import events  # noqa: E402
import notify  # noqa: E402

_DATA = Path(__file__).resolve().parents[2] / "kb-investor-flow-data"


def replay(date, market="kospi", data_root=_DATA, cfg=None):
    cfg = cfg or events.CFG
    full = json.loads((Path(data_root) / "data" / f"{date}.json").read_text(encoding="utf-8"))
    snaps = full["snapshots"]
    counts: dict = {}
    prev_labels, prev_fast, fired_map = {}, {}, {}
    day_high, day_low, streak, session_done, last_alert = {}, {}, {}, {}, None
    managed = notify._monitor_actors()
    enabled = events.enabled_events()

    for n in range(2, len(snaps) + 1):
        sub = snaps[:n]
        ts = sub[-1]["ts"]
        if not ("09:00" <= ts[11:16] <= "15:30"):
            continue
        details, cums = {}, {}
        for a in notify.ALL_ACTORS:
            cum = notify._series(sub, a, market)
            cums[a] = cum
            details[a] = notify.classify_full(cum) if len(cum) >= 2 else {"official": "중립", "pace": 0.0, "e_dir": 0}
        for a in notify.ALL_ACTORS:
            streak[a] = streak.get(a, 0) + 1 if details[a]["official"] == "지속매수" else 0
        cur = notify._index_series(sub, market)
        header = notify._index_header(sub)
        raw = []
        for a in managed:
            raw += events.detect_confirmed_transition(a, details[a], prev_labels.get(a), cums[a], cfg)
            raw += events.detect_provisional_transition(a, details[a], prev_fast.get(a, 0), cums[a], cfg)
            raw += events.detect_flow_spike(a, cums[a], cfg)
            raw += events.detect_milestone(a, streak.get(a, 0), cfg)
        raw += events.detect_alignment({a: details[a] for a in managed}, cfg)
        raw += events.detect_individual_divergence(details, managed, cfg)
        raw += events.detect_index_window(market, cur, cfg)
        raw += events.detect_index_spike(market, cur, cfg)
        if cur:
            raw += events.detect_new_high_low(market, cur[-1], day_high.get(market), day_low.get(market), cfg)
        raw += events.detect_index_divergence(notify._index_series(sub, "kospi"), notify._index_series(sub, "kosdaq"), cfg)
        raw += events.detect_session(ts[11:16], session_done, header, cfg)

        for e in raw:
            last = fired_map.get(e["dedup"])
            cd = events.COOLDOWN.get(e["kind"], 0)
            if last is not None and notify._minutes_between(last, ts) < cd:
                continue
            fired_map[e["dedup"]] = ts
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
            if e["dedup"] == "open":
                session_done["open"] = True
            if e["dedup"] == "close":
                session_done["close"] = True
        if cur:
            c = cur[-1]
            day_high[market] = max(day_high.get(market, c), c)
            day_low[market] = min(day_low.get(market, c), c)
        prev_labels = {a: details[a]["official"] for a in managed}
        prev_fast = {a: details[a]["e_dir"] for a in managed}
    return counts


def main():
    import argparse
    p = argparse.ArgumentParser(description="감지기 발사횟수 리플레이")
    p.add_argument("date")
    p.add_argument("--market", default="kospi", choices=["kospi", "kosdaq"])
    args = p.parse_args()
    rep = replay(args.date, args.market)
    print(f"[{args.date} {args.market.upper()}] 감지기별 발사횟수")
    for k in events.EVENT_KINDS:
        print(f"  {k:10} {rep.get(k, 0)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd collect && python -m pytest tests/test_notify_v2.py -k calibrate -v`
Expected: PASS

- [ ] **Step 5: 실데이터 캘리브레이션 + CFG 확정**

origin/data의 과거 거래일에 대해 실행해 발사횟수를 본다(데몬 환경 데이터가 있는 곳에서):

Run: `cd collect && python calibrate.py 2026-06-01 --market kospi`
Expected: kind별 카운트 출력.

판단 기준:
- `확정전환`이 하루 한 자릿수 초중반이면 `ratchet_D` 적정. 과다하면 `D`↑.
- `지수윈도우`/`지수스파이크`가 과다하면 `win_pct`/`spike_pct`↑.
- 결과를 보고 `events.CFG` 값을 조정 커밋. (가설 C·`D=30`을 데이터로 대체)

- [ ] **Step 6: Commit**

```bash
git add collect/calibrate.py collect/tests/test_notify_v2.py
git commit -m "feat(notify): calibrate.py 리플레이로 감지기 발사횟수 집계"
# CFG 조정이 있었다면:
git add collect/events.py && git commit -m "tune(notify): 캘리브레이션 기반 임계값 확정"
```

---

## Task 9: 최종 회귀 + README 메모

**Files:**
- Modify: `collect/README.md` (있으면 알림 v2 한 단락 추가)

- [ ] **Step 1: 전체 테스트**

Run: `cd collect && python -m pytest tests/ -v`
Expected: 전부 PASS (test_parse, test_storage, test_events 28, test_notify_v2 8+)

- [ ] **Step 2: selftest 회귀**

Run: `cd collect && python notify.py --selftest`
Expected: `일치`

- [ ] **Step 3: 라이브 dry 출력 확인 (옵션, 데이터 있는 환경)**

Run: `cd collect && python notify.py --test`
Expected: stdout에 헤더/이벤트/`states:` footer가 보이거나, 변화 없으면 무출력.

- [ ] **Step 4: README 한 단락 추가** (`collect/README.md` 알림 섹션)

```markdown
### 알림 v2 (events.py)
매분 12종 감지기를 돌려 그 분의 이벤트를 1메시지로 통합 발송한다.
`NOTIFY_EVENTS`(쉼표구분)로 감지기 on/off — 메시지 맨끝 `states:` 줄에서
발사빈도를 보고 무용한 감지기를 솎아낸다. 임계값은 `events.CFG`,
근거는 `python calibrate.py <date>`. 트리거 주체 기본 = 금융투자·외국인·연기금등.
```

- [ ] **Step 5: Commit**

```bash
git add collect/README.md
git commit -m "docs(notify): 알림 v2 사용법 README 추가"
```

---

## Self-Review 결과

- **스펙 커버리지:** §3 구조(events/notify/calibrate)=Task1·7·8 / §4 12감지기=Task3·4·5·6 / §5 래칫=Task3 / §6 상태스키마=Task7 / §7 포맷·헤더·footer=Task1·7 / §8 게이팅·쿨다운=Task7 / §9 임계값=Task1+Task8 / §10 테스트·캘리브레이션=전 Task+Task8. 1번(지수 전일종가%)=Task7 `_index_header`. 누락 없음.
- **플레이스홀더:** `ratchet_D=30` 등은 의도된 캘리브레이션 출발점(Task8에서 데이터로 확정) — TODO 아님.
- **타입 일관성:** Event=dict(kind/icon/text/rank/dedup) 전 Task 동일. `classify_full`→{official,pace,e_dir} Task2 정의, Task3·7·8에서 동일 키 사용. `detect_*` 시그니처 Task7 호출부와 정의부 일치 확인.
