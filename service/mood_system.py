"""
Mood and Tone System - Tracks and applies mood/tone effects to narrative generation
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum

from .llm_narrative import LLMNarrativeEnhancer, get_narrative_enhancer


class Mood(Enum):
    """Different mood states that can affect the narrative"""
    NEUTRAL = "neutral"
    JOYFUL = "joyful"
    EXCITED = "excited"
    TENSE = "tense"
    DANGEROUS = "dangerous"
    MYSTERIOUS = "mysterious"
    PEACEFUL = "peaceful"
    SAD = "sad"
    HORRIFIC = "horrific"
    EPIC = "epic"


class ToneModifier:
    """Modifies narrative tone based on current mood"""
    
    def __init__(self, mood: Mood, intensity: float = 1.0):
        self.mood = mood
        self.intensity = intensity  # 0.0 to 2.0
        
    def apply_to_narrative(self, narrative: str) -> str:
        """Apply tone modifications to narrative text"""
        if self.intensity <= 0:
            return narrative
        
        # Simple text modifications based on mood
        modifications = {
            Mood.JOYFUL: {
                'adjectives': ['joyful', 'happy', 'bright', 'cheerful', 'delightful'],
                'verbs': ['laughs', 'smiles', 'rejoices', 'celebrates'],
                'intensifier': 'wonderfully'
            },
            Mood.EXCITED: {
                'adjectives': ['thrilling', 'exciting', 'electrifying', 'pulsating', 'vibrant'],
                'verbs': ['thrills', 'excites', 'energizes', 'invigorates'],
                'intensifier': 'incredibly'
            },
            Mood.TENSE: {
                'adjectives': ['tense', 'nervous', 'anxious', 'apprehensive', 'uneasy'],
                'verbs': ['tenses', 'nervously watches', 'anxiously awaits'],
                'intensifier': 'painfully'
            },
            Mood.DANGEROUS: {
                'adjectives': ['dangerous', 'perilous', 'hazardous', 'treacherous', 'deadly'],
                'verbs': ['threatens', 'endangers', 'jeopardizes'],
                'intensifier': 'extremely'
            },
            Mood.MYSTERIOUS: {
                'adjectives': ['mysterious', 'enigmatic', 'cryptic', 'puzzling', 'arcane'],
                'verbs': ['hides', 'conceals', 'mystifies'],
                'intensifier': 'curiously'
            },
            Mood.PEACEFUL: {
                'adjectives': ['peaceful', 'serene', 'tranquil', 'calm', 'placid'],
                'verbs': ['soothes', 'calms', 'relaxes'],
                'intensifier': 'gently'
            },
            Mood.SAD: {
                'adjectives': ['sad', 'melancholic', 'gloomy', 'depressed', 'mournful'],
                'verbs': ['weeps', 'mourns', 'laments'],
                'intensifier': 'deeply'
            },
            Mood.HORRIFIC: {
                'adjectives': ['horrific', 'terrifying', 'gruesome', 'macabre', 'nightmarish'],
                'verbs': ['horrifies', 'terrifies', 'shocks'],
                'intensifier': 'utterly'
            },
            Mood.EPIC: {
                'adjectives': ['epic', 'heroic', 'legendary', 'monumental', 'grand'],
                'verbs': ['inspires', 'awes', 'astounds'],
                'intensifier': 'truly'
            }
        }
        
        if self.mood in modifications:
            mods = modifications[self.mood]
            
            # Replace some adjectives
            result = narrative
            if 'adjectives' in mods and random.random() < 0.3 * self.intensity:
                adjective = random.choice(mods['adjectives'])
                result = result.replace('scene', f'{adjective} scene')
                result = result.replace('atmosphere', f'{adjective} atmosphere')
            
            # Add intensifier
            if 'intensifier' in mods and random.random() < 0.2 * self.intensity:
                intensifier = mods['intensifier']
                result = result.replace('very', intensifier)
                result = result.replace('really', intensifier)
        
        return result
    
    def get_narrative_guidance(self) -> Dict:
        """Get guidance for generating narrative with this mood"""
        guidance = {
            Mood.NEUTRAL: {
                'description': 'Standard narrative tone',
                'suggestions': ['Describe the scene objectively', 'Use balanced language']
            },
            Mood.JOYFUL: {
                'description': 'Upbeat and positive tone',
                'suggestions': ['Focus on positive aspects', 'Use cheerful language', 'Highlight beauty and happiness']
            },
            Mood.EXCITED: {
                'description': 'Energetic and thrilling tone',
                'suggestions': ['Use dynamic language', 'Short, punchy sentences', 'Highlight action and energy']
            },
            Mood.TENSE: {
                'description': 'Anxious and suspenseful tone',
                'suggestions': ['Build suspense gradually', 'Use uncertain language', 'Highlight potential dangers']
            },
            Mood.DANGEROUS: {
                'description': 'Perilous and threatening tone',
                'suggestions': ['Emphasize risks and dangers', 'Use urgent language', 'Highlight potential consequences']
            },
            Mood.MYSTERIOUS: {
                'description': 'Enigmatic and cryptic tone',
                'suggestions': ['Leave some things unexplained', 'Use vague language', 'Create intrigue']
            },
            Mood.PEACEFUL: {
                'description': 'Calm and serene tone',
                'suggestions': ['Use gentle language', 'Focus on sensory details', 'Create a relaxing atmosphere']
            },
            Mood.SAD: {
                'description': 'Melancholic and mournful tone',
                'suggestions': ['Use somber language', 'Focus on loss and sadness', 'Create emotional depth']
            },
            Mood.HORRIFIC: {
                'description': 'Terrifying and gruesome tone',
                'suggestions': ['Use disturbing imagery', 'Create a sense of dread', 'Highlight the macabre']
            },
            Mood.EPIC: {
                'description': 'Heroic and grand tone',
                'suggestions': ['Use grandiose language', 'Highlight scale and importance', 'Create a sense of destiny']
            }
        }
        
        return guidance.get(self.mood, guidance[Mood.NEUTRAL])


class MoodSystem:
    """Manages the mood and tone system for a session"""
    
    def __init__(self, session_slug: str, base_root: Optional[Path] = None):
        self.session_slug = session_slug
        root = base_root or Path(__file__).resolve().parent.parent
        self.session_root = root / "sessions" / session_slug
        self.mood_file = self.session_root / "mood_state.json"
        self.current_mood = Mood.NEUTRAL
        self.mood_intensity = 1.0
        self.mood_history = []
        self._load_mood_state()
    
    def _load_mood_state(self):
        """Load mood state from file"""
        if self.mood_file.exists():
            with self.mood_file.open() as f:
                data = json.load(f)
                self.current_mood = Mood(data.get('current_mood', 'neutral'))
                self.mood_intensity = data.get('mood_intensity', 1.0)
                self.mood_history = data.get('mood_history', [])
        else:
            self.current_mood = Mood.NEUTRAL
            self.mood_intensity = 1.0
            self.mood_history = []
    
    def _save_mood_state(self):
        """Save mood state to file"""
        data = {
            'current_mood': self.current_mood.value,
            'mood_intensity': self.mood_intensity,
            'mood_history': self.mood_history
        }
        
        with self.mood_file.open('w') as f:
            json.dump(data, f, indent=2)
    
    def get_current_mood(self) -> Mood:
        """Get the current mood"""
        return self.current_mood
    
    def get_mood_intensity(self) -> float:
        """Get the current mood intensity"""
        return self.mood_intensity
    
    def get_mood_history(self) -> List[Dict]:
        """Get the mood history"""
        return self.mood_history
    
    def set_mood(self, mood: Mood, intensity: float = 1.0, reason: str = "Unknown") -> Dict:
        """Set the current mood and intensity"""
        old_mood = self.current_mood
        old_intensity = self.mood_intensity
        
        self.current_mood = mood
        self.mood_intensity = max(0.0, min(2.0, intensity))  # Clamp between 0 and 2
        
        # Record mood change
        mood_change = {
            'timestamp': datetime.utcnow().isoformat(),
            'old_mood': old_mood.value,
            'new_mood': mood.value,
            'old_intensity': old_intensity,
            'new_intensity': self.mood_intensity,
            'reason': reason
        }
        
        self.mood_history.append(mood_change)
        self._save_mood_state()
        
        return {
            'message': 'Mood updated successfully',
            'old_mood': old_mood.value,
            'new_mood': mood.value,
            'old_intensity': old_intensity,
            'new_intensity': self.mood_intensity
        }
    
    def adjust_mood(self, mood_change: Mood, intensity_change: float = 0.0, 
                   reason: str = "Unknown") -> Dict:
        """Adjust the current mood by applying a change"""
        old_mood = self.current_mood
        old_intensity = self.mood_intensity
        
        # Apply mood change (can be positive or negative)
        mood_values = list(Mood)
        current_index = mood_values.index(self.current_mood)
        change_index = mood_values.index(mood_change)
        
        # Calculate new mood index (with wrapping)
        new_index = (current_index + change_index) % len(mood_values)
        self.current_mood = mood_values[new_index]
        
        # Apply intensity change
        self.mood_intensity = max(0.0, min(2.0, self.mood_intensity + intensity_change))
        
        # Record mood change
        mood_change_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'old_mood': old_mood.value,
            'new_mood': self.current_mood.value,
            'old_intensity': old_intensity,
            'new_intensity': self.mood_intensity,
            'change_type': 'adjustment',
            'mood_change': mood_change.value,
            'intensity_change': intensity_change,
            'reason': reason
        }
        
        self.mood_history.append(mood_change_record)
        self._save_mood_state()
        
        return {
            'message': 'Mood adjusted successfully',
            'old_mood': old_mood.value,
            'new_mood': self.current_mood.value,
            'old_intensity': old_intensity,
            'new_intensity': self.mood_intensity
        }
    
    def apply_mood_to_narrative(self, narrative: str) -> str:
        """Apply current mood to narrative text"""
        modifier = ToneModifier(self.current_mood, self.mood_intensity)
        return modifier.apply_to_narrative(narrative)
    
    async def generate_mood_enhanced_narrative(self, base_prompt: str, context: Dict) -> str:
        """Generate narrative enhanced with current mood using LLM"""
        enhancer = get_narrative_enhancer()
        
        if not enhancer.settings.has_llm_config:
            # Fallback to simple mood application
            return self.apply_mood_to_narrative(base_prompt)
        
        try:
            # Get mood guidance
            modifier = ToneModifier(self.current_mood, self.mood_intensity)
            guidance = modifier.get_narrative_guidance()
            
            # Create enhanced prompt with mood context
            enhanced_prompt = f"""Generate narrative with the following mood: {self.current_mood.value}

