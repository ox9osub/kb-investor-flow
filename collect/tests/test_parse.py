import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import parse

FIXTURES = Path(__file__).resolve().parent / "fixtures"

def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_index_json_extracts_both_markets():
    result = parse.parse_index_json(_read("index_sample.json"))
    assert result["kospi"] == {"지수": 7875.44, "전일대비": -221.49, "등락률": -2.74}
    assert result["kosdaq"] == {"지수": 975.24, "전일대비": 7.43, "등락률": 0.77}


def test_kospi_has_four_top_level_categories():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    assert set(result.keys()) == {"외국인", "개인", "기관", "기타법인"}


def test_kospi_외국인_has_three_values():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    foreigner = result["외국인"]
    assert set(foreigner.keys()) == {"매도", "매수", "순매수"}
    assert all(isinstance(v, int) for v in foreigner.values())


def test_kospi_기관_has_eight_subcategories():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    expected_subs = {
        "금융투자", "투신", "보험", "사모펀드",
        "은행", "기타금융", "연기금등", "국가/지자체",
    }
    assert set(result["기관"]["세부"].keys()) == expected_subs


def test_kospi_기관_세부_금융투자_has_values():
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    finance = result["기관"]["세부"]["금융투자"]
    assert set(finance.keys()) == {"매도", "매수", "순매수"}
    assert isinstance(finance["순매수"], int)


def test_kospi_기관_top_has_aggregate_and_세부_keys():
    """기관 dict는 합계(매도/매수/순매수) + 세부 트리를 함께 가짐."""
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    inst = result["기관"]
    assert "매도" in inst and "매수" in inst and "순매수" in inst
    assert "세부" in inst


def test_kospi_negative_values_parsed_correctly():
    """음수 텍스트(-778 등)가 음수 int로 파싱되어야 함."""
    html = _read("kospi_sample.html")
    result = parse.parse_market_html(html)
    foreigner_net = result["외국인"]["순매수"]
    assert isinstance(foreigner_net, int)
    for cat_data in result.values():
        for key in ("매도", "매수", "순매수"):
            assert isinstance(cat_data[key], int)


def test_kosdaq_parses_with_same_structure():
    """KOSDAQ도 동일한 키 구조로 파싱."""
    html = _read("kosdaq_sample.html")
    result = parse.parse_market_html(html)
    assert set(result.keys()) == {"외국인", "개인", "기관", "기타법인"}
    assert len(result["기관"]["세부"]) == 8
