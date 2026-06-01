import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import storage


def test_today_str_format():
    s = storage.today_str()
    assert len(s) == 10 and s[4] == "-" and s[7] == "-"


def test_now_iso_has_kst_offset():
    s = storage.now_iso()
    assert s.endswith("+09:00")


def test_load_or_init_creates_skeleton_when_missing(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = storage.load_or_init(path, "2026-05-27")
    assert data["date"] == "2026-05-27"
    assert data["unit"] == "억원"
    assert data["snapshots"] == []
    assert "kospi" in data["source"] and "kosdaq" in data["source"]


def test_append_snapshot_grows_list_and_updates_timestamp(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = storage.load_or_init(path, "2026-05-27")
    kospi = {"외국인": {"매도": 1, "매수": 2, "순매수": 1}}
    kosdaq = {"외국인": {"매도": 3, "매수": 4, "순매수": 1}}
    data = storage.append_snapshot(data, "2026-05-27T09:00:12+09:00", kospi, kosdaq)
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["ts"] == "2026-05-27T09:00:12+09:00"
    assert data["updated_at"] == "2026-05-27T09:00:12+09:00"


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = storage.load_or_init(path, "2026-05-27")
    data = storage.append_snapshot(data, "2026-05-27T09:00:12+09:00", {}, {})
    storage.save(path, data)

    reloaded = storage.load_or_init(path, "2026-05-27")
    assert reloaded["updated_at"] == "2026-05-27T09:00:12+09:00"
    assert len(reloaded["snapshots"]) == 1


def test_save_writes_utf8_with_unicode_keys(tmp_path):
    path = tmp_path / "2026-05-27.json"
    data = {"date": "2026-05-27", "snapshots": [{"외국인": 1}]}
    storage.save(path, data)
    raw = path.read_text(encoding="utf-8")
    assert "외국인" in raw


def test_minute_relpath_uses_day_folder_and_hh_mm():
    rel = storage.minute_relpath("2026-06-01", "2026-06-01T10:47:00+09:00")
    assert rel == "data/2026-06-01/10-47.json"


def test_save_minute_writes_single_snapshot(tmp_path):
    kospi = {"외국인": {"매도": 1, "매수": 2, "순매수": 1}}
    kosdaq = {"외국인": {"매도": 3, "매수": 4, "순매수": 1}}
    path = tmp_path / "2026-06-01" / "10-47.json"
    storage.save_minute(path, "2026-06-01T10:47:00+09:00", kospi, kosdaq)

    snap = json.loads(path.read_text(encoding="utf-8"))
    assert snap["ts"] == "2026-06-01T10:47:00+09:00"
    assert snap["kospi"]["외국인"]["순매수"] == 1
    assert snap["kosdaq"]["외국인"]["매수"] == 4
