import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import ValidationError

from .config import Settings
from .llm import call_llm_api
from .diff_highlights import summarize_diff, derive_consequence_echo
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


_RISK_ORDER = ["low", "medium", "high"]
_ALLOWED_INTENTS = {"talk", "sneak", "fight", "magic", "investigate", "travel", "other"}
_BANNED_CHOICE_WORDS = {"continue", "do nothing", "wait", "skip"}


def _default_choices(state: Dict) -> List[DMChoice]:
    location = state.get("location", "this place")
    return [
        DMChoice(id="A", text=f"Ask locals about {location}", intent_tag="talk", risk="low"),
        DMChoice(id="B", text="Probe quietly for weak spots", intent_tag="sneak", risk="medium"),
        DMChoice(id="C", text="Force the issue with bold action", intent_tag="fight", risk="high"),
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

    if len(sanitized) < 2:
        fallback_used = True
        existing_ids = {c.id for c in sanitized}
        for fallback in fallback_choices:
            if fallback.id in existing_ids:
                continue
            sanitized.append(fallback)
            if len(sanitized) >= 3:
                break

    if len(sanitized) > 4:
        fallback_used = True
        sanitized = sanitized[:4]

    # ensure risk diversity if possible
    risks_present = {c.risk for c in sanitized}
    if "low" not in risks_present or "high" not in risks_present:
        fallback_used = True
        for target_risk, template in zip(["low", "high"], fallback_choices):
            if target_risk not in risks_present:
                sanitized.append(template)
                risks_present.add(target_risk)
        sanitized = sanitized[:4]

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
        "  narration: string,\n"
        "  recap: string,\n"
        "  stakes: string (1-2 sentences),\n"
        "  choices: array of 2-4 items with fields {id: A/B/C/D, text, intent_tag: talk|sneak|fight|magic|investigate|travel|other, risk: low|medium|high},\n"
        "  discovery_added: optional {title, text},\n"
        "  consequence_echo: optional string summarizing the consequence in 1 line\n"
        "}.\n"
        "Rules: concise, grounded in provided state; keep outputs safe; do not add dice.\n"
        "Choice contract: Return 2-4 DISTINCT options. Avoid placeholders like 'continue' or 'do nothing'.\n"
        "When possible, include: one safe/low-risk option, one risky/high-stakes option, one clever/indirect option.\n"
        "Vary intent_tag labels when possible to avoid duplicates."
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
