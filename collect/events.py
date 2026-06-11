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
