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
