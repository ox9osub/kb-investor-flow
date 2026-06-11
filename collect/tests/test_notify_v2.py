# collect/tests/test_notify_v2.py
import sys
import json
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


def test_classify_full_e_dir_negative_on_sustained_selling():
    cum = [0, -10, -25, -45, -70, -100, -135, -175]  # 단조 강한 매도
    assert notify.classify_full(cum)["e_dir"] == -1


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


def test_no_spurious_new_high_when_baseline_has_higher_peak(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "_STATE_FILE", tmp_path / ".state.json")
    # 기준선에 이미 2660 진고점이 있고 마지막은 2650으로 내려온 상태
    prices = [2650.0, 2655.0, 2660.0, 2655.0, 2650.0, 2650.0]
    snaps = [_snap(f"2026-06-11T09:0{i}:00+09:00", prices[i], 770.0, 0) for i in range(6)]
    root = _make_day(tmp_path, "2026-06-11", snaps)
    notify.check_and_notify("2026-06-11", "kospi", data_root=root, test=True)  # 기준선
    # 다음 분 2658 — 마지막(2650)보다 높지만 당일 진고점(2660)보단 낮음 → 신고가 아님
    snaps.append(_snap("2026-06-11T09:06:00+09:00", 2658.0, 770.0, 0))
    _make_day(tmp_path, "2026-06-11", snaps)
    msg = notify.check_and_notify("2026-06-11", "kospi", data_root=root, test=True)
    assert msg is None or "신고가" not in msg
