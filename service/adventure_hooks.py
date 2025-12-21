"""
Adventure Hooks System - Generates starting adventure hooks for solo players
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Optional

from .llm_narrative import LLMNarrativeEnhancer, get_narrative_enhancer


class AdventureHook:
    """Represents an adventure hook for starting a solo D&D session"""
    
    def __init__(self, hook_id: str, title: str, description: str, hook_type: str, 
                 location: str, difficulty: str, rewards: List[str], 
                 starting_scene: str, quest_template: Optional[str] = None):
        self.hook_id = hook_id
        self.title = title
        self.description = description
        self.hook_type = hook_type
        self.location = location
        self.difficulty = difficulty
        self.rewards = rewards
        self.starting_scene = starting_scene
        self.quest_template = quest_template
    
    def to_dict(self) -> Dict:
        return {
            'hook_id': self.hook_id,
            'title': self.title,
            'description': self.description,
            'hook_type': self.hook_type,
            'location': self.location,
            'difficulty': self.difficulty,
            'rewards': self.rewards,
            'starting_scene': self.starting_scene,
            'quest_template': self.quest_template
        }


class AdventureHooksService:
    """Service for generating and managing adventure hooks"""
    
    def __init__(self):
        self.hooks_data_path = Path(__file__).resolve().parent.parent / "data" / "adventure_hooks.json"
        self.quests_path = Path(__file__).resolve().parent.parent / "quests" / "templates"
        
    def get_available_hooks(self) -> List[AdventureHook]:
        """Get all available adventure hooks"""
        hooks = []
        
        # Load from file if exists
        if self.hooks_data_path.exists():
            with self.hooks_data_path.open() as f:
                hooks_data = json.load(f)
                for hook_data in hooks_data:
                    hooks.append(AdventureHook(**hook_data))
        
        # Add some default hooks if file doesn't exist or is empty
        if not hooks:
            hooks = self._generate_default_hooks()
            self._save_hooks(hooks)
        
        return hooks
    
    def get_hook_by_id(self, hook_id: str) -> Optional[AdventureHook]:
        """Get a specific adventure hook by ID"""
        hooks = self.get_available_hooks()
        for hook in hooks:
            if hook.hook_id == hook_id:
                return hook
        return None
    
    def get_recommended_hooks(self, character_class: Optional[str] = None, 
                             character_level: int = 1) -> List[AdventureHook]:
        """Get hooks recommended for a specific character"""
        all_hooks = self.get_available_hooks()
        
        # Filter by appropriate difficulty
        recommended = [
            hook for hook in all_hooks 
            if hook.difficulty in ['easy', 'medium'] or character_level >= 3
        ]
        
        # If character class is provided, try to match hook types
        if character_class:
            class_preferences = self._get_class_preferences(character_class)
            recommended = sorted(
                recommended, 
                key=lambda hook: class_preferences.get(hook.hook_type, 0), 
                reverse=True
            )
        
        return recommended[:5]  # Return top 5 recommendations
    
    async def generate_llm_enhanced_hook(self, character_context: Dict) -> AdventureHook:
        """Generate a custom adventure hook using LLM based on character context"""
        enhancer = get_narrative_enhancer()
        
        if not enhancer.settings.has_llm_config:
            # Fallback to random hook if LLM not available
            hooks = self.get_available_hooks()
            return random.choice(hooks)
        
        # Generate hook using LLM
        character_name = character_context.get('name', 'Adventurer')
        character_class = character_context.get('class', 'Hero')
        character_level = character_context.get('level', 1)
        
        prompt = f"""Generate a compelling D&D adventure hook for a solo player:

Character: {character_name}, Level {character_level} {character_class}

Create an adventure hook that includes:
1. A catchy title
2. Brief description (2-3 sentences)
3. Hook type (quest, exploration, combat, mystery, social)
4. Starting location
5. Difficulty level (easy, medium, hard, epic)
6. Potential rewards
7. Starting scene description

