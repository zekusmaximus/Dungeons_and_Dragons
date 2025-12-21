import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import ValidationError

from .config import Settings
from .llm import call_llm_api
from .diff_highlights import summarize_diff, derive_consequence_echo
from .models import DMNarration, DMChoice, DiscoveryItem, RollRequest


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


_RISK_ORDER = ["low", "medium", "high"]
_ALLOWED_INTENTS = {"talk", "sneak", "fight", "magic", "investigate", "travel", "other"}
_BANNED_CHOICE_WORDS = {"continue", "do nothing", "wait", "skip"}
_OPENING_HOOKS = {
    "classic dungeon": {
        "problem": "A sealed stairwell yawns open as fresh tremors shake the stonework.",
        "reason": "A lead from your past points to something valuable buried below.",
    },
    "urban mystery": {
        "problem": "A missing contact leaves behind a warning and a trail of coded notes.",
        "reason": "Your background makes you the only one trusted with the quiet investigation.",
    },
    "wilderness survival": {
        "problem": "A storm crushes the trail and a nearby camp calls for immediate aid.",
        "reason": "You were hired for your grit and local know-how.",
    },
    "political intrigue": {
        "problem": "A rival faction moves against your patron during a public gathering.",
        "reason": "You are here to keep the peace and extract the truth.",
    },
    "horror": {
        "problem": "An unnatural hush blankets the area and a survivor begs for help.",
        "reason": "You came to confirm the rumors before anyone else vanishes.",
    },
}


def _default_choices(state: Dict) -> List[DMChoice]:
    location = state.get("location", "this place")
    return [
        DMChoice(id="A", text=f"Ask locals about {location}", intent_tag="talk", risk="low"),
        DMChoice(id="B", text="Probe quietly for weak spots", intent_tag="sneak", risk="medium"),
        DMChoice(id="C", text="Force the issue with bold action", intent_tag="fight", risk="high"),
        DMChoice(id="D", text="Study the scene for clues or magic traces", intent_tag="investigate", risk="medium"),
        DMChoice(id="E", text="Change position and scout a new angle", intent_tag="travel", risk="low"),
    ]


def _sanitize_choices(choices: List[Dict], state: Dict) -> Tuple[List[DMChoice], bool]:
    sanitized: List[DMChoice] = []
    seen_texts = set()
    fallback_used = False

    def _should_drop(text: str) -> bool:
        lower = text.lower()
        return any(bad in lower for bad in _BANNED_CHOICE_WORDS)

    fallback_choices = _default_choices(state)

    for idx, raw in enumerate(choices):
        if not isinstance(raw, dict):
            fallback_used = True
            continue
        text = str(raw.get("text", "")).strip()
        if not text or _should_drop(text):
            fallback_used = True
            continue
        lowered = text.lower()
        if lowered in seen_texts:
            fallback_used = True
            continue
        seen_texts.add(lowered)

        intent_tag = raw.get("intent_tag") if raw.get("intent_tag") in _ALLOWED_INTENTS else "other"
        risk = raw.get("risk") if raw.get("risk") in _RISK_ORDER else "medium"
        choice_id = raw.get("id") or chr(ord("A") + len(sanitized))

        try:
            sanitized.append(DMChoice(id=str(choice_id), text=text, intent_tag=intent_tag, risk=risk))
        except Exception:
            fallback_used = True
            continue

    if len(sanitized) < 4:
        fallback_used = True
        existing_ids = {c.id for c in sanitized}
        for fallback in fallback_choices:
            if fallback.id in existing_ids:
                continue
            sanitized.append(fallback)
            if len(sanitized) >= 4:
                break

    # ensure intent diversity and at least 4 options
    intents_present = {c.intent_tag for c in sanitized}
    desired_intents = ["talk", "sneak", "fight", "investigate", "travel"]
    if len(sanitized) < 4 or len(intents_present) < 3:
        fallback_used = True
        for template in fallback_choices:
            if template.intent_tag not in intents_present:
                sanitized.append(template)
                intents_present.add(template.intent_tag)
            if len(sanitized) >= 5:
                break

    if len(sanitized) > 5:
        fallback_used = True
        sanitized = sanitized[:5]

    # ensure risk diversity if possible
    risks_present = {c.risk for c in sanitized}
    if "low" not in risks_present or "high" not in risks_present:
        fallback_used = True
        for target_risk, template in zip(["low", "high"], fallback_choices):
            if target_risk not in risks_present:
                sanitized.append(template)
                risks_present.add(target_risk)
        if len(sanitized) > 5:
            sanitized = sanitized[:5]

    return sanitized, fallback_used


