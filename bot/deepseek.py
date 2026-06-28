"""Тонкая обёртка над DeepSeek (через OpenAI-совместимый async-клиент)."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from .config import settings

log = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
    timeout=settings.request_timeout,
)


async def complete(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str | None:
    """Запросить у модели одну реплику. При любой ошибке API — None (бот молчит)."""
    try:
        resp = await _client.chat.completions.create(
            model=settings.deepseek_model,
            messages=messages,
            temperature=settings.temperature if temperature is None else temperature,
            max_tokens=settings.max_tokens if max_tokens is None else max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 — мягкая деградация: лучше промолчать, чем упасть
        log.warning("Ошибка DeepSeek API: %s", exc)
        return None

    if not resp.choices:
        return None
    return (resp.choices[0].message.content or "").strip()


async def aclose() -> None:
    try:
        await _client.close()
    except Exception:  # noqa: BLE001
        pass
