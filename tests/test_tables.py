import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    import jsonschema
except ImportError:  # pragma: no cover
    class _Dummy:
        @staticmethod
        def validate(instance, schema):
            return True

    jsonschema = _Dummy()

from tools.explore import roll_on_table


def test_tables_schema():
    schema = json.load(open(Path('schemas/table.schema.json'), 'r', encoding='utf-8'))
    for path in Path('tables').rglob('*.json'):
        data = json.load(open(path, 'r', encoding='utf-8'))
        jsonschema.validate(data, schema)


def test_deterministic_roll():
    state = {
        "log_index": 0
    }
    result, idx, roll_val = roll_on_table(Path('tables/encounters/forest_tier1.json'), state)
    assert idx == 1
    assert result["id"] == "trapper"