Mood Guidance: {guidance.get('description', '')}
Suggestions: {', '.join(guidance.get('suggestions', []))}

Base Prompt: {base_prompt}

Generate a vivid description that captures the essence of the {self.current_mood.value} mood."""
            
            narrative = await enhancer.enhance_scene_description(
                enhanced_prompt,
                context.get('scene_type', 'general'),
                self.current_mood.value,
                context
            )
            
            # Apply additional mood modifications
            return self.apply_mood_to_narrative(narrative)
            
        except Exception:
            return self.apply_mood_to_narrative(base_prompt)
    
    def get_mood_suggestions(self) -> Dict:
        """Get suggestions for maintaining or changing the current mood"""
        suggestions = {
            Mood.NEUTRAL: [
                "Introduce an unexpected event to change the mood",
                "Add a mysterious element to create intrigue",
                "Include a humorous situation to lighten the mood"
            ],
            Mood.JOYFUL: [
                "Describe a beautiful natural scene",
                "Include a celebration or festival",
                "Add playful interactions between characters"
            ],
            Mood.EXCITED: [
                "Build up to a dramatic reveal",
                "Add a sense of urgency or time pressure",
                "Include thrilling action or danger"
            ],
            Mood.TENSE: [
                "Add foreshadowing of potential danger",
                "Create uncertainty about outcomes",
                "Include suspicious or ambiguous behavior"
            ],
            Mood.DANGEROUS: [
                "Describe imminent threats in detail",
                "Highlight the consequences of failure",
                "Add environmental hazards or obstacles"
            ],
            Mood.MYSTERIOUS: [
                "Introduce unexplained phenomena",
                "Add cryptic clues or riddles",
                "Include characters with hidden motives"
            ],
            Mood.PEACEFUL: [
                "Describe a serene natural setting",
                "Include calming sensory details",
                "Add moments of reflection or meditation"
            ],
            Mood.SAD: [
                "Describe a tragic backstory or loss",
                "Include melancholic weather or settings",
                "Add characters expressing grief or sorrow"
            ],
            Mood.HORRIFIC: [
                "Describe gruesome or disturbing imagery",
                "Add supernatural or unnatural elements",
                "Include psychological horror elements"
            ],
            Mood.EPIC: [
                "Describe grand landscapes or vistas",
                "Add heroic or legendary characters",
                "Include world-changing stakes or consequences"
            ]
        }
        
        return {
            'current_mood': self.current_mood.value,
            'suggestions': suggestions.get(self.current_mood, []),
            'intensity': self.mood_intensity
        }


def get_mood_system(session_slug: str, base_root: Optional[Path] = None) -> MoodSystem:
    """Get the mood system for a session"""
    return MoodSystem(session_slug, base_root=base_root)
