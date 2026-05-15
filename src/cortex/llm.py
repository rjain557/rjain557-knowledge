"""All Claude API calls go through this module. Tracks token usage."""

from __future__ import annotations

import structlog
from anthropic import Anthropic

from cortex.config import get_settings

log = structlog.get_logger(__name__)

_client: Anthropic | None = None

# Cumulative usage for the current process (reset on restart)
_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def complete(
    *,
    system: str,
    prompt: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Single-turn completion. Returns the text of the first content block."""
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    _usage["input_tokens"] += response.usage.input_tokens
    _usage["output_tokens"] += response.usage.output_tokens
    log.debug(
        "llm.complete",
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cumulative_input=_usage["input_tokens"],
        cumulative_output=_usage["output_tokens"],
    )
    return response.content[0].text


def get_usage() -> dict[str, int]:
    return dict(_usage)
