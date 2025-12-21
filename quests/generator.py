import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from tools.explore import next_entropy, roll_from_entry


def generate_dynamic_quest(
    character_context: Dict,
    session_context: Dict,
    use_llm: bool = True
) -> Dict:
    """Generate a dynamic quest based on character and session context"""
    
    # Basic quest structure
    quest_id = f"quest-{session_context.get('log_index', random.randint(1000, 9999))}"
    character_name = character_context.get('name', 'Adventurer')
    character_class = character_context.get('class', 'Hero')
    character_level = character_context.get('level', 1)
    current_location = session_context.get('location', 'Briarwood')
    
    # Determine quest type based on character class
    quest_types = {
        'fighter': ['combat', 'escort', 'hunt'],
        'rogue': ['stealth', 'infiltration', 'theft', 'investigation'],
        'wizard': ['research', 'arcane', 'puzzle', 'cursed_item'],
        'cleric': ['healing', 'exorcism', 'blessing', 'restoration'],
        'ranger': ['tracking', 'exploration', 'hunting', 'survival'],
        'paladin': ['justice', 'protection', 'holy_quest', 'redemption'],
        'bard': ['performance', 'diplomacy', 'intrigue', 'information_gathering'],
        'barbarian': ['combat', 'endurance', 'tribal', 'beast_hunt'],
        'monk': ['training', 'discipline', 'balance', 'spiritual'],
        'druid': ['nature', 'animal', 'elemental', 'restoration']
    }
    
    class_key = next((cls for cls in quest_types if cls in character_class.lower()), 'fighter')
    quest_type = random.choice(quest_types[class_key])
    
    # Generate quest based on type
    if quest_type in ['combat', 'hunt', 'tribal', 'beast_hunt']:
        quest = _generate_combat_quest(character_context, session_context, quest_type)
    elif quest_type in ['stealth', 'infiltration', 'theft', 'investigation']:
        quest = _generate_stealth_quest(character_context, session_context, quest_type)
    elif quest_type in ['research', 'arcane', 'puzzle', 'cursed_item']:
        quest = _generate_arcane_quest(character_context, session_context, quest_type)
    elif quest_type in ['healing', 'exorcism', 'blessing', 'restoration']:
        quest = _generate_divine_quest(character_context, session_context, quest_type)
    elif quest_type in ['tracking', 'exploration', 'hunting', 'survival']:
        quest = _generate_exploration_quest(character_context, session_context, quest_type)
    elif quest_type in ['justice', 'protection', 'holy_quest', 'redemption']:
        quest = _generate_holy_quest(character_context, session_context, quest_type)
    elif quest_type in ['performance', 'diplomacy', 'intrigue', 'information_gathering']:
        quest = _generate_social_quest(character_context, session_context, quest_type)
    elif quest_type in ['training', 'discipline', 'balance', 'spiritual']:
        quest = _generate_training_quest(character_context, session_context, quest_type)
    else:  # nature, animal, elemental
        quest = _generate_nature_quest(character_context, session_context, quest_type)
    
    # Add quest ID and character-specific details
    quest['id'] = quest_id
    quest['character_name'] = character_name
    quest['character_class'] = character_class
    quest['character_level'] = character_level
    quest['starting_location'] = current_location
    quest['quest_type'] = quest_type
    
    return quest