def _sanitize_dm_payload(
    payload: Dict,
    state: Dict,
    player_intent: str,
    diff: List[str],
    include_discovery: bool,
    before_state: Optional[Dict],
) -> DMNarration:
    working = dict(payload)
    before = before_state or state
    highlights = summarize_diff(diff, before, state)

    narration = str(working.get("narration") or "").strip()
    recap = str(working.get("recap") or "").strip()
    stakes = str(working.get("stakes") or "").strip()
    if not narration:
        narration = f"The scene shifts after {player_intent}. { ' '.join(diff) or 'Tension lingers.' }"
    if not recap:
        recap = f"Turn {state.get('turn', 0)} recap at {state.get('location', 'the field')}."
    if not stakes:
        stakes = "Each option carries a cost; failure introduces new pressure."
    if not narration.rstrip().endswith("What do you do?"):
        narration = narration.rstrip()
        narration = f"{narration} What do you do?"

    raw_choices = working.get("choices") if isinstance(working.get("choices"), list) else []
    choices, choices_fallback = _sanitize_choices(raw_choices, state)

    if include_discovery and not working.get("discovery_added"):
        working["discovery_added"] = {
            "title": f"Lead near {state.get('location', 'here')}",
            "text": "A clue surfaces, hinting at a hidden path or ally.",
        }

    consequence_echo = derive_consequence_echo(
        working.get("consequence_echo"),
        highlights,
        narration,
        diff,
    )

    return DMNarration(
        narration=narration,
        recap=recap,
        stakes=stakes,
        choices=choices,
        consequence_echo=consequence_echo,
        choices_fallback=choices_fallback or working.get("choices_fallback", False),
        discovery_added=working.get("discovery_added"),
        roll_request=None if not working.get("roll_request") else RollRequest(**working["roll_request"]),
    )


def _opening_defaults(state: Dict, character: Optional[Dict], hook_label: Optional[str]) -> Dict[str, str]:
    location = state.get("location", "a frontier outpost")
    name = (character or {}).get("name", "The hero")
    background = (character or {}).get("background", "Wanderer")
    hook_key = (hook_label or "classic dungeon").strip().lower()
    hook_details = _OPENING_HOOKS.get(hook_key, {})
    problem = hook_details.get("problem", "A sudden disruption threatens the area.")
    reason = hook_details.get("reason", f"Your {background.lower()} past ties you to the trouble.")
    return {
        "scene": f"{name} arrives at {location}, drawn toward a {hook_label or 'classic dungeon'} lead.",
        "problem": problem,
        "reason": reason,
    }


def _enforce_opening_contract(
    narration: str,
    state: Dict,
    character: Optional[Dict],
    hook_label: Optional[str],
) -> str:
    defaults = _opening_defaults(state, character, hook_label)
    lower = narration.lower()
    parts = []
    if "scene:" in lower:
        parts.append(narration.strip())
    else:
        parts.append(f"Scene: {defaults['scene']}")
        parts.append(f"Immediate problem: {defaults['problem']}")
        parts.append(f"Reason: {defaults['reason']}")
    if "immediate problem:" not in lower:
        parts.append(f"Immediate problem: {defaults['problem']}")
    if "reason:" not in lower:
        parts.append(f"Reason: {defaults['reason']}")
    if "question:" not in lower:
        parts.append("Question: What do you do?")
    merged = "\n".join(parts).strip()
    if not merged.endswith("What do you do?"):
        merged = merged.rstrip()
        merged = f"{merged} What do you do?"
    return merged


def _fallback_opening_output(
    state: Dict,
    character: Optional[Dict],
    hook_label: Optional[str],
    player_intent: str,
    diff: List[str],
    include_discovery: bool,
    before_state: Optional[Dict],
) -> DMNarration:
    defaults = _opening_defaults(state, character, hook_label)
    narration = (
        f"Scene: {defaults['scene']}\n"
        f"Immediate problem: {defaults['problem']}\n"
        f"Reason: {defaults['reason']}\n"
        "Question: What do you do?"
    )
    choices, _ = _sanitize_choices([], state)
    recap = f"Opening scene for {state.get('character', 'the hero')}."
    stakes = "Act quickly to shape the tone of this adventure."
    return DMNarration(
        narration=narration,
        recap=recap,
        stakes=stakes,
        choices=choices,
        consequence_echo=derive_consequence_echo(None, summarize_diff(diff, before_state or state, state), narration, diff),
        choices_fallback=True,
    )


def _fallback_dm_output(
    state: Dict,
    player_intent: str,
    diff: List[str],
    include_discovery: bool,
    before_state: Optional[Dict],
) -> DMNarration:
    location = state.get("location", "the current area")
    turn = state.get("turn", 0)
    recap = f"Turn {turn}: {state.get('character', 'The hero')} pushes onward at {location}."
    stakes = "Consequences ripple from each move; risk what you value to advance." if diff else "Small shifts, but pressure builds." 
    changes = diff or ["No major state shifts recorded."]
    narration = (
        f"After choosing '{player_intent}', the scene adjusts: "
        f"{' '.join(changes)}"
    )
    if not narration.endswith("What do you do?"):
        narration = f"{narration} What do you do?"
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
        DMChoice(id="D", text="Study signs or magic traces", intent_tag="investigate", risk="medium"),
        DMChoice(id="E", text="Fall back to regroup and watch", intent_tag="travel", risk="low"),
    ]
    highlights = summarize_diff(diff, before_state or state, state)
    echo = derive_consequence_echo(None, highlights, narration, diff)
    return DMNarration(
        narration=narration,
        recap=recap,
        stakes=stakes,
        choices=base_choices,
        consequence_echo=echo,
        choices_fallback=True,
        discovery_added=discovery,
    )


