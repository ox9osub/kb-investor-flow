# collect/tests/test_notify_v2.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notify


def test_classify_last_delegates_to_full():
    cum = [0, 10, 25, 45, 70, 100, 135]  # 단조 강한 매수
    label, pace = notify.classify_last(cum)
    full = notify.classify_full(cum)
    assert full["official"] == label
    assert full["pace"] == pace
    assert set(full.keys()) == {"official", "pace", "e_dir"}


def test_classify_full_e_dir_positive_on_sustained_buying():
    cum = [0, 10, 25, 45, 70, 100, 135, 175]
    assert notify.classify_full(cum)["e_dir"] == 1


def test_classify_full_neutral_on_flat():
    cum = [0, 0, 0, 0, 0, 0]
    full = notify.classify_full(cum)
    assert full["e_dir"] == 0
    assert full["official"] in {"중립", "혼조"}