def _generate_combat_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate combat-focused quests"""
    monsters = ['goblins', 'bandits', 'orcs', 'trolls', 'undead', 'giant spiders']
    locations = ['ancient ruins', 'abandoned mine', 'haunted forest', 'bandit camp', 'cursed temple']
    
    monster = random.choice(monsters)
    location = random.choice(locations)
    
    if quest_type == 'hunt':
        return {
            'name': f'Hunt the {monster.capitalize()}',
            'description': f'A local village is being terrorized by {monster} in the nearby {location}. Eliminate the threat.',
            'objectives': [
                f'Find the {monster} lair in the {location}',
                f'Eliminate the {monster} leader',
                'Return with proof of your victory'
            ],
            'rewards': ['Gold bounty', 'Local gratitude', 'Possible magic item'],
            'difficulty': 'medium',
            'starting_scene': f'The village elder pleads for your help: "Our children are afraid to leave their homes! Please, {character_context.get("name", "hero")}, rid us of this menace!"'
        }
    else:
        return {
            'name': f'Clear the {location.capitalize()}',
            'description': f'Dangerous {monster} have taken over the {location}. Clear them out and make it safe for travelers.',
            'objectives': [
                f'Travel to the {location}',
                f'Defeat all {monster}',
                'Secure the area'
            ],
            'rewards': ['Gold reward', 'Safe passage rights', 'Experience'],
            'difficulty': 'medium',
            'starting_scene': f'A town crier announces: "Brave warriors needed! The {location} must be reclaimed!"'
        }


def _generate_stealth_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate stealth-focused quests"""
    targets = ['noble', 'merchant', 'guildmaster', 'spymaster', 'cult leader']
    locations = ['grand manor', 'guild hall', 'warehouse', 'secret meeting', 'underground vault']
    
    target = random.choice(targets)
    location = random.choice(locations)
    
    if quest_type == 'theft':
        return {
            'name': f'The {target.capitalize()}\'s Secret',
            'description': f'Retrieve a valuable item from the {target}\'s {location} without being detected.',
            'objectives': [
                f'Infiltrate the {location}',
                f'Find and steal the target item',
                'Escape without raising the alarm'
            ],
            'rewards': ['Substantial gold payment', 'Faction favor', 'Rare item'],
            'difficulty': 'hard',
            'starting_scene': f'A shadowy figure in a dark alley whispers: "I have a job for someone with your... particular skills."'
        }
    else:
        return {
            'name': f'Shadows in the {location.capitalize()}',
            'description': f'Investigate suspicious activity in the {location} without being noticed.',
            'objectives': [
                f'Enter the {location} unseen',
                'Gather information about the activity',
                'Report back to your employer'
            ],
            'rewards': ['Valuable information', 'Faction reputation', 'Possible blackmail material'],
            'difficulty': 'medium',
            'starting_scene': f'Your contact slides a note across the tavern table: "Meet me at the old docks. I have work for you."'
        }


def _generate_arcane_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate arcane/magic-focused quests"""
    artifacts = ['ancient tome', 'mystical artifact', 'enchanted crystal', 'forbidden scroll', 'arcane focus']
    phenomena = ['magical disturbance', 'dimensional rift', 'cursed object', 'haunting', 'elemental imbalance']
    
    artifact = random.choice(artifacts)
    phenomenon = random.choice(phenomena)
    
    if quest_type == 'research':
        return {
            'name': f'The Lost {artifact.capitalize()}',
            'description': f'Find and decipher the ancient {artifact} hidden in a forgotten library.',
            'objectives': [
                'Locate the hidden library',
                f'Retrieve the {artifact}',
                'Decipher its secrets'
            ],
            'rewards': ['Arcane knowledge', 'Powerful spell', 'Scholar reputation'],
            'difficulty': 'medium',
            'starting_scene': f'The old librarian eyes you carefully: "I believe you may be the one who can finally unlock the secrets of the {artifact}."'
        }
    else:
        return {
            'name': f'The {phenomenon.capitalize()}',
            'description': f'Investigate and resolve the strange {phenomenon} affecting the local area.',
            'objectives': [
                f'Find the source of the {phenomenon}',
                'Determine its cause',
                'Resolve or contain the phenomenon'
            ],
            'rewards': ['Magical insight', 'Local gratitude', 'Possible enchanted item'],
            'difficulty': 'hard',
            'starting_scene': f'The town sage rushes to you: "The very fabric of magic is unraveling! We need your expertise!"'
        }


def _generate_divine_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate divine/holy-focused quests"""
    afflictions = ['plague', 'curse', 'undead scourge', 'demonic influence', 'divine punishment']
    sacred_items = ['holy relic', 'blessed artifact', 'sacred text', 'divine symbol', 'consecrated ground']
    
    affliction = random.choice(afflictions)
    sacred_item = random.choice(sacred_items)
    
    if quest_type == 'healing':
        return {
            'name': f'Cure the {affliction.capitalize()}',
            'description': f'A terrible {affliction} has struck the land. Find its source and heal the afflicted.',
            'objectives': [
                f'Investigate the {affliction}',
                'Find its supernatural source',
                'Purify the land and heal the people'
            ],
            'rewards': ['Divine favor', 'Local reverence', 'Holy relic'],
            'difficulty': 'medium',
            'starting_scene': f'The temple bells toll mournfully as the high priestess begs: "Please, help us end this suffering!"'
        }
    else:
        return {
            'name': f'Recover the {sacred_item.capitalize()}',
            'description': f'A sacred {sacred_item} has been stolen. Recover it before it falls into evil hands.',
            'objectives': [
                'Track the thieves',
                f'Retrieve the {sacred_item}',
                'Return it to its rightful place'
            ],
            'rewards': ['Divine blessing', 'Temple favor', 'Spiritual enlightenment'],
            'difficulty': 'medium',
            'starting_scene': f'The temple doors burst open as a frantic acolyte shouts: "The {sacred_item} is gone!"'
        }


