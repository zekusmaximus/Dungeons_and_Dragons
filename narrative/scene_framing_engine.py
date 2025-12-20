import json
from pathlib import Path
from typing import Dict, Optional
import sys

import random

# Add service directory to path for LLM narrative module
sys.path.append(str(Path(__file__).resolve().parent.parent / "service"))

try:
    from llm_narrative import LLMNarrativeEnhancer, get_narrative_enhancer
    llm_available = True
except ImportError:
    llm_available = False


def load_beats() -> Dict[str, Dict[str, str]]:
    beats_path = Path(__file__).resolve().parent.parent / "exploration" / "beats.json"
    with beats_path.open() as handle:
        return json.load(handle)


def frame_scene(
    scene_type: str,
    tone: str,
    seed: int | None = None,
    use_llm_enhancement: bool = False,
    context: Optional[Dict] = None
) -> Dict[str, str]:
    """Frame a scene with optional LLM enhancement"""
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
    
    # Add LLM enhancement if requested and available
    if use_llm_enhancement and llm_available:
        try:
            enhancer = get_narrative_enhancer()
            if enhancer.settings.has_llm_config:
                # Get the base description from beats
                base_description = beat_pack.get("description", "A scene unfolds.")
                
                # Enhance with LLM
                import asyncio
                enhanced_description = asyncio.run(
                    enhancer.enhance_scene_description(
                        base_description,
                        scene_type,
                        tone,
                        context
                    )
                )
                framed["llm_enhanced_description"] = enhanced_description
                framed["enhancement_source"] = "llm"
            else:
                framed["enhancement_source"] = "none"
        except Exception as e:
            framed["enhancement_error"] = str(e)
            framed["enhancement_source"] = "error"
    else:
        framed["enhancement_source"] = "disabled"
    
    return framed


def generate_llm_narrative(
    prompt: str,
    scene_type: Optional[str] = None,
    tone: Optional[str] = None,
    context: Optional[Dict] = None
) -> Optional[str]:
    """Generate narrative using LLM if available"""
    if not llm_available:
        return None
    
    try:
        enhancer = get_narrative_enhancer()
        if not enhancer.settings.has_llm_config:
            return None
        
        # Use scene enhancement as the base method
        base_desc = scene_type and tone and f"Scene: {scene_type}, Tone: {tone}" or "Generic scene"
        import asyncio
        return asyncio.run(
            enhancer.enhance_scene_description(base_desc, scene_type or "generic", tone or "neutral", context)
        )
    except Exception:
        return None


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
