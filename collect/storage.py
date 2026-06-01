"""일별 JSON 파일 I/O + KST 시간 유틸."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_KOSPI_URL  = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0"
_KOSDAQ_URL = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=1"


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def load_or_init(path: Path, date: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "date": date,
        "unit": "억원",
        "source": {"kospi": _KOSPI_URL, "kosdaq": _KOSDAQ_URL},
        "updated_at": None,
        "snapshots": [],
    }


def append_snapshot(data: dict, ts: str, kospi: dict, kosdaq: dict) -> dict:
    data["snapshots"].append({"ts": ts, "kospi": kospi, "kosdaq": kosdaq})
    data["updated_at"] = ts
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def minute_relpath(date: str, ts: str) -> str:
    """분 단위 스냅샷의 data 브랜치 상대경로. 예: data/2026-06-01/10-47.json

    파일명에 시·분을 박아 매 분 URL이 달라지므로 CDN/브라우저 캐시를 우회한다
    (raw·jsdelivr 모두 쿼리스트링 ?t= 를 캐시 키에서 무시하므로 파일명으로 분리).
    """
    hh_mm = ts[11:16].replace(":", "-")  # "10:47" -> "10-47"
    return f"data/{date}/{hh_mm}.json"


def save_minute(path: Path, ts: str, kospi: dict, kosdaq: dict) -> None:
    """해당 분의 단일 스냅샷만 기록 (누적 아님)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    snap = {"ts": ts, "kospi": kospi, "kosdaq": kosdaq}
    path.write_text(
        json.dumps(snap, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
