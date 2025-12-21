"""
Discovery Log System - Tracks and manages player discoveries and achievements
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .llm_narrative import LLMNarrativeEnhancer, get_narrative_enhancer


class Discovery:
    """Represents a discovery made by the player"""
    
    def __init__(self, discovery_id: str, name: str, discovery_type: str, 
                 description: str, location: str, discovered_at: str,
                 importance: int = 1, related_quest: Optional[str] = None,
                 rewards: List[str] = None):
        self.discovery_id = discovery_id
        self.name = name
        self.discovery_type = discovery_type
        self.description = description
        self.location = location
        self.discovered_at = discovered_at
        self.importance = importance
        self.related_quest = related_quest
        self.rewards = rewards or []
    
    def to_dict(self) -> Dict:
        return {
            'discovery_id': self.discovery_id,
            'name': self.name,
            'discovery_type': self.discovery_type,
            'description': self.description,
            'location': self.location,
            'discovered_at': self.discovered_at,
            'importance': self.importance,
            'related_quest': self.related_quest,
            'rewards': self.rewards
        }


class DiscoveryLog:
    """Manages the discovery log for a session"""
    
    def __init__(self, session_slug: str):
        self.session_slug = session_slug
        self.discovery_file = (
            Path(__file__).resolve().parent.parent / "sessions" / session_slug / "discovery_log.json"
        )
        self.discoveries = []
        self._load_discoveries()
    
    def _load_discoveries(self):
        """Load discoveries from file"""
        if self.discovery_file.exists():
            with self.discovery_file.open() as f:
                data = json.load(f)
                self.discoveries = [Discovery(**discovery_data) for discovery_data in data]
        else:
            self.discoveries = []
    
    def _save_discoveries(self):
        """Save discoveries to file"""
        data = [discovery.to_dict() for discovery in self.discoveries]
        
        with self.discovery_file.open('w') as f:
            json.dump(data, f, indent=2)
    
    def log_discovery(self, discovery: Discovery):
        """Log a new discovery"""
        self.discoveries.append(discovery)
        self._save_discoveries()
    
    def get_all_discoveries(self) -> List[Discovery]:
        """Get all discoveries"""
        return self.discoveries
    
    def get_discoveries_by_type(self, discovery_type: str) -> List[Discovery]:
        """Get discoveries by type"""
        return [d for d in self.discoveries if d.discovery_type == discovery_type]
    
    def get_recent_discoveries(self, limit: int = 5) -> List[Discovery]:
        """Get most recent discoveries"""
        return sorted(self.discoveries, key=lambda d: d.discovered_at, reverse=True)[:limit]
    
    def get_important_discoveries(self, min_importance: int = 3) -> List[Discovery]:
        """Get important discoveries"""
        return [d for d in self.discoveries if d.importance >= min_importance]
    
    def get_discovery_stats(self) -> Dict:
        """Get statistics about discoveries"""
        if not self.discoveries:
            return {
                'total_discoveries': 0,
                'discoveries_by_type': {},
                'most_important': None,
                'recent_discovery': None
            }
        
        # Count by type
        type_counts = {}
        for discovery in self.discoveries:
            type_counts[discovery.discovery_type] = type_counts.get(discovery.discovery_type, 0) + 1
        
        # Find most important
        most_important = max(self.discoveries, key=lambda d: d.importance)
        
        # Find most recent
        recent = max(self.discoveries, key=lambda d: d.discovered_at)
        
        return {
            'total_discoveries': len(self.discoveries),
            'discoveries_by_type': type_counts,
            'most_important': {
                'discovery_id': most_important.discovery_id,
                'name': most_important.name,
                'importance': most_important.importance
            },
            'recent_discovery': {
                'discovery_id': recent.discovery_id,
                'name': recent.name,
                'discovered_at': recent.discovered_at
            }
        }
    
    def generate_discovery_id(self) -> str:
        """Generate a unique discovery ID"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        random_suffix = f"{random.randint(100, 999)}"
        return f"disc-{timestamp}-{random_suffix}"
    
    async def generate_discovery_description(self, discovery: Discovery) -> str:
        """Generate an enhanced description for a discovery using LLM"""
        enhancer = get_narrative_enhancer()
        
        if not enhancer.settings.has_llm_config:
            return discovery.description
        
        try:
            prompt = f"""Enhance this discovery description for a D&D game:

Discovery: {discovery.name}
Type: {discovery.discovery_type}
Location: {discovery.location}
Current Description: {discovery.description}

Provide a more vivid, detailed description that captures the excitement and significance of this discovery. Include sensory details and emotional impact."""
            
            enhanced_description = await enhancer.enhance_scene_description(
                prompt,
                discovery.discovery_type,
                "excited",
                {
                    'discovery': discovery.name,
                    'location': discovery.location,
                    'type': discovery.discovery_type
                }
            )
            
            return enhanced_description
            
        except Exception:
            return discovery.description
    
    def create_discovery(self, name: str, discovery_type: str, description: str,
                        location: str, importance: int = 1,
                        related_quest: Optional[str] = None,
                        rewards: List[str] = None) -> Discovery:
        """Create a new discovery entry"""
        discovery_id = self.generate_discovery_id()
        discovered_at = datetime.utcnow().isoformat()
        
        discovery = Discovery(
            discovery_id=discovery_id,
            name=name,
            discovery_type=discovery_type,
            description=description,
            location=location,
            discovered_at=discovered_at,
            importance=importance,
            related_quest=related_quest,
            rewards=rewards or []
        )
        
        self.log_discovery(discovery)
        return discovery


def get_discovery_log(session_slug: str) -> DiscoveryLog:
    """Get the discovery log for a session"""
    return DiscoveryLog(session_slug)