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
