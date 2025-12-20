#!/usr/bin/env python3
"""
Narrative generation tool that uses LLM to enhance scene descriptions
while preserving deterministic game mechanics.
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Add service directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "service"))

from llm_narrative import LLMNarrativeEnhancer, get_narrative_enhancer


def load_scene_context(slug: str, scene_type: str) -> dict:
    """Load context from session for narrative generation"""
    context = {
        "scene_type": scene_type,
        "session_slug": slug,
    }
    
    # Load character data
    character_path = Path(f"data/characters/{slug}.json")
    if character_path.exists():
        with character_path.open() as f:
            context["character"] = json.load(f)
    
    # Load state data
    state_path = Path(f"sessions/{slug}/state.json")
    if state_path.exists():
        with state_path.open() as f:
            context["state"] = json.load(f)
    
    return context


async def generate_scene_narrative(
    slug: str,
    scene_type: str,
    tone: str = "neutral",
    prompt: str = "",
    use_llm: bool = True
) -> dict:
    """Generate narrative for a scene"""
    enhancer = get_narrative_enhancer()
    context = load_scene_context(slug, scene_type)
    
    result = {
        "slug": slug,
        "scene_type": scene_type,
        "tone": tone,
        "use_llm": use_llm,
        "context_used": context,
    }
    
    if use_llm and enhancer.settings.has_llm_config:
        try:
            if prompt:
                # Use custom prompt
                narrative = await enhancer.enhance_scene_description(
                    prompt,
                    scene_type,
                    tone,
                    context
                )
            else:
                # Generate based on scene type
                base_desc = f"A {scene_type} scene unfolds with {tone} tone"
                narrative = await enhancer.enhance_scene_description(
                    base_desc,
                    scene_type,
                    tone,
                    context
                )
            
            result["narrative"] = narrative
            result["source"] = "llm"
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            result["source"] = "error"
            result["success"] = False
    else:
        # Fallback to deterministic narrative
        from narrative.scene_framing_engine import frame_scene
        framed = frame_scene(scene_type, tone, seed=42, use_llm_enhancement=False)
        result["narrative"] = framed.get("description", "A scene unfolds.")
        result["source"] = "deterministic"
        result["success"] = True
    
    return result


async def generate_npc_dialogue(
    slug: str,
    npc_name: str,
    npc_role: str,
    situation: str
) -> dict:
    """Generate dialogue for an NPC"""
    enhancer = get_narrative_enhancer()
    context = load_scene_context(slug, "dialogue")
    
    result = {
        "slug": slug,
        "npc_name": npc_name,
        "npc_role": npc_role,
        "situation": situation,
    }
    
    if enhancer.settings.has_llm_config:
        try:
            dialogue = await enhancer.generate_npc_dialogue(
                npc_name,
                npc_role,
                situation,
                context.get("character", {})
            )
            result["dialogue"] = dialogue
            result["source"] = "llm"
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            result["source"] = "error"
            result["success"] = False
    else:
        result["dialogue"] = f"{npc_name} speaks in a generic manner about {situation}."
        result["source"] = "deterministic"
        result["success"] = True
    
    return result


async def generate_creature_description(
    slug: str,
    creature_path: str,
    encounter_context: str
) -> dict:
    """Generate vivid description for a creature"""
    enhancer = get_narrative_enhancer()
    
    # Load creature data
    creature_full_path = Path(creature_path)
    if not creature_full_path.exists():
        return {
            "error": f"Creature file not found: {creature_path}",
            "success": False
        }
    
    with creature_full_path.open() as f:
        creature_data = json.load(f)
    
    result = {
        "slug": slug,
        "creature": creature_data.get("name", "unknown"),
        "encounter_context": encounter_context,
    }
    
    if enhancer.settings.has_llm_config:
        try:
            description = await enhancer.generate_creature_description(
                creature_data,
                encounter_context
            )
            result["description"] = description
            result["source"] = "llm"
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            result["source"] = "error"
            result["success"] = False
    else:
        result["description"] = creature_data.get("description", "A creature appears.")
        result["source"] = "deterministic"
        result["success"] = True
    
    return result


async def main():
    parser = argparse.ArgumentParser(description="LLM Narrative Generation Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Scene narrative command
    scene_parser = subparsers.add_parser("scene", help="Generate scene narrative")
    scene_parser.add_argument("--slug", required=True, help="Session slug")
    scene_parser.add_argument("--scene-type", required=True, help="Type of scene")
    scene_parser.add_argument("--tone", default="neutral", help="Tone of scene")
    scene_parser.add_argument("--prompt", help="Custom prompt for narrative")
    scene_parser.add_argument("--no-llm", action="store_true", help="Disable LLM enhancement")
    
    # NPC dialogue command
    npc_parser = subparsers.add_parser("npc", help="Generate NPC dialogue")
    npc_parser.add_argument("--slug", required=True, help="Session slug")
    npc_parser.add_argument("--npc-name", required=True, help="NPC name")
    npc_parser.add_argument("--npc-role", required=True, help="NPC role")
    npc_parser.add_argument("--situation", required=True, help="Situation description")
    
    # Creature description command
    creature_parser = subparsers.add_parser("creature", help="Generate creature description")
    creature_parser.add_argument("--slug", required=True, help="Session slug")
    creature_parser.add_argument("--creature-path", required=True, help="Path to creature JSON file")
    creature_parser.add_argument("--context", required=True, help="Encounter context")
    
    args = parser.parse_args()
    
    if args.command == "scene":
        result = await generate_scene_narrative(
            args.slug,
            args.scene_type,
            args.tone,
            args.prompt or "",
            not args.no_llm
        )
    elif args.command == "npc":
        result = await generate_npc_dialogue(
            args.slug,
            args.npc_name,
            args.npc_role,
            args.situation
        )
    elif args.command == "creature":
        result = await generate_creature_description(
            args.slug,
            args.creature_path,
            args.context
        )
    else:
        print("Unknown command")
        return
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())