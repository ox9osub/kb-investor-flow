"""KB 페이지 HTTP fetch — EUC-KR 디코드 + 1회 재시도."""
import time
import requests

KOSPI_URL  = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0"
KOSDAQ_URL = "https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=1"

# 지수 값(코스피/코스닥)은 KB 매매동향 페이지에 없어 네이버 금융 폴링 API로 별도 수집.
INDEX_URL = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ"

_TIMEOUT_SEC      = 10
_RETRY_DELAY_SEC  = 5
_MAX_RETRIES      = 1


def fetch_market_html(url: str) -> str:
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=_TIMEOUT_SEC)
            r.encoding = "euc-kr"
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SEC)
    raise RuntimeError(f"fetch failed after {_MAX_RETRIES + 1} attempts: {last_err}")


def fetch_index_json(url: str = INDEX_URL) -> str:
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=_TIMEOUT_SEC)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SEC)
    raise RuntimeError(f"index fetch failed after {_MAX_RETRIES + 1} attempts: {last_err}")
