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

# 동일 dedup 키가 이 분(分) 안에 또 떠도 억제. 0 = 쿨다운 없음, 미등록 kind도 0(항상 허용).
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
    if kind not in EVENT_KINDS:
        raise ValueError(f"ev(): unknown kind {kind!r}")
    return {"kind": kind, "icon": icon, "text": text,
            "rank": EVENT_KINDS.index(kind), "dedup": dedup or kind}


def enabled_events() -> list[str]:
    env = os.environ.get("NOTIFY_EVENTS", "").strip()
    if not env:
        return list(EVENT_KINDS)
    picked = {a.strip() for a in env.split(",") if a.strip()}
    return [k for k in EVENT_KINDS if k in picked]


def render_roster(enabled: list[str], fired: set[str]) -> str:
    fr = [k for k in enabled if k in fired]
    qt = [k for k in enabled if k not in fired]
    roster = " ".join("●" + k for k in fr)
    if fr and qt:
        roster += " · "
    roster += " ".join(qt)
    return "states: " + roster


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
    variance = sum((x - mean) ** 2 for x in base) / len(base)
    sd = variance ** 0.5
    if sd == 0:
        # 베이스 구간 분산이 0일 때: last가 mean과 같으면 침묵, 다르면 무한 z → 급증 판정
        if last == mean:
            return []
        z = float("inf") if last > mean else float("-inf")
    else:
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
