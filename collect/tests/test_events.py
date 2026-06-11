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


def test_ev_custom_dedup_flows_through():
    e = events.ev("flow급증", "💥", "금융투자 분당 +80억 급증 (z+3.0)", dedup="flow:금융투자")
    assert e["dedup"] == "flow:금융투자"


def test_ev_unknown_kind_raises():
    import pytest
    with pytest.raises(ValueError):
        events.ev("없는종류", "x", "y")


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
    assert out[0]["dedup"] == "confirm:금융투자"


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
    assert out[0]["dedup"] == "prov:금융투자"


def test_drawdown_ok_window_excludes_old_extremes():
    # 옛 고점(200)은 W=3 윈도우 밖 → 최근 3분 [120,118,116]만 봄 → 4 하락뿐 → False
    cum = [0, 100, 200, 120, 118, 116]
    assert events._drawdown_ok(-1, cum, D=30, W=3) is False
    # 같은 데이터, W=20이면 옛 고점 200 포함 → 84 하락 → True
    assert events._drawdown_ok(-1, cum, D=30, W=20) is True


def test_provisional_not_refired_same_regime():
    detail = {"official": "지속매도", "pace": 35.0, "e_dir": 1}
    cum = [0, -50, -100, -150, -150, -110]
    out = events.detect_provisional_transition("금융투자", detail, prev_fast=1,
                                               cum=cum, cfg=events.CFG)
    assert out == []  # prev_fast가 이미 +1 → 같은 국면, 재발사 안 함