def _generate_exploration_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate exploration-focused quests"""
    locations = ['uncharted island', 'ancient ruins', 'hidden valley', 'forgotten cave system', 'mystical grove']
    discoveries = ['lost civilization', 'rare creature', 'hidden treasure', 'ancient secret', 'magical phenomenon']
    
    location = random.choice(locations)
    discovery = random.choice(discoveries)
    
    return {
        'name': f'Explore the {location.capitalize()}',
        'description': f'Venture into the unexplored {location} and discover what lies within.',
        'objectives': [
            f'Find a way into the {location}',
            'Map the area',
            f'Discover the secret of the {discovery}'
        ],
        'rewards': ['New territory discovered', 'Rare artifacts', 'Explorer reputation'],
        'difficulty': 'medium',
        'starting_scene': f'A weathered map unfolds before you, revealing the location of the fabled {location}.'
    }


def _generate_holy_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate holy/justice-focused quests"""
    injustices = ['tyrant ruler', 'corrupt official', 'oppressed villagers', 'stolen lands', 'broken oaths']
    holy_artifacts = ['sacred sword', 'holy grail', 'divine shield', 'blessed armor', 'consecrated relic']
    
    injustice = random.choice(injustices)
    artifact = random.choice(holy_artifacts)
    
    if quest_type == 'justice':
        return {
            'name': f'End the {injustice.capitalize()}',
            'description': f'Bring justice to those suffering under the {injustice}.',
            'objectives': [
                f'Investigate the {injustice}',
                'Gather evidence',
                'Bring the perpetrators to justice'
            ],
            'rewards': ['Local hero status', 'Divine favor', 'Justice served'],
            'difficulty': 'hard',
            'starting_scene': f'A desperate villager falls at your feet: "Please, noble {character_context.get("class", "hero")}, save us from this tyranny!"'
        }
    else:
        return {
            'name': f'Quest for the {artifact.capitalize()}',
            'description': f'Retrieve the legendary {artifact} to restore balance to the land.',
            'objectives': [
                f'Find clues to the {artifact}\'s location',
                'Overcome the trials',
                f'Return with the {artifact}'
            ],
            'rewards': ['Divine blessing', 'Legendary status', 'Powerful artifact'],
            'difficulty': 'hard',
            'starting_scene': f'A divine vision reveals the location of the lost {artifact}. Your holy quest begins.'
        }


def _generate_social_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate social/interaction-focused quests"""
    events = ['grand ball', 'royal wedding', 'noble feast', 'diplomatic summit', 'cultural festival']
    conflicts = ['family feud', 'political scandal', 'trade dispute', 'noble rivalry', 'cultural misunderstanding']
    
    event = random.choice(events)
    conflict = random.choice(conflicts)
    
    if quest_type == 'performance':
        return {
            'name': f'Perform at the {event.capitalize()}',
            'description': f'You have been invited to perform at the prestigious {event}. Make a lasting impression.',
            'objectives': [
                'Prepare your performance',
                f'Attend the {event}',
                'Impress the audience'
            ],
            'rewards': ['Social reputation', 'Noble favor', 'Gold payment'],
            'difficulty': 'easy',
            'starting_scene': f'An ornate invitation arrives: "You are cordially invited to perform at the {event}."'
        }
    else:
        return {
            'name': f'Resolve the {conflict.capitalize()}',
            'description': f'Mediate the {conflict} before it escalates into violence.',
            'objectives': [
                'Meet with both parties',
                'Understand their grievances',
                'Find a peaceful resolution'
            ],
            'rewards': ['Diplomatic reputation', 'Faction favor', 'Prevented conflict'],
            'difficulty': 'medium',
            'starting_scene': f'A frantic messenger arrives: "The {conflict} is about to tear our community apart!"'
        }


def _generate_training_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate training/self-improvement quests"""
    masters = ['ancient monk', 'wise sage', 'legendary warrior', 'mystical hermit', 'divine oracle']
    challenges = ['physical trial', 'mental challenge', 'spiritual test', 'elemental trial', 'ancient ritual']
    
    master = random.choice(masters)
    challenge = random.choice(challenges)
    
    return {
        'name': f'Trial of the {master.capitalize()}',
        'description': f'Seek out the {master} and complete their {challenge} to prove your worth.',
        'objectives': [
            f'Find the {master}',
            f'Complete the {challenge}',
            'Gain new insights and abilities'
        ],
        'rewards': ['New abilities', 'Master favor', 'Personal growth'],
        'difficulty': 'hard',
        'starting_scene': f'A mysterious stranger hands you a scroll: "The {master} awaits those worthy of their teachings."'
    }


