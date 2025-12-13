import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_rules_index_and_search(tmp_path):
    subprocess.run(["python", "tools/index_rules.py"], check=True)
    result = subprocess.run(["python", "tools/search_rules.py", "movement"], capture_output=True, text=True, check=True)
    assert "movement.md" in result.stdout
