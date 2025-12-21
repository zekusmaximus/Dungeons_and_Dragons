"""
NPC Relationship Tracking System - Tracks and manages relationships between player characters and NPCs
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .llm_narrative import LLMNarrativeEnhancer, get_narrative_enhancer


class NPCRelationship:
    """Represents the relationship between a character and an NPC"""
    
    def __init__(self, npc_id: str, name: str, relationship_level: int = 0, 
                 trust: int = 0, liking: int = 0, fear: int = 0, 
                 last_interaction: Optional[str] = None, 
                 interaction_history: List[Dict] = None):
        self.npc_id = npc_id
        self.name = name
        self.relationship_level = relationship_level  # -10 to 10 scale
        self.trust = trust  # 0-100
        self.liking = liking  # 0-100
        self.fear = fear  # 0-100
        self.last_interaction = last_interaction
        self.interaction_history = interaction_history or []
    
    def update_relationship(self, interaction_type: str, success: bool, context: Dict) -> Dict:
        """Update relationship based on interaction"""
        changes = {
            'interaction_type': interaction_type,
            'success': success,
            'old_level': self.relationship_level,
            'old_trust': self.trust,
            'old_liking': self.liking,
            'old_fear': self.fear
        }
        
        # Calculate relationship changes based on interaction
        if interaction_type == 'help':
            self.relationship_level += 2 if success else -1
            self.trust += 15 if success else -5
            self.liking += 10 if success else -5
        
        elif interaction_type == 'threat':
            self.relationship_level -= 3
            self.trust -= 20
            self.liking -= 15
            self.fear += 25 if success else 5
        
        elif interaction_type == 'gift':
            self.relationship_level += 1 if success else 0
            self.trust += 5 if success else 0
            self.liking += 10 if success else 0
        
        elif interaction_type == 'lie':
            self.relationship_level -= 2 if success else -1
            self.trust -= 25 if success else -10
            self.liking -= 5
        
        elif interaction_type == 'promise':
            self.relationship_level += 1 if success else -2
            self.trust += 10 if success else -15
            self.liking += 5 if success else -5
        
        elif interaction_type == 'insult':
            self.relationship_level -= 2
            self.trust -= 10
            self.liking -= 20
            self.fear += 5
        
        # Clamp values
        self.relationship_level = max(-10, min(10, self.relationship_level))
        self.trust = max(0, min(100, self.trust))
        self.liking = max(0, min(100, self.liking))
        self.fear = max(0, min(100, self.fear))
        
        # Record interaction
        interaction_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': interaction_type,
            'success': success,
            'context': context,
            'relationship_change': self.relationship_level - changes['old_level'],
            'trust_change': self.trust - changes['old_trust'],
            'liking_change': self.liking - changes['old_liking'],
            'fear_change': self.fear - changes['old_fear']
        }
        
        self.interaction_history.append(interaction_record)
        self.last_interaction = interaction_record['timestamp']
        
        changes.update({
            'new_level': self.relationship_level,
            'new_trust': self.trust,
            'new_liking': self.liking,
            'new_fear': self.fear
        })
        
        return changes
    
    def get_relationship_status(self) -> str:
        """Get a text description of the relationship status"""
        if self.relationship_level >= 8:
            return 'Best Friends'
        elif self.relationship_level >= 5:
            return 'Close Friends'
        elif self.relationship_level >= 2:
            return 'Friends'
        elif self.relationship_level >= -2:
            return 'Acquaintances'
        elif self.relationship_level >= -5:
            return 'Distrustful'
        elif self.relationship_level >= -8:
            return 'Hostile'
        else:
            return 'Enemies'
    
    def get_attitude(self) -> str:
        """Get the NPC's current attitude based on relationship"""
        status = self.get_relationship_status()
        
        attitudes = {
            'Best Friends': 'Warm and welcoming',
            'Close Friends': 'Friendly and helpful',
            'Friends': 'Pleasant and cooperative',
            'Acquaintances': 'Polite but cautious',
            'Distrustful': 'Cold and suspicious',
            'Hostile': 'Unfriendly and aggressive',
            'Enemies': 'Openly hostile'
        }
        
        return attitudes.get(status, 'Neutral')
    
    def to_dict(self) -> Dict:
        return {
            'npc_id': self.npc_id,
            'name': self.name,
            'relationship_level': self.relationship_level,
            'trust': self.trust,
            'liking': self.liking,
            'fear': self.fear,
            'last_interaction': self.last_interaction,
            'interaction_history': self.interaction_history,
            'relationship_status': self.get_relationship_status(),
            'attitude': self.get_attitude()
        }


