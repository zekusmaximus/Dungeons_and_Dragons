import json
from pathlib import Path
from typing import Dict

import random


def load_beats() -> Dict[str, Dict[str, str]]:
    beats_path = Path(__file__).resolve().parent.parent / "exploration" / "beats.json"
    with beats_path.open() as handle:
        return json.load(handle)


def frame_scene(scene_type: str, tone: str, seed: int | None = None) -> Dict[str, str]:
    beats = load_beats()
    if scene_type not in beats:
        raise ValueError(f"Unknown scene type: {scene_type}")
    rng = random.Random(seed)
    palette = []
    tone_path = Path(__file__).resolve().parent / "tone_dials.json"
    with tone_path.open() as handle:
        tones = json.load(handle)
    for tone_def in tones.get("tones", []):
        if tone_def.get("name") == tone:
            palette = tone_def.get("palette", [])
            break
    beat_pack = beats[scene_type]
    framed = {k: f"{v} | tone: {tone}" for k, v in beat_pack.items()}
    if palette:
        framed["palette_word"] = rng.choice(palette)
    return framed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scene framing helper")
    parser.add_argument("--scene-type", required=True)
    parser.add_argument("--tone", required=True)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    framing = frame_scene(args.scene_type, args.tone, args.seed)
    print(json.dumps(framing, indent=2))


if __name__ == "__main__":
    main()
