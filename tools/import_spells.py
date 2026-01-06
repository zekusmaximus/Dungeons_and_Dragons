"""
Import SRD spells from an external JSON file and normalize into data/spells/spells.json.

Expected input shape (compatible with open5e / 5etools exports):
- Each entry must include at least: "name", "level_int" or "level" (int), "school", "range",
  "casting_time", "duration", "components" (string or list), and "desc" / "description".

Usage:
  python tools/import_spells.py --input path/to/srd_spells.json --output data/spells/spells.json
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _load_raw(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        if "results" in data:
            return data["results"]
        if "spell" in data:
            return data["spell"]
        return list(data.values())
    if not isinstance(data, list):
        raise ValueError("Unsupported input shape; expected list or dict with 'results'")
    return data


def _normalize_components(raw) -> List[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x]
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
        # Keep only uppercase component tags (V,S,M) where possible
        return [p.upper() for p in parts if len(p) <= 3]
    return []


def _normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    level = entry.get("level_int") or entry.get("level") or 0
    school = entry.get("school") or entry.get("school_short") or entry.get("school_name") or ""
    description = entry.get("description") or entry.get("desc") or entry.get("higher_level") or ""
    casting_time = entry.get("casting_time") or entry.get("time") or ""
    duration = entry.get("duration") or entry.get("duration_raw") or ""
    components = _normalize_components(entry.get("components") or entry.get("components_raw") or "")
    range_ = entry.get("range") or entry.get("range_raw") or ""
    return {
        "name": entry.get("name", "").strip(),
        "level": int(level),
        "school": school,
        "range": range_,
        "casting_time": casting_time,
        "duration": duration,
        "components": components,
        "description": description if isinstance(description, str) else " ".join(description),
    }


def main():
    parser = argparse.ArgumentParser(description="Normalize SRD spells into data/spells/spells.json")
    parser.add_argument("--input", required=True, help="Path to SRD spells source JSON")
    parser.add_argument("--output", default="data/spells/spells.json", help="Destination path")
    args = parser.parse_args()

    raw_entries = _load_raw(Path(args.input))
    normalized = []
    for entry in raw_entries:
        try:
            norm = _normalize_entry(entry)
        except Exception as exc:
            print(f"Skipping {entry.get('name')}: {exc}")
            continue
        if not norm["name"]:
            continue
        normalized.append(norm)

    normalized.sort(key=lambda x: (x["level"], x["name"]))
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    print(f"Wrote {len(normalized)} spells to {out_path}")


if __name__ == "__main__":
    main()
