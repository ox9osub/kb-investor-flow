"""KB 투자자별 매매동향 1분 수집 사이클 진입점.

Task Scheduler가 매분 호출하는 CLI. --dry-run, --no-push 지원.
data worktree는 본 스크립트의 부모 디렉토리 sibling인
'kb-investor-flow-data\\' 라고 가정.
"""
import argparse
import json
import sys
from pathlib import Path

import fetch
import git_sync
import parse
import storage

_THIS_DIR = Path(__file__).resolve().parent
_MAIN_REPO_ROOT = _THIS_DIR.parent
_DATA_REPO_ROOT = _MAIN_REPO_ROOT.parent / "kb-investor-flow-data"


def collect_once(dry_run: bool = False, skip_push: bool = False) -> None:
    kospi_html  = fetch.fetch_market_html(fetch.KOSPI_URL)
    kosdaq_html = fetch.fetch_market_html(fetch.KOSDAQ_URL)
    kospi  = parse.parse_market_html(kospi_html)
    kosdaq = parse.parse_market_html(kosdaq_html)

    date = storage.today_str()
    ts   = storage.now_iso()

    if dry_run:
        print(json.dumps(
            {"ts": ts, "kospi": kospi, "kosdaq": kosdaq},
            ensure_ascii=False, indent=2,
        ))
        return

    # 1) 누적 파일 — 차트 과거 시계열 본체 (CDN 캐시로 최대 5분 낡을 수 있음)
    rel = f"data/{date}.json"
    path = _DATA_REPO_ROOT / rel
    data = storage.load_or_init(path, date)
    data = storage.append_snapshot(data, ts, kospi, kosdaq)
    storage.save(path, data)

    # 2) 분 단위 파일 — 파일명에 시·분을 박아 고유 URL → CDN/브라우저 캐시 우회.
    #    프론트가 누적 파일의 마지막 시점 이후 부족분을 이 파일들로 메워 1분 신선도 확보.
    minute_rel = storage.minute_relpath(date, ts)
    minute_path = _DATA_REPO_ROOT / minute_rel
    storage.save_minute(minute_path, ts, kospi, kosdaq)

    print(f"wrote {path} ({len(data['snapshots'])} snapshots) + {minute_rel}, updated_at={ts}")

    if skip_push:
        return

    git_sync.commit_and_push(
        repo_dir=_DATA_REPO_ROOT,
        relpath=[rel, minute_rel],
        message=f"data: {date} {ts[11:19]} KST",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="KB 투자자별 매매동향 1분 수집기")
    p.add_argument("--dry-run", action="store_true",
                   help="파싱 결과를 stdout에 출력만, 파일/git 손대지 않음")
    p.add_argument("--no-push", action="store_true",
                   help="파일은 저장하되 git commit/push 안 함")
    args = p.parse_args()

    try:
        collect_once(dry_run=args.dry_run, skip_push=args.no_push)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
