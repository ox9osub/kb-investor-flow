"""투자주체 추세 상태 변화 → 슬랙 알림 (라이브 수집 파이프라인용).

매 분 수집 직후 호출돼, 각 주체의 8개 라벨 상태(trend.py와 동일 로직)를 계산하고
직전 분 대비 **라벨이 바뀐 주체**가 있으면 슬랙으로 한 줄 알림을 보낸다.

pandas 의존을 피하려고 분류 로직을 순수 파이썬으로 재구현했다(수집 데몬 venv는
requests/bs4만 둠). 로직·파라미터는 trend.classify와 일치하며,
`python collect/notify.py <date> --selftest` 로 trend.py와 라벨 일치를 검증한다.

슬랙 설정 (우선순위: 환경변수 → collect/.slack.json → 미설정 시 stdout):
  봇토큰 방식  SLACK_BOT_TOKEN(or SLACK_TOKEN) + SLACK_CHANNEL  ─ chat.postMessage
  웹훅 방식    SLACK_WEBHOOK_URL
  .slack.json  {"token": "xoxb-…", "channel": "C…"} 또는 {"webhook": "https://…"}
              (gitignore 처리됨. 봇은 해당 채널에 /invite 돼 있어야 함)

트리거 주체 (NOTIFY_ACTORS 환경변수로 재정의, 쉼표구분):
  기본 = 금융투자 only. 금융투자가 분단위로 가장 깔끔(하루 3~22회 변화)하고
  사용자 1순위 관심사이기 때문. 매 알림에 11개 주체 전체 상태를 함께 싣는다.
  외국인·개인 등 대형주체는 분단위로 하루 15~23회씩 출렁여 단독 트리거 시 과다.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_DATA_REPO_ROOT = _THIS_DIR.parent.parent / "kb-investor-flow-data"
_STATE_FILE = _THIS_DIR / ".trend_state.json"
_SLACK_CFG = _THIS_DIR / ".slack.json"
DEFAULT_CHANNEL = "C0B99209CKB"
DEFAULT_TRIGGERS = ["금융투자", "연기금등", "외국인"]

PRIORITY = "금융투자"
ALL_ACTORS = ["외국인", "개인", "기관", "기타법인",
              "금융투자", "투신", "보험", "사모펀드", "은행", "기타금융", "연기금등"]
# 출력 순위: 금융투자 > 연기금 > 외국인 > 나머지(기존 ALL_ACTORS 순).
_RANK_HEAD = ["금융투자", "연기금등", "외국인"]

# 8라벨 아이콘 (trend._ARROW와 동일): 지속=차트, 전환=원, 둔화=다이아, 혼조🟡 중립⚪
ICON = {"지속매수": "📈", "매수전환": "🔴", "매수둔화": "🔸", "혼조": "🟡",
        "중립": "⚪", "매도둔화": "🔹", "매도전환": "🔵", "지속매도": "📉"}

_TOP = {"외국인", "개인", "기관", "기타법인"}


def _rank(a: str) -> int:
    return _RANK_HEAD.index(a) if a in _RANK_HEAD else len(_RANK_HEAD) + ALL_ACTORS.index(a)


def _monitor_actors() -> list[str]:
    env = os.environ.get("NOTIFY_ACTORS", "").strip()
    picked = [a.strip() for a in env.split(",") if a.strip()] if env else list(DEFAULT_TRIGGERS)
    if PRIORITY not in picked:
        picked.append(PRIORITY)
    return [a for a in ALL_ACTORS if a in picked]


def _slack_config() -> dict:
    tok = os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("SLACK_TOKEN")
    ch = os.environ.get("SLACK_CHANNEL")
    wh = os.environ.get("SLACK_WEBHOOK_URL")
    if not tok and not wh and _SLACK_CFG.exists():
        try:
            j = json.loads(_SLACK_CFG.read_text(encoding="utf-8"))
            tok = tok or j.get("token")
            ch = ch or j.get("channel")
            wh = wh or j.get("webhook")
        except Exception:
            pass
    return {"token": tok, "channel": ch or DEFAULT_CHANNEL, "webhook": wh}


def _series(snapshots, actor: str, market: str) -> list[int]:
    """09:00~15:30 구간의 actor 누적순매수 시퀀스."""
    out = []
    for s in snapshots:
        hhmm = s["ts"][11:16]
        if not ("09:00" <= hhmm <= "15:30"):
            continue
        k = s[market]
        if actor in _TOP:
            out.append(k[actor]["순매수"])
        else:
            out.append(k["기관"].get("세부", {}).get(actor, {}).get("순매수", 0))
    return out


def _ema(x: float, prev: float | None, span: int) -> float:
    a = 2.0 / (span + 1)
    return x if prev is None else a * x + (1 - a) * prev


def classify_last(cum, pace_span=9, base_span=30, dead_frac=0.4, floor=1.0,
                  confirm=3, stop_n=3, chop_win=7, chop_n=4, hold=3):
    """누적순매수 시퀀스 → (마지막 분 공식라벨, 현재속도). trend.classify와 동일 로직.

    확정방향 E를 sticky 유지 + 출력라벨을 hold분 디바운스 — 1~2분 깜빡임을 흡수해
    공식 라벨은 천천히만 바뀐다(알림 폭주 방지).
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
    return cur_off, round(last_pace, 1)


