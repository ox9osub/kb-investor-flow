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
            hi, lo = max(cur), min(cur)
            day_high[market] = max(day_high.get(market, hi), hi)
            day_low[market] = min(day_low.get(market, lo), lo)
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