class NPCRelationshipService:
    """Service for managing NPC relationships"""
    
    def __init__(self, session_slug: str):
        self.session_slug = session_slug
        self.relationships_file = (
            Path(__file__).resolve().parent.parent / "sessions" / session_slug / "npc_relationships.json"
        )
        self._load_relationships()
    
    def _load_relationships(self):
        """Load relationships from file"""
        if self.relationships_file.exists():
            with self.relationships_file.open() as f:
                data = json.load(f)
                self.relationships = {
                    npc_id: NPCRelationship(**npc_data)
                    for npc_id, npc_data in data.items()
                }
        else:
            self.relationships = {}
    
    def _save_relationships(self):
        """Save relationships to file"""
        data = {
            npc_id: relationship.to_dict()
            for npc_id, relationship in self.relationships.items()
        }
        
        with self.relationships_file.open('w') as f:
            json.dump(data, f, indent=2)
    
    def get_relationship(self, npc_id: str) -> Optional[NPCRelationship]:
        """Get relationship with a specific NPC"""
        return self.relationships.get(npc_id)
    
    def get_all_relationships(self) -> List[NPCRelationship]:
        """Get all NPC relationships"""
        return list(self.relationships.values())
    
    def get_relationship_status(self, npc_id: str) -> Optional[str]:
        """Get the status of a relationship"""
        relationship = self.get_relationship(npc_id)
        return relationship.get_relationship_status() if relationship else None
    
    def update_relationship(self, npc_id: str, npc_name: str, interaction_type: str, 
                           success: bool, context: Dict) -> Dict:
        """Update relationship with an NPC"""
        if npc_id not in self.relationships:
            self.relationships[npc_id] = NPCRelationship(npc_id, npc_name)
        
        changes = self.relationships[npc_id].update_relationship(interaction_type, success, context)
        self._save_relationships()
        return changes
    
    def add_new_npc(self, npc_id: str, npc_name: str) -> NPCRelationship:
        """Add a new NPC to track"""
        if npc_id not in self.relationships:
            self.relationships[npc_id] = NPCRelationship(npc_id, npc_name)
            self._save_relationships()
        return self.relationships[npc_id]
    
    def get_npc_attitude(self, npc_id: str) -> Optional[str]:
        """Get an NPC's current attitude"""
        relationship = self.get_relationship(npc_id)
        return relationship.get_attitude() if relationship else None
    
    def get_relationship_summary(self, npc_id: str) -> Optional[Dict]:
        """Get a summary of the relationship with an NPC"""
        relationship = self.get_relationship(npc_id)
        if not relationship:
            return None
        
        return {
            'npc_id': relationship.npc_id,
            'name': relationship.name,
            'status': relationship.get_relationship_status(),
            'attitude': relationship.get_attitude(),
            'relationship_level': relationship.relationship_level,
            'trust': relationship.trust,
            'liking': relationship.liking,
            'fear': relationship.fear,
            'last_interaction': relationship.last_interaction
        }
    
    async def generate_relationship_dialogue(self, npc_id: str, context: Dict) -> Optional[str]:
        """Generate dialogue based on current relationship status"""
        relationship = self.get_relationship(npc_id)
        if not relationship:
            return None
        
        enhancer = get_narrative_enhancer()
        if not enhancer.settings.has_llm_config:
            # Fallback to simple dialogue based on relationship
            status = relationship.get_relationship_status()
            attitudes = {
                'Best Friends': f"Greetings, my dear friend! It's wonderful to see you again.",
                'Close Friends': f"Ah, {context.get('character_name', 'friend')}! Always a pleasure.",
                'Friends': f"Hello there! How have you been?",
                'Acquaintances': f"Greetings. What can I do for you?",
                'Distrustful': f"What do you want?",
                'Hostile': f"I have nothing to say to you.",
                'Enemies': f"Get away from me!"
            }
            return attitudes.get(status, "Hello.")
        
        try:
            # Generate relationship-aware dialogue using LLM
            relationship_status = relationship.get_relationship_status()
            attitude = relationship.get_attitude()
            
            prompt = f"""Generate dialogue for an NPC based on their relationship with the player:

NPC: {relationship.name}
Player: {context.get('character_name', 'Adventurer')}
Relationship Status: {relationship_status}
Attitude: {attitude}
Current Situation: {context.get('situation', 'meeting in town')}

Generate a brief greeting that reflects their current relationship and attitude."""
            
            dialogue = await enhancer.generate_npc_dialogue(
                relationship.name,
                relationship_status,
                context.get('situation', 'meeting'),
                context
            )
            
            return dialogue
            
        except Exception:
            return f"{relationship.name} acknowledges you with a {attitude.lower()} demeanor."


def get_npc_relationship_service(session_slug: str) -> NPCRelationshipService:
    """Get the NPC relationship service for a session"""
    return NPCRelationshipService(session_slug)