def _generate_nature_quest(character_context: Dict, session_context: Dict, quest_type: str) -> Dict:
    """Generate nature-focused quests"""
    creatures = ['ancient treant', 'wounded unicorn', 'lost dryad', 'angry elemental', 'cursed beast']
    phenomena = ['blighted forest', 'polluted river', 'dying grove', 'unbalanced ecosystem', 'corrupted nature']
    
    creature = random.choice(creatures)
    phenomenon = random.choice(phenomena)
    
    if quest_type == 'animal':
        return {
            'name': f'Help the {creature.capitalize()}',
            'description': f'A {creature} needs your help to overcome a magical affliction.',
            'objectives': [
                f'Find the {creature}',
                'Determine the cause of their suffering',
                'Heal or aid the creature'
            ],
            'rewards': ['Nature favor', 'Magical gift', 'Druidic reputation'],
            'difficulty': 'medium',
            'starting_scene': f'The forest itself seems to guide you toward the suffering {creature}.'
        }
    else:
        return {
            'name': f'Heal the {phenomenon.capitalize()}',
            'description': f'The natural {phenomenon} must be restored to maintain balance.',
            'objectives': [
                f'Investigate the {phenomenon}',
                'Find its unnatural cause',
                'Restore the natural balance'
            ],
            'rewards': ['Nature blessing', 'Druid favor', 'Ecosystem restored'],
            'difficulty': 'hard',
            'starting_scene': f'The very earth cries out as you approach the {phenomenon}.'
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--template", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    session_dir = root / "sessions" / args.slug
    transcript_path = session_dir / "transcript.md"
    changelog_path = session_dir / "changelog.md"

    template = json.load(open(root / "quests" / "templates" / f"{args.template}.json", "r", encoding="utf-8"))
    entry = next_entropy(json.load(open(session_dir / "state.json"))["log_index"])
    state_path = session_dir / "state.json"
    state = json.load(open(state_path))
    state["log_index"] = entry["i"]

    world = json.load(open(root / "worlds" / state["world"] / "hexmap.json", "r", encoding="utf-8"))
    quest_nodes = []
    for node in template["nodes"]:
        for hx in world["hexes"]:
            if hx["biome"] == node["biome"]:
                quest_nodes.append({"id": node["id"], "hex": {"q": hx["q"], "r": hx["r"]}, "biome": node["biome"], "description": node.get("description", "")})
                break

    quest_id = f"quest-{entry['i']}"
    quest = {
        "id": quest_id,
        "name": template["name"],
        "status": "active",
        "objectives": template["objectives"],
        "nodes": quest_nodes,
    }
    quests_dir = session_dir / "quests"
    quests_dir.mkdir(exist_ok=True)
    json.dump(quest, open(quests_dir / f"{quest_id}.json", "w", encoding="utf-8"), indent=2)
    state.setdefault("quests", {})[quest_id] = {"status": "active"}
    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)

    with open(transcript_path, "a", encoding="utf-8") as tlog:
        tlog.write(
            " ".join(
                [
                    "A patron seeks aid recovering a relic from a forest ruin.",
                    "Leads point toward an overgrown shrine and a pursuit across nearby hills.",
                    "The prize could sway local druidic circles.",
                    "Rumors mention competing hunters and ancient wards.",
                    "Speed and discretion are rewarded."
                ]
            )
            + "\n"
        )

    with open(changelog_path, "a", encoding="utf-8") as clog:
        clog.write(
            json.dumps(
                {
                    "type": "quest_init",
                    "template": template["id"],
                    "nodes": [n["id"] for n in quest_nodes],
                    "entropy_index": entry["i"],
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
