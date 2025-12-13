import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.explore import roll_on_table, advance_time


def test_advance_time_modifiers():
    new_time = advance_time("2023-01-01T00:00:00Z", 1.5)
    assert new_time.startswith("2023-01-01T01:30")


def test_rolls_valid_entries():
    state = {"log_index": 0}
    result, idx, roll_val = roll_on_table(Path('tables/weather/temperate.json'), state)
    assert result['condition']
    assert idx == 1