Make it engaging and tailored to the character's class and level."""
        
        try:
            hook_text = await enhancer.enhance_scene_description(
                "Generate a D&D adventure hook",
                "adventure_hook",
                "engaging",
                character_context
            )
            
            # Parse the LLM response (this would be more sophisticated in production)
            return self._parse_llm_hook_response(hook_text, character_context)
            
        except Exception:
            # Fallback to random hook if LLM fails
            hooks = self.get_available_hooks()
            return random.choice(hooks)
    
    def _parse_llm_hook_response(self, hook_text: str, character_context: Dict) -> AdventureHook:
        """Parse LLM-generated hook text into structured data"""
        # This is a simplified parser - in production you'd use proper parsing
        lines = hook_text.split('\n')
        
        title = lines[0].replace('Title:', '').strip() if lines else 'Mysterious Adventure'
        description = '\n'.join([line for line in lines if 'Description:' in line or 
                                 (not any(x in line for x in ['Title:', 'Type:', 'Location:', 
                                                               'Difficulty:', 'Rewards:', 'Scene:']))])
        
        hook_type = 'quest'
        location = 'Nearby Town'
        difficulty = 'medium'
        rewards = ['Gold', 'Experience', 'Local Renown']
        starting_scene = '\n'.join([line for line in lines if 'Scene:' in line or 
                                    line.startswith('You find yourself')])
        
        if not starting_scene:
            starting_scene = f"You find yourself in {location}, ready to begin your adventure."
        
        character_name = character_context.get('name', 'Adventurer')
        hook_id = f"generated-{character_name.lower()}-{random.randint(1000, 9999)}"
        
        return AdventureHook(
            hook_id=hook_id,
            title=title,
            description=description,
            hook_type=hook_type,
            location=location,
            difficulty=difficulty,
            rewards=rewards,
            starting_scene=starting_scene
        )
    
    def _generate_default_hooks(self) -> List[AdventureHook]:
        """Generate default adventure hooks"""
        return [
            AdventureHook(
                hook_id="hook-001",
                title="The Missing Caravan",
                description="A merchant caravan has gone missing on the road to Silverpeak. The local guild is offering a reward for information or rescue.",
                hook_type="quest",
                location="Silverpeak Road",
                difficulty="easy",
                rewards=["100 gold", "Merchant favor", "Experience"],
                starting_scene="You stand at the town gates of Briarwood, where a worried merchant approaches you with a plea for help."
            ),
            AdventureHook(
                hook_id="hook-002",
                title="The Haunted Mill",
                description="Strange lights and eerie sounds come from the old mill at night. The townsfolk are too afraid to investigate.",
                hook_type="mystery",
                location="Briarwood",
                difficulty="medium",
                rewards=["Magic item", "Local hero status", "Experience"],
                starting_scene="As night falls over Briarwood, you notice the townsfolk avoiding the old mill on the hill, their faces pale with fear."
            ),
            AdventureHook(
                hook_id="hook-003",
                title="Goblin Trouble",
                description="Goblins have been raiding farms on the outskirts. The mayor needs someone to put an end to their mischief.",
                hook_type="combat",
                location="Farmlands near Briarwood",
                difficulty="easy",
                rewards=["50 gold", "Farmers' gratitude", "Experience"],
                starting_scene="The mayor's office is bustling with angry farmers demanding action against the goblin raids."
            ),
            AdventureHook(
                hook_id="hook-004",
                title="The Lost Heirloom",
                description="A noble family's precious heirloom has been stolen. They suspect a rival house but need proof.",
                hook_type="social",
                location="Briarwood Manor",
                difficulty="medium",
                rewards=["Noble favor", "200 gold", "Experience"],
                starting_scene="You are summoned to the grand manor of House Briarwood, where Lady Elara explains the delicate situation."
            ),
            AdventureHook(
                hook_id="hook-005",
                title="The Cursed Forest",
                description="The Whispering Woods are said to contain ancient elven ruins with powerful magic, but none who enter return unchanged.",
                hook_type="exploration",
                location="Whispering Woods",
                difficulty="hard",
                rewards=["Powerful artifact", "Ancient knowledge", "Experience"],
                starting_scene="At the edge of the forest, the trees seem to whisper your name as the wind rustles through their leaves."
            )
        ]
    
    def _get_class_preferences(self, character_class: str) -> Dict[str, int]:
        """Get hook type preferences for different character classes"""
        preferences = {
            'fighter': {'combat': 3, 'quest': 2, 'exploration': 1, 'mystery': 1, 'social': 0},
            'rogue': {'quest': 2, 'social': 2, 'exploration': 2, 'combat': 1, 'mystery': 1},
            'wizard': {'mystery': 3, 'exploration': 2, 'quest': 1, 'social': 1, 'combat': 1},
            'cleric': {'quest': 2, 'social': 2, 'mystery': 2, 'combat': 1, 'exploration': 1},
            'ranger': {'exploration': 3, 'combat': 2, 'quest': 2, 'mystery': 1, 'social': 0},
            'paladin': {'quest': 3, 'combat': 2, 'social': 2, 'mystery': 1, 'exploration': 1},
            'bard': {'social': 3, 'quest': 2, 'mystery': 2, 'exploration': 1, 'combat': 1},
            'barbarian': {'combat': 3, 'exploration': 2, 'quest': 1, 'mystery': 0, 'social': 0},
            'monk': {'quest': 2, 'combat': 2, 'exploration': 2, 'mystery': 1, 'social': 1},
            'druid': {'exploration': 3, 'mystery': 2, 'quest': 2, 'social': 1, 'combat': 1}
        }
        
        return preferences.get(character_class.lower(), 
                              {'quest': 1, 'combat': 1, 'exploration': 1, 'mystery': 1, 'social': 1})
    
    def _save_hooks(self, hooks: List[AdventureHook]):
        """Save hooks to file"""
        hooks_data = [hook.to_dict() for hook in hooks]
        
        with self.hooks_data_path.open('w') as f:
            json.dump(hooks_data, f, indent=2)


def get_adventure_hooks_service() -> AdventureHooksService:
    """Get the adventure hooks service instance"""
    return AdventureHooksService()