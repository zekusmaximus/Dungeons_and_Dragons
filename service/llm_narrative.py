import json
from pathlib import Path
from typing import Dict, Optional, Any
import httpx

from .config import Settings, get_settings


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
        if not self.settings.has_llm_config:
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
        if not self.settings.has_llm_config:
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
        if not self.settings.has_llm_config:
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
    
    async def _call_llm_api(
        self,
        prompt: str,
        context: Optional[Dict] = None
    ) -> str:
        """Internal method to call LLM API"""
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json"
        }
        
        # Build messages with context
        messages = [{"role": "system", "content": "You are a helpful D&D narrative assistant."}]
        
        if context:
            context_str = json.dumps(context, indent=2)
            messages.append({
                "role": "system",
                "content": f"Context:\n{context_str}"
            })
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()


def get_narrative_enhancer() -> LLMNarrativeEnhancer:
    """Get a narrative enhancer instance with current settings"""
    return LLMNarrativeEnhancer(get_settings())