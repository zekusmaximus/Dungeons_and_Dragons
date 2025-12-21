import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import ValidationError

from .config import Settings
from .llm import call_llm_api
from .models import DMNarration, DMChoice, DiscoveryItem


def _parse_dm_json(raw: str) -> Optional[Dict]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Attempt to extract JSON from fenced blocks
    if "{" in raw and "}" in raw:
        candidate = raw[raw.find("{") : raw.rfind("}") + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


def _fallback_dm_output(state: Dict, player_intent: str, diff: List[str], include_discovery: bool) -> DMNarration:
    location = state.get("location", "the current area")
    turn = state.get("turn", 0)
    recap = f"Turn {turn}: {state.get('character', 'The hero')} pushes onward at {location}."
    stakes = "Consequences ripple from each move; risk what you value to advance." if diff else "Small shifts, but pressure builds." 
    changes = diff or ["No major state shifts recorded."]
    narration = (
        f"After choosing '{player_intent}', the scene adjusts: "
        f"{' '.join(changes)}"
    )
    discovery: Optional[DiscoveryItem] = None
    if include_discovery:
        discovery = DiscoveryItem(
            title=f"Rumor about {location}",
            text="A fresh rumor surfaces, hinting at something hidden nearby."
        )
    base_choices = [
        DMChoice(id="A", text=f"Ask around about {location} rumors", intent_tag="talk", risk="low"),
        DMChoice(id="B", text="Scout for hidden paths", intent_tag="sneak", risk="medium"),
        DMChoice(id="C", text="Press forward boldly", intent_tag="fight", risk="high"),
    ]
    return DMNarration(
        narration=narration,
        recap=recap,
        stakes=stakes,
        choices=base_choices,
        discovery_added=discovery,
    )


async def generate_dm_narration(
    settings: Settings,
    slug: str,
    state: Dict,
    player_intent: str,
    diff: List[str],
    include_discovery: bool = False,
) -> Tuple[DMNarration, Optional[Dict[str, int]]]:
    prompt = (
        "You are the deterministic DM. Return ONLY valid JSON matching the schema.\n"
        "Schema: {\n"
        "  narration: string,\n"
        "  recap: string,\n"
        "  stakes: string (1-2 sentences),\n"
        "  choices: array of 2-4 items with fields {id: A/B/C/D, text, intent_tag: talk|sneak|fight|magic|investigate|travel|other, risk: low|medium|high},\n"
        "  discovery_added: optional {title, text}\n"
        "}.\n"
        "Rules: concise, grounded in provided state; keep outputs safe; do not add dice."
    )
    if include_discovery:
        prompt += " Always include discovery_added describing a new clue or rumor this turn."

    context = {
        "session": slug,
        "state": state,
        "player_intent": player_intent,
        "diff": diff,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    attempts = []
    last_usage: Optional[Dict[str, int]] = None
    for attempt in range(2):
        try:
            result = await call_llm_api(settings, prompt, context)
            last_usage = result.get("usage")
            raw = result.get("content", "")
            parsed = _parse_dm_json(raw)
            if not parsed:
                raise ValueError("LLM did not return JSON")
            dm = DMNarration.model_validate(parsed)
            return dm, last_usage
        except Exception as exc:  # noqa: BLE001
            attempts.append(str(exc))
            prompt = (
                "Previous response was invalid JSON. Respond again with ONLY the JSON body per schema."
                " Ensure choices have id, text, intent_tag, and risk."
            )
            continue

    try:
        return _fallback_dm_output(state, player_intent, diff, include_discovery), last_usage
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build DM narration: {exc}")
