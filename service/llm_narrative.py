import json
from typing import Dict, Optional, Any

from .config import Settings, get_settings
from .llm import call_llm_api, get_effective_llm_config


class LLMNarrativeEnhancer:
    """Enhances narrative generation using LLM while preserving deterministic mechanics"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
    
    async def enhance_scene_description(
        self,
        base_description: str,
        scene_type: str,
        tone: str,
        context: Optional[Dict] = None
    ) -> str:
        """Enhance a base scene description with LLM-generated details"""
        if not get_effective_llm_config(self.settings).api_key:
            return base_description  # Fallback to original if no LLM config
        
        prompt = f"""Enhance this D&D scene description while preserving the core details:

Base description: {base_description}

Scene type: {scene_type}
Tone: {tone}

Provide a more vivid, immersive version that maintains the same plot points and game state but adds atmospheric details, sensory descriptions, and narrative flair. Keep it concise (2-3 paragraphs max)."""
        
        try:
            enhanced = await self._call_llm_api(prompt, context)
            return enhanced
        except Exception:
            return base_description  # Graceful fallback
    
    async def generate_npc_dialogue(
        self,
        npc_name: str,
        npc_role: str,
        situation: str,
            player_character: Dict
    ) -> str:
        """Generate context-appropriate dialogue for an NPC"""
        if not get_effective_llm_config(self.settings).api_key:
            return f"{npc_name} speaks in a generic manner."  # Fallback
        
        prompt = f"""Generate brief but characterful dialogue for an NPC in a D&D game:

NPC Name: {npc_name}
NPC Role: {npc_role}
Situation: {situation}
Player Character: {player_character.get('name', 'adventurer')}

Provide 2-3 lines of dialogue that fit the NPC's role and the situation. Make it natural and engaging."""
        
        try:
            dialogue = await self._call_llm_api(prompt, {"npc": npc_name, "situation": situation})
            return f"{npc_name}: {dialogue}"
        except Exception:
            return f"{npc_name} speaks in a generic manner."
    
    async def generate_creature_description(
        self,
        creature_data: Dict,
        encounter_context: str
    ) -> str:
        """Generate a vivid description of a creature/monster"""
        if not get_effective_llm_config(self.settings).api_key:
            return creature_data.get("description", "A creature appears.")
        
        prompt = f"""Describe this D&D creature vividly for first-time encounter:

Creature: {creature_data.get('name', 'unknown')}
Type: {creature_data.get('type', 'creature')}
Size: {creature_data.get('size', 'medium')}
Environment: {encounter_context}

Provide a 2-3 sentence atmospheric description highlighting its most striking features and behavior. Make it memorable for players."""
        
        try:
            description = await self._call_llm_api(prompt, {"creature": creature_data})
            return description
        except Exception:
            return creature_data.get("description", "A creature appears.")
    
    async def _call_llm_api(self, prompt: str, context: Optional[Dict] = None) -> str:
        return await call_llm_api(self.settings, prompt, context)

def get_narrative_enhancer() -> LLMNarrativeEnhancer:
    """Get a narrative enhancer instance with current settings"""
    return LLMNarrativeEnhancer(get_settings())
