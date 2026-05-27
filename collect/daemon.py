"""KB 투자자별 매매동향 상시 수집 데몬.

콘솔 창 하나 열어 두면 24/7 동작. 매 분 정각에 거래시간 체크 후
collect.collect_once()를 호출. 종료는 Ctrl+C.

거래시간: 평일 08:50 – 15:40 KST (한국 정규장 + 동시호가 여유)
"""
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import collect

KST = ZoneInfo("Asia/Seoul")

TRADING_START_MIN = 8 * 60 + 50   # 08:50
TRADING_END_MIN   = 15 * 60 + 40  # 15:40


def _is_trading_window(now: datetime) -> bool:
    if now.weekday() > 4:
        return False
    cur = now.hour * 60 + now.minute
    return TRADING_START_MIN <= cur <= TRADING_END_MIN


def _sleep_to_next_minute() -> None:
    now = datetime.now(KST)
    secs = 60 - now.second - now.microsecond / 1_000_000
    if secs > 0:
        time.sleep(secs)


def main() -> None:
    print("=" * 60)
    print(f"KB-InvestorFlow daemon started at {datetime.now(KST):%Y-%m-%d %H:%M:%S} KST")
    print(f"Trading window: weekdays 08:50 - 15:40 KST")
    print("Press Ctrl+C to stop.")
    print("=" * 60, flush=True)

    while True:
        try:
            _sleep_to_next_minute()
            now = datetime.now(KST)
            ts = now.strftime("%H:%M:%S")

            if _is_trading_window(now):
                try:
                    collect.collect_once()
                except Exception as e:
                    print(f"[{ts}] ERROR: {e}", flush=True)
            elif now.minute == 0:
                print(f"[{ts}] idle (outside trading window)", flush=True)
        except KeyboardInterrupt:
            print(f"\n[{datetime.now(KST):%H:%M:%S}] stopped by user", flush=True)
            return
        except Exception:
            print(f"[{datetime.now(KST):%H:%M:%S}] UNEXPECTED:", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
