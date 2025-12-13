import argparse
import json
from dataclasses import dataclass
from typing import List


@dataclass
class Combatant:
    name: str
    attack: int
    ac: int
    hp: int
    stance_bonus: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Combatant":
        return cls(
            name=data.get("name", "unknown"),
            attack=int(data.get("attack", 0)),
            ac=int(data.get("ac", 10)),
            hp=int(data.get("hp", 1)),
            stance_bonus=int(data.get("stance_bonus", 0)),
        )


def expected_hits(attacker: Combatant, defender: Combatant) -> float:
    delta = attacker.attack + attacker.stance_bonus - defender.ac
    # deterministic approximation: chance to hit mapped from delta
    base = 0.55 + (delta * 0.05)
    return max(0.05, min(0.95, base)) * attacker.hp


def evaluate_battle(heroes: List[Combatant], enemies: List[Combatant]) -> dict:
    hero_pressure = sum(expected_hits(h, e) for h, e in zip(heroes, enemies * len(heroes)))
    enemy_pressure = sum(expected_hits(e, h) for e, h in zip(enemies, heroes * len(enemies)))
    outcome = "stalemate"
    if hero_pressure > enemy_pressure:
        outcome = "heroes_edge"
    elif enemy_pressure > hero_pressure:
        outcome = "enemies_edge"
    return {
        "heroes_pressure": round(hero_pressure, 2),
        "enemies_pressure": round(enemy_pressure, 2),
        "outcome": outcome
    }


def parse_list(raw: str) -> List[Combatant]:
    data = json.loads(raw)
    return [Combatant.from_dict(entry) for entry in data]


def main():
    parser = argparse.ArgumentParser(description="Deterministic combat outcome calculator")
    parser.add_argument("--heroes", required=True, help="JSON list of hero combatants")
    parser.add_argument("--enemies", required=True, help="JSON list of enemy combatants")
    args = parser.parse_args()

    heroes = parse_list(args.heroes)
    enemies = parse_list(args.enemies)
    result = evaluate_battle(heroes, enemies)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
