from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from .config import Settings


class EffectiveLLMConfig(BaseModel):
    api_key: Optional[str]
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    source: str


def _config_path(settings: Settings) -> Path:
    return settings.repo_root / ".dm_llm_config.json"


def _load_contract(settings: Settings) -> str:
    contract_path = settings.repo_root / "PROMPTS" / "dm_v3_contract.md"
    if contract_path.exists():
        return contract_path.read_text(encoding="utf-8")
    return (
        "You are the deterministic Dungeon Master for a solo D&D adventure. "
        "Honor the procedures in PROTOCOL.md, consume deterministic dice, and avoid leaking secrets."
    )


def load_persisted_llm_config(settings: Settings) -> Dict[str, Any]:
    path = _config_path(settings)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def persist_llm_config(settings: Settings, config_update: Dict[str, Any]) -> EffectiveLLMConfig:
    path = _config_path(settings)
    current = load_persisted_llm_config(settings)
    current.update({k: v for k, v in config_update.items() if v is not None})
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return get_effective_llm_config(settings)


def get_effective_llm_config(settings: Settings) -> EffectiveLLMConfig:
    persisted = load_persisted_llm_config(settings)
    api_key = persisted.get("api_key") or settings.llm_api_key
    return EffectiveLLMConfig(
        api_key=api_key,
        base_url=persisted.get("base_url") or settings.llm_base_url,
        model=persisted.get("model") or settings.llm_model,
        temperature=float(persisted.get("temperature", settings.llm_temperature)),
        max_tokens=int(persisted.get("max_tokens", settings.llm_max_tokens)),
        source="file" if persisted else "env",
    )


async def call_llm_api(
    settings: Settings,
    prompt: str,
    context: Optional[Dict] = None,
    max_tokens: Optional[int] = None,
) -> str:
    config = get_effective_llm_config(settings)
    if not config.api_key:
        raise HTTPException(
            status_code=400,
            detail="LLM API key not configured. Set DM_SERVICE_LLM_API_KEY or POST /llm/config.",
        )

    messages = [
        {
            "role": "system",
            "content": _load_contract(settings),
        }
    ]

    if context:
        context_str = json.dumps(context, indent=2)
        messages.append(
            {
                "role": "system",
                "content": f"Session context:\n{context_str}",
            }
        )

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": max_tokens or config.max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    f"{config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            except httpx.TimeoutException:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise HTTPException(status_code=504, detail="LLM API timed out")
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM API error (status {e.response.status_code})",
                )
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise HTTPException(
                    status_code=500,
                    detail=f"LLM API call failed: {exc}",
                )
