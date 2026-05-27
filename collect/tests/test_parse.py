import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import parse

FIXTURES = Path(__file__).resolve().parent / "fixtures"

def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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