def current_board(date: str, market: str = "kospi", data_root: Path = _DATA_REPO_ROOT):
    """{주체: (라벨, 속도)} + 마지막 스냅샷 ts."""
    data = json.loads((Path(data_root) / "data" / f"{date}.json").read_text(encoding="utf-8"))
    snaps = data["snapshots"]
    board = {}
    for a in ALL_ACTORS:
        cum = _series(snaps, a, market)
        board[a] = classify_last(cum) if len(cum) >= 2 else ("중립", 0.0)
    return board, (snaps[-1]["ts"] if snaps else "")


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(date: str, labels: dict) -> None:
    _STATE_FILE.write_text(json.dumps({"date": date, "labels": labels},
                                      ensure_ascii=False), encoding="utf-8")


# '그 외' 주체를 진영별로 묶는 버킷 (가독성). 각 주체는 자기 아이콘으로 표기해 8라벨 유지.
_BUCKETS = [
    ("📈 매수", {"지속매수", "매수전환", "매수둔화"}),
    ("📉 매도", {"지속매도", "매도전환", "매도둔화"}),
    ("🟡 혼조", {"혼조"}),
    ("⚪ 중립", {"중립"}),
]


def _format(changed: dict, board: dict, ts: str, market: str) -> str:
    # 1줄: 변화 주체 (금융투자 > 연기금 > 외국인 > 나머지 순)
    order = sorted(changed, key=_rank)
    head = ", ".join(
        f"{a} {ICON[changed[a][0]]}{changed[a][0]}→{ICON[changed[a][1]]}{changed[a][1]}"
        f"({board[a][1]:+.0f}억/분)" for a in order
    )
    # 그 다음: 나머지 주체를 매수/매도/혼조/중립 진영으로 묶어 줄바꿈
    others = [a for a in ALL_ACTORS if a not in changed]
    lines = [head]
    for title, labs in _BUCKETS:
        members = sorted((a for a in others if board[a][0] in labs), key=_rank)
        if members:
            lines.append(f"{title} · " + " · ".join(f"{ICON[board[a][0]]}{a}" for a in members))
    when = ts[:16].replace("T", " ") if ts else ""
    lines.append(f"{when} · {market.upper()}")
    return "\n".join(lines)


def _post_slack(text: str, cfg: dict) -> None:
    import requests
    if cfg.get("token"):
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {cfg['token']}"},
            json={"channel": cfg["channel"], "text": text}, timeout=10,
        )
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"slack api error: {data.get('error')}")
    elif cfg.get("webhook"):
        requests.post(cfg["webhook"], json={"text": text}, timeout=10).raise_for_status()
    else:
        raise RuntimeError("no slack config (SLACK_BOT_TOKEN+SLACK_CHANNEL / webhook / .slack.json)")


def check_and_notify(date: str | None = None, market: str = "kospi",
                     data_root: Path = _DATA_REPO_ROOT, test: bool = False):
    """수집 직후 1회 호출용. 트리거 주체 라벨 변화 시 슬랙 발송(또는 test 시 stdout)."""
    if date is None:
        import storage
        date = storage.today_str()
    board, ts = current_board(date, market, data_root)
    monitored = _monitor_actors()
    cur = {a: board[a][0] for a in monitored}

    state = _load_state()
    prev = state.get("labels") if state.get("date") == date else None
    _save_state(date, cur)

    if prev is None:                       # 그날 첫 관측 → 기준선만 잡고 침묵
        return None
    changed = {a: (prev[a], cur[a]) for a in monitored
               if a in prev and prev[a] != cur[a]}
    if not changed:
        return None

    msg = _format(changed, board, ts, market)
    cfg = _slack_config()
    if not test and (cfg.get("token") or cfg.get("webhook")):
        try:
            _post_slack(msg, cfg)
        except Exception as e:
            print(f"[notify] slack post failed: {e}", flush=True)
    else:
        print("[notify]\n" + msg, flush=True)
    return msg


def _selftest(date: str, market: str = "kospi"):
    """trend.classify(pandas)와 마지막-분 라벨 일치 검증."""
    import sys
    sys.path.insert(0, str(_THIS_DIR))
    import trend
    res = trend.classify_day(date, market)
    board, _ = current_board(date, market)
    ok = True
    for a in ALL_ACTORS:
        if a not in res:
            continue
        pd_lab = res[a]["state"].iloc[-1]
        my_lab = board[a][0]
        mark = "OK" if pd_lab == my_lab else "DIFF"
        if pd_lab != my_lab:
            ok = False
        print(f"  {a:8} pandas={pd_lab:6} pure={my_lab:6} {mark}")
    print("일치" if ok else "불일치 — 파라미터/그리드 차이 점검 필요")


def main():
    import argparse
    p = argparse.ArgumentParser(description="투자주체 상태변화 슬랙 알림")
    p.add_argument("date", nargs="?", help="YYYY-MM-DD (생략 시 오늘)")
    p.add_argument("--market", default="kospi", choices=["kospi", "kosdaq"])
    p.add_argument("--test", action="store_true", help="슬랙 대신 stdout 출력")
    p.add_argument("--selftest", action="store_true", help="trend.py와 라벨 일치 검증")
    args = p.parse_args()
    if args.selftest:
        date = args.date or sorted(
            f.stem for f in (_DATA_REPO_ROOT / "data").glob("????-??-??.json"))[-1]
        _selftest(date, args.market)
        return
    cfg = _slack_config()
    configured = bool(cfg.get("token") or cfg.get("webhook"))
    check_and_notify(args.date, args.market, test=args.test or not configured)


if __name__ == "__main__":
    main()
