"""투자주체별 누적순매수 → 매분 '추세 상태' 분류기.

KB 페이지가 주는 값은 장 시작부터의 **누적 순매수**(억원)다. 그 곡선의
기울기(=분당 실제 순매수)를 매분 평가해 각 주체가 지금 어떤 상태인지 라벨링한다.

상태(7종):
  지속매수 / 지속매도          ─ 같은 방향으로 계속 매매 중
  매수둔화 / 매도둔화          ─ 매수/매도를 (사실상) 멈춤 (속도가 데드밴드 안)
  매수전환 / 매도전환          ─ 반대 방향에서 막 돌아섬 (매도→매수 / 매수→매도)
  혼조                        ─ 짧은 구간에 부호가 자주 뒤집힘 (방향 불명확)
  중립                        ─ 아직 방향이 확립된 적 없음 (개장 직후 등)

핵심 파라미터:
  pace_span  현재 매매속도 EMA 창(분). 작을수록 민감/노이즈.
  base_span  '전형적 매매강도' 기준 EMA 창. 데드밴드 크기 산정용.
  dead_frac  데드밴드 = dead_frac × 전형강도. 이 안이면 '둔화/멈춤'으로 본다.
  floor      데드밴드 하한(억/분). 거래 미미한 주체(은행·보험)의 노이즈 차단.
  confirm    새 방향이 이 분(分)만큼 지속돼야 '전환'으로 확정 (마이크로 플립 무시).
  chop_win/n 최근 chop_win분 중 부호변경 chop_n회 이상이면 '혼조'.

가격(122630 등)과의 관계는 별도 분석 참고. 여기서는 순수 자금흐름 추세만 본다.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

# data 브랜치 worktree (collect/ 기준 형제 디렉토리)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "kb-investor-flow-data" / "data"

TOP = ["외국인", "개인", "기관", "기타법인"]
SUBS = ["금융투자", "투신", "보험", "사모펀드", "은행", "기타금융", "연기금등", "국가/지자체"]
ACTORS = ["외국인", "개인", "기관", "기타법인"] + SUBS

_BUY = {"지속매수", "매수전환"}
_SELL = {"지속매도", "매도전환"}


def load_day(date: str, market: str = "kospi", data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """하루치 JSON → index=timestamp, columns=주체별 누적순매수 DataFrame."""
    d = json.loads((Path(data_dir) / f"{date}.json").read_text(encoding="utf-8"))
    rows = []
    for s in d["snapshots"]:
        t = pd.Timestamp(s["ts"]).tz_localize(None)
        k = s[market]
        r = {"timestamp": t}
        for a in TOP:
            r[a] = k[a]["순매수"]
        sd = k["기관"].get("세부", {})
        for sub in SUBS:
            r[sub] = sd.get(sub, {}).get("순매수", 0)
        rows.append(r)
    df = pd.DataFrame(rows).set_index("timestamp").sort_index()
    return df.resample("1min").last().ffill()


def classify(
    cum: pd.Series,
    pace_span: int = 9,
    base_span: int = 30,
    dead_frac: float = 0.4,
    floor: float = 1.0,
    confirm: int = 3,
    stop_n: int = 3,
    chop_win: int = 7,
    chop_n: int = 4,
    hold: int = 3,
) -> pd.DataFrame:
    """누적순매수 시계열 → 매분 상태. 반환: state / pace / dir 컬럼 DataFrame.

    확정 방향 E를 '끈적하게(sticky)' 유지한다. 일단 지속매수가 확정되면
    1~2분짜리 반대 틱으로는 라벨이 흔들리지 않고, 다음 중 하나일 때만 바뀐다:
      · 반대 방향이 confirm분 연속 확정 → 매도전환/매수전환
      · 데드밴드 안 머무름이 stop_n분 지속      → 매수둔화/매도둔화
      · 최근 chop_win분에 부호변경 chop_n회↑ & 미확정 → 혼조
    이 sticky 처리가 없으면 라벨이 매분 깜빡여 알림이 폭주한다(금융투자 하루 41회→한자릿수).
    """
    flow = cum.diff()                                  # 분당 실제 순매수(억), 부호 有
    pace = flow.ewm(span=pace_span).mean()             # 현재 매매 속도(평활)
    typ = flow.abs().ewm(span=base_span).mean()        # 최근 전형적 매매강도
    eps = (dead_frac * typ).clip(lower=floor)          # 적응형 데드밴드

    d = pd.Series(0, index=cum.index, dtype=int)       # instant 방향 -1/0/+1
    d[pace > eps] = 1
    d[pace < -eps] = -1

    sign = np.sign(flow.fillna(0))
    flips = sign.diff().abs().gt(0).rolling(chop_win).sum()

    raw, official = [], []
    E, run_dir, run_len = 0, 0, 0
    cur_off, cand, cand_len = "중립", None, 0
    for di, fl in zip(d, flips):
        if di == run_dir:
            run_len += 1
        else:
            run_dir, run_len = di, 1
        confirmed = run_dir != 0 and run_len >= confirm
        newly = confirmed and run_dir != E
        if newly:
            E = run_dir
        stopped = run_dir == 0 and run_len >= stop_n
        choppy = (fl is not None and fl >= chop_n) and run_len < confirm

        if newly:
            lab = "매수전환" if E == 1 else "매도전환"
        elif E == 1:
            lab = "매수둔화" if stopped else ("혼조" if choppy else "지속매수")
        elif E == -1:
            lab = "매도둔화" if stopped else ("혼조" if choppy else "지속매도")
        else:
            lab = "혼조" if choppy else "중립"
        raw.append(lab)

        # 출력 디바운스: 전환은 지속으로 흡수 후, 새 라벨이 hold분 지속돼야 공식 채택
        reg = {"매수전환": "지속매수", "매도전환": "지속매도"}.get(lab, lab)
        if reg == cur_off:
            cand, cand_len = None, 0
        elif reg == cand:
            cand_len += 1
            if cand_len >= hold:
                cur_off, cand, cand_len = reg, None, 0
        else:
            cand, cand_len = reg, 1
        official.append(cur_off)

    return pd.DataFrame({"state": official, "raw": raw, "pace": pace.round(1), "dir": d},
                        index=cum.index)


def classify_day(date: str, market: str = "kospi", actors=ACTORS, data_dir: Path = DEFAULT_DATA_DIR, **kw):
    """하루치 → {주체: 상태DataFrame}. 정규장(09:00~15:30)만."""
    cum = load_day(date, market, data_dir).between_time("09:00", "15:30")
    return {a: classify(cum[a], **kw) for a in actors if a in cum.columns}


def latest_board(date: str, market: str = "kospi", data_dir: Path = DEFAULT_DATA_DIR, **kw) -> pd.DataFrame:
    """가장 최근 분의 주체별 현재상태 보드 (대시보드/매분 체크용)."""
    res = classify_day(date, market, data_dir=data_dir, **kw)
    rows = {}
    for a, df in res.items():
        last = df.iloc[-1]
        rows[a] = {"상태": last["state"], "속도(억/분)": last["pace"], "누적(억)": int(load_day(date, market, data_dir)[a].iloc[-1])}
    return pd.DataFrame(rows).T


# 8라벨 아이콘: 지속=차트(📈📉), 전환=원(🔴🔵), 둔화=다이아(🔸🔹), 혼조🟡 중립⚪
_ARROW = {"지속매수": "📈", "매수전환": "🔴", "매수둔화": "🔸", "혼조": "🟡",
          "중립": "⚪", "매도둔화": "🔹", "매도전환": "🔵", "지속매도": "📉"}


def main():
    import argparse
    p = argparse.ArgumentParser(description="투자주체 매분 추세 상태")
    p.add_argument("date", nargs="?", help="YYYY-MM-DD (생략 시 data 디렉토리 최신일)")
    p.add_argument("--market", default="kospi", choices=["kospi", "kosdaq"])
    p.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    p.add_argument("--transitions", action="store_true", help="전환 이벤트 로그만 출력")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    date = args.date or sorted(f.stem for f in data_dir.glob("????-??-??.json"))[-1]

    res = classify_day(date, args.market, data_dir=data_dir)
    print(f"[{date} {args.market.upper()}] 투자주체 추세 상태\n")

    if args.transitions:
        for a, df in res.items():
            ev = df[df["state"].isin(["매수전환", "매도전환"])]
            if len(ev):
                print(f"── {a}")
                for t, r in ev.iterrows():
                    print(f"   {t.strftime('%H:%M')}  {r['state']}  (속도 {r['pace']:+.0f}억/분)")
        return

    board = latest_board(date, args.market, data_dir=data_dir)
    t_last = res["외국인"].index[-1].strftime("%H:%M")
    print(f"현재시각 {t_last} 기준 — 현재 상태 보드")
    print(f"{'주체':10}{'상태':8}{'':3}{'속도(억/분)':>12}{'누적(억)':>12}")
    for a in ACTORS:
        if a not in board.index:
            continue
        r = board.loc[a]
        print(f"{a:10}{r['상태']:8}{_ARROW.get(r['상태'],''):3}{r['속도(억/분)']:>12}{r['누적(억)']:>12}")


if __name__ == "__main__":
    main()
