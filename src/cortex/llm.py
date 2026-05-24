"""All LLM calls go through this module. Tracks token usage + cost.

Two entry points:
  * complete()       — direct single-turn call, caller picks the Claude model.
                       Kept for Anthropic-only paths (e.g. web_search loops).
  * complete_task()  — routes a logical task name through config/models.yaml,
                       dispatching to the configured provider (Anthropic native
                       or any OpenAI-compatible endpoint) with automatic
                       fallback to a known-good model on provider error.
"""

from __future__ import annotations

import httpx
import structlog
from anthropic import Anthropic

from cortex.config import get_models_config, get_settings

log = structlog.get_logger(__name__)

_client: Anthropic | None = None

# Cumulative usage for the current process (reset on restart)
_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
_cost_usd: float = 0.0


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _record(model: str, input_tokens: int, output_tokens: int) -> None:
    global _cost_usd
    _usage["input_tokens"] += input_tokens
    _usage["output_tokens"] += output_tokens
    prices = get_models_config().get("pricing", {})
    p = prices.get(model)
    if p:
        _cost_usd += (input_tokens / 1_000_000) * p.get("in", 0) + (
            output_tokens / 1_000_000
        ) * p.get("out", 0)


def complete(
    *,
    system: str,
    prompt: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Single-turn Anthropic completion. Returns the first content block's text."""
    text, tin, tout = _call_anthropic(system, prompt, model, max_tokens, temperature)
    _record(model, tin, tout)
    log.debug("llm.complete", model=model, input_tokens=tin, output_tokens=tout)
    return text


def complete_task(
    task: str,
    *,
    system: str,
    prompt: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Route a logical task through config/models.yaml.

    Falls back to the task's configured fallback model (default: Haiku) if the
    primary provider errors, so an unattended cycle survives a provider outage.
    """
    cfg = get_models_config()
    spec = cfg.get("tasks", {}).get(task)
    if spec is None:
        raise KeyError(f"Unknown LLM task '{task}' — add it to config/models.yaml")

    mt = max_tokens if max_tokens is not None else spec.get("max_tokens", 1024)
    temp = temperature if temperature is not None else spec.get("temperature", 0.2)

    try:
        return _dispatch(spec["provider"], spec["model"], system, prompt, mt, temp)
    except Exception as exc:
        fb = spec.get("fallback") or cfg.get("defaults", {}).get("fallback")
        log.warning(
            "llm.task_primary_failed",
            task=task,
            provider=spec.get("provider"),
            model=spec.get("model"),
            error=str(exc)[:200],
            fallback=fb,
        )
        if not fb:
            raise
        return _dispatch(fb["provider"], fb["model"], system, prompt, mt, temp)


def probe(provider: str, model: str) -> tuple[bool, str]:
    """Liveness check for a specific provider+model (no fallback).

    Returns (ok, detail). Used by the 7-day model-refresh job to catch dead
    model ids, auth failures, or unfunded accounts before they break a cycle.
    """
    try:
        out = _dispatch(provider, model, "Reply with the single word OK.", "ping", 8, 0.0)
        return True, out.strip()[:40]
    except Exception as exc:
        return False, str(exc)[:160]


def get_usage() -> dict[str, int]:
    return dict(_usage)


def get_cost_usd() -> float:
    return round(_cost_usd, 4)


# ── Provider dispatch ───────────────────────────────────────────────────────


def _dispatch(
    provider: str, model: str, system: str, prompt: str, max_tokens: int, temperature: float
) -> str:
    providers = get_models_config().get("providers", {})
    pcfg = providers.get(provider)
    if pcfg is None:
        raise KeyError(f"Unknown provider '{provider}' in config/models.yaml")

    kind = pcfg.get("kind")
    if kind == "anthropic":
        text, tin, tout = _call_anthropic(system, prompt, model, max_tokens, temperature)
    elif kind == "openai_compatible":
        text, tin, tout = _call_openai_compatible(
            pcfg, system, prompt, model, max_tokens, temperature
        )
    else:
        raise ValueError(f"Provider '{provider}' has unsupported kind '{kind}'")

    _record(model, tin, tout)
    log.debug(
        "llm.dispatch", provider=provider, model=model, input_tokens=tin, output_tokens=tout
    )
    return text


def _call_anthropic(
    system: str, prompt: str, model: str, max_tokens: int, temperature: float
) -> tuple[str, int, int]:
    client = _get_client()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        resp = client.messages.create(**kwargs)
    except Exception as exc:
        # Some newer models (e.g. Opus 4.7) reject `temperature`. Retry without it.
        if "temperature" in str(exc).lower():
            kwargs.pop("temperature", None)
            resp = client.messages.create(**kwargs)
        else:
            raise
    return resp.content[0].text, resp.usage.input_tokens, resp.usage.output_tokens


def _call_openai_compatible(
    pcfg: dict, system: str, prompt: str, model: str, max_tokens: int, temperature: float
) -> tuple[str, int, int]:
    settings = get_settings()
    api_key = getattr(settings, pcfg["api_key_setting"], "")
    if not api_key:
        raise RuntimeError(f"Missing API key setting '{pcfg['api_key_setting']}'")

    base = pcfg["base_url"].rstrip("/")
    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