async def generate_dm_narration(
    settings: Settings,
    slug: str,
    state: Dict,
    before_state: Optional[Dict],
    player_intent: str,
    diff: List[str],
    include_discovery: bool = False,
) -> Tuple[DMNarration, Optional[Dict[str, int]]]:
    prompt = (
        "You are the deterministic DM. Return ONLY valid JSON matching the schema.\n"
        "Schema: {\n"
        "  narration: string, end with 'What do you do?'\n"
        "  recap: string,\n"
        "  stakes: string (1-2 sentences),\n"
        "  choices: array of 4-5 items with fields {id: A/B/C/D/E, text, intent_tag: talk|sneak|fight|magic|investigate|travel|other, risk: low|medium|high},\n"
        "  discovery_added: optional {title, text},\n"
        "  consequence_echo: optional string summarizing the consequence in 1 line,\n"
        "  roll_request: optional {type: ability_check|saving_throw|attack|damage|initiative, ability?: STR|DEX|CON|INT|WIS|CHA, skill?: string, dc?: number, advantage?: advantage|disadvantage|normal, notes?: string}\n"
        "}.\n"
        "Rules: concise, grounded in provided state; keep outputs safe; do not add dice unless roll_request is present. Only include roll_request when a roll is actually needed.\n"
        "Choice contract: Return 4-5 DISTINCT options. Avoid placeholders like 'continue' or 'do nothing'. Label options with varied intent_tag when possible.\n"
        "End narration with a direct invitation: What do you do?\n"
        "When possible, include: one safe/low-risk option, one risky/high-stakes option, one clever/indirect option."
    )
    if include_discovery:
        prompt += " Always include discovery_added describing a new clue or rumor this turn."

    context = {
        "session": slug,
        "state": state,
        "prior_state": before_state,
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
            dm = _sanitize_dm_payload(parsed, state, player_intent, diff, include_discovery, before_state)
            return dm, last_usage
        except Exception as exc:  # noqa: BLE001
            attempts.append(str(exc))
            prompt = (
                "Previous response was invalid JSON. Respond again with ONLY the JSON body per schema."
                " Ensure choices have id, text, intent_tag, and risk."
            )
            continue

    try:
        return _fallback_dm_output(state, player_intent, diff, include_discovery, before_state), last_usage
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build DM narration: {exc}")


async def generate_opening_narration(
    settings: Settings,
    slug: str,
    state: Dict,
    before_state: Optional[Dict],
    player_intent: str,
    diff: List[str],
    character: Optional[Dict],
    hook_label: Optional[str],
    include_discovery: bool = False,
) -> Tuple[DMNarration, Optional[Dict[str, int]]]:
    prompt = (
        "You are the deterministic DM. This is the OPENING scene for a new solo D&D session.\n"
        "Return ONLY valid JSON matching the schema.\n"
        "Schema: {\n"
        "  narration: string (include labeled lines: 'Scene:', 'Immediate problem:', 'Reason:', 'Question:'),\n"
        "  recap: string,\n"
        "  stakes: string (1-2 sentences),\n"
        "  choices: array of 4-5 items with fields {id: A/B/C/D/E, text, intent_tag: talk|sneak|fight|magic|investigate|travel|other, risk: low|medium|high},\n"
        "  discovery_added: optional {title, text},\n"
        "  consequence_echo: optional string summarizing the consequence in 1 line,\n"
        "  roll_request: optional {type: ability_check|saving_throw|attack|damage|initiative, ability?: STR|DEX|CON|INT|WIS|CHA, skill?: string, dc?: number, advantage?: advantage|disadvantage|normal, notes?: string}\n"
        "}.\n"
        "Rules: concise, grounded in provided state; keep outputs safe.\n"
        "Opening contract: narration MUST explicitly state the scene, the immediate problem, why the character is here, "
        "and an explicit question ending with 'What do you do?'.\n"
        "Choice contract: return 4-5 DISTINCT options with varied intent_tag when possible."
    )
    if include_discovery:
        prompt += " Always include discovery_added describing a new clue or rumor this turn."

    context = {
        "session": slug,
        "state": state,
        "prior_state": before_state,
        "player_intent": player_intent,
        "diff": diff,
        "character": character,
        "hook": hook_label,
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
            dm = _sanitize_dm_payload(parsed, state, player_intent, diff, include_discovery, before_state)
            narration = _enforce_opening_contract(dm.narration, state, character, hook_label)
            dm = dm.model_copy(update={"narration": narration})
            return dm, last_usage
        except Exception as exc:  # noqa: BLE001
            attempts.append(str(exc))
            prompt = (
                "Previous response was invalid JSON. Respond again with ONLY the JSON body per schema."
                " Ensure choices have id, text, intent_tag, and risk."
            )
            continue

    try:
        dm = _fallback_opening_output(
            state, character, hook_label, player_intent, diff, include_discovery, before_state
        )
        narration = _enforce_opening_contract(dm.narration, state, character, hook_label)
        dm = dm.model_copy(update={"narration": narration})
        return dm, last_usage
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build opening narration: {exc}")
