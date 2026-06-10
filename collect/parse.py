"""KB 투자자별 매매동향 HTML 파서.

KB증권 모바일 페이지의 단일 시장(KOSPI 또는 KOSDAQ) HTML을 받아
{외국인, 개인, 기관, 기타법인} 4개 최상위 카테고리 dict로 변환.
기관은 8개 세부 카테고리를 `세부` 키 아래 중첩.
"""
import json

from bs4 import BeautifulSoup

_INSTITUTION_PARENT_IN  = "기관계"
_INSTITUTION_PARENT_OUT = "기관"


def parse_market_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tbody tr")
    result: dict = {}
    current_parent_key: str | None = None

    for tr in rows:
        cells = tr.find_all("td")
        if len(cells) != 4:
            continue

        name = cells[0].get_text(strip=True)
        values = _row_values(cells[1:])

        if name.startswith("- "):
            child = name[2:].strip()
            if current_parent_key:
                result[current_parent_key].setdefault("세부", {})[child] = values
            continue

        if name == _INSTITUTION_PARENT_IN:
            current_parent_key = _INSTITUTION_PARENT_OUT
            result[current_parent_key] = {**values, "세부": {}}
        else:
            result[name] = values
            current_parent_key = None

    return result


def _row_values(cells) -> dict:
    sell, buy, net = (_to_int(c.get_text(strip=True)) for c in cells)
    return {"매도": sell, "매수": buy, "순매수": net}


def _to_int(text: str) -> int:
    return int(text.replace(",", "").strip())


def parse_index_json(text: str) -> dict:
    """네이버 금융 지수 폴링 JSON → {"kospi": {...}, "kosdaq": {...}}.

    각 시장: {지수, 전일대비, 등락률}. 장 마감/휴장이어도 직전 종가가 내려온다.
    """
    payload = json.loads(text)
    out: dict = {}
    for item in payload.get("datas", []):
        code = item.get("itemCode")
        key = {"KOSPI": "kospi", "KOSDAQ": "kosdaq"}.get(code)
        if not key:
            continue
        out[key] = {
            "지수": _to_float(item.get("closePriceRaw")),
            "전일대비": _to_float(item.get("compareToPreviousClosePriceRaw")),
            "등락률": _to_float(item.get("fluctuationsRatioRaw")),
        }
    return out


def _to_float(text) -> float | None:
    if text is None:
        return None
    return float(str(text).replace(",", "").strip())